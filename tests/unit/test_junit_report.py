"""Unit tests for JUnit XML test report generation."""

import xml.etree.ElementTree as ET
from pbiscan.engine.issue import AuditIssue
from pbiscan.render.junit_report import JUnitRenderer


class TestJUnitRenderer:
    """Test suite for JUnit XML format generation."""

    def test_clean_report_emits_passing_testcase(self):
        renderer = JUnitRenderer()
        output = renderer.render(
            issues=[],
            scores={"overall": 100, "category_scores": {"model": 100, "dax": 100}},
            report_name="CleanReport",
            execution_time=0.012,
        )

        root = ET.fromstring(output)
        assert root.tag == "testsuites"
        assert root.attrib["failures"] == "0"
        assert root.attrib["tests"] == "1"

        testsuite = root.find("testsuite")
        assert testsuite is not None
        assert testsuite.attrib["failures"] == "0"

        testcases = testsuite.findall("testcase")
        assert len(testcases) == 1
        assert testcases[0].find("failure") is None

        # Check properties
        props = testsuite.find("properties")
        assert props is not None
        score_prop = props.find("./property[@name='overall_health_score']")
        assert score_prop is not None
        assert score_prop.attrib["value"] == "100"

    def test_findings_emit_failure_nodes(self):
        issues = [
            AuditIssue(
                rule_id="DAX_UNUSED_MEASURE",
                category="dax",
                severity="ADVISORY",
                title="Unused DAX measure",
                issue="Measure is unreferenced.",
                evidence="Measure 'UnusedKPI' is not used.",
                impact="Memory overhead.",
                recommendation="Remove measure.",
                confidence=95,
                location="Measure: UnusedKPI",
            ),
            AuditIssue(
                rule_id="MODEL_BIDIRECTIONAL",
                category="model",
                severity="WARNING",
                title="Bidirectional relationship",
                issue="Bidirectional cross-filtering.",
                evidence="Sales <-> Customer",
                impact="Ambiguity.",
                recommendation="Use single direction.",
                confidence=100,
                location="Sales <-> Customer",
                suppressed=True,  # Suppressed issue should NOT create a test failure
                suppression_reason="Intentional",
            ),
        ]

        renderer = JUnitRenderer()
        output = renderer.render(
            issues=issues,
            scores={"overall": 98, "category_scores": {"dax": 98, "model": 100}},
            report_name="SampleReport",
        )

        root = ET.fromstring(output)
        assert root.attrib["failures"] == "1"
        assert root.attrib["tests"] == "1"

        testsuite = root.find("testsuite")
        testcases = testsuite.findall("testcase")
        assert len(testcases) == 1

        tc = testcases[0]
        assert "DAX_UNUSED_MEASURE" in tc.attrib["name"]
        failure = tc.find("failure")
        assert failure is not None
        assert "UnusedKPI" in failure.text
