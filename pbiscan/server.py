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
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.engine.issue import IssueGenerator
from pbiscan.engine.scoring import calculate_scores, load_config
from pbiscan.engine.suppressions import load_suppressions, apply_suppressions
from pbiscan.extraction.pbip_reader import PBIPReader, PBIScanError
from pbiscan.render.html_report import HtmlRenderer
from pbiscan.render.sarif_report import SarifRenderer
from pbiscan.render.junit_report import JUnitRenderer
from pbiscan.rules.dax import DAX_RULES
from pbiscan.rules.model import MODEL_RULES
from pbiscan.rules.report import REPORT_RULES

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

    # Load configuration
    config = _get_config(req.config_path)

    # Step 1: Extract
    try:
        reader = PBIPReader()
        raw = reader.read(project_path)
    except PBIScanError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.error_type}: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}")

    # Step 2: Canonical Model
    builder = CanonicalBuilder()
    report = builder.build(raw)

    # Step 3: Rule Evaluation
    thresholds = config.get("thresholds", {})
    max_visuals = thresholds.get("maxVisualsPerPage", 15)
    max_slicers = thresholds.get("maxSlicersPerPage", 6)
    max_calc = thresholds.get("maxCalculatedColumnsPerTable", 4)

    raw_patterns = config.get("dax_suspicious_patterns", [])
    dax_patterns = [(p["pattern"], p["description"]) for p in raw_patterns] or None

    findings = []
    for rule in MODEL_RULES:
        findings.extend(rule(report))

    findings.extend(DAX_RULES[0](report, patterns=dax_patterns))
    findings.extend(DAX_RULES[1](report, threshold=max_calc))
    findings.extend(DAX_RULES[2](report))
    findings.extend(DAX_RULES[3](report))

    findings.extend(REPORT_RULES[0](report, max_visuals=max_visuals))
    findings.extend(REPORT_RULES[1](report, max_slicers=max_slicers))

    # Step 4: Issue Generation
    gen = IssueGenerator()
    issues = gen.generate(findings)

    # Step 4.5: Apply Suppressions
    suppressions = load_suppressions(project_path)
    issues = apply_suppressions(issues, suppressions)

    # Step 5: Scoring
    scores = calculate_scores(issues, config)

    # Serialize structured model objects for frontend
    table_data = [
        {
            "name": t.name,
            "hidden": t.hidden,
            "is_date_table": t.is_date_table,
            "column_count": len(t.columns),
            "columns": [
                {
                    "name": c.name,
                    "data_type": c.data_type,
                    "is_unique": c.is_unique,
                    "in_relationship": c.in_relationship,
                    "hidden": c.hidden,
                }
                for c in t.columns
            ],
            "measures_count": sum(1 for m in report.dax.measures if m.table.lower() == t.name.lower()),
            "calc_cols_count": sum(1 for cc in report.dax.calculated_columns if cc.table.lower() == t.name.lower()),
        }
        for t in report.model.tables
    ]

    rel_data = [
        {
            "from_table": r.from_table,
            "from_column": r.from_column,
            "to_table": r.to_table,
            "to_column": r.to_column,
            "cardinality": r.cardinality,
            "cross_filter_direction": r.cross_filter_direction,
            "is_active": r.is_active,
        }
        for r in report.model.relationships
    ]

    measure_data = [
        {
            "name": m.name,
            "table": m.table,
            "expression": m.expression,
            "hidden": m.hidden,
        }
        for m in report.dax.measures
    ]

    calc_col_data = [
        {
            "name": cc.name,
            "table": cc.table,
            "expression": cc.expression,
            "data_type": cc.data_type,
        }
        for cc in report.dax.calculated_columns
    ]

    # Step 6: Extract Semantic References & DAG info for frontend visualization
    sem_refs = report.semantic_references
    sem_ref_data = {
        "total_count": len(sem_refs),
        "active_roots": list(sem_refs.active_root_measure_names()),
        "references": [
            {
                "target_name": r.target_name,
                "target_table": r.target_table,
                "target_type": r.target_type,
                "source_type": r.source_type,
                "source_object": r.source_object,
                "source_file": r.source_file,
                "source_expression": r.source_expression,
                "activates_root": r.activates_root,
            }
            for r in sem_refs.references
        ],
    }

    # Build DAX DAG node & edge data
    dax_graph = report.dax_graph
    dax_nodes = []
    dax_edges = []
    if dax_graph:
        for node_name, node in dax_graph.nodes.items():
            meas_expr = next((m.expression for m in report.dax.measures if m.name.lower() == node.name.lower()), "")
            dax_nodes.append({
                "name": node.name,
                "table": node.table,
                "kind": node.kind,
                "expression": meas_expr,
                "references": list(dax_graph.references(node.name)),
                "referenced_by": list(dax_graph.referenced_by(node.name)),
            })
            for target in dax_graph.references(node.name):
                dax_edges.append({
                    "source": node.name,
                    "target": target,
                })

    page_data = [
        {
            "name": p.name,
            "display_name": p.display_name or p.name,
            "is_hidden": p.is_hidden,
            "visual_count": p.visual_count,
            "slicer_count": p.slicer_count,
            "visuals": [
                {
                    "visual_type": v.visual_type,
                    "measure_refs": v.measure_refs,
                    "fields_used": v.fields_used,
                    "is_slicer": v.is_slicer,
                    "hidden": v.hidden,
                }
                for v in p.visuals
            ],
        }
        for p in report.report.pages
    ]

    issue_data = [
        {
            "rule_id": i.rule_id,
            "category": i.category,
            "severity": i.severity,
            "title": i.title,
            "issue": i.issue,
            "evidence": i.evidence,
            "impact": i.impact,
            "recommendation": i.recommendation,
            "confidence": i.confidence,
            "location": i.location,
            "suppressed": i.suppressed,
            "suppression_reason": i.suppression_reason,
        }
        for i in issues
    ]

    return {
        "report_name": report.report_name,
        "source_path": report.source_path,
        "scores": scores,
        "findings": issue_data,
        "tables": table_data,
        "relationships": rel_data,
        "measures": measure_data,
        "calculated_columns": calc_col_data,
        "pages": page_data,
        "semantic_references": sem_ref_data,
        "dax_graph": {
            "nodes": dax_nodes,
            "edges": dax_edges,
            "has_cycles": bool(dax_graph.find_cycles()) if dax_graph else False,
            "cycles": dax_graph.find_cycles() if dax_graph else [],
        },
        "warnings": raw.warnings,
        "summary": {
            "total_findings": len(issues),
            "table_count": len(table_data),
            "relationship_count": len(rel_data),
            "measure_count": len(measure_data),
            "page_count": len(page_data),
            "semantic_reference_count": len(sem_refs),
            "active_root_count": len(sem_refs.active_root_measure_names()),
        },
    }


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
    """Add a suppression rule to the project's .pbiscanignore file."""
    proj_path = Path(req.project_path)
    if not proj_path.exists():
        raise HTTPException(status_code=404, detail="Project path does not exist")

    ignore_file = proj_path if proj_path.is_file() else proj_path / ".pbiscanignore"
    if ignore_file.suffix == ".pbip":
        ignore_file = ignore_file.parent / ".pbiscanignore"

    line = f"{req.rule_id} {req.location}  # {req.reason}\n"
    with open(ignore_file, "a", encoding="utf-8") as f:
        f.write(line)

    return {"status": "ok", "message": f"Added suppression to {ignore_file.name}", "line": line.strip()}


@app.post("/api/export")
async def export_audit(req: ExportRequest):
    """Generate export content in specified format (html, json, sarif, junit)."""
    proj_path = Path(req.project_path)
    if not proj_path.exists():
        raise HTTPException(status_code=404, detail="Project path does not exist")

    reader = PBIPReader()
    raw = reader.read(proj_path)
    builder = CanonicalBuilder()
    report = builder.build(raw)

    findings = []
    for r in MODEL_RULES:
        findings.extend(r(report))
    findings.extend(DAX_RULES[0](report))
    findings.extend(DAX_RULES[1](report))
    findings.extend(DAX_RULES[2](report))
    findings.extend(DAX_RULES[3](report))
    findings.extend(REPORT_RULES[0](report))
    findings.extend(REPORT_RULES[1](report))

    gen = IssueGenerator()
    issues = gen.generate(findings)
    suppressions = load_suppressions(proj_path)
    issues = apply_suppressions(issues, suppressions)
    scores = calculate_scores(issues, _get_config(req.config_path))

    fmt = req.format.lower()
    if fmt == "json":
        import json
        data = {
            "report_name": report.report_name,
            "scanner_version": __version__,
            "scores": scores,
            "findings": [
                {
                    "rule_id": i.rule_id,
                    "category": i.category,
                    "severity": i.severity,
                    "title": i.title,
                    "evidence": i.evidence,
                    "impact": i.impact,
                    "recommendation": i.recommendation,
                    "confidence": i.confidence,
                    "location": i.location,
                    "suppressed": i.suppressed,
                }
                for i in issues
            ],
        }
        return {"content": json.dumps(data, indent=2), "mime": "application/json", "filename": f"{report.report_name}-audit.json"}
    elif fmt == "sarif":
        sarif_text = SarifRenderer().render(issues=issues, report_path=req.project_path)
        return {"content": sarif_text, "mime": "application/json", "filename": f"{report.report_name}.sarif"}
    elif fmt == "junit":
        junit_text = JUnitRenderer().render(issues=issues, scores=scores, report_name=report.report_name)
        return {"content": junit_text, "mime": "application/xml", "filename": f"{report.report_name}-junit.xml"}
    else:
        html_text = HtmlRenderer().render(
            issues=issues,
            scores=scores,
            meta={"report_name": report.report_name, "scanner_version": __version__, "source_path": req.project_path, "scan_timestamp": ""},
        )
        return {"content": html_text, "mime": "text/html", "filename": f"{report.report_name}-audit.html"}


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
