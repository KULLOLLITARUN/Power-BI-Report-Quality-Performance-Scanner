"""The measure patcher reads each model file once per plan, never trusting a stale read.

Planning 900 unused measures used to re-read every model file for every measure (minutes). The
files are now cached, so these tests pin the one thing a cache could get wrong: a file that
changes between two plans must be seen, or a measure that has just gained a consumer could be
proposed for deletion.
"""
import json
import shutil
from pathlib import Path

import pytest

from pbiscan.remediation.engine import RemediationEngine
from pbiscan.remediation.patchers.measure import MeasurePatcher

FIXTURE = Path(__file__).resolve().parents[1] / "golden" / "test_unusedmeasure"


@pytest.fixture()
def project(tmp_path):
    dest = tmp_path / "proj"
    shutil.copytree(FIXTURE, dest)
    return dest


def _deleted_measures(project: Path) -> list[str]:
    scan = RemediationEngine.analyze(project)
    plan = RemediationEngine.plan(project, scan)
    return [name for p in plan.actionable_patches for name in p.evidence.affected_objects if "Unused Measure" in name]


def _add_consumer(project: Path) -> None:
    bim = project / "fixture.SemanticModel" / "model.bim"
    model = json.loads(bim.read_text(encoding="utf-8"))
    model["model"]["tables"][0]["measures"].append({"name": "Consumer", "expression": "[Unused Measure] + 1"})
    bim.write_text(json.dumps(model, indent=2), encoding="utf-8")


def test_the_unused_measure_is_proposed_for_deletion(project):
    # Control: before any change the measure really is deletable.
    assert len(_deleted_measures(project)) == 1


def test_a_file_changed_after_the_scan_is_still_seen_by_the_plan(project):
    # The scan says the measure is unused. A consumer is then added on disk, so the scan is stale.
    # The plan reads the files itself and must refuse the deletion rather than trust the scan.
    stale_scan = RemediationEngine.analyze(project)
    _add_consumer(project)
    plan = RemediationEngine.plan(project, stale_scan)
    assert [n for p in plan.actionable_patches for n in p.evidence.affected_objects if "Unused Measure" in n] == []


def test_the_cache_is_dropped_when_a_plan_ends(project):
    patcher = MeasurePatcher()
    scan = RemediationEngine.analyze(project)
    issue = next(i for i in scan.unsuppressed_issues if i.rule_id == "DAX_UNUSED_MEASURE")
    patcher.begin_plan()
    assert not patcher.analyze(issue, scan.report, project).violated_preconditions
    patcher.end_plan()
    assert patcher._files_cache is None
    # Outside a plan every call checks the files on disk, so a new consumer is noticed at once.
    _add_consumer(project)
    assert "clean_syntax_boundary" in patcher.analyze(issue, scan.report, project).violated_preconditions


@pytest.mark.parametrize(
    "text, expected",
    [
        ("see revenue here", True),
        ("revenue", True),
        ("(revenue)", True),
        ("revenues", False),
        ("net_revenue", False),
        ("revenue2", False),
        ("revenues and revenue", True),  # first hit has a letter after it, the second is a whole word
        ("nothing here", False),
    ],
)
def test_whole_word_match(text, expected):
    assert MeasurePatcher._names_whole_word(text, "revenue") is expected


def test_an_empty_name_never_matches():
    assert MeasurePatcher._names_whole_word("anything", "") is False
