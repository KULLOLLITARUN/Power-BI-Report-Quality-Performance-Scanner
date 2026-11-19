"""One `pbiscan fix` apply at a time per project (pbiscan/remediation/lock.py)."""
from __future__ import annotations

import os
import shutil
import threading
import time
from pathlib import Path

import pytest

from pbiscan.remediation.engine import RemediationEngine
from pbiscan.remediation.lock import ProjectLockedError, lock_path_for, project_lock
from pbiscan.remediation.validator import SandboxValidator

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden"


def test_lock_is_exclusive_and_released_afterwards(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    with project_lock(project):
        assert lock_path_for(project).exists()
        with pytest.raises(ProjectLockedError):
            with project_lock(project):
                pass
    assert not lock_path_for(project).exists()
    with project_lock(project):  # free again
        pass


def test_lock_is_released_when_the_block_raises(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    with pytest.raises(RuntimeError):
        with project_lock(project):
            raise RuntimeError("boom")
    assert not lock_path_for(project).exists()


def test_lock_lives_beside_the_project_not_inside_it(tmp_path: Path):
    """A rollback replaces the whole project folder, so a lock inside it would vanish."""
    project = tmp_path / "proj"
    project.mkdir()
    with project_lock(project):
        assert lock_path_for(project).parent == tmp_path
        assert list(project.iterdir()) == []


def test_stale_lock_from_a_crashed_run_is_replaced(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    lock = lock_path_for(project)
    lock.write_text("pid=1 started=0\n", encoding="utf-8")
    old = time.time() - 7200
    os.utime(lock, (old, old))
    with project_lock(project, stale_after=3600):
        assert lock.exists()
    assert not lock.exists()


def test_fresh_lock_is_not_treated_as_stale(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    lock_path_for(project).write_text("pid=1\n", encoding="utf-8")
    with pytest.raises(ProjectLockedError) as info:
        with project_lock(project, stale_after=3600):
            pass
    assert str(lock_path_for(project)) in str(info.value)


def _prepared(tmp_path: Path):
    project = tmp_path / "bi"
    shutil.copytree(GOLDEN_DIR / "test_bidirectional", project)
    scan = RemediationEngine.analyze(project)
    plan = RemediationEngine.plan(project, scan)
    validation = RemediationEngine.validate(plan, scan)
    assert validation.accepted and plan.actionable_patches
    return project, scan, plan, validation


def test_second_apply_is_refused_while_the_first_is_writing(tmp_path: Path, monkeypatch):
    project, scan, plan, validation = _prepared(tmp_path)
    before = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}

    writing = threading.Event()
    proceed = threading.Event()
    real_apply = SandboxValidator.apply_patches_to_dir.__func__

    def slow_apply(cls, patches, target_dir):
        writing.set()
        assert proceed.wait(timeout=20)
        return real_apply(cls, patches, target_dir)

    monkeypatch.setattr(SandboxValidator, "apply_patches_to_dir", classmethod(slow_apply))

    outcome: dict = {}
    first = threading.Thread(
        target=lambda: outcome.update(
            result=RemediationEngine.apply(plan, validation, backup=True, original_scan=scan)
        )
    )
    first.start()
    try:
        assert writing.wait(timeout=20), "the first apply never reached its write step"

        # Same project, same plan, while the first apply holds the lock.
        ok, manifest = RemediationEngine.apply(plan, validation, backup=True, original_scan=scan)
        assert ok is False
        assert manifest.decision == "REJECTED"
        assert any("Another `pbiscan fix` is applying" in r for r in manifest.rejection_reasons)
        # The refused apply touched nothing: the project is unchanged and the only backup is the
        # first apply's (taken before it reached its write step), not a second one.
        assert {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()} == before
        assert len([p for p in tmp_path.iterdir() if ".bak_" in p.name]) == 1
    finally:
        proceed.set()
        first.join(timeout=60)

    ok, manifest = outcome["result"]
    assert ok is True and manifest.decision == "ACCEPTED"
    assert not lock_path_for(project).exists()


def test_apply_works_again_after_a_refused_one(tmp_path: Path):
    project, scan, plan, validation = _prepared(tmp_path)
    lock = lock_path_for(project)
    lock.write_text("pid=1\n", encoding="utf-8")
    ok, manifest = RemediationEngine.apply(plan, validation, backup=True, original_scan=scan)
    assert ok is False and manifest.decision == "REJECTED"
    lock.unlink()

    # Rejected patches are not reusable; a fresh plan applies normally once the lock is free.
    scan = RemediationEngine.analyze(project)
    plan = RemediationEngine.plan(project, scan)
    validation = RemediationEngine.validate(plan, scan)
    ok, manifest = RemediationEngine.apply(plan, validation, backup=True, original_scan=scan)
    assert ok is True, manifest.rejection_reasons
