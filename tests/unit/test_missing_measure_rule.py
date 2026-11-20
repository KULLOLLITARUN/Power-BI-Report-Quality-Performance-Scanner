"""Unit tests for REPORT_MISSING_MEASURE (R003): when it flags, and when it must stay silent."""
from __future__ import annotations

from pbiscan.canonical.model import CanonicalReport, DaxDictionary, Measure, ModelGraph, Table
from pbiscan.canonical.references import SemanticReference, SemanticReferenceIndex
from pbiscan.rules.report import check_missing_measures


def _ref(name: str, source_type: str = "visual_projection", where: str = "Page 1.barChart",
         target_type: str = "measure") -> SemanticReference:
    return SemanticReference(target_name=name, target_type=target_type, source_type=source_type, source_object=where)


def _report(refs: list[SemanticReference], *, tables=("Sales",), measures=(("Revenue", "Sales"),),
            extension=(), unread=()) -> CanonicalReport:
    index = SemanticReferenceIndex()
    index.add_many(refs)
    return CanonicalReport(
        model=ModelGraph(tables=[Table(name=t) for t in tables]),
        dax=DaxDictionary(measures=[Measure(name=n, table=t, expression="1") for n, t in measures]),
        semantic_references=index,
        report_extension_measure_names=list(extension),
        unread_files=list(unread),
    )


def test_flags_a_visual_that_uses_a_missing_measure():
    findings = check_missing_measures(_report([_ref("Total Sugars")]))
    assert [f.location for f in findings] == ["Measure: Total Sugars"]
    assert "'Page 1'" in findings[0].evidence


def test_flags_a_page_filter_that_uses_a_missing_measure():
    findings = check_missing_measures(_report([_ref("Gone", "visual_filter", "Page 2.filters")]))
    assert [f.location for f in findings] == ["Measure: Gone"]
    assert "'Page 2'" in findings[0].evidence


def test_one_finding_per_measure_however_many_visuals_use_it():
    refs = [_ref("Gone", where="Page 1.barChart"), _ref("Gone", where="Page 1.card"), _ref("gone", where="Page 2.card")]
    findings = check_missing_measures(_report(refs))
    assert len(findings) == 1
    assert "'Page 1', 'Page 2'" in findings[0].evidence


def test_long_page_lists_are_shortened():
    refs = [_ref("Gone", where=f"Page {n}.card") for n in range(1, 6)]
    (finding,) = check_missing_measures(_report(refs))
    assert "and 2 more" in finding.evidence


def test_does_not_flag_a_measure_the_model_defines_even_with_other_capitalisation():
    assert check_missing_measures(_report([_ref("revenue")])) == []


def test_does_not_flag_a_measure_defined_on_another_table():
    # The visual may name the wrong table, but the measure exists, so this rule stays silent.
    report = _report([_ref("Margin")], measures=(("Margin", "Other"),))
    assert check_missing_measures(report) == []


def test_does_not_flag_a_report_level_measure():
    assert check_missing_measures(_report([_ref("Margin Ext")], extension=("Margin Ext",))) == []


def test_silent_for_a_thin_report_with_no_local_model():
    assert check_missing_measures(_report([_ref("Anything")], tables=(), measures=())) == []


def test_silent_when_a_project_file_could_not_be_read():
    assert check_missing_measures(_report([_ref("Total Sugars")], unread=("Sales.tmdl",))) == []


def test_ignores_references_that_are_not_visible_breakage():
    refs = [
        _ref("Gone", "report_filter", "report"),
        _ref("Gone", "calc_item_predicate", "Group"),
        _ref("Gone", "visual_projection", "Page 1.card", target_type="column"),
    ]
    assert check_missing_measures(_report(refs)) == []
