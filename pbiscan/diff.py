"""pbiscan Historical Scan Diffing & CI/CD Drift Engine.

Compares two scan results (PBIP projects or pre-computed JSON scan artifacts),
tracks score drift across categories, calculates finding transitions
(NEW, RESOLVED, PERSISTENT, MODIFIED), and evaluates CI/CD quality gate policies.

Guarantees canonical integrity:
All PBIP scans delegate strictly through ScanService.execute_scan().
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

from pbiscan.engine.issue import AuditIssue
from pbiscan.service import ScanResult, ScanService

SEVERITY_ORDER: list[str] = ["CRITICAL", "HIGH", "MEDIUM", "WARNING", "LOW", "ADVISORY"]
SEVERITY_WEIGHTS: dict[str, int] = {
    "CRITICAL": 6,
    "HIGH": 5,
    "MEDIUM": 4,
    "WARNING": 3,
    "LOW": 2,
    "ADVISORY": 1,
}


def normalize_location(location: Optional[str]) -> str:
    """Normalize location string for stable identity matching across scans."""
    if not location:
        return ""
    # Normalize slashes, whitespace, and bracket formatting
    loc = location.strip().lower()
    loc = " ".join(loc.split())
    return loc


def compute_finding_identity(rule_id: str, location: Optional[str]) -> str:
    """Deterministic canonical finding identity key."""
    norm_loc = normalize_location(location)
    return f"{rule_id.strip().upper()}::{norm_loc}"


@dataclass
class FindingTransition:
    """Represents the lifecycle transition of a single finding between scans."""

    state: str  # "NEW", "RESOLVED", "PERSISTENT", "MODIFIED"
    finding_id: str
    rule_id: str
    category: str
    severity: str
    baseline_severity: Optional[str]
    title: str
    location: Optional[str]
    evidence: str
    baseline_finding: Optional[AuditIssue] = None
    current_finding: Optional[AuditIssue] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "finding_id": self.finding_id,
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "baseline_severity": self.baseline_severity,
            "title": self.title,
            "location": self.location,
            "evidence": self.evidence,
        }


@dataclass
class ScoreDrift:
    """Tracks overall and per-category score drift between scans."""

    baseline_score: float
    current_score: float
    overall_delta: float
    direction: str  # "IMPROVED", "DEGRADED", "UNCHANGED"
    category_deltas: dict[str, int | float]
    baseline_categories: dict[str, int]
    current_categories: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_score": self.baseline_score,
            "current_score": self.current_score,
            "overall_delta": self.overall_delta,
            "direction": self.direction,
            "category_deltas": self.category_deltas,
            "baseline_categories": self.baseline_categories,
            "current_categories": self.current_categories,
        }


@dataclass
class QualityGatePolicy:
    """Configurable quality gate policy for CI/CD enforcement."""

    fail_on_regression: bool = False
    max_score_drop: Optional[float] = None
    fail_on_new: Optional[str] = None  # e.g. "HIGH", "CRITICAL"
    fail_on_category_regression: Optional[str] = None  # e.g. "model", "dax", "report"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fail_on_regression": self.fail_on_regression,
            "max_score_drop": self.max_score_drop,
            "fail_on_new": self.fail_on_new,
            "fail_on_category_regression": self.fail_on_category_regression,
        }


@dataclass
class QualityGateVerdict:
    """Decision and explanation emitted by the quality gate policy evaluator."""

    passed: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "reasons": self.reasons,
        }


@dataclass
class DiffResult:
    """Canonical diff result comparing baseline and current scans."""

    baseline_name: str
    current_name: str
    score_drift: ScoreDrift
    transitions: list[FindingTransition]
    verdict: QualityGateVerdict
    policy: QualityGatePolicy
    baseline_findings_count: int
    current_findings_count: int

    @property
    def new_findings(self) -> list[FindingTransition]:
        return [t for t in self.transitions if t.state == "NEW"]

    @property
    def resolved_findings(self) -> list[FindingTransition]:
        return [t for t in self.transitions if t.state == "RESOLVED"]

    @property
    def persistent_findings(self) -> list[FindingTransition]:
        return [t for t in self.transitions if t.state == "PERSISTENT"]

    @property
    def modified_findings(self) -> list[FindingTransition]:
        return [t for t in self.transitions if t.state == "MODIFIED"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_name": self.baseline_name,
            "current_name": self.current_name,
            "score_drift": self.score_drift.to_dict(),
            "transitions": [t.to_dict() for t in self.transitions],
            "counts": {
                "baseline_total": self.baseline_findings_count,
                "current_total": self.current_findings_count,
                "new": len(self.new_findings),
                "resolved": len(self.resolved_findings),
                "persistent": len(self.persistent_findings),
                "modified": len(self.modified_findings),
            },
            "quality_gate": self.verdict.to_dict(),
            "policy": self.policy.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class DiffService:
    """Canonical diffing service for PBIP Sentinel."""

    @classmethod
    def compare(
        cls,
        baseline: Union[ScanResult, str, Path, dict],
        current: Union[ScanResult, str, Path, dict],
        policy: Optional[QualityGatePolicy] = None,
        config_path: Optional[str | Path] = None,
        config: Optional[dict] = None,
    ) -> DiffResult:
        """Compare baseline and current scans, calculate drift, and evaluate quality gate."""
        if policy is None:
            policy = QualityGatePolicy()

        base_res = cls._resolve_scan(baseline, config_path=config_path, config=config)
        curr_res = cls._resolve_scan(current, config_path=config_path, config=config)

        # 1. Calculate Score Drift
        score_drift = cls._compute_score_drift(base_res, curr_res)

        # 2. Compute Finding Transitions
        transitions = cls._compute_transitions(base_res, curr_res)

        # 3. Evaluate Quality Gate Policy
        verdict = cls._evaluate_quality_gate(score_drift, transitions, policy)

        return DiffResult(
            baseline_name=base_res.report_name,
            current_name=curr_res.report_name,
            score_drift=score_drift,
            transitions=transitions,
            verdict=verdict,
            policy=policy,
            baseline_findings_count=len(base_res.unsuppressed_issues),
            current_findings_count=len(curr_res.unsuppressed_issues),
        )

    @classmethod
    def _resolve_scan(
        cls,
        target: Union[ScanResult, str, Path, dict],
        config_path: Optional[str | Path] = None,
        config: Optional[dict] = None,
    ) -> ScanResult:
        """Resolve any target (ScanResult, JSON file, dict, or PBIP directory) into a ScanResult."""
        if isinstance(target, ScanResult):
            return target

        if isinstance(target, dict):
            return cls._from_dict(target)

        target_path = Path(target)
        if not target_path.exists():
            raise FileNotFoundError(f"Input path does not exist: {target}")

        if target_path.is_file() and target_path.suffix.lower() == ".json":
            # Load pre-computed JSON scan artifact
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid or malformed JSON artifact in {target_path}: {exc}") from exc

            if not isinstance(data, dict):
                raise ValueError(f"Invalid scan artifact: root JSON in {target_path} must be a dictionary object")

            return cls._from_dict(data, source_path=str(target_path))

        # PBIP directory or .pbip file -> execute canonical ScanService
        return ScanService.execute_scan(target_path, config_path=config_path, config=config)

    @classmethod
    def _from_dict(cls, data: dict, source_path: str = "") -> ScanResult:
        """Construct a ScanResult from serialized JSON data."""
        if not isinstance(data, dict):
            raise ValueError("Scan artifact data must be a dictionary object")

        report_name = data.get("report_name", "Report")
        scores = data.get("scores", {"overall": 100.0, "category_scores": {}})

        issues = []
        raw_findings = data.get("findings", [])
        for item in raw_findings:
            issues.append(
                AuditIssue(
                    rule_id=item.get("rule_id", "UNKNOWN"),
                    category=item.get("category", "model"),
                    severity=item.get("severity", "WARNING"),
                    title=item.get("title", ""),
                    issue=item.get("issue", ""),
                    evidence=item.get("evidence", ""),
                    impact=item.get("impact", ""),
                    recommendation=item.get("recommendation", ""),
                    confidence=item.get("confidence", 100),
                    location=item.get("location"),
                    suppressed=item.get("suppressed", False),
                    suppression_reason=item.get("suppression_reason"),
                )
            )

        return ScanResult(
            report_name=report_name,
            source_path=source_path or data.get("source_path", report_name),
            report=None,  # Not needed for diffing pre-computed findings
            issues=issues,
            scores=scores,
            config=data.get("config", {}),
            scanner_version=data.get("scanner_version", "1.4.0"),
            warnings=data.get("warnings", []),
        )

    @classmethod
    def _compute_score_drift(cls, baseline: ScanResult, current: ScanResult) -> ScoreDrift:
        """Calculate overall and category score deltas."""
        base_score = float(baseline.overall_score)
        curr_score = float(current.overall_score)
        overall_delta = round(curr_score - base_score, 1)

        if overall_delta > 0:
            direction = "IMPROVED"
        elif overall_delta < 0:
            direction = "DEGRADED"
        else:
            direction = "UNCHANGED"

        base_cats = baseline.category_scores or {}
        curr_cats = current.category_scores or {}

        all_cats = set(base_cats.keys()) | set(curr_cats.keys()) | {"model", "dax", "report"}
        cat_deltas: dict[str, int | float] = {}

        for cat in sorted(all_cats):
            b_val = base_cats.get(cat, 100)
            c_val = curr_cats.get(cat, 100)
            cat_deltas[cat] = round(c_val - b_val, 1)

        return ScoreDrift(
            baseline_score=base_score,
            current_score=curr_score,
            overall_delta=overall_delta,
            direction=direction,
            category_deltas=cat_deltas,
            baseline_categories=base_cats,
            current_categories=curr_cats,
        )

    @classmethod
    def _compute_transitions(cls, baseline: ScanResult, current: ScanResult) -> list[FindingTransition]:
        """Compute state transitions for all unsuppressed findings."""
        base_issues = baseline.unsuppressed_issues
        curr_issues = current.unsuppressed_issues

        base_map: dict[str, AuditIssue] = {}
        for issue in base_issues:
            ident = compute_finding_identity(issue.rule_id, issue.location)
            base_map[ident] = issue

        curr_map: dict[str, AuditIssue] = {}
        for issue in curr_issues:
            ident = compute_finding_identity(issue.rule_id, issue.location)
            curr_map[ident] = issue

        transitions: list[FindingTransition] = []

        # 1. Process all findings in current
        for ident, curr_iss in curr_map.items():
            if ident in base_map:
                base_iss = base_map[ident]
                if curr_iss.severity != base_iss.severity:
                    transitions.append(
                        FindingTransition(
                            state="MODIFIED",
                            finding_id=ident,
                            rule_id=curr_iss.rule_id,
                            category=curr_iss.category,
                            severity=curr_iss.severity,
                            baseline_severity=base_iss.severity,
                            title=curr_iss.title,
                            location=curr_iss.location,
                            evidence=curr_iss.evidence,
                            baseline_finding=base_iss,
                            current_finding=curr_iss,
                        )
                    )
                else:
                    transitions.append(
                        FindingTransition(
                            state="PERSISTENT",
                            finding_id=ident,
                            rule_id=curr_iss.rule_id,
                            category=curr_iss.category,
                            severity=curr_iss.severity,
                            baseline_severity=base_iss.severity,
                            title=curr_iss.title,
                            location=curr_iss.location,
                            evidence=curr_iss.evidence,
                            baseline_finding=base_iss,
                            current_finding=curr_iss,
                        )
                    )
            else:
                transitions.append(
                    FindingTransition(
                        state="NEW",
                        finding_id=ident,
                        rule_id=curr_iss.rule_id,
                        category=curr_iss.category,
                        severity=curr_iss.severity,
                        baseline_severity=None,
                        title=curr_iss.title,
                        location=curr_iss.location,
                        evidence=curr_iss.evidence,
                        baseline_finding=None,
                        current_finding=curr_iss,
                    )
                )

        # 2. Identify resolved findings (in baseline but not current)
        for ident, base_iss in base_map.items():
            if ident not in curr_map:
                transitions.append(
                    FindingTransition(
                        state="RESOLVED",
                        finding_id=ident,
                        rule_id=base_iss.rule_id,
                        category=base_iss.category,
                        severity=base_iss.severity,
                        baseline_severity=base_iss.severity,
                        title=base_iss.title,
                        location=base_iss.location,
                        evidence=base_iss.evidence,
                        baseline_finding=base_iss,
                        current_finding=None,
                    )
                )

        # Sort transitions: NEW -> MODIFIED -> RESOLVED -> PERSISTENT, then severity
        def sort_key(t: FindingTransition) -> tuple[int, int, str]:
            state_priority = {"NEW": 0, "MODIFIED": 1, "RESOLVED": 2, "PERSISTENT": 3}
            sev_weight = -SEVERITY_WEIGHTS.get(t.severity.upper(), 0)
            return (state_priority.get(t.state, 99), sev_weight, t.finding_id)

        transitions.sort(key=sort_key)
        return transitions

    @classmethod
    def _evaluate_quality_gate(
        cls,
        drift: ScoreDrift,
        transitions: list[FindingTransition],
        policy: QualityGatePolicy,
    ) -> QualityGateVerdict:
        """Evaluate quality gate policy against drift and transitions."""
        reasons: list[str] = []

        # 1. Check overall regression
        if policy.fail_on_regression and drift.overall_delta < 0:
            reasons.append(f"Overall health score regressed by {abs(drift.overall_delta):.1f} points ({drift.baseline_score:.1f} -> {drift.current_score:.1f})")

        # 2. Check max score drop
        if policy.max_score_drop is not None:
            if drift.overall_delta < 0 and abs(drift.overall_delta) > policy.max_score_drop:
                reasons.append(
                    f"Score drop of {abs(drift.overall_delta):.1f} points exceeds maximum allowed drop of {policy.max_score_drop:.1f}"
                )

        # 3. Check new findings by severity threshold
        if policy.fail_on_new:
            threshold_weight = SEVERITY_WEIGHTS.get(policy.fail_on_new.upper(), 0)
            new_violations = []
            for t in transitions:
                if t.state == "NEW":
                    sev_wt = SEVERITY_WEIGHTS.get(t.severity.upper(), 0)
                    if sev_wt >= threshold_weight:
                        new_violations.append(f"[{t.severity}] {t.rule_id} ({t.location or 'Global'})")

            if new_violations:
                count = len(new_violations)
                plural = "finding" if count == 1 else "findings"
                reasons.append(
                    f"Introduced {count} new {policy.fail_on_new.upper()}+ {plural}: {', '.join(new_violations[:3])}"
                    + (f" and {count - 3} more" if count > 3 else "")
                )

        # 4. Check category regression
        if policy.fail_on_category_regression:
            cat = policy.fail_on_category_regression.lower()
            cat_delta = drift.category_deltas.get(cat, 0)
            if cat_delta < 0:
                reasons.append(f"Category '{cat}' regressed by {abs(cat_delta)} points")

        passed = len(reasons) == 0
        return QualityGateVerdict(passed=passed, reasons=reasons)
