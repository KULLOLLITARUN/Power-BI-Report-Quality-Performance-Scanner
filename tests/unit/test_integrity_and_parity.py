"""Regression tests for Studio integrity, demo fallback prevention, and scan configuration parity."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pbiscan.server import app
from pbiscan.service import ScanService, resolve_config

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


class TestDemoFallbackIntegrity:
    """Test that failed scans never silently substitute demo data."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_scan_failure_returns_404_not_demo(self, client):
        """Invalid path returns 404 error and does not return synthetic demo data."""
        res = client.post("/api/scan", json={"path": "C:\\Invalid\\NonExistent\\Report.pbip"})
        assert res.status_code == 404
        data = res.json()
        assert "Path does not exist" in data["detail"]
        assert "findings" not in data

    def test_scan_failure_with_sales_in_path_returns_404_not_demo(self, client):
        """Invalid path containing 'sales' or 'banana' returns 404 and does not trigger demo mock."""
        res = client.post("/api/scan", json={"path": "C:\\Users\\Customer\\Enterprise_Sales_Report.pbip"})
        assert res.status_code == 404
        data = res.json()
        assert "Path does not exist" in data["detail"]
        assert "findings" not in data


class TestScanAndExportConfigurationParity:
    """Test that /api/scan, /api/export, ScanService, and CLI all produce identical results with custom configuration."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_visual_bloat_threshold_parity(self, client, tmp_path):
        """test_visualbloat fixture has 16 visuals (default threshold 15 fires REPORT_VISUAL_BLOAT).

        When configured with maxVisualsPerPage=25, both /api/scan and /api/export
        must return 0 findings and 100.0 score.
        """
        fixture_path = GOLDEN_DIR / "test_visualbloat"
        custom_cfg = {
            "weights": {"model": 0.35, "dax": 0.25, "report": 0.20, "security": 0.20},
            "deductions": {"CRITICAL": 15, "HIGH": 10, "MEDIUM": 5, "WARNING": 3, "ADVISORY": 1, "LOW": 2},
            "thresholds": {"maxVisualsPerPage": 25, "maxSlicersPerPage": 10, "maxCalculatedColumnsPerTable": 10},
        }
        cfg_file = tmp_path / "custom_rules.config.json"
        cfg_file.write_text(json.dumps(custom_cfg), encoding="utf-8")

        # 1. /api/scan with custom config
        scan_res = client.post("/api/scan", json={"path": str(fixture_path), "config_path": str(cfg_file)})
        assert scan_res.status_code == 200
        scan_data = scan_res.json()

        # 2. /api/export (JSON) with custom config
        export_json_res = client.post(
            "/api/export",
            json={"project_path": str(fixture_path), "config_path": str(cfg_file), "format": "json"},
        )
        assert export_json_res.status_code == 200
        export_data = json.loads(export_json_res.json()["content"])

        # 3. /api/export (SARIF) with custom config
        export_sarif_res = client.post(
            "/api/export",
            json={"project_path": str(fixture_path), "config_path": str(cfg_file), "format": "sarif"},
        )
        assert export_sarif_res.status_code == 200
        sarif_data = json.loads(export_sarif_res.json()["content"])

        # 4. /api/export (JUnit) with custom config
        export_junit_res = client.post(
            "/api/export",
            json={"project_path": str(fixture_path), "config_path": str(cfg_file), "format": "junit"},
        )
        assert export_junit_res.status_code == 200
        junit_content = export_junit_res.json()["content"]

        # 5. Direct ScanService execution with custom config
        service_result = ScanService.execute_scan(fixture_path, config_path=cfg_file)

        # Assert Exact Parity:
        # All 5 consumers must report 0 findings
        assert len(scan_data["findings"]) == 0
        assert len(export_data["findings"]) == 0
        assert len(sarif_data["runs"][0]["results"]) == 0
        assert 'failures="0"' in junit_content
        assert len(service_result.issues) == 0

        # All must report 100.0 overall health score
        assert scan_data["scores"]["overall"] == 100.0
        assert export_data["scores"]["overall"] == 100.0
        assert service_result.overall_score == 100.0

    def test_export_formats_generated_from_canonical_result(self, tmp_path):
        """Verify all export formats (JSON, SARIF, JUnit, HTML) originate from single canonical ScanResult."""
        fixture_path = GOLDEN_DIR / "test_calc_group_variants"
        result = ScanService.execute_scan(fixture_path)

        json_out = result.to_json()
        sarif_out = result.to_sarif()
        junit_out = result.to_junit()
        html_out = result.to_html(timestamp="2026-08-17")

        assert isinstance(json_out, str)
        assert isinstance(sarif_out, str)
        assert isinstance(junit_out, str)
        assert isinstance(html_out, str)

        parsed_json = json.loads(json_out)
        parsed_sarif = json.loads(sarif_out)

        assert len(parsed_json["findings"]) == len(result.issues)
        assert len(parsed_sarif["runs"][0]["results"]) == len(result.issues)
