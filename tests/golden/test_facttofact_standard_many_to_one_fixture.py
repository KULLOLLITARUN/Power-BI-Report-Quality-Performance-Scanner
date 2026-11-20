"""Golden fixture contract test: a standard many-to-one is never a fact-to-fact link.

'Customer' is a dimension that holds a measure ('# Customers') and has no dimension-style name, so
the old name-and-measures heuristic reported Sales -> Customer as MODEL_FACT_TO_FACT. The "one" side
of a many-to-one is unique by definition. The true-positive controls are the many-to-many fixtures
test_facttofact and test_facttofact_lookalike_dim_names (see tests/golden/test_golden.py).
"""
from pathlib import Path

from pbiscan.service import ScanService

FIXTURE = Path(__file__).parent / "test_facttofact_standard_many_to_one"


def test_a_dimension_with_a_measure_is_not_flagged_as_fact_to_fact():
    result = ScanService.execute_scan(FIXTURE)
    assert [i for i in result.issues if i.rule_id == "MODEL_FACT_TO_FACT"] == []
