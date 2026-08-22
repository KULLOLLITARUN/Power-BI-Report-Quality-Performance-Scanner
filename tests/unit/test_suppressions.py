"""Unit tests for the suppression engine (engine/suppressions.py) and scoring integration."""
from __future__ import annotations
from pbiscan.engine.issue import Issue
from pbiscan.engine.suppressions import SuppressionRule, apply_suppressions
from pbiscan.engine.scoring import score_category


class TestSuppressionRule:
    def test_exact_match(self):
        rule = SuppressionRule(
            rule_id="MODEL_BIDIRECTIONAL",
            location_pattern="Sales[CustID] <-> Customer[CustID]",
            reason="Approved exception",
        )
        assert rule.matches("MODEL_BIDIRECTIONAL", "Sales[CustID] <-> Customer[CustID]")
        assert rule.matches("model_bidirectional", "sales[custid] <-> customer[custid]")
        assert not rule.matches("MODEL_MANY_TO_MANY", "Sales[CustID] <-> Customer[CustID]")
        assert not rule.matches("MODEL_BIDIRECTIONAL", "Other[ID] <-> Table[ID]")

    def test_glob_match(self):
        rule = SuppressionRule(
            rule_id="DAX_UNUSED_MEASURE",
            location_pattern="Sales[*]",
            reason="Sales measures reserved for Excel",
        )
        assert rule.matches("DAX_UNUSED_MEASURE", "Sales[Revenue]")
        assert rule.matches("DAX_UNUSED_MEASURE", "sales[total margin]")
        assert not rule.matches("DAX_UNUSED_MEASURE", "Customer[Spend]")

    def test_wildcard_all_locations(self):
        rule = SuppressionRule(
            rule_id="REPORT_VISUAL_BLOAT",
            location_pattern="*",
            reason="High visual density allowed by design system",
        )
        assert rule.matches("REPORT_VISUAL_BLOAT", "Page: Executive Summary")
        assert rule.matches("REPORT_VISUAL_BLOAT", None)


class TestApplySuppressions:
    def test_apply_suppressions_marks_without_deleting(self):
        i1 = Issue(
            rule_id="MODEL_BIDIRECTIONAL", category="model", severity="WARNING",
            title="Bidi", issue="Bidi rel", evidence="A <-> B", impact="Context",
            recommendation="Fix", confidence=100, location="A <-> B"
        )
        i2 = Issue(
            rule_id="DAX_SUSPICIOUS_PATTERN", category="dax", severity="ADVISORY",
            title="Suspicious", issue="Filter all", evidence="FILTER(ALL)", impact="Perf",
            recommendation="Fix", confidence=65, location="Sales[Total]"
        )
        issues = [i1, i2]
        supps = [
            SuppressionRule(
                rule_id="MODEL_BIDIRECTIONAL",
                location_pattern="A <-> B",
                reason="Intentional bidi filter for returns",
            )
        ]

        result = apply_suppressions(issues, supps)
        # Never deletes issues
        assert len(result) == 2

        # First issue is marked suppressed
        assert result[0].suppressed is True
        assert result[0].suppression_reason == "Intentional bidi filter for returns"

        # Second issue is untouched
        assert result[1].suppressed is False
        assert result[1].suppression_reason is None


class TestScoringSuppressionInteraction:
    def test_score_category_excludes_suppressed(self):
        deductions = {"WARNING": 3, "ADVISORY": 1, "MEDIUM": 5}
        
        # 2 warnings in model: 1 active (3 pts), 1 suppressed (3 pts)
        i1 = Issue(
            rule_id="MODEL_BIDIRECTIONAL", category="model", severity="WARNING",
            title="Bidi 1", issue="Bidi rel", evidence="A <-> B", impact="Context",
            recommendation="Fix", confidence=100, location="A <-> B",
            suppressed=False
        )
        i2 = Issue(
            rule_id="MODEL_BIDIRECTIONAL", category="model", severity="WARNING",
            title="Bidi 2", issue="Bidi rel", evidence="C <-> D", impact="Context",
            recommendation="Fix", confidence=100, location="C <-> D",
            suppressed=True, suppression_reason="Approved"
        )

        score = score_category([i1, i2], "model", deductions)
        # Expected: only 1 warning deducted (100 - 3 = 97), NOT 100 - 6 = 94
        assert score == 97

    def test_all_suppressed_scores_100(self):
        deductions = {"CRITICAL": 15, "HIGH": 10, "MEDIUM": 5, "WARNING": 3, "ADVISORY": 1}
        i1 = Issue(
            rule_id="MODEL_MANY_TO_MANY", category="model", severity="HIGH",
            title="M:M", issue="M:M", evidence="A *..* B", impact="Perf",
            recommendation="Fix", confidence=100, location="A *..* B",
            suppressed=True, suppression_reason="Known"
        )
        score = score_category([i1], "model", deductions)
        assert score == 100
