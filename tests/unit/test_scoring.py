"""Unit tests — scoring engine."""
from __future__ import annotations
import pytest
from pbiscan.engine.scoring import (
    score_category, score_overall, calculate_scores, ConfigError,
)
from pbiscan.engine.issue import AuditIssue


def _issue(category, severity) -> AuditIssue:
    return AuditIssue(
        rule_id="RULE_X", category=category, severity=severity,
        title="T", issue="I", evidence="E", impact="Im",
        recommendation="R", confidence=100,
    )


DEDUCTIONS = {"CRITICAL": 15, "HIGH": 10, "MEDIUM": 5, "WARNING": 3, "ADVISORY": 1, "LOW": 2}
WEIGHTS = {"model": 0.35, "dax": 0.25, "report": 0.20, "security": 0.20}


class TestScoreCategory:
    def test_no_issues_scores_100(self):
        assert score_category([], "model", DEDUCTIONS) == 100

    def test_single_medium_deduction(self):
        issues = [_issue("model", "MEDIUM")]
        assert score_category(issues, "model", DEDUCTIONS) == 95

    def test_clamps_at_zero(self):
        issues = [_issue("model", "CRITICAL")] * 10  # 150 deductions → clamped at 0
        assert score_category(issues, "model", DEDUCTIONS) == 0

    def test_only_scores_correct_category(self):
        issues = [
            _issue("model", "CRITICAL"),   # should affect model
            _issue("dax", "WARNING"),       # should NOT affect model score
        ]
        assert score_category(issues, "model", DEDUCTIONS) == 85
        assert score_category(issues, "dax", DEDUCTIONS) == 97

    def test_missing_severity_raises(self):
        issues = [_issue("model", "UNKNOWN_SEV")]
        issues[0].severity = "UNKNOWN_SEV"
        with pytest.raises(ConfigError, match="UNKNOWN_SEV"):
            score_category(issues, "model", DEDUCTIONS)

    def test_advisory_deduction(self):
        issues = [_issue("dax", "ADVISORY")]
        assert score_category(issues, "dax", DEDUCTIONS) == 99


class TestScoreOverall:
    def test_perfect_scores_overall_100(self):
        scores = {"model": 100, "dax": 100, "report": 100}
        assert score_overall(scores, WEIGHTS) == 100.0

    def test_zero_scores_overall_0(self):
        scores = {"model": 0, "dax": 0, "report": 0}
        assert score_overall(scores, WEIGHTS) == 0.0

    def test_mixed_scores_weighted(self):
        # model=100 (35%), dax=0 (25%), report=100 (20%) → active weight=0.80
        # normalised: model=43.75%, dax=31.25%, report=25%
        scores = {"model": 100, "dax": 0, "report": 100}
        result = score_overall(scores, WEIGHTS)
        expected = (100 * 0.35 + 0 * 0.25 + 100 * 0.20) / (0.35 + 0.25 + 0.20)
        assert abs(result - round(expected, 1)) < 0.01

    def test_security_excluded_from_v1(self):
        """Security not in active_categories — score stays at 100 for perfect model."""
        scores = {"model": 100, "dax": 100, "report": 100}
        result = score_overall(scores, WEIGHTS, active_categories=("model", "dax", "report"))
        assert result == 100.0

    def test_no_categories_returns_100(self):
        assert score_overall({}, WEIGHTS, active_categories=()) == 100.0


class TestCalculateScores:
    def _config(self):
        return {"weights": WEIGHTS, "deductions": DEDUCTIONS}

    def test_clean_report_all_100(self):
        result = calculate_scores([], self._config())
        assert result["overall"] == 100.0
        assert result["category_scores"] == {"model": 100, "dax": 100, "report": 100}

    def test_single_medium_finding(self):
        issues = [_issue("model", "MEDIUM")]
        result = calculate_scores(issues, self._config())
        assert result["category_scores"]["model"] == 95
        assert result["category_scores"]["dax"] == 100
        assert result["overall"] < 100.0

    def test_missing_severity_propagates(self):
        issues = [_issue("model", "MEDIUM")]
        issues[0].severity = "EXTREME"
        with pytest.raises(ConfigError):
            calculate_scores(issues, self._config())
