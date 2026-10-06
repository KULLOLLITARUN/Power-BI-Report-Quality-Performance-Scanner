"""Errors must be reported, never silently swallowed into a different outcome.

Covers the failure modes that previously changed behavior without telling anyone:
- a missing or invalid config file silently replaced by another config / defaults
- a malformed suppressions file silently ignored, or overwritten (deleting entries)
- Studio 500 responses leaking raw exception text to the client
- a corrupt remediation history.json silently overwritten (losing the audit trail)
- manifest IDs used as filesystem paths without validation
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from pbiscan.cli import main
from pbiscan.engine.scoring import ConfigError
from pbiscan.engine.suppressions import load_suppressions
from pbiscan.mcp.tools import handle_add_suppression
from pbiscan.remediation.store import RemediationAuditStore
from pbiscan.server import STUDIO_TOKEN, TOKEN_HEADER, app
from pbiscan.service import ScanService, resolve_config

TOKEN_HEADERS = {TOKEN_HEADER: STUDIO_TOKEN}

GOLDEN_DIR = Path(__file__).parent.parent / "golden"
FIXTURE = GOLDEN_DIR / "test_unusedmeasure"
CORRUPT = "{ this is not json"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    dest = tmp_path / "project"
    shutil.copytree(FIXTURE, dest)
    return dest


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, base_url="http://127.0.0.1", headers=TOKEN_HEADERS)


class TestConfigErrors:

    def test_missing_explicit_config_raises(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            resolve_config(config_path=tmp_path / "typo.config.json")

    def test_invalid_project_config_raises_instead_of_falling_through(self, project):
        (project / ".pbiscan.config.json").write_text(CORRUPT, encoding="utf-8")
        with pytest.raises(ConfigError):
            resolve_config(project_path=project)

    def test_incomplete_project_config_raises(self, project):
        (project / ".pbiscan.config.json").write_text(json.dumps({"thresholds": {}}), encoding="utf-8")
        with pytest.raises(ConfigError, match="weights"):
            resolve_config(project_path=project)

    def test_cli_scan_with_missing_config_exits_with_config_error(self, project, tmp_path):
        result = CliRunner().invoke(main, ["scan", str(project), "--config", str(tmp_path / "typo.json")])
        assert result.exit_code == 1
        assert "Config error" in result.output

    def test_studio_scan_with_missing_config_returns_422(self, client, project, tmp_path):
        resp = client.post("/api/scan", json={"path": str(project), "config_path": str(tmp_path / "typo.json")})
        assert resp.status_code == 422
        assert "CONFIG_ERROR" in resp.json()["detail"]


class TestSuppressionFileErrors:

    @pytest.mark.parametrize("content", [CORRUPT, "[1, 2, 3]", '{"suppressions": "nope"}'])
    def test_malformed_file_is_reported(self, project, content, caplog):
        (project / "pbiscan.suppressions.json").write_text(content, encoding="utf-8")
        warnings: list[str] = []
        with caplog.at_level(logging.WARNING, logger="pbiscan.engine.suppressions"):
            assert load_suppressions(project, warnings=warnings) == []
        assert len(warnings) == 1 and "Ignoring suppressions" in warnings[0]
        assert "Ignoring suppressions" in caplog.text

    def test_scan_result_surfaces_suppression_warning(self, project):
        (project / "pbiscan.suppressions.json").write_text(CORRUPT, encoding="utf-8")
        result = ScanService.execute_scan(project)
        assert any("Ignoring suppressions" in w for w in result.warnings)

    def test_studio_refuses_to_overwrite_corrupt_file(self, client, project):
        supp = project / "pbiscan.suppressions.json"
        supp.write_text(CORRUPT, encoding="utf-8")
        resp = client.post("/api/suppress", json={
            "project_path": str(project), "rule_id": "DAX_UNUSED_MEASURE", "location": "Measure: X",
        })
        assert resp.status_code == 409
        assert supp.read_text(encoding="utf-8") == CORRUPT

    def test_mcp_refuses_to_overwrite_corrupt_file(self, project):
        supp = project / "pbiscan.suppressions.json"
        supp.write_text(CORRUPT, encoding="utf-8")
        res = handle_add_suppression(str(project), "DAX_UNUSED_MEASURE", "Measure: X")
        assert res["status"] == "ERROR"
        assert supp.read_text(encoding="utf-8") == CORRUPT

    def test_valid_file_is_appended_not_replaced(self, client, project):
        supp = project / "pbiscan.suppressions.json"
        supp.write_text(json.dumps({"suppressions": [{"rule_id": "A", "location": "x", "reason": "keep"}]}), encoding="utf-8")
        resp = client.post("/api/suppress", json={
            "project_path": str(project), "rule_id": "B", "location": "y",
        })
        assert resp.status_code == 200
        rules = json.loads(supp.read_text(encoding="utf-8"))["suppressions"]
        assert [r["rule_id"] for r in rules] == ["A", "B"]


class TestStudioInternalErrors:

    def test_500_does_not_leak_exception_text_and_logs_it(self, client, project, caplog):
        boom = RuntimeError("C:\\secret\\internal\\path detail")
        with mock.patch("pbiscan.server.ScanService.execute_scan", side_effect=boom), \
                caplog.at_level(logging.ERROR, logger="pbiscan.server"):
            resp = client.post("/api/scan", json={"path": str(project)})
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "secret" not in detail
        assert "RuntimeError" in detail
        assert "secret" in caplog.text


class TestRemediationStoreErrors:

    def test_corrupt_history_is_preserved_not_overwritten(self, tmp_path):
        from pbiscan.remediation.models import RemediationManifest

        store = RemediationAuditStore.ensure_store_dir(tmp_path)
        (store / "history.json").write_text(CORRUPT, encoding="utf-8")

        manifest = RemediationManifest(model_name="m", model_path=str(tmp_path), decision="REJECTED")
        RemediationAuditStore.save_manifest(manifest, tmp_path)

        preserved = list(store.glob("history.corrupt-*.json"))
        assert len(preserved) == 1
        assert preserved[0].read_text(encoding="utf-8") == CORRUPT
        history = json.loads((store / "history.json").read_text(encoding="utf-8"))
        assert [e["manifest_id"] for e in history] == [manifest.manifest_id]

    def test_corrupt_history_lists_as_empty_with_warning(self, tmp_path, caplog):
        store = RemediationAuditStore.ensure_store_dir(tmp_path)
        (store / "history.json").write_text(CORRUPT, encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="pbiscan.remediation.store"):
            assert RemediationAuditStore.list_manifests(tmp_path) == []
        assert "Unreadable remediation history" in caplog.text

    @pytest.mark.parametrize("manifest_id", ["../../secrets", "..\\..\\secrets", "a/b", ""])
    def test_manifest_id_with_path_characters_is_rejected(self, tmp_path, manifest_id):
        store = RemediationAuditStore.ensure_store_dir(tmp_path)
        (store.parent.parent / "manifest_..").mkdir(exist_ok=True)
        assert RemediationAuditStore.get_manifest(manifest_id, tmp_path) is None

    def test_studio_manifest_endpoint_rejects_traversal_id(self, client, project):
        RemediationAuditStore.ensure_store_dir(project)
        # Backslashes stay inside the {manifest_id} path segment (a "/" would not match the route)
        resp = client.get("/api/remediation/manifest/..%5C..%5Csecrets", params={"project_path": str(project)})
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]
