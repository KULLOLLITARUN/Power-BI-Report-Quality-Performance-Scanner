"""Comprehensive unit test suite for PBIP Sentinel MCP Server."""
from __future__ import annotations

import json
from pathlib import Path
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

    def test_suggest_dax_rewrite_advisory(self):
        res = handle_suggest_dax_rewrite(
            rule_id="DAX_SUSPICIOUS_PATTERN",
            dax_expression="CALCULATE(SUM(Sales[Amount]), ALL(Sales))",
        )
        assert res["rule_id"] == "DAX_SUSPICIOUS_PATTERN"
        assert "advisory_note" in res
        assert "recommendation" in res


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
