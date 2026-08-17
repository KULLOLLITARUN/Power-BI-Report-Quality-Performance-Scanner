"""pbiscan Diff Console Renderer.

Formats DiffResult into clean, colored terminal output with:
- Overall score comparison & delta
- Category score drift
- Finding transitions breakdown (NEW, RESOLVED, PERSISTENT, MODIFIED)
- Quality gate verdict and failure explanations
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pbiscan.diff import DiffResult

# ANSI Color formatting
_RESET = "\033[0m"
_BOLD = "\033[1m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_BLUE = "\033[34m"
_CYAN = "\033[36m"
_DIM = "\033[2m"


def _colour(text: str, code: str) -> str:
    if sys.stdout.isatty():
        return f"{code}{text}{_RESET}"
    return text


class DiffConsoleRenderer:
    """Renders DiffResult to formatted ANSI terminal text."""

    def render(self, diff: DiffResult) -> str:
        lines: list[str] = []
        lines.append("")
        lines.append(_colour("PBIP SENTINEL DIFF", _BOLD))
        lines.append(f"  Baseline: {_colour(diff.baseline_name, _CYAN)}")
        lines.append(f"  Current:  {_colour(diff.current_name, _CYAN)}")
        lines.append("")

        # 1. Health Score Comparison
        lines.append(_colour("Health Score", _BOLD))
        base_s = f"{diff.score_drift.baseline_score:.1f}"
        curr_s = f"{diff.score_drift.current_score:.1f}"
        delta = diff.score_drift.overall_delta

        if delta > 0:
            delta_str = _colour(f"+{delta:.1f}  IMPROVED", _GREEN)
        elif delta < 0:
            delta_str = _colour(f"{delta:.1f}  DEGRADED", _RED)
        else:
            delta_str = _colour("0.0  UNCHANGED", _DIM)

        lines.append(f"  Baseline: {base_s}")
        lines.append(f"  Current:  {curr_s}")
        lines.append(f"  Delta:    {delta_str}")
        lines.append("")

        # 2. Category Drift
        lines.append(_colour("Category Drift", _BOLD))
        for cat, d_val in diff.score_drift.category_deltas.items():
            cat_name = cat.capitalize()
            if d_val > 0:
                d_str = _colour(f"+{d_val:.1f}", _GREEN)
            elif d_val < 0:
                d_str = _colour(f"{d_val:.1f}", _RED)
            else:
                d_str = _colour("0.0", _DIM)
            lines.append(f"  {cat_name:<10s} {d_str}")
        lines.append("")

        # 3. Finding Transitions Summary
        counts = {
            "NEW": len(diff.new_findings),
            "RESOLVED": len(diff.resolved_findings),
            "PERSISTENT": len(diff.persistent_findings),
            "MODIFIED": len(diff.modified_findings),
        }
        lines.append(_colour("Findings", _BOLD))
        lines.append(f"  NEW         {_colour(str(counts['NEW']), _RED if counts['NEW'] > 0 else _DIM)}")
        lines.append(f"  RESOLVED    {_colour(str(counts['RESOLVED']), _GREEN if counts['RESOLVED'] > 0 else _DIM)}")
        lines.append(f"  PERSISTENT  {counts['PERSISTENT']}")
        lines.append(f"  MODIFIED    {counts['MODIFIED']}")
        lines.append("")

        # 4. Detailed Transitions List
        if diff.new_findings:
            lines.append(_colour("Newly Introduced Findings (+):", _BOLD + _RED))
            for t in diff.new_findings:
                loc = f" | {t.location}" if t.location else ""
                lines.append(f"  + [{t.severity:<8s}] {t.rule_id}{loc}")
                if t.title:
                    lines.append(f"    {_colour(t.title, _DIM)}")
            lines.append("")

        if diff.resolved_findings:
            lines.append(_colour("Resolved Findings (-):", _BOLD + _GREEN))
            for t in diff.resolved_findings:
                loc = f" | {t.location}" if t.location else ""
                lines.append(f"  - [{t.severity:<8s}] {t.rule_id}{loc}")
                if t.title:
                    lines.append(f"    {_colour(t.title, _DIM)}")
            lines.append("")

        if diff.modified_findings:
            lines.append(_colour("Modified Findings (Δ):", _BOLD + _YELLOW))
            for t in diff.modified_findings:
                loc = f" | {t.location}" if t.location else ""
                lines.append(f"  Δ [{t.baseline_severity} -> {t.severity}] {t.rule_id}{loc}")
            lines.append("")

        # 5. Quality Gate Verdict
        lines.append(_colour("Quality Gate", _BOLD))
        if diff.verdict.passed:
            lines.append(f"  Verdict: {_colour('PASS', _BOLD + _GREEN)}")
        else:
            lines.append(f"  Verdict: {_colour('FAIL', _BOLD + _RED)}")
            for r in diff.verdict.reasons:
                lines.append(f"  Reason:  {_colour(r, _RED)}")
        lines.append("")

        return "\n".join(lines)
