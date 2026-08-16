"""JUnit XML Test Report Renderer for pbiscan (Azure DevOps / Jenkins / CI pipelines)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Optional
from pbiscan import __version__
from pbiscan.engine.issue import AuditIssue


class JUnitRenderer:
    """Renders AuditIssues and scores into standard JUnit XML test report format."""

    def render(
        self,
        issues: list[AuditIssue],
        scores: Optional[dict[str, Any]] = None,
        report_name: str = "PBIP Report",
        execution_time: float = 0.0,
    ) -> str:
        """Generate formatted JUnit XML string from audit findings and scores."""
        scores = scores or {"overall": 100, "category_scores": {}}
        cat_scores = scores.get("category_scores", {})
        
        # Only non-suppressed issues count as test failures
        active_issues = [i for i in issues if not i.suppressed]
        total_tests = max(len(active_issues), 1)  # At least 1 testcase for clean reports
        total_failures = len(active_issues)

        testsuites = ET.Element(
            "testsuites",
            name=f"pbiscan-{report_name}",
            tests=str(total_tests),
            failures=str(total_failures),
            errors="0",
            time=f"{execution_time:.3f}",
        )

        testsuite = ET.SubElement(
            testsuites,
            "testsuite",
            name="pbiscan.quality_audit",
            tests=str(total_tests),
            failures=str(total_failures),
            errors="0",
            time=f"{execution_time:.3f}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Record scoring properties
        properties = ET.SubElement(testsuite, "properties")
        ET.SubElement(properties, "property", name="scanner_version", value=__version__)
        ET.SubElement(properties, "property", name="overall_health_score", value=str(scores.get("overall", 100)))
        for cat, sc in cat_scores.items():
            ET.SubElement(properties, "property", name=f"{cat}_score", value=str(sc))

        if not active_issues:
            # Clean report pass testcase
            ET.SubElement(
                testsuite,
                "testcase",
                classname=f"pbiscan.{report_name}",
                name="Report Quality Health Audit",
                time=f"{execution_time:.3f}",
            )
        else:
            for issue in active_issues:
                tc_name = f"{issue.rule_id}"
                if issue.location:
                    tc_name += f" [{issue.location}]"

                testcase = ET.SubElement(
                    testsuite,
                    "testcase",
                    classname=f"pbiscan.{issue.category}",
                    name=tc_name,
                    time="0.001",
                )

                failure_text = (
                    f"Issue: {issue.title}\n"
                    f"Evidence: {issue.evidence}\n"
                    f"Impact: {issue.impact}\n"
                    f"Recommendation: {issue.recommendation}\n"
                    f"Location: {issue.location or 'N/A'}\n"
                    f"Severity: {issue.severity}\n"
                    f"Confidence: {issue.confidence}%"
                )

                failure = ET.SubElement(
                    testcase,
                    "failure",
                    message=f"{issue.rule_id}: {issue.title or issue.evidence}",
                    type=issue.rule_id,
                )
                failure.text = failure_text

        # Generate XML string with declaration
        return ET.tostring(testsuites, encoding="utf-8", xml_declaration=True).decode("utf-8")
