"""Golden fixture contract tests for Field Parameters Dynamic Measure Lineage (v1.4 Evidence).

Validates:
1. Documents and locks the observed Field Parameter / NAMEOF() behavior (V14-CAND-02).
2. Measures referenced via Field Parameter calculated tables (NAMEOF('Sales'[Measure]))
   whose parameter columns are projected in visuals are flagged as unused in v1.3.0 baseline (False Positive).
3. Truly orphaned measures (UnusedKPI) remain accurately flagged as unused (True Positive).
"""

from pathlib import Path
import pytest

from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.rules.dax import check_unused_measures

GOLDEN_DIR = Path(__file__).parent


class TestFieldParametersMeasureExtraction:
    """Contract tests for Field Parameters and NAMEOF() dynamic measure reachability."""

    @pytest.fixture
    def report_and_findings(self):
        fixture_path = GOLDEN_DIR / "test_field_parameters_usage"
        reader = PBIPReader()
        raw = reader.read(fixture_path)
        builder = CanonicalBuilder()
        report = builder.build(raw)
        unused_findings = check_unused_measures(report)
        return report, unused_findings

    def test_reproducible_v14_candidate_02_field_parameter_gap(self, report_and_findings):
        """Documents the reproducible V14-CAND-02 gap where Field Parameter NAMEOF() bindings cause false positives in v1.3.

        In v1.3.0 control baseline:
        - 'UnusedKPI' is a True Positive (genuinely unused).
        - 'ParameterMeasureA' and 'ParameterMeasureB' are observed False Positives
          (referenced via Field Parameter table MeasureSelector projected in visual).
        """
        _, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}

        # Assert exact v1.3.0 baseline behavior is locked
        assert "Measure: UnusedKPI" in flagged_locations
        assert "Measure: ParameterMeasureA" in flagged_locations
        assert "Measure: ParameterMeasureB" in flagged_locations
        assert len(unused_findings) == 3
