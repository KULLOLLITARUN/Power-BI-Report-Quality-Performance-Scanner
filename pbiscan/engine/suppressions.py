"""Suppression engine — loads and applies pbiscan.suppressions.json rules.

Suppression does NOT prevent a rule from firing.
Suppression marks matching findings as suppressed=True and excludes them from scoring deductions,
while keeping them transparently visible and auditable in reports.
"""
from __future__ import annotations
from dataclasses import dataclass
import fnmatch
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from pbiscan.engine.issue import Issue


def _normalise_loc(loc: str) -> str:
    return loc.lower().replace("↔", "<->").replace("→", "->").replace("←", "<-").strip()


@dataclass
class SuppressionRule:
    """A single suppression rule declared in pbiscan.suppressions.json."""
    rule_id: str
    location_pattern: str      # exact match or glob pattern against Issue.location
    reason: str
    added_by: Optional[str] = None
    added_at: Optional[str] = None

    def matches(self, issue_rule_id: str, issue_location: Optional[str]) -> bool:
        """Check if this suppression matches a given finding."""
        if self.rule_id.upper() != issue_rule_id.upper():
            return False

        if not self.location_pattern or self.location_pattern == "*":
            return True

        if not issue_location:
            return False

        norm_pat = _normalise_loc(self.location_pattern)
        norm_loc = _normalise_loc(issue_location)

        # 1. Exact match
        if norm_pat == norm_loc:
            return True

        # 2. Glob / wildcard match (safe with square brackets e.g. Table[Column])
        if "*" in norm_pat or "?" in norm_pat:
            parts = norm_pat.split("*")
            escaped_parts = [re.escape(p).replace(r"\?", ".") for p in parts]
            regex_str = "^" + ".*".join(escaped_parts) + "$"
            if re.match(regex_str, norm_loc, re.IGNORECASE):
                return True

        # 3. Substring match
        if norm_pat in norm_loc:
            return True

        return False


def load_suppressions(path: str | Path) -> list[SuppressionRule]:
    """Reads pbiscan.suppressions.json from the scan target directory.
    
    Absent file = no suppressions, not an error.
    """
    p = Path(path)
    suppressions_file: Optional[Path] = None

    if p.is_file():
        if p.name == "pbiscan.suppressions.json":
            suppressions_file = p
        else:
            # Check sibling in same directory
            candidate = p.parent / "pbiscan.suppressions.json"
            if candidate.is_file():
                suppressions_file = candidate
    elif p.is_dir():
        candidate = p / "pbiscan.suppressions.json"
        if candidate.is_file():
            suppressions_file = candidate

    if not suppressions_file or not suppressions_file.exists():
        return []

    try:
        data = json.loads(suppressions_file.read_text(encoding="utf-8"))
        raw_list = data.get("suppressions", [])
        rules: list[SuppressionRule] = []
        for item in raw_list:
            rule_id = item.get("rule_id", "")
            loc = item.get("location") or item.get("location_pattern", "*")
            reason = item.get("reason", "Suppressed by team policy")
            added_by = item.get("added_by")
            added_at = item.get("added_at")
            if rule_id:
                rules.append(SuppressionRule(
                    rule_id=rule_id,
                    location_pattern=loc,
                    reason=reason,
                    added_by=added_by,
                    added_at=added_at,
                ))
        return rules
    except Exception:
        # Invalid JSON or unreadable file: return empty list safely
        return []


def apply_suppressions(issues: list[Issue], suppressions: list[SuppressionRule]) -> list[Issue]:
    """Marks matching issues as suppressed=True with suppression_reason set.
    
    Never removes an issue from the list — suppression must remain visible/auditable.
    """
    if not suppressions:
        return issues

    for issue in issues:
        for supp in suppressions:
            if supp.matches(issue.rule_id, issue.location):
                issue.suppressed = True
                issue.suppression_reason = supp.reason
                break

    return issues
