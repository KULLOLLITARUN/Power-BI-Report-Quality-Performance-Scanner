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
from pbiscan.extraction.pbip_reader import PBIScanError
from pbiscan.service import ScanService, resolve_config

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
    mode = req.mode if req else "file"
    return await asyncio.to_thread(_show_dialog_sync, mode)


def _get_config(config_path: Optional[str] = None) -> dict:
    """Helper to load config or return default weights/deductions."""
    cfg_file = config_path or "rules.config.json"
    if Path(cfg_file).exists():
        try:
            return load_config(cfg_file)
        except Exception:
            pass
    return {
        "weights": {"model": 0.35, "dax": 0.25, "report": 0.20, "security": 0.20},
        "deductions": {"CRITICAL": 15, "HIGH": 10, "MEDIUM": 5, "WARNING": 3, "ADVISORY": 1, "LOW": 2},
        "thresholds": {"maxVisualsPerPage": 15, "maxSlicersPerPage": 6, "maxCalculatedColumnsPerTable": 4},
    }


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

    data = {"suppressions": []}
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
