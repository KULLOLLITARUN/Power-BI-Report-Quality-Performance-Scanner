"""Golden fixture contract test: legacy report.json projections must not turn columns into measures.

In report.json every field a visual uses is listed in `projections` as a bare queryRef, columns and
column aggregations included. The fixture's report uses:

- 'Year', 'Channel':      columns (control: must not be reported as missing measures)
- 'Min(Sales.Environment)': a column aggregation (control: must not become 'Environment)')
- 'Revenue':              a model measure (control)
- 'Ghost Margin':         a measure defined nowhere (true positive)
"""
from pathlib import Path

import pytest

from pbiscan.service import ScanService

FIXTURE = Path(__file__).parent / "test_report_missing_measure_legacy_projections"


@pytest.fixture(scope="module")
def flagged():
    result = ScanService.execute_scan(FIXTURE)
    return {i.location for i in result.issues if i.rule_id == "REPORT_MISSING_MEASURE"}


def test_only_the_measure_defined_nowhere_is_flagged(flagged):
    assert flagged == {"Measure: Ghost Margin"}
