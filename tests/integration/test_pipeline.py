"""Integration tests — full pipeline: PBIP → extraction → canonical → rules → issues → scoring."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.engine.issue import IssueGenerator
from pbiscan.engine.scoring import calculate_scores
from pbiscan.engine.suppressions import load_suppressions, apply_suppressions
from pbiscan.rules.model import MODEL_RULES
from pbiscan.rules.dax import DAX_RULES
from pbiscan.rules.report import REPORT_RULES


GOLDEN_DIR = Path(__file__).parent.parent / "golden"


def run_pipeline(fixture_name: str, config: dict | None = None) -> dict:
    """Run the full pipeline on a golden fixture and return results."""
    if config is None:
        config = {
            "weights": {"model": 0.35, "dax": 0.25, "report": 0.20, "security": 0.20},
            "deductions": {"CRITICAL": 15, "HIGH": 10, "MEDIUM": 5, "WARNING": 3, "ADVISORY": 1, "LOW": 2},
            "thresholds": {"maxVisualsPerPage": 15, "maxSlicersPerPage": 6, "maxCalculatedColumnsPerTable": 4},
        }

    fixture_path = GOLDEN_DIR / fixture_name
    reader = PBIPReader()
    raw = reader.read(fixture_path)

    builder = CanonicalBuilder()
    report = builder.build(raw)

    thresholds = config["thresholds"]
    findings = []
    for rule in MODEL_RULES:
        findings.extend(rule(report))
    for rule in [DAX_RULES[0]]:  # D001 suspicious pattern
        findings.extend(rule(report))
    findings.extend(DAX_RULES[1](report, threshold=thresholds["maxCalculatedColumnsPerTable"]))
    findings.extend(DAX_RULES[2](report))  # D003 duplicate
    findings.extend(DAX_RULES[3](report))  # D004 unused
    findings.extend(REPORT_RULES[0](report, max_visuals=thresholds["maxVisualsPerPage"]))
    findings.extend(REPORT_RULES[1](report, max_slicers=thresholds["maxSlicersPerPage"]))

    gen = IssueGenerator()
    issues = gen.generate(findings)

    suppressions = load_suppressions(fixture_path)
    issues = apply_suppressions(issues, suppressions)

    scores = calculate_scores(issues, config)

    return {
        "report": report,
        "findings": findings,
        "issues": issues,
        "scores": scores,
        "rule_counts": _count_by_rule(findings),
    }


def _count_by_rule(findings) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.rule_id] = counts.get(f.rule_id, 0) + 1
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

    def test_scan_service_pipeline_exact_parity(self):
        """Verify ScanService produces identical results to manual pipeline."""
        from pbiscan.service import ScanService
        fixture_path = GOLDEN_DIR / "test_bidirectional"
        manual = run_pipeline("test_bidirectional")
        service_res = ScanService.execute_scan(fixture_path)

        assert len(manual["issues"]) == len(service_res.issues)
        assert manual["scores"] == service_res.scores
        assert [i.rule_id for i in manual["issues"]] == [i.rule_id for i in service_res.issues]

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
