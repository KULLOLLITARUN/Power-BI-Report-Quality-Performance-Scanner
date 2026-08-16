"""Integration tests for Unified Semantic Reference Index pipeline in CanonicalBuilder."""

from pathlib import Path
from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.canonical.references import SemanticReferenceIndex

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


class TestSemanticReferenceIndexIntegration:
    """Integration test suite for CanonicalBuilder and SemanticReferenceIndex."""

    def test_calc_group_references_in_canonical_builder(self):
        fixture_path = GOLDEN_DIR / "test_calc_group_variants"
        reader = PBIPReader()
        raw = reader.read(fixture_path)
        builder = CanonicalBuilder()
        report = builder.build(raw)

        assert isinstance(report.semantic_references, SemanticReferenceIndex)
        active_roots = report.semantic_references.active_root_measure_names()

        # Visual projection
        assert "ActualSales" in active_roots
        # Calc item DAX
        assert "BudgetSales" in active_roots
        # ISSELECTEDMEASURE predicate
        assert "TargetMargin" in active_roots
        # Control orphans not in roots
        assert "DynamicFormatKPI" not in active_roots
        assert "UnusedKPI" not in active_roots

    def test_field_parameter_references_in_canonical_builder(self):
        fixture_path = GOLDEN_DIR / "test_field_parameter_variants"
        reader = PBIPReader()
        raw = reader.read(fixture_path)
        builder = CanonicalBuilder()
        report = builder.build(raw)

        active_roots = report.semantic_references.active_root_measure_names()
        assert "NetRevenue" in active_roots
        assert "UnitsSold" in active_roots
        assert "ProfitMargin" in active_roots
        assert "SlicerActivatedMetric" in active_roots

        # Column reference in field param must NOT be in active measure roots
        assert "Category" not in active_roots
        assert "UnusedKPI" not in active_roots

    def test_rls_references_in_canonical_builder(self):
        fixture_path = GOLDEN_DIR / "test_rls_variants"
        reader = PBIPReader()
        raw = reader.read(fixture_path)
        builder = CanonicalBuilder()
        report = builder.build(raw)

        active_roots = report.semantic_references.active_root_measure_names()
        assert "IsUserAuthorizedRegion" in active_roots
        assert "ComplianceFlagMeasure" in active_roots
        assert "TotalSales" in active_roots
        assert "UnusedKPI" not in active_roots
