"""Golden fixture contract test: only the project's own model counts, not a loose copy beside it.

fixture.SemanticModel has Sales[Amount]. A loose model/ folder next to it is an old copy that still
has Sales[Region]. The report uses Amount and Region, so Region is missing from the real model and
must be reported. An engine that reads every model file in the folder would see Region in the old
copy and report nothing. Both engines must report it: the parity tests run this fixture too.
"""
from pathlib import Path

from pbiscan.service import ScanService

FIXTURE = Path(__file__).parent / "test_loose_model_copy"


def test_a_column_only_a_loose_model_copy_has_is_reported_missing():
    result = ScanService.execute_scan(FIXTURE)
    assert [i.location for i in result.issues if i.rule_id == "REPORT_MISSING_COLUMN"] == ["Column: Sales[Region]"]
