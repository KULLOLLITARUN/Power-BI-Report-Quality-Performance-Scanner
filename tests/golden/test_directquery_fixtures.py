"""Golden fixture contract tests for DirectQuery & Composite Storage Models (v1.4 Evidence).

Validates:
1. TMDL partitions with mixed storage modes (DirectQuery, Dual, Import) parse cleanly.
2. DirectQuery measures and transitive dependencies across storage boundaries are recognized as active with 0 FP.
3. Truly orphaned measures (UnusedKPI) remain accurately flagged (1 TP).
4. Relationships across DirectQuery, Dual, and Import tables trigger no spurious model findings.
5. DOM-04 demonstrates CLEAN BEHAVIOR in v1.3.0 baseline (No candidate defect required).
"""

from pathlib import Path
import pytest

from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.rules.dax import check_unused_measures
from pbiscan.rules.model import check_bidirectional, check_many_to_many, check_no_date_table

GOLDEN_DIR = Path(__file__).parent


class TestDirectQueryCompositeStorage:
    """Contract tests for DirectQuery, Dual, and Import composite models."""

    @pytest.fixture
    def report_and_findings(self):
        fixture_path = GOLDEN_DIR / "test_directquery_composite_storage"
        reader = PBIPReader()
        raw = reader.read(fixture_path)
        builder = CanonicalBuilder()
        report = builder.build(raw)
        unused_findings = check_unused_measures(report)
        return report, unused_findings

    def test_directquery_measures_reachability_is_clean(self, report_and_findings):
        """DirectQuery measures and multi-hop dependencies across storage modes must NOT be flagged as unused."""
        _, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}

        # Assert only UnusedKPI is flagged; DirectQuery measures are active
        assert "Measure: UnusedKPI" in flagged_locations
        assert "Measure: DirectQueryFilteredSales" not in flagged_locations
        assert "Measure: DirectQuerySales" not in flagged_locations
        assert len(unused_findings) == 1

    def test_composite_relationships_and_date_rules_are_clean(self, report_and_findings):
        """Cross-storage mode relationships and date tables must not trigger spurious model warnings."""
        report, _ = report_and_findings
        bidir = check_bidirectional(report)
        m2m = check_many_to_many(report)
        nodate = check_no_date_table(report)

        assert len(bidir) == 0, f"Spurious bidirectional finding: {bidir}"
        assert len(m2m) == 0, f"Spurious many-to-many finding: {m2m}"
        assert len(nodate) == 0, f"Spurious no date table finding: {nodate}"
