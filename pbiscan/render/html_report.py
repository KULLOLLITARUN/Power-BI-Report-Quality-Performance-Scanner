"""HTML report renderer — Jinja2-based self-contained HTML generation."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader


TEMPLATE_DIR = Path(__file__).parent / "templates"

# Most severe first, with the marker shape Studio draws for each
# (studio-ui/src/lib/severity.ts). Shapes keep severities apart without colour.
SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "WARNING", "LOW", "ADVISORY"]
SEVERITY_SHAPES = {
    "CRITICAL": "diamond",
    "HIGH": "tri",
    "MEDIUM": "square",
    "WARNING": "circle",
    "LOW": "dash",
    "ADVISORY": "ring",
}
AREA_LABELS = {"model": "Model", "dax": "DAX", "report": "Report"}
# The "target" tick on Studio's per-area score bars.
SCORE_TARGET = 80


def grade(score: float) -> str:
    """Letter grade for a 0-100 score, as Studio shows it."""
    for floor, letter in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
        if score >= floor:
            return letter
    return "F"


def _severity_rank(severity: str) -> int:
    sev = (severity or "").upper()
    return SEVERITY_ORDER.index(sev) if sev in SEVERITY_ORDER else len(SEVERITY_ORDER)


class HtmlRenderer:
    """Renders the audit report as a self-contained, script-free HTML file."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=True,
        )

    def render(
        self,
        issues: list,
        scores: dict,
        meta: dict,
        warnings: Optional[list[str]] = None,
    ) -> str:
        """Render the HTML report.

        Args:
            issues:   list of AuditIssue objects
            scores:   output of calculate_scores()
            meta:     dict with keys: report_name, scan_timestamp, scanner_version, source_path
            warnings: scan warnings (e.g. files that could not be read)

        Returns:
            Self-contained HTML string.
        """
        template = self._env.get_template("report.html.j2")

        # Most severe first, then most confident (Studio's sortFindings order).
        ordered = sorted(issues, key=lambda i: (_severity_rank(i.severity), -(i.confidence or 0)))
        open_issues = [i for i in ordered if not getattr(i, "suppressed", False)]
        suppressed_issues = [i for i in ordered if getattr(i, "suppressed", False)]

        severity_counts: dict[str, int] = {}
        for issue in open_issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

        overall = float(scores.get("overall", 0))
        cat_scores = scores.get("category_scores", {})
        if overall >= 80:
            verdict = "Minor concerns only."
        elif overall >= 60:
            verdict = "Needs attention: review the findings below."
        else:
            verdict = "Action required: significant issues found."

        return template.render(
            open_issues=open_issues,
            suppressed_issues=suppressed_issues,
            overall_score=overall,
            grade=grade(overall),
            verdict=verdict,
            categories=[
                {"label": AREA_LABELS[cat], "score": float(cat_scores.get(cat, 100))}
                for cat in ("model", "dax", "report")
            ],
            target=SCORE_TARGET,
            severity_order=SEVERITY_ORDER,
            severity_shapes=SEVERITY_SHAPES,
            severity_counts=severity_counts,
            area_labels=AREA_LABELS,
            warnings=warnings or [],
            meta=meta,
        )
