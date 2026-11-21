"""Windows long paths: a file whose full path is 260 characters or more must be read, not skipped.

Windows reports such a file as missing unless the path is in extended-length form, so a reader that
checks `exists()` quietly ignored deep visual files and measures used only there looked unused.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from pbiscan.extraction.raw import extended_path, plain_path_text
from pbiscan.service import ScanService

GOLDEN = Path(__file__).parent.parent / "golden"


class TestPathHelpers:
    """The string logic, checked on every system by naming the platform."""

    def test_a_drive_path_gets_the_extended_prefix(self):
        assert str(extended_path("D:\\Projects\\Report", windows=True)) == "\\\\?\\D:\\Projects\\Report"

    def test_a_network_share_gets_the_unc_form(self):
        assert str(extended_path("\\\\server\\share\\Report", windows=True)) == "\\\\?\\UNC\\server\\share\\Report"

    def test_a_path_already_in_extended_form_is_left_alone(self):
        assert str(extended_path("\\\\?\\D:\\Projects", windows=True)) == "\\\\?\\D:\\Projects"

    def test_dot_segments_and_slashes_are_tidied_because_windows_will_not_do_it_for_extended_paths(self):
        assert str(extended_path("D:/Projects/./a/../Report", windows=True)) == "\\\\?\\D:\\Projects\\Report"

    def test_other_systems_are_unchanged(self):
        assert str(extended_path("/home/me/Report", windows=False)) == str(Path("/home/me/Report"))

    @pytest.mark.parametrize("text", [
        "Skipped \\\\?\\D:\\Projects\\a.tmdl: bad",
        "Skipped \\\\?\\UNC\\server\\share\\a.tmdl: bad",
        "no prefix here",
    ])
    def test_the_prefix_is_removed_from_text_people_read(self, text):
        out = plain_path_text(text)
        assert "?" not in out.split(":")[0] and "\\\\?\\" not in out
        assert plain_path_text(out) == out

    def test_a_network_path_is_restored(self):
        assert plain_path_text("\\\\?\\UNC\\server\\share\\a") == "\\\\server\\share\\a"


def _project_folder(base: Path) -> Path:
    """A project folder of ordinary length (about 200 characters) that is long enough for the files
    inside it to pass the 259-character limit, as a project under a deep Documents or OneDrive path does."""
    pad = max(1, 200 - len(str(base)) - 1)
    return base / ("p" * pad)


@pytest.mark.skipif(os.name != "nt", reason="the 260-character limit applies to Windows only")
class TestDeepProjectOnWindows:
    def test_a_project_with_files_over_259_characters_is_scanned_like_the_same_project_nearby(self, tmp_path):
        source = GOLDEN / "test_report_missing_column"
        deep = _project_folder(tmp_path)
        shutil.copytree(extended_path(source), extended_path(deep))

        longest = max(len(str(p)) for p in Path(extended_path(deep)).rglob("*") if p.is_file()) - len("\\\\?\\")
        assert longest >= 260, "the test project must be deeper than the Windows limit"

        near = ScanService.execute_scan(source)
        far = ScanService.execute_scan(deep)
        assert sorted((i.rule_id, i.location) for i in far.issues) == sorted((i.rule_id, i.location) for i in near.issues)
        assert far.report.report.pages and sum(len(p.visuals) for p in far.report.report.pages) > 0

    def test_results_show_ordinary_paths_not_the_extended_form(self, tmp_path):
        deep = _project_folder(tmp_path)
        shutil.copytree(extended_path(GOLDEN / "test_report_missing_column"), extended_path(deep))
        result = ScanService.execute_scan(deep)
        assert "\\\\?\\" not in result.source_path
        assert all("\\\\?\\" not in w for w in result.warnings)
