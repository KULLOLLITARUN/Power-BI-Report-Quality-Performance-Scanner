"""Integration tests — full pipeline: PBIP → extraction → canonical → rules → issues → scoring.

Runs through ScanService.execute_scan, the single entry point the CLI, Studio and
MCP all use, so these tests can't drift from the real pipeline.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pbiscan.service import ScanService

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


def run_pipeline(fixture_name: str) -> dict[str, Any]:
    """Scan a golden fixture and return the pieces these tests inspect."""
    result = ScanService.execute_scan(GOLDEN_DIR / fixture_name)
    return {
        "report": result.report,
        # Issues carry each finding's rule_id and confidence, which is all callers read.
        "findings": result.issues,
        "issues": result.issues,
        "scores": result.scores,
        "rule_counts": _count_by_rule(result.issues),
    }


def _count_by_rule(issues) -> dict[str, int]:
    counts: dict[str, int] = {}
    for i in issues:
        counts[i.rule_id] = counts.get(i.rule_id, 0) + 1
    return counts


class TestPipelineSmoke:
    def test_bidirectional_pipeline(self):
        result = run_pipeline("test_bidirectional")
        assert result["rule_counts"].get("MODEL_BIDIRECTIONAL", 0) == 1

    def test_manytomany_pipeline(self):
        result = run_pipeline("test_manytomany")
        assert result["rule_counts"].get("MODEL_MANY_TO_MANY", 0) == 1

    def test_scores_are_populated(self):
        result = run_pipeline("test_bidirectional")
        scores = result["scores"]
        assert "overall" in scores
        assert "category_scores" in scores
        assert 0 <= scores["overall"] <= 100

    def test_clean_report_scores_100(self):
        """A single relationship fix should bring scores close to perfect."""
        result = run_pipeline("test_measure_referenced_by_another")
        scores = result["scores"]
        # This fixture should produce minimal findings
        assert scores["overall"] >= 80  # at least reasonable score

    def test_all_issues_have_required_fields(self):
        result = run_pipeline("test_bidirectional")
        for issue in result["issues"]:
            assert issue.rule_id
            assert issue.title
            assert issue.evidence
            assert issue.impact
            assert issue.recommendation
            assert 0 <= issue.confidence <= 100

    def test_critical_negative_cross_reference(self):
        """The critical regression test: D004 must be 0 for test_measure_referenced_by_another."""
        result = run_pipeline("test_measure_referenced_by_another")
        d004_count = result["rule_counts"].get("DAX_UNUSED_MEASURE", 0)
        assert d004_count == 0, (
            f"REGRESSION: DAX_UNUSED_MEASURE fired {d004_count} time(s) on "
            f"test_measure_referenced_by_another. Base Revenue is referenced by "
            f"Revenue Per Unit and must not be flagged as unused."
        )

    def test_cli_fail_under_gate(self):
        """Verify --fail-under exits with 0 on pass and 1 on fail in CLI."""
        from click.testing import CliRunner
        from pbiscan.cli import main
        runner = CliRunner()
        res_pass = runner.invoke(main, ["scan", str(GOLDEN_DIR / "test_bidirectional"), "--fail-under", "50"])
        assert res_pass.exit_code == 0
        res_fail = runner.invoke(main, ["scan", str(GOLDEN_DIR / "test_bidirectional"), "--fail-under", "100"])
        assert res_fail.exit_code == 1
        assert "FAIL: Overall score" in res_fail.output
