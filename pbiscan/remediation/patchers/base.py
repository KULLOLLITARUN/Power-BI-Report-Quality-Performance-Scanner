from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from pbiscan.canonical.model import CanonicalReport
from pbiscan.engine.issue import AuditIssue
from pbiscan.remediation.models import Patch, PatchEvidence


class BasePatcher(ABC):
    """Abstract base class enforcing the 2-phase patcher protocol."""

    rule_id: str

    def begin_plan(self) -> None:
        """Called before a planner runs this patcher over every finding. Files do not change
        until the plan is done, so a patcher may cache what it reads until end_plan()."""

    def end_plan(self) -> None:
        """Called when the plan is finished. Drop anything cached in begin_plan()."""

    @abstractmethod
    def analyze(self, issue: AuditIssue, report: CanonicalReport, model_dir: Path) -> PatchEvidence:
        """Phase 1: Examine topology and dependencies; produce auditable PatchEvidence."""
        pass

    def generate_patch(
        self,
        issue: AuditIssue,
        evidence: PatchEvidence,
        model_dir: Path,
    ) -> Optional[Patch]:
        """Phase 2: Generate structured patch chunks with hash anchoring only if preconditions satisfied."""
        return None

    def generate_patches(
        self,
        issue: AuditIssue,
        evidence: PatchEvidence,
        model_dir: Path,
    ) -> list[Patch]:
        """Generate one or more structured patches for the finding."""
        p = self.generate_patch(issue, evidence, model_dir)
        return [p] if p else []

