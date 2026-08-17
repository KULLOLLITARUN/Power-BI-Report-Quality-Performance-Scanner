"""Remediation engine coordinating analysis, planning, sandbox validation, and transactional apply."""
from __future__ import annotations

import difflib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from pbiscan import __version__
from pbiscan.remediation.backup import BackupManager
from pbiscan.remediation.models import (
    PatchLifecycleState,
    PatchValidationResult,
    RemediationManifest,
    RemediationPlan,
    compute_file_sha256,
    compute_sha256,
)
from pbiscan.remediation.planner import RemediationPlanner
from pbiscan.remediation.validator import SandboxValidator
from pbiscan.service import ScanResult, ScanService


class RemediationEngine:
    """Enterprise Safe Remediation Engine for PBIP Sentinel."""

    @classmethod
    def analyze(cls, model_path: Path, config_path: Optional[str] = None) -> ScanResult:
        """Phase 1: Canonical scan execution via ScanService."""
        return ScanService.execute_scan(model_path, config_path=config_path)

    @classmethod
    def plan(
        cls,
        model_path: Path,
        scan_result: ScanResult,
        rule_filter: Optional[str] = None,
    ) -> RemediationPlan:
        """Phase 2: Generate candidate patch plan with auditable PatchEvidence."""
        planner = RemediationPlanner()
        return planner.plan(model_path, scan_result, rule_filter=rule_filter)

    @classmethod
    def validate(
        cls,
        plan: RemediationPlan,
        original_scan: ScanResult,
        config_path: Optional[str] = None,
    ) -> PatchValidationResult:
        """Phase 3: Execute Before -> After sandbox validation loop."""
        return SandboxValidator.validate_plan(plan, original_scan, config_path=config_path)

    @classmethod
    def apply(
        cls,
        plan: RemediationPlan,
        validation_result: PatchValidationResult,
        backup: bool = True,
        config_path: Optional[str] = None,
    ) -> Tuple[bool, RemediationManifest]:
        """Phase 4: Apply validated patches to real workspace with transactional rollback."""
        actionable = plan.actionable_patches
        created_at = datetime.utcnow().isoformat()
        
        # 1. Validation gate check
        if not validation_result.accepted:
            manifest = RemediationManifest(
                engine_version=__version__,
                model_name=plan.model_path.name,
                baseline_scan_hash=compute_file_sha256(plan.model_path / "model.bim") or "",
                created_at=created_at,
                decision="REJECTED",
                before_score=validation_result.before_score,
                after_score=validation_result.after_score,
                score_delta=validation_result.score_delta,
                patches=[p.to_dict() for p in plan.patches],
                conflicts=[c.to_dict() for c in plan.conflicts],
                rejection_reasons=validation_result.rejection_reasons,
            )
            return False, manifest

        # 2. Re-verify source hashes on real workspace to protect against stale changes
        for patch in actionable:
            current_hash = compute_file_sha256(patch.file_path)
            if current_hash != patch.source_hash:
                reason = (
                    f"Target file changed after remediation plan was generated: {patch.file_path.name} "
                    f"(expected {patch.source_hash[:8]}, actual {current_hash[:8]})"
                )
                for p in actionable:
                    p.state = PatchLifecycleState.REJECTED
                manifest = RemediationManifest(
                    engine_version=__version__,
                    model_name=plan.model_path.name,
                    baseline_scan_hash=patch.source_hash,
                    created_at=created_at,
                    decision="REJECTED",
                    before_score=validation_result.before_score,
                    after_score=validation_result.after_score,
                    score_delta=0.0,
                    patches=[p.to_dict() for p in plan.patches],
                    conflicts=[c.to_dict() for c in plan.conflicts],
                    rejection_reasons=[reason],
                )
                return False, manifest

        # 3. Create transactional backup
        backup_dir = None
        if backup:
            backup_dir = BackupManager.create_backup(plan.model_path)

        # 4. Apply patches to real workspace
        apply_errors = SandboxValidator.apply_patches_to_dir(actionable, plan.model_path)
        if apply_errors:
            if backup_dir:
                BackupManager.restore_backup(backup_dir, plan.model_path)
            for p in actionable:
                p.state = PatchLifecycleState.REJECTED
            manifest = RemediationManifest(
                engine_version=__version__,
                model_name=plan.model_path.name,
                baseline_scan_hash=compute_file_sha256(plan.model_path / "model.bim") or "",
                created_at=created_at,
                decision="REJECTED",
                before_score=validation_result.before_score,
                after_score=validation_result.after_score,
                score_delta=0.0,
                patches=[p.to_dict() for p in plan.patches],
                conflicts=[c.to_dict() for c in plan.conflicts],
                rejection_reasons=[f"Disk write error: {e}" for e in apply_errors],
            )
            return False, manifest

        # 5. Execute final verification scan on real workspace
        try:
            final_scan = ScanService.execute_scan(plan.model_path, config_path=config_path)
            if final_scan.overall_score < validation_result.before_score:
                raise ValueError(
                    f"Final scan score ({final_scan.overall_score:.1f}) regressed below baseline ({validation_result.before_score:.1f})"
                )
        except Exception as exc:
            # Rollback and verify restoration
            if backup_dir:
                BackupManager.restore_backup(backup_dir, plan.model_path)
                restored_ok = BackupManager.verify_restoration(backup_dir, plan.model_path)
                if not restored_ok:
                    raise RuntimeError("Critical rollback error: Restored model does not match original backup.")

            for p in actionable:
                p.state = PatchLifecycleState.REJECTED
            manifest = RemediationManifest(
                engine_version=__version__,
                model_name=plan.model_path.name,
                baseline_scan_hash=compute_file_sha256(plan.model_path / "model.bim") or "",
                created_at=created_at,
                decision="REJECTED",
                before_score=validation_result.before_score,
                after_score=0.0,
                score_delta=0.0,
                patches=[p.to_dict() for p in plan.patches],
                conflicts=[c.to_dict() for c in plan.conflicts],
                rejection_reasons=[f"Final verification failed, rolled back to backup: {exc}"],
            )
            return False, manifest

        # 6. Mark patches as APPLIED and assemble manifest
        for p in actionable:
            p.state = PatchLifecycleState.APPLIED

        manifest_id = f"MAN-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{compute_sha256(str(plan.model_path) + created_at)[:6]}"
        manifest = RemediationManifest(
            manifest_id=manifest_id,
            manifest_version="1.8",
            engine_version=__version__,
            model_name=plan.model_path.name,
            model_path=str(plan.model_path),
            created_at=created_at,
            actor="CLI",
            decision="ACCEPTED",
            baseline_scan_fingerprint=compute_file_sha256(plan.model_path / "model.bim") or "",
            before_score=validation_result.before_score,
            after_score=final_scan.overall_score,
            score_delta=round(final_scan.overall_score - validation_result.before_score, 1),
            backup_id=str(backup_dir) if backup_dir else None,
            applied_patches=[p.to_dict() for p in plan.applied_patches],
            rejected_patches=[p.to_dict() for p in plan.patches if p.state == PatchLifecycleState.REJECTED],
            skipped_findings=plan.skipped_findings,
            conflicts=[c.to_dict() for c in plan.conflicts],
            validation_result=validation_result.to_dict(),
            rejection_reasons=[],
            rollback_executed=False,
        )

        try:
            from pbiscan.remediation.store import RemediationAuditStore
            RemediationAuditStore.save_manifest(manifest, plan.model_path)
        except Exception:
            pass

        return True, manifest

    @classmethod
    def render_preview(
        cls,
        plan: RemediationPlan,
        validation_result: PatchValidationResult,
        output_format: str = "console",
    ) -> str:
        """Render formatted preview of the remediation plan and validation verdict."""
        if output_format.lower() == "json":
            out = {
                "model_path": str(plan.model_path),
                "validation": validation_result.to_dict(),
                "plan": plan.to_dict(),
            }
            return json.dumps(out, indent=2)

        lines: list[str] = []
        if output_format.lower() == "markdown":
            lines.append(f"## PBIP Sentinel Remediation Plan — `{plan.model_path.name}`\n")
            lines.append(f"**Validation Verdict**: `{'ACCEPTED' if validation_result.accepted else 'REJECTED'}`")
            lines.append(f"- **Baseline Score**: {validation_result.before_score:.1f}")
            lines.append(f"- **Predicted Score**: {validation_result.after_score:.1f} ({validation_result.score_delta:+.1f})")
            lines.append(f"- **Patches Planned**: {len(plan.actionable_patches)}\n")

            for i, p in enumerate(plan.patches, 1):
                lines.append(f"### Patch {i}: `{p.patch_id}` ({p.rule_id})")
                lines.append(f"- **Target File**: `{p.file_path.name}`")
                lines.append(f"- **Safety**: `{p.safety.value}` | **State**: `{p.state.value}`")
                lines.append(f"- **Rationale**: {p.rationale}")
                lines.append(f"- **Semantic Risk**: `{p.evidence.semantic_risk}`\n")
                lines.append("```diff")
                for c in p.chunks:
                    diff = difflib.unified_diff(
                        c.original_text.splitlines(keepends=True),
                        c.replacement_text.splitlines(keepends=True),
                        fromfile=f"a/{p.file_path.name}",
                        tofile=f"b/{p.file_path.name}",
                    )
                    lines.extend([d.rstrip("\n") for d in diff])
                lines.append("```\n")

            return "\n".join(lines)

        # ANSI Console preview
        lines.append("\n=======================================================")
        lines.append("        PBIP SENTINEL SAFE REMEDIATION ENGINE          ")
        lines.append("=======================================================")
        lines.append(f"  Model:            {plan.model_path.name}")
        lines.append(f"  Planned Patches:  {len(plan.actionable_patches)}")
        lines.append(f"  Skipped Findings: {len(plan.skipped_findings)}")
        lines.append(f"  Unsupported:      {len(plan.unsupported_findings)}")
        lines.append("-------------------------------------------------------")
        lines.append(f"  Validation:       {'ACCEPTED (Verified)' if validation_result.accepted else 'REJECTED'}")
        lines.append(f"  Score Impact:     {validation_result.before_score:.1f} -> {validation_result.after_score:.1f} ({validation_result.score_delta:+.1f})")
        lines.append("=======================================================\n")

        for i, p in enumerate(plan.patches, 1):
            lines.append(f"[{i}] {p.patch_id} — {p.rule_id} ({p.safety.value})")
            lines.append(f"    Target:  {p.file_path.name}")
            lines.append(f"    State:   {p.state.value}")
            lines.append(f"    Risk:    {p.evidence.semantic_risk}")
            lines.append(f"    Reason:  {p.rationale}")
            lines.append("    Diff:")
            for c in p.chunks:
                diff = difflib.unified_diff(
                    c.original_text.splitlines(keepends=True),
                    c.replacement_text.splitlines(keepends=True),
                    fromfile=f"a/{p.file_path.name}",
                    tofile=f"b/{p.file_path.name}",
                )
                for d in diff:
                    lines.append(f"      {d.rstrip()}")
            lines.append("")

        if validation_result.rejection_reasons:
            lines.append("  Rejection Reasons:")
            for r in validation_result.rejection_reasons:
                lines.append(f"    ✖ {r}")
            lines.append("")

        return "\n".join(lines)
