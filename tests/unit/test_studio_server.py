"""Unit, integration, and hardening tests for pbiscan Studio FastAPI server endpoints."""

from pathlib import Path
import json
import pytest
from fastapi.testclient import TestClient
from pbiscan import __version__
from pbiscan.server import app

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


class TestStudioServerApi:
    """Comprehensive test suite for FastAPI backend endpoints & hardening contracts."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health_check(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "pbiscan-studio"
        assert data["version"] == __version__

    def test_scan_project_golden_fixture(self, client):
        fixture_path = str(GOLDEN_DIR / "test_calc_group_variants")
        response = client.post("/api/scan", json={"path": fixture_path})
        assert response.status_code == 200
        data = response.json()

        assert "scores" in data
        assert "findings" in data
        assert "tables" in data
        assert "relationships" in data
        assert "measures" in data
        assert "pages" in data
        assert "semantic_references" in data
        assert "dax_graph" in data

        # Check semantic reference payload
        sem_refs = data["semantic_references"]
        assert sem_refs["total_count"] >= 1
        assert "ActualSales" in sem_refs["active_roots"]

        # Check DAX graph DAG payload
        dax_graph = data["dax_graph"]
        assert "nodes" in dax_graph
        assert "edges" in dax_graph
        assert "has_cycles" in dax_graph

    def test_scan_nonexistent_path_returns_404(self, client):
        response = client.post("/api/scan", json={"path": "non_existent_folder_12345"})
        assert response.status_code == 404
        assert "Path does not exist" in response.json()["detail"]

    def test_browse_filesystem(self, client):
        response = client.post("/api/browse", json={"path": str(GOLDEN_DIR)})
        assert response.status_code == 200
        data = response.json()
        assert "current_path" in data
        assert "pbip_projects" in data
        assert len(data["pbip_projects"]) >= 1

    def test_serve_spa_index_page(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "PBIP Sentinel" in response.text
        assert 'id="root"' in response.text

    def test_spa_client_routing_fallback(self, client):
        """SPA fallback should serve index.html for virtual frontend routes."""
        for route in ("/overview", "/findings", "/dax-dag", "/model", "/sem-refs", "/canvas"):
            response = client.get(route)
            assert response.status_code == 200
            assert "PBIP Sentinel" in response.text
            assert 'id="root"' in response.text

    def test_export_endpoints(self, client):
        fixture_path = str(GOLDEN_DIR / "test_calc_group_variants")

        # 1. HTML export
        resp_html = client.post("/api/export", json={"project_path": fixture_path, "format": "html"})
        assert resp_html.status_code == 200
        assert "<!DOCTYPE html>" in resp_html.json()["content"]

        # 2. SARIF export
        resp_sarif = client.post("/api/export", json={"project_path": fixture_path, "format": "sarif"})
        assert resp_sarif.status_code == 200
        assert "2.1.0" in resp_sarif.json()["content"]

        # 3. JUnit export
        resp_junit = client.post("/api/export", json={"project_path": fixture_path, "format": "junit"})
        assert resp_junit.status_code == 200
        assert "<testsuites" in resp_junit.json()["content"]

        # 4. JSON export
        resp_json = client.post("/api/export", json={"project_path": fixture_path, "format": "json"})
        assert resp_json.status_code == 200
        assert "scores" in resp_json.json()["content"]

    def test_export_and_scan_parity(self, client):
        """Ensure /api/scan and /api/export generate exact finding counts and scores."""
        fixture_path = str(GOLDEN_DIR / "test_m_hardcoded_datasource")
        scan_res = client.post("/api/scan", json={"path": fixture_path}).json()
        export_res = client.post("/api/export", json={"project_path": fixture_path, "format": "json"}).json()
        export_data = json.loads(export_res["content"])

        assert len(scan_res["findings"]) == len(export_data["findings"])
        assert scan_res["scores"]["overall"] == export_data["scores"]["overall"]

    def test_export_nonexistent_path_returns_404(self, client):
        response = client.post("/api/export", json={"project_path": "invalid_path_404", "format": "html"})
        assert response.status_code == 404

    def test_suppress_endpoint_and_lifecycle(self, client):
        fixture_path = GOLDEN_DIR / "test_unusedmeasure"
        # First scan without suppression to get exact finding
        scan_before = client.post("/api/scan", json={"path": str(fixture_path)}).json()
        assert len(scan_before["findings"]) >= 1
        target_f = scan_before["findings"][0]

        supp_file = fixture_path / "pbiscan.suppressions.json"
        if supp_file.exists():
            supp_file.unlink()

        try:
            # 1. Add suppression using exact rule_id and location from finding
            resp = client.post("/api/suppress", json={
                "project_path": str(fixture_path),
                "rule_id": target_f["rule_id"],
                "location": target_f["location"],
                "reason": "Test studio suppression"
            })
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"
            assert supp_file.exists()

            # 2. Rescan and verify suppression applied
            scan_after = client.post("/api/scan", json={"path": str(fixture_path)}).json()
            suppressed_findings = [f for f in scan_after["findings"] if f.get("suppressed")]
            assert len(suppressed_findings) >= 1
            assert suppressed_findings[0]["rule_id"] == target_f["rule_id"]
        finally:
            if supp_file.exists():
                supp_file.unlink()

    def test_suppress_nonexistent_path_returns_404(self, client):
        response = client.post("/api/suppress", json={
            "project_path": "invalid_path_404",
            "rule_id": "TEST_RULE",
            "location": "Loc"
        })
        assert response.status_code == 404

    def test_studio_diff_api_success(self, client):
        fixture = str(GOLDEN_DIR / "test_calc_group_variants")
        resp = client.post("/api/diff", json={
            "baseline_path": fixture,
            "current_path": fixture,
            "fail_on_regression": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "score_drift" in data
        assert "transitions" in data
        assert "counts" in data
        assert "quality_gate" in data
        assert data["counts"]["new"] == 0
        assert data["counts"]["resolved"] == 0
        assert data["quality_gate"]["passed"] is True

    def test_studio_diff_api_with_quality_gate_policy(self, client):
        fixture1 = str(GOLDEN_DIR / "test_calc_group_variants")
        fixture2 = str(GOLDEN_DIR / "test_field_parameter_variants")
        resp = client.post("/api/diff", json={
            "baseline_path": fixture1,
            "current_path": fixture2,
            "fail_on_regression": True,
            "fail_on_new": "CRITICAL",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "score_drift" in data
        assert data["quality_gate"]["passed"] is False  # Regressed score

    def test_studio_diff_api_missing_paths_returns_404(self, client):
        resp_base = client.post("/api/diff", json={
            "baseline_path": "nonexistent_base_404",
            "current_path": str(GOLDEN_DIR / "test_calc_group_variants"),
        })
        assert resp_base.status_code == 404

        resp_curr = client.post("/api/diff", json={
            "baseline_path": str(GOLDEN_DIR / "test_calc_group_variants"),
            "current_path": "nonexistent_curr_404",
        })
        assert resp_curr.status_code == 404

    def test_studio_diff_never_returns_demo_fallback(self, client):
        resp = client.post("/api/diff", json={
            "baseline_path": "sample_bananas_nonexistent",
            "current_path": "sample_enterprise_nonexistent",
        })
        assert resp.status_code == 404
        assert resp.json().get("detail") is not None

    def test_studio_remediation_plan_api(self, client):
        fixture = str(GOLDEN_DIR / "test_bidirectional")
        resp = client.post("/api/remediation/plan", json={"project_path": fixture})
        assert resp.status_code == 200
        data = resp.json()
        assert "plan" in data
        assert "validation" in data
        assert len(data["plan"]["patches"]) == 1
        assert data["validation"]["accepted"] is True

    def test_studio_remediation_apply_and_history_lifecycle(self, client, tmp_path):
        import shutil
        model_dir = tmp_path / "test_remediation_studio"
        shutil.copytree(GOLDEN_DIR / "test_bidirectional", model_dir)

        # 1. Plan
        plan_resp = client.post("/api/remediation/plan", json={"project_path": str(model_dir)})
        assert plan_resp.status_code == 200
        patch_id = plan_resp.json()["plan"]["patches"][0]["patch_id"]

        # 2. Apply
        apply_resp = client.post("/api/remediation/apply", json={
            "project_path": str(model_dir),
            "patch_ids": [patch_id],
            "backup": True,
        })
        assert apply_resp.status_code == 200
        apply_data = apply_resp.json()
        assert apply_data["success"] is True
        manifest_id = apply_data["manifest"]["manifest_id"]

        # 3. History
        hist_resp = client.get(f"/api/remediation/history?project_path={model_dir}")
        assert hist_resp.status_code == 200
        history = hist_resp.json()["history"]
        assert len(history) >= 1
        assert history[0]["manifest_id"] == manifest_id

        # 4. Manifest Detail
        man_resp = client.get(f"/api/remediation/manifest/{manifest_id}?project_path={model_dir}")
        assert man_resp.status_code == 200
        assert man_resp.json()["manifest_id"] == manifest_id
        assert man_resp.json()["decision"] == "ACCEPTED"


class TestAgentMcpIntegrationApi:
    """Studio UI's informational 'Agent / MCP' tab endpoints. Must never require
    the optional `mcp` extra to respond — only /api/mcp/tools's live-introspection
    path uses it, with a static fallback otherwise."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_mcp_status_reports_environment(self, client):
        resp = client.get("/api/mcp/status")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["mcp_installed"], bool)
        assert data["server_command"] == "pbiscan"
        assert data["server_args"] == ["mcp"]
        assert data["python_executable"]

    def test_mcp_status_never_exposes_groq_key_material(self, client, monkeypatch):
        """The status endpoint must report only a boolean groq_configured flag —
        never any substring of the real GROQ_API_KEY value, even partially."""
        real_key = "gsk_supersecretvaluethatmustneverleak1234567890"
        monkeypatch.setenv("GROQ_API_KEY", real_key)
        resp = client.get("/api/mcp/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["groq_configured"] is True
        assert "groq_masked_key" not in data
        body_text = resp.text
        assert real_key not in body_text
        assert real_key[:6] not in body_text
        assert real_key[-4:] not in body_text

    def test_mcp_tools_matches_real_server_classification(self, client):
        resp = client.get("/api/mcp/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tools"]) == 8

        tool_map = {t["name"]: t for t in data["tools"]}
        for name in ("scan_model", "diff_models", "get_measure_lineage", "plan_remediation", "list_suppressions", "suggest_dax_rewrite"):
            assert tool_map[name]["read_only"] is True
            assert tool_map[name]["destructive"] is False
        for name in ("apply_remediation", "add_suppression"):
            assert tool_map[name]["read_only"] is False
            assert tool_map[name]["destructive"] is True

    def test_mcp_config_snippets_endpoint_removed(self, client):
        """Multi-host (Claude/Cursor/VS Code) config-snippet material was removed
        by explicit user decision — pbiscan's Agent/MCP surface is Groq-only.
        The route falls through to the SPA catch-all rather than 404ing, so
        assert on content instead of status code."""
        resp = client.get("/api/mcp/config-snippets")
        assert resp.headers.get("content-type", "").startswith("text/html") or resp.status_code == 404
        assert b"claude_desktop" not in resp.content
        assert b"mcpServers" not in resp.content

    def test_mcp_rules_matches_static_catalog(self, client):
        resp = client.get("/api/mcp/rules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rules"] == 13
        assert "MODEL_BIDIRECTIONAL" in data["rules"]
        assert "DAX_UNUSED_MEASURE" in data["rules"]

    def test_mcp_tools_and_server_registry_never_disagree(self, client):
        """Regression guard for the exact drift class this whole feature exists
        to prevent: the Studio API's tool list must always match the real MCP
        server's actual registered + classified tool names."""
        from pbiscan.mcp.server import DESTRUCTIVE_TOOL_NAMES, READ_ONLY_TOOL_NAMES

        resp = client.get("/api/mcp/tools")
        api_names = {t["name"] for t in resp.json()["tools"]}
        assert api_names == set(READ_ONLY_TOOL_NAMES) | set(DESTRUCTIVE_TOOL_NAMES)
