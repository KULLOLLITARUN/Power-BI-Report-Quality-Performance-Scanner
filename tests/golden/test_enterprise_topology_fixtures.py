"""Golden fixture contract tests for Enterprise Diamond Topologies & Bridge Tables (v1.4 Evidence).

Validates:
1. Complex diamond topology with bridge tables, multiple fact tables, and convergent dimensions
   (DimDate <-> FactSales / FactReturns <-> BridgeCustomer <-> DimCustomer / DimRegion <-> DimManager)
   does not trigger spurious relationship warnings (MODEL_BIDIRECTIONAL, MODEL_MANY_TO_MANY, MODEL_FACT_TO_FACT).
2. Measures traversing multi-fact cross-branch paths (NetSales, ReturnRate, RegionalPerformance)
   are recognized as active with 0 False Positives.
3. Inactive relationships with USERELATIONSHIP (ShipDateSales) and unreferenced measures (UnusedTopologyKPI)
   are accurately detected (True Positives).
4. Isolated parameter tables (DisconnectedConfig) are identified by topology infrastructure
   without inflicting scoring penalties on production rules.
5. DOM-06 demonstrates CLEAN BEHAVIOR in v1.3.0 baseline (No candidate defect required).
"""

from pathlib import Path
import pytest

from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.rules.dax import check_unused_measures
from pbiscan.rules.model import (
    check_bidirectional,
    check_many_to_many,
    check_no_date_table,
    check_fact_to_fact,
)

GOLDEN_DIR = Path(__file__).parent


class TestEnterpriseDiamondTopology:
    """Contract tests for diamond schemas, bridge tables, and inactive relationship networks."""

    @pytest.fixture
    def report_and_findings(self):
        fixture_path = GOLDEN_DIR / "test_enterprise_diamond_topology"
        reader = PBIPReader()
        raw = reader.read(fixture_path)
        builder = CanonicalBuilder()
        report = builder.build(raw)
        unused_findings = check_unused_measures(report)
        return report, unused_findings

    def test_diamond_topology_cross_branch_measures_are_active(self, report_and_findings):
        """Cross-branch measures bound to visual must NOT be flagged as unused."""
        _, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}

        active_measures = {
            "Measure: NetSales",
            "Measure: ReturnRate",
            "Measure: RegionalPerformance",
        }

        overlap = active_measures.intersection(flagged_locations)
        assert not overlap, f"Active diamond topology measures incorrectly flagged: {overlap}"

    def test_unrendered_measures_accurately_flagged(self, report_and_findings):
        """Measures not bound to visuals (ShipDateSales, UnusedTopologyKPI) must be flagged (2 TP)."""
        _, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}

        assert "Measure: ShipDateSales" in flagged_locations
        assert "Measure: UnusedTopologyKPI" in flagged_locations
        assert len(unused_findings) == 2

    def test_diamond_and_bridge_relationships_trigger_no_model_defects(self, report_and_findings):
        """Complex diamond schemas and bridge tables must not trigger spurious model rule warnings."""
        report, _ = report_and_findings
        bidir = check_bidirectional(report)
        m2m = check_many_to_many(report)
        nodate = check_no_date_table(report)
        f2f = check_fact_to_fact(report)

        assert len(bidir) == 0, f"Spurious bidirectional finding: {bidir}"
        assert len(m2m) == 0, f"Spurious many-to-many finding: {m2m}"
        assert len(nodate) == 0, f"Spurious no date table finding: {nodate}"
        assert len(f2f) == 0, f"Spurious fact-to-fact finding: {f2f}"

    def test_topology_graph_infrastructure_detects_isolated_and_multi_paths(self, report_and_findings):
        """SemanticModel topology methods correctly identify isolated table and diamond paths."""
        report, _ = report_and_findings
        assert report.model.isolated_tables() == ["DisconnectedConfig"]
        assert len(report.model.connected_components()) == 2

        # 4 distinct simple paths exist between DimManager and FactSales across active relationships
        paths = report.model.relationship_paths("DimManager", "FactSales")
        assert len(paths) == 4
