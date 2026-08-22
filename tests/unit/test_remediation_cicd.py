"""Unit tests for PBIP Sentinel CI/CD PR Remediation Proposals & Governance (v1.8-P2)."""
from __future__ import annotations

from pathlib import Path
import pytest
from click.testing import CliRunner

from pbiscan.cli import main
from pbiscan.remediation.engine import RemediationEngine
from pbiscan.remediation.models import compute_file_sha256
from pbiscan.render.remediation_markdown import RemediationMarkdownRenderer

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


@pytest.fixture
def temp_bidirectional_model(tmp_path: Path) -> Path:
    import shutil
    model_dir = tmp_path / "test_bidirectional_cicd"
    shutil.copytree(GOLDEN_DIR / "test_bidirectional", model_dir)
    return model_dir


@pytest.fixture
def temp_clean_model(tmp_path: Path) -> Path:
    import shutil
    model_dir = tmp_path / "test_clean_model_cicd"
    shutil.copytree(GOLDEN_DIR / "test_isolated_table_negative", model_dir)
    return model_dir


class TestRemediationCicdGovernance:
    def test_remediation_markdown_renderer_structure_and_details(self, temp_bidirectional_model: Path):
        scan_res = RemediationEngine.analyze(temp_bidirectional_model)
        plan = RemediationEngine.plan(temp_bidirectional_model, scan_res)
        validation = RemediationEngine.validate(plan, scan_res)

        rendered = RemediationMarkdownRenderer.render(plan, validation, "Sales_Report.pbip")

        # Header and Table
        assert "## 🛡️ PBIP Sentinel — Safe Remediation Proposal" in rendered
        assert "Sales_Report.pbip" in rendered
        assert "| **Overall Health Score** |" in rendered
        assert "🟢 **PASSED (Safe to Apply)**" in rendered

        # Collapsible details
        assert "<details>" in rendered
        assert "<summary><b>🔧 [1/1]" in rendered
        assert "MODEL_BIDIRECTIONAL" in rendered
        assert "```diff" in rendered
        assert "-        \"crossFilteringBehavior\": \"bothDirections\"" in rendered
        assert "+        \"crossFilteringBehavior\": \"oneDirection\"" in rendered
        assert "pbiscan fix \"Sales_Report.pbip\" --patch-id" in rendered

        # Instructions
        assert "### 🚀 How to Apply These Remediations Locally" in rendered
        assert "pbiscan fix \"Sales_Report.pbip\" --interactive" in rendered

    def test_remediation_markdown_clean_model(self, temp_clean_model: Path):
        scan_res = RemediationEngine.analyze(temp_clean_model)
        plan = RemediationEngine.plan(temp_clean_model, scan_res)
        validation = RemediationEngine.validate(plan, scan_res)

        rendered = RemediationMarkdownRenderer.render(plan, validation)
        assert "### ✨ Model is Clean" in rendered
        assert "No automated remediation patches are required" in rendered
        assert "🟢 **CLEAN (No Remediation Required)**" in rendered

    def test_cli_fix_fail_on_remediation_available_flag_triggers_exit_1(self, temp_bidirectional_model: Path):
        runner = CliRunner()
        res = runner.invoke(main, ["fix", str(temp_bidirectional_model), "--fail-on-remediation-available"])
        assert res.exit_code == 1
        assert "Safe remediation is available but unapplied" in res.output

    def test_cli_fix_fail_on_remediation_available_passes_on_clean_model(self, temp_clean_model: Path):
        runner = CliRunner()
        res = runner.invoke(main, ["fix", str(temp_clean_model), "--fail-on-remediation-available"])
        assert res.exit_code == 0

    def test_ci_cd_zero_mutation_guarantee(self, temp_bidirectional_model: Path, tmp_path: Path):
        bim_path = temp_bidirectional_model / "fixture.SemanticModel" / "model.bim"
        initial_hash = compute_file_sha256(bim_path)
        out_markdown = tmp_path / "pr_proposal.md"

        runner = CliRunner()
        res = runner.invoke(main, [
            "fix",
            str(temp_bidirectional_model),
            "--format", "markdown",
            "--out", str(out_markdown),
        ])

        # Plan-only returns exit 3
        assert res.exit_code == 3
        assert out_markdown.exists()
        assert "## 🛡️ PBIP Sentinel — Safe Remediation Proposal" in out_markdown.read_text(encoding="utf-8")

        # Verify disk files remain 100% byte-for-byte unmodified
        final_hash = compute_file_sha256(bim_path)
        assert initial_hash == final_hash

        # Verify no .pbiscan/ mutation directory was left behind in the workspace
        assert not (temp_bidirectional_model / ".pbiscan").exists()
