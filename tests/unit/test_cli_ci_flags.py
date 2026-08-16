"""Unit and integration tests for CLI CI/CD quality gate flags and output formats."""

from pathlib import Path
from click.testing import CliRunner
from pbiscan.cli import main

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


class TestCliCiQualityGates:
    """Test suite for CLI CI flags, fail thresholds, and output formats."""

    def test_cli_default_scan_succeeds(self):
        runner = CliRunner()
        fixture_path = str(GOLDEN_DIR / "test_measure_referenced_by_another")
        result = runner.invoke(main, ["scan", fixture_path])
        assert result.exit_code == 0
        assert "Overall Health" in result.output

    def test_cli_fail_under_triggers_failure_when_below_threshold(self):
        runner = CliRunner()
        # test_enterprise_stress has score ~95
        fixture_path = str(GOLDEN_DIR / "test_enterprise_stress")
        result = runner.invoke(main, ["scan", fixture_path, "--fail-under", "99"])
        assert result.exit_code == 1
        assert "Overall score" in result.output
        assert "is below threshold" in result.output

    def test_cli_fail_under_passes_when_above_threshold(self):
        runner = CliRunner()
        fixture_path = str(GOLDEN_DIR / "test_enterprise_stress")
        result = runner.invoke(main, ["scan", fixture_path, "--fail-under", "90"])
        assert result.exit_code == 0

    def test_cli_fail_on_severity_triggers_failure(self):
        runner = CliRunner()
        # test_enterprise_stress has HIGH and WARNING findings
        fixture_path = str(GOLDEN_DIR / "test_enterprise_stress")
        result = runner.invoke(main, ["scan", fixture_path, "--fail-on", "WARNING"])
        assert result.exit_code == 1
        assert "Found" in result.output
        assert "unsuppressed issue(s) with severity >=" in result.output

    def test_cli_fail_on_higher_severity_passes_when_no_matching_issues(self):
        runner = CliRunner()
        # test_calc_groups_selectedmeasure has only ADVISORY findings
        fixture_path = str(GOLDEN_DIR / "test_calc_groups_selectedmeasure")
        result = runner.invoke(main, ["scan", fixture_path, "--fail-on", "CRITICAL"])
        assert result.exit_code == 0

    def test_cli_format_sarif_file_generation(self, tmp_path):
        runner = CliRunner()
        fixture_path = str(GOLDEN_DIR / "test_calc_group_variants")
        out_file = str(tmp_path / "report.sarif")

        result = runner.invoke(main, ["scan", fixture_path, "--out", out_file, "--format", "sarif"])
        assert result.exit_code == 0
        assert Path(out_file).exists()

        content = Path(out_file).read_text(encoding="utf-8")
        assert "$schema" in content
        assert "sarif-schema-2.1.0" in content
        assert "DynamicFormatKPI" in content

    def test_cli_format_junit_file_generation(self, tmp_path):
        runner = CliRunner()
        fixture_path = str(GOLDEN_DIR / "test_calc_group_variants")
        out_file = str(tmp_path / "report.xml")

        result = runner.invoke(main, ["scan", fixture_path, "--out", out_file, "--format", "junit"])
        assert result.exit_code == 0
        assert Path(out_file).exists()

        content = Path(out_file).read_text(encoding="utf-8")
        assert "<testsuites" in content
        assert "DAX_UNUSED_MEASURE" in content
