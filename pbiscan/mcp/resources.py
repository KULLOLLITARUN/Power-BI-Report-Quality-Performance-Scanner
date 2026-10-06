"""URI-addressable static resources for PBIP Sentinel MCP Server.

Provides direct access to rule specifications and catalog metadata without dynamic LLM round-trips.
"""
from __future__ import annotations

import json
from typing import Any
from pbiscan.engine.recommendations import RECOMMENDATIONS
from pbiscan.rules.catalog import RULES_BY_ID


def _rule_entry(rule_id: str) -> dict[str, Any]:
    spec = RULES_BY_ID[rule_id]
    meta = RECOMMENDATIONS.get(rule_id, {})
    return {
        "rule_id": rule_id,
        "code": spec.code,
        "category": spec.category,
        "severity": spec.severity,
        "confidence": spec.confidence,
        "title": meta.get("title", ""),
        "issue": meta.get("issue", ""),
        "impact": meta.get("impact", ""),
        "recommendation": meta.get("recommendation", ""),
    }


def get_rules_catalog_json() -> str:
    """Return the entire static rule catalog as a formatted JSON string."""
    catalog = {rule_id: _rule_entry(rule_id) for rule_id in sorted(RULES_BY_ID)}
    return json.dumps({"rules": catalog, "total_rules": len(catalog)}, indent=2)


def get_rule_detail_json(rule_id: str) -> str:
    """Return structured specification and guidance for a single rule_id."""
    normalized_id = rule_id.strip().upper()
    if normalized_id not in RULES_BY_ID:
        return json.dumps({
            "error": f"Rule '{rule_id}' not found in PBIP Sentinel rule catalog",
            "available_rules": sorted(RULES_BY_ID),
        }, indent=2)
    return json.dumps(_rule_entry(normalized_id), indent=2)
