"""pbiscan Studio — FastAPI Backend API Server.

Serves endpoints for project scanning, filesystem browsing, and static React SPA.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from pbiscan import __version__
from pbiscan.diff import DiffService, QualityGatePolicy
from pbiscan.extraction.pbip_reader import PBIScanError
from pbiscan.service import ScanService

app = FastAPI(
    title="pbiscan Studio API",
    version=__version__,
    description="Backend API powering pbiscan Studio developer dashboard",
)

# Enable CORS for local Vite development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        return {"path": "", "canceled": True, "error": str(exc)}


@app.post("/api/native-dialog")
async def open_native_dialog(req: Optional[DialogRequest] = None):
    """Open native Windows file/folder picker dialog asynchronously."""
    import asyncio
    mode = req.mode if (req and req.mode) else "file"
    return await asyncio.to_thread(_show_dialog_sync, mode)


@app.post("/api/scan")
async def scan_project(req: ScanRequest):
    """Scan a PBIP project and return structured quality audit data."""
    project_path = Path(req.path)

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Path does not exist: {req.path}")

    try:
        result = ScanService.execute_scan(
            project_path=project_path,
            config_path=req.config_path,
        )
        return result.to_dict()
    except PBIScanError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.error_type}: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scan failed: {exc}")


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
async def add_suppression(req: SuppressRequest):
    """Add a suppression rule to the project's pbiscan.suppressions.json file."""
    proj_path = Path(req.project_path)
    if not proj_path.exists():
        raise HTTPException(status_code=404, detail="Project path does not exist")

    supp_dir = proj_path if proj_path.is_dir() else proj_path.parent
    supp_file = supp_dir / "pbiscan.suppressions.json"

    data: dict[str, Any] = {"suppressions": []}
    if supp_file.exists():
        try:
            import json as json_mod
            data = json_mod.loads(supp_file.read_text(encoding="utf-8"))
            if not isinstance(data.get("suppressions"), list):
                data["suppressions"] = []
        except Exception:
            data = {"suppressions": []}

    data["suppressions"].append({
        "rule_id": req.rule_id,
        "location": req.location,
        "reason": req.reason or "Suppressed via Studio",
    })

    import json as json_mod
    supp_file.write_text(json_mod.dumps(data, indent=2), encoding="utf-8")

    return {"status": "ok", "message": f"Added suppression to {supp_file.name}"}


@app.post("/api/export")
async def export_audit(req: ExportRequest):
    """Generate export content in specified format (html, json, sarif, junit)."""
    proj_path = Path(req.project_path)
    if not proj_path.exists():
        raise HTTPException(status_code=404, detail="Project path does not exist")

    try:
        result = ScanService.execute_scan(
            project_path=proj_path,
            config_path=req.config_path,
        )
    except PBIScanError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.error_type}: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}")

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
    base_path = Path(req.baseline_path)
    if not base_path.exists():
        raise HTTPException(status_code=404, detail=f"Baseline path does not exist: {req.baseline_path}")

    curr_path = Path(req.current_path)
    if not curr_path.exists():
        raise HTTPException(status_code=404, detail=f"Current path does not exist: {req.current_path}")

    policy = QualityGatePolicy(
        fail_on_regression=req.fail_on_regression or False,
        max_score_drop=req.max_score_drop,
        fail_on_new=req.fail_on_new,
        fail_on_category_regression=req.fail_on_category_regression,
    )

    try:
        diff_res = DiffService.compare(
            baseline=base_path,
            current=curr_path,
            policy=policy,
            config_path=req.config_path,
        )
        return diff_res.to_dict()
    except PBIScanError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.error_type}: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Diff failed: {exc}")


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
    proj_path = Path(req.project_path)
    if not proj_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {req.project_path}")

    try:
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
    except PBIScanError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.error_type}: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Remediation planning failed: {exc}")


@app.post("/api/remediation/apply")
async def apply_remediation(req: RemediationApplyRequest):
    """Apply approved remediation patches with atomic backup, sandbox re-verification, and audit trail."""
    proj_path = Path(req.project_path)
    if not proj_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {req.project_path}")

    try:
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
    except PBIScanError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.error_type}: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Remediation apply failed: {exc}")


@app.get("/api/remediation/history")
async def get_remediation_history(project_path: str):
    """Fetch all past remediation audit manifests for a project."""
    proj_path = Path(project_path)
    if not proj_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    try:
        from pbiscan.remediation.store import RemediationAuditStore
        history = RemediationAuditStore.list_manifests(proj_path)
        return {"history": history}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve remediation history: {exc}")


@app.get("/api/remediation/manifest/{manifest_id}")
async def get_remediation_manifest(manifest_id: str, project_path: str):
    """Retrieve full detail for a specific remediation audit manifest."""
    proj_path = Path(project_path)
    if not proj_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    try:
        from pbiscan.remediation.store import RemediationAuditStore
        manifest = RemediationAuditStore.get_manifest(manifest_id, proj_path)
        if not manifest:
            raise HTTPException(status_code=404, detail=f"Remediation manifest not found: {manifest_id}")
        return manifest.to_dict()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve manifest: {exc}")


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

    import os
    groq_key = os.environ.get("GROQ_API_KEY")
    masked_key = f"{groq_key[:6]}...{groq_key[-4:]}" if groq_key and len(groq_key) > 10 else ("Configured" if groq_key else None)
    groq_model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

    return {
        "mcp_installed": spec is not None,
        "mcp_version": mcp_version,
        "python_executable": sys.executable,
        "server_command": "pbiscan",
        "server_args": ["mcp"],
        "groq_configured": bool(groq_key),
        "groq_masked_key": masked_key,
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
    """Return the static 13-rule catalog (same content the MCP `pbiscan://rules`
    resource serves to an agent) — no `mcp` dependency needed for this."""
    import json as json_mod
    from pbiscan.mcp.resources import get_rules_catalog_json
    return json_mod.loads(get_rules_catalog_json())


@app.get("/api/mcp/config-snippets")
async def mcp_config_snippets():
    """Generate ready-to-paste MCP client configuration snippets for common
    AI agent hosts, using the actual command a user would run locally."""
    server_entry = {"command": "pbiscan", "args": ["mcp"]}

    return {
        "claude_desktop": {
            "file": "claude_desktop_config.json",
            "snippet": {"mcpServers": {"pbip-sentinel": server_entry}},
        },
        "cursor": {
            "file": ".cursor/mcp.json",
            "snippet": {"mcpServers": {"pbip-sentinel": server_entry}},
        },
        "claude_code_cli": {
            "file": None,
            "snippet": "claude mcp add pbip-sentinel -- pbiscan mcp",
        },
        "vscode_cline_roo": {
            "file": "cline_mcp_settings.json",
            "snippet": {"mcpServers": {"pbip-sentinel": server_entry}},
        },
    }


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

    file_path = STATIC_DIR / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    index_html = STATIC_DIR / "index.html"
    if index_html.exists():
        return FileResponse(index_html)

    return {"message": "index.html not found"}


def start_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Start the Uvicorn web server."""
    import uvicorn
    uvicorn.run("pbiscan.server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    start_server(reload=True)
