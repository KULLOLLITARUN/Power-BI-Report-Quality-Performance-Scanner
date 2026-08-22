from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from pbiscan.service import ScanResult
from pbiscan.remediation.models import (
    Patch,
    PatchConflict,
    PatchLifecycleState,
    RemediationPlan,
)
from pbiscan.remediation.patchers.autodate import AutoDatePatcher
from pbiscan.remediation.patchers.base import BasePatcher
from pbiscan.remediation.patchers.datasource import DataSourcePatcher
from pbiscan.remediation.patchers.measure import MeasurePatcher
from pbiscan.remediation.patchers.relationship import RelationshipPatcher


class RemediationPlanner:
    """Orchestrates patchers, evaluates preconditions, and detects conflicts."""

    def __init__(self) -> None:
        self._patchers: Dict[str, BasePatcher] = {}
        self.register_patcher(RelationshipPatcher())
        self.register_patcher(MeasurePatcher())
        self.register_patcher(DataSourcePatcher())
        self.register_patcher(AutoDatePatcher())

    def register_patcher(self, patcher: BasePatcher) -> None:
        """Register a rule-specific patcher."""
        self._patchers[patcher.rule_id] = patcher

    def plan(
        self,
        model_path: Path,
        scan_result: ScanResult,
        rule_filter: Optional[str] = None,
    ) -> RemediationPlan:
        """Generate full remediation plan for findings in scan_result."""
        patches: list[Patch] = []
        conflicts: list[PatchConflict] = []
        skipped_findings: list[dict] = []
        unsupported_findings: list[dict] = []

        report = scan_result.report
        if report is None:
            return RemediationPlan(
                model_path=model_path,
                created_at=datetime.now(timezone.utc).isoformat(),
                patches=[],
                conflicts=[],
                skipped_findings=[{"reason": "ScanResult contains no canonical report object"}],
                unsupported_findings=[],
            )

        issues = scan_result.unsuppressed_issues

        for issue in issues:
            rule_id = issue.rule_id
            if rule_filter and rule_id.upper() != rule_filter.upper():
                continue

            patcher = self._patchers.get(rule_id)
            if not patcher:
                unsupported_findings.append({
                    "issue_key": f"{rule_id}::{issue.location or ''}",
                    "rule_id": rule_id,
                    "location": issue.location,
                    "reason": f"No certified remediation strategy available for rule {rule_id}",
                })
                continue

            # Phase 1: Analyze & gather evidence.
            # A crash analyzing/patching ONE finding (e.g. a file with a byte that
            # isn't valid UTF-8) must not abort remediation for every OTHER finding
            # in the project — skip just this finding and keep going.
            try:
                evidence = patcher.analyze(issue, report, model_path)
            except Exception as exc:
                skipped_findings.append({
                    "issue_key": f"{rule_id}::{issue.location or ''}",
                    "rule_id": rule_id,
                    "location": issue.location,
                    "reason": f"Patcher analysis crashed: {exc}",
                })
                continue

            if evidence.violated_preconditions:
                skipped_findings.append({
                    "issue_key": f"{rule_id}::{issue.location or ''}",
                    "rule_id": rule_id,
                    "location": issue.location,
                    "violated_preconditions": evidence.violated_preconditions,
                    "satisfied_preconditions": evidence.satisfied_preconditions,
                })
                continue

            # Phase 2: Generate patch(es)
            try:
                generated = patcher.generate_patches(issue, evidence, model_path)
            except Exception as exc:
                skipped_findings.append({
                    "issue_key": f"{rule_id}::{issue.location or ''}",
                    "rule_id": rule_id,
                    "location": issue.location,
                    "reason": f"Patch generation crashed: {exc}",
                })
                continue

            if generated:
                patches.extend(generated)
            else:
                skipped_findings.append({
                    "issue_key": f"{rule_id}::{issue.location or ''}",
                    "rule_id": rule_id,
                    "location": issue.location,
                    "reason": "Patcher was unable to generate valid replacement chunk(s)",
                })

        # Conflict detection: check for overlapping line ranges targeting the same file
        patches_by_file: Dict[Path, list[Patch]] = {}
        for p in patches:
            patches_by_file.setdefault(p.file_path, []).append(p)

        for file_path, file_patches in patches_by_file.items():
            if len(file_patches) > 1:
                # Check overlapping chunks
                for i in range(len(file_patches)):
                    for j in range(i + 1, len(file_patches)):
                        p1, p2 = file_patches[i], file_patches[j]
                        for c1 in p1.chunks:
                            for c2 in p2.chunks:
                                if max(c1.start_line, c2.start_line) <= min(c1.end_line, c2.end_line):
                                    p1.state = PatchLifecycleState.CONFLICT
                                    p2.state = PatchLifecycleState.CONFLICT
                                    conflicts.append(PatchConflict(
                                        file_path=file_path,
                                        patch_ids=[p1.patch_id, p2.patch_id],
                                        reason=(
                                            f"Overlapping line ranges [{c1.start_line}:{c1.end_line}] "
                                            f"and [{c2.start_line}:{c2.end_line}] in {file_path.name}"
                                        ),
                                    ))

        return RemediationPlan(
            model_path=model_path,
            patches=patches,
            conflicts=conflicts,
            skipped_findings=skipped_findings,
            unsupported_findings=unsupported_findings,
        )
