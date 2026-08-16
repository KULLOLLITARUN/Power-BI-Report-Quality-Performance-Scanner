"""Edge cases and CLI resilience tests for PBIP Sentinel (v1.3).

Tests minimal empty models, corrupted metadata, and CLI error boundaries.
"""

from pathlib import Path
import pytest
from click.testing import CliRunner

from pbiscan.cli import scan
from pbiscan.extraction.pbip_reader import PBIPReader, PBIScanError, InputError, ParseError
from pbiscan.canonical.builder import CanonicalBuilder


class TestEdgeCasesAndCLI:
    """Test minimal models and robust error handling."""

    def test_minimal_empty_pbip(self, tmp_path):
        """A PBIP with 0 tables, 0 measures, and 0 pages must parse cleanly and score 100."""
        proj_dir = tmp_path / "EmptyModel"
        proj_dir.mkdir()
        (proj_dir / "EmptyModel.pbip").write_text('{"version": "1.0"}', encoding="utf-8")

        report_dir = proj_dir / "EmptyModel.Report"
        def_dir = report_dir / "definition"
        def_dir.mkdir(parents=True)
        (def_dir / "report.json").write_text('{"name": "Empty"}', encoding="utf-8")
        (report_dir / "definition.pbir").write_text('{"version": "4.0", "datasetReference": {"byPath": {"path": "../EmptyModel.SemanticModel"}}}', encoding="utf-8")

        sm_dir = proj_dir / "EmptyModel.SemanticModel"
        tmdl_dir = sm_dir / "definition" / "tables"
        tmdl_dir.mkdir(parents=True)
        (sm_dir / "definition.pbism").write_text('{"version": "4.0"}', encoding="utf-8")
        (sm_dir / "definition" / "model.tmdl").write_text("model Model\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(scan, [str(proj_dir / "EmptyModel.pbip")])
        assert result.exit_code == 0
        assert "Overall Health:  100" in result.output
        assert "[PASS] No findings" in result.output

    def test_nonexistent_pbip_path(self, tmp_path):
        """Scanning a non-existent path must fail gracefully with exit code 1 or 2."""
        fake_path = tmp_path / "NonExistent.pbip"
        runner = CliRunner()
        result = runner.invoke(scan, [str(fake_path)])
        assert result.exit_code != 0
        assert "Extraction failed" in result.output or "Error" in result.output or "not exist" in result.output

    def test_corrupted_json_in_pbip(self, tmp_path):
        """Malformed JSON in legacy report.json must be caught gracefully with exit code 2."""
        proj_dir = tmp_path / "BrokenModel"
        proj_dir.mkdir()
        (proj_dir / "BrokenModel.pbip").write_text('{"version": "1.0"}', encoding="utf-8")

        report_dir = proj_dir / "BrokenModel.Report"
        report_dir.mkdir(parents=True)
        (report_dir / "report.json").write_text('{ unclosed invalid json :::: ', encoding="utf-8")

        sm_dir = proj_dir / "BrokenModel.SemanticModel"
        tmdl_dir = sm_dir / "definition"
        tmdl_dir.mkdir(parents=True)
        (sm_dir / "definition.pbism").write_text('{"version": "4.0"}', encoding="utf-8")
        (sm_dir / "definition" / "model.tmdl").write_text("model Model\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(scan, [str(proj_dir / "BrokenModel.pbip")])
        assert result.exit_code == 2
        assert "Extraction failed" in result.output
