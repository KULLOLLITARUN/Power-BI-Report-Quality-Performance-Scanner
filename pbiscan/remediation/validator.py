"""Sandbox Before -> After validation loop for candidate remediation patches."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Optional

from pbiscan.diff import DiffService, QualityGatePolicy
from pbiscan.service import ScanResult, ScanService
from pbiscan.remediation.models import (
    Patch,
    PatchLifecycleState,
    PatchValidationResult,
    RemediationPlan,
    compute_file_sha256,
    compute_sha256,
)


class SandboxValidator:
    """Validates candidate remediation plans in an isolated temporary sandbox."""

    @classmethod
    def apply_patches_to_dir(cls, patches: list[Patch], target_dir: Path) -> list[str]:
        """Apply patch chunks to files inside target_dir. Returns list of errors if any."""
        errors: list[str] = []

        # Group patches and their chunks by resolved target file
        patches_by_filename: dict[str, list[Patch]] = {}
        for patch in patches:
            patches_by_filename.setdefault(patch.file_path.name, []).append(patch)

        for filename, file_patches in patches_by_filename.items():
            candidates = [p for p in target_dir.glob(f"**/{filename}")]
            if not candidates:
                errors.append(f"Target file not found in sandbox: {filename}")
                continue

            sandbox_file = candidates[0]
            
            # Check source hash against expected
            expected_hash = file_patches[0].source_hash
            current_hash = compute_file_sha256(sandbox_file)
            if current_hash != expected_hash:
                errors.append(
                    f"Source hash mismatch for {sandbox_file.name}: "
                    f"expected {expected_hash[:8]}, got {current_hash[:8]}"
                )
                continue

            content = sandbox_file.read_text(encoding="utf-8")
            lines = content.splitlines(keepends=True)

            # Collect all chunks across all patches for this file
            all_chunks = []
            for p in file_patches:
                all_chunks.extend(p.chunks)

            # Sort chunks in reverse line order (highest line number first)
            sorted_chunks = sorted(all_chunks, key=lambda c: c.start_line, reverse=True)
            chunk_error = False

            for chunk in sorted_chunks:
                start_idx = chunk.start_line - 1
                end_idx = chunk.end_line  # non-inclusive slice

                if start_idx < 0 or end_idx > len(lines):
                    errors.append(f"Line range [{chunk.start_line}:{chunk.end_line}] out of bounds in {sandbox_file.name}")
                    chunk_error = True
                    break

                target_slice = "".join(lines[start_idx:end_idx])
                slice_hash = compute_sha256(target_slice)

                if slice_hash != chunk.original_text_hash:
                    errors.append(
                        f"Chunk text hash mismatch in {sandbox_file.name} line {chunk.start_line}: "
                        f"expected {chunk.original_text_hash[:8]}, got {slice_hash[:8]}"
                    )
                    chunk_error = True
                    break

                # Replace slice
                if chunk.replacement_text:
                    repl_lines = chunk.replacement_text.splitlines(keepends=True)
                    lines[start_idx:end_idx] = repl_lines
                else:
                    lines[start_idx:end_idx] = []

            if not chunk_error:
                sandbox_file.write_text("".join(lines), encoding="utf-8")

        return errors

    @classmethod
    def validate_plan(
        cls,
        plan: RemediationPlan,
        original_scan: ScanResult,
        config_path: Optional[str] = None,
    ) -> PatchValidationResult:
        """Execute the full Before -> After sandbox validation loop."""
        rejection_reasons: list[str] = []
        actionable = plan.actionable_patches

        if not actionable:
            return PatchValidationResult(
                accepted=True,
                rejection_reasons=[],
                finding_resolved=True,
                resolved_count=0,
                expected_resolved_count=0,
                score_delta=0.0,
                new_high_critical_count=0,
                new_findings=[],
                resolved_findings=[],
                before_score=original_scan.overall_score,
                after_score=original_scan.overall_score,
            )

        # 1. Create temporary sandbox workspace
        with tempfile.TemporaryDirectory(prefix="pbiscan_sandbox_") as temp_dir:
            sandbox_path = Path(temp_dir) / plan.model_path.name
            shutil.copytree(plan.model_path, sandbox_path)

            # 2. Apply candidate patches in sandbox
            patch_errors = cls.apply_patches_to_dir(actionable, sandbox_path)
            if patch_errors:
                for p in actionable:
                    p.state = PatchLifecycleState.REJECTED
                return PatchValidationResult(
                    accepted=False,
                    rejection_reasons=[f"Patch application error: {e}" for e in patch_errors],
                    finding_resolved=False,
                    resolved_count=0,
                    expected_resolved_count=len(actionable),
                    score_delta=0.0,
                    new_high_critical_count=0,
                    new_findings=[],
                    resolved_findings=[],
                    before_score=original_scan.overall_score,
                    after_score=original_scan.overall_score,
                )

            # 3. Rescan patched sandbox model
            try:
                after_scan = ScanService.execute_scan(
                    project_path=sandbox_path,
                    config_path=config_path,
                )
            except Exception as exc:
                for p in actionable:
                    p.state = PatchLifecycleState.REJECTED
                return PatchValidationResult(
                    accepted=False,
                    rejection_reasons=[f"Post-patch model scan crashed: {exc}"],
                    finding_resolved=False,
                    resolved_count=0,
                    expected_resolved_count=len(actionable),
                    score_delta=0.0,
                    new_high_critical_count=0,
                    new_findings=[],
                    resolved_findings=[],
                    before_score=original_scan.overall_score,
                    after_score=0.0,
                )

            # 4. Compare Before vs After using DiffService
            diff_res = DiffService.compare(
                baseline=original_scan,
                current=after_scan,
                policy=QualityGatePolicy(fail_on_regression=False),
            )

            # 5. Evaluate strict acceptance criteria
            resolved_findings = [
                t.to_dict() for t in diff_res.transitions
                if str(t.state.value if hasattr(t.state, 'value') else t.state) == "RESOLVED"
            ]
            new_findings = [
                t.to_dict() for t in diff_res.transitions
                if str(t.state.value if hasattr(t.state, 'value') else t.state) == "NEW"
            ]
            new_high_critical = [
                f for f in new_findings
                if str(f.get("severity", "")).upper() in ("CRITICAL", "HIGH")
            ]

            target_rules = {p.rule_id for p in actionable}
            resolved_rules = {f.get("rule_id") for f in resolved_findings}

            # Check: Did each target finding resolve?
            for p in actionable:
                matched = any(
                    rf.get("rule_id") == p.rule_id
                    for rf in resolved_findings
                )
                if not matched:
                    rejection_reasons.append(
                        f"Target finding for rule {p.rule_id} ({p.evidence.finding_key}) was not resolved after patch."
                    )

            # Check: Score regression
            score_delta = diff_res.score_drift.overall_delta
            if score_delta < 0.0:
                rejection_reasons.append(
                    f"Health score regressed from {diff_res.score_drift.baseline_score:.1f} to {diff_res.score_drift.current_score:.1f} (delta {score_delta:+.1f})"
                )

            # Check: New high/critical findings
            if new_high_critical:
                rejection_reasons.append(
                    f"Patch introduced {len(new_high_critical)} new HIGH/CRITICAL finding(s): "
                    + ", ".join(f.get("rule_id", "UNKNOWN") for f in new_high_critical)
                )

            accepted = len(rejection_reasons) == 0

            # Update patch lifecycle states
            for p in actionable:
                if accepted:
                    p.state = PatchLifecycleState.VALIDATED
                else:
                    p.state = PatchLifecycleState.REJECTED

            return PatchValidationResult(
                accepted=accepted,
                rejection_reasons=rejection_reasons,
                finding_resolved=len(target_rules.intersection(resolved_rules)) > 0,
                resolved_count=len(resolved_findings),
                expected_resolved_count=len(actionable),
                score_delta=score_delta,
                new_high_critical_count=len(new_high_critical),
                new_findings=new_findings,
                resolved_findings=resolved_findings,
                before_score=diff_res.score_drift.baseline_score,
                after_score=diff_res.score_drift.current_score,
            )
