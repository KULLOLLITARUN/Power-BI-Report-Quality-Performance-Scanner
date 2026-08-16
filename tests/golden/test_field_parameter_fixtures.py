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

    def test_v14_field_parameter_resolution(self, report_and_findings):
        """Validates that Field Parameter NAMEOF() measures are active in v1.4.

        In v1.4 resolution:
        - 'UnusedKPI' is correctly flagged as orphan (True Positive).
        - 'ParameterMeasureA' and 'ParameterMeasureB' are active (0 FP).
        """
        report, unused_findings = report_and_findings
        flagged_locations = {f.location for f in unused_findings}

        assert "Measure: UnusedKPI" in flagged_locations
        assert "Measure: ParameterMeasureA" not in flagged_locations
        assert "Measure: ParameterMeasureB" not in flagged_locations
        assert len(unused_findings) == 1

    def test_provenance_metadata_recorded(self, report_and_findings):
        """Validates exact provenance metadata in SemanticReferenceIndex."""
        report, _ = report_and_findings
        param_a_refs = report.semantic_references.find_by_target("ParameterMeasureA")
        assert len(param_a_refs) == 1
        assert param_a_refs[0].source_type == "field_parameter"
        assert param_a_refs[0].source_object == "MeasureSelector"
        assert param_a_refs[0].target_type == "measure"
