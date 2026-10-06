"""Comprehensive unit test suite for PBIP Sentinel MCP Server."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock
from click.testing import CliRunner
import pytest

from pbiscan.cli import main
from pbiscan.mcp.prompts import (
    get_audit_model_prompt,
    get_inspect_dax_prompt,
    get_remediate_safely_prompt,
)
from pbiscan.mcp.resources import (
    get_rule_detail_json,
    get_rules_catalog_json,
)
from pbiscan.mcp.tools import (
    handle_add_suppression,
    handle_apply_remediation,
    handle_diff_models,
    handle_get_measure_lineage,
    handle_list_suppressions,
    handle_plan_remediation,
    handle_scan_model,
    handle_suggest_dax_rewrite,
)

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


class TestMcpResources:
    """Test static URI-addressable resource generation."""

    def test_rules_catalog_resource(self):
        catalog_raw = get_rules_catalog_json()
        data = json.loads(catalog_raw)
        assert "rules" in data
        assert data["total_rules"] == 13
        assert "MODEL_BIDIRECTIONAL" in data["rules"]
        assert "DAX_UNUSED_MEASURE" in data["rules"]
        assert "REPORT_VISUAL_BLOAT" in data["rules"]
        assert data["rules"]["MODEL_BIDIRECTIONAL"]["category"] == "model"

    def test_rule_detail_valid_rule(self):
        detail_raw = get_rule_detail_json("MODEL_BIDIRECTIONAL")
        data = json.loads(detail_raw)
        assert data["rule_id"] == "MODEL_BIDIRECTIONAL"
        assert data["category"] == "model"
        assert "title" in data and len(data["title"]) > 0
        assert "impact" in data and len(data["impact"]) > 0
        assert "recommendation" in data and len(data["recommendation"]) > 0

    def test_rule_detail_invalid_rule_returns_fallback_catalog(self):
        detail_raw = get_rule_detail_json("FAKE_RULE_XYZ")
        data = json.loads(detail_raw)
        assert "error" in data
        assert "available_rules" in data
        assert len(data["available_rules"]) == 13


class TestMcpPrompts:
    """Test pre-registered MCP prompt workflow templates."""

    def test_audit_model_prompt(self):
        prompt = get_audit_model_prompt("/path/to/model.pbip")
        assert "scan_model" in prompt
        assert "/path/to/model.pbip" in prompt

    def test_remediate_safely_prompt(self):
        prompt = get_remediate_safely_prompt("/path/to/model.pbip", rule_filter="MODEL_BIDIRECTIONAL")
        assert "plan_remediation" in prompt
        assert "apply_remediation" in prompt
        assert "MODEL_BIDIRECTIONAL" in prompt

    def test_inspect_dax_prompt(self):
        prompt = get_inspect_dax_prompt("/path/to/model.pbip", measure_name="TotalSales")
        assert "get_measure_lineage" in prompt
        assert "TotalSales" in prompt


class TestMcpTools:
    """Test typed tool handlers for scan, diff, lineage, and safe remediation."""

    def test_scan_model_tool(self):
        model_path = str(GOLDEN_DIR / "test_bidirectional")
        res = handle_scan_model(model_path)
        assert "report_name" in res
        assert "scores" in res
        assert "findings" in res
        assert len(res["findings"]) > 0

    def test_scan_model_tool_missing_path(self):
        res = handle_scan_model("nonexistent_path_404")
        assert "error" in res
        assert res["status"] == "ERROR"

    def test_diff_models_tool(self):
        base_path = str(GOLDEN_DIR / "test_bidirectional")
        curr_path = str(GOLDEN_DIR / "test_unusedmeasure")
        res = handle_diff_models(base_path, curr_path)
        assert "score_drift" in res
        assert "quality_gate" in res
        assert "baseline_name" in res and "current_name" in res

    def test_diff_models_tool_missing_path(self):
        res = handle_diff_models("nonexistent_base", str(GOLDEN_DIR / "test_bidirectional"))
        assert "error" in res
        assert res["status"] == "ERROR"

    def test_get_measure_lineage_tool(self):
        model_path = str(GOLDEN_DIR / "test_measure_referenced_by_another")
        res = handle_get_measure_lineage(model_path, "Revenue Per Unit")
        assert res["measure_name"] == "Revenue Per Unit"
        assert res["table"] == "Sales"
        assert res["is_reachable_from_visual"] is True
        assert "Base Revenue" in res["outbound_references"]

    def test_get_measure_lineage_missing_measure(self):
        model_path = str(GOLDEN_DIR / "test_measure_referenced_by_another")
        res = handle_get_measure_lineage(model_path, "NonExistentMeasure")
        assert "error" in res
        assert "available_measures" in res

    def test_plan_remediation_tool(self):
        model_path = str(GOLDEN_DIR / "test_bidirectional")
        res = handle_plan_remediation(model_path)
        assert "plan" in res
        assert "validation" in res
        assert res["total_proposals"] == 1
        assert res["before_score"] < res["after_score"]
        assert res["score_gain"] > 0

    def test_plan_remediation_tool_missing_path(self):
        res = handle_plan_remediation("nonexistent_path_404")
        assert "error" in res
        assert res["status"] == "ERROR"

    def test_apply_remediation_non_matching_patch_ids(self):
        model_path = str(GOLDEN_DIR / "test_bidirectional")
        res = handle_apply_remediation(model_path, patch_ids=["NON_EXISTENT_PATCH_ID"])
        assert res["status"] == "NO_OP"

    def test_apply_remediation_missing_path(self):
        res = handle_apply_remediation("nonexistent_path_404", patch_ids=["REM-001"])
        assert "error" in res
        assert res["status"] == "ERROR"

    def test_add_and_list_suppressions_tools(self, tmp_path: Path):
        proj_dir = tmp_path / "my_project"
        proj_dir.mkdir()

        # Add first suppression
        res_add1 = handle_add_suppression(
            str(proj_dir),
            rule_id="MODEL_BIDIRECTIONAL",
            location="Sales[ID] <-> Targets[ID]",
            reason="Approved design exception",
        )
        assert res_add1["status"] == "SUCCESS"
        assert res_add1["total_suppressions"] == 1

        # Add second suppression
        res_add2 = handle_add_suppression(
            str(proj_dir),
            rule_id="DAX_UNUSED_MEASURE",
            location="Measure: DeprecatedCalc",
            reason="Legacy migration",
        )
        assert res_add2["status"] == "SUCCESS"
        assert res_add2["total_suppressions"] == 2

        # List suppressions
        res_list = handle_list_suppressions(str(proj_dir))
        assert res_list["total_suppressions"] == 2
        assert res_list["suppressions"][0]["rule_id"] == "MODEL_BIDIRECTIONAL"
        assert res_list["suppressions"][1]["rule_id"] == "DAX_UNUSED_MEASURE"

    def test_suggest_dax_rewrite_advisory(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        res = handle_suggest_dax_rewrite(
            rule_id="DAX_SUSPICIOUS_PATTERN",
            dax_expression="CALCULATE(SUM(Sales[Amount]), ALL(Sales))",
        )
        assert res["rule_id"] == "DAX_SUSPICIOUS_PATTERN"
        assert "advisory_note" in res
        assert "recommendation" in res
        assert res["ai_generated"] is False
        assert "suggested_rewrite" not in res


class TestSuggestDaxRewriteGroqIntegration:
    """suggest_dax_rewrite must be BYO-key and never fail hard: no key means
    the static fallback, a Groq failure means the static fallback, and a
    successful call means a real, parsed AI suggestion layered on top.

    tests/conftest.py sets PBISCAN_DISABLE_DOTENV=1 for the whole session, so
    these tests are never influenced by whatever real .env file happens to
    exist in the developer's working directory — GROQ_API_KEY is controlled
    purely via monkeypatch here.
    """

    def test_no_api_key_never_attempts_network_call(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        from pbiscan.mcp.groq_client import is_groq_configured
        assert is_groq_configured() is False

        res = handle_suggest_dax_rewrite("DAX_SUSPICIOUS_PATTERN", "SUM(Sales[Amount])")
        assert res["ai_generated"] is False

    def test_successful_groq_reply_is_parsed_into_rewrite_and_explanation(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        fake_reply = (
            "DIVIDE(SUM(Sales[Amount]), SUM(Sales[Units]), 0)\n\n"
            "DIVIDE avoids a divide-by-zero error and is the idiomatic safe-division pattern in DAX."
        )
        with mock.patch("pbiscan.mcp.tools.call_groq_chat", return_value=fake_reply):
            res = handle_suggest_dax_rewrite(
                rule_id="DAX_SUSPICIOUS_PATTERN",
                dax_expression="SUM(Sales[Amount]) / SUM(Sales[Units])",
            )
        assert res["ai_generated"] is True
        assert res["suggested_rewrite"] == "DIVIDE(SUM(Sales[Amount]), SUM(Sales[Units]), 0)"
        assert "DIVIDE avoids" in res["rewrite_explanation"]
        assert res["ai_model"]

    def test_multiline_rewrite_with_blank_lines_is_kept_whole(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        rewrite = (
            "VAR Units = SUM(Sales[Units])\n\n"
            "VAR Amount = SUM(Sales[Amount])\n\n"
            "RETURN DIVIDE(Amount, Units, 0)"
        )
        fake_reply = f"{rewrite}\n###EXPLANATION###\nVariables evaluate once and DIVIDE is safe."
        with mock.patch("pbiscan.mcp.tools.call_groq_chat", return_value=fake_reply):
            res = handle_suggest_dax_rewrite("DAX_SUSPICIOUS_PATTERN", "SUM(Sales[Amount]) / SUM(Sales[Units])")
        assert res["suggested_rewrite"] == rewrite
        assert res["rewrite_explanation"] == "Variables evaluate once and DIVIDE is safe."

    def test_code_fenced_rewrite_is_unwrapped(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        fake_reply = "```dax\nDIVIDE([A], [B])\n```\n###EXPLANATION###\nSafe division."
        with mock.patch("pbiscan.mcp.tools.call_groq_chat", return_value=fake_reply):
            res = handle_suggest_dax_rewrite("DAX_SUSPICIOUS_PATTERN", "[A] / [B]")
        assert res["suggested_rewrite"] == "DIVIDE([A], [B])"
        assert res["rewrite_explanation"] == "Safe division."

    def test_groq_failure_falls_back_to_static_recommendation(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        with mock.patch("pbiscan.mcp.tools.call_groq_chat", return_value=None):
            res = handle_suggest_dax_rewrite("DAX_SUSPICIOUS_PATTERN", "SUM(Sales[Amount])")
        assert res["ai_generated"] is False
        assert "recommendation" in res

    def test_groq_client_returns_none_without_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        from pbiscan.mcp.groq_client import call_groq_chat
        assert call_groq_chat("system", "user") is None

    def test_groq_client_handles_http_error_gracefully(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        import urllib.error
        from pbiscan.mcp.groq_client import call_groq_chat

        def _raise(*args, **kwargs):
            raise urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)

        with mock.patch("urllib.request.urlopen", side_effect=_raise):
            assert call_groq_chat("system", "user") is None

    def test_groq_client_handles_malformed_response_gracefully(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        from pbiscan.mcp.groq_client import call_groq_chat

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b'{"unexpected": "shape"}'

        with mock.patch("urllib.request.urlopen", return_value=_FakeResponse()):
            assert call_groq_chat("system", "user") is None


class TestDotenvLoader:
    """Regression coverage for the exact bug this class of test caught during
    development: a real .env file at the repo root (left by a developer for
    manual local testing) must never leak into or affect test behavior."""

    def test_disabled_by_env_var_skips_file_entirely(self, monkeypatch, tmp_path):
        import pbiscan.mcp.groq_client as groq_client_mod

        (tmp_path / ".env").write_text("GROQ_API_KEY=should-never-be-loaded\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PBISCAN_DISABLE_DOTENV", "1")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setattr(groq_client_mod, "_dotenv_loaded", False)

        groq_client_mod.load_dotenv_if_present()
        assert "GROQ_API_KEY" not in os.environ

    def test_loads_unset_vars_from_env_file(self, monkeypatch, tmp_path):
        import pbiscan.mcp.groq_client as groq_client_mod

        (tmp_path / ".env").write_text('GROQ_API_KEY="from-dotenv-file"\n# a comment\n\nGROQ_MODEL=some-model\n', encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PBISCAN_DISABLE_DOTENV", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_MODEL", raising=False)
        monkeypatch.setattr(groq_client_mod, "_dotenv_loaded", False)

        # load_dotenv writes os.environ directly; patch.dict restores it so the
        # loaded values don't leak into later tests
        with mock.patch.dict(os.environ):
            groq_client_mod.load_dotenv_if_present()
            assert os.environ["GROQ_API_KEY"] == "from-dotenv-file"
            assert os.environ["GROQ_MODEL"] == "some-model"

    def test_real_environment_variable_always_wins_over_dotenv_file(self, monkeypatch, tmp_path):
        import pbiscan.mcp.groq_client as groq_client_mod

        (tmp_path / ".env").write_text("GROQ_API_KEY=from-dotenv-file\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PBISCAN_DISABLE_DOTENV", raising=False)
        monkeypatch.setenv("GROQ_API_KEY", "from-real-environment")
        monkeypatch.setattr(groq_client_mod, "_dotenv_loaded", False)

        groq_client_mod.load_dotenv_if_present()
        assert os.environ["GROQ_API_KEY"] == "from-real-environment"


class TestMcpCliAndServerFactory:
    """Test MCP CLI subcommand and server factory lifecycle."""

    def test_create_server_factory(self):
        from pbiscan.mcp.server import MCP_AVAILABLE, create_server
        if MCP_AVAILABLE:
            server = create_server()
            assert server is not None
            assert server.name == "PBIP Sentinel"
        else:
            with pytest.raises(ImportError, match="Install it via: pip install 'pbiscan\\[mcp\\]'"):
                create_server()

    def test_cli_mcp_command_help(self):
        runner = CliRunner()
        res = runner.invoke(main, ["mcp", "--help"])
        assert res.exit_code == 0
        assert "Start the PBIP Sentinel Model Context Protocol (MCP) server" in res.output

    def test_tool_annotations_protocol_guarantees(self):
        import asyncio
        from pbiscan.mcp.server import MCP_AVAILABLE, create_server

        if not MCP_AVAILABLE:
            pytest.skip("mcp package is not installed")

        server = create_server()

        async def _check_tools():
            tools = await server.list_tools()
            tool_map = {t.name: t for t in tools}

            # Expected read-only tools
            read_only_tools = [
                "scan_model",
                "diff_models",
                "get_measure_lineage",
                "plan_remediation",
                "list_suppressions",
                "suggest_dax_rewrite",
            ]
            for name in read_only_tools:
                assert name in tool_map, f"Missing tool {name}"
                assert tool_map[name].annotations is not None, f"Tool {name} has None annotations"
                assert tool_map[name].annotations.readOnlyHint is True
                assert tool_map[name].annotations.destructiveHint is False

            # Expected destructive tools (host approval gate triggers)
            destructive_tools = [
                "apply_remediation",
                "add_suppression",
            ]
            for name in destructive_tools:
                assert name in tool_map, f"Missing tool {name}"
                assert tool_map[name].annotations is not None, f"Tool {name} has None annotations"
                assert tool_map[name].annotations.readOnlyHint is False
                assert tool_map[name].annotations.destructiveHint is True

        asyncio.run(_check_tools())



class TestMcpToolHandlerErrorPaths:
    """Error branches of the tool handlers an agent can hit with bad input."""

    def test_diff_models_missing_current_path(self):
        res = handle_diff_models(str(GOLDEN_DIR / "test_bidirectional"), "nonexistent_path_404")
        assert res["status"] == "ERROR"
        assert "Current path does not exist" in res["error"]

    def test_get_measure_lineage_missing_path(self):
        res = handle_get_measure_lineage("nonexistent_path_404", measure_name="Total Sales")
        assert res["status"] == "ERROR"

    def test_list_suppressions_missing_path(self):
        res = handle_list_suppressions("nonexistent_path_404")
        assert res["status"] == "ERROR"

    def test_add_suppression_missing_path(self):
        res = handle_add_suppression("nonexistent_path_404", rule_id="MODEL_BIDIRECTIONAL", location="x")
        assert res["status"] == "ERROR"

    def test_add_suppression_refuses_to_overwrite_corrupt_file(self, tmp_path: Path):
        supp_file = tmp_path / "pbiscan.suppressions.json"
        supp_file.write_text("{ not valid json", encoding="utf-8")

        res = handle_add_suppression(str(tmp_path), rule_id="MODEL_BIDIRECTIONAL", location="x")

        assert res["status"] == "ERROR"
        assert supp_file.read_text(encoding="utf-8") == "{ not valid json"

    def test_apply_remediation_rejected_by_sandbox_writes_nothing(self, tmp_path: Path):
        import shutil
        from pbiscan.remediation.engine import RemediationEngine
        from pbiscan.remediation.models import compute_file_sha256

        model_dir = tmp_path / "model"
        shutil.copytree(GOLDEN_DIR / "test_bidirectional", model_dir)
        before = {p: compute_file_sha256(p) for p in model_dir.rglob("*") if p.is_file()}

        rejected = mock.Mock(accepted=False, rejection_reasons=["sandbox rescan regressed"])
        with mock.patch.object(RemediationEngine, "validate", return_value=rejected):
            res = handle_apply_remediation(str(model_dir), patch_ids=[])

        assert res["status"] == "REJECTED"
        assert res["rejection_reasons"] == ["sandbox rescan regressed"]
        assert {p: compute_file_sha256(p) for p in model_dir.rglob("*") if p.is_file()} == before

    def test_apply_remediation_applies_patch_and_reports_backup(self, tmp_path: Path):
        import shutil

        model_dir = tmp_path / "model"
        shutil.copytree(GOLDEN_DIR / "test_bidirectional", model_dir)

        res = handle_apply_remediation(str(model_dir), patch_ids=[])

        assert res["status"] == "APPLIED"
        assert res["applied_count"] == 1
        assert res["after_score"] >= res["before_score"]
        assert Path(res["backup_location"]).exists()
        findings = handle_scan_model(str(model_dir))["findings"]
        assert not [f for f in findings if f["rule_id"] == "MODEL_BIDIRECTIONAL"]


class TestMcpServerWiring:
    """Call every registered tool, resource and prompt through FastMCP itself, so
    a wrong argument name or a mis-wired handler fails here, not in an agent."""

    @pytest.fixture
    def server(self):
        from pbiscan.mcp.server import MCP_AVAILABLE, create_server
        if not MCP_AVAILABLE:
            pytest.skip("mcp package is not installed")
        return create_server()

    @staticmethod
    def _call(server, name: str, args: dict) -> dict:
        import asyncio
        result = asyncio.run(server.call_tool(name, args))
        # FastMCP returns (content_blocks, structured_result) for dict-returning tools.
        if isinstance(result, tuple):
            return result[1].get("result", result[1])
        return json.loads(result[0].text)

    def test_read_only_tools(self, server, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        fixture = str(GOLDEN_DIR / "test_bidirectional")

        assert "findings" in self._call(server, "scan_model", {"path": fixture})
        diff = self._call(server, "diff_models", {"baseline_path": fixture, "current_path": fixture})
        assert diff["score_drift"]["baseline_score"] == diff["score_drift"]["current_score"]
        lineage = self._call(server, "get_measure_lineage", {
            "path": str(GOLDEN_DIR / "test_measure_referenced_by_another"), "measure_name": "Revenue Per Unit",
        })
        assert "Base Revenue" in lineage["outbound_references"]
        assert self._call(server, "plan_remediation", {"path": fixture})["total_proposals"] == 1
        assert self._call(server, "list_suppressions", {"path": fixture})["total_suppressions"] == 0
        assert self._call(server, "suggest_dax_rewrite", {
            "rule_id": "DAX_SUSPICIOUS_PATTERN", "dax_expression": "SUM(Sales[Amount])",
        })["ai_generated"] is False

    def test_destructive_tools(self, server, tmp_path: Path):
        proj = tmp_path / "proj"
        proj.mkdir()
        res = self._call(server, "add_suppression",
                         {"path": str(proj), "rule_id": "MODEL_BIDIRECTIONAL", "location": "A <-> B"})
        assert res["status"] == "SUCCESS"
        saved = json.loads((proj / "pbiscan.suppressions.json").read_text(encoding="utf-8"))
        assert "MCP Agent" in json.dumps(saved)

        res = self._call(server, "apply_remediation", {"path": str(proj), "patch_ids": ["REM-NONE"]})
        assert res["status"] in ("NO_OP", "ERROR")

    def test_resources_and_prompts(self, server):
        import asyncio

        async def _check():
            catalog = list(await server.read_resource("pbiscan://rules"))
            assert "MODEL_BIDIRECTIONAL" in catalog[0].content
            detail = list(await server.read_resource("pbiscan://rules/MODEL_BIDIRECTIONAL"))
            assert json.loads(detail[0].content)["rule_id"] == "MODEL_BIDIRECTIONAL"
            for name, args in [
                ("audit-model", {"path": "C:/proj"}),
                ("remediate-safely", {"path": "C:/proj"}),
                ("inspect-dax-measure", {"path": "C:/proj", "measure_name": "Total Sales"}),
            ]:
                prompt = await server.get_prompt(name, args)
                assert "C:/proj" in prompt.messages[0].content.text

        asyncio.run(_check())
