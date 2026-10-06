"""pbiscan Studio — FastAPI Backend API Server.

Serves endpoints for project scanning, filesystem browsing, and static React SPA.
"""
from __future__ import annotations

import logging
import os
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from pbiscan import __version__
from pbiscan.diff import DiffService, QualityGatePolicy
from pbiscan.engine.scoring import ConfigError
from pbiscan.engine.suppressions import SuppressionFileError, add_suppression
from pbiscan.extraction.pbip_reader import PBIScanError
from pbiscan.service import ScanService

app = FastAPI(
    title="pbiscan Studio API",
    version=__version__,
    description="Backend API powering pbiscan Studio developer dashboard",
)

# Studio exposes filesystem browse/read/write endpoints, so it must only ever be
# driven by its own SPA (same-origin) or the local Vite dev server. Any other
# website open in the user's browser must not be able to call it.
DEV_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}

# Per-run access token. The Host/Origin checks stop web pages; this stops other
# local processes (another user's, or a sandboxed one that can reach loopback)
# from driving the API. `pbiscan studio` generates it, passes it here through
# the environment, and opens the browser at /?token=<it>; the SPA then sends it
# in TOKEN_HEADER on every /api/* call. Setting PBISCAN_STUDIO_TOKEN yourself
# pins it (e.g. for the Vite dev server).
TOKEN_ENV = "PBISCAN_STUDIO_TOKEN"
TOKEN_HEADER = "X-PBIScan-Token"
STUDIO_TOKEN = os.environ.get(TOKEN_ENV) or secrets.token_urlsafe(32)
TOKEN_EXEMPT_PATHS = {"/api/health"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(DEV_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", TOKEN_HEADER],
)


def _allowed_hosts() -> set[str]:
    """Loopback names plus any extra hosts from PBISCAN_STUDIO_ALLOWED_HOSTS
    (comma-separated), set by `pbiscan studio --host <non-loopback>`."""
    extra = os.environ.get("PBISCAN_STUDIO_ALLOWED_HOSTS", "")
    return LOOPBACK_HOSTS | {h.strip().lower() for h in extra.split(",") if h.strip()}


def _strip_port(host: str) -> str:
    host = host.strip().lower()
    if host.startswith("["):
        return host.split("]", 1)[0] + "]"
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


@app.middleware("http")
async def local_origin_guard(request: Request, call_next):
    """Reject DNS-rebinding (foreign Host header) and cross-site requests
    (foreign Origin header) before they reach any endpoint."""
    host_header = request.headers.get("host", "")
    if _strip_port(host_header) not in _allowed_hosts():
        return JSONResponse(status_code=403, content={"detail": "Host not allowed"})

    origin = request.headers.get("origin")
    if origin is not None:
        allowed_origins = {f"http://{host_header.lower()}", f"https://{host_header.lower()}", *DEV_ORIGINS}
        if origin.lower() not in allowed_origins:
            return JSONResponse(status_code=403, content={"detail": "Origin not allowed"})

    path = request.url.path
    if path.startswith("/api/") and path not in TOKEN_EXEMPT_PATHS and request.method != "OPTIONS":
        supplied = request.headers.get(TOKEN_HEADER, "")
        if not secrets.compare_digest(supplied.encode(), STUDIO_TOKEN.encode()):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Missing or invalid Studio access token. Open Studio from the "
                              "URL printed by `pbiscan studio`."
                },
            )

    return await call_next(request)

logger = logging.getLogger(__name__)


def _internal_error(action: str, exc: Exception) -> HTTPException:
    """Log the full traceback server-side; return only a short message to the client."""
    logger.error("%s", action, exc_info=exc)
    return HTTPException(
        status_code=500,
        detail=f"{action} ({type(exc).__name__}). See the pbiscan Studio console for details.",
    )


def _existing_path(raw: str, label: str = "Path") -> Path:
    """Return `raw` as a Path, or raise 404 if nothing exists there."""
    path = Path(raw)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{label} does not exist: {raw}")
    return path


@contextmanager
def _error_responses(action: str) -> Iterator[None]:
    """Map engine errors to HTTP responses for one endpoint.

    Problems the user can fix in their input (bad project, bad config) become
    422, an existing suppressions file we refuse to overwrite becomes 409, and
    anything unexpected becomes a 500 whose details stay in the server log.
    """
    try:
        yield
    except HTTPException:
        raise
    except (PBIScanError, ConfigError) as exc:
        raise HTTPException(status_code=422, detail=f"{exc.error_type}: {exc}")
    except SuppressionFileError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise _internal_error(action, exc)


# Path to static frontend build
STATIC_DIR = Path(__file__).parent / "studio" / "dist"


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    path: str
    config_path: Optional[str] = None


class BrowseRequest(BaseModel):
    path: Optional[str] = None


class SuppressRequest(BaseModel):
    project_path: str
    rule_id: str
    location: str
    reason: Optional[str] = "Suppressed via Studio"


class ExportRequest(BaseModel):
    project_path: str
    format: str  # "html", "json", "sarif", "junit"
    config_path: Optional[str] = None


class DiffRequest(BaseModel):
    baseline_path: str
    current_path: str
    config_path: Optional[str] = None
    fail_on_regression: Optional[bool] = False
    max_score_drop: Optional[float] = None
    fail_on_new: Optional[str] = None
    fail_on_category_regression: Optional[str] = None


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": __version__, "service": "pbiscan-studio"}


class DialogRequest(BaseModel):
    mode: Optional[str] = "file"  # "file" or "folder"


def _show_dialog_sync(mode: str) -> dict:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        root.update()

        if mode == "folder":
            selected_path = filedialog.askdirectory(title="Select Power BI Project Folder")
        else:
            selected_path = filedialog.askopenfilename(
                title="Select Power BI Project (.pbip) File",
                filetypes=[
                    ("Power BI Projects (*.pbip)", "*.pbip"),
                    ("All Files (*.*)", "*.*"),
                ],
            )

        root.destroy()
        if selected_path:
            return {"path": os.path.normpath(selected_path), "canceled": False}
        return {"path": "", "canceled": True}
    except Exception as exc:
        logger.error("Native file dialog failed", exc_info=exc)
        return {
            "path": "",
            "canceled": True,
            "error": "Could not open the file picker. See the pbiscan Studio console for details.",
        }


@app.post("/api/native-dialog")
async def open_native_dialog(req: Optional[DialogRequest] = None):
    """Open native Windows file/folder picker dialog asynchronously."""
    import asyncio
    mode = req.mode if (req and req.mode) else "file"
    return await asyncio.to_thread(_show_dialog_sync, mode)


@app.post("/api/scan")
async def scan_project(req: ScanRequest):
    """Scan a PBIP project and return structured quality audit data."""
    project_path = _existing_path(req.path)
    with _error_responses("Scan failed"):
        result = ScanService.execute_scan(project_path=project_path, config_path=req.config_path)
        return result.to_dict()


@app.post("/api/browse")
async def browse_filesystem(req: BrowseRequest):
    """Browse directories on the local host to pick PBIP projects."""
    target_path = Path(req.path) if req.path else Path.cwd()

    if not target_path.exists():
        target_path = Path.cwd()

    directories = []
    pbip_projects = []

    try:
        if target_path.is_file():
            target_path = target_path.parent

        for entry in os.scandir(target_path):
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                is_pbip = (
                    any(f.name.endswith(".pbip") for f in os.scandir(entry.path) if f.is_file())
                    or (entry.name.endswith(".pbip"))
                    or (entry.name.endswith(".SemanticModel"))
                )
                if is_pbip or entry.name.endswith(".pbip"):
                    pbip_projects.append({"name": entry.name, "path": entry.path})
                else:
                    directories.append({"name": entry.name, "path": entry.path})
            elif entry.is_file() and entry.name.endswith(".pbip"):
                pbip_projects.append({"name": entry.name, "path": entry.path})
    except PermissionError:
        pass

    return {
        "current_path": str(target_path.resolve()),
        "parent_path": str(target_path.parent.resolve()) if target_path.parent != target_path else None,
        "directories": sorted(directories, key=lambda x: x["name"].lower()),
        "pbip_projects": sorted(pbip_projects, key=lambda x: x["name"].lower()),
    }


@app.post("/api/suppress")
async def suppress_finding(req: SuppressRequest):
    """Add a suppression rule to the project's pbiscan.suppressions.json file."""
    proj_path = _existing_path(req.project_path, "Project path")
    with _error_responses("Adding suppression failed"):
        supp_file, _ = add_suppression(
            proj_path, req.rule_id, req.location, req.reason or "Suppressed via Studio", added_by="pbiscan Studio",
        )
    return {"status": "ok", "message": f"Added suppression to {supp_file.name}"}


@app.post("/api/export")
async def export_audit(req: ExportRequest):
    """Generate export content in specified format (html, json, sarif, junit)."""
    proj_path = _existing_path(req.project_path, "Project path")
    with _error_responses("Export failed"):
        result = ScanService.execute_scan(project_path=proj_path, config_path=req.config_path)

    fmt = req.format.lower()
    if fmt == "json":
        return {"content": result.to_json(), "mime": "application/json", "filename": f"{result.report_name}-audit.json"}
    elif fmt == "sarif":
        return {"content": result.to_sarif(), "mime": "application/json", "filename": f"{result.report_name}.sarif"}
    elif fmt == "junit":
        return {"content": result.to_junit(), "mime": "application/xml", "filename": f"{result.report_name}-junit.xml"}
    else:
        return {"content": result.to_html(), "mime": "text/html", "filename": f"{result.report_name}-audit.html"}


@app.post("/api/diff")
async def diff_audit(req: DiffRequest):
    """Compare two scans (PBIP directories or JSON artifacts) and return canonical DiffResult."""
    base_path = _existing_path(req.baseline_path, "Baseline path")
    curr_path = _existing_path(req.current_path, "Current path")

    policy = QualityGatePolicy(
        fail_on_regression=req.fail_on_regression or False,
        max_score_drop=req.max_score_drop,
        fail_on_new=req.fail_on_new,
        fail_on_category_regression=req.fail_on_category_regression,
    )

    with _error_responses("Diff failed"):
        diff_res = DiffService.compare(
            baseline=base_path,
            current=curr_path,
            policy=policy,
            config_path=req.config_path,
        )
        return diff_res.to_dict()


# ---------------------------------------------------------------------------
# Remediation Subsystem Endpoints
# ---------------------------------------------------------------------------

class RemediationPlanRequest(BaseModel):
    project_path: str
    config_path: Optional[str] = None
    rule_filter: Optional[str] = None


class RemediationApplyRequest(BaseModel):
    project_path: str
    patch_ids: Optional[list[str]] = None
    backup: bool = True
    config_path: Optional[str] = None


@app.post("/api/remediation/plan")
async def plan_remediation(req: RemediationPlanRequest):
    """Analyze and generate candidate safe remediation plan with sandbox validation."""
    proj_path = _existing_path(req.project_path, "Project path")
    with _error_responses("Remediation planning failed"):
        from pbiscan.remediation.engine import RemediationEngine
        scan_res = RemediationEngine.analyze(proj_path, config_path=req.config_path)
        plan = RemediationEngine.plan(proj_path, scan_res, rule_filter=req.rule_filter)
        validation = RemediationEngine.validate(plan, scan_res, config_path=req.config_path)
        return {
            "plan": plan.to_dict(),
            "validation": validation.to_dict(),
            "baseline_score": scan_res.overall_score,
            "project_name": proj_path.name,
        }


@app.post("/api/remediation/apply")
async def apply_remediation(req: RemediationApplyRequest):
    """Apply approved remediation patches with atomic backup, sandbox re-verification, and audit trail."""
    proj_path = _existing_path(req.project_path, "Project path")
    with _error_responses("Remediation apply failed"):
        from pbiscan.remediation.engine import RemediationEngine
        scan_res = RemediationEngine.analyze(proj_path, config_path=req.config_path)
        plan = RemediationEngine.plan(proj_path, scan_res)
        if req.patch_ids:
            plan = plan.filter_by_patch_ids(req.patch_ids)
        validation = RemediationEngine.validate(plan, scan_res, config_path=req.config_path)
        success, manifest = RemediationEngine.apply(
            plan=plan,
            validation_result=validation,
            backup=req.backup,
            config_path=req.config_path,
            original_scan=scan_res,
        )
        return {
            "success": success,
            "manifest": manifest.to_dict(),
        }


@app.get("/api/remediation/history")
async def get_remediation_history(project_path: str):
    """Fetch all past remediation audit manifests for a project."""
    proj_path = _existing_path(project_path, "Project path")
    with _error_responses("Failed to retrieve remediation history"):
        from pbiscan.remediation.store import RemediationAuditStore
        history = RemediationAuditStore.list_manifests(proj_path)
        return {"history": history}


@app.get("/api/remediation/manifest/{manifest_id}")
async def get_remediation_manifest(manifest_id: str, project_path: str):
    """Retrieve full detail for a specific remediation audit manifest."""
    proj_path = _existing_path(project_path, "Project path")
    with _error_responses("Failed to retrieve manifest"):
        from pbiscan.remediation.store import RemediationAuditStore
        manifest = RemediationAuditStore.get_manifest(manifest_id, proj_path)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Remediation manifest not found: {manifest_id}")
    return manifest.to_dict()


# ---------------------------------------------------------------------------
# Agent / MCP Integration (informational — never requires the `mcp` extra to
# render; only live tool introspection needs it, with a static fallback)
# ---------------------------------------------------------------------------

@app.get("/api/mcp/status")
async def mcp_status():
    """Report whether the optional `mcp` extra is installed, and the exact
    command an AI agent host should be configured to run."""
    import importlib.util
    import sys

    spec = importlib.util.find_spec("mcp")
    mcp_version = None
    if spec is not None:
        try:
            import mcp as _mcp_pkg
            mcp_version = getattr(_mcp_pkg, "__version__", None)
        except Exception:
            mcp_version = None

    from pbiscan.mcp.groq_client import DEFAULT_GROQ_MODEL, is_groq_configured

    groq_configured = is_groq_configured()  # also loads .env, matching the rewrite tool
    groq_model = os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)

    return {
        "mcp_installed": spec is not None,
        "mcp_version": mcp_version,
        "python_executable": sys.executable,
        "server_command": "pbiscan",
        "server_args": ["mcp"],
        "groq_configured": groq_configured,
        "groq_model": groq_model,
    }


@app.post("/api/dax/rewrite")
async def dax_rewrite_endpoint(payload: dict):
    """Invoke Groq AI directly from the UI to optimize and explain a DAX expression."""
    from pbiscan.mcp.tools import handle_suggest_dax_rewrite

    rule_id = payload.get("rule_id", "DAX_SUSPICIOUS_PATTERN")
    dax_expression = payload.get("dax_expression", "")
    evidence = payload.get("evidence", "")

    if not dax_expression:
        raise HTTPException(status_code=400, detail="dax_expression is required")

    return handle_suggest_dax_rewrite(
        rule_id=rule_id,
        dax_expression=dax_expression,
        evidence=evidence,
    )


@app.get("/api/mcp/tools")
async def mcp_tools():
    """List the MCP tool surface and its read-only/destructive classification.

    Introspects a real, live server (with its actual protocol-level
    ToolAnnotations) when the `mcp` extra is installed; otherwise falls back
    to the same READ_ONLY_TOOL_NAMES/DESTRUCTIVE_TOOL_NAMES constants the real
    server registers from, so the two can never silently disagree.
    """
    from pbiscan.mcp.server import DESTRUCTIVE_TOOL_NAMES, MCP_AVAILABLE, READ_ONLY_TOOL_NAMES, create_server

    if MCP_AVAILABLE:
        server = create_server()
        live_tools = server._tool_manager.list_tools()
        return {
            "live": True,
            "tools": [
                {
                    "name": t.name,
                    "description": (t.description or "").strip().splitlines()[0] if t.description else "",
                    "read_only": bool(t.annotations and t.annotations.readOnlyHint),
                    "destructive": bool(t.annotations and t.annotations.destructiveHint),
                }
                for t in live_tools
            ],
        }

    return {
        "live": False,
        "message": "Install pbiscan[mcp] to verify live protocol annotations.",
        "tools": (
            [{"name": n, "description": "", "read_only": True, "destructive": False} for n in READ_ONLY_TOOL_NAMES]
            + [{"name": n, "description": "", "read_only": False, "destructive": True} for n in DESTRUCTIVE_TOOL_NAMES]
        ),
    }


@app.get("/api/mcp/rules")
async def mcp_rules():
    """Return the rule catalog (same content the MCP `pbiscan://rules`
    resource serves to an agent) — no `mcp` dependency needed for this."""
    import json as json_mod
    from pbiscan.mcp.resources import get_rules_catalog_json
    return json_mod.loads(get_rules_catalog_json())


# ---------------------------------------------------------------------------
# SPA Static File Fallback Handler
# ---------------------------------------------------------------------------

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve static React SPA with fallback to index.html for client routing."""
    if not STATIC_DIR.exists():
        return {
            "message": "pbiscan Studio API is running.",
            "note": "React frontend in studio-ui/",
            "api_endpoints": ["/api/health", "/api/scan", "/api/browse", "/docs"],
        }

    # Reject traversal syntax outright rather than relying on resolve(): a backslash
    # is a separator on Windows but an ordinary filename character on Linux, so the
    # same request would otherwise be blocked on one OS and fall through to
    # index.html on the other.
    if "\\" in full_path or ".." in full_path.split("/"):
        raise HTTPException(status_code=404, detail="Not found")

    static_root = STATIC_DIR.resolve()
    file_path = (static_root / full_path).resolve()
    if not file_path.is_relative_to(static_root):
        raise HTTPException(status_code=404, detail="Not found")
    if file_path.is_file():
        return FileResponse(file_path)

    index_html = STATIC_DIR / "index.html"
    if index_html.exists():
        return FileResponse(index_html)

    return {"message": "index.html not found"}


def start_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Start the Uvicorn web server (development entry point; `pbiscan studio` is the usual one)."""
    import uvicorn
    # Reload runs the app in a child process; the environment carries the same token there.
    os.environ[TOKEN_ENV] = STUDIO_TOKEN
    print(f"pbiscan Studio: http://{host}:{port}/?token={STUDIO_TOKEN}")
    uvicorn.run("pbiscan.server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    start_server(reload=True)
