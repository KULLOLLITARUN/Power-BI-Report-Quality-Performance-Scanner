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

    @abstractmethod
    def analyze(self, issue: AuditIssue, report: CanonicalReport, model_dir: Path) -> PatchEvidence:
        """Phase 1: Examine topology and dependencies; produce auditable PatchEvidence."""
        pass

    @abstractmethod
    def generate_patch(
        self,
        issue: AuditIssue,
        evidence: PatchEvidence,
        model_dir: Path,
    ) -> Optional[Patch]:
        """Phase 2: Generate structured patch chunks with hash anchoring only if preconditions satisfied."""
        pass

