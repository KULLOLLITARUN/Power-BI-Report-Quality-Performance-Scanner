"""SARIF (Static Analysis Results Interchange Format) v2.1.0 Renderer for pbiscan."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pbiscan import __version__
from pbiscan.engine.issue import AuditIssue


# SARIF Level mapping from pbiscan severities
_SEVERITY_TO_SARIF_LEVEL = {
    "CRITICAL": "error",
    "HIGH": "error",
    "MEDIUM": "warning",
    "WARNING": "warning",
    "ADVISORY": "note",
    "LOW": "note",
}


def artifact_uri(report_path: str) -> str:
    """The file every result points at: a path GitHub Code Scanning accepts.

    A SARIF artifact location must be a file URI relative to the repository. A finding's own label
    ("Measure: Sales", "Column: Sales[Region]") is not one: GitHub reads the text before the colon as
    a URI scheme and rejects the whole upload. So results point at the project's .pbip file (or the
    given path), relative to the working directory, and the label goes in logicalLocations.
    """
    if not report_path:
        return "report"
    path = Path(report_path)
    if path.is_dir():
        pbip_files = sorted(path.glob("*.pbip"))
        if pbip_files:
            path = pbip_files[0]
    try:
        relative = Path(os.path.relpath(path, Path.cwd()))
    except ValueError:  # another drive on Windows
        relative = path
    text = relative.as_posix()
    if relative.is_absolute() or text == ".." or text.startswith("../"):
        text = path.name
    return quote(text or "report", safe="/")


class SarifRenderer:
    """Renders AuditIssues into OASIS SARIF v2.1.0 JSON format for GitHub Code Scanning."""

    def __init__(self, scanner_version: str = __version__) -> None:
        self.scanner_version = scanner_version

    def render(
        self,
        issues: list[AuditIssue],
        report_path: str = "",
    ) -> str:
        """Render AuditIssues as a formatted SARIF v2.1.0 JSON string."""
        rules_map: dict[str, dict[str, Any]] = {}
        results: list[dict[str, Any]] = []
        uri = artifact_uri(report_path)

        for issue in issues:
            # 1. Register rule if not already present
            if issue.rule_id not in rules_map:
                sarif_level = _SEVERITY_TO_SARIF_LEVEL.get(issue.severity, "warning")
                rules_map[issue.rule_id] = {
                    "id": issue.rule_id,
                    "name": issue.rule_id.replace("_", " ").title().replace(" ", ""),
                    "shortDescription": {
                        "text": issue.title or issue.rule_id,
                    },
                    "fullDescription": {
                        "text": issue.issue or issue.title or issue.rule_id,
                    },
                    "defaultConfiguration": {
                        "level": sarif_level,
                    },
                    "help": {
                        "text": f"{issue.recommendation}\n\nImpact: {issue.impact}",
                        "markdown": f"### Recommendation\n{issue.recommendation}\n\n**Impact**: {issue.impact}",
                    },
                    "properties": {
                        "category": issue.category,
                        "confidence": issue.confidence,
                        "severity": issue.severity,
                    },
                }

            # 2. Build SARIF result
            sarif_level = _SEVERITY_TO_SARIF_LEVEL.get(issue.severity, "warning")
            
            # The finding's own label (a measure, column, page ...) is a logical location, not a file
            loc_str = issue.location or "report"
            result_obj: dict[str, Any] = {
                "ruleId": issue.rule_id,
                "level": sarif_level,
                "message": {
                    "text": f"{issue.title}: {issue.evidence}" if issue.title else issue.evidence,
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": uri,
                                "uriBaseId": "%SRCROOT%",
                            }
                        },
                        "logicalLocations": [
                            {"name": loc_str, "fullyQualifiedName": loc_str},
                        ],
                    }
                ],
                "properties": {
                    "severity": issue.severity,
                    "confidence": issue.confidence,
                    "category": issue.category,
                    "suppressed": issue.suppressed,
                },
            }

            if issue.suppressed:
                result_obj["suppressions"] = [
                    {
                        "kind": "external",
                        "justification": issue.suppression_reason or "Suppressed via .pbiscanignore",
                    }
                ]

            results.append(result_obj)

        sarif_doc = {
            "$schema": "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "pbiscan",
                            "semanticVersion": self.scanner_version,
                            "informationUri": "https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner",
                            "rules": list(rules_map.values()),
                        }
                    },
                    "results": results,
                }
            ],
        }

        return json.dumps(sarif_doc, indent=2)
