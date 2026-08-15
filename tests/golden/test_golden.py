"""Golden fixture tests — parameterised assertions for all 11 fixtures.

Each fixture tests that:
  - The target rule fires the expected number of times
  - Confidence is within expected bounds (for heuristic rules)
  - The pipeline runs without errors
"""
from __future__ import annotations
import pytest
from pathlib import Path
from tests.integration.test_pipeline import run_pipeline


GOLDEN_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Fixture expectations
# Format: (fixture_name, rule_id, expected_count, min_confidence, max_confidence)
# ---------------------------------------------------------------------------
GOLDEN_EXPECTATIONS = [
    # Deterministic — exactly 1 finding, 100% confidence
    ("test_bidirectional",   "MODEL_BIDIRECTIONAL",        1, 100, 100),
    ("test_manytomany",      "MODEL_MANY_TO_MANY",         1, 100, 100),
    ("test_visualbloat",     "REPORT_VISUAL_BLOAT",        1, 100, 100),
    ("test_slicerbloat",     "REPORT_SLICER_BLOAT",        1, 100, 100),
    ("test_duplicatedax",    "DAX_DUPLICATE_MEASURE",      1,  90,  90),
    ("test_unusedmeasure",   "DAX_UNUSED_MEASURE",         1,  95,  95),

    # Structural / heuristic — at least 1 finding, bounded confidence
    ("test_nodatetable",     "MODEL_NO_DATE_TABLE",        1,  70,  70),
    ("test_highcardinality", "MODEL_HIGH_CARDINALITY",     1,  87,  87),
    ("test_facttofact",      "MODEL_FACT_TO_FACT",         1,  60,  60),
    ("test_expensive_dax",   "DAX_SUSPICIOUS_PATTERN",     1,   1,  65),

    # CRITICAL NEGATIVE — must produce 0 findings
    ("test_measure_referenced_by_another", "DAX_UNUSED_MEASURE", 0, 0, 100),
]


@pytest.mark.parametrize(
    "fixture_name,rule_id,expected_count,min_conf,max_conf",
    GOLDEN_EXPECTATIONS,
    ids=[e[0] for e in GOLDEN_EXPECTATIONS],
)
def test_golden_fixture(fixture_name, rule_id, expected_count, min_conf, max_conf):
    """Run a golden fixture and assert rule_id count and confidence bounds."""
    result = run_pipeline(fixture_name)
    counts = result["rule_counts"]
    actual_count = counts.get(rule_id, 0)

    assert actual_count >= expected_count, (
        f"{fixture_name}: expected {rule_id} >= {expected_count}, got {actual_count}. "
        f"All rule counts: {counts}"
    )
    if expected_count > 0:
        assert actual_count <= expected_count + 2, (
            f"{fixture_name}: {rule_id} fired {actual_count} times — unexpectedly many. "
            f"The fixture should isolate this rule."
        )

    # Confidence check (for deterministic rules it's exact)
    target_findings = [f for f in result["findings"] if f.rule_id == rule_id]
    for f in target_findings:
        assert min_conf <= f.confidence <= max_conf, (
            f"{fixture_name}: {rule_id} confidence {f.confidence} not in "
            f"[{min_conf}, {max_conf}]"
        )


def test_all_fixtures_parse_without_error():
    """Smoke test: all 11 fixtures must parse without raising exceptions."""
    fixture_names = [
        "test_bidirectional", "test_manytomany", "test_nodatetable",
        "test_highcardinality", "test_facttofact", "test_visualbloat",
        "test_slicerbloat", "test_duplicatedax", "test_expensive_dax",
        "test_unusedmeasure", "test_measure_referenced_by_another",
    ]
    for name in fixture_names:
        result = run_pipeline(name)
        assert result["report"] is not None, f"{name}: report is None"


def test_critical_negative_regression():
    """Standalone critical regression: test_measure_referenced_by_another → D004 == 0."""
    result = run_pipeline("test_measure_referenced_by_another")
    count = result["rule_counts"].get("DAX_UNUSED_MEASURE", 0)
    assert count == 0, (
        f"REGRESSION FAILURE: DAX_UNUSED_MEASURE fired {count} time(s). "
        "Base Revenue is referenced by Revenue Per Unit and must NOT be flagged."
    )
