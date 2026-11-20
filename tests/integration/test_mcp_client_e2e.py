"""End-to-End integration test suite for PBIP Sentinel MCP Server.

Spawns the MCP server as a real external subprocess over stdio and drives it with
mcp.client.session.ClientSession, verifying real-world JSON-RPC protocol transport,
tool discovery, safety annotations, static resources, prompts, and tool executions.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
import pytest

# Starts a real MCP server process: left out of the quick tier (`-m "not slow"`).
pytestmark = pytest.mark.slow

from pbiscan.mcp.server import MCP_AVAILABLE

if not MCP_AVAILABLE:
    pytest.skip("mcp package not installed", allow_module_level=True)

from mcp import ClientSession, StdioServerParameters  # type: ignore[import-not-found]
from mcp.client.stdio import stdio_client  # type: ignore[import-not-found]

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


@pytest.fixture
def mcp_server_params() -> StdioServerParameters:
    """Configure subprocess launch parameters for PBIP Sentinel MCP Server."""
    env = os.environ.copy()
    # Ensure current workspace is on PYTHONPATH
    repo_root = str(Path(__file__).parent.parent.parent)
    env["PYTHONPATH"] = f"{repo_root}{os.pathsep}{env.get('PYTHONPATH', '')}"

    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "pbiscan.cli", "mcp"],
        env=env,
    )


class TestMcpClientE2E:
    """End-to-end integration tests over real JSON-RPC stdio subprocess transport."""

    def test_e2e_mcp_lifecycle_and_protocol_annotations(
        self,
        mcp_server_params: StdioServerParameters,
    ):
        """Test server startup, initialization handshake, and tool discovery with safety hints."""

        async def _run():
            async with stdio_client(mcp_server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    init_result = await session.initialize()
                    assert init_result is not None

                    # 1. Verify Tools Discovery & Safety Hints
                    tools_res = await session.list_tools()
                    tools = tools_res.tools
                    tool_map = {t.name: t for t in tools}

                    assert len(tools) == 8

                    read_only_tools = [
                        "scan_model",
                        "diff_models",
                        "get_measure_lineage",
                        "plan_remediation",
                        "list_suppressions",
                        "suggest_dax_rewrite",
                    ]
                    for name in read_only_tools:
                        assert name in tool_map, f"Missing tool: {name}"
                        ann = tool_map[name].annotations
                        assert ann is not None, f"Tool {name} missing annotations"
                        assert ann.readOnlyHint is True, f"Tool {name} readOnlyHint must be True"
                        assert ann.destructiveHint is False, f"Tool {name} destructiveHint must be False"

                    destructive_tools = [
                        "apply_remediation",
                        "add_suppression",
                    ]
                    for name in destructive_tools:
                        assert name in tool_map, f"Missing tool: {name}"
                        ann = tool_map[name].annotations
                        assert ann is not None, f"Tool {name} missing annotations"
                        assert ann.readOnlyHint is False, f"Tool {name} readOnlyHint must be False"
                        assert ann.destructiveHint is True, f"Tool {name} destructiveHint must be True"

        asyncio.run(_run())

    def test_e2e_mcp_resources_and_prompts(
        self,
        mcp_server_params: StdioServerParameters,
    ):
        """Test URI-addressable static resources and prompt template workflows."""

        async def _run():
            async with stdio_client(mcp_server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    # 1. Read Rules Catalog Resource
                    catalog_res = await session.read_resource("pbiscan://rules")
                    assert len(catalog_res.contents) > 0
                    catalog_json = json.loads(catalog_res.contents[0].text)  # type: ignore[attr-defined]
                    assert catalog_json["total_rules"] == 14
                    assert "MODEL_BIDIRECTIONAL" in catalog_json["rules"]

                    # 2. Read Single Rule Detail Resource
                    rule_res = await session.read_resource("pbiscan://rules/MODEL_BIDIRECTIONAL")
                    assert len(rule_res.contents) > 0
                    rule_json = json.loads(rule_res.contents[0].text)  # type: ignore[attr-defined]
                    assert rule_json["rule_id"] == "MODEL_BIDIRECTIONAL"
                    assert "impact" in rule_json

                    # 3. Test Prompts
                    prompts_res = await session.list_prompts()
                    prompt_names = {p.name for p in prompts_res.prompts}
                    assert "audit-model" in prompt_names
                    assert "remediate-safely" in prompt_names
                    assert "inspect-dax-measure" in prompt_names

                    audit_prompt = await session.get_prompt(
                        "audit-model",
                        arguments={"path": "/workspace/Sales.pbip"},
                    )
                    assert len(audit_prompt.messages) > 0
                    assert "/workspace/Sales.pbip" in audit_prompt.messages[0].content.text  # type: ignore[attr-defined]

        asyncio.run(_run())

    def test_e2e_mcp_tool_execution_pipeline(
        self,
        mcp_server_params: StdioServerParameters,
        tmp_path: Path,
    ):
        """Test invoking real analysis, lineage, diffing, and sandbox planning over JSON-RPC."""

        async def _run():
            async with stdio_client(mcp_server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    # 1. Execute scan_model tool
                    scan_args = {"path": str(GOLDEN_DIR / "test_bidirectional")}
                    scan_call = await session.call_tool("scan_model", arguments=scan_args)
                    assert not scan_call.isError
                    scan_data = json.loads(scan_call.content[0].text)  # type: ignore[attr-defined]
                    assert "report_name" in scan_data
                    assert "scores" in scan_data
                    assert len(scan_data["findings"]) > 0

                    # 2. Execute diff_models tool
                    diff_args = {
                        "baseline_path": str(GOLDEN_DIR / "test_bidirectional"),
                        "current_path": str(GOLDEN_DIR / "test_unusedmeasure"),
                    }
                    diff_call = await session.call_tool("diff_models", arguments=diff_args)
                    assert not diff_call.isError
                    diff_data = json.loads(diff_call.content[0].text)  # type: ignore[attr-defined]
                    assert "score_drift" in diff_data
                    assert "quality_gate" in diff_data

                    # 3. Execute get_measure_lineage tool
                    lineage_args = {
                        "path": str(GOLDEN_DIR / "test_measure_referenced_by_another"),
                        "measure_name": "Revenue Per Unit",
                    }
                    lineage_call = await session.call_tool("get_measure_lineage", arguments=lineage_args)
                    assert not lineage_call.isError
                    lineage_data = json.loads(lineage_call.content[0].text)  # type: ignore[attr-defined]
                    assert lineage_data["measure_name"] == "Revenue Per Unit"
                    assert lineage_data["is_reachable_from_visual"] is True
                    assert "Base Revenue" in lineage_data["outbound_references"]

                    # 4. Execute plan_remediation tool
                    plan_args = {"path": str(GOLDEN_DIR / "test_bidirectional")}
                    plan_call = await session.call_tool("plan_remediation", arguments=plan_args)
                    assert not plan_call.isError
                    plan_data = json.loads(plan_call.content[0].text)  # type: ignore[attr-defined]
                    assert plan_data["total_proposals"] == 1
                    assert plan_data["score_gain"] > 0

                    # 5. Execute add_suppression & list_suppressions on temporary model copy
                    temp_model = tmp_path / "temp_pbip"
                    shutil.copytree(GOLDEN_DIR / "test_bidirectional", temp_model)

                    add_supp_args = {
                        "path": str(temp_model),
                        "rule_id": "MODEL_BIDIRECTIONAL",
                        "location": "Sales[ID] <-> Customer[ID]",
                        "reason": "E2E Test Exception",
                    }
                    add_supp_call = await session.call_tool("add_suppression", arguments=add_supp_args)
                    assert not add_supp_call.isError
                    add_supp_data = json.loads(add_supp_call.content[0].text)  # type: ignore[attr-defined]
                    assert add_supp_data["status"] == "SUCCESS"
                    assert add_supp_data["total_suppressions"] == 1

                    list_supp_call = await session.call_tool("list_suppressions", arguments={"path": str(temp_model)})
                    assert not list_supp_call.isError
                    list_supp_data = json.loads(list_supp_call.content[0].text)  # type: ignore[attr-defined]
                    assert list_supp_data["total_suppressions"] == 1
                    assert list_supp_data["suppressions"][0]["rule_id"] == "MODEL_BIDIRECTIONAL"

                    # 6. Execute suggest_dax_rewrite tool
                    dax_args = {
                        "rule_id": "DAX_SUSPICIOUS_PATTERN",
                        "dax_expression": "CALCULATE(SUM(Sales[Amount]), ALL(Sales))",
                    }
                    dax_call = await session.call_tool("suggest_dax_rewrite", arguments=dax_args)
                    assert not dax_call.isError
                    dax_data = json.loads(dax_call.content[0].text)  # type: ignore[attr-defined]
                    assert dax_data["rule_id"] == "DAX_SUSPICIOUS_PATTERN"
                    assert "advisory_note" in dax_data

        asyncio.run(_run())

    def test_e2e_mcp_apply_remediation_lifecycle(
        self,
        mcp_server_params: StdioServerParameters,
        tmp_path: Path,
    ):
        """Test full plan -> approve -> apply_remediation -> backup -> re-scan cycle over JSON-RPC."""

        async def _run():
            async with stdio_client(mcp_server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    # 1. Prepare isolated model in tmp_path
                    target_model = tmp_path / "model_to_fix"
                    shutil.copytree(GOLDEN_DIR / "test_bidirectional", target_model)

                    # 2. Plan remediation over JSON-RPC
                    plan_call = await session.call_tool("plan_remediation", arguments={"path": str(target_model)})
                    assert not plan_call.isError
                    plan_data = json.loads(plan_call.content[0].text)  # type: ignore[attr-defined]
                    patches = plan_data["plan"]["patches"]
                    assert len(patches) >= 1
                    patch_id = patches[0]["patch_id"]

                    # 3. Apply remediation over JSON-RPC with typed patch_ids list
                    apply_call = await session.call_tool(
                        "apply_remediation",
                        arguments={"path": str(target_model), "patch_ids": [patch_id]},
                    )
                    assert not apply_call.isError
                    apply_data = json.loads(apply_call.content[0].text)  # type: ignore[attr-defined]
                    assert apply_data["status"] == "APPLIED"
                    assert apply_data["applied_count"] == 1
                    assert apply_data["score_gain"] > 0
                    assert apply_data["backup_location"] is not None
                    assert Path(apply_data["backup_location"]).exists()

                    # 4. Verify model state improved upon re-scan over JSON-RPC
                    scan_after = await session.call_tool("scan_model", arguments={"path": str(target_model)})
                    assert not scan_after.isError
                    scan_after_data = json.loads(scan_after.content[0].text)  # type: ignore[attr-defined]
                    # Bidirectional finding should now be resolved
                    assert not any(f["rule_id"] == "MODEL_BIDIRECTIONAL" for f in scan_after_data["findings"])

        asyncio.run(_run())

    def test_e2e_mcp_apply_whole_plan_and_suppression_survives(
        self,
        mcp_server_params: StdioServerParameters,
        tmp_path: Path,
    ):
        """Apply every patch of a multi-file plan over JSON-RPC, with a suppression added first.

        Covers what the single-patch lifecycle test does not: one apply that edits several
        files and creates a new parameter file, and a suppression that must stay in force
        after the model has been rewritten.
        """

        async def _run():
            async with stdio_client(mcp_server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    model = tmp_path / "multi_patch_model"
                    shutil.copytree(GOLDEN_DIR / "test_model_auto_datetime_bloat", model)

                    async def scan() -> dict:
                        call = await session.call_tool("scan_model", arguments={"path": str(model)})
                        assert not call.isError
                        return json.loads(call.content[0].text)  # type: ignore[attr-defined]

                    before = await scan()
                    assert any(f["rule_id"] == "MODEL_AUTO_DATETIME_BLOAT" for f in before["findings"])

                    # Suppress one unrelated finding first, so we can check it is still hidden afterwards.
                    other = next((f for f in before["findings"] if f["rule_id"] != "MODEL_AUTO_DATETIME_BLOAT"), None)
                    assert other is not None, "the fixture needs a second finding to suppress"
                    supp = await session.call_tool("add_suppression", arguments={
                        "path": str(model), "rule_id": other["rule_id"],
                        "location": other.get("location") or "", "reason": "kept across apply",
                    })
                    assert not supp.isError

                    plan_call = await session.call_tool("plan_remediation", arguments={"path": str(model)})
                    assert not plan_call.isError
                    plan = json.loads(plan_call.content[0].text)  # type: ignore[attr-defined]
                    ids = [p["patch_id"] for p in plan["plan"]["patches"]]
                    assert len(ids) >= 2, "the fixture should need more than one patch"
                    files = {p["file_path"] for p in plan["plan"]["patches"]}
                    assert len(files) >= 2, "the patches should touch more than one file"

                    apply_call = await session.call_tool("apply_remediation", arguments={"path": str(model), "patch_ids": ids})
                    assert not apply_call.isError
                    applied = json.loads(apply_call.content[0].text)  # type: ignore[attr-defined]
                    assert applied["status"] == "APPLIED"
                    assert applied["applied_count"] == len(ids)
                    assert Path(applied["backup_location"]).exists()

                    after = await scan()
                    assert not any(f["rule_id"] == "MODEL_AUTO_DATETIME_BLOAT" and not f.get("suppressed") for f in after["findings"])
                    assert after["scores"]["overall"] > before["scores"]["overall"]
                    still = [f for f in after["findings"] if f["rule_id"] == other["rule_id"] and f.get("location") == other.get("location")]
                    assert still and all(f.get("suppressed") for f in still), "the suppression must survive the apply"

        asyncio.run(_run())
