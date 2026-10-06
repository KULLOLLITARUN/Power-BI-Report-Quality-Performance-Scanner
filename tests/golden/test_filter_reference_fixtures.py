"""Golden fixture contract tests for filter-pane, bookmark and report-extension reachability.

A measure used only in a page-level filter, a report-level filter, a bookmark,
a legacy visual-level `filters` string, or inside a report-level ("thin report")
measure is in use: flagging it as DAX_UNUSED_MEASURE would make `pbiscan fix`
offer to delete a measure the report depends on.

Validates, for both PBIR and legacy report.json layouts:
1. Each of those measures is an active reachability root (0 false positives).
2. Each reference is recorded with the expected provenance source_type.
3. A genuinely orphaned measure is still flagged (true positive preserved).
"""

from pathlib import Path

import pytest

from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.remediation.engine import RemediationEngine
from pbiscan.rules.dax import check_unused_measures

GOLDEN_DIR = Path(__file__).parent


def _build(fixture_name: str):
    raw = PBIPReader().read(GOLDEN_DIR / fixture_name)
    report = CanonicalBuilder().build(raw)
    return report, check_unused_measures(report)


class TestPbirFilterReferences:

    @pytest.fixture
    def built(self):
        return _build("test_pbir_filter_references")

    def test_only_genuinely_unused_measure_flagged(self, built):
        _, unused = built
        assert {f.location for f in unused} == {"Measure: GenuinelyUnusedMetric"}

    @pytest.mark.parametrize("measure, source_type", [
        ("PageFilterMetric", "visual_filter"),
        ("ReportFilterMetric", "report_filter"),
        ("BookmarkMetric", "report_filter"),
        ("ExtensionBaseMetric", "report_extension_measure"),
    ])
    def test_reference_provenance(self, built, measure, source_type):
        report, _ = built
        refs = report.semantic_references.find_by_target(measure)
        assert [r.source_type for r in refs] == [source_type]
        assert refs[0].activates_root

    def test_extension_reference_records_report_measure(self, built):
        report, _ = built
        (ref,) = report.semantic_references.find_by_target("ExtensionBaseMetric")
        assert ref.source_object == "Sales[Report Ratio]"
        assert "DIVIDE([ExtensionBaseMetric], 2)" in (ref.source_expression or "")

    def test_remediation_never_proposes_deleting_filter_measures(self):
        path = GOLDEN_DIR / "test_pbir_filter_references"
        scan = RemediationEngine.analyze(path)
        plan = RemediationEngine.plan(path, scan, rule_filter="DAX_UNUSED_MEASURE")
        targeted = " ".join(str(p.to_dict()) for p in plan.actionable_patches)
        for measure in ("PageFilterMetric", "ReportFilterMetric", "BookmarkMetric", "ExtensionBaseMetric"):
            assert measure not in targeted


class TestLegacyReportJsonFilterReferences:

    @pytest.fixture
    def built(self):
        return _build("test_legacy_filter_references")

    def test_only_genuinely_unused_measure_flagged(self, built):
        _, unused = built
        assert {f.location for f in unused} == {"Measure: GenuinelyUnusedMetric"}

    def test_visual_level_filters_string_is_parsed(self, built):
        report, _ = built
        visual = report.report.pages[0].visuals[0]
        assert "VisualFilterMetric" in visual.measure_refs

    @pytest.mark.parametrize("measure, source_type", [
        ("PageFilterMetric", "visual_filter"),
        ("ReportFilterMetric", "report_filter"),
        ("ExtensionBaseMetric", "report_extension_measure"),
    ])
    def test_reference_provenance(self, built, measure, source_type):
        report, _ = built
        refs = report.semantic_references.find_by_target(measure)
        assert [r.source_type for r in refs] == [source_type]


def test_malformed_report_level_file_does_not_crash(tmp_path):
    """A corrupt bookmark/reportExtensions file is skipped, not fatal."""
    import shutil

    project = tmp_path / "proj"
    shutil.copytree(GOLDEN_DIR / "test_pbir_filter_references", project)
    definition = project / "fixture.Report" / "definition"
    (definition / "bookmarks" / "bm1.bookmark.json").write_text("{not json", encoding="utf-8")
    (definition / "reportExtensions.json").write_text("{not json", encoding="utf-8")

    raw = PBIPReader().read(project)
    report = CanonicalBuilder().build(raw)
    flagged = {f.location for f in check_unused_measures(report)}
    assert "Measure: BookmarkMetric" in flagged
    assert "Measure: PageFilterMetric" not in flagged
