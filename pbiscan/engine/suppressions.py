"""Suppression engine — loads and applies pbiscan.suppressions.json rules.

Suppression does NOT prevent a rule from firing.
Suppression marks matching findings as suppressed=True and excludes them from scoring deductions,
while keeping them transparently visible and auditable in reports.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, Optional

from pbiscan.fileio import atomic_write_text

if TYPE_CHECKING:
    from pbiscan.engine.issue import Issue

logger = logging.getLogger(__name__)

SUPPRESSIONS_FILENAME = "pbiscan.suppressions.json"


class SuppressionFileError(Exception):
    """Raised when an existing suppressions file cannot be safely updated."""
    error_type = "SUPPRESSION_FILE_ERROR"


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


def load_suppressions(path: str | Path, warnings: Optional[list[str]] = None) -> list[SuppressionRule]:
    """Reads pbiscan.suppressions.json from the scan target directory.

    Absent file = no suppressions, not an error. An unreadable or malformed
    file also yields no suppressions, but is reported: it is logged, and the
    message is appended to `warnings` when a list is passed, so the user can
    see why previously suppressed findings reappeared.
    """
    p = Path(path)
    suppressions_file: Optional[Path] = None

    if p.is_file():
        if p.name == SUPPRESSIONS_FILENAME:
            suppressions_file = p
        else:
            # Check sibling in same directory
            candidate = p.parent / SUPPRESSIONS_FILENAME
            if candidate.is_file():
                suppressions_file = candidate
    elif p.is_dir():
        candidate = p / SUPPRESSIONS_FILENAME
        if candidate.is_file():
            suppressions_file = candidate

    if not suppressions_file or not suppressions_file.exists():
        return []

    def report(problem: str) -> list[SuppressionRule]:
        message = f"Ignoring suppressions in {suppressions_file}: {problem}"
        logger.warning(message)
        if warnings is not None:
            warnings.append(message)
        return []

    try:
        data = json.loads(suppressions_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return report(str(exc))

    if not isinstance(data, dict) or not isinstance(data.get("suppressions", []), list):
        return report('expected an object with a "suppressions" list')

    rules: list[SuppressionRule] = []
    for item in data.get("suppressions", []):
        if not isinstance(item, dict):
            continue
        rule_id = item.get("rule_id", "")
        if rule_id:
            rules.append(SuppressionRule(
                rule_id=rule_id,
                location_pattern=item.get("location") or item.get("location_pattern", "*"),
                reason=item.get("reason", "Suppressed by team policy"),
                added_by=item.get("added_by"),
                added_at=item.get("added_at"),
            ))
    return rules

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


def add_suppression(
    project_path: str | Path,
    rule_id: str,
    location: str,
    reason: str,
    added_by: Optional[str] = None,
) -> tuple[Path, int]:
    """Append one suppression to the project's pbiscan.suppressions.json.

    The file lives next to a .pbip file, or inside a project directory, and is
    created if absent. Returns the file path and the new suppression count.

    Raises:
        SuppressionFileError: if the existing file is unreadable or malformed.
            It is never overwritten in that case, since rewriting it would
            delete the team's existing suppressions.
    """
    p = Path(project_path)
    supp_file = (p if p.is_dir() else p.parent) / SUPPRESSIONS_FILENAME

    data: dict[str, Any] = {"suppressions": []}
    if supp_file.exists():
        try:
            data = json.loads(supp_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SuppressionFileError(
                f"{supp_file.name} is unreadable ({exc}); fix or remove it before adding suppressions."
            ) from exc
        if not isinstance(data, dict) or not isinstance(data.get("suppressions", []), list):
            raise SuppressionFileError(
                f'{supp_file.name} must be an object with a "suppressions" list; fix it before adding suppressions.'
            )
        data.setdefault("suppressions", [])

    entry: dict[str, Any] = {
        "rule_id": rule_id.strip().upper(),
        "location": location.strip(),
        "reason": reason.strip(),
    }
    if added_by:
        entry["added_by"] = added_by
    entry["added_at"] = datetime.now(timezone.utc).isoformat()
    data["suppressions"].append(entry)

    atomic_write_text(supp_file, json.dumps(data, indent=2))
    return supp_file, len(data["suppressions"])
