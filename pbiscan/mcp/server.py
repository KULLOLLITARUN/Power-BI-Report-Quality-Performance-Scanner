"""PBIP Sentinel FastMCP Server implementation.

Registers URI-addressable resources, prompts, and typed tool handlers with strict annotations.
"""
from __future__ import annotations

from typing import Any, Optional

try:
    from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
    MCP_AVAILABLE = True
except ImportError:
    FastMCP = None  # type: ignore
    MCP_AVAILABLE = False

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


def create_server() -> Any:
    """Instantiate and configure the PBIP Sentinel FastMCP Server."""
    if not MCP_AVAILABLE or FastMCP is None:
        raise ImportError(
            "The 'mcp' package is required to run the PBIP Sentinel MCP server. "
            "Install it via: pip install 'pbiscan[mcp]'"
        )

    mcp = FastMCP(
        name="PBIP Sentinel",
        instructions=(
            "PBIP Sentinel Model Context Protocol Server. "
            "Provides deterministic static analysis, rule catalog inspection, "
            "and safe remediation planning for Power BI PBIP projects."
        ),
    )

    # -----------------------------------------------------------------------
    # Resources (URI-Addressable Static Rule Catalog)
    # -----------------------------------------------------------------------

    @mcp.resource("pbiscan://rules")
    def rules_catalog() -> str:
        """Full PBIP Sentinel static quality rule catalog (13 rules)."""
        return get_rules_catalog_json()

    @mcp.resource("pbiscan://rules/{rule_id}")
    def rule_detail(rule_id: str) -> str:
        """Specification, description, impact, and recommendation for a specific rule ID."""
        return get_rule_detail_json(rule_id)

    # -----------------------------------------------------------------------
    # Prompts (Pre-Registered Guided Workflows)
    # -----------------------------------------------------------------------

    @mcp.prompt("audit-model")
    def prompt_audit(path: str) -> str:
        """Execute a full PBIP Sentinel quality and governance audit on a Power BI project."""
        return get_audit_model_prompt(path)

    @mcp.prompt("remediate-safely")
    def prompt_remediate(path: str, rule_filter: str = "") -> str:
        """Perform a multi-step safe remediation review with sandbox validation."""
        return get_remediate_safely_prompt(path, rule_filter=rule_filter)

    @mcp.prompt("inspect-dax-measure")
    def prompt_inspect_measure(path: str, measure_name: str) -> str:
        """Inspect dependency lineage, inbound callers, and visual reachability for a measure."""
        return get_inspect_dax_prompt(path, measure_name=measure_name)

    # -----------------------------------------------------------------------
    # Read-Only Tools (Zero Mutation)
    # -----------------------------------------------------------------------

    @mcp.tool(name="scan_model")
    def scan_model(path: str, config_path: Optional[str] = None) -> dict[str, Any]:
        """Scan a Power BI project (PBIP directory) and return structured quality findings and scores.

        Read-only tool: performs zero mutations.
        """
        return handle_scan_model(path=path, config_path=config_path)

    @mcp.tool(name="diff_models")
    def diff_models(
        baseline_path: str,
        current_path: str,
        policy: str = "PASS_ON_IMPROVEMENT_ONLY",
    ) -> dict[str, Any]:
        """Compare a baseline model against a current model to calculate score drift and CI/CD gate status.

        Read-only tool: performs zero mutations.
        """
        return handle_diff_models(
            baseline_path=baseline_path,
            current_path=current_path,
            policy=policy,
        )

    @mcp.tool(name="get_measure_lineage")
    def get_measure_lineage(path: str, measure_name: str) -> dict[str, Any]:
        """Inspect dependency lineage, inbound callers, and visual reachability for a DAX measure.

        Read-only tool: performs zero mutations.
        """
        return handle_get_measure_lineage(path=path, measure_name=measure_name)

    @mcp.tool(name="plan_remediation")
    def plan_remediation(path: str, rule_filter: Optional[str] = None) -> dict[str, Any]:
        """Generate a candidate safe remediation plan with Before/After score projections and diffs.

        Read-only tool: runs in an isolated temporary sandbox and modifies zero files on disk.
        """
        return handle_plan_remediation(path=path, rule_filter=rule_filter)

    @mcp.tool(name="list_suppressions")
    def list_suppressions(path: str) -> dict[str, Any]:
        """List all active finding suppressions in pbiscan.suppressions.json for a project.

        Read-only tool: performs zero mutations.
        """
        return handle_list_suppressions(path=path)

    @mcp.tool(name="suggest_dax_rewrite")
    def suggest_dax_rewrite(
        rule_id: str,
        dax_expression: str,
        evidence: str = "",
    ) -> dict[str, Any]:
        """Advisory guidance for rewriting flagged DAX anti-patterns into high-performance alternatives.

        Read-only tool: advisory suggestion for human review only.
        """
        return handle_suggest_dax_rewrite(
            rule_id=rule_id,
            dax_expression=dax_expression,
            evidence=evidence,
        )

    # -----------------------------------------------------------------------
    # Destructive / File Mutation Tools (Host Confirmation Prompt Triggered)
    # -----------------------------------------------------------------------

    @mcp.tool(name="apply_remediation")
    def apply_remediation(path: str, patch_ids: list[str]) -> dict[str, Any]:
        """Apply approved candidate remediation patches with SHA-256 validation, backups, and audit store.

        DESTRUCTIVE TOOL: Mutates model files on disk after creating atomic backups.
        """
        return handle_apply_remediation(path=path, patch_ids=patch_ids)

    @mcp.tool(name="add_suppression")
    def add_suppression(
        path: str,
        rule_id: str,
        location: str,
        reason: str = "Suppressed via MCP",
        added_by: str = "MCP Agent",
    ) -> dict[str, Any]:
        """Add a permanent rule finding suppression to pbiscan.suppressions.json.

        DESTRUCTIVE TOOL: Writes suppression rule to pbiscan.suppressions.json.
        """
        return handle_add_suppression(
            path=path,
            rule_id=rule_id,
            location=location,
            reason=reason,
            added_by=added_by,
        )

    return mcp
