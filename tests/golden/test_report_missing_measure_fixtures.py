"""Golden fixture contract tests for REPORT_MISSING_MEASURE.

The fixture's report uses these measures:

- 'Revenue':               defined in the model (control: must not be flagged)
- 'REVENUE':               the same measure with different capitalisation (control)
- 'Margin Ext':            a report-level measure in reportExtensions.json (control: it lives in the
                           report, so it is not a broken reference)
- 'Total Sugars':          defined nowhere, used by two visible visuals on two pages (true positive,
                           reported once)
- 'Revealed By Bookmark':  defined nowhere, used only by a hidden visual (flagged, and says it is hidden)
- 'Half Hidden':           defined nowhere, used by one visible and one hidden visual
"""
from pathlib import Path

import pytest

from pbiscan.service import ScanService

FIXTURE = Path(__file__).parent / "test_report_missing_measure"


@pytest.fixture(scope="module")
def result():
    return ScanService.execute_scan(FIXTURE)


@pytest.fixture(scope="module")
def flagged(result):
    return {i.location: i for i in result.issues if i.rule_id == "REPORT_MISSING_MEASURE"}


def test_exactly_the_measures_defined_nowhere_are_flagged(flagged):
    assert set(flagged) == {"Measure: Total Sugars", "Measure: Revealed By Bookmark", "Measure: Half Hidden"}


def test_it_is_reported_once_with_every_page_that_uses_it(flagged):
    issue = flagged["Measure: Total Sugars"]
    assert "'Overview'" in issue.evidence and "'Detail'" in issue.evidence
    assert (issue.category, issue.severity, issue.confidence) == ("report", "MEDIUM", 90)


def test_visible_uses_carry_no_hidden_note(flagged):
    assert "hidden" not in flagged["Measure: Total Sugars"].evidence


def test_a_measure_used_only_by_hidden_visuals_says_so(flagged):
    assert "Every visual that uses it is hidden" in flagged["Measure: Revealed By Bookmark"].evidence


def test_a_measure_used_by_visible_and_hidden_visuals_says_so(flagged):
    evidence = flagged["Measure: Half Hidden"].evidence
    assert "Some of these visuals are hidden" in evidence
    assert "Every visual" not in evidence


def test_model_report_level_and_differently_cased_measures_are_not_flagged(result):
    text = " ".join(i.evidence for i in result.issues)
    for control in ("Revenue", "REVENUE", "Margin Ext"):
        assert f"'{control}'" not in text


def test_report_level_measure_names_are_carried_into_the_canonical_report(result):
    assert result.report.report_extension_measure_names == ["Margin Ext"]


def test_no_other_findings(result):
    assert [i.rule_id for i in result.issues] == ["REPORT_MISSING_MEASURE"] * 3
    assert result.warnings == []
