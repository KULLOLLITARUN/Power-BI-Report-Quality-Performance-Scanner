from pathlib import Path
from typing import Dict, List, Optional

from pbiscan.canonical.model import CanonicalReport
from pbiscan.service import ScanResult
from pbiscan.remediation.models import (
    Patch,
    PatchConflict,
    PatchLifecycleState,
    RemediationPlan,
)
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

            # Phase 1: Analyze & gather evidence
            evidence = patcher.analyze(issue, report, model_path)
            
            if evidence.violated_preconditions:
                skipped_findings.append({
                    "issue_key": f"{rule_id}::{issue.location or ''}",
                    "rule_id": rule_id,
                    "location": issue.location,
                    "violated_preconditions": evidence.violated_preconditions,
                    "satisfied_preconditions": evidence.satisfied_preconditions,
                })
                continue

            # Phase 2: Generate patch
            patch = patcher.generate_patch(issue, evidence, model_path)
            if patch:
                patches.append(patch)
            else:
                skipped_findings.append({
                    "issue_key": f"{rule_id}::{issue.location or ''}",
                    "rule_id": rule_id,
                    "location": issue.location,
                    "reason": "Patcher was unable to generate a valid replacement chunk",
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
