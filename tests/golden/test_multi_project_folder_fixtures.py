"""Golden fixture contract tests for choosing the project in a folder that holds several.

The folder has two reports (A, B) and two models (A, B). fixture.pbip points at report B, and
B.Report's definition.pbir points at B.SemanticModel, so the project is B + B and nothing else:

- model B has Sales[Amount] and Sales[Region]; model A has only Sales[Amount]
- report B uses Amount and Region (present) and Gone (missing: the one true positive)
- report A uses Sales[OnlyReportA], which no model has: it must not be reported, because report A is
  not part of this project

Picking report A or model A, or mixing the two, changes the findings (a missing Region, a flagged
OnlyReportA). Both engines must follow the .pbip link: the parity tests run this fixture too.
"""
from pathlib import Path

import pytest

from pbiscan.extraction.pbip_reader import PBIPReader, resolve_project_dirs
from pbiscan.service import ScanService

FIXTURE = Path(__file__).parent / "test_multi_project_folder"


@pytest.fixture(scope="module")
def result():
    return ScanService.execute_scan(FIXTURE)


def test_the_pbip_link_chooses_report_and_model():
    report_dir, model_dir = resolve_project_dirs(FIXTURE, FIXTURE / "fixture.pbip")
    assert (report_dir.name, model_dir.name) == ("B.Report", "B.SemanticModel")


def test_only_the_chosen_pair_is_read():
    raw = PBIPReader().read(FIXTURE)
    assert [c["name"] for c in raw.tables[0].columns] == ["Amount", "Region"]
    assert [p.display_name for p in raw.pages] == ["B page"]


def test_only_the_missing_column_of_the_chosen_report_is_flagged(result):
    assert [i.location for i in result.issues if i.rule_id == "REPORT_MISSING_COLUMN"] == ["Column: Sales[Gone]"]


def test_passing_the_pbip_file_gives_the_same_project():
    raw = PBIPReader().read(FIXTURE / "fixture.pbip")
    assert [p.display_name for p in raw.pages] == ["B page"]


def test_without_a_pbip_link_the_first_folder_in_name_order_is_used(tmp_path):
    for name in ("B.Report", "A.Report", "B.SemanticModel", "A.SemanticModel"):
        (tmp_path / name).mkdir()
    report_dir, model_dir = resolve_project_dirs(tmp_path, None)
    assert (report_dir.name, model_dir.name) == ("A.Report", "A.SemanticModel")


def test_a_link_that_leaves_the_project_folder_is_not_followed(tmp_path):
    project = tmp_path / "project"
    (project / "R.Report").mkdir(parents=True)
    (project / "R.SemanticModel").mkdir()
    (tmp_path / "outside").mkdir()
    (project / "R.Report" / "definition.pbir").write_text('{"datasetReference": {"byPath": {"path": "../../outside"}}}', encoding="utf-8")
    (project / "app.pbip").write_text('{"artifacts": [{"report": {"path": "R.Report"}}]}', encoding="utf-8")
    _, model_dir = resolve_project_dirs(project, project / "app.pbip")
    assert model_dir.name == "R.SemanticModel"


def test_unreadable_pbip_and_pbir_fall_back_to_folder_order(tmp_path):
    for name in ("Z.Report", "Z.SemanticModel"):
        (tmp_path / name).mkdir()
    (tmp_path / "app.pbip").write_text("not json", encoding="utf-8")
    (tmp_path / "Z.Report" / "definition.pbir").write_text("[1, 2]", encoding="utf-8")
    report_dir, model_dir = resolve_project_dirs(tmp_path, tmp_path / "app.pbip")
    assert (report_dir.name, model_dir.name) == ("Z.Report", "Z.SemanticModel")
