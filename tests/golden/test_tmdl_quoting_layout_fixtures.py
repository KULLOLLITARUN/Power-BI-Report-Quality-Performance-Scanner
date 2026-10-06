"""Golden fixture contract tests for TMDL layout and quoting.

test_tmdl_quoting_layout exercises TMDL that Power BI and editors produce but
the parser used to misread, each of which silently dropped a table or renamed
a measure (and a renamed measure looks unused to D004):

- a table file saved with a UTF-8 byte-order mark (whole table was dropped)
- `table<TAB>Customer` (whole table was dropped)
- 'Bob''s Sales' — TMDL's doubled-quote escape in table and measure names
- a measure named 'Revenue = Net' (was split at the '=' inside the quotes)
- a ``` fenced expression containing a line that looks like a property
- quoted relationship endpoints ('Bob''s Sales'.'Cust Key')

The true-positive control 'Orphan''s Metric' is still flagged.
"""
from pathlib import Path

import pytest

from pbiscan.service import ScanService

FIXTURE = Path(__file__).parent / "test_tmdl_quoting_layout"


@pytest.fixture(scope="module")
def result():
    return ScanService.execute_scan(FIXTURE)


def test_fixture_table_file_really_has_a_bom():
    data = (FIXTURE / "fixture.SemanticModel" / "definition" / "tables" / "Bob's Sales.tmdl").read_bytes()
    assert data.startswith(b"\xef\xbb\xbf")


def test_every_table_is_read(result):
    assert sorted(t.name for t in result.report.model.tables) == ["Bob's Sales", "Customer", "Date"]
    assert result.warnings == []


def test_measure_names_and_expressions(result):
    measures = {m.name: m.expression for m in result.report.dax.measures}
    assert measures == {
        "Revenue = Net": "[Base Amount] * 2",
        "Base Amount": "SUM('Bob''s Sales'[Amount])",
        "Fenced": "VAR x = [Fence Helper]\nRETURN x",
        "Fence Helper": "1",
        "Orphan's Metric": "42",
    }


def test_quoted_relationship_endpoints(result):
    rels = {(r.from_table, r.from_column, r.to_table, r.to_column) for r in result.report.model.relationships}
    assert rels == {
        ("Bob's Sales", "Cust Key", "Customer", "CustKey"),
        ("Bob's Sales", "Amount", "Date", "Date"),
    }


def test_only_the_orphan_is_unused(result):
    unused = {i.location for i in result.issues if i.rule_id == "DAX_UNUSED_MEASURE"}
    assert unused == {"Measure: Orphan's Metric"}
