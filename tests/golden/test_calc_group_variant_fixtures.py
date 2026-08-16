"""Golden fixture contract tests for Calculation Group Variants (Phase 2A Evidence).

Validates 5 distinct Calculation Group syntax variants:
1. Direct visual measure passing through SELECTEDMEASURE() (ActualSales).
2. Explicit measure bracket references inside calculationItem DAX expressions (BudgetSales).
3. Measure introspection inside ISSELECTEDMEASURE() predicates (TargetMargin).
4. Calculation group precedence ordering (TimeCalcGroup prec 20, CurrencyCalcGroup prec 10).
5. formatStringDefinition expressions with SELECTEDMEASUREFORMATSTRING().
6. Genuinely unused control measures (UnusedKPI, DynamicFormatKPI).
"""

from pathlib import Path
import pytest

from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.rules.dax import check_unused_measures

GOLDEN_DIR = Path(__file__).parent


class TestCalculationGroupVariants:
    """Contract tests for Calculation Group structural variants and provenance requirements."""

    @pytest.fixture
    def report_and_findings(self):
        fixture_path = GOLDEN_DIR / "test_calc_group_variants"
        reader = PBIPReader()
        raw = reader.read(fixture_path)
        builder = CanonicalBuilder()
        report = builder.build(raw)
        unused_findings = check_unused_measures(report)
        return report, unused_findings

    def test_direct_visual_measure_through_selectedmeasure_is_active(self, report_and_findings):
        """Directly projected measure evaluated by SELECTEDMEASURE() is active (0 findings)."""
        _, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}
        assert "Measure: ActualSales" not in flagged_locations

    def test_calc_item_bracket_and_isselectedmeasure_references_flagged_in_v13(self, report_and_findings):
        """Documents baseline gap where calculation item DAX and ISSELECTEDMEASURE measures are flagged.

        In v1.3.0 control baseline:
        - BudgetSales (used in calc item 'vs Budget %') is flagged (False Positive).
        - TargetMargin (used in calc item 'Custom Logic' ISSELECTEDMEASURE) is flagged (False Positive).
        - DynamicFormatKPI & UnusedKPI are flagged (True Positives).
        """
        _, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}

        assert "Measure: BudgetSales" in flagged_locations
        assert "Measure: TargetMargin" in flagged_locations
        assert "Measure: DynamicFormatKPI" in flagged_locations
        assert "Measure: UnusedKPI" in flagged_locations
        assert len(unused_findings) == 4
