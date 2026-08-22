"""URI-addressable static resources for PBIP Sentinel MCP Server.

Provides direct access to rule specifications and catalog metadata without dynamic LLM round-trips.
"""
from __future__ import annotations

import json
from typing import Any
from pbiscan.engine.recommendations import RECOMMENDATIONS


def get_rules_catalog_json() -> str:
    """Return the entire static rule catalog as a formatted JSON string."""
    catalog: dict[str, Any] = {}
    for rule_id, meta in sorted(RECOMMENDATIONS.items()):
        category = rule_id.split("_")[0].lower()
        catalog[rule_id] = {
            "rule_id": rule_id,
            "category": category,
            "title": meta.get("title", ""),
            "issue": meta.get("issue", ""),
            "impact": meta.get("impact", ""),
            "recommendation": meta.get("recommendation", ""),
        }
    return json.dumps({"rules": catalog, "total_rules": len(catalog)}, indent=2)


def get_rule_detail_json(rule_id: str) -> str:
    """Return structured specification and guidance for a single rule_id."""
    normalized_id = rule_id.strip().upper()
    meta = RECOMMENDATIONS.get(normalized_id)
    if not meta:
        return json.dumps({
            "error": f"Rule '{rule_id}' not found in PBIP Sentinel rule catalog",
            "available_rules": sorted(RECOMMENDATIONS.keys()),
        }, indent=2)

    category = normalized_id.split("_")[0].lower()
    return json.dumps({
        "rule_id": normalized_id,
        "category": category,
        "title": meta.get("title", ""),
        "issue": meta.get("issue", ""),
        "impact": meta.get("impact", ""),
        "recommendation": meta.get("recommendation", ""),
    }, indent=2)
