"""Pre-registered MCP prompt workflows for PBIP Sentinel."""
from __future__ import annotations


def get_audit_model_prompt(path: str) -> str:
    """Prompt template instructing the assistant to execute a full quality audit."""
    return (
        f"Please run a comprehensive PBIP Sentinel quality and governance audit on the Power BI project at: `{path}`.\n\n"
        f"Workflow instructions:\n"
        f"1. Use the `scan_model` tool on `{path}` to extract structured findings and calculate health scores.\n"
        f"2. Summarize overall health and category breakdowns (Model, DAX, Report Layout, Security).\n"
        f"3. Highlight any CRITICAL or HIGH severity findings, explaining the underlying performance and governance risks.\n"
        f"4. Propose safe next steps for remediation."
    )


def get_remediate_safely_prompt(path: str, rule_filter: str = "") -> str:
    """Prompt template guiding a multi-step safe remediation review."""
    rule_clause = f" specifically for rule `{rule_filter}`" if rule_filter else ""
    return (
        f"Please perform a safe remediation analysis on the Power BI project at `{path}`{rule_clause}.\n\n"
        f"Workflow instructions:\n"
        f"1. Call `plan_remediation` on `{path}` to generate candidate patches and sandbox Before/After score projections.\n"
        f"2. Review the proposed diffs and explain the exact structural changes to the user.\n"
        f"3. Verify that zero semantic references or active visual consumers are broken.\n"
        f"4. Ask for explicit user confirmation before executing `apply_remediation` with the approved patch IDs."
    )


def get_inspect_dax_prompt(path: str, measure_name: str) -> str:
    """Prompt template for inspecting measure lineage and DAX graph connectivity."""
    return (
        f"Please inspect the measure `{measure_name}` in the Power BI project at `{path}`.\n\n"
        f"Workflow instructions:\n"
        f"1. Call `get_measure_lineage` on `{path}` for measure `{measure_name}`.\n"
        f"2. Analyze its inbound dependents, outbound referenced measures, and visual reachability.\n"
        f"3. If the measure is unused, check if it is referenced in calculation groups, field parameters, or RLS."
    )
