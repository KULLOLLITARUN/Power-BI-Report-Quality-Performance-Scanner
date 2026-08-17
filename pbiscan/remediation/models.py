"""Data models and formal contracts for PBIP Sentinel Safe Remediation Engine."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class PatchLifecycleState(str, Enum):
    """Lifecycle state of a candidate remediation patch."""
    PLANNED = "PLANNED"
    VALIDATED = "VALIDATED"
    SKIPPED = "SKIPPED"
    UNSUPPORTED = "UNSUPPORTED"
    CONFLICT = "CONFLICT"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"


class RemediationSafety(str, Enum):
    """Safety classification for remediation."""
    SAFE_AUTO = "SAFE_AUTO"              # Reserved for certified non-breaking structural fixes
    REVIEW_REQUIRED = "REVIEW_REQUIRED"  # Deterministic patch available; semantic review required
    UNSUPPORTED = "UNSUPPORTED"          # Advisory explanation only


@dataclass(frozen=True)
class PatchEvidence:
    """Auditable evidence justifying a proposed remediation patch."""
    rule_id: str
    finding_key: str
    confidence: float
    preconditions: list[str] = field(default_factory=list)
    satisfied_preconditions: list[str] = field(default_factory=list)
    violated_preconditions: list[str] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    affected_objects: list[str] = field(default_factory=list)
    dependency_count: int = 0
    semantic_risk: str = "MEDIUM"        # "LOW", "MEDIUM", "HIGH"
    expected_resolution: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_sha256(text: str) -> str:
    """Compute SHA-256 hash of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file's text contents."""
    if not file_path.exists():
        return ""
    return compute_sha256(file_path.read_text(encoding="utf-8"))


@dataclass
class PatchChunk:
    """Single contiguous replacement chunk with line hash anchoring."""
    start_line: int                      # 1-indexed start line in target file
    end_line: int                        # 1-indexed end line (inclusive)
    original_text: str                   # Exact original text block
    original_text_hash: str              # SHA-256 of original_text (chunk stale protection)
    replacement_text: str                # Drop-in replacement text

    @classmethod
    def create(cls, start_line: int, end_line: int, original_text: str, replacement_text: str) -> PatchChunk:
        return cls(
            start_line=start_line,
            end_line=end_line,
            original_text=original_text,
            original_text_hash=compute_sha256(original_text),
            replacement_text=replacement_text,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Patch:
    """Structured remediation patch targeting a specific file."""
    patch_id: str                        # Deterministic hash: REM-<RULE>-<TARGET>-<HASH>
    rule_id: str
    file_path: Path
    source_hash: str                     # SHA-256 of whole file before patch (file stale protection)
    safety: RemediationSafety
    state: PatchLifecycleState
    evidence: PatchEvidence
    chunks: list[PatchChunk]
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "rule_id": self.rule_id,
            "file_path": str(self.file_path),
            "source_hash": self.source_hash,
            "safety": self.safety.value,
            "state": self.state.value,
            "evidence": self.evidence.to_dict(),
            "chunks": [c.to_dict() for c in self.chunks],
            "rationale": self.rationale,
        }


@dataclass
class PatchConflict:
    """Details of a conflict between overlapping patches."""
    file_path: Path
    patch_ids: list[str]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": str(self.file_path),
            "patch_ids": self.patch_ids,
            "reason": self.reason,
        }


@dataclass
class PatchValidationResult:
    """Authoritative verdict from temporary sandbox Before -> After scan comparison."""
    accepted: bool
    rejection_reasons: list[str]
    finding_resolved: bool
    resolved_count: int
    expected_resolved_count: int
    score_delta: float
    new_high_critical_count: int
    new_findings: list[dict]
    resolved_findings: list[dict]
    before_score: float
    after_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepted": self.accepted,
            "rejection_reasons": self.rejection_reasons,
            "finding_resolved": self.finding_resolved,
            "resolved_count": self.resolved_count,
            "expected_resolved_count": self.expected_resolved_count,
            "score_delta": self.score_delta,
            "new_high_critical_count": self.new_high_critical_count,
            "new_findings": self.new_findings,
            "resolved_findings": self.resolved_findings,
            "before_score": self.before_score,
            "after_score": self.after_score,
        }


@dataclass
class RemediationPlan:
    """Full remediation plan for a scanned PBIP project."""
    model_path: Path
    patches: list[Patch]
    conflicts: list[PatchConflict] = field(default_factory=list)
    skipped_findings: list[dict] = field(default_factory=list)
    unsupported_findings: list[dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def actionable_patches(self) -> list[Patch]:
        return [p for p in self.patches if p.state in (PatchLifecycleState.PLANNED, PatchLifecycleState.VALIDATED, PatchLifecycleState.APPLIED)]

    @property
    def applied_patches(self) -> list[Patch]:
        return [p for p in self.patches if p.state == PatchLifecycleState.APPLIED]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_path": str(self.model_path),
            "created_at": self.created_at,
            "patches": [p.to_dict() for p in self.patches],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "skipped_findings": self.skipped_findings,
            "unsupported_findings": self.unsupported_findings,
        }


@dataclass
class RemediationManifest:
    """Permanent audit record of a remediation run."""
    engine_version: str
    model_name: str
    baseline_scan_hash: str
    created_at: str
    decision: str                        # "ACCEPTED", "REJECTED", "REVIEW_REQUIRED"
    before_score: float
    after_score: float
    score_delta: float
    patches: list[dict]
    conflicts: list[dict]
    rejection_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
