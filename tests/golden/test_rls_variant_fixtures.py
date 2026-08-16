"""Golden fixture contract tests for Row-Level Security (RLS) Structural Variants (Phase 2A Evidence).

Validates 6 distinct RLS syntax and lineage variants:
1. Multi-role definitions (RegionalManagerRole and ComplianceOfficerRole).
2. Multi-table permissions (Sales and DimCustomer within same role).
3. Direct measure-based RLS filter expressions (IsUserAuthorizedRegion).
4. Multi-hop transitive measure dependencies cascading from RLS filters (CurrentUserRegion -> UserSecurityHash).
5. Dual visual and RLS referenced measures (TotalSales remains active without interference).
6. Cross-table LOOKUPVALUE expressions in security filters.
7. Genuinely orphaned control measure (UnusedKPI).
"""

from pathlib import Path
import pytest

from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.rules.dax import check_unused_measures

GOLDEN_DIR = Path(__file__).parent


class TestRlsStructuralVariants:
    """Contract tests for RLS structural variants and provenance requirements."""

    @pytest.fixture
    def report_and_findings(self):
        fixture_path = GOLDEN_DIR / "test_rls_variants"
        reader = PBIPReader()
        raw = reader.read(fixture_path)
        builder = CanonicalBuilder()
        report = builder.build(raw)
        unused_findings = check_unused_measures(report)
        return report, unused_findings

    def test_dual_referenced_measure_remains_active(self, report_and_findings):
        """Measures referenced by both visuals and RLS filters (TotalSales) must NOT be flagged."""
        _, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}
        assert "Measure: TotalSales" not in flagged_locations

    def test_rls_filter_measures_and_cascading_dependencies_flagged_in_v13(self, report_and_findings):
        """Documents baseline gap where RLS role filter measures cascade to unused in v1.3.

        In v1.3.0 control baseline:
        - IsUserAuthorizedRegion, ComplianceFlagMeasure (Direct RLS measures) are flagged (False Positives).
        - CurrentUserRegion, UserSecurityHash (Transitive RLS measures) cascade to flagged (Cascading False Positives).
        - UnusedKPI is correctly flagged (True Positive).
        """
        _, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}

        assert "Measure: IsUserAuthorizedRegion" in flagged_locations
        assert "Measure: ComplianceFlagMeasure" in flagged_locations
        assert "Measure: CurrentUserRegion" in flagged_locations
        assert "Measure: UserSecurityHash" in flagged_locations
        assert "Measure: UnusedKPI" in flagged_locations
        assert len(unused_findings) == 5
