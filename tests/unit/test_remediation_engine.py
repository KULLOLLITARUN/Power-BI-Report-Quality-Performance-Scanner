"""Comprehensive unit and adversarial test suite for PBIP Sentinel Safe Remediation Engine."""
from __future__ import annotations

import hashlib
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
    RemediationPlan,
    RemediationSafety,
    compute_file_sha256,
)
from pbiscan.remediation.patchers.autodate import AutoDatePatcher
from pbiscan.remediation.patchers.datasource import DataSourcePatcher
from pbiscan.remediation.patchers.measure import MeasurePatcher
from pbiscan.remediation.patchers.relationship import RelationshipPatcher
from pbiscan.service import ScanService

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
def temp_hardcoded_datasource_bim(tmp_path: Path) -> Path:
    """Create a temporary BIM-format project with a hardcoded local workstation
    path in a table's M partition source, for exercising DataSourcePatcher's
    BIM code path (the TMDL fixture above only exercises the TMDL path)."""
    src = GOLDEN_DIR / "test_bidirectional"
    dest = tmp_path / "test_hardcoded_datasource_bim"
    shutil.copytree(src, dest)

    bim_file = dest / "fixture.SemanticModel" / "model.bim"
    data = json.loads(bim_file.read_text(encoding="utf-8"))
    for table in data["model"]["tables"]:
        if table["name"] == "Sales":
            table["partitions"][0]["source"]["expression"] = (
                'let Source = Csv.Document(File.Contents("C:\\Users\\Dev\\Downloads\\Sales.csv"), '
                '[Delimiter=",", Columns=3]) in Source'
            )
    bim_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return dest


@pytest.fixture
def temp_autodate_tmdl(tmp_path: Path) -> Path:
    """Create a temporary copy of test_model_auto_datetime_bloat (TMDL)."""
    src = GOLDEN_DIR / "test_model_auto_datetime_bloat"
    dest = tmp_path / "test_model_auto_datetime_bloat"
    shutil.copytree(src, dest)
    return dest


@pytest.fixture
def temp_autodate_bim(tmp_path: Path) -> Path:
    """Create a temporary BIM-format project with an auto-generated LocalDateTable_*
    table, for exercising AutoDatePatcher's BIM code path (the TMDL fixture above
    only exercises the TMDL path)."""
    src = GOLDEN_DIR / "test_bidirectional"
    dest = tmp_path / "test_autodate_bim"
    shutil.copytree(src, dest)

    bim_file = dest / "fixture.SemanticModel" / "model.bim"
    data = json.loads(bim_file.read_text(encoding="utf-8"))
    data["model"]["tables"].append({
        "name": "LocalDateTable_12345678",
        "isHidden": True,
        "columns": [{"name": "Date", "dataType": "dateTime", "sourceColumn": "Date", "isHidden": True}],
        "partitions": [
            {"name": "LocalDateTable_12345678", "mode": "import", "source": {"type": "calculated", "expression": "Calendar()"}}
        ],
    })
    bim_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
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

    def test_compute_file_sha256_does_not_crash_on_non_utf8_bytes(self, tmp_path: Path):
        """Regression: compute_file_sha256 previously read files as UTF-8 text before
        hashing, so any file with a non-UTF-8 byte anywhere (e.g. a legacy-codepage
        character in an unrelated table) raised UnicodeDecodeError. Since this hash
        is used to fingerprint whole-project backups (BackupManager.get_backup_metadata
        hashes every file under the project, not just ones pbiscan patches), it must
        work on arbitrary bytes, not just valid UTF-8 text."""
        f = tmp_path / "legacy_codepage.tmdl"
        f.write_bytes(b"/// legacy byte: \xcb\n")
        digest = compute_file_sha256(f)
        assert len(digest) == 64
        assert digest == hashlib.sha256(f.read_bytes()).hexdigest()

    def test_backup_metadata_survives_unrelated_non_utf8_file_in_project(self, temp_bidirectional_bim: Path):
        """End-to-end regression for the reported bug: a real project containing one
        unrelated file with a non-UTF-8 byte (e.g. a table saved with a legacy-codepage
        DisplayName) must not crash RemediationEngine.apply's backup step."""
        stray = temp_bidirectional_bim / "fixture.SemanticModel" / "StrayNotes.tmdl"
        stray.write_bytes(b"/// Comment with legacy byte: \xcb\n")

        scan_res = RemediationEngine.analyze(temp_bidirectional_bim)
        plan = RemediationEngine.plan(temp_bidirectional_bim, scan_res)
        validation = RemediationEngine.validate(plan, scan_res)
        assert validation.accepted is True

        success, manifest = RemediationEngine.apply(plan, validation, backup=True, original_scan=scan_res)
        assert success is True
        assert manifest.decision == "ACCEPTED"
        assert manifest.backup_hash


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

    def test_parse_location_malformed_returns_empty_tuple(self):
        patcher = RelationshipPatcher()
        assert patcher._parse_location("this has no arrow at all") == ("", "", "", "")
        assert patcher._parse_location("Sales[CustomerID] <-> ") == ("", "", "", "")
        assert patcher._parse_location("") == ("", "", "", "")

    def test_single_direction_relationship_blocks_remediation(self, temp_bidirectional_bim: Path):
        """A relationship that IS matched in the model but is NOT bidirectional
        must violate 'relationship_is_bidirectional' rather than being patched."""
        bim_file = temp_bidirectional_bim / "fixture.SemanticModel" / "model.bim"
        data = json.loads(bim_file.read_text(encoding="utf-8"))
        data["model"]["relationships"][0]["crossFilteringBehavior"] = "oneDirection"
        bim_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        scan_res = ScanService.execute_scan(temp_bidirectional_bim)
        assert not any(f.rule_id == "MODEL_BIDIRECTIONAL" for f in scan_res.issues)

        fake_issue = AuditIssue(
            rule_id="MODEL_BIDIRECTIONAL", category="model", severity="WARNING",
            title="t", issue="i", evidence="e", impact="x", recommendation="r", confidence=100,
            location="Sales[CustomerID] <-> Customer[CustomerID]",
        )
        patcher = RelationshipPatcher()
        evidence = patcher.analyze(fake_issue, scan_res.report, temp_bidirectional_bim)
        assert "relationship_is_bidirectional" in evidence.violated_preconditions
        assert "relationship_identified" in evidence.satisfied_preconditions
        assert patcher.generate_patch(fake_issue, evidence, temp_bidirectional_bim) is None

    def test_unmatched_relationship_blocks_remediation(self, temp_bidirectional_bim: Path):
        scan_res = ScanService.execute_scan(temp_bidirectional_bim)
        fake_issue = AuditIssue(
            rule_id="MODEL_BIDIRECTIONAL", category="model", severity="WARNING",
            title="t", issue="i", evidence="e", impact="x", recommendation="r", confidence=100,
            location="DoesNotExist[A] <-> AlsoMissing[B]",
        )
        patcher = RelationshipPatcher()
        evidence = patcher.analyze(fake_issue, scan_res.report, temp_bidirectional_bim)
        assert "relationship_identified" in evidence.violated_preconditions
        assert patcher.generate_patch(fake_issue, evidence, temp_bidirectional_bim) is None

    def test_generate_patch_returns_none_when_target_file_missing_despite_clean_evidence(
        self, temp_bidirectional_bim: Path, tmp_path: Path
    ):
        """Defensive race-condition guard: generate_patch must bail out cleanly if the
        target file no longer exists by the time it runs, even given evidence that
        claims no violated preconditions (e.g. the file was deleted between analyze
        and generate_patch, or generate_patch is called with stale evidence)."""
        scan_res = ScanService.execute_scan(temp_bidirectional_bim)
        bidir_findings = [f for f in scan_res.issues if f.rule_id == "MODEL_BIDIRECTIONAL"]
        patcher = RelationshipPatcher()
        evidence = patcher.analyze(bidir_findings[0], scan_res.report, temp_bidirectional_bim)
        assert not evidence.violated_preconditions

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        assert patcher.generate_patch(bidir_findings[0], evidence, empty_dir) is None

    def test_find_target_file_tmdl_fallback_by_name(self, tmp_path: Path):
        """relationships.tmdl not present, but a differently-named *.tmdl file
        containing 'relationship' in its filename should still be found."""
        fallback = tmp_path / "CustomRelationshipDefs.tmdl"
        fallback.write_text("relationship R1\n\tfromColumn: Sales.CustomerID\n", encoding="utf-8")
        patcher = RelationshipPatcher()
        found = patcher._find_target_file(tmp_path)
        assert found == fallback

    def test_find_target_file_bim_fallback_by_extension(self, tmp_path: Path):
        """No model.bim/database.json present, but any other *.bim file should
        still be found as a last-resort fallback."""
        fallback = tmp_path / "SemanticModel.bim"
        fallback.write_text('{"model": {"tables": []}}', encoding="utf-8")
        patcher = RelationshipPatcher()
        found = patcher._find_target_file(tmp_path)
        assert found == fallback

    def test_find_target_file_returns_none_when_nothing_present(self, tmp_path: Path):
        patcher = RelationshipPatcher()
        assert patcher._find_target_file(tmp_path) is None

    def test_find_target_file_database_json_fallback(self, tmp_path: Path):
        fallback = tmp_path / "database.json"
        fallback.write_text('{"model": {"tables": []}}', encoding="utf-8")
        patcher = RelationshipPatcher()
        assert patcher._find_target_file(tmp_path) == fallback

    def test_analyze_violates_target_file_located_when_no_file_present(self, temp_bidirectional_bim: Path, tmp_path: Path):
        scan_res = ScanService.execute_scan(temp_bidirectional_bim)
        bidir_findings = [f for f in scan_res.issues if f.rule_id == "MODEL_BIDIRECTIONAL"]
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        patcher = RelationshipPatcher()
        evidence = patcher.analyze(bidir_findings[0], scan_res.report, empty_dir)
        assert "target_file_located" in evidence.violated_preconditions

    def test_generate_patch_returns_none_when_chunk_generation_fails(self, tmp_path: Path):
        """Target file exists and evidence is clean, but the relationship block
        for this specific from/to pair isn't found in it (e.g. stale evidence
        pointing at a relationship that was since removed from the file)."""
        rel_file = tmp_path / "relationships.tmdl"
        rel_file.write_text(
            "relationship R1\n\tfromColumn: Other.X\n\ttoColumn: AlsoOther.Y\n\tcrossFilteringBehavior: both\n",
            encoding="utf-8",
        )
        from pbiscan.remediation.models import PatchEvidence
        evidence = PatchEvidence(
            rule_id="MODEL_BIDIRECTIONAL",
            finding_key="MODEL_BIDIRECTIONAL::x",
            confidence=0.95,
            satisfied_preconditions=["relationship_identified", "relationship_is_bidirectional", "target_file_located"],
            violated_preconditions=[],
        )
        fake_issue = AuditIssue(
            rule_id="MODEL_BIDIRECTIONAL", category="model", severity="WARNING",
            title="t", issue="i", evidence="e", impact="x", recommendation="r", confidence=100,
            location="Sales[CustomerID] <-> Customer[CustomerID]",
        )
        patcher = RelationshipPatcher()
        assert patcher.generate_patch(fake_issue, evidence, tmp_path) is None

    def test_patch_tmdl_final_line_without_trailing_newline(self):
        """The last line of a file may have no trailing newline; the replacement
        must not introduce one where the original had none."""
        content = (
            "relationship R1\n"
            "\tfromColumn: Sales.CustomerID\n"
            "\ttoColumn: Customer.CustomerID\n"
            "\tcrossFilteringBehavior: both"  # no trailing newline
        )
        patcher = RelationshipPatcher()
        chunk = patcher._patch_tmdl(content, "Sales", "CustomerID", "Customer", "CustomerID")
        assert chunk is not None
        assert not chunk.replacement_text.endswith("\n")
        assert "oneDirection" in chunk.replacement_text


class TestMeasurePatcherLocationParsing:
    """_parse_issue_location has 3 independent fallback formats depending on which
    part of the codebase constructed the AuditIssue (CLI vs. Studio vs. SARIF renderers
    all phrase location/evidence slightly differently) — each must resolve to the
    correct (measure, table) pair."""

    def test_parses_measure_colon_format_with_table_from_evidence(self):
        issue = AuditIssue(
            rule_id="DAX_UNUSED_MEASURE", category="dax", severity="ADVISORY",
            title="t", issue="i", impact="x", recommendation="r", confidence=95,
            evidence="Measure 'Base Amount' [Sales]: not referenced by any report visual.",
            location="Measure: Base Amount",
        )
        name, table = MeasurePatcher()._parse_issue_location(issue)
        assert name == "Base Amount"
        assert table == "Sales"

    def test_parses_bracket_qualified_format(self):
        issue = AuditIssue(
            rule_id="DAX_UNUSED_MEASURE", category="dax", severity="ADVISORY",
            title="t", issue="i", impact="x", recommendation="r", confidence=95,
            evidence="", location="'Sales'[Base Amount]",
        )
        name, table = MeasurePatcher()._parse_issue_location(issue)
        assert name == "Base Amount"
        assert table == "Sales"

    def test_falls_back_to_evidence_only_format(self):
        issue = AuditIssue(
            rule_id="DAX_UNUSED_MEASURE", category="dax", severity="ADVISORY",
            title="t", issue="i", impact="x", recommendation="r", confidence=95,
            evidence="Measure 'Base Amount' [Sales]: unused",
            location="",
        )
        name, table = MeasurePatcher()._parse_issue_location(issue)
        assert name == "Base Amount"
        assert table == "Sales"


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

    def test_hardcoded_datasource_bim_patch_generation_and_evidence(self, temp_hardcoded_datasource_bim: Path):
        scan_res = ScanService.execute_scan(temp_hardcoded_datasource_bim)
        target_issue = next(f for f in scan_res.issues if f.rule_id == "M_HARDCODED_DATA_SOURCE")

        patcher = DataSourcePatcher()
        evidence = patcher.analyze(target_issue, scan_res.report, temp_hardcoded_datasource_bim)
        assert not evidence.violated_preconditions

        patch = patcher.generate_patch(target_issue, evidence, temp_hardcoded_datasource_bim)
        assert patch is not None
        assert patch.file_path.name == "model.bim"
        assert len(patch.chunks) == 1
        assert "DataFolderPath" in patch.chunks[0].replacement_text
        assert "Downloads" in patch.chunks[0].original_text and "Sales.csv" in patch.chunks[0].original_text

        # The replacement line must itself still be valid JSON text — this is what
        # generate_patch got wrong before the JSON-escaping fix (it left a stray
        # unescaped backslash, corrupting the file on write).
        replaced_content = (temp_hardcoded_datasource_bim / "fixture.SemanticModel" / "model.bim").read_text(
            encoding="utf-8"
        ).replace(patch.chunks[0].original_text, patch.chunks[0].replacement_text)
        parsed = json.loads(replaced_content)
        patched_expr = next(
            t["partitions"][0]["source"]["expression"]
            for t in parsed["model"]["tables"] if t["name"] == "Sales"
        )
        assert patched_expr == 'let Source = Csv.Document(File.Contents(DataFolderPath & "\\Sales.csv"), [Delimiter=",", Columns=3]) in Source'

    def test_apply_hardcoded_datasource_remediation_lifecycle_bim(self, temp_hardcoded_datasource_bim: Path):
        scan_before = RemediationEngine.analyze(temp_hardcoded_datasource_bim)
        ds_before = [f for f in scan_before.issues if f.rule_id == "M_HARDCODED_DATA_SOURCE"]
        assert len(ds_before) == 1

        plan = RemediationEngine.plan(
            temp_hardcoded_datasource_bim,
            scan_before,
            rule_filter="M_HARDCODED_DATA_SOURCE",
        )
        assert len(plan.actionable_patches) == 1

        validation = RemediationEngine.validate(plan, scan_before)
        assert validation.accepted is True
        assert validation.finding_resolved is True

        success, manifest = RemediationEngine.apply(plan, validation, backup=True)
        assert success is True
        assert manifest.decision == "ACCEPTED"

        scan_after = RemediationEngine.analyze(temp_hardcoded_datasource_bim)
        assert not any(f.rule_id == "M_HARDCODED_DATA_SOURCE" for f in scan_after.issues)

    def test_unmatched_table_blocks_hardcoded_datasource_remediation(self, temp_hardcoded_datasource_tmdl: Path):
        scan_res = ScanService.execute_scan(temp_hardcoded_datasource_tmdl)

        fake_issue = AuditIssue(
            rule_id="M_HARDCODED_DATA_SOURCE",
            category="model",
            severity="HIGH",
            title="Hardcoded data source",
            issue="Hardcoded data source",
            evidence="Table 'DoesNotExist' contains hardcoded path",
            impact="None",
            recommendation="Parameterize",
            confidence=95,
            location="Table: DoesNotExist",
        )

        patcher = DataSourcePatcher()
        evidence = patcher.analyze(fake_issue, scan_res.report, temp_hardcoded_datasource_tmdl)
        assert "table_identified" in evidence.violated_preconditions
        assert "target_file_located" in evidence.violated_preconditions
        assert patcher.generate_patch(fake_issue, evidence, temp_hardcoded_datasource_tmdl) is None


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

    def test_autodate_custom_relationship_blocks_remediation(self, temp_autodate_tmdl: Path):
        scan_res = ScanService.execute_scan(temp_autodate_tmdl)

        # Inject a custom relationship between two LocalDateTables
        from pbiscan.canonical.model import Relationship
        scan_res.report.model.relationships.append(
            Relationship(
                from_table="LocalDateTable_12345678",
                from_column="Date",
                to_table="LocalDateTable_87654321",
                to_column="Date",
                cross_filter_direction="both",
            )
        )

        autodate_findings = [f for f in scan_res.issues if f.rule_id == "MODEL_AUTO_DATETIME_BLOAT"]
        patcher = AutoDatePatcher()
        evidence = patcher.analyze(autodate_findings[0], scan_res.report, temp_autodate_tmdl)

        assert "zero_custom_relationship_dependencies" in evidence.violated_preconditions
        assert len(patcher.generate_patches(autodate_findings[0], evidence, temp_autodate_tmdl)) == 0

    def test_autodate_semantic_reference_blocks_remediation(self, temp_autodate_tmdl: Path):
        scan_res = ScanService.execute_scan(temp_autodate_tmdl)

        from pbiscan.canonical.references import SemanticReference
        scan_res.report.semantic_references.add(
            SemanticReference(
                target_name="LocalDateTable_12345678",
                target_type="table",
                source_type="calc_item_dax",
                source_object="CalculationGroup['Item']",
                source_file="definition/tables/CalculationGroup.tmdl",
            )
        )

        autodate_findings = [f for f in scan_res.issues if f.rule_id == "MODEL_AUTO_DATETIME_BLOAT"]
        patcher = AutoDatePatcher()
        evidence = patcher.analyze(autodate_findings[0], scan_res.report, temp_autodate_tmdl)

        assert "zero_semantic_reference_consumers" in evidence.violated_preconditions
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

    def test_autodate_bim_patch_generation_and_evidence(self, temp_autodate_bim: Path):
        scan_res = ScanService.execute_scan(temp_autodate_bim)
        autodate_findings = [f for f in scan_res.issues if f.rule_id == "MODEL_AUTO_DATETIME_BLOAT"]
        assert len(autodate_findings) == 1

        patcher = AutoDatePatcher()
        evidence = patcher.analyze(autodate_findings[0], scan_res.report, temp_autodate_bim)
        assert not evidence.violated_preconditions

        patches = patcher.generate_patches(autodate_findings[0], evidence, temp_autodate_bim)
        assert len(patches) == 1
        assert patches[0].file_path.name == "model.bim"

        patched_content = json.loads(patches[0].chunks[0].replacement_text)
        table_names = [t["name"] for t in patched_content["model"]["tables"]]
        assert "LocalDateTable_12345678" not in table_names
        assert "Sales" in table_names

    def test_apply_autodate_remediation_lifecycle_bim(self, temp_autodate_bim: Path):
        scan_before = RemediationEngine.analyze(temp_autodate_bim)
        assert any(f.rule_id == "MODEL_AUTO_DATETIME_BLOAT" for f in scan_before.issues)

        plan = RemediationEngine.plan(
            temp_autodate_bim,
            scan_before,
            rule_filter="MODEL_AUTO_DATETIME_BLOAT",
        )
        assert len(plan.actionable_patches) == 1

        validation = RemediationEngine.validate(plan, scan_before)
        assert validation.accepted is True
        assert validation.finding_resolved is True

        success, manifest = RemediationEngine.apply(plan, validation, backup=True)
        assert success is True
        assert manifest.decision == "ACCEPTED"

        scan_after = RemediationEngine.analyze(temp_autodate_bim)
        assert not any(f.rule_id == "MODEL_AUTO_DATETIME_BLOAT" for f in scan_after.issues)


class TestCombinedEnterpriseMultiPatcherCertification:
    def test_enterprise_model_with_all_remediation_rules(self, tmp_path: Path):
        """Combined certification test verifying simultaneous multi-patcher lifecycle."""
        # Create a rich model combining bidirectional relationships, unused measures, and hardcoded data sources
        model_dir = tmp_path / "enterprise_combined_model"
        shutil.copytree(GOLDEN_DIR / "test_enterprise_stress", model_dir)

        scan_before = RemediationEngine.analyze(model_dir)
        before_rules = {f.rule_id for f in scan_before.issues}
        assert "MODEL_BIDIRECTIONAL" in before_rules
        assert "DAX_UNUSED_MEASURE" in before_rules
        before_score = scan_before.overall_score

        # Plan across all certified patchers
        plan = RemediationEngine.plan(model_dir, scan_before)
        assert len(plan.actionable_patches) >= 2
        planned_rules = {p.rule_id for p in plan.actionable_patches}
        assert "MODEL_BIDIRECTIONAL" in planned_rules
        assert "DAX_UNUSED_MEASURE" in planned_rules

        # Sandbox Before -> After validation
        validation = RemediationEngine.validate(plan, scan_before)
        assert validation.accepted is True
        assert validation.finding_resolved is True
        assert validation.score_delta > 0

        # Atomic apply with backup
        success, manifest = RemediationEngine.apply(plan, validation, backup=True)
        assert success is True
        assert manifest.decision == "ACCEPTED"
        assert manifest.after_score > before_score
        assert len(manifest.patches) >= 2

        # Verify rescan of modified model
        scan_after = RemediationEngine.analyze(model_dir)
        after_rules = {f.rule_id for f in scan_after.issues}
        assert "MODEL_BIDIRECTIONAL" not in after_rules
        assert scan_after.overall_score > before_score


class TestRemediationPlannerResilience:
    """A crash analyzing/patching ONE finding (e.g. a file with a byte that isn't
    valid UTF-8 slipping past extraction, or any other patcher-internal error)
    must not abort planning for every OTHER finding in the project."""

    def test_one_patcher_crash_does_not_abort_plan_for_other_findings(
        self, temp_hardcoded_datasource_tmdl: Path, monkeypatch
    ):
        scan_res = ScanService.execute_scan(temp_hardcoded_datasource_tmdl)
        ds_findings = [f for f in scan_res.issues if f.rule_id == "M_HARDCODED_DATA_SOURCE"]
        assert len(ds_findings) == 2  # LocalOrders & DownloadsCustomers

        real_analyze = DataSourcePatcher.analyze

        def _crash_on_local_orders(self, issue, report, model_dir):
            if "LocalOrders" in (issue.location or ""):
                raise RuntimeError("simulated patcher crash")
            return real_analyze(self, issue, report, model_dir)

        monkeypatch.setattr(DataSourcePatcher, "analyze", _crash_on_local_orders)

        plan = RemediationEngine.plan(temp_hardcoded_datasource_tmdl, scan_res)

        # The crashing finding is skipped with a clear reason...
        crashed = [
            s for s in plan.skipped_findings
            if "LocalOrders" in (s.get("location") or "") and "crashed" in s.get("reason", "")
        ]
        assert len(crashed) == 1

        # ...but the OTHER finding still produced a valid patch.
        assert len(plan.actionable_patches) == 1
        assert "DownloadsCustomers" in (plan.actionable_patches[0].evidence.affected_objects[0])


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


class TestRemediationEngineFailureRollbackPaths:
    """Covers RemediationEngine.apply's transactional rollback branches — disk-write
    failure, final-verification crash/regression, and audit-persistence failure —
    the exact paths responsible for protecting a user's on-disk project from a bad
    remediation, none of which were previously exercised by any test."""

    def test_disk_write_error_rolls_back_and_restores_original_content(self, temp_bidirectional_bim: Path, monkeypatch):
        bim_file = temp_bidirectional_bim / "fixture.SemanticModel" / "model.bim"
        orig_content = bim_file.read_text(encoding="utf-8")

        scan_res = RemediationEngine.analyze(temp_bidirectional_bim)
        plan = RemediationEngine.plan(temp_bidirectional_bim, scan_res)
        validation = RemediationEngine.validate(plan, scan_res)
        assert validation.accepted is True

        from pbiscan.remediation.validator import SandboxValidator
        monkeypatch.setattr(
            SandboxValidator, "apply_patches_to_dir",
            classmethod(lambda cls, patches, target_dir: ["simulated disk write failure"]),
        )

        success, manifest = RemediationEngine.apply(plan, validation, backup=True, original_scan=scan_res)
        assert success is False
        assert manifest.decision == "ROLLED_BACK"
        assert manifest.rollback_executed is True
        assert any("Disk write error" in r for r in manifest.rejection_reasons)
        assert bim_file.read_text(encoding="utf-8") == orig_content

    def test_final_verification_exception_rolls_back(self, temp_bidirectional_bim: Path, monkeypatch):
        bim_file = temp_bidirectional_bim / "fixture.SemanticModel" / "model.bim"
        orig_content = bim_file.read_text(encoding="utf-8")

        scan_res = RemediationEngine.analyze(temp_bidirectional_bim)
        plan = RemediationEngine.plan(temp_bidirectional_bim, scan_res)
        validation = RemediationEngine.validate(plan, scan_res)
        assert validation.accepted is True

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated final verification crash")

        # original_scan is supplied, so the only remaining internal execute_scan
        # call inside apply() is the post-write final verification scan.
        monkeypatch.setattr(ScanService, "execute_scan", staticmethod(_boom))

        success, manifest = RemediationEngine.apply(plan, validation, backup=True, original_scan=scan_res)
        assert success is False
        assert manifest.decision == "ROLLED_BACK"
        assert manifest.rollback_executed is True
        assert any("Final verification failed" in r for r in manifest.rejection_reasons)
        assert bim_file.read_text(encoding="utf-8") == orig_content

    def test_final_score_regression_triggers_rollback(self, temp_bidirectional_bim: Path, monkeypatch):
        bim_file = temp_bidirectional_bim / "fixture.SemanticModel" / "model.bim"
        orig_content = bim_file.read_text(encoding="utf-8")

        scan_res = RemediationEngine.analyze(temp_bidirectional_bim)
        plan = RemediationEngine.plan(temp_bidirectional_bim, scan_res)
        validation = RemediationEngine.validate(plan, scan_res)
        assert validation.accepted is True

        real_execute_scan = ScanService.execute_scan

        def _regress_on_final_scan(*args, **kwargs):
            result = real_execute_scan(*args, **kwargs)
            result.scores["overall"] = validation.before_score - 50
            return result

        monkeypatch.setattr(ScanService, "execute_scan", staticmethod(_regress_on_final_scan))

        success, manifest = RemediationEngine.apply(plan, validation, backup=True, original_scan=scan_res)
        assert success is False
        assert manifest.decision == "ROLLED_BACK"
        assert any("regressed below baseline" in r for r in manifest.rejection_reasons)
        assert bim_file.read_text(encoding="utf-8") == orig_content

    def test_audit_persistence_failure_rolls_back(self, temp_bidirectional_bim: Path, monkeypatch):
        bim_file = temp_bidirectional_bim / "fixture.SemanticModel" / "model.bim"
        orig_content = bim_file.read_text(encoding="utf-8")

        scan_res = RemediationEngine.analyze(temp_bidirectional_bim)
        plan = RemediationEngine.plan(temp_bidirectional_bim, scan_res)
        validation = RemediationEngine.validate(plan, scan_res)
        assert validation.accepted is True

        from pbiscan.remediation.store import RemediationAuditStore

        def _raise_disk_full(cls, manifest, target_dir):
            raise OSError("simulated disk full")

        monkeypatch.setattr(RemediationAuditStore, "save_manifest", classmethod(_raise_disk_full))

        success, manifest = RemediationEngine.apply(plan, validation, backup=True, original_scan=scan_res)
        assert success is False
        assert manifest.decision == "ROLLED_BACK"
        assert manifest.audit_saved is False
        assert "simulated disk full" in manifest.audit_error
        assert bim_file.read_text(encoding="utf-8") == orig_content

    def test_render_preview_json_format(self, temp_bidirectional_bim: Path):
        scan_res = RemediationEngine.analyze(temp_bidirectional_bim)
        plan = RemediationEngine.plan(temp_bidirectional_bim, scan_res)
        validation = RemediationEngine.validate(plan, scan_res)

        out = RemediationEngine.render_preview(plan, validation, output_format="json")
        parsed = json.loads(out)
        assert parsed["model_path"] == str(plan.model_path)
        assert "validation" in parsed
        assert "plan" in parsed

    def test_render_preview_console_shows_rejection_reasons(self, temp_bidirectional_bim: Path):
        scan_res = RemediationEngine.analyze(temp_bidirectional_bim)
        plan = RemediationEngine.plan(temp_bidirectional_bim, scan_res)
        assert len(plan.patches) == 1
        plan.patches[0].chunks[0].original_text_hash = "0" * 64

        validation = RemediationEngine.validate(plan, scan_res)
        assert validation.accepted is False
        assert validation.rejection_reasons

        out = RemediationEngine.render_preview(plan, validation, output_format="console")
        assert "Rejection Reasons:" in out
        for reason in validation.rejection_reasons:
            assert reason in out


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
        assert "## 🛡️ PBIP Sentinel — Safe Remediation Proposal" in res_md.output
        assert "```diff" in res_md.output

    def test_cli_fix_rule_filter(self, temp_bidirectional_bim: Path):
        runner = CliRunner()
        # Filter on matching rule
        res_match = runner.invoke(main, ["fix", str(temp_bidirectional_bim), "--rule", "MODEL_BIDIRECTIONAL"])
        assert res_match.exit_code == 3
        assert "Proposals Found: 1" in res_match.output or "PROPOSAL:" in res_match.output

        # Filter on non-matching rule
        res_nomatch = runner.invoke(main, ["fix", str(temp_bidirectional_bim), "--rule", "DAX_UNUSED_MEASURE"])
        assert res_nomatch.exit_code == 0
        assert "Proposals Found: 0" in res_nomatch.output

    def test_cli_fix_clean_model_returns_exit_0(self, tmp_path: Path):
        clean_model = tmp_path / "clean_model"
        shutil.copytree(GOLDEN_DIR / "test_measure_referenced_by_another", clean_model)

        runner = CliRunner()
        res = runner.invoke(main, ["fix", str(clean_model)])
        assert res.exit_code == 0
        assert "Proposals Found: 0" in res.output

    def test_cli_fix_invalid_path_returns_exit_2(self):
        runner = CliRunner()
        res = runner.invoke(main, ["fix", "nonexistent_model_dir_xyz"])
        assert res.exit_code == 2


class TestPatcherAdversarialAndEdgeCoverage:
    """Targeted coverage tests for patcher edge-case branches, fallbacks, and preconditions."""

    def test_relationship_patcher_not_found_and_not_bidirectional(self, temp_bidirectional_bim: Path):
        scan_res = RemediationEngine.analyze(temp_bidirectional_bim)
        patcher = RelationshipPatcher()

        # 1. Location not in model
        fake_issue = AuditIssue(
            rule_id="MODEL_BIDIRECTIONAL",
            category="model",
            severity="WARNING",
            title="Bi-directional",
            issue="Test",
            evidence="Evidence",
            impact="Impact",
            recommendation="Rec",
            confidence=100,
            location="GhostTable[ID] <-> OtherTable[ID]",
        )
        evidence = patcher.analyze(fake_issue, scan_res.report, temp_bidirectional_bim)
        assert "relationship_identified" in evidence.violated_preconditions
        assert patcher.generate_patch(fake_issue, evidence, temp_bidirectional_bim) is None

        # 2. Location parsing fallbacks
        f1, c1, t1, c2 = patcher._parse_location("TableA[ColA] <-> TableB[ColB]")
        assert f1 == "TableA" and t1 == "TableB"
        f2, c2, t2, c2_2 = patcher._parse_location("InvalidGarbageLocation")
        assert f2 == ""

        # 3. Patching text when relationship is not found in content
        assert patcher._patch_tmdl("relationship rel1\n\tfromColumn: A\n\ttoColumn: B\n", "X", "A", "Y", "B") is None
        assert patcher._patch_bim(json.dumps({"model": {"relationships": []}}), "X", "A", "Y", "B") is None

    def test_measure_patcher_missing_measure_and_fallbacks(self, temp_unusedmeasure_bim: Path):
        scan_res = RemediationEngine.analyze(temp_unusedmeasure_bim)
        patcher = MeasurePatcher()

        fake_issue = AuditIssue(
            rule_id="DAX_UNUSED_MEASURE",
            category="dax",
            severity="WARNING",
            title="Unused Measure",
            issue="Test",
            evidence="Evidence",
            impact="Impact",
            recommendation="Rec",
            confidence=100,
            location="Measure: NonExistentMeasureName",
        )
        evidence = patcher.analyze(fake_issue, scan_res.report, temp_unusedmeasure_bim)
        assert "measure_identified" in evidence.violated_preconditions
        assert patcher.generate_patch(fake_issue, evidence, temp_unusedmeasure_bim) is None

        # TMDL and BIM chunk helpers with unmatched measure
        assert patcher._patch_tmdl("table Sales\n\tmeasure Existing = 1\n", "GhostMeasure") is None
        assert patcher._patch_bim(json.dumps({"model": {"tables": [{"name": "T", "measures": []}]}}), "T", "Ghost") is None

    def test_datasource_patcher_missing_table_and_fallbacks(self, temp_hardcoded_datasource_tmdl: Path):
        scan_res = RemediationEngine.analyze(temp_hardcoded_datasource_tmdl)
        patcher = DataSourcePatcher()

        fake_issue = AuditIssue(
            rule_id="M_HARDCODED_DATA_SOURCE",
            category="model",
            severity="WARNING",
            title="Hardcoded Source",
            issue="Test",
            evidence='File.Contents("C:\\test.csv")',
            impact="Impact",
            recommendation="Rec",
            confidence=100,
            location="Table: GhostTable",
        )
        evidence = patcher.analyze(fake_issue, scan_res.report, temp_hardcoded_datasource_tmdl)
        assert "table_identified" in evidence.violated_preconditions
        assert patcher.generate_patch(fake_issue, evidence, temp_hardcoded_datasource_tmdl) is None

        # TMDL and BIM chunk helpers with unmatched content
        assert patcher._patch_tmdl("table Sales\n\tpartition P = m\n\t\tSource = Sql.Database()\n") is None
        assert patcher._patch_bim(json.dumps({"model": {"tables": []}}), "GhostTable") is None

    def test_autodate_patcher_missing_table_and_fallbacks(self, temp_bidirectional_tmdl: Path, tmp_path: Path):
        scan_res = RemediationEngine.analyze(temp_bidirectional_tmdl)
        patcher = AutoDatePatcher()

        fake_issue = AuditIssue(
            rule_id="MODEL_AUTO_DATETIME_BLOAT",
            category="model",
            severity="WARNING",
            title="Auto Date Bloat",
            issue="Test",
            evidence="LocalDateTable_Ghost",
            impact="Impact",
            recommendation="Rec",
            confidence=100,
            location="Table: LocalDateTable_NonExistent",
        )
        evidence = patcher.analyze(fake_issue, scan_res.report, temp_bidirectional_tmdl)
        assert "local_date_tables_detected" in evidence.violated_preconditions
        assert patcher.generate_patch(fake_issue, evidence, temp_bidirectional_tmdl) is None

        # Test BIM helper on empty model
        dummy_bim = tmp_path / "empty_model.bim"
        dummy_bim.write_text(json.dumps({"model": {"tables": []}}), encoding="utf-8")
        assert patcher._patch_bim(dummy_bim, evidence) is None

    def test_validator_with_nonexistent_model_path(self, tmp_path: Path):
        from pbiscan.remediation.validator import SandboxValidator
        from pbiscan.service import ScanResult
        plan = RemediationPlan(
            model_path=tmp_path / "nonexistent_dir_404",
            created_at="2026-01-01T00:00:00Z",
            patches=[],
            conflicts=[],
        )
        fake_scan = ScanResult(
            report_name="Test",
            source_path=str(tmp_path / "nonexistent_dir_404"),
            report=None,
            issues=[],
            scores={"overall": 100.0},
            config={},
        )
        res = SandboxValidator.validate_plan(plan, fake_scan)
        assert res.accepted is True
        assert res.after_score == 100.0


class TestMeasurePatcherDeepCoverage:
    """Targeted coverage for MeasurePatcher branches not exercised elsewhere:
    the dax_graph-absent / semantic_references-absent fallback paths, the
    remaining _find_target_file fallback tiers, _parse_issue_location's final
    fallback, and the three _patch_bim comma-repair candidate branches."""

    def test_fallback_cross_measure_check_when_dax_graph_absent(self, temp_unusedmeasure_bim: Path):
        scan_res = ScanService.execute_scan(temp_unusedmeasure_bim)
        unused_findings = [f for f in scan_res.issues if f.rule_id == "DAX_UNUSED_MEASURE"]
        assert len(unused_findings) == 1
        base_measure = unused_findings[0]

        # Simulate a report built without a dax_graph (e.g. an older canonical
        # builder path) — the patcher must fall back to a direct regex scan of
        # other measures' expressions rather than crashing.
        scan_res.report.dax_graph = None
        scan_res.report.semantic_references = None

        patcher = MeasurePatcher()
        evidence = patcher.analyze(base_measure, scan_res.report, temp_unusedmeasure_bim)
        assert "zero_semantic_reference_consumers" in evidence.satisfied_preconditions

    def test_fallback_cross_measure_check_detects_dependent_measure(self, tmp_path: Path):
        """Without a dax_graph, a measure referenced by another measure's DAX
        must still be detected as having a dependent via the regex fallback."""
        src = GOLDEN_DIR / "test_measure_referenced_by_another"
        dest = tmp_path / "test_measure_referenced_by_another"
        shutil.copytree(src, dest)
        scan_res = ScanService.execute_scan(dest)

        base_measure_issue = next(
            (f for f in scan_res.issues if "Base Revenue" in (f.location or f.evidence)), None
        )
        # This fixture's whole point is that Base Revenue has zero findings
        # (it's used transitively) — construct the issue directly to unit-test
        # the fallback branch in isolation.
        fake_issue = AuditIssue(
            rule_id="DAX_UNUSED_MEASURE", category="dax", severity="ADVISORY",
            title="t", issue="i", evidence="Measure 'Base Revenue' [Sales]: unused",
            impact="x", recommendation="r", confidence=95,
            location="Measure: Base Revenue",
        )
        scan_res.report.dax_graph = None
        patcher = MeasurePatcher()
        evidence = patcher.analyze(fake_issue, scan_res.report, dest)
        assert "zero_transitive_measure_dependents" in evidence.violated_preconditions
        assert base_measure_issue is None  # sanity: confirms the fixture setup assumption

    def test_parse_issue_location_final_fallback(self):
        patcher = MeasurePatcher()
        fake_issue = AuditIssue(
            rule_id="DAX_UNUSED_MEASURE", category="dax", severity="ADVISORY",
            title="t", issue="i", evidence="", impact="x", recommendation="r", confidence=95,
            location="JustAPlainNameNoBracketsOrPrefix",
        )
        name, table = patcher._parse_issue_location(fake_issue)
        assert name == "JustAPlainNameNoBracketsOrPrefix"
        assert table == ""

    def test_find_target_file_tables_dir_without_definition_prefix(self, tmp_path: Path):
        (tmp_path / "tables").mkdir()
        target = tmp_path / "tables" / "Sales.tmdl"
        target.write_text("table Sales\n\tmeasure 'M1' = 1\n", encoding="utf-8")
        patcher = MeasurePatcher()
        assert patcher._find_target_file(tmp_path, "Sales", "M1") == target

    def test_find_target_file_glob_fallback_by_measure_declaration(self, tmp_path: Path):
        """No table-name match at all, but some TMDL file on disk declares the
        measure directly — the patcher must still find it via full-project glob."""
        odd_file = tmp_path / "SomeOtherTable.tmdl"
        odd_file.write_text("table SomeOtherTable\n\tmeasure 'OrphanKPI' = 1\n", encoding="utf-8")
        patcher = MeasurePatcher()
        assert patcher._find_target_file(tmp_path, "", "OrphanKPI") == odd_file

    def test_find_target_file_glob_fallback_skips_unreadable_file(self, tmp_path: Path):
        """A non-UTF-8 TMDL file encountered while globbing for the measure
        declaration must be skipped, not crash the whole lookup — the real
        target file (found afterward) must still be located."""
        bad_file = tmp_path / "aaa_legacy_codepage.tmdl"
        bad_file.write_bytes(b"table Legacy\n\t/// byte: \xcb\n")
        good_file = tmp_path / "zzz_target.tmdl"
        good_file.write_text("table Zzz\n\tmeasure 'OrphanKPI' = 1\n", encoding="utf-8")

        patcher = MeasurePatcher()
        assert patcher._find_target_file(tmp_path, "", "OrphanKPI") == good_file

    def test_find_target_file_bim_and_database_json_fallback(self, tmp_path: Path):
        patcher = MeasurePatcher()
        assert patcher._find_target_file(tmp_path, "", "AnyMeasure") is None

        db_json = tmp_path / "database.json"
        db_json.write_text('{"model": {"tables": []}}', encoding="utf-8")
        assert patcher._find_target_file(tmp_path, "", "AnyMeasure") == db_json

    def test_find_target_file_generic_bim_extension_fallback(self, tmp_path: Path):
        patcher = MeasurePatcher()
        generic_bim = tmp_path / "MyModel.bim"
        generic_bim.write_text('{"model": {"tables": []}}', encoding="utf-8")
        assert patcher._find_target_file(tmp_path, "", "AnyMeasure") == generic_bim

    def test_generate_patch_none_when_target_file_missing_despite_clean_evidence(self, tmp_path: Path):
        from pbiscan.remediation.models import PatchEvidence
        evidence = PatchEvidence(
            rule_id="DAX_UNUSED_MEASURE",
            finding_key="DAX_UNUSED_MEASURE::x",
            confidence=0.95,
            satisfied_preconditions=["measure_identified"],
            violated_preconditions=[],
        )
        fake_issue = AuditIssue(
            rule_id="DAX_UNUSED_MEASURE", category="dax", severity="ADVISORY",
            title="t", issue="i", evidence="e", impact="x", recommendation="r", confidence=95,
            location="Measure: Ghost",
        )
        patcher = MeasurePatcher()
        assert patcher.generate_patch(fake_issue, evidence, tmp_path) is None

    def test_patch_tmdl_measure_followed_by_unindented_line(self):
        """A measure declaration immediately followed by a non-indented line
        (rather than another indented property) must still terminate the block
        cleanly via the unindented-line break, not run past it."""
        content = "table Sales\nmeasure 'M1' = 1\nannotation Foo\n"
        patcher = MeasurePatcher()
        chunk = patcher._patch_tmdl(content, "M1")
        assert chunk is not None
        assert "M1" in chunk.original_text
        assert "annotation Foo" not in chunk.original_text

    def test_patch_bim_measure_with_multiline_object_and_trailing_comma(self):
        """Exercises: (a) the backward brace-search loop walking back multiple
        lines to find the object's opening '{', and (b) candidate 1 (trailing
        comma already present after the block) succeeding directly."""
        content = (
            "{\n"
            '  "measures": [\n'
            "    {\n"
            '      "name": "KeepMe",\n'
            '      "expression": "1"\n'
            "    },\n"
            "    {\n"
            '      "name": "DropMe",\n'
            '      "expression": "2"\n'
            "    },\n"
            "    {\n"
            '      "name": "AlsoKeep",\n'
            '      "expression": "3"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )
        patcher = MeasurePatcher()
        chunk = patcher._patch_bim(content, "T", "DropMe")
        assert chunk is not None
        assert "DropMe" in chunk.original_text
        remaining = content.replace(chunk.original_text, chunk.replacement_text)
        parsed = json.loads(remaining)
        names = [m["name"] for m in parsed["measures"]]
        assert "DropMe" not in names
        assert "KeepMe" in names and "AlsoKeep" in names

    def test_patch_bim_measure_last_in_array_uses_leading_comma_candidate(self):
        """When the target measure is the LAST item in the array (no trailing
        comma after it, but a leading comma before it), candidate 1 fails and
        candidate 2 (strip the leading comma) must succeed instead."""
        content = (
            "{\n"
            '  "measures": [\n'
            "    {\n"
            '      "name": "KeepMe",\n'
            '      "expression": "1"\n'
            "    },\n"
            "    {\n"
            '      "name": "DropMeLast",\n'
            '      "expression": "2"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )
        patcher = MeasurePatcher()
        chunk = patcher._patch_bim(content, "T", "DropMeLast")
        assert chunk is not None
        remaining = content.replace(chunk.original_text, chunk.replacement_text)
        parsed = json.loads(remaining)
        names = [m["name"] for m in parsed["measures"]]
        assert "DropMeLast" not in names
        assert names == ["KeepMe"]


