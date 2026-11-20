"""Golden fixture contract tests: a table saved with `dataCategory: Time` is a date table.

Power BI stores "Mark as date table" as a table-level `dataCategory: Time` in TMDL. The name check
is English-only, so a marked table called 'Calendario' used to produce a false MODEL_NO_DATE_TABLE.

- test_date_table_data_category:         'Calendario' is marked with dataCategory: Time (control:
                                         must not be flagged)
- test_date_table_data_category_absent:  no table is marked and none looks like a date table
                                         (true positive: must be flagged)
"""
from pathlib import Path

from pbiscan.service import ScanService

GOLDEN = Path(__file__).parent


def _no_date_table(name: str) -> list:
    result = ScanService.execute_scan(GOLDEN / name)
    return [i for i in result.issues if i.rule_id == "MODEL_NO_DATE_TABLE"]


def test_a_table_marked_with_data_category_time_is_a_date_table():
    assert _no_date_table("test_date_table_data_category") == []


def test_a_model_with_no_date_signal_is_still_flagged():
    assert len(_no_date_table("test_date_table_data_category_absent")) == 1
