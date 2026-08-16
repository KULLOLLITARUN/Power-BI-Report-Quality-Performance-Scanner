"""Unit tests for SARIF v2.1.0 report generation."""

import json
from pbiscan.engine.issue import AuditIssue
from pbiscan.render.sarif_report import SarifRenderer


class TestSarifRenderer:
    """Test suite for SARIF v2.1.0 JSON format generation."""

    def test_empty_issues_renders_valid_sarif(self):
        renderer = SarifRenderer(scanner_version="1.4.0")
        output = renderer.render(issues=[], report_path="test_report.pbip")
        
        doc = json.loads(output)
        assert doc["version"] == "2.1.0"
        assert len(doc["runs"]) == 1
        run = doc["runs"][0]
        assert run["tool"]["driver"]["name"] == "pbiscan"
        assert run["tool"]["driver"]["semanticVersion"] == "1.4.0"
        assert run["results"] == []
        assert run["tool"]["driver"]["rules"] == []

    def test_issues_render_with_severity_mapping_and_locations(self):
        issues = [
            AuditIssue(
                rule_id="MODEL_BIDIRECTIONAL",
                category="model",
                severity="WARNING",
                title="Bi-directional relationship detected",
                issue="A relationship uses bidirectional filtering.",
                evidence="FactSales[ID] <-> DimCustomer[ID]",
                impact="Increases model ambiguity.",
                recommendation="Use single direction filtering.",
                confidence=100,
                location="FactSales[ID] <-> DimCustomer[ID]",
            ),
            AuditIssue(
                rule_id="DAX_UNUSED_MEASURE",
                category="dax",
                severity="ADVISORY",
                title="Unused DAX measure",
                issue="Measure is not referenced.",
                evidence="Measure 'UnusedKPI' is unreferenced.",
                impact="Increases model bloat.",
                recommendation="Remove measure.",
                confidence=95,
                location="Measure: UnusedKPI",
            ),
            AuditIssue(
                rule_id="MODEL_FACT_TO_FACT",
                category="model",
                severity="HIGH",
                title="Fact-to-fact relationship",
                issue="Direct relationship between two fact tables.",
                evidence="FactSales[ID] <-> FactReturns[ID]",
                impact="Severe ambiguity and performance degradation.",
                recommendation="Introduce a shared dimension table.",
                confidence=80,
                location="FactSales[ID] <-> FactReturns[ID]",
            ),
        ]

        renderer = SarifRenderer(scanner_version="1.4.0")
        output = renderer.render(issues=issues, report_path="test_report.pbip")
        doc = json.loads(output)

        results = doc["runs"][0]["results"]
        rules = doc["runs"][0]["tool"]["driver"]["rules"]

        assert len(results) == 3
        assert len(rules) == 3

        # Check severity mappings
        # HIGH -> error
        high_res = next(r for r in results if r["ruleId"] == "MODEL_FACT_TO_FACT")
        assert high_res["level"] == "error"

        # WARNING -> warning
        warn_res = next(r for r in results if r["ruleId"] == "MODEL_BIDIRECTIONAL")
        assert warn_res["level"] == "warning"

        # ADVISORY -> note
        adv_res = next(r for r in results if r["ruleId"] == "DAX_UNUSED_MEASURE")
        assert adv_res["level"] == "note"

        # Check location
        assert adv_res["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "Measure: UnusedKPI"

    def test_suppressed_issue_includes_suppression_metadata(self):
        issues = [
            AuditIssue(
                rule_id="MODEL_BIDIRECTIONAL",
                category="model",
                severity="WARNING",
                title="Bi-directional relationship detected",
                issue="Bidirectional filtering.",
                evidence="FactSales[ID] <-> DimCustomer[ID]",
                impact="Ambiguity.",
                recommendation="Review direction.",
                confidence=100,
                location="FactSales[ID] <-> DimCustomer[ID]",
                suppressed=True,
                suppression_reason="Intentional for cross-filtering returns",
            )
        ]

        renderer = SarifRenderer(scanner_version="1.4.0")
        output = renderer.render(issues=issues)
        doc = json.loads(output)

        res = doc["runs"][0]["results"][0]
        assert "suppressions" in res
        assert res["suppressions"][0]["justification"] == "Intentional for cross-filtering returns"
