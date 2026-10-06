"""Shared code paths that replaced per-caller copies.

- add_suppression(): the single writer behind Studio /api/suppress and the MCP
  add_suppression tool, with atomic writes.
- ScanResult.to_audit_dict(): the single serialization behind to_json(),
  to_dict() and the JSON artifacts DiffService reads back.
- Studio request helpers: consistent 404 / 409 / 422 / 500 mapping.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from pbiscan.diff import DiffService
from pbiscan.engine.issue import RuleFinding
from pbiscan.engine.suppressions import (
    SUPPRESSIONS_FILENAME,
    SuppressionFileError,
    add_suppression,
    load_suppressions,
)
from pbiscan.mcp.tools import handle_add_suppression, handle_get_measure_lineage
from pbiscan.server import app
from pbiscan.service import ScanService

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    dest = tmp_path / "project"
    shutil.copytree(GOLDEN_DIR / "test_suppression_scoring", dest)
    return dest


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, base_url="http://127.0.0.1")


class TestAddSuppression:

    def test_creates_file_next_to_pbip(self, tmp_path):
        pbip = tmp_path / "Sales.pbip"
        pbip.write_text("{}", encoding="utf-8")
        supp_file, total = add_suppression(pbip, " dax_unused_measure ", " Measure: X ", " legacy ")
        assert supp_file == tmp_path / SUPPRESSIONS_FILENAME
        assert total == 1
        entry = json.loads(supp_file.read_text(encoding="utf-8"))["suppressions"][0]
        assert entry["rule_id"] == "DAX_UNUSED_MEASURE"
        assert entry["location"] == "Measure: X"
        assert entry["reason"] == "legacy"
        assert "added_at" in entry and "added_by" not in entry

    def test_appends_and_preserves_other_keys(self, project):
        supp = project / SUPPRESSIONS_FILENAME
        data = json.loads(supp.read_text(encoding="utf-8"))
        data["_comment"] = "team-owned"
        supp.write_text(json.dumps(data), encoding="utf-8")

        _, total = add_suppression(project, "DAX_UNUSED_MEASURE", "Measure: X", "r", added_by="me")
        saved = json.loads(supp.read_text(encoding="utf-8"))
        assert total == 2
        assert saved["_comment"] == "team-owned"
        assert [s["rule_id"] for s in saved["suppressions"]] == ["MODEL_BIDIRECTIONAL", "DAX_UNUSED_MEASURE"]
        assert saved["suppressions"][1]["added_by"] == "me"

    def test_written_entry_is_loadable(self, tmp_path):
        add_suppression(tmp_path, "MODEL_BIDIRECTIONAL", "A[x] <-> B[x]", "ok")
        rules = load_suppressions(tmp_path)
        assert len(rules) == 1 and rules[0].matches("MODEL_BIDIRECTIONAL", "A[x] ↔ B[x]")

    @pytest.mark.parametrize("content", ["{ broken", "[]", '{"suppressions": {}}'])
    def test_refuses_malformed_file(self, tmp_path, content):
        supp = tmp_path / SUPPRESSIONS_FILENAME
        supp.write_text(content, encoding="utf-8")
        with pytest.raises(SuppressionFileError):
            add_suppression(tmp_path, "R", "x", "y")
        assert supp.read_text(encoding="utf-8") == content

    def test_failed_write_leaves_original_and_no_temp_file(self, project):
        supp = project / SUPPRESSIONS_FILENAME
        original = supp.read_text(encoding="utf-8")
        with mock.patch("pbiscan.fileio.os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                add_suppression(project, "R", "x", "y")
        assert supp.read_text(encoding="utf-8") == original
        assert [p.name for p in project.iterdir() if p.suffix == ".tmp"] == []

    def test_studio_and_mcp_write_the_same_shape(self, tmp_path, client):
        studio_dir, mcp_dir = tmp_path / "studio", tmp_path / "mcp"
        studio_dir.mkdir()
        mcp_dir.mkdir()
        resp = client.post("/api/suppress", json={
            "project_path": str(studio_dir), "rule_id": "dax_unused_measure", "location": "Measure: X", "reason": "r",
        })
        assert resp.status_code == 200
        assert handle_add_suppression(str(mcp_dir), "dax_unused_measure", "Measure: X", "r")["status"] == "SUCCESS"

        def entry(d: Path) -> dict:
            return json.loads((d / SUPPRESSIONS_FILENAME).read_text(encoding="utf-8"))["suppressions"][0]

        studio, mcp = entry(studio_dir), entry(mcp_dir)
        assert studio.keys() == mcp.keys()
        assert studio["rule_id"] == mcp["rule_id"] == "DAX_UNUSED_MEASURE"
        assert studio["added_by"] == "pbiscan Studio"
        assert mcp["added_by"] == "MCP Agent"


class TestScanSerialization:

    def test_to_json_is_the_audit_dict(self, project):
        result = ScanService.execute_scan(project)
        assert json.loads(result.to_json()) == result.to_audit_dict()

    def test_to_dict_extends_the_audit_dict(self, project):
        result = ScanService.execute_scan(project)
        full = result.to_dict()
        for key, value in result.to_audit_dict().items():
            assert full[key] == value
        assert full["findings"] == [i.to_dict() for i in result.issues]

    def test_json_export_round_trips_through_diff_loader(self, project, tmp_path):
        result = ScanService.execute_scan(project)
        assert any(i.suppressed for i in result.issues)
        artifact = tmp_path / "baseline.json"
        artifact.write_text(result.to_json(), encoding="utf-8")

        loaded = DiffService._resolve_scan(artifact)
        assert [i.to_dict() for i in loaded.issues] == [i.to_dict() for i in result.issues]
        assert loaded.scores == result.scores
        assert loaded.warnings == result.warnings

    def test_lineage_references_match_scan_serialization(self):
        path = GOLDEN_DIR / "test_measure_referenced_by_another"
        result = ScanService.execute_scan(path)
        measure = result.report.dax.measures[0].name
        lineage = handle_get_measure_lineage(str(path), measure)
        scan_refs = [r for r in result.to_dict()["semantic_references"]["references"]
                     if r["target_name"].lower() == measure.lower()]
        assert lineage["semantic_references"] == scan_refs

    def test_report_name_comes_from_pbip_file(self, project):
        assert ScanService.execute_scan(project).report_name == "fixture"

    def test_security_is_not_a_rule_category(self):
        with pytest.raises(ValueError, match="category"):
            RuleFinding(rule_id="X", category="security", severity="HIGH", confidence=90, evidence="e")


class TestStudioErrorMapping:

    @pytest.mark.parametrize("endpoint,body", [
        ("/api/scan", {"path": "no/such/path"}),
        ("/api/export", {"project_path": "no/such/path", "format": "json"}),
        ("/api/suppress", {"project_path": "no/such/path", "rule_id": "R", "location": "x"}),
        ("/api/remediation/plan", {"project_path": "no/such/path"}),
        ("/api/diff", {"baseline_path": "no/such/path", "current_path": "."}),
    ])
    def test_missing_path_is_404_naming_the_path(self, client, endpoint, body):
        resp = client.post(endpoint, json=body)
        assert resp.status_code == 404
        assert "no/such/path" in resp.json()["detail"]

    def test_corrupt_suppressions_file_is_409(self, client, project):
        (project / SUPPRESSIONS_FILENAME).write_text("{ broken", encoding="utf-8")
        resp = client.post("/api/suppress", json={"project_path": str(project), "rule_id": "R", "location": "x"})
        assert resp.status_code == 409

    @pytest.mark.parametrize("endpoint,body,target", [
        ("/api/export", {"format": "json"}, "pbiscan.server.ScanService.execute_scan"),
        ("/api/diff", {}, "pbiscan.server.DiffService.compare"),
        ("/api/remediation/plan", {}, "pbiscan.remediation.engine.RemediationEngine.analyze"),
    ])
    def test_unexpected_error_is_500_without_details(self, client, project, endpoint, body, target):
        paths = (
            {"baseline_path": str(project), "current_path": str(project)}
            if endpoint == "/api/diff" else {"project_path": str(project)}
        )
        with mock.patch(target, side_effect=RuntimeError("C:\\secret")):
            resp = client.post(endpoint, json={**body, **paths})
        assert resp.status_code == 500
        assert "secret" not in resp.json()["detail"]
        assert "RuntimeError" in resp.json()["detail"]
