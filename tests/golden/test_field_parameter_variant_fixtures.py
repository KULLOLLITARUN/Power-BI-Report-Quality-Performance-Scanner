"""Golden fixture contract tests for Field Parameter Structural Variants (Phase 2A Evidence).

Validates 5 distinct Field Parameter syntax variants:
1. Pure measure parameter targets (NetRevenue, UnitsSold).
2. Mixed dimension and measure parameter tables (DimProduct[Category] + Sales[Measures]).
3. Multi-column 4-tuple grouped parameter tables (ProfitMargin with Group column).
4. Slicer-only parameter projections (SlicerActivatedMetric in standalone slicer).
5. Transitive measure dependency cascading from parameter targets (BaseRevenue).
6. Genuinely orphaned control measure (UnusedKPI).
"""

from pathlib import Path
import pytest

from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.rules.dax import check_unused_measures

GOLDEN_DIR = Path(__file__).parent


class TestFieldParameterVariants:
    """Contract tests for Field Parameter structural variants and provenance requirements."""

    @pytest.fixture
    def report_and_findings(self):
        fixture_path = GOLDEN_DIR / "test_field_parameter_variants"
        reader = PBIPReader()
        raw = reader.read(fixture_path)
        builder = CanonicalBuilder()
        report = builder.build(raw)
        unused_findings = check_unused_measures(report)
        return report, unused_findings

    def test_field_parameter_variants_and_cascading_dependencies_flagged_in_v13(self, report_and_findings):
        """Documents baseline gap where all 5 field parameter measures cascade to unused in v1.3.

        In v1.3.0 control baseline:
        - NetRevenue, UnitsSold (Variant 1 pure measure targets) are flagged (False Positives).
        - ProfitMargin, SlicerActivatedMetric (Variant 3 & 4 grouped/slicer targets) are flagged (False Positives).
        - BaseRevenue (Variant 5 transitive base measure) cascades to flagged (Cascading False Positive).
        - UnusedKPI is correctly flagged (True Positive).
        """
        _, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}

        assert "Measure: NetRevenue" in flagged_locations
        assert "Measure: UnitsSold" in flagged_locations
        assert "Measure: ProfitMargin" in flagged_locations
        assert "Measure: SlicerActivatedMetric" in flagged_locations
        assert "Measure: BaseRevenue" in flagged_locations
        assert "Measure: UnusedKPI" in flagged_locations
        assert len(unused_findings) == 6
