"""Golden fixture contract tests for REPORT_MISSING_COLUMN.

The model has Sales (Amount, Region, a calculated column Profit, a measure Revenue) and Date
(Date, Year). The report uses:

- Sales[Region], Sales[Amount], Sales[PROFIT], Date[Year], measure Revenue: all present (controls;
  'PROFIT' is the calculated column in another case)
- Sales[Old Region]:  not in the model, used by a visible visual on two pages (true positive,
                      reported once)
- Sales[Retired]:     not in the model, reached only through a visual filter whose table is an
                      alias resolved through its From list (true positive)
- Date[Quarter]:      not in the model, used by a page filter (true positive)
- Sales[Ghost]:       not in the model, used only by a hidden visual (flagged, says so)
- Sales[Half]:        not in the model, used by one visible and one hidden visual
- Archive[Anything], LocalDateTable_1234[Year]: tables the model does not have (controls: this
                      rule checks columns of tables the model defines, so they are not flagged)
"""
from pathlib import Path

import pytest

from pbiscan.service import ScanService

FIXTURE = Path(__file__).parent / "test_report_missing_column"


@pytest.fixture(scope="module")
def result():
    return ScanService.execute_scan(FIXTURE)


@pytest.fixture(scope="module")
def flagged(result):
    return {i.location: i for i in result.issues if i.rule_id == "REPORT_MISSING_COLUMN"}


def test_exactly_the_columns_the_table_lacks_are_flagged(flagged):
    assert set(flagged) == {
        "Column: Sales[Old Region]", "Column: Sales[Retired]", "Column: Date[Quarter]",
        "Column: Sales[Ghost]", "Column: Sales[Half]",
    }


def test_it_is_reported_once_with_every_page_that_uses_it(flagged):
    issue = flagged["Column: Sales[Old Region]"]
    assert "'Overview'" in issue.evidence and "'Detail'" in issue.evidence
    assert (issue.category, issue.severity, issue.confidence) == ("report", "MEDIUM", 85)


def test_a_filter_alias_is_resolved_to_its_table(flagged):
    assert "Column 'Retired' of table 'Sales'" in flagged["Column: Sales[Retired]"].evidence


def test_a_page_filter_is_checked(flagged):
    assert "page 'Overview'" in flagged["Column: Date[Quarter]"].evidence


def test_visible_uses_carry_no_hidden_note(flagged):
    assert "hidden" not in flagged["Column: Sales[Old Region]"].evidence


def test_a_column_used_only_by_hidden_visuals_says_so(flagged):
    assert "Every visual that uses it is hidden" in flagged["Column: Sales[Ghost]"].evidence


def test_a_column_used_by_visible_and_hidden_visuals_says_so(flagged):
    evidence = flagged["Column: Sales[Half]"].evidence
    assert "Some of these visuals are hidden" in evidence
    assert "Every visual" not in evidence


def test_present_columns_and_foreign_tables_are_not_flagged(result):
    text = " ".join(i.evidence for i in result.issues)
    for control in ("Region'", "Amount", "PROFIT", "Profit", "Year", "Revenue", "Anything", "LocalDateTable"):
        assert control not in text.replace("Old Region", "")


def test_no_other_findings(result):
    assert [i.rule_id for i in result.issues] == ["REPORT_MISSING_COLUMN"] * 5
    assert result.warnings == []
