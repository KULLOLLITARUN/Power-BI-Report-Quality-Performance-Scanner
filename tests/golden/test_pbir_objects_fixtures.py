"""Golden fixture contract tests for PBIR visual `objects` measure reference extraction (v1.3).

Validates that measures bound inside PBIR visual property extensions (Card Reference Labels,
Reference Label Details, Dynamic Titles, Subtitles, Conditional Formatting, Dynamic Axis Bounds)
are properly recognized as active visual references, preventing false-positive DAX_UNUSED_MEASURE
findings while preserving accurate detection for genuinely unused measures.
"""

from pathlib import Path
import pytest

from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.rules.dax import check_unused_measures

GOLDEN_DIR = Path(__file__).parent


class TestPbirObjectsMeasureExtraction:
    """Contract tests for PBIR `objects` visual property extraction."""

    @pytest.fixture
    def report_and_unused_findings(self):
        fixture_path = GOLDEN_DIR / "test_pbir_objects_references"
        reader = PBIPReader()
        raw = reader.read(fixture_path)
        builder = CanonicalBuilder()
        report = builder.build(raw)
        unused_findings = check_unused_measures(report)
        return report, unused_findings

    def test_objects_bound_measures_are_extracted(self, report_and_unused_findings):
        """Measures bound inside `objects` subtrees must be captured in visual.measure_refs."""
        report, _ = report_and_unused_findings
        
        all_visual_measure_refs = set()
        for page in report.report.pages:
            for visual in page.visuals:
                all_visual_measure_refs.update(visual.measure_refs)

        expected_objects_measures = {
            "TotalSales",
            "CardRefMetric",
            "CardDetailMetric",
            "DynamicTitleMetric",
            "DynamicSubTitleMetric",
            "ColorFormatMetric",
            "DynamicAxisMetric",
        }
        
        # Verify that all 7 active measures are identified in visual references
        assert expected_objects_measures.issubset(all_visual_measure_refs), (
            f"Missing extracted visual measure references: {expected_objects_measures - all_visual_measure_refs}"
        )

    def test_dax_unused_measure_only_fires_for_genuinely_unused(self, report_and_unused_findings):
        """DAX_UNUSED_MEASURE must NOT fire for objects-bound measures, only for genuinely unused."""
        _, unused_findings = report_and_unused_findings
        
        # GenuinelyUnusedMetric is the only true unused measure
        assert len(unused_findings) == 1, (
            f"Expected exactly 1 unused measure finding, got {len(unused_findings)}: {[f.location for f in unused_findings]}"
        )
        assert unused_findings[0].location == "Measure: GenuinelyUnusedMetric"
