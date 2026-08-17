"""Unit tests for RemediationAuditStore and RemediationManifest operations."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from pbiscan.canonical.model import CanonicalReport
from pbiscan.engine.issue import AuditIssue
from pbiscan.remediation.models import (
    RemediationManifest,
    compute_scan_fingerprint,
)
from pbiscan.remediation.store import RemediationAuditStore
from pbiscan.remediation.engine import RemediationEngine
from pbiscan.service import ScanResult, ScanService

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


class TestRemediationManifestAndFingerprint:
    def test_manifest_serialization_round_trip(self):
        manifest = RemediationManifest(
            manifest_id="MAN-20260818-120000-A1B2C3",
            manifest_version="1.8",
            engine_version="1.8.0",
            model_name="SalesModel",
            model_path="/path/to/SalesModel.pbip",
            actor="CLI",
            decision="ACCEPTED",
            baseline_scan_fingerprint="abc123hash",
            post_scan_fingerprint="def456hash",
            before_score=82.5,
            after_score=85.0,
            score_delta=2.5,
            backup_id="/path/to/backup.zip",
            applied_patches=[{"patch_id": "REM-1", "rule_id": "MODEL_BIDIRECTIONAL"}],
            rejected_patches=[],
            skipped_findings=[],
            conflicts=[],
            validation_result={"accepted": True, "resolved_count": 1},
            rejection_reasons=[],
            rollback_executed=False,
        )

        json_str = manifest.to_json()
        assert "MAN-20260818-120000-A1B2C3" in json_str
        assert "82.5" in json_str

        restored = RemediationManifest.from_json(json_str)
        assert restored.manifest_id == manifest.manifest_id
        assert restored.manifest_version == "1.8"
        assert restored.model_name == "SalesModel"
        assert restored.before_score == 82.5
        assert restored.after_score == 85.0
        assert restored.score_delta == 2.5
        assert len(restored.applied_patches) == 1
        assert restored.applied_patches[0]["patch_id"] == "REM-1"
        assert restored.decision == "ACCEPTED"

    def test_scan_fingerprint_determinism(self):
        issue1 = AuditIssue(
            rule_id="MODEL_BIDIRECTIONAL",
            category="model",
            severity="MEDIUM",
            title="Bi-directional",
            issue="Bi-directional",
            evidence="Relationship is bothDirections",
            impact="None",
            recommendation="Change",
            confidence=95,
            location="Relationship: Sales -> Store",
        )
        issue2 = AuditIssue(
            rule_id="DAX_UNUSED_MEASURE",
            category="dax",
            severity="ADVISORY",
            title="Unused measure",
            issue="Unused measure",
            evidence="Measure 'UnusedKPI'",
            impact="None",
            recommendation="Delete",
            confidence=95,
            location="Measure: UnusedKPI",
        )

        scan_a = ScanResult(
            report_name="test",
            source_path="test",
            report=CanonicalReport(),
            issues=[issue1, issue2],
            scores={"model": 90.0, "dax": 95.0, "overall": 92.5},
            config={},
        )
        scan_b = ScanResult(
            report_name="test",
            source_path="test",
            report=CanonicalReport(),
            issues=[issue2, issue1],  # different ordering
            scores={"model": 90.0, "dax": 95.0, "overall": 92.5},
            config={},
        )

        fp_a = compute_scan_fingerprint(scan_a)
        fp_b = compute_scan_fingerprint(scan_b)
        assert fp_a != ""
        assert fp_a == fp_b  # order-independent deterministic fingerprint

        # Altering a score or finding changes fingerprint
        scan_c = ScanResult(
            report_name="test",
            source_path="test",
            report=CanonicalReport(),
            issues=[issue1],
            scores={"model": 90.0, "overall": 90.0},
            config={},
        )
        assert compute_scan_fingerprint(scan_c) != fp_a


class TestRemediationAuditStore:
    def test_save_and_retrieve_manifest(self, tmp_path: Path):
        manifest = RemediationManifest(
            manifest_id="MAN-TEST-001",
            model_name="TestProject",
            actor="CLI",
            decision="ACCEPTED",
            before_score=80.0,
            after_score=85.0,
            score_delta=5.0,
            applied_patches=[{"patch_id": "REM-1"}],
        )

        manifest_path = RemediationAuditStore.save_manifest(manifest, tmp_path)
        assert manifest_path.exists()
        assert "manifest_MAN-TEST-001.json" in manifest_path.name

        retrieved = RemediationAuditStore.get_manifest("MAN-TEST-001", tmp_path)
        assert retrieved is not None
        assert retrieved.manifest_id == "MAN-TEST-001"
        assert retrieved.model_name == "TestProject"
        assert retrieved.score_delta == 5.0

    def test_history_indexing_and_reverse_chronological_ordering(self, tmp_path: Path):
        m1 = RemediationManifest(
            manifest_id="MAN-001",
            model_name="ModelA",
            created_at="2026-08-18T10:00:00Z",
            decision="ACCEPTED",
            before_score=70.0,
            after_score=75.0,
            score_delta=5.0,
        )
        m2 = RemediationManifest(
            manifest_id="MAN-002",
            model_name="ModelA",
            created_at="2026-08-18T11:00:00Z",
            decision="ACCEPTED",
            before_score=75.0,
            after_score=82.0,
            score_delta=7.0,
        )

        RemediationAuditStore.save_manifest(m1, tmp_path)
        RemediationAuditStore.save_manifest(m2, tmp_path)

        history = RemediationAuditStore.list_manifests(tmp_path)
        assert len(history) == 2
        assert history[0]["manifest_id"] == "MAN-002"  # newer first
        assert history[1]["manifest_id"] == "MAN-001"

    def test_remediation_engine_apply_creates_audit_record(self, tmp_path: Path):
        import shutil
        model_dir = tmp_path / "test_model"
        shutil.copytree(GOLDEN_DIR / "test_bidirectional", model_dir)

        scan_before = RemediationEngine.analyze(model_dir)
        plan = RemediationEngine.plan(model_dir, scan_before)
        validation = RemediationEngine.validate(plan, scan_before)

        success, manifest = RemediationEngine.apply(plan, validation, backup=True)
        assert success is True
        assert manifest.manifest_id != ""

        # Verify manifest was automatically saved to .pbiscan/remediation/
        saved = RemediationAuditStore.get_manifest(manifest.manifest_id, model_dir)
        assert saved is not None
        assert saved.decision == "ACCEPTED"
        assert saved.actor == "CLI"
        assert saved.after_score >= saved.before_score
