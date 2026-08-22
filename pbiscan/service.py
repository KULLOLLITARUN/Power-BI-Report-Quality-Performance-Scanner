"""pbiscan Canonical Scan Service.

Consolidates extraction, canonical building, configuration resolution,
rule execution, suppression application, scoring, and multi-format rendering
into a single canonical execution pipeline.

Guarantees the core invariant:
    Same input + same configuration = same canonical scan result
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pbiscan import __version__
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.canonical.model import CanonicalReport
from pbiscan.engine.issue import AuditIssue, IssueGenerator
from pbiscan.engine.scoring import calculate_scores, load_config
from pbiscan.engine.suppressions import load_suppressions, apply_suppressions
from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.render.html_report import HtmlRenderer
from pbiscan.render.sarif_report import SarifRenderer
from pbiscan.render.junit_report import JUnitRenderer
from pbiscan.rules.dax import (
    check_suspicious_dax,
    check_excessive_calc_columns,
    check_duplicate_measures,
    check_unused_measures,
)
from pbiscan.rules.model import MODEL_RULES
from pbiscan.rules.report import (
    check_visual_bloat,
    check_slicer_bloat,
)

DEFAULT_CONFIG: dict[str, Any] = {
    "weights": {"model": 0.35, "dax": 0.25, "report": 0.20, "security": 0.20},
    "deductions": {"CRITICAL": 15, "HIGH": 10, "MEDIUM": 5, "WARNING": 3, "ADVISORY": 1, "LOW": 2},
    "thresholds": {"maxVisualsPerPage": 15, "maxSlicersPerPage": 6, "maxCalculatedColumnsPerTable": 4},
}


def resolve_config(
    config_path: Optional[str | Path] = None,
    explicit_config: Optional[dict] = None,
    project_path: Optional[str | Path] = None,
) -> dict:
    """Resolve and validate the configuration dictionary.

    Resolution order:
    1. explicit_config dictionary if provided
    2. config_path file if provided and exists
    3. .pbiscan.config.json inside project_path directory (if project_path provided)
    4. rules.config.json in current working directory
    5. rules.config.json in package root
    6. DEFAULT_CONFIG fallback
    """
    if explicit_config is not None:
        return explicit_config

    if config_path:
        cp = Path(config_path)
        if cp.exists():
            return load_config(cp)

    if project_path:
        pp = Path(project_path)
        proj_cfg = pp / ".pbiscan.config.json" if pp.is_dir() else pp.parent / ".pbiscan.config.json"
        if proj_cfg.exists():
            try:
                return load_config(proj_cfg)
            except Exception:
                pass

    local = Path("rules.config.json")
    if local.exists():
        try:
            return load_config(local)
        except Exception:
            pass

    package_root = Path(__file__).parent.parent / "rules.config.json"
    if package_root.exists():
        try:
            return load_config(package_root)
        except Exception:
            pass

    return DEFAULT_CONFIG.copy()


@dataclass
class ScanResult:
    """Canonical scan result containing raw model, issues, scores, and metadata."""

    report_name: str
    source_path: str
    report: Optional[CanonicalReport]
    issues: list[AuditIssue]
    scores: dict[str, Any]
    config: dict[str, Any]
    scanner_version: str = __version__
    warnings: Optional[list[str]] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []

    @property
    def overall_score(self) -> float:
        return self.scores.get("overall", 100.0)

    @property
    def category_scores(self) -> dict[str, int]:
        return self.scores.get("category_scores", {})

    @property
    def unsuppressed_issues(self) -> list[AuditIssue]:
        return [i for i in self.issues if not i.suppressed]

    def to_dict(self) -> dict[str, Any]:
        """Serialize structured audit and model metadata for Studio API and JSON consumers."""
        if not self.report:
            return {
                "report_name": self.report_name,
                "source_path": self.source_path,
                "scores": self.scores,
                "findings": [i.to_dict() for i in self.issues],
                "scanner_version": self.scanner_version,
                "warnings": self.warnings,
            }
        report = self.report

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
                        "measure_refs": list(v.measure_refs),
                        "fields_used": list(v.fields_used),
                        "is_slicer": v.is_slicer,
                        "hidden": v.hidden,
                    }
                    for v in p.visuals
                ],
            }
            for p in report.report.pages
        ]

        return {
            "report_name": self.report_name,
            "source_path": self.source_path,
            "scanner_version": self.scanner_version,
            "scores": self.scores,
            "findings": [
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
                for i in self.issues
            ],
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
            "warnings": self.warnings,
            "summary": {
                "total_findings": len(self.issues),
                "table_count": len(table_data),
                "relationship_count": len(rel_data),
                "measure_count": len(measure_data),
                "page_count": len(page_data),
                "semantic_reference_count": len(sem_refs),
                "active_root_count": len(sem_refs.active_root_measure_names()),
            },
        }

    def to_json(self, indent: int = 2) -> str:
        """Render raw JSON audit export."""
        data = {
            "report_name": self.report_name,
            "scanner_version": self.scanner_version,
            "scores": self.scores,
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
                for i in self.issues
            ],
        }
        return json.dumps(data, indent=indent)

    def to_sarif(self) -> str:
        """Render SARIF format string."""
        return SarifRenderer().render(issues=self.issues, report_path=self.source_path)

    def to_junit(self) -> str:
        """Render JUnit XML format string."""
        return JUnitRenderer().render(issues=self.issues, scores=self.scores, report_name=self.report_name)

    def to_html(self, timestamp: str = "") -> str:
        """Render standalone interactive HTML report string."""
        return HtmlRenderer().render(
            issues=self.issues,
            scores=self.scores,
            meta={
                "report_name": self.report_name,
                "scanner_version": self.scanner_version,
                "source_path": self.source_path,
                "scan_timestamp": timestamp,
            },
        )


class ScanService:
    """Unified scanning execution service."""

    @staticmethod
    def execute_scan(
        project_path: str | Path,
        config_path: Optional[str | Path] = None,
        config: Optional[dict] = None,
        suppressions_path: Optional[str | Path] = None,
    ) -> ScanResult:
        """Execute complete scan pipeline and return canonical ScanResult."""
        proj_path = Path(project_path)
        if not proj_path.exists():
            raise FileNotFoundError(f"Path does not exist: {project_path}")

        # Resolve configuration
        effective_config = resolve_config(config_path=config_path, explicit_config=config, project_path=proj_path)

        # Step 1: Extract PBIP metadata
        reader = PBIPReader()
        raw = reader.read(proj_path)

        # Step 2: Build Canonical Model
        builder = CanonicalBuilder()
        report = builder.build(raw)

        # Step 3: Execute Rules with configured thresholds
        thresholds = effective_config.get("thresholds", {})
        max_visuals = thresholds.get("maxVisualsPerPage", 15)
        max_slicers = thresholds.get("maxSlicersPerPage", 6)
        max_calc = thresholds.get("maxCalculatedColumnsPerTable", 4)

        raw_patterns = effective_config.get("dax_suspicious_patterns", [])
        dax_patterns = [(p["pattern"], p["description"]) for p in raw_patterns] or None

        findings = []
        for rule in MODEL_RULES:
            findings.extend(rule(report))

        findings.extend(check_suspicious_dax(report, patterns=dax_patterns))               # D001
        findings.extend(check_excessive_calc_columns(report, threshold=max_calc))          # D002
        findings.extend(check_duplicate_measures(report))                                  # D003
        findings.extend(check_unused_measures(report))                                     # D004

        findings.extend(check_visual_bloat(report, max_visuals=max_visuals))              # R001
        findings.extend(check_slicer_bloat(report, max_slicers=max_slicers))              # R002

        # Step 4: Issue Generation
        gen = IssueGenerator()
        issues = gen.generate(findings)

        # Step 5: Load and Apply Suppressions
        supp_dir = Path(suppressions_path) if suppressions_path else proj_path
        suppressions = load_suppressions(supp_dir)
        issues = apply_suppressions(issues, suppressions)

        # Step 6: Scoring
        scores = calculate_scores(issues, effective_config)

        # Determine report name
        report_name = report.report_name
        if not report_name or report_name.lower() == "fixture":
            report_name = proj_path.name if proj_path.is_file() else proj_path.name

        return ScanResult(
            report_name=report_name,
            source_path=str(proj_path),
            report=report,
            issues=issues,
            scores=scores,
            config=effective_config,
            warnings=list(raw.warnings) if hasattr(raw, "warnings") and raw.warnings else [],
        )
