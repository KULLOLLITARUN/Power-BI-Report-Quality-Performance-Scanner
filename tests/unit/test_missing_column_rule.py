"""Unit tests for REPORT_MISSING_COLUMN (R004): when it flags, and when it must stay silent."""
from __future__ import annotations

from pbiscan.canonical.model import (
    CalculatedColumn, CanonicalReport, Column, DaxDictionary, Measure, ModelGraph, Page, ReportDOM, Table, Visual,
)
from pbiscan.rules.report import check_missing_columns


def _visual(page: str, *refs: tuple[str, str], hidden: bool = False) -> Visual:
    return Visual(visual_type="card", page=page, column_refs=list(refs), hidden=hidden)


def _report(pages: dict[str, list[Visual]] | None = None, *, page_filters=None, tables=None,
            calc=(), measures=(), unread=()) -> CanonicalReport:
    tables = tables if tables is not None else {"Sales": ["Amount", "Region"]}
    page_filters = page_filters or {}
    report_pages = [
        Page(name=label, display_name=label, visuals=vs, filter_column_refs=list(page_filters.get(label, [])))
        for label, vs in (pages or {}).items()
    ]
    for label, refs in page_filters.items():
        if label not in (pages or {}):
            report_pages.append(Page(name=label, display_name=label, filter_column_refs=list(refs)))
    return CanonicalReport(
        model=ModelGraph(tables=[Table(name=t, columns=[Column(name=c, table=t) for c in cols]) for t, cols in tables.items()]),
        dax=DaxDictionary(
            measures=[Measure(name=n, table=t, expression="1") for n, t in measures],
            calculated_columns=[CalculatedColumn(name=n, table=t, expression="1") for n, t in calc],
        ),
        report=ReportDOM(pages=report_pages),
        unread_files=list(unread),
    )


def test_flags_a_visual_that_uses_a_missing_column():
    findings = check_missing_columns(_report({"Page 1": [_visual("Page 1", ("Sales", "Old"))]}))
    assert [f.location for f in findings] == ["Column: Sales[Old]"]
    assert "'Page 1'" in findings[0].evidence and "hidden" not in findings[0].evidence


def test_flags_a_page_filter_that_uses_a_missing_column():
    findings = check_missing_columns(_report(page_filters={"Page 2": [("Sales", "Old")]}))
    assert [f.location for f in findings] == ["Column: Sales[Old]"]
    assert "'Page 2'" in findings[0].evidence


def test_columns_calculated_columns_and_measures_of_the_table_are_present_in_any_case():
    report = _report(
        {"Page 1": [_visual("Page 1", ("Sales", "AMOUNT"), ("sales", "region"), ("Sales", "Profit"), ("Sales", "Revenue"))]},
        calc=[("Profit", "Sales")], measures=[("Revenue", "Sales")],
    )
    assert check_missing_columns(report) == []


def test_a_column_of_another_table_does_not_count():
    report = _report({"Page 1": [_visual("Page 1", ("Sales", "Year"))]}, tables={"Sales": ["Amount"], "Date": ["Year"]})
    assert [f.location for f in check_missing_columns(report)] == ["Column: Sales[Year]"]


def test_a_table_the_model_does_not_have_is_not_checked():
    assert check_missing_columns(_report({"Page 1": [_visual("Page 1", ("Archive", "Anything"))]})) == []


def test_a_table_with_no_known_columns_is_not_checked():
    report = _report({"Page 1": [_visual("Page 1", ("Calc", "Anything"))]}, tables={"Sales": ["Amount"], "Calc": []})
    assert check_missing_columns(report) == []


def test_auto_date_tables_are_not_checked():
    report = _report({"Page 1": [_visual("Page 1", ("LocalDateTable_1", "Year"))]},
                     tables={"Sales": ["Amount"], "LocalDateTable_1": ["Date"]})
    assert check_missing_columns(report) == []


def test_silent_without_a_semantic_model():
    assert check_missing_columns(_report({"Page 1": [_visual("Page 1", ("Sales", "Old"))]}, tables={})) == []


def test_silent_when_a_project_file_could_not_be_read():
    report = _report({"Page 1": [_visual("Page 1", ("Sales", "Old"))]}, unread=["broken.tmdl"])
    assert check_missing_columns(report) == []


def test_one_finding_per_column_however_many_visuals_use_it():
    report = _report({
        "Page 1": [_visual("Page 1", ("Sales", "Old")), _visual("Page 1", ("sales", "OLD"))],
        "Page 2": [_visual("Page 2", ("Sales", "Old"))],
    })
    (finding,) = check_missing_columns(report)
    assert "'Page 1', 'Page 2'" in finding.evidence


def test_long_page_lists_are_shortened():
    report = _report({f"Page {n}": [_visual(f"Page {n}", ("Sales", "Old"))] for n in range(1, 6)})
    (finding,) = check_missing_columns(report)
    assert "and 2 more" in finding.evidence


def test_hidden_notes():
    only_hidden = _report({"P": [_visual("P", ("Sales", "Old"), hidden=True)]})
    mixed = _report({"P": [_visual("P", ("Sales", "Old"), hidden=True), _visual("P", ("Sales", "Old"))]})
    assert "Every visual that uses it is hidden" in check_missing_columns(only_hidden)[0].evidence
    assert "Some of these visuals are hidden" in check_missing_columns(mixed)[0].evidence
