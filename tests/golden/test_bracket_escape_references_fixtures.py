"""Golden fixture contract tests for `]]` escapes in measure names.

DAX writes a literal `]` inside a bracketed name as `]]`, so `[Margin [%]]]` names the
measure `Margin [%]`. Each measure below is used in exactly one place that reads its name
with an extractor of its own. Reading `[Margin [%]]]` as `Margin [%` would leave the measure
looking unused, and `pbiscan fix` would offer to delete it.

- 'Margin [%]': [Margin [%]]] in a calculation item
- 'Rate [x]':   [Rate [x]]] in an RLS table permission
- 'Pick [y]':   NAMEOF('Sales'[Pick [y]]]) in a field parameter

Control: 'Orphan [z]' is referenced nowhere and is still flagged.
"""
from pathlib import Path

import pytest

from pbiscan.service import ScanService

FIXTURE = Path(__file__).parent / "test_bracket_escape_references"


@pytest.fixture(scope="module")
def result():
    return ScanService.execute_scan(FIXTURE)


def test_only_the_orphan_is_unused(result):
    unused = {i.location for i in result.issues if i.rule_id == "DAX_UNUSED_MEASURE"}
    assert unused == {"Measure: Orphan [z]"}


@pytest.mark.parametrize(
    ("measure", "source_type"),
    [
        ("Margin [%]", "calc_item"),
        ("Rate [x]", "rls_table_permission"),
        ("Pick [y]", "field_parameter"),
    ],
)
def test_escaped_names_resolve_to_the_measure(result, measure, source_type):
    refs = [
        r for r in result.report.semantic_references.references
        if r.target_name == measure and r.source_type.startswith(source_type)
    ]
    assert refs, f"no {source_type} reference recorded for {measure!r}"
