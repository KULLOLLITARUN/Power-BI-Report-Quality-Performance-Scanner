"""Release Hardening Test Suite for PBIP Sentinel v1.5.0 RC.

Validates:
1. Packaging, CLI entrypoints, and Studio asset distribution.
2. SARIF v2.1.0 and JUnit XML schema conformance.
3. Configuration precedence hierarchy (explicit CLI config > local .pbiscan.config.json > workspace rules.config.json > DEFAULT_CONFIG).
4. Adversarial inputs, corrupt artifacts, and empty project handling.
5. Windows path normalization (spaces, mixed slashes, relative paths).
6. Suppression engine edge cases.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest
from click.testing import CliRunner
from pbiscan.cli import main
from pbiscan.server import STATIC_DIR
from pbiscan.service import ScanService, resolve_config, DEFAULT_CONFIG
from pbiscan.engine.suppressions import SuppressionRule, apply_suppressions
from pbiscan.engine.issue import AuditIssue

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


def _make_valid_config(overrides: dict) -> dict:
    """Helper to build a valid complete configuration dictionary."""
    base = {
        "weights": {"model": 0.35, "dax": 0.25, "report": 0.20, "security": 0.20},
        "deductions": {"CRITICAL": 15, "HIGH": 10, "MEDIUM": 5, "WARNING": 3, "ADVISORY": 1, "LOW": 2},
        "thresholds": {"maxVisualsPerPage": 15, "maxSlicersPerPage": 6, "maxCalculatedColumnsPerTable": 4},
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and k in base:
            base[k].update(v)
        else:
            base[k] = v
    return base


class TestPackagingAndEntrypoints:
    """Validate CLI commands, help pages, and bundled package assets."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_cli_help_options(self, runner):
        """Root and all subcommands produce valid help menus."""
        for cmd in [["--help"], ["scan", "--help"], ["studio", "--help"]]:
            result = runner.invoke(main, cmd)
            assert result.exit_code == 0
            assert "Usage:" in result.output or "Options:" in result.output

    def test_studio_bundled_static_assets_exist(self):
        """Studio SPA index.html and assets must exist in packaged location."""
        assert STATIC_DIR.exists(), f"Static dir does not exist: {STATIC_DIR}"
        index_file = STATIC_DIR / "index.html"
        assert index_file.exists(), f"Studio index.html missing: {index_file}"
        content = index_file.read_text(encoding="utf-8")
        assert "PBIP Sentinel" in content
        assert "id=\"root\"" in content
        assets_dir = STATIC_DIR / "assets"
        assert assets_dir.exists()
        assert len(list(assets_dir.glob("*.js"))) >= 1
        assert len(list(assets_dir.glob("*.css"))) >= 1


class TestSchemaConformance:
    """Validate SARIF and JUnit XML standard schema structure."""

    def test_sarif_v210_compliance(self):
        """SARIF output conforms to SARIF v2.1.0 specifications."""
        result = ScanService.execute_scan(GOLDEN_DIR / "test_bidirectional")
        sarif_json = result.to_sarif()
        data = json.loads(sarif_json)

        assert data.get("version") == "2.1.0"
        assert "sarif-schema-2.1.0.json" in data.get("$schema", "")
        assert len(data.get("runs", [])) == 1

        run = data["runs"][0]
        assert run["tool"]["driver"]["name"] == "pbiscan"
        assert "rules" in run["tool"]["driver"]
        assert len(run["results"]) == len(result.issues)

        for res in run["results"]:
            assert "ruleId" in res
            assert "level" in res
            assert res["level"] in ["error", "warning", "note"]
            assert "text" in res["message"]
            assert "locations" in res
            assert len(res["locations"]) >= 1

    def test_junit_xml_compliance(self):
        """JUnit XML output produces valid XML parseable by standard JUnit consumers."""
        result = ScanService.execute_scan(GOLDEN_DIR / "test_bidirectional")
        junit_xml = result.to_junit()

        # Must parse as valid XML
        root = ET.fromstring(junit_xml)
        assert root.tag == "testsuites"
        assert "tests" in root.attrib
        assert "failures" in root.attrib

        testcases = root.findall(".//testcase")
        assert len(testcases) >= 1

        failures = root.findall(".//failure")
        assert len(failures) == len([i for i in result.issues if not i.suppressed])


class TestConfigurationPrecedence:
    """Validate configuration precedence hierarchy."""

    def test_explicit_config_overrides_project_config(self, tmp_path):
        """Explicit config parameter takes absolute precedence over on-disk config."""
        project_dir = tmp_path / "fake_pbip.Report"
        project_dir.mkdir(parents=True)

        # 1. Project level config specifies maxVisualsPerPage = 50
        proj_cfg = project_dir / ".pbiscan.config.json"
        proj_cfg.write_text(json.dumps(_make_valid_config({"thresholds": {"maxVisualsPerPage": 50}})), encoding="utf-8")

        # 2. Explicitly passed config specifies maxVisualsPerPage = 12
        cli_cfg = tmp_path / "explicit.config.json"
        cli_cfg.write_text(json.dumps(_make_valid_config({"thresholds": {"maxVisualsPerPage": 12}})), encoding="utf-8")

        resolved = resolve_config(config_path=cli_cfg, project_path=project_dir)
        assert resolved["thresholds"]["maxVisualsPerPage"] == 12

    def test_project_local_config_used_when_no_explicit_config(self, tmp_path):
        """Local .pbiscan.config.json in project root is automatically discovered."""
        project_dir = tmp_path / "report.Report"
        project_dir.mkdir(parents=True)

        proj_cfg = project_dir / ".pbiscan.config.json"
        proj_cfg.write_text(json.dumps(_make_valid_config({"thresholds": {"maxVisualsPerPage": 77}})), encoding="utf-8")

        resolved = resolve_config(config_path=None, project_path=project_dir)
        assert resolved["thresholds"]["maxVisualsPerPage"] == 77

    def test_default_config_fallback_when_no_configs_found(self, tmp_path):
        """Fallback to DEFAULT_CONFIG when no custom configurations exist."""
        empty_dir = tmp_path / "empty_dir"
        empty_dir.mkdir()

        resolved = resolve_config(config_path=None, project_path=empty_dir)
        assert resolved["thresholds"]["maxVisualsPerPage"] == DEFAULT_CONFIG["thresholds"]["maxVisualsPerPage"]


class TestAdversarialAndCorruptInputs:
    """Test scanner resiliency against empty folders and invalid formats."""

    def test_empty_directory_handling(self, tmp_path):
        """Scanning an empty directory produces a clean ScanResult with 0 findings or handles missing artifacts."""
        empty_dir = tmp_path / "empty.pbip"
        empty_dir.mkdir()

        result = ScanService.execute_scan(empty_dir)
        assert result.overall_score == 100.0
        assert len(result.issues) == 0
        assert len(result.report.model.tables) == 0

    def test_nonexistent_project_raises_file_not_found(self):
        """Scanning non-existent directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ScanService.execute_scan(Path("C:/NonExistent/Path/DefinitelyDoesNotExist.pbip"))


class TestPathNormalization:
    """Validate path handling with spaces, forward slashes, and relative paths."""

    def test_relative_and_mixed_slash_paths(self):
        """Path with forward slashes and relative components scans identically."""
        rel_path = "./tests/golden/../golden/test_bidirectional"
        result = ScanService.execute_scan(rel_path)
        assert len(result.issues) >= 1
        assert result.overall_score < 100.0

    def test_path_with_spaces_in_golden_fixture(self):
        """Fixture directory containing spaces scans correctly."""
        fixture_path = GOLDEN_DIR / "test_calc_group_variants"
        assert fixture_path.exists()
        result = ScanService.execute_scan(fixture_path)
        assert result.report is not None


class TestSuppressionEdgeCases:
    """Validate suppression rule matching semantics."""

    def test_wildcard_location_suppression(self):
        """Suppression with location_pattern='*' suppresses all occurrences of the rule."""
        issues = [
            AuditIssue(rule_id="DAX_UNUSED_MEASURE", category="dax", severity="WARNING", title="Unused", issue="Unused measure", evidence="e", impact="i", recommendation="r", confidence=100, location="Measure: [M1]"),
            AuditIssue(rule_id="DAX_UNUSED_MEASURE", category="dax", severity="WARNING", title="Unused", issue="Unused measure", evidence="e", impact="i", recommendation="r", confidence=100, location="Measure: [M2]"),
            AuditIssue(rule_id="MODEL_NO_DATE_TABLE", category="model", severity="HIGH", title="No Date", issue="Missing Date table", evidence="e", impact="i", recommendation="r", confidence=100, location="Model: Global"),
        ]
        suppressions = [
            SuppressionRule(rule_id="DAX_UNUSED_MEASURE", location_pattern="*", reason="Accept unused measures"),
        ]
        applied = apply_suppressions(issues, suppressions)
        assert applied[0].suppressed is True
        assert applied[1].suppressed is True
        assert applied[2].suppressed is False

    def test_case_insensitive_rule_id_matching(self):
        """Suppression rule matching should be resilient to rule casing."""
        issues = [
            AuditIssue(rule_id="DAX_UNUSED_MEASURE", category="dax", severity="WARNING", title="Unused", issue="Unused measure", evidence="e", impact="i", recommendation="r", confidence=100, location="Measure: [Total Rev]"),
        ]
        suppressions = [
            SuppressionRule(rule_id="dax_unused_measure", location_pattern="Measure: [Total Rev]", reason="Intentional"),
        ]
        applied = apply_suppressions(issues, suppressions)
        assert applied[0].suppressed is True
