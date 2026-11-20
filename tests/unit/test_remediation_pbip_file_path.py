"""`pbiscan fix` accepts the .pbip file as well as the project folder, like `pbiscan scan` does.

Before, passing the .pbip file produced "0 actionable patches" and an ACCEPTED verdict with no
change, because the planner looked for the model files inside the file path.
"""
from pathlib import Path

from click.testing import CliRunner

from pbiscan.cli import main
from pbiscan.remediation.engine import RemediationEngine

FIXTURE = Path(__file__).resolve().parents[1] / "golden" / "test_unusedmeasure"


def _plan(path: Path):
    scan = RemediationEngine.analyze(path)
    return RemediationEngine.plan(path, scan)


def test_the_folder_has_patches_to_find():
    # Control: the fixture really has something to fix.
    assert len(_plan(FIXTURE).actionable_patches) > 0


def test_the_pbip_file_gives_the_same_patches_as_the_folder():
    from_folder = _plan(FIXTURE)
    from_file = _plan(FIXTURE / "fixture.pbip")
    assert [p.patch_id for p in from_file.actionable_patches] == [p.patch_id for p in from_folder.actionable_patches]
    assert from_file.model_path == FIXTURE


def test_cli_fix_with_the_pbip_file_finds_the_patches():
    # Exit code 3 is the CLI's "proposals need review" status, the same as for the folder.
    from_file = CliRunner().invoke(main, ["fix", str(FIXTURE / "fixture.pbip")])
    from_folder = CliRunner().invoke(main, ["fix", str(FIXTURE)])
    assert "Proposals Found: 1 actionable" in from_file.output
    assert from_file.exit_code == from_folder.exit_code
