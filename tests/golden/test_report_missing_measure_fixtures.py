"""Golden fixture contract tests for REPORT_MISSING_MEASURE.

The fixture's report uses four measures:

- 'Revenue':       defined in the model (control: must not be flagged)
- 'REVENUE':       the same measure with different capitalisation (control)
- 'Margin Ext':    a report-level measure in reportExtensions.json (control: it lives in the
                   report, so it is not a broken reference)
- 'Total Sugars':  defined nowhere, used on two pages (true positive, reported once)
"""
from pathlib import Path

import pytest

from pbiscan.service import ScanService

FIXTURE = Path(__file__).parent / "test_report_missing_measure"


@pytest.fixture(scope="module")
def result():
    return ScanService.execute_scan(FIXTURE)


def test_only_the_measure_defined_nowhere_is_flagged(result):
    flagged = [i for i in result.issues if i.rule_id == "REPORT_MISSING_MEASURE"]
    assert [i.location for i in flagged] == ["Measure: Total Sugars"]


def test_it_is_reported_once_with_every_page_that_uses_it(result):
    (issue,) = [i for i in result.issues if i.rule_id == "REPORT_MISSING_MEASURE"]
    assert "'Overview'" in issue.evidence and "'Detail'" in issue.evidence
    assert (issue.category, issue.severity, issue.confidence) == ("report", "MEDIUM", 90)


def test_model_report_level_and_differently_cased_measures_are_not_flagged(result):
    text = " ".join(i.evidence for i in result.issues)
    for control in ("Revenue", "REVENUE", "Margin Ext"):
        assert f"'{control}'" not in text


def test_report_level_measure_names_are_carried_into_the_canonical_report(result):
    assert result.report.report_extension_measure_names == ["Margin Ext"]


def test_no_other_findings(result):
    assert [i.rule_id for i in result.issues] == ["REPORT_MISSING_MEASURE"]
    assert result.warnings == []
