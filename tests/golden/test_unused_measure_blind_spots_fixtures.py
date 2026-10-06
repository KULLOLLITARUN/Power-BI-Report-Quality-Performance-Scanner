"""Golden fixture contract tests for DAX_UNUSED_MEASURE blind spots.

Each measure below is used only in a place that is easy to miss. Flagging any
of them would let `pbiscan fix` offer to delete a measure the report needs.

- 'Drill Only':   a visual on a hidden drillthrough page
- 'Tooltip Only': a visual on a hidden report-page tooltip
- 'Margin %':     SWITCH(SELECTEDMEASURENAME(), "Margin %", ...) in a calculation item
- Discount:       "Discount" = SELECTEDMEASURENAME() (reversed comparison)
- 'Return Rate':  SELECTEDMEASURENAME() IN { "Return Rate" }
- Units:          SWITCH(SELECTEDMEASURENAME(), "Units", ...) in a formatStringDefinition

Controls: Orphan is referenced nowhere and is flagged. Page visibility is
read from PBIR's string values: the hidden drillthrough page's 7 slicers are
not bloat, but the same 7 slicers on a page marked "AlwaysVisible" are.
"""
from pathlib import Path

import pytest

from pbiscan.service import ScanService

FIXTURE = Path(__file__).parent / "test_unused_measure_blind_spots"


@pytest.fixture(scope="module")
def result():
    return ScanService.execute_scan(FIXTURE)


def test_only_the_orphan_is_unused(result):
    unused = {i.location for i in result.issues if i.rule_id == "DAX_UNUSED_MEASURE"}
    assert unused == {"Measure: Orphan"}


@pytest.mark.parametrize("measure", ["Margin %", "Discount", "Return Rate", "Units"])
def test_selectedmeasurename_strings_are_references(result, measure):
    refs = [
        r for r in result.report.semantic_references.references
        if r.target_name == measure and r.source_type == "calc_item_predicate"
    ]
    assert refs, f"no calc_item_predicate reference recorded for {measure!r}"


def test_hidden_page_visuals_still_count_as_usage(result):
    hidden = {p.name for p in result.report.report.pages if p.is_hidden}
    assert hidden == {"Drill", "Tip"}


def test_pbir_visibility_strings_drive_page_rules(result):
    bloat = {i.location for i in result.issues if i.rule_id == "REPORT_SLICER_BLOAT"}
    assert bloat == {"Page: Busy"}


def test_no_other_findings(result):
    assert sorted(i.rule_id for i in result.issues) == ["DAX_UNUSED_MEASURE", "REPORT_SLICER_BLOAT"]
    assert result.warnings == []
