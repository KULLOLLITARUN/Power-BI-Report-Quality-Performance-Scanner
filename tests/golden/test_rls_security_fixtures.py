"""Golden fixture contract tests for Row-Level Security (RLS) Lineage (v1.4 Evidence).

Validates:
1. Documents and locks the observed RLS role filter measure reachability behavior (V14-CAND-03).
2. Measures referenced exclusively inside TMDL / TMSL Role tablePermission DAX expressions
   (e.g., [SalesRegionSecurityMeasure] == 1) are flagged as unused in v1.3.0 baseline (False Positive).
3. Truly orphaned measures (UnusedKPI) remain accurately flagged as unused (True Positive).
4. Model rules correctly recognize security tables linked via relationships without spurious findings.
"""

from pathlib import Path
import pytest

from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.rules.dax import check_unused_measures
from pbiscan.rules.model import check_bidirectional, check_many_to_many

GOLDEN_DIR = Path(__file__).parent


class TestRlsSecurityMeasureExtraction:
    """Contract tests for Row-Level Security role expressions and dynamic measure reachability."""

    @pytest.fixture
    def report_and_findings(self):
        fixture_path = GOLDEN_DIR / "test_rls_ols_security"
        reader = PBIPReader()
        raw = reader.read(fixture_path)
        builder = CanonicalBuilder()
        report = builder.build(raw)
        unused_findings = check_unused_measures(report)
        return report, unused_findings

    def test_reproducible_v14_candidate_03_rls_measure_gap(self, report_and_findings):
        """Documents the reproducible V14-CAND-03 gap where RLS role filter measures are flagged in v1.3.

        In v1.3.0 control baseline:
        - 'UnusedKPI' is a True Positive (genuinely unused).
        - 'SalesRegionSecurityMeasure' is an observed False Positive
          (referenced only in roles/RegionalManagerRole.tmdl tablePermission).
        - 'TotalSales' is active in report visual (not flagged).
        """
        _, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}

        # Assert exact v1.3.0 baseline behavior is locked
        assert "Measure: UnusedKPI" in flagged_locations
        assert "Measure: SalesRegionSecurityMeasure" in flagged_locations
        assert "Measure: TotalSales" not in flagged_locations
        assert len(unused_findings) == 2

    def test_rls_security_relationships_produce_no_model_noise(self, report_and_findings):
        """Security dimension relationships (DimUser -> Sales) must not trigger spurious model findings."""
        report, _ = report_and_findings
        bidir = check_bidirectional(report)
        m2m = check_many_to_many(report)
        assert len(bidir) == 0
        assert len(m2m) == 0
