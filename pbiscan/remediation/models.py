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


def compute_scan_fingerprint(scan_res: Any) -> str:
    """Compute deterministic SHA-256 fingerprint for a ScanResult."""
    if not scan_res:
        return ""
    # Collect canonical finding signatures and scores
    findings_sig = [
        f"{issue.rule_id}::{issue.location or ''}::{issue.severity or ''}"
        for issue in sorted(getattr(scan_res, "issues", []), key=lambda x: (x.rule_id, x.location or ""))
    ]
    scores_dict = getattr(scan_res, "scores", {})
    payload = {
        "overall_score": getattr(scan_res, "overall_score", 0.0),
        "scores": scores_dict,
        "findings": findings_sig,
    }
    import json
    return compute_sha256(json.dumps(payload, sort_keys=True))


def generate_manifest_id(prefix: str = "MAN", seed: str = "") -> str:
    """Generate collision-proof unique manifest ID with 12-char SHA-256 entropy."""
    import uuid
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    entropy = f"{seed}_{uuid.uuid4().hex}_{datetime.utcnow().isoformat()}"
    suffix = compute_sha256(entropy)[:12].upper()
    return f"{prefix}-{timestamp}-{suffix}"


@dataclass
class RemediationManifest:
    """Permanent, immutable audit record of a remediation run."""
    manifest_id: str = field(default_factory=lambda: generate_manifest_id("MAN"))
    manifest_version: str = "1.8"
    engine_version: str = "1.8.0"
    model_name: str = ""
    model_path: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    actor: str = "CLI"                   # "CLI", "STUDIO", "CI", "AUTOMATION"
    decision: str = "ACCEPTED"           # "ACCEPTED", "REJECTED", "REVIEW_REQUIRED", "ROLLED_BACK", "DRY_RUN"
    baseline_scan_fingerprint: str = ""
    post_scan_fingerprint: str = ""
    before_score: float = 0.0
    after_score: float = 0.0
    score_delta: float = 0.0
    backup_id: Optional[str] = None
    backup_location: Optional[str] = None
    backup_hash: Optional[str] = None
    files_backed_up: list[str] = field(default_factory=list)
    applied_patches: list[dict] = field(default_factory=list)
    rejected_patches: list[dict] = field(default_factory=list)
    skipped_findings: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    validation_result: Optional[dict] = None
    rejection_reasons: list[str] = field(default_factory=list)
    rollback_executed: bool = False
    audit_saved: bool = True
    audit_error: Optional[str] = None
    baseline_scan_hash: str = ""
    patches: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.baseline_scan_fingerprint and self.baseline_scan_hash:
            self.baseline_scan_fingerprint = self.baseline_scan_hash
        if not self.baseline_scan_hash and self.baseline_scan_fingerprint:
            self.baseline_scan_hash = self.baseline_scan_fingerprint
        if not self.applied_patches and self.patches:
            self.applied_patches = self.patches
        if not self.patches and self.applied_patches:
            self.patches = self.applied_patches

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "manifest_version": self.manifest_version,
            "engine_version": self.engine_version,
            "model_name": self.model_name,
            "model_path": self.model_path,
            "created_at": self.created_at,
            "actor": self.actor,
            "decision": self.decision,
            "baseline_scan_fingerprint": self.baseline_scan_fingerprint,
            "post_scan_fingerprint": self.post_scan_fingerprint,
            "before_score": self.before_score,
            "after_score": self.after_score,
            "score_delta": self.score_delta,
            "backup_id": self.backup_id,
            "backup_location": self.backup_location,
            "backup_hash": self.backup_hash,
            "files_backed_up": self.files_backed_up,
            "applied_patches": self.applied_patches,
            "rejected_patches": self.rejected_patches,
            "skipped_findings": self.skipped_findings,
            "conflicts": self.conflicts,
            "validation_result": self.validation_result,
            "rejection_reasons": self.rejection_reasons,
            "rollback_executed": self.rollback_executed,
            "audit_saved": self.audit_saved,
            "audit_error": self.audit_error,
            "patches": self.applied_patches,
            "baseline_scan_hash": self.baseline_scan_fingerprint,
        }

    def to_json(self, indent: int = 2) -> str:
        import json
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RemediationManifest:
        return cls(
            manifest_id=data.get("manifest_id", ""),
            manifest_version=data.get("manifest_version", "1.8"),
            engine_version=data.get("engine_version", "1.8.0"),
            model_name=data.get("model_name", ""),
            model_path=data.get("model_path", ""),
            created_at=data.get("created_at", ""),
            actor=data.get("actor", "CLI"),
            decision=data.get("decision", "ACCEPTED"),
            baseline_scan_fingerprint=data.get("baseline_scan_fingerprint", data.get("baseline_scan_hash", "")),
            post_scan_fingerprint=data.get("post_scan_fingerprint", ""),
            before_score=float(data.get("before_score", 0.0)),
            after_score=float(data.get("after_score", 0.0)),
            score_delta=float(data.get("score_delta", 0.0)),
            backup_id=data.get("backup_id"),
            backup_location=data.get("backup_location"),
            backup_hash=data.get("backup_hash"),
            files_backed_up=data.get("files_backed_up", []),
            applied_patches=data.get("applied_patches", data.get("patches", [])),
            rejected_patches=data.get("rejected_patches", []),
            skipped_findings=data.get("skipped_findings", []),
            conflicts=data.get("conflicts", []),
            validation_result=data.get("validation_result"),
            rejection_reasons=data.get("rejection_reasons", []),
            rollback_executed=bool(data.get("rollback_executed", False)),
            audit_saved=bool(data.get("audit_saved", True)),
            audit_error=data.get("audit_error"),
            baseline_scan_hash=data.get("baseline_scan_hash", ""),
            patches=data.get("patches", []),
        )

    @classmethod
    def from_json(cls, json_str: str) -> RemediationManifest:
        import json
        return cls.from_dict(json.loads(json_str))
