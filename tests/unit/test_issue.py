"""Unit tests — issue contracts and IssueGenerator."""
from __future__ import annotations
import pytest
from pbiscan.engine.issue import RuleFinding, AuditIssue, IssueGenerator, VALID_SEVERITIES


class TestRuleFinding:
    def test_valid_creation(self):
        f = RuleFinding(
            rule_id="MODEL_BIDIRECTIONAL",
            category="model",
            severity="WARNING",
            confidence=100,
            evidence="Sales[CID] ↔ Customer[CID]",
        )
        assert f.rule_id == "MODEL_BIDIRECTIONAL"
        assert f.confidence == 100
        assert f.location is None

    def test_invalid_severity_raises(self):
        with pytest.raises(ValueError, match="Invalid severity"):
            RuleFinding(
                rule_id="X", category="model", severity="TYPO",
                confidence=50, evidence="test"
            )

    def test_invalid_category_raises(self):
        with pytest.raises(ValueError, match="Invalid category"):
            RuleFinding(
                rule_id="X", category="banana", severity="WARNING",
                confidence=50, evidence="test"
            )

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(ValueError, match="Confidence"):
            RuleFinding(
                rule_id="X", category="model", severity="WARNING",
                confidence=101, evidence="test"
            )

    def test_confidence_zero_valid(self):
        f = RuleFinding(
            rule_id="X", category="model", severity="ADVISORY",
            confidence=0, evidence="test"
        )
        assert f.confidence == 0

    def test_all_valid_severities(self):
        for sev in VALID_SEVERITIES:
            f = RuleFinding(
                rule_id="X", category="model", severity=sev,
                confidence=50, evidence="test"
            )
            assert f.severity == sev


class TestIssueGenerator:
    def _make_finding(self, rule_id="MODEL_BIDIRECTIONAL") -> RuleFinding:
        return RuleFinding(
            rule_id=rule_id,
            category="model",
            severity="WARNING",
            confidence=100,
            evidence="Sales[CID] ↔ Customer[CID]",
            location="Sales[CID] ↔ Customer[CID]",
        )

    def test_converts_finding_to_issue(self):
        gen = IssueGenerator()
        issues = gen.generate([self._make_finding("MODEL_BIDIRECTIONAL")])
        assert len(issues) == 1
        issue = issues[0]
        assert isinstance(issue, AuditIssue)
        assert issue.rule_id == "MODEL_BIDIRECTIONAL"
        assert issue.title  # non-empty
        assert issue.impact  # non-empty
        assert issue.recommendation  # non-empty
        assert issue.confidence == 100

    def test_unknown_rule_raises(self):
        gen = IssueGenerator()
        finding = RuleFinding(
            rule_id="UNKNOWN_RULE_XYZ",
            category="model", severity="WARNING",
            confidence=50, evidence="test"
        )
        with pytest.raises(KeyError, match="UNKNOWN_RULE_XYZ"):
            gen.generate([finding])

    def test_empty_findings(self):
        gen = IssueGenerator()
        assert gen.generate([]) == []

    def test_all_11_rules_have_recommendations(self):
        """Verify every v1 rule_id has a registered recommendation."""
        from pbiscan.engine.recommendations import RECOMMENDATIONS
        expected_ids = {
            "MODEL_BIDIRECTIONAL", "MODEL_MANY_TO_MANY", "MODEL_NO_DATE_TABLE",
            "MODEL_HIGH_CARDINALITY", "MODEL_FACT_TO_FACT",
            "DAX_SUSPICIOUS_PATTERN", "DAX_EXCESSIVE_CALC_COLUMNS",
            "DAX_DUPLICATE_MEASURE", "DAX_UNUSED_MEASURE",
            "REPORT_VISUAL_BLOAT", "REPORT_SLICER_BLOAT",
        }
        for rule_id in expected_ids:
            assert rule_id in RECOMMENDATIONS, f"{rule_id} missing from recommendations"
            rec = RECOMMENDATIONS[rule_id]
            assert rec.get("title"), f"{rule_id} has empty title"
            assert rec.get("issue"), f"{rule_id} has empty issue"
            assert rec.get("impact"), f"{rule_id} has empty impact"
            assert rec.get("recommendation"), f"{rule_id} has empty recommendation"
