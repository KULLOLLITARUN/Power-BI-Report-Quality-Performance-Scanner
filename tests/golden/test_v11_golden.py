"""v1.1 Golden Fixture tests — establishing expected baseline contracts for v1.1.

Fixtures created per v1.1_ARCHITECTURE.md Section 6:
  - test_dax_graph_multihop: 3+ measure chain (C -> B -> A). Visual only contains C.
  - test_dax_graph_cycle: Two measures referencing each other in a loop.
  - test_topology_disconnected: Table with 0 relationships (isolated table).
  - test_topology_ambiguous_path: Two tables connected by 2 distinct active paths (+ single-path negative baseline).
  - test_suppression_scoring: 3 findings, 1 suppressed via pbiscan.suppressions.json.
  - test_suppression_absent_file: Same 3 findings, no pbiscan.suppressions.json.
"""
from __future__ import annotations
from pathlib import Path
import pytest
from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from tests.integration.test_pipeline import run_pipeline


GOLDEN_DIR = Path(__file__).parent


V11_FIXTURE_NAMES = [
    "test_dax_graph_multihop",
    "test_dax_graph_cycle",
    "test_topology_disconnected",
    "test_topology_ambiguous_path",
    "test_suppression_scoring",
    "test_suppression_absent_file",
]


@pytest.mark.parametrize("fixture_name", V11_FIXTURE_NAMES)
def test_v11_fixtures_parse_without_error(fixture_name: str):
    """Smoke test: all v1.1 golden fixtures must parse without raising exceptions."""
    reader = PBIPReader()
    raw = reader.read(GOLDEN_DIR / fixture_name)
    assert raw is not None, f"{fixture_name}: raw is None"

    builder = CanonicalBuilder()
    report = builder.build(raw)
    assert report is not None, f"{fixture_name}: canonical report is None"
    assert report.model is not None, f"{fixture_name}: model is None"
    assert report.dax is not None, f"{fixture_name}: dax is None"
    assert report.report is not None, f"{fixture_name}: report is None"


def test_dax_graph_multihop_raw_contract():
    """Verify raw measures in multihop fixture."""
    reader = PBIPReader()
    raw = reader.read(GOLDEN_DIR / "test_dax_graph_multihop")
    builder = CanonicalBuilder()
    report = builder.build(raw)

    measure_names = {m.name for m in report.dax.measures}
    assert measure_names == {"Base Profit", "Net Margin", "Final KPI"}

    # Base Profit is referenced by Net Margin, which is referenced by Final KPI
    # Final KPI is bound to the visual
    visual_measure_refs = set()
    for p in report.report.pages:
        for v in p.visuals:
            for ref in v.measure_refs:
                visual_measure_refs.add(ref)

    assert "Final KPI" in visual_measure_refs


def test_dax_graph_cycle_raw_contract():
    """Verify raw measures in cycle fixture."""
    reader = PBIPReader()
    raw = reader.read(GOLDEN_DIR / "test_dax_graph_cycle")
    builder = CanonicalBuilder()
    report = builder.build(raw)

    measure_names = {m.name for m in report.dax.measures}
    assert measure_names == {"Cycle Measure A", "Cycle Measure B"}


def test_topology_disconnected_raw_contract():
    """Verify tables and relationships in disconnected topology fixture."""
    reader = PBIPReader()
    raw = reader.read(GOLDEN_DIR / "test_topology_disconnected")
    builder = CanonicalBuilder()
    report = builder.build(raw)

    table_names = {t.name for t in report.model.tables}
    assert table_names == {"FactSales", "DimCustomer", "DimDate", "IsolatedAuditLog"}
    assert len(report.model.relationships) == 2

    # Topology query assertions
    assert report.model.isolated_tables() == ["IsolatedAuditLog"]
    comps = report.model.connected_components()
    assert len(comps) == 2
    assert {"FactSales", "DimCustomer", "DimDate"} in comps
    assert {"IsolatedAuditLog"} in comps


def test_topology_ambiguous_path_raw_contract():
    """Verify tables and relationships in ambiguous path topology fixture."""
    reader = PBIPReader()
    raw = reader.read(GOLDEN_DIR / "test_topology_ambiguous_path")
    builder = CanonicalBuilder()
    report = builder.build(raw)

    table_names = {t.name for t in report.model.tables}
    assert table_names == {"FactSales", "DimStore", "DimRegion", "DimCustomer", "DimCity", "DimDate"}
    assert len(report.model.relationships) == 5

    # Positive case: 2 active paths between FactSales and DimRegion
    sales_to_region_paths = report.model.relationship_paths("FactSales", "DimRegion")
    assert len(sales_to_region_paths) == 2
    path_tuples = [tuple(p) for p in sales_to_region_paths]
    assert ("FactSales", "DimRegion") in path_tuples
    assert ("FactSales", "DimStore", "DimRegion") in path_tuples

    # Negative baseline case: exactly 1 path between FactSales and DimCity
    sales_to_city_paths = report.model.relationship_paths("FactSales", "DimCity")
    assert len(sales_to_city_paths) == 1
    assert sales_to_city_paths[0] == ["FactSales", "DimCustomer", "DimCity"]


def test_suppression_scoring_fixture_contract():
    """Verify suppression fixture files exist and parse cleanly."""
    suppressions_path = GOLDEN_DIR / "test_suppression_scoring" / "pbiscan.suppressions.json"
    assert suppressions_path.exists(), "pbiscan.suppressions.json must exist in test_suppression_scoring"

    absent_path = GOLDEN_DIR / "test_suppression_absent_file" / "pbiscan.suppressions.json"
    assert not absent_path.exists(), "pbiscan.suppressions.json must NOT exist in test_suppression_absent_file"


def test_dax_graph_multihop_pipeline_regression():
    """Pipeline integration: Final KPI in visual -> Base Profit & Net Margin transitively reachable -> D004 == 0."""
    result = run_pipeline("test_dax_graph_multihop")
    unused_count = result["rule_counts"].get("DAX_UNUSED_MEASURE", 0)
    assert unused_count == 0, (
        f"Transitive regression failure: DAX_UNUSED_MEASURE fired {unused_count} times on multihop fixture. "
        "Base Profit and Net Margin must be recognized as used via Final KPI."
    )


def test_dax_graph_cycle_pipeline_safety():
    """Pipeline integration: Circular references must terminate cleanly without infinite loop or crash."""
    result = run_pipeline("test_dax_graph_cycle")
    assert result["report"] is not None
    assert result["scores"] is not None
