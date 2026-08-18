"""Unit tests for PBIP Sentinel CLI Remediation UX and Selective Apply (v1.8-P1)."""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from click.testing import CliRunner

from pbiscan.cli import main
from pbiscan.remediation.models import compute_file_sha256

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


@pytest.fixture
def temp_multirule_model(tmp_path: Path) -> Path:
    import shutil
    model_dir = tmp_path / "test_multirule_model"
    shutil.copytree(GOLDEN_DIR / "test_enterprise_stress", model_dir)
    return model_dir


@pytest.fixture
def temp_bidirectional_model(tmp_path: Path) -> Path:
    import shutil
    model_dir = tmp_path / "test_bidirectional_cli"
    shutil.copytree(GOLDEN_DIR / "test_bidirectional", model_dir)
    return model_dir


class TestCliRemediationUxAndSelectiveApply:
    def test_cli_fix_plan_only_console_cards(self, temp_bidirectional_model: Path):
        runner = CliRunner()
        res = runner.invoke(main, ["fix", str(temp_bidirectional_model)])
        assert res.exit_code == 3
        assert "PBIP SENTINEL SAFE REMEDIATION ENGINE" in res.output
        assert "PROPOSAL:" in res.output
        assert "MODEL_BIDIRECTIONAL" in res.output
        assert "Proposed Diff:" in res.output
        assert "REMEDIATION VALIDATION VERDICT" in res.output

    def test_cli_fix_format_json_with_out_file(self, temp_bidirectional_model: Path, tmp_path: Path):
        out_file = tmp_path / "plan.json"
        runner = CliRunner()
        res = runner.invoke(main, ["fix", str(temp_bidirectional_model), "--format", "json", "--out", str(out_file)])
        assert res.exit_code == 3
        assert out_file.exists()

        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert "plan" in data
        assert "validation" in data
        assert len(data["plan"]["patches"]) == 1
        assert data["validation"]["accepted"] is True
        assert data["validation"]["score_delta"] > 0

    def test_cli_fix_format_markdown_with_out_file(self, temp_bidirectional_model: Path, tmp_path: Path):
        out_file = tmp_path / "plan.md"
        runner = CliRunner()
        res = runner.invoke(main, ["fix", str(temp_bidirectional_model), "--format", "markdown", "--out", str(out_file)])
        assert res.exit_code == 3
        assert out_file.exists()

        content = out_file.read_text(encoding="utf-8")
        assert "## PBIP Sentinel Remediation Plan" in content
        assert "```diff" in content

    def test_cli_fix_selective_patch_id_apply(self, temp_multirule_model: Path):
        # Discover patch IDs first
        runner = CliRunner()
        plan_res = runner.invoke(main, ["fix", str(temp_multirule_model), "--format", "json"])
        assert plan_res.exit_code == 3
        data = json.loads(plan_res.output)
        patches = data["plan"]["patches"]
        assert len(patches) >= 2

        target_patch = patches[0]
        target_id = target_patch["patch_id"]

        # Apply only target_id
        apply_res = runner.invoke(main, ["fix", str(temp_multirule_model), "--patch-id", target_id, "--apply"])
        assert apply_res.exit_code == 0
        assert "Successfully applied 1 remediation patch" in apply_res.output

    def test_cli_fix_interactive_approval_single_patch(self, temp_bidirectional_model: Path):
        runner = CliRunner()
        # Input 'y' to approve the prompt
        res = runner.invoke(main, ["fix", str(temp_bidirectional_model), "--interactive"], input="y\n")
        assert res.exit_code == 0
        assert "Successfully applied 1 remediation patch" in res.output

    def test_cli_fix_interactive_reject_all(self, temp_bidirectional_model: Path):
        bim_file = temp_bidirectional_model / "fixture.SemanticModel" / "model.bim"
        orig_hash = compute_file_sha256(bim_file)

        runner = CliRunner()
        # Input 'n' to reject the prompt
        res = runner.invoke(main, ["fix", str(temp_bidirectional_model), "--interactive"], input="n\n")
        assert res.exit_code == 0
        assert "No patches approved. Exiting without modifying disk." in res.output

        # Verify disk remains 100% untouched
        assert compute_file_sha256(bim_file) == orig_hash

    def test_cli_fix_interactive_quit_aborts(self, temp_bidirectional_model: Path):
        runner = CliRunner()
        res = runner.invoke(main, ["fix", str(temp_bidirectional_model), "--interactive"], input="q\n")
        assert res.exit_code == 0
        assert "Remediation aborted by user." in res.output

    def test_cli_fix_clean_model_returns_exit_0(self, tmp_path: Path):
        import shutil
        model_dir = tmp_path / "clean_model"
        shutil.copytree(GOLDEN_DIR / "test_isolated_table_negative", model_dir)

        runner = CliRunner()
        res = runner.invoke(main, ["fix", str(model_dir)])
        assert res.exit_code == 0
        assert "No actionable patches" in res.output or "0" in res.output
