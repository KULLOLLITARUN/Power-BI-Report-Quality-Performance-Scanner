"""Golden fixture contract tests for two things the browser engine used to read differently.

test_bim_and_tmdl_model: a model folder holding both model.bim and TMDL files for the same table.
  The Python reader uses model.bim alone. Reading both counted every measure twice, so the browser
  engine reported duplicate measures and a second copy of each unused measure.
  Expected: Orphan is the one unused measure, reported once, and no measure is a duplicate.

test_hidden_table_calc_columns: a visible and a hidden table with 5 calculated columns each.
  Hidden and internal tables (Power BI's auto date tables) are not counted, so only the visible
  table is reported.

Both engines must agree: the parity tests run these fixtures too.
"""
from pathlib import Path

from pbiscan.service import ScanService

GOLDEN = Path(__file__).parent


def _locations(fixture: str, rule_id: str) -> list[str]:
    return [i.location for i in ScanService.execute_scan(GOLDEN / fixture).issues if i.rule_id == rule_id]


def test_a_model_with_bim_and_tmdl_is_read_from_the_bim_alone():
    assert _locations("test_bim_and_tmdl_model", "DAX_UNUSED_MEASURE") == ["Measure: Orphan"]


def test_a_model_with_bim_and_tmdl_has_no_duplicate_measures():
    assert _locations("test_bim_and_tmdl_model", "DAX_DUPLICATE_MEASURE") == []


def test_only_the_visible_table_is_reported_for_calculated_columns():
    assert _locations("test_hidden_table_calc_columns", "DAX_EXCESSIVE_CALC_COLUMNS") == ["Table: Visible"]
