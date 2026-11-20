"""Report quality rules — R001, R002 and R003.

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
from pbiscan.rules.catalog import new_finding


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
            findings.append(new_finding(
                "REPORT_VISUAL_BLOAT",
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
            findings.append(new_finding(
                "REPORT_SLICER_BLOAT",
                evidence=(
                    f"Page '{page.label}' has {page.slicer_count} slicers "
                    f"(threshold: {max_slicers})."
                ),
                location=f"Page: {page.label}",
            ))
    return findings


# ---------------------------------------------------------------------------
# R003 — Visual or page filter uses a measure the model does not have
# ---------------------------------------------------------------------------

# Only places where a missing field visibly breaks the report. Report-level filters, bookmarks and
# conditional-format references are left out: they are mixed together at extraction time.
_VISIBLE_REFERENCE_SOURCES = frozenset({"visual_projection", "visual_filter"})


def check_missing_measures(report: CanonicalReport) -> list[RuleFinding]:
    """R003 — Detect visuals and page filters that use a measure no model or report defines.

    The match is by name, case-insensitively, against every model measure and every report-level
    measure, so it flags only measures that exist nowhere. A measure that exists on another table
    is not flagged.

    Not checked (returns nothing) when it could not be decided:
      - the project has no semantic model (a thin report bound to a published model), or
      - some project file could not be read, so the measure list may be incomplete.

    Confidence: 90% (deterministic name match; depends on extraction being complete).
    """
    if not report.model.tables or report.unread_files:
        return []

    known = {m.name.lower() for m in report.dax.measures}
    known |= {name.lower() for name in report.report_extension_measure_names}

    places: dict[str, tuple[str, list[str]]] = {}  # lowercase name -> (name as written, places in use)
    for ref in report.semantic_references.references:
        if ref.target_type != "measure" or ref.source_type not in _VISIBLE_REFERENCE_SOURCES:
            continue
        key = ref.target_name.lower()
        if key in known:
            continue
        # source_object is "<page label>.<visual type>" or "<page label>.filters"
        where = ref.source_object.rsplit(".", 1)[0] if ref.source_object else "the report"
        name, seen = places.setdefault(key, (ref.target_name, []))
        if where not in seen:
            seen.append(where)

    findings: list[RuleFinding] = []
    for name, seen in places.values():
        shown = ", ".join(f"'{p}'" for p in seen[:3]) + (f" and {len(seen) - 3} more" if len(seen) > 3 else "")
        findings.append(new_finding(
            "REPORT_MISSING_MEASURE",
            evidence=(
                f"Measure '{name}' is used on {'page' if len(seen) == 1 else 'pages'} {shown}, "
                "but the model and the report define no measure with that name."
            ),
            location=f"Measure: {name}",
        ))
    return findings


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

REPORT_RULES = [
    check_visual_bloat,
    check_slicer_bloat,
    check_missing_measures,
]
