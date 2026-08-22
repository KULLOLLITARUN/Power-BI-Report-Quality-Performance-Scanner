"""Rich terminal console renderer for PBIP Sentinel Safe Remediation Engine."""
from __future__ import annotations

import sys
from typing import Optional

from pbiscan.remediation.models import (
    Patch,
    PatchValidationResult,
    RemediationPlan,
    RemediationSafety,
)

# ANSI Color codes
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[91m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_BLUE = "\033[94m"
_CYAN = "\033[96m"
_GRAY = "\033[90m"


def _supports_color() -> bool:
    return sys.stdout.isatty()


def _color(text: str, color_code: str) -> str:
    if not _supports_color():
        return text
    return f"{color_code}{text}{_RESET}"


class RemediationConsoleRenderer:
    """Renders human-readable remediation cards, diffs, and summaries to the terminal."""

    @classmethod
    def render_header(cls, model_name: str, proposal_count: int, before_score: float) -> str:
        """Render top summary banner for remediation proposals."""
        lines = [
            f"\n{_color('PBIP SENTINEL SAFE REMEDIATION ENGINE', _BOLD + _CYAN)}",
            _color("═" * 70, _CYAN),
            f"  {_color('Target Project :', _DIM)} {_color(model_name, _BOLD)}",
            f"  {_color('Baseline Score :', _DIM)} {_color(f'{before_score:.1f} / 100', _YELLOW)}",
            f"  {_color('Proposals Found:', _DIM)} {_color(str(proposal_count), _BOLD + _GREEN if proposal_count > 0 else _DIM)} actionable remediation patch(es)",
            _color("─" * 70, _GRAY),
        ]
        return "\n".join(lines)

    @classmethod
    def render_patch_card(
        cls,
        patch: Patch,
        index: int,
        total: int,
        predicted_after_score: Optional[float] = None,
        before_score: Optional[float] = None,
    ) -> str:
        """Render a single remediation proposal as an inspection card."""
        risk_color = _YELLOW if patch.evidence.semantic_risk == "MEDIUM" else (_RED if patch.evidence.semantic_risk == "HIGH" else _GREEN)
        safety_color = _GREEN if patch.safety == RemediationSafety.SAFE_AUTO else _YELLOW

        score_text = ""
        if predicted_after_score is not None and before_score is not None:
            delta = predicted_after_score - before_score
            delta_str = f"+{delta:.1f}" if delta > 0 else f"{delta:.1f}"
            score_text = f"  │ {_color('Predicted Score :', _DIM)} {before_score:.1f} → {_color(f'{predicted_after_score:.1f} ({delta_str})', _BOLD + _GREEN)}"

        lines = [
            f"\n┌─ {_color(f'[{index}/{total}] PROPOSAL: {patch.patch_id}', _BOLD + _CYAN)} " + "─" * max(0, 50 - len(patch.patch_id)),
            f"  │ {_color('Rule ID         :', _DIM)} {_color(patch.rule_id, _BOLD)}",
            f"  │ {_color('Safety Level    :', _DIM)} {_color(patch.safety.value, safety_color)}",
            f"  │ {_color('Semantic Risk   :', _DIM)} {_color(patch.evidence.semantic_risk, risk_color)}",
            f"  │ {_color('Target File     :', _DIM)} {_color(patch.file_path.name, _BOLD)} ({patch.file_path.as_posix()})",
            f"  │ {_color('Rationale       :', _DIM)} {patch.rationale}",
            f"  │ {_color('Expected Effect :', _DIM)} {_color(patch.evidence.expected_resolution or 'Target finding resolved', _GREEN)}",
        ]
        if score_text:
            lines.append(score_text)

        if patch.evidence.affected_objects:
            lines.append(f"  │ {_color('Affected Objects:', _DIM)} {', '.join(patch.evidence.affected_objects[:3])}")

        # Render Diff Preview
        lines.append("  │")
        lines.append(f"  │ {_color('Proposed Diff:', _BOLD)}")
        for chunk_idx, chunk in enumerate(patch.chunks, 1):
            lines.append(f"  │   {_color(f'@@ Lines {chunk.start_line}..{chunk.end_line} @@', _CYAN)}")
            for orig_line in chunk.original_text.splitlines():
                lines.append(f"  │   {_color('- ' + orig_line, _RED)}")
            for repl_line in chunk.replacement_text.splitlines():
                lines.append(f"  │   {_color('+ ' + repl_line, _GREEN)}")

        lines.append("└" + "─" * 68)
        return "\n".join(lines)

    @classmethod
    def render_summary(cls, plan: RemediationPlan, validation: PatchValidationResult) -> str:
        """Render final validation verdict and summary."""
        verdict_color = _BOLD + _GREEN if validation.accepted else _BOLD + _RED
        verdict_str = "ACCEPTED (PASSED ALL GATES)" if validation.accepted else "REJECTED (FAILED GATES)"
        delta_str = f"+{validation.score_delta:.1f}" if validation.score_delta > 0 else f"{validation.score_delta:.1f}"

        lines = [
            f"\n{_color('REMEDIATION VALIDATION VERDICT', _BOLD + _CYAN)}",
            _color("═" * 70, _CYAN),
            f"  {_color('Sandbox Gate  :', _DIM)} {_color(verdict_str, verdict_color)}",
            f"  {_color('Before Score  :', _DIM)} {validation.before_score:.1f} / 100",
            f"  {_color('After Score   :', _DIM)} {_color(f'{validation.after_score:.1f} / 100 ({delta_str})', _BOLD + _GREEN if validation.score_delta > 0 else _YELLOW)}",
            f"  {_color('Resolved Debt :', _DIM)} {_color(str(validation.resolved_count), _BOLD + _GREEN)} finding(s) resolved in sandbox",
            f"  {_color('New Findings  :', _DIM)} {_color(str(validation.new_high_critical_count), _GREEN if validation.new_high_critical_count == 0 else _RED)} new HIGH/CRITICAL",
        ]

        if validation.rejection_reasons:
            lines.append(f"\n  {_color('Rejection Reasons:', _BOLD + _RED)}")
            for r in validation.rejection_reasons:
                lines.append(f"   • {_color(r, _RED)}")

        lines.append(_color("═" * 70, _CYAN))
        return "\n".join(lines)
