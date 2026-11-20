"""Unit tests for REPORT_MISSING_MEASURE (R003): when it flags, and when it must stay silent."""
from __future__ import annotations

from pbiscan.canonical.model import CanonicalReport, DaxDictionary, Measure, ModelGraph, Page, ReportDOM, Table, Visual
from pbiscan.canonical.references import SemanticReference, SemanticReferenceIndex
from pbiscan.extraction.pbir_parser import parse_pbir_visual
from pbiscan.rules.report import check_missing_measures


def _visual(page: str, *measures: str, hidden: bool = False, vtype: str = "card") -> Visual:
    return Visual(visual_type=vtype, page=page, measure_refs=list(measures), hidden=hidden)


def _filter_ref(name: str, where: str = "Page 2.filters") -> SemanticReference:
    return SemanticReference(target_name=name, target_type="measure", source_type="visual_filter", source_object=where)


def _report(visuals_by_page: dict[str, list[Visual]] | None = None, *, filters=(), tables=("Sales",),
            measures=(("Revenue", "Sales"),), extension=(), unread=()) -> CanonicalReport:
    pages = [Page(name=label, display_name=label, visuals=vs) for label, vs in (visuals_by_page or {}).items()]
    index = SemanticReferenceIndex()
    index.add_many(list(filters))
    return CanonicalReport(
        model=ModelGraph(tables=[Table(name=t) for t in tables]),
        dax=DaxDictionary(measures=[Measure(name=n, table=t, expression="1") for n, t in measures]),
        report=ReportDOM(pages=pages),
        semantic_references=index,
        report_extension_measure_names=list(extension),
        unread_files=list(unread),
    )


def test_flags_a_visual_that_uses_a_missing_measure():
    findings = check_missing_measures(_report({"Page 1": [_visual("Page 1", "Total Sugars")]}))
    assert [f.location for f in findings] == ["Measure: Total Sugars"]
    assert "'Page 1'" in findings[0].evidence
    assert "hidden" not in findings[0].evidence


def test_flags_a_page_filter_that_uses_a_missing_measure():
    findings = check_missing_measures(_report(filters=[_filter_ref("Gone")]))
    assert [f.location for f in findings] == ["Measure: Gone"]
    assert "'Page 2'" in findings[0].evidence
    assert "hidden" not in findings[0].evidence


def test_one_finding_per_measure_however_many_visuals_use_it():
    report = _report({
        "Page 1": [_visual("Page 1", "Gone"), _visual("Page 1", "Gone", vtype="barChart")],
        "Page 2": [_visual("Page 2", "gone")],
    })
    findings = check_missing_measures(report)
    assert len(findings) == 1
    assert "'Page 1', 'Page 2'" in findings[0].evidence


def test_long_page_lists_are_shortened():
    report = _report({f"Page {n}": [_visual(f"Page {n}", "Gone")] for n in range(1, 6)})
    (finding,) = check_missing_measures(report)
    assert "and 2 more" in finding.evidence


def test_says_so_when_every_visual_using_it_is_hidden():
    (finding,) = check_missing_measures(_report({"Page 1": [_visual("Page 1", "Gone", hidden=True)]}))
    assert "Every visual that uses it is hidden" in finding.evidence


def test_says_so_when_only_some_visuals_using_it_are_hidden():
    report = _report({"Page 1": [_visual("Page 1", "Gone"), _visual("Page 1", "Gone", hidden=True)]})
    (finding,) = check_missing_measures(report)
    assert "Some of these visuals are hidden" in finding.evidence
    assert "Every visual" not in finding.evidence


def test_a_page_filter_use_counts_as_visible():
    report = _report({"Page 1": [_visual("Page 1", "Gone", hidden=True)]}, filters=[_filter_ref("Gone", "Page 1.filters")])
    (finding,) = check_missing_measures(report)
    assert "Some of these visuals are hidden" in finding.evidence


def test_does_not_flag_a_measure_the_model_defines_even_with_other_capitalisation():
    assert check_missing_measures(_report({"Page 1": [_visual("Page 1", "revenue")]})) == []


def test_does_not_flag_a_measure_defined_on_another_table():
    # The visual may name the wrong table, but the measure exists, so this rule stays silent.
    report = _report({"Page 1": [_visual("Page 1", "Margin")]}, measures=(("Margin", "Other"),))
    assert check_missing_measures(report) == []


def test_does_not_flag_a_report_level_measure():
    report = _report({"Page 1": [_visual("Page 1", "Margin Ext")]}, extension=("Margin Ext",))
    assert check_missing_measures(report) == []


def test_silent_for_a_thin_report_with_no_local_model():
    report = _report({"Page 1": [_visual("Page 1", "Anything")]}, tables=(), measures=())
    assert check_missing_measures(report) == []


def test_silent_when_a_project_file_could_not_be_read():
    report = _report({"Page 1": [_visual("Page 1", "Total Sugars")]}, unread=("Sales.tmdl",))
    assert check_missing_measures(report) == []


def test_ignores_references_that_are_not_visible_breakage():
    other = [
        SemanticReference(target_name="Gone", target_type="measure", source_type="report_filter", source_object="report"),
        SemanticReference(target_name="Gone", target_type="measure", source_type="calc_item_predicate", source_object="Group"),
        SemanticReference(target_name="Gone", target_type="column", source_type="visual_filter", source_object="Page 1.filters"),
    ]
    assert check_missing_measures(_report(filters=other)) == []


def test_pbir_visual_reads_is_hidden():
    """PBIR marks a hidden visual with "isHidden": true (the old code read "hidden", so it never saw it)."""
    def raw(**extra):
        return {"name": "v", "visual": {"visualType": "card"}, **extra}

    assert parse_pbir_visual(raw(isHidden=True)).hidden is True
    assert parse_pbir_visual(raw(isHidden=False)).hidden is False
    assert parse_pbir_visual(raw()).hidden is False
    assert parse_pbir_visual(raw(hidden=True)).hidden is True  # the older spelling still works
