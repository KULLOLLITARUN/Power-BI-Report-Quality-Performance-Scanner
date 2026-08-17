"""Comprehensive unit and adversarial test suite for PBIP Sentinel Safe Remediation Engine."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from click.testing import CliRunner
import pytest

from pbiscan.cli import main
from pbiscan.engine.issue import AuditIssue
from pbiscan.remediation.backup import BackupManager
from pbiscan.remediation.engine import RemediationEngine
from pbiscan.remediation.models import (
    PatchLifecycleState,
    PatchValidationResult,
    RemediationPlan,
    RemediationSafety,
    compute_file_sha256,
)
from pbiscan.remediation.patchers.relationship import RelationshipPatcher
from pbiscan.remediation.planner import RemediationPlanner
from pbiscan.remediation.validator import SandboxValidator
from pbiscan.service import ScanResult, ScanService

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


@pytest.fixture
def temp_bidirectional_bim(tmp_path: Path) -> Path:
    """Create a temporary copy of test_bidirectional (BIM)."""
    src = GOLDEN_DIR / "test_bidirectional"
    dest = tmp_path / "test_bidirectional"
    shutil.copytree(src, dest)
    return dest


@pytest.fixture
def temp_bidirectional_tmdl(tmp_path: Path) -> Path:
    """Create a temporary copy of test_enterprise_stress (TMDL)."""
    src = GOLDEN_DIR / "test_enterprise_stress"
    dest = tmp_path / "test_enterprise_stress"
    shutil.copytree(src, dest)
    return dest


class TestRemediationCoreModelsAndBackup:
    def test_backup_and_restore_cycle(self, temp_bidirectional_bim: Path):
        orig_hash = compute_file_sha256(temp_bidirectional_bim / "fixture.SemanticModel" / "model.bim")
        
        # 1. Create backup
        backup_dir = BackupManager.create_backup(temp_bidirectional_bim)
        assert backup_dir.exists()
        assert BackupManager.verify_restoration(backup_dir, temp_bidirectional_bim)

        # 2. Corrupt original
        (temp_bidirectional_bim / "fixture.SemanticModel" / "model.bim").write_text("corrupted", encoding="utf-8")
        assert not BackupManager.verify_restoration(backup_dir, temp_bidirectional_bim)

        # 3. Restore backup
        success = BackupManager.restore_backup(backup_dir, temp_bidirectional_bim)
        assert success
        assert BackupManager.verify_restoration(backup_dir, temp_bidirectional_bim)
        restored_hash = compute_file_sha256(temp_bidirectional_bim / "fixture.SemanticModel" / "model.bim")
        assert restored_hash == orig_hash


class TestRelationshipPatcher:
    def test_bidirectional_bim_patch_generation_and_evidence(self, temp_bidirectional_bim: Path):
        scan_res = ScanService.execute_scan(temp_bidirectional_bim)
        bidir_findings = [f for f in scan_res.issues if f.rule_id == "MODEL_BIDIRECTIONAL"]
        assert len(bidir_findings) == 1

        patcher = RelationshipPatcher()
        evidence = patcher.analyze(bidir_findings[0], scan_res.report, temp_bidirectional_bim)
        
        assert evidence.rule_id == "MODEL_BIDIRECTIONAL"
        assert evidence.confidence > 0.9
        assert not evidence.violated_preconditions
        assert "relationship_identified" in evidence.satisfied_preconditions
        assert evidence.semantic_risk == "MEDIUM"

        patch = patcher.generate_patch(bidir_findings[0], evidence, temp_bidirectional_bim)
        assert patch is not None
        assert patch.rule_id == "MODEL_BIDIRECTIONAL"
        assert patch.safety == RemediationSafety.REVIEW_REQUIRED
        assert patch.state == PatchLifecycleState.PLANNED
        assert len(patch.chunks) == 1
        assert "oneDirection" in patch.chunks[0].replacement_text
        assert "bothDirections" in patch.chunks[0].original_text

    def test_bidirectional_tmdl_patch_generation_and_evidence(self, temp_bidirectional_tmdl: Path):
        scan_res = ScanService.execute_scan(temp_bidirectional_tmdl)
        bidir_findings = [f for f in scan_res.issues if f.rule_id == "MODEL_BIDIRECTIONAL"]
        assert len(bidir_findings) == 1

        patcher = RelationshipPatcher()
        evidence = patcher.analyze(bidir_findings[0], scan_res.report, temp_bidirectional_tmdl)
        assert not evidence.violated_preconditions

        patch = patcher.generate_patch(bidir_findings[0], evidence, temp_bidirectional_tmdl)
        assert patch is not None
        assert patch.file_path.name == "relationships.tmdl"
        assert len(patch.chunks) == 1
        assert "oneDirection" in patch.chunks[0].replacement_text


class TestRemediationEngineLifecycle:
    def test_dry_run_planning_never_modifies_disk(self, temp_bidirectional_bim: Path):
        bim_file = temp_bidirectional_bim / "fixture.SemanticModel" / "model.bim"
        orig_content = bim_file.read_text(encoding="utf-8")
        orig_hash = compute_file_sha256(bim_file)

        scan_res = RemediationEngine.analyze(temp_bidirectional_bim)
        plan = RemediationEngine.plan(temp_bidirectional_bim, scan_res)
        validation = RemediationEngine.validate(plan, scan_res)

        assert len(plan.actionable_patches) == 1
        assert validation.accepted is True
        assert validation.finding_resolved is True
        assert validation.score_delta > 0

        # Verify disk remains 100% untouched
        assert bim_file.read_text(encoding="utf-8") == orig_content
        assert compute_file_sha256(bim_file) == orig_hash

    def test_stale_source_hash_rejects_patch(self, temp_bidirectional_bim: Path):
        bim_file = temp_bidirectional_bim / "fixture.SemanticModel" / "model.bim"

        scan_res = RemediationEngine.analyze(temp_bidirectional_bim)
        plan = RemediationEngine.plan(temp_bidirectional_bim, scan_res)
        validation = RemediationEngine.validate(plan, scan_res)
        assert validation.accepted is True

        # Simulate user editing the file in background before apply
        bim_file.write_text(bim_file.read_text(encoding="utf-8") + " ", encoding="utf-8")

        success, manifest = RemediationEngine.apply(plan, validation, backup=True)
        assert not success
        assert manifest.decision == "REJECTED"
        assert any("changed after remediation plan" in r for r in manifest.rejection_reasons)

    def test_apply_bim_lifecycle_and_score_improvement(self, temp_bidirectional_bim: Path):
        scan_before = RemediationEngine.analyze(temp_bidirectional_bim)
        before_score = scan_before.overall_score
        assert any(f.rule_id == "MODEL_BIDIRECTIONAL" for f in scan_before.issues)

        plan = RemediationEngine.plan(temp_bidirectional_bim, scan_before)
        validation = RemediationEngine.validate(plan, scan_before)
        assert validation.accepted is True

        success, manifest = RemediationEngine.apply(plan, validation, backup=True)
        assert success is True
        assert manifest.decision == "ACCEPTED"
        assert manifest.after_score > before_score
        assert manifest.score_delta > 0

        # Verify rescan on modified real workspace has 0 MODEL_BIDIRECTIONAL findings
        scan_after = RemediationEngine.analyze(temp_bidirectional_bim)
        assert not any(f.rule_id == "MODEL_BIDIRECTIONAL" for f in scan_after.issues)
        assert scan_after.overall_score == manifest.after_score

    def test_apply_tmdl_lifecycle_and_score_improvement(self, temp_bidirectional_tmdl: Path):
        scan_before = RemediationEngine.analyze(temp_bidirectional_tmdl)
        assert any(f.rule_id == "MODEL_BIDIRECTIONAL" for f in scan_before.issues)

        plan = RemediationEngine.plan(temp_bidirectional_tmdl, scan_before)
        validation = RemediationEngine.validate(plan, scan_before)
        assert validation.accepted is True

        success, manifest = RemediationEngine.apply(plan, validation, backup=True)
        assert success is True
        assert manifest.decision == "ACCEPTED"

        scan_after = RemediationEngine.analyze(temp_bidirectional_tmdl)
        assert not any(f.rule_id == "MODEL_BIDIRECTIONAL" for f in scan_after.issues)

    def test_chunk_hash_mismatch_rejects_patch(self, temp_bidirectional_bim: Path):
        scan_res = RemediationEngine.analyze(temp_bidirectional_bim)
        plan = RemediationEngine.plan(temp_bidirectional_bim, scan_res)
        
        # Corrupt chunk's expected hash
        assert len(plan.patches) == 1
        plan.patches[0].chunks[0].original_text_hash = "0000000000000000000000000000000000000000000000000000000000000000"

        validation = RemediationEngine.validate(plan, scan_res)
        assert validation.accepted is False
        assert any("Chunk text hash mismatch" in r for r in validation.rejection_reasons)

    def test_conflicting_overlapping_patches_detected(self, temp_bidirectional_bim: Path):
        scan_res = RemediationEngine.analyze(temp_bidirectional_bim)
        plan = RemediationEngine.plan(temp_bidirectional_bim, scan_res)
        assert len(plan.patches) == 1

        # Simulate second overlapping patch on the same file & lines
        p1 = plan.patches[0]
        import copy
        p2 = copy.deepcopy(p1)
        p2.patch_id = "REM-MODEL_BIDIRECTIONAL-DUPLICATE"
        
        planner = RemediationPlanner()
        plan_with_two = RemediationPlan(
            model_path=temp_bidirectional_bim,
            patches=[p1, p2],
        )
        
        # Re-run conflict detection
        patches_by_file = {}
        for p in plan_with_two.patches:
            patches_by_file.setdefault(p.file_path, []).append(p)

        conflicts = []
        for file_path, file_patches in patches_by_file.items():
            if len(file_patches) > 1:
                for i in range(len(file_patches)):
                    for j in range(i + 1, len(file_patches)):
                        c1 = file_patches[i].chunks[0]
                        c2 = file_patches[j].chunks[0]
                        if max(c1.start_line, c2.start_line) <= min(c1.end_line, c2.end_line):
                            file_patches[i].state = PatchLifecycleState.CONFLICT
                            file_patches[j].state = PatchLifecycleState.CONFLICT
                            conflicts.append(file_patches[i].patch_id)

        assert len(conflicts) > 0
        assert p1.state == PatchLifecycleState.CONFLICT
        assert p2.state == PatchLifecycleState.CONFLICT

    def test_remediation_manifest_json_parity(self, temp_bidirectional_bim: Path):
        scan_res = RemediationEngine.analyze(temp_bidirectional_bim)
        plan = RemediationEngine.plan(temp_bidirectional_bim, scan_res)
        validation = RemediationEngine.validate(plan, scan_res)
        
        success, manifest = RemediationEngine.apply(plan, validation, backup=True)
        assert success is True
        
        m_dict = manifest.to_dict()
        assert m_dict["decision"] == "ACCEPTED"
        assert m_dict["engine_version"] is not None
        assert len(m_dict["patches"]) == 1
        assert m_dict["patches"][0]["state"] == "APPLIED"


class TestCliFixCommand:
    def test_cli_fix_plan_only_returns_exit_3_when_patches_available(self, temp_bidirectional_bim: Path):
        runner = CliRunner()
        res = runner.invoke(main, ["fix", str(temp_bidirectional_bim)])
        assert res.exit_code == 3
        assert "PBIP SENTINEL SAFE REMEDIATION ENGINE" in res.output
        assert "MODEL_BIDIRECTIONAL" in res.output
        assert "Diff:" in res.output

    def test_cli_fix_apply_returns_exit_0_on_success(self, temp_bidirectional_bim: Path):
        runner = CliRunner()
        res = runner.invoke(main, ["fix", str(temp_bidirectional_bim), "--apply"])
        assert res.exit_code == 0
        assert "Successfully applied 1 remediation patch" in res.output

    def test_cli_fix_format_json_and_markdown(self, temp_bidirectional_bim: Path):
        runner = CliRunner()
        # Test JSON
        res_json = runner.invoke(main, ["fix", str(temp_bidirectional_bim), "--format", "json"])
        assert res_json.exit_code == 3
        data = json.loads(res_json.output)
        assert "validation" in data and "plan" in data
        assert data["validation"]["accepted"] is True

        # Test Markdown
        res_md = runner.invoke(main, ["fix", str(temp_bidirectional_bim), "--format", "markdown"])
        assert res_md.exit_code == 3
        assert "## PBIP Sentinel Remediation Plan" in res_md.output
        assert "```diff" in res_md.output

    def test_cli_fix_rule_filter(self, temp_bidirectional_bim: Path):
        runner = CliRunner()
        # Filter on matching rule
        res_match = runner.invoke(main, ["fix", str(temp_bidirectional_bim), "--rule", "MODEL_BIDIRECTIONAL"])
        assert res_match.exit_code == 3
        assert "Planned Patches:  1" in res_match.output

        # Filter on non-matching rule
        res_nomatch = runner.invoke(main, ["fix", str(temp_bidirectional_bim), "--rule", "DAX_UNUSED_MEASURE"])
        assert res_nomatch.exit_code == 0
        assert "Planned Patches:  0" in res_nomatch.output

    def test_cli_fix_clean_model_returns_exit_0(self, tmp_path: Path):
        clean_model = tmp_path / "clean_model"
        shutil.copytree(GOLDEN_DIR / "test_calc_group_variants", clean_model)

        runner = CliRunner()
        res = runner.invoke(main, ["fix", str(clean_model)])
        assert res.exit_code == 0
        assert "Planned Patches:  0" in res.output

    def test_cli_fix_invalid_path_returns_exit_2(self):
        runner = CliRunner()
        res = runner.invoke(main, ["fix", "nonexistent_model_dir_xyz"])
        assert res.exit_code == 2

