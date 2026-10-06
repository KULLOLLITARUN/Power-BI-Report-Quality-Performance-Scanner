"""Rule catalog — the single source of each rule's code, category, severity and confidence.

Rule functions build findings through new_finding(), so they cannot disagree
with this table. The README rule table, the MCP rules resource and the
in-browser engine (studio-ui/src/engine/clientScanner.ts) are checked against
it by tests/unit/test_rule_catalog.py and the cross-engine parity test.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from pbiscan.engine.issue import RuleFinding


@dataclass(frozen=True)
class RuleSpec:
    code: str          # short code shown in the README, e.g. "M001"
    rule_id: str
    category: str
    severity: str
    confidence: int    # 0–100


RULE_CATALOG: tuple[RuleSpec, ...] = (
    RuleSpec("M001", "MODEL_BIDIRECTIONAL", "model", "WARNING", 100),
    RuleSpec("M002", "MODEL_MANY_TO_MANY", "model", "WARNING", 100),
    RuleSpec("M003", "MODEL_NO_DATE_TABLE", "model", "WARNING", 70),
    RuleSpec("M004", "MODEL_HIGH_CARDINALITY", "model", "ADVISORY", 87),
    RuleSpec("M005", "MODEL_FACT_TO_FACT", "model", "ADVISORY", 60),
    RuleSpec("M006", "M_HARDCODED_DATA_SOURCE", "model", "HIGH", 95),
    RuleSpec("M007", "MODEL_AUTO_DATETIME_BLOAT", "model", "MEDIUM", 100),
    RuleSpec("D001", "DAX_SUSPICIOUS_PATTERN", "dax", "ADVISORY", 65),
    RuleSpec("D002", "DAX_EXCESSIVE_CALC_COLUMNS", "dax", "MEDIUM", 100),
    RuleSpec("D003", "DAX_DUPLICATE_MEASURE", "dax", "MEDIUM", 90),
    RuleSpec("D004", "DAX_UNUSED_MEASURE", "dax", "ADVISORY", 95),
    RuleSpec("R001", "REPORT_VISUAL_BLOAT", "report", "MEDIUM", 100),
    RuleSpec("R002", "REPORT_SLICER_BLOAT", "report", "MEDIUM", 100),
)

RULES_BY_ID: dict[str, RuleSpec] = {spec.rule_id: spec for spec in RULE_CATALOG}


def new_finding(
    rule_id: str,
    evidence: str,
    location: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> RuleFinding:
    """Build a RuleFinding with the catalog's category, severity and confidence."""
    spec = RULES_BY_ID[rule_id]
    return RuleFinding(
        rule_id=spec.rule_id,
        category=spec.category,
        severity=spec.severity,
        confidence=spec.confidence,
        evidence=evidence,
        location=location,
        metadata=metadata or {},
    )
