"""MCP Tool implementations for PBIP Sentinel.

Wraps deterministic scan, diff, lineage, and remediation engines into typed JSON handlers.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pbiscan.diff import DiffService, QualityGatePolicy
from pbiscan.engine.recommendations import RECOMMENDATIONS
from pbiscan.engine.suppressions import load_suppressions
from pbiscan.remediation.engine import RemediationEngine
from pbiscan.service import ScanService


def handle_scan_model(path: str, config_path: Optional[str] = None) -> dict[str, Any]:
    """Scan a Power BI project directory and return structured quality audit findings and scores."""
    p = Path(path)
    if not p.exists():
        return {"error": f"Path does not exist: {path}", "status": "ERROR"}

    res = ScanService.execute_scan(project_path=p, config_path=config_path)
    return res.to_dict()


def handle_diff_models(
    baseline_path: str,
    current_path: str,
    policy: str = "PASS_ON_IMPROVEMENT_ONLY",
) -> dict[str, Any]:
    """Compare a baseline model against a current model to calculate score drift and quality gate status."""
    p_base = Path(baseline_path)
    p_curr = Path(current_path)

    if not p_base.exists():
        return {"error": f"Baseline path does not exist: {baseline_path}", "status": "ERROR"}
    if not p_curr.exists():
        return {"error": f"Current path does not exist: {current_path}", "status": "ERROR"}

    base_scan = ScanService.execute_scan(p_base)
    curr_scan = ScanService.execute_scan(p_curr)

    gate_policy = QualityGatePolicy(fail_on_regression=True) if policy.upper() == "FAIL_ON_REGRESSION" else QualityGatePolicy()

    diff_res = DiffService.compare(base_scan, curr_scan, policy=gate_policy)
    return diff_res.to_dict()


def handle_get_measure_lineage(path: str, measure_name: str) -> dict[str, Any]:
    """Inspect dependency lineage, inbound callers, and visual reachability for a DAX measure."""
    p = Path(path)
    if not p.exists():
        return {"error": f"Path does not exist: {path}", "status": "ERROR"}

    res = ScanService.execute_scan(p)
    if not res.report:
        return {"error": "Failed to extract canonical report object", "status": "ERROR"}

    dax_graph = res.report.dax_graph
    target_meas = next(
        (m for m in res.report.dax.measures if m.name.lower() == measure_name.strip().lower()),
        None,
    )

    if not target_meas:
        return {
            "error": f"Measure '{measure_name}' not found in model",
            "available_measures": [m.name for m in res.report.dax.measures],
        }

    used_in_visuals = {
        r.target_name
        for r in res.report.semantic_references.references
        if r.activates_root
    }
    inbound = list(dax_graph.referenced_by(target_meas.name))
    outbound = list(dax_graph.references(target_meas.name))
    is_reachable = dax_graph.is_reachable_from_visual(target_meas.name, used_in_visuals)

    # Check semantic references
    sem_refs = [
        {
            "target_name": r.target_name,
            "target_table": r.target_table,
            "target_type": r.target_type,
            "source_type": r.source_type,
            "source_object": r.source_object,
            "source_file": r.source_file,
            "source_expression": r.source_expression,
        }
        for r in res.report.semantic_references.references
        if r.target_name.lower() == target_meas.name.lower()
    ]

    return {
        "measure_name": target_meas.name,
        "table": target_meas.table,
        "expression": target_meas.expression,
        "is_reachable_from_visual": is_reachable,
        "inbound_dependents": inbound,
        "outbound_references": outbound,
        "semantic_references": sem_refs,
    }


def handle_plan_remediation(path: str, rule_filter: Optional[str] = None) -> dict[str, Any]:
    """Generate a sandbox candidate remediation plan with Before/After score projections and diffs."""
    p = Path(path)
    if not p.exists():
        return {"error": f"Path does not exist: {path}", "status": "ERROR"}

    scan_res = RemediationEngine.analyze(p)
    plan = RemediationEngine.plan(p, scan_res, rule_filter=rule_filter)
    val = RemediationEngine.validate(plan, scan_res)

    return {
        "plan": plan.to_dict(),
        "validation": val.to_dict(),
        "total_proposals": len(plan.actionable_patches),
        "before_score": val.before_score,
        "after_score": val.after_score,
        "score_gain": round(val.after_score - val.before_score, 1),
    }


def handle_apply_remediation(path: str, patch_ids: list[str]) -> dict[str, Any]:
    """Apply approved candidate remediation patches with SHA-256 validation, backups, and audit store."""
    p = Path(path)
    if not p.exists():
        return {"error": f"Path does not exist: {path}", "status": "ERROR"}

    scan_res = RemediationEngine.analyze(p)
    plan = RemediationEngine.plan(p, scan_res)

    if patch_ids:
        plan = plan.filter_by_patch_ids(patch_ids)

    if not plan.actionable_patches:
        return {"status": "NO_OP", "message": "No actionable patches matched the requested IDs"}

    val = RemediationEngine.validate(plan, scan_res)
    if not val.accepted:
        return {
            "status": "REJECTED",
            "message": "Sandbox validation rejected the candidate patches",
            "rejection_reasons": val.rejection_reasons,
        }

    success, manifest = RemediationEngine.apply(
        plan=plan,
        validation_result=val,
        original_scan=scan_res,
    )
    return {
        "status": "APPLIED" if success else manifest.decision,
        "manifest_id": manifest.manifest_id,
        "applied_count": len(manifest.patches),
        "before_score": manifest.before_score,
        "after_score": manifest.after_score,
        "score_gain": round(manifest.after_score - manifest.before_score, 1),
        "backup_location": manifest.backup_location,
    }


def handle_add_suppression(
    path: str,
    rule_id: str,
    location: str,
    reason: str = "Suppressed via MCP",
    added_by: str = "MCP Agent",
) -> dict[str, Any]:
    """Add a permanent rule finding suppression to pbiscan.suppressions.json."""
    p = Path(path)
    if not p.exists():
        return {"error": f"Path does not exist: {path}", "status": "ERROR"}

    supp_dir = p if p.is_dir() else p.parent
    supp_file = supp_dir / "pbiscan.suppressions.json"

    data: dict[str, Any] = {"suppressions": []}
    if supp_file.exists():
        try:
            data = json.loads(supp_file.read_text(encoding="utf-8"))
            if not isinstance(data.get("suppressions"), list):
                data["suppressions"] = []
        except Exception:
            data = {"suppressions": []}

    new_supp = {
        "rule_id": rule_id.strip().upper(),
        "location": location.strip(),
        "reason": reason.strip(),
        "added_by": added_by,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    data["suppressions"].append(new_supp)
    supp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return {
        "status": "SUCCESS",
        "message": f"Added suppression for rule '{rule_id}' at location '{location}' to {supp_file.name}",
        "total_suppressions": len(data["suppressions"]),
    }


def handle_list_suppressions(path: str) -> dict[str, Any]:
    """List all active suppressions defined in pbiscan.suppressions.json for a project."""
    p = Path(path)
    if not p.exists():
        return {"error": f"Path does not exist: {path}", "status": "ERROR"}

    rules = load_suppressions(p)
    return {
        "total_suppressions": len(rules),
        "suppressions": [
            {
                "rule_id": r.rule_id,
                "location_pattern": r.location_pattern,
                "reason": r.reason,
                "added_by": r.added_by,
                "added_at": r.added_at,
            }
            for r in rules
        ],
    }


def handle_suggest_dax_rewrite(
    rule_id: str,
    dax_expression: str,
    evidence: str = "",
) -> dict[str, Any]:
    """Advisory helper providing best-practice DAX rewrite guidance for a flagged pattern."""
    normalized_id = rule_id.strip().upper()
    meta = RECOMMENDATIONS.get(normalized_id, {})

    return {
        "rule_id": normalized_id,
        "input_dax": dax_expression,
        "issue_summary": meta.get("issue", "Anti-pattern detected in DAX measure."),
        "recommendation": meta.get("recommendation", "Review and optimize DAX structure."),
        "advisory_note": (
            "DAX rewrites are advisory recommendations for human review. "
            "Never apply unverified DAX expressions directly without manual validation."
        ),
    }
