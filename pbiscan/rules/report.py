"""Report layout quality rules — R001 and R002.

Each function:
  - accepts a CanonicalReport (and optional threshold from config)
  - returns list[RuleFinding]
  - contains ONLY detection logic
  - does NOT import from pbiscan.extraction
  - does NOT contain recommendation prose
"""
from __future__ import annotations

from pbiscan.canonical.model import CanonicalReport
from pbiscan.engine.issue import RuleFinding


# ---------------------------------------------------------------------------
# R001 — Visual bloat
# ---------------------------------------------------------------------------

def check_visual_bloat(
    report: CanonicalReport,
    max_visuals: int = 15,
) -> list[RuleFinding]:
    """R001 — Detect pages with more than `max_visuals` visuals.

    Confidence: 100% (deterministic count).
    Hidden pages are excluded from analysis.
    """
    findings: list[RuleFinding] = []
    for page in report.report.pages:
        if page.is_hidden:
            continue
        if page.visual_count > max_visuals:
            findings.append(RuleFinding(
                rule_id="REPORT_VISUAL_BLOAT",
                category="report",
                severity="MEDIUM",
                confidence=100,
                evidence=(
                    f"Page '{page.label}' has {page.visual_count} visuals "
                    f"(threshold: {max_visuals})."
                ),
                location=f"Page: {page.label}",
            ))
    return findings


# ---------------------------------------------------------------------------
# R002 — Slicer bloat
# ---------------------------------------------------------------------------

def check_slicer_bloat(
    report: CanonicalReport,
    max_slicers: int = 6,
) -> list[RuleFinding]:
    """R002 — Detect pages with more than `max_slicers` slicers.

    Confidence: 100% (deterministic count).
    Hidden pages are excluded from analysis.
    """
    findings: list[RuleFinding] = []
    for page in report.report.pages:
        if page.is_hidden:
            continue
        if page.slicer_count > max_slicers:
            findings.append(RuleFinding(
                rule_id="REPORT_SLICER_BLOAT",
                category="report",
                severity="MEDIUM",
                confidence=100,
                evidence=(
                    f"Page '{page.label}' has {page.slicer_count} slicers "
                    f"(threshold: {max_slicers})."
                ),
                location=f"Page: {page.label}",
            ))
    return findings


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

REPORT_RULES = [
    check_visual_bloat,
    check_slicer_bloat,
]
