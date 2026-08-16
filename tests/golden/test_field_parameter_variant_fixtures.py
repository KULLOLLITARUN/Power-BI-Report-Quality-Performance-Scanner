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

    def test_field_parameter_variants_and_cascading_dependencies_resolved_in_v14(self, report_and_findings):
        """Validates that all field parameter measures and cascading dependencies are resolved in v1.4.

        In v1.4 resolution:
        - NetRevenue, UnitsSold (Variant 1 pure measure targets) are active (0 FP).
        - ProfitMargin, SlicerActivatedMetric (Variant 3 & 4 grouped/slicer targets) are active (0 FP).
        - BaseRevenue (Variant 5 transitive base measure) is reachable and active (0 FP).
        - UnusedKPI is correctly flagged as orphan (True Positive).
        """
        report, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}

        assert "Measure: NetRevenue" not in flagged_locations
        assert "Measure: UnitsSold" not in flagged_locations
        assert "Measure: ProfitMargin" not in flagged_locations
        assert "Measure: SlicerActivatedMetric" not in flagged_locations
        assert "Measure: BaseRevenue" not in flagged_locations
        assert "Measure: UnusedKPI" in flagged_locations
        assert len(unused_findings) == 1

    def test_entity_discrimination_and_provenance(self, report_and_findings):
        """Validates entity discrimination (column vs measure) and provenance."""
        report, _ = report_and_findings
        # Column reference inside field param should be classified as column and NOT activate root
        cat_refs = report.semantic_references.find_by_target("Category")
        assert len(cat_refs) == 1
        assert cat_refs[0].target_type == "column"
        assert cat_refs[0].activates_root is False

        # Grouped parameter should record field_parameter_grouped
        margin_refs = report.semantic_references.find_by_target("ProfitMargin")
        assert len(margin_refs) == 1
        assert margin_refs[0].source_type == "field_parameter_grouped"
        assert margin_refs[0].source_object == "GroupedSelector"
