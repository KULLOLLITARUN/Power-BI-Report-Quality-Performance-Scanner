"""Remediation output must still parse, and change only what the patch meant to change.

The post-patch rescan alone cannot prove that: the TMDL parser skips a table it
can't read, so a patch that corrupts a table file makes that table's findings
disappear, and the rescan would count them as resolved. These tests cover the
per-file re-parse (check_patched_text), the all-or-nothing write in
apply_patches_to_dir, and the "no newly unreadable files" check in both the
sandbox validation and the real apply.
"""
from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import pytest

from pbiscan.remediation import validator as validator_module
from pbiscan.remediation.engine import RemediationEngine
from pbiscan.remediation.integrity import check_patched_text
from pbiscan.remediation.models import Patch, PatchChunk, compute_file_sha256
from pbiscan.remediation.validator import SandboxValidator
from pbiscan.service import ScanService

GOLDEN_DIR = Path(__file__).parent.parent / "golden"

TABLE = (
    "table Sales\n"
    "\tmeasure Keep = 1\n"
    "\n"
    "\tmeasure Drop =\n"
    "\t\t\tVAR x = 2\n"
    "\t\t\tRETURN x\n"
    "\n"
    "\tcolumn Amount\n"
    "\t\tdataType: double\n"
)


# ---------------------------------------------------------------------------
# check_patched_text
# ---------------------------------------------------------------------------

class TestCheckPatchedText:
    def test_clean_measure_removal_passes(self):
        after = TABLE.replace("\tmeasure Drop =\n\t\t\tVAR x = 2\n\t\t\tRETURN x\n\n", "")
        assert check_patched_text(Path("Sales.tmdl"), TABLE, after) == []

    def test_header_removed_but_body_left_behind_is_rejected(self):
        """The orphaned body lines would silently become part of measure Keep."""
        after = TABLE.replace("\n\tmeasure Drop =\n", "\n")
        problems = check_patched_text(Path("Sales.tmdl"), TABLE, after)
        assert problems == ["Sales.tmdl: expression of measure 'Keep' changed by the patch"]

    def test_emptying_a_table_file_passes(self):
        assert check_patched_text(Path("LocalDateTable_1.tmdl"), TABLE, "") == []

    def test_losing_the_table_declaration_is_rejected(self):
        problems = check_patched_text(Path("Sales.tmdl"), TABLE, TABLE.replace("table Sales\n", ""))
        assert problems == ["Sales.tmdl no longer declares table 'Sales' after patching"]

    def test_column_loss_is_rejected(self):
        after = TABLE.replace("\tcolumn Amount\n\t\tdataType: double\n", "")
        assert check_patched_text(Path("Sales.tmdl"), TABLE, after) == ["Sales.tmdl: columns changed by the patch"]

    def test_partition_source_change_passes(self):
        """The data-source patcher rewrites partition M code; that is allowed."""
        before = TABLE + "\tpartition Sales = m\n\t\tsource = File.Contents(\"C:\\Users\\a.csv\")\n"
        after = before.replace('File.Contents("C:\\Users\\a.csv")', "File.Contents(DataPath)")
        assert check_patched_text(Path("Sales.tmdl"), before, after) == []

    def test_byte_order_mark_is_tolerated(self):
        after = TABLE.replace("\tmeasure Drop =\n\t\t\tVAR x = 2\n\t\t\tRETURN x\n\n", "")
        assert check_patched_text(Path("Sales.tmdl"), "\ufeff" + TABLE, "\ufeff" + after) == []

    def test_relationship_direction_change_passes_but_endpoint_change_is_rejected(self):
        before = "relationship r1\n\tfromColumn: Sales.Key\n\ttoColumn: Customer.Key\n\tcrossFilteringBehavior: bothDirections\n"
        direction = before.replace("\tcrossFilteringBehavior: bothDirections\n", "")
        endpoint = before.replace("toColumn: Customer.Key", "toColumn: Customer.Ky")
        assert check_patched_text(Path("relationships.tmdl"), before, direction) == []
        assert check_patched_text(Path("relationships.tmdl"), before, endpoint) == [
            "relationships.tmdl: relationship endpoints changed by the patch"
        ]

    @pytest.mark.parametrize("name", ["model.bim", "report.json", "definition.pbir"])
    def test_json_must_still_parse(self, name: str):
        problems = check_patched_text(Path(name), '{"a": [1, 2]}', '{"a": [1, ]}')
        assert len(problems) == 1 and "no longer valid JSON" in problems[0]

    def test_non_table_tmdl_is_not_compared(self):
        before = "model Model\n\tculture: en-US\nref table LocalDateTable_1\n"
        assert check_patched_text(Path("model.tmdl"), before, "model Model\n\tculture: en-US\n") == []


# ---------------------------------------------------------------------------
# apply_patches_to_dir
# ---------------------------------------------------------------------------

@pytest.fixture
def base_patch(tmp_path: Path) -> Patch:
    """A real planned patch, used as a template for hand-built ones."""
    project = tmp_path / "stress"
    shutil.copytree(GOLDEN_DIR / "test_enterprise_stress", project)
    scan = ScanService.execute_scan(project)
    plan = RemediationEngine.plan(project, scan, rule_filter="DAX_UNUSED_MEASURE")
    return plan.actionable_patches[0]


def _patch_for(template: Patch, path: Path, start: int, end: int, replacement: str) -> Patch:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    original = "".join(lines[start - 1:end])
    return dataclasses.replace(
        template,
        file_path=path,
        source_hash=compute_file_sha256(path),
        chunks=[PatchChunk.create(start, end, original, replacement)],
    )


class TestApplyPatchesToDir:
    def test_bad_patch_is_not_written(self, tmp_path: Path, base_patch: Patch):
        target = tmp_path / "proj" / "Sales.tmdl"
        target.parent.mkdir()
        target.write_bytes(TABLE.encode())

        errors = SandboxValidator.apply_patches_to_dir(
            [_patch_for(base_patch, target, 4, 4, "")], target.parent  # header only
        )

        assert errors == ["Sales.tmdl: expression of measure 'Keep' changed by the patch"]
        assert target.read_bytes() == TABLE.encode()

    def test_one_bad_file_blocks_every_write(self, tmp_path: Path, base_patch: Patch):
        proj = tmp_path / "proj"
        proj.mkdir()
        good, bad = proj / "Good.tmdl", proj / "Bad.tmdl"
        good.write_bytes(TABLE.replace("Sales", "Good").encode())
        bad.write_bytes(TABLE.replace("Sales", "Bad").encode())

        errors = SandboxValidator.apply_patches_to_dir(
            [
                _patch_for(base_patch, good, 4, 7, ""),  # whole measure: fine on its own
                _patch_for(base_patch, bad, 4, 4, ""),   # header only: rejected
            ],
            proj,
        )

        assert len(errors) == 1
        assert good.read_bytes() == TABLE.replace("Sales", "Good").encode()
        assert bad.read_bytes() == TABLE.replace("Sales", "Bad").encode()

    @pytest.mark.parametrize("newline", ["\n", "\r\n"])
    def test_line_endings_are_preserved(self, tmp_path: Path, base_patch: Patch, newline: str):
        target = tmp_path / "proj" / "Sales.tmdl"
        target.parent.mkdir()
        target.write_bytes(TABLE.replace("\n", newline).encode())

        errors = SandboxValidator.apply_patches_to_dir([_patch_for(base_patch, target, 4, 7, "")], target.parent)

        assert errors == []
        expected = TABLE.replace("\tmeasure Drop =\n\t\t\tVAR x = 2\n\t\t\tRETURN x\n\n", "")
        assert target.read_bytes() == expected.replace("\n", newline).encode()


# ---------------------------------------------------------------------------
# Whole-project check: no file may become unreadable
# ---------------------------------------------------------------------------

def _plan_that_breaks_sales_tmdl(project: Path):
    """The real unused-measure plan, plus a chunk that strips Sales.tmdl's
    `table` line, leaving a non-empty file the reader can't use."""
    scan = ScanService.execute_scan(project)
    plan = RemediationEngine.plan(project, scan, rule_filter="DAX_UNUSED_MEASURE")
    patch = next(p for p in plan.actionable_patches if p.file_path.name == "Sales.tmdl")
    header = PatchChunk.create(1, 1, "table Sales\n", "/// table line removed\n")
    patch.chunks = [*patch.chunks, header]
    return scan, plan


def test_sandbox_rejects_a_patch_that_leaves_a_file_unreadable(tmp_path: Path, monkeypatch):
    project = tmp_path / "stress"
    shutil.copytree(GOLDEN_DIR / "test_enterprise_stress", project)
    scan, plan = _plan_that_breaks_sales_tmdl(project)
    # Bypass the per-file check to prove the whole-project check catches it on its own.
    monkeypatch.setattr(validator_module, "check_patched_text", lambda *a: [])

    result = RemediationEngine.validate(plan, scan)

    assert not result.accepted
    assert any("no longer parse" in r and "Sales.tmdl" in r for r in result.rejection_reasons)


def test_auto_date_fix_leaves_a_fully_readable_model(tmp_path: Path):
    """The auto-date patcher empties LocalDateTable_*.tmdl files instead of deleting
    them. An empty file must not count as unreadable, or every later scan would
    switch unused-measure detection off."""
    project = tmp_path / "autodate"
    shutil.copytree(GOLDEN_DIR / "test_model_auto_datetime_bloat", project)
    scan = ScanService.execute_scan(project)
    plan = RemediationEngine.plan(project, scan, rule_filter="MODEL_AUTO_DATETIME_BLOAT")
    validation = RemediationEngine.validate(plan, scan)
    assert validation.accepted, validation.rejection_reasons

    success, _ = RemediationEngine.apply(plan, validation, backup=True, original_scan=scan)

    assert success
    emptied = [p for p in project.rglob("LocalDateTable_*.tmdl") if not p.read_text(encoding="utf-8").strip()]
    assert emptied, "fixture no longer exercises the emptied-file case"
    after = ScanService.execute_scan(project)
    assert after.report.unread_files == []
    assert not [w for w in after.warnings if w.startswith("Skipped") or "was not checked" in w]


def test_apply_rolls_back_a_patch_that_leaves_a_file_unreadable(tmp_path: Path, monkeypatch):
    project = tmp_path / "stress"
    shutil.copytree(GOLDEN_DIR / "test_enterprise_stress", project)
    sales = next(project.rglob("Sales.tmdl"))
    original = sales.read_bytes()
    scan, plan = _plan_that_breaks_sales_tmdl(project)
    # Let both sandbox checks pass so the real apply's final verification is what's tested.
    monkeypatch.setattr(validator_module, "check_patched_text", lambda *a: [])
    monkeypatch.setattr(validator_module, "new_unread_files", lambda *a: [])
    validation = RemediationEngine.validate(plan, scan)
    assert validation.accepted

    success, manifest = RemediationEngine.apply(plan, validation, backup=True, original_scan=scan)

    assert not success
    assert manifest.decision == "ROLLED_BACK"
    assert any("no longer parse" in r for r in manifest.rejection_reasons)
    assert sales.read_bytes() == original
