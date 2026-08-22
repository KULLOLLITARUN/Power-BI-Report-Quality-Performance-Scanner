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
    compute_scan_fingerprint,
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
        original_scan: Optional[ScanResult] = None,
    ) -> Tuple[bool, RemediationManifest]:
        """Phase 4: Apply validated patches to real workspace with transactional rollback."""
        actionable = plan.actionable_patches
        created_at = datetime.utcnow().isoformat()
        
        # 0. Capture authoritative baseline scan fingerprint
        if original_scan is None:
            try:
                original_scan = ScanService.execute_scan(plan.model_path, config_path=config_path)
            except Exception:
                original_scan = None
        baseline_fp = compute_scan_fingerprint(original_scan) if original_scan else ""

        # 1. Validation gate check
        if not validation_result.accepted:
            manifest = RemediationManifest(
                engine_version=__version__,
                model_name=plan.model_path.name,
                model_path=str(plan.model_path),
                created_at=created_at,
                decision="REJECTED",
                baseline_scan_fingerprint=baseline_fp,
                before_score=validation_result.before_score,
                after_score=validation_result.after_score,
                score_delta=validation_result.score_delta,
                patches=[p.to_dict() for p in plan.patches],
                conflicts=[c.to_dict() for c in plan.conflicts],
                rejection_reasons=validation_result.rejection_reasons,
            )
            try:
                from pbiscan.remediation.store import RemediationAuditStore
                RemediationAuditStore.save_manifest(manifest, plan.model_path)
            except Exception:
                pass
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
                    model_path=str(plan.model_path),
                    baseline_scan_fingerprint=baseline_fp,
                    created_at=created_at,
                    decision="REJECTED",
                    before_score=validation_result.before_score,
                    after_score=validation_result.after_score,
                    score_delta=0.0,
                    patches=[p.to_dict() for p in plan.patches],
                    conflicts=[c.to_dict() for c in plan.conflicts],
                    rejection_reasons=[reason],
                )
                try:
                    from pbiscan.remediation.store import RemediationAuditStore
                    RemediationAuditStore.save_manifest(manifest, plan.model_path)
                except Exception:
                    pass
                return False, manifest

        # 3. Create transactional backup
        backup_dir = None
        backup_meta = {}
        if backup:
            backup_dir = BackupManager.create_backup(plan.model_path)
            backup_meta = BackupManager.get_backup_metadata(backup_dir)

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
                model_path=str(plan.model_path),
                baseline_scan_fingerprint=baseline_fp,
                created_at=created_at,
                decision="ROLLED_BACK",
                before_score=validation_result.before_score,
                after_score=validation_result.after_score,
                score_delta=0.0,
                backup_id=backup_meta.get("backup_id"),
                backup_location=backup_meta.get("backup_location"),
                backup_hash=backup_meta.get("backup_hash"),
                files_backed_up=backup_meta.get("files_backed_up", []),
                rollback_executed=True,
                patches=[p.to_dict() for p in plan.patches],
                conflicts=[c.to_dict() for c in plan.conflicts],
                rejection_reasons=[f"Disk write error: {e}" for e in apply_errors],
            )
            try:
                from pbiscan.remediation.store import RemediationAuditStore
                RemediationAuditStore.save_manifest(manifest, plan.model_path)
            except Exception:
                pass
            return False, manifest

        # 5. Execute final verification scan on real workspace
        try:
            final_scan = ScanService.execute_scan(plan.model_path, config_path=config_path)
            if final_scan.overall_score < validation_result.before_score:
                raise ValueError(
                    f"Final scan score ({final_scan.overall_score:.1f}) regressed below baseline ({validation_result.before_score:.1f})"
                )
            final_fp = compute_scan_fingerprint(final_scan)
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
                model_path=str(plan.model_path),
                baseline_scan_fingerprint=baseline_fp,
                created_at=created_at,
                decision="ROLLED_BACK",
                before_score=validation_result.before_score,
                after_score=0.0,
                score_delta=0.0,
                backup_id=backup_meta.get("backup_id"),
                backup_location=backup_meta.get("backup_location"),
                backup_hash=backup_meta.get("backup_hash"),
                files_backed_up=backup_meta.get("files_backed_up", []),
                rollback_executed=True,
                patches=[p.to_dict() for p in plan.patches],
                conflicts=[c.to_dict() for c in plan.conflicts],
                rejection_reasons=[f"Final verification failed, rolled back to backup: {exc}"],
            )
            try:
                from pbiscan.remediation.store import RemediationAuditStore
                RemediationAuditStore.save_manifest(manifest, plan.model_path)
            except Exception:
                pass
            return False, manifest

        # 6. Mark patches as APPLIED and assemble manifest
        for p in actionable:
            p.state = PatchLifecycleState.APPLIED

        manifest = RemediationManifest(
            engine_version=__version__,
            model_name=plan.model_path.name,
            model_path=str(plan.model_path),
            created_at=created_at,
            actor="CLI",
            decision="ACCEPTED",
            baseline_scan_fingerprint=baseline_fp,
            post_scan_fingerprint=final_fp,
            before_score=validation_result.before_score,
            after_score=final_scan.overall_score,
            score_delta=round(final_scan.overall_score - validation_result.before_score, 1),
            backup_id=backup_meta.get("backup_id"),
            backup_location=backup_meta.get("backup_location"),
            backup_hash=backup_meta.get("backup_hash"),
            files_backed_up=backup_meta.get("files_backed_up", []),
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
        except Exception as audit_err:
            if backup_dir:
                BackupManager.restore_backup(backup_dir, plan.model_path)
            manifest.decision = "ROLLED_BACK"
            manifest.rollback_executed = True
            manifest.audit_saved = False
            manifest.audit_error = str(audit_err)
            manifest.rejection_reasons.append(f"Audit persistence failure: {audit_err}")
            return False, manifest

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

        if output_format.lower() == "markdown":
            from pbiscan.render.remediation_markdown import RemediationMarkdownRenderer
            return RemediationMarkdownRenderer.render(plan, validation_result)

        # ANSI Console preview
        lines: list[str] = []
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
