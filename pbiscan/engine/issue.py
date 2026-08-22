"""Issue contracts — RuleFinding and AuditIssue.

Flow:
    Rule function → list[RuleFinding]
                        │
                        ▼
                  IssueGenerator
                        │
                        ▼
                  list[AuditIssue]   ← rendered in HTML / CLI

Rules return RuleFinding (detection data only, no prose).
IssueGenerator converts them to AuditIssue using engine/recommendations.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


VALID_SEVERITIES: frozenset[str] = frozenset(
    {"CRITICAL", "HIGH", "MEDIUM", "WARNING", "ADVISORY", "LOW"}
)
VALID_CATEGORIES: frozenset[str] = frozenset(
    {"model", "dax", "report", "security"}
)


# ---------------------------------------------------------------------------
# RuleFinding — returned by rule functions
# ---------------------------------------------------------------------------

@dataclass
class RuleFinding:
    """Returned by a rule function. Contains detection data only.

    Rules MUST NOT include recommendation prose here.
    Rules MUST NOT reference engine/recommendations.py.
    """
    rule_id: str
    category: str
    severity: str
    confidence: int                          # 0–100
    evidence: str                            # specific structural proof
    location: Optional[str] = None           # optional, e.g. "Table[Column]"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{self.severity}'. "
                f"Must be one of {sorted(VALID_SEVERITIES)}"
            )
        if self.category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{self.category}'. "
                f"Must be one of {sorted(VALID_CATEGORIES)}"
            )
        if not 0 <= self.confidence <= 100:
            raise ValueError(
                f"Confidence must be 0–100, got {self.confidence}"
            )


# ---------------------------------------------------------------------------
# AuditIssue — final output object, one row in the audit report
# ---------------------------------------------------------------------------

@dataclass
class AuditIssue:
    """Final audit output — one finding in the HTML report and CLI output."""
    rule_id: str
    category: str
    severity: str
    title: str
    issue: str
    evidence: str
    impact: str
    recommendation: str
    confidence: int
    location: Optional[str] = None
    suppressed: bool = False
    suppression_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize issue for JSON and Studio API responses."""
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "issue": self.issue,
            "evidence": self.evidence,
            "impact": self.impact,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "location": self.location,
            "suppressed": self.suppressed,
            "suppression_reason": self.suppression_reason,
        }


# Alias for canonical engine contract
Issue = AuditIssue


# ---------------------------------------------------------------------------
# IssueGenerator — converts RuleFinding → AuditIssue
# ---------------------------------------------------------------------------

class IssueGenerator:
    """Converts raw rule findings into full AuditIssue objects.

    Looks up title, issue, impact, and recommendation from the
    recommendations registry. Raises KeyError if a rule_id is
    not registered (unreviewed rules must not emit empty text).
    """

    def __init__(self) -> None:
        # Import here to avoid circular imports at module load time
        from pbiscan.engine.recommendations import get_recommendation
        self._get_recommendation = get_recommendation

    def generate(self, findings: list[RuleFinding]) -> list[AuditIssue]:
        """Convert a list of RuleFindings into AuditIssues."""
        issues: list[AuditIssue] = []
        for finding in findings:
            rec = self._get_recommendation(finding.rule_id)
            issues.append(AuditIssue(
                rule_id=finding.rule_id,
                category=finding.category,
                severity=finding.severity,
                title=rec["title"],
                issue=rec["issue"],
                evidence=finding.evidence,
                impact=rec["impact"],
                recommendation=rec["recommendation"],
                confidence=finding.confidence,
                location=finding.location,
            ))
        return issues
