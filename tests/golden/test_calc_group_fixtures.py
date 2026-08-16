"""Golden fixture contract tests for Calculation Groups & Deep DAX Chains (v1.4 Evidence).

Validates:
1. Multi-hop DAX reachability: 5-level deep transitive dependencies
   (Base Amount -> Net Amount -> Net Amount YTD -> Net Amount YTD (Ship Date) -> Growth vs Prior Ship-Date YTD %)
   are recognized as active with zero false positives.
2. Inactive relationships with USERELATIONSHIP produce no false-positive relationship diagnostics.
3. Locks the observed Calculation Group / SELECTEDMEASURE() behavior (V14-CAND-01).
"""

from pathlib import Path
import pytest

from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.rules.dax import check_unused_measures
from pbiscan.rules.model import check_bidirectional, check_many_to_many

GOLDEN_DIR = Path(__file__).parent


class TestCalcGroupsAndDeepDaxChains:
    """Contract tests for calculation groups, SELECTEDMEASURE, and deep DAX lineage."""

    @pytest.fixture
    def report_and_findings(self):
        fixture_path = GOLDEN_DIR / "test_calc_groups_selectedmeasure"
        reader = PBIPReader()
        raw = reader.read(fixture_path)
        builder = CanonicalBuilder()
        report = builder.build(raw)
        unused_findings = check_unused_measures(report)
        return report, unused_findings

    def test_five_level_deep_dax_chain_is_fully_reachable(self, report_and_findings):
        """All 5 measures in the deep transitive DAX chain must NOT be flagged as unused."""
        _, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}

        deep_chain_measures = {
            "Measure: Base Amount",
            "Measure: Net Amount",
            "Measure: Net Amount YTD",
            "Measure: Net Amount YTD (Ship Date)",
            "Measure: Growth vs Prior Ship-Date YTD %",
        }

        # None of the 5 measures in the transitive chain should be flagged
        overlap = deep_chain_measures.intersection(flagged_locations)
        assert not overlap, f"Deep DAX chain measures were incorrectly flagged as unused: {overlap}"

    def test_inactive_userelationship_produces_no_model_defects(self, report_and_findings):
        """Inactive relationship used via USERELATIONSHIP must not trigger bidirectional or M:N findings."""
        report, _ = report_and_findings
        bidir = check_bidirectional(report)
        m2m = check_many_to_many(report)
        assert len(bidir) == 0, f"Spurious bidirectional finding on inactive relationship: {bidir}"
        assert len(m2m) == 0, f"Spurious many-to-many finding on inactive relationship: {m2m}"

    def test_reproducible_v14_candidate_01_selectedmeasure_gap(self, report_and_findings):
        """Documents the reproducible V14-CAND-01 gap where SELECTEDMEASURE() causes Raw Margin to be flagged in v1.3.

        In v1.3.0 control baseline:
        - 'UnusedKPI' is a True Positive (genuinely unused).
        - 'Raw Margin' is an observed False Positive (invoked dynamically via Calculation Group SELECTEDMEASURE()).
        """
        _, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}

        # Assert exact v1.3.0 baseline behavior is locked
        assert "Measure: UnusedKPI" in flagged_locations
        assert "Measure: Raw Margin" in flagged_locations
        assert len(unused_findings) == 2
