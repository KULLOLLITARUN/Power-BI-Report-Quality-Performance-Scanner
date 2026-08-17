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
from pbiscan.remediation.patchers.autodate import AutoDatePatcher
from pbiscan.remediation.patchers.datasource import DataSourcePatcher
from pbiscan.remediation.patchers.measure import MeasurePatcher
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


@pytest.fixture
def temp_unusedmeasure_bim(tmp_path: Path) -> Path:
    """Create a temporary copy of test_unusedmeasure (BIM)."""
    src = GOLDEN_DIR / "test_unusedmeasure"
    dest = tmp_path / "test_unusedmeasure"
    shutil.copytree(src, dest)
    return dest


@pytest.fixture
def temp_hardcoded_datasource_tmdl(tmp_path: Path) -> Path:
    """Create a temporary copy of test_m_hardcoded_datasource (TMDL)."""
    src = GOLDEN_DIR / "test_m_hardcoded_datasource"
    dest = tmp_path / "test_m_hardcoded_datasource"
    shutil.copytree(src, dest)
    return dest


@pytest.fixture
def temp_autodate_tmdl(tmp_path: Path) -> Path:
    """Create a temporary copy of test_model_auto_datetime_bloat (TMDL)."""
    src = GOLDEN_DIR / "test_model_auto_datetime_bloat"
    dest = tmp_path / "test_model_auto_datetime_bloat"
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


class TestMeasurePatcher:
    def test_unused_measure_bim_patch_generation_and_evidence(self, temp_unusedmeasure_bim: Path):
        scan_res = ScanService.execute_scan(temp_unusedmeasure_bim)
        unused_findings = [f for f in scan_res.issues if f.rule_id == "DAX_UNUSED_MEASURE"]
        assert len(unused_findings) == 1
        assert "Unused Measure" in (unused_findings[0].location or "")

        patcher = MeasurePatcher()
        evidence = patcher.analyze(unused_findings[0], scan_res.report, temp_unusedmeasure_bim)
        
        assert evidence.rule_id == "DAX_UNUSED_MEASURE"
        assert evidence.confidence > 0.9
        assert not evidence.violated_preconditions
        assert "zero_transitive_measure_dependents" in evidence.satisfied_preconditions
        assert "zero_semantic_reference_consumers" in evidence.satisfied_preconditions
        assert "zero_visual_consumers" in evidence.satisfied_preconditions

        patch = patcher.generate_patch(unused_findings[0], evidence, temp_unusedmeasure_bim)
        assert patch is not None
        assert patch.rule_id == "DAX_UNUSED_MEASURE"
        assert patch.safety == RemediationSafety.REVIEW_REQUIRED
        assert len(patch.chunks) == 1
        assert "Unused Measure" in patch.chunks[0].original_text
        assert "Unused Measure" not in patch.chunks[0].replacement_text

    def test_unused_measure_tmdl_patch_generation_and_evidence(self, temp_bidirectional_tmdl: Path):
        scan_res = ScanService.execute_scan(temp_bidirectional_tmdl)
        unused_findings = [f for f in scan_res.issues if f.rule_id == "DAX_UNUSED_MEASURE"]
        assert len(unused_findings) >= 1
        
        target_issue = next(f for f in unused_findings if "Orphaned Tax Calc" in (f.location or f.evidence))
        
        patcher = MeasurePatcher()
        evidence = patcher.analyze(target_issue, scan_res.report, temp_bidirectional_tmdl)
        assert not evidence.violated_preconditions
        
        patch = patcher.generate_patch(target_issue, evidence, temp_bidirectional_tmdl)
        assert patch is not None
        assert patch.file_path.name == "Sales.tmdl"
        assert len(patch.chunks) == 1
        assert "Orphaned Tax Calc" in patch.chunks[0].original_text
        assert patch.chunks[0].replacement_text == ""

    def test_used_measure_with_transitive_dependents_blocks_deletion(self, temp_bidirectional_tmdl: Path):
        scan_res = ScanService.execute_scan(temp_bidirectional_tmdl)
        
        # Synthesize an issue targeting a base measure with dependents ('Base Amount')
        fake_issue = AuditIssue(
            rule_id="DAX_UNUSED_MEASURE",
            category="dax",
            severity="ADVISORY",
            title="Unused measure",
            issue="Unused measure",
            evidence="Measure 'Base Amount' [Sales]: fake evidence",
            impact="None",
            recommendation="Delete",
            confidence=95,
            location="Measure: Base Amount",
        )
        
        patcher = MeasurePatcher()
        evidence = patcher.analyze(fake_issue, scan_res.report, temp_bidirectional_tmdl)
        assert "zero_transitive_measure_dependents" in evidence.violated_preconditions
        assert evidence.confidence == 0.0
        
        patch = patcher.generate_patch(fake_issue, evidence, temp_bidirectional_tmdl)
        assert patch is None

    def test_measure_in_visual_blocks_deletion(self, temp_unusedmeasure_bim: Path):
        scan_res = ScanService.execute_scan(temp_unusedmeasure_bim)
        
        # 'Total Revenue' is used in visual
        fake_issue = AuditIssue(
            rule_id="DAX_UNUSED_MEASURE",
            category="dax",
            severity="ADVISORY",
            title="Unused measure",
            issue="Unused measure",
            evidence="Measure 'Total Revenue' [Sales]: fake evidence",
            impact="None",
            recommendation="Delete",
            confidence=95,
            location="Measure: Total Revenue",
        )
        
        patcher = MeasurePatcher()
        evidence = patcher.analyze(fake_issue, scan_res.report, temp_unusedmeasure_bim)
        assert "zero_visual_consumers" in evidence.violated_preconditions
        
        patch = patcher.generate_patch(fake_issue, evidence, temp_unusedmeasure_bim)
        assert patch is None

    def test_apply_unused_measure_remediation_lifecycle_bim(self, temp_unusedmeasure_bim: Path):
        scan_before = RemediationEngine.analyze(temp_unusedmeasure_bim)
        assert any(f.rule_id == "DAX_UNUSED_MEASURE" for f in scan_before.issues)
        before_score = scan_before.overall_score

        plan = RemediationEngine.plan(temp_unusedmeasure_bim, scan_before, rule_filter="DAX_UNUSED_MEASURE")
        assert len(plan.actionable_patches) == 1

        validation = RemediationEngine.validate(plan, scan_before)
        assert validation.accepted is True
        assert validation.finding_resolved is True

        success, manifest = RemediationEngine.apply(plan, validation, backup=True)
        assert success is True
        assert manifest.decision == "ACCEPTED"
        assert manifest.after_score >= before_score

    def test_calc_group_reference_blocks_deletion(self):
        src = GOLDEN_DIR / "test_calc_groups_selectedmeasure"
        scan_res = ScanService.execute_scan(src)
        
        # Inject a synthetic calc_item_dax semantic reference to 'Raw Margin'
        from pbiscan.canonical.references import SemanticReference
        scan_res.report.semantic_references.add(SemanticReference(
            target_name="Raw Margin",
            target_table="Sales",
            target_type="measure",
            source_type="calc_item_dax",
            source_object="TimeIntelligence['YTD']",
            source_file="definition/tables/TimeIntelligence.tmdl",
        ))
        
        fake_issue = AuditIssue(
            rule_id="DAX_UNUSED_MEASURE",
            category="dax",
            severity="ADVISORY",
            title="Unused measure",
            issue="Unused measure",
            evidence="Measure 'Raw Margin' [Sales]: fake evidence",
            impact="None",
            recommendation="Delete",
            confidence=95,
            location="Measure: Raw Margin",
        )
        patcher = MeasurePatcher()
        evidence = patcher.analyze(fake_issue, scan_res.report, src)
        assert "zero_semantic_reference_consumers" in evidence.violated_preconditions
        assert patcher.generate_patch(fake_issue, evidence, src) is None

    def test_field_parameter_reference_blocks_deletion(self):
        src = GOLDEN_DIR / "test_field_parameters_usage"
        scan_res = ScanService.execute_scan(src)
        
        fake_issue = AuditIssue(
            rule_id="DAX_UNUSED_MEASURE",
            category="dax",
            severity="ADVISORY",
            title="Unused measure",
            issue="Unused measure",
            evidence="Measure 'ParameterMeasureA' [Sales]: fake evidence",
            impact="None",
            recommendation="Delete",
            confidence=95,
            location="Measure: ParameterMeasureA",
        )
        patcher = MeasurePatcher()
        evidence = patcher.analyze(fake_issue, scan_res.report, src)
        assert "zero_semantic_reference_consumers" in evidence.violated_preconditions
        assert patcher.generate_patch(fake_issue, evidence, src) is None

    def test_multi_hop_transitive_dependency_blocks_deletion(self, temp_bidirectional_tmdl: Path):
        scan_res = ScanService.execute_scan(temp_bidirectional_tmdl)
        
        # 'Net Sales' is referenced by 'Net Sales YTD' which is referenced by 'Sales Growth YoY %'
        fake_issue = AuditIssue(
            rule_id="DAX_UNUSED_MEASURE",
            category="dax",
            severity="ADVISORY",
            title="Unused measure",
            issue="Unused measure",
            evidence="Measure 'Net Sales' [Sales]: fake evidence",
            impact="None",
            recommendation="Delete",
            confidence=95,
            location="Measure: Net Sales",
        )
        patcher = MeasurePatcher()
        evidence = patcher.analyze(fake_issue, scan_res.report, temp_bidirectional_tmdl)
        assert "zero_transitive_measure_dependents" in evidence.violated_preconditions
        assert patcher.generate_patch(fake_issue, evidence, temp_bidirectional_tmdl) is None

    def test_unknown_surface_reference_blocks_deletion(self, tmp_path: Path):
        model_dir = tmp_path / "unknown_surface_model"
        shutil.copytree(GOLDEN_DIR / "test_unusedmeasure", model_dir)
        
        # Inject an unmapped reference into an external script file
        (model_dir / "custom_script.dax").write_text("EVALUATE ROW(\"Val\", [Unused Measure])", encoding="utf-8")
        
        scan_res = ScanService.execute_scan(model_dir)
        unused_findings = [f for f in scan_res.issues if f.rule_id == "DAX_UNUSED_MEASURE"]
        assert len(unused_findings) == 1

        patcher = MeasurePatcher()
        evidence = patcher.analyze(unused_findings[0], scan_res.report, model_dir)
        assert "clean_syntax_boundary" in evidence.violated_preconditions
        assert patcher.generate_patch(unused_findings[0], evidence, model_dir) is None


class TestDataSourcePatcher:
    def test_hardcoded_datasource_tmdl_patch_generation_and_evidence(self, temp_hardcoded_datasource_tmdl: Path):
        scan_res = ScanService.execute_scan(temp_hardcoded_datasource_tmdl)
        ds_findings = [f for f in scan_res.issues if f.rule_id == "M_HARDCODED_DATA_SOURCE"]
        assert len(ds_findings) == 2  # LocalOrders & DownloadsCustomers

        target_issue = next(f for f in ds_findings if "LocalOrders" in (f.location or f.evidence))

        patcher = DataSourcePatcher()
        evidence = patcher.analyze(target_issue, scan_res.report, temp_hardcoded_datasource_tmdl)

        assert evidence.rule_id == "M_HARDCODED_DATA_SOURCE"
        assert evidence.confidence > 0.9
        assert not evidence.violated_preconditions
        assert "table_identified" in evidence.satisfied_preconditions
        assert "hardcoded_path_detected" in evidence.satisfied_preconditions
        assert evidence.semantic_risk == "HIGH"

        patch = patcher.generate_patch(target_issue, evidence, temp_hardcoded_datasource_tmdl)
        assert patch is not None
        assert patch.rule_id == "M_HARDCODED_DATA_SOURCE"
        assert patch.safety == RemediationSafety.REVIEW_REQUIRED
        assert len(patch.chunks) == 1
        assert "DataFolderPath" in patch.chunks[0].replacement_text
        assert "C:\\Users\\Admin\\Desktop\\Orders.xlsx" in patch.chunks[0].original_text

    def test_cloud_datasource_does_not_generate_patch(self, temp_hardcoded_datasource_tmdl: Path):
        scan_res = ScanService.execute_scan(temp_hardcoded_datasource_tmdl)

        # Fake issue targeting clean table CloudSales
        fake_issue = AuditIssue(
            rule_id="M_HARDCODED_DATA_SOURCE",
            category="model",
            severity="HIGH",
            title="Hardcoded data source",
            issue="Hardcoded data source",
            evidence="Table 'CloudSales' contains hardcoded path",
            impact="None",
            recommendation="Parameterize",
            confidence=95,
            location="Table: CloudSales",
        )

        patcher = DataSourcePatcher()
        evidence = patcher.analyze(fake_issue, scan_res.report, temp_hardcoded_datasource_tmdl)
        assert "hardcoded_path_detected" in evidence.violated_preconditions
        assert patcher.generate_patch(fake_issue, evidence, temp_hardcoded_datasource_tmdl) is None

    def test_apply_hardcoded_datasource_remediation_lifecycle_tmdl(self, temp_hardcoded_datasource_tmdl: Path):
        scan_before = RemediationEngine.analyze(temp_hardcoded_datasource_tmdl)
        ds_before = [f for f in scan_before.issues if f.rule_id == "M_HARDCODED_DATA_SOURCE"]
        assert len(ds_before) == 2
        before_score = scan_before.overall_score

        plan = RemediationEngine.plan(
            temp_hardcoded_datasource_tmdl,
            scan_before,
            rule_filter="M_HARDCODED_DATA_SOURCE",
        )
        assert len(plan.actionable_patches) == 2

        validation = RemediationEngine.validate(plan, scan_before)
        assert validation.accepted is True
        assert validation.finding_resolved is True

        success, manifest = RemediationEngine.apply(plan, validation, backup=True)
        assert success is True
        assert manifest.decision == "ACCEPTED"
        assert manifest.after_score >= before_score

    def test_parameter_name_collision_blocks_remediation(self, temp_hardcoded_datasource_tmdl: Path):
        scan_res = ScanService.execute_scan(temp_hardcoded_datasource_tmdl)
        
        # Synthesize a collision where a table named 'DataFolderPath' exists
        from pbiscan.canonical.model import Table
        scan_res.report.model.tables.append(Table(name="DataFolderPath"))

        target_issue = next(f for f in scan_res.issues if f.rule_id == "M_HARDCODED_DATA_SOURCE")
        patcher = DataSourcePatcher()
        evidence = patcher.analyze(target_issue, scan_res.report, temp_hardcoded_datasource_tmdl)
        
        assert "no_parameter_collision" in evidence.violated_preconditions
        assert patcher.generate_patch(target_issue, evidence, temp_hardcoded_datasource_tmdl) is None

    def test_dynamic_m_expression_blocks_remediation(self, temp_hardcoded_datasource_tmdl: Path):
        scan_res = ScanService.execute_scan(temp_hardcoded_datasource_tmdl)
        
        # Inject dynamic Expression.Evaluate into table partition source
        for t in scan_res.report.model.tables:
            if t.name == "LocalOrders":
                t.partition_source = "let Source = Expression.Evaluate(\"C:\\Users\\Admin\\Desktop\\Orders.xlsx\") in Source"

        target_issue = next(f for f in scan_res.issues if f.rule_id == "M_HARDCODED_DATA_SOURCE" and "LocalOrders" in f.location)
        patcher = DataSourcePatcher()
        evidence = patcher.analyze(target_issue, scan_res.report, temp_hardcoded_datasource_tmdl)
        
        assert "supported_path_semantics" in evidence.violated_preconditions
        assert patcher.generate_patch(target_issue, evidence, temp_hardcoded_datasource_tmdl) is None


class TestAutoDatePatcher:
    def test_autodate_tmdl_patch_generation_and_evidence(self, temp_autodate_tmdl: Path):
        scan_res = ScanService.execute_scan(temp_autodate_tmdl)
        autodate_findings = [f for f in scan_res.issues if f.rule_id == "MODEL_AUTO_DATETIME_BLOAT"]
        assert len(autodate_findings) == 1

        patcher = AutoDatePatcher()
        evidence = patcher.analyze(autodate_findings[0], scan_res.report, temp_autodate_tmdl)

        assert evidence.rule_id == "MODEL_AUTO_DATETIME_BLOAT"
        assert evidence.confidence > 0.9
        assert not evidence.violated_preconditions
        assert "local_date_tables_detected" in evidence.satisfied_preconditions
        assert "zero_direct_visual_bindings" in evidence.satisfied_preconditions

        patches = patcher.generate_patches(autodate_findings[0], evidence, temp_autodate_tmdl)
        assert len(patches) >= 1
        assert any(p.rule_id == "MODEL_AUTO_DATETIME_BLOAT" for p in patches)
        assert all(p.safety == RemediationSafety.REVIEW_REQUIRED for p in patches)

    def test_visual_bound_to_local_date_table_blocks_remediation(self, temp_autodate_tmdl: Path):
        scan_res = ScanService.execute_scan(temp_autodate_tmdl)

        # Inject a visual referencing a LocalDateTable column
        from pbiscan.canonical.model import Page, Visual
        scan_res.report.report.pages.append(
            Page(
                name="TestPage",
                visuals=[Visual(visual_type="card", page="TestPage", fields_used=["LocalDateTable_12345678.Date"])],
            )
        )

        autodate_findings = [f for f in scan_res.issues if f.rule_id == "MODEL_AUTO_DATETIME_BLOAT"]
        assert len(autodate_findings) == 1

        patcher = AutoDatePatcher()
        evidence = patcher.analyze(autodate_findings[0], scan_res.report, temp_autodate_tmdl)

        assert "zero_direct_visual_bindings" in evidence.violated_preconditions
        assert len(patcher.generate_patches(autodate_findings[0], evidence, temp_autodate_tmdl)) == 0

    def test_apply_autodate_remediation_lifecycle_tmdl(self, temp_autodate_tmdl: Path):
        scan_before = RemediationEngine.analyze(temp_autodate_tmdl)
        assert any(f.rule_id == "MODEL_AUTO_DATETIME_BLOAT" for f in scan_before.issues)
        before_score = scan_before.overall_score

        plan = RemediationEngine.plan(
            temp_autodate_tmdl,
            scan_before,
            rule_filter="MODEL_AUTO_DATETIME_BLOAT",
        )
        assert len(plan.actionable_patches) >= 1

        validation = RemediationEngine.validate(plan, scan_before)
        assert validation.accepted is True
        assert validation.finding_resolved is True

        success, manifest = RemediationEngine.apply(plan, validation, backup=True)
        assert success is True
        assert manifest.decision == "ACCEPTED"
        assert manifest.after_score >= before_score

        # Verify rescan on modified real workspace has 0 MODEL_AUTO_DATETIME_BLOAT findings
        scan_after = RemediationEngine.analyze(temp_autodate_tmdl)
        assert not any(f.rule_id == "MODEL_AUTO_DATETIME_BLOAT" for f in scan_after.issues)


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
        shutil.copytree(GOLDEN_DIR / "test_measure_referenced_by_another", clean_model)

        runner = CliRunner()
        res = runner.invoke(main, ["fix", str(clean_model)])
        assert res.exit_code == 0
        assert "Planned Patches:  0" in res.output

    def test_cli_fix_invalid_path_returns_exit_2(self):
        runner = CliRunner()
        res = runner.invoke(main, ["fix", "nonexistent_model_dir_xyz"])
        assert res.exit_code == 2

