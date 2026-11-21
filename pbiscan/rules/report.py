"""Report quality rules — R001 to R004.

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

def check_missing_measures(report: CanonicalReport) -> list[RuleFinding]:
    """R003 — Detect visuals and page filters that use a measure no model or report defines.

    The match is by name, case-insensitively, against every model measure and every report-level
    measure, so it flags only measures that exist nowhere. A measure that exists on another table
    is not flagged. Only visuals and page filters count: report-level filters, bookmarks and
    conditional-format references are mixed together at extraction time, so they are left out.
    Hidden visuals are flagged too (a bookmark or button can reveal them), and the evidence says
    when every use is hidden.

    Not checked (returns nothing) when it could not be decided:
      - the project has no semantic model (a thin report bound to a published model), or
      - some project file could not be read, so the measure list may be incomplete.

    Confidence: 90% (deterministic name match; depends on extraction being complete).
    """
    if not report.model.tables or report.unread_files:
        return []

    known = {m.name.lower() for m in report.dax.measures}
    known |= {name.lower() for name in report.report_extension_measure_names}

    # lowercase name -> (name as written, pages in use, one hidden flag per use)
    uses: dict[str, tuple[str, list[str], list[bool]]] = {}

    def note(name: str, where: str, hidden: bool) -> None:
        _, pages, flags = uses.setdefault(name.lower(), (name, [], []))
        if where not in pages:
            pages.append(where)
        flags.append(hidden)

    # Visuals come from the page model, which knows whether each one is hidden.
    for page in report.report.pages:
        for visual in page.visuals:
            for ref in visual.measure_refs:
                if ref.lower() not in known:
                    note(ref, page.label, visual.hidden)
    # Page filter panes have no hidden state: a missing measure there always shows.
    for sref in report.semantic_references.references:
        if sref.target_type == "measure" and sref.source_type == "visual_filter" and sref.target_name.lower() not in known:
            # source_object is "<page label>.filters"
            note(sref.target_name, sref.source_object.rsplit(".", 1)[0] if sref.source_object else "the report", False)

    findings: list[RuleFinding] = []
    for name, pages, flags in uses.values():
        shown = ", ".join(f"'{p}'" for p in pages[:3]) + (f" and {len(pages) - 3} more" if len(pages) > 3 else "")
        evidence = (
            f"Measure '{name}' is used on {'page' if len(pages) == 1 else 'pages'} {shown}, "
            "but the model and the report define no measure with that name."
        )
        if all(flags):
            evidence += " Every visual that uses it is hidden, so no error shows until one is revealed, for example by a bookmark."
        elif any(flags):
            evidence += " Some of these visuals are hidden."
        findings.append(new_finding("REPORT_MISSING_MEASURE", evidence=evidence, location=f"Measure: {name}"))
    return findings


# ---------------------------------------------------------------------------
# R004 — Visual or page filter uses a column the model does not have
# ---------------------------------------------------------------------------

# Power BI's own date tables: their columns are generated, so a missing one is not a broken reference.
_GENERATED_TABLE_PREFIXES = ("localdatetable_", "datetabletemplate_")


def check_missing_columns(report: CanonicalReport) -> list[RuleFinding]:
    """R004 — Detect visuals and page filters that use a column its table no longer has.

    The match is by table and column name, case-insensitively. A column counts as present when the
    table has a column, a calculated column or a measure of that name. Only a table the model
    defines and whose columns are known is checked, so a reference to a table the model lacks
    (a thin report, or a table removed on purpose) is not reported here. Only visuals and page
    filters count, as in REPORT_MISSING_MEASURE. Hidden visuals are flagged too, and the evidence
    says when every use is hidden.

    Not checked (returns nothing) when it could not be decided:
      - the project has no semantic model (a thin report bound to a published model), or
      - some project file could not be read, so a table's columns may be incomplete.

    Confidence: 85% (deterministic name match; depends on the model parser reading every column).
    """
    if not report.model.tables or report.unread_files:
        return []

    known: dict[str, set[str]] = {}
    for model_table in report.model.tables:
        if not model_table.name.lower().startswith(_GENERATED_TABLE_PREFIXES):
            known.setdefault(model_table.name.lower(), set()).update(c.name.lower() for c in model_table.columns)
    for calc in report.dax.calculated_columns:
        if calc.table.lower() in known:
            known[calc.table.lower()].add(calc.name.lower())
    for measure in report.dax.measures:
        if measure.table.lower() in known:
            known[measure.table.lower()].add(measure.name.lower())

    # (table, column) in lower case -> (names as written, pages in use, one hidden flag per use)
    uses: dict[tuple[str, str], tuple[tuple[str, str], list[str], list[bool]]] = {}

    def note(table: str, column: str, where: str, hidden: bool) -> None:
        names = known.get(table.lower())
        if not names or column.lower() in names:   # unknown table, or a table with no known columns
            return
        _, pages, flags = uses.setdefault((table.lower(), column.lower()), ((table, column), [], []))
        if where not in pages:
            pages.append(where)
        flags.append(hidden)

    for page in report.report.pages:
        for visual in page.visuals:
            for table, column in visual.column_refs:
                note(table, column, page.label, visual.hidden)
        for table, column in page.filter_column_refs:
            note(table, column, page.label, False)

    findings: list[RuleFinding] = []
    for (table, column), pages, flags in uses.values():
        shown = ", ".join(f"'{p}'" for p in pages[:3]) + (f" and {len(pages) - 3} more" if len(pages) > 3 else "")
        evidence = (
            f"Column '{column}' of table '{table}' is used on {'page' if len(pages) == 1 else 'pages'} {shown}, "
            "but that table has no column or measure with that name."
        )
        if all(flags):
            evidence += " Every visual that uses it is hidden, so no error shows until one is revealed, for example by a bookmark."
        elif any(flags):
            evidence += " Some of these visuals are hidden."
        findings.append(new_finding("REPORT_MISSING_COLUMN", evidence=evidence, location=f"Column: {table}[{column}]"))
    return findings


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

REPORT_RULES = [
    check_visual_bloat,
    check_slicer_bloat,
    check_missing_measures,
    check_missing_columns,
]
