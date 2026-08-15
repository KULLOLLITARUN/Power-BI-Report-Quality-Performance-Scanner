"""HTML report renderer — Jinja2-based self-contained HTML generation."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader


TEMPLATE_DIR = Path(__file__).parent / "templates"


class HtmlRenderer:
    """Renders the audit report as a self-contained HTML file."""

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
    ) -> str:
        """Render the HTML report.

        Args:
            issues:  list of AuditIssue objects
            scores:  output of calculate_scores()
            meta:    dict with keys: report_name, scan_timestamp, scanner_version, source_path

        Returns:
            Self-contained HTML string.
        """
        template = self._env.get_template("report.html.j2")

        # Build severity summary
        severity_counts: dict[str, int] = {}
        for issue in issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

        # Build category summaries
        category_counts: dict[str, int] = {}
        for issue in issues:
            category_counts[issue.category] = category_counts.get(issue.category, 0) + 1

        # Colour map for severity badges
        severity_colours = {
            "CRITICAL": "#ef4444",
            "HIGH":     "#f97316",
            "MEDIUM":   "#f59e0b",
            "WARNING":  "#eab308",
            "ADVISORY": "#6366f1",
            "LOW":      "#94a3b8",
        }

        # Score colour
        def score_colour(score: float) -> str:
            if score >= 80:
                return "#22c55e"
            if score >= 60:
                return "#f59e0b"
            return "#ef4444"

        cat_scores = scores.get("category_scores", {})

        return template.render(
            issues=issues,
            overall_score=scores.get("overall", 0),
            overall_colour=score_colour(scores.get("overall", 0)),
            category_scores={
                cat: {
                    "score": cat_scores.get(cat, 100),
                    "colour": score_colour(cat_scores.get(cat, 100)),
                }
                for cat in ("model", "dax", "report")
            },
            severity_counts=severity_counts,
            category_counts=category_counts,
            severity_colours=severity_colours,
            total_findings=len(issues),
            meta=meta,
        )
