"""Golden fixture contract tests for Complex Deep DAX Dependency Trees (v1.4 Evidence).

Validates:
1. 10-level deep branching DAX dependency graph:
   (Base_Revenue, Base_Cost, Base_Units -> Base_Margin, Avg_Price_Per_Unit -> Weighted_Margin [SUMX] ->
    Filtered_Enterprise_Margin [CALCULATE+FILTER] -> Switched_Scenario_KPI [VAR+SWITCH] ->
    Prior_Year_Scenario_KPI [SAMEPERIODLASTYEAR] -> Final_Executive_Target_Growth [DIVIDE])
   All 10 active measures are recognized as reachable with 0 False Positives.
2. Multi-tier orphaned subtree (Orphan_Branch_L1 -> Orphan_Branch_L2 -> Orphan_Branch_L3)
   is correctly identified as unused with 3 True Positives.
3. Standalone orphan (DeliberatelyUnusedKPI) is correctly identified with 1 True Positive.
4. DOM-05 demonstrates CLEAN BEHAVIOR in v1.3.0 baseline (No candidate defect required).
"""

from pathlib import Path
import pytest

from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.rules.dax import check_unused_measures

GOLDEN_DIR = Path(__file__).parent


class TestComplexDeepDaxDependencyTree:
    """Contract tests for 10-level deep converging DAX dependency graph and orphan subtrees."""

    @pytest.fixture
    def report_and_findings(self):
        fixture_path = GOLDEN_DIR / "test_deep_dax_dependency_tree"
        reader = PBIPReader()
        raw = reader.read(fixture_path)
        builder = CanonicalBuilder()
        report = builder.build(raw)
        unused_findings = check_unused_measures(report)
        return report, unused_findings

    def test_ten_level_deep_converging_dax_tree_is_fully_active(self, report_and_findings):
        """All 10 active measures in the converging dependency tree must NOT be flagged as unused."""
        _, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}

        active_tree_measures = {
            "Measure: Base_Revenue",
            "Measure: Base_Cost",
            "Measure: Base_Units",
            "Measure: Base_Margin",
            "Measure: Avg_Price_Per_Unit",
            "Measure: Weighted_Margin",
            "Measure: Filtered_Enterprise_Margin",
            "Measure: Switched_Scenario_KPI",
            "Measure: Prior_Year_Scenario_KPI",
            "Measure: Final_Executive_Target_Growth",
        }

        # None of the 10 measures in the active tree should be flagged
        overlap = active_tree_measures.intersection(flagged_locations)
        assert not overlap, f"Active DAX tree measures were incorrectly flagged as unused: {overlap}"

    def test_orphan_subtree_and_standalone_orphan_correctly_flagged(self, report_and_findings):
        """All 3 measures in the orphan subtree and the standalone orphan must be flagged (4 TP)."""
        _, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}

        expected_orphans = {
            "Measure: Orphan_Branch_L1",
            "Measure: Orphan_Branch_L2",
            "Measure: Orphan_Branch_L3",
            "Measure: DeliberatelyUnusedKPI",
        }

        assert expected_orphans == flagged_locations
        assert len(unused_findings) == 4
