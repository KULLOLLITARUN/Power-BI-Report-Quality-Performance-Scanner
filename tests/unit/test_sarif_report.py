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

        # The file is the report path; the measure is a logical location, not a URI
        location = adv_res["locations"][0]
        assert location["physicalLocation"]["artifactLocation"]["uri"] == "test_report.pbip"
        assert location["logicalLocations"] == [{"name": "Measure: UnusedKPI", "fullyQualifiedName": "Measure: UnusedKPI"}]

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


def _issue(location: str) -> AuditIssue:
    return AuditIssue(
        rule_id="REPORT_MISSING_COLUMN", category="report", severity="MEDIUM", title="t", issue="i",
        evidence="e", impact="m", recommendation="r", confidence=85, location=location,
    )


def _uris(report_path: str, *locations: str) -> list[str]:
    doc = json.loads(SarifRenderer().render(issues=[_issue(loc) for loc in locations], report_path=report_path))
    return [r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] for r in doc["runs"][0]["results"]]


class TestSarifArtifactUri:
    """GitHub Code Scanning rejects a result whose artifact URI has a scheme that is not a file."""

    def test_a_finding_label_never_becomes_the_uri(self):
        from urllib.parse import urlparse
        labels = ["Measure: Sales", "Column: Sales[Region]", "Page: Overview", "Table: Sales", "FactSales[ID] <-> DimCustomer[ID]"]
        for uri in _uris("model.pbip", *labels):
            assert urlparse(uri).scheme == "", uri
            assert uri == "model.pbip"

    def test_a_project_folder_points_at_its_pbip_file(self, tmp_path, monkeypatch):
        project = tmp_path / "repo" / "my project"
        project.mkdir(parents=True)
        (project / "b.pbip").write_text("{}", encoding="utf-8")
        (project / "a.pbip").write_text("{}", encoding="utf-8")
        monkeypatch.chdir(tmp_path / "repo")
        assert _uris(str(project), "Measure: X") == ["my%20project/a.pbip"]

    def test_a_folder_without_a_pbip_file_uses_the_folder(self, tmp_path, monkeypatch):
        (tmp_path / "proj").mkdir()
        monkeypatch.chdir(tmp_path)
        assert _uris(str(tmp_path / "proj"), "Measure: X") == ["proj"]

    def test_a_path_outside_the_working_directory_falls_back_to_its_name(self, tmp_path, monkeypatch):
        (tmp_path / "elsewhere").mkdir()
        (tmp_path / "elsewhere" / "m.pbip").write_text("{}", encoding="utf-8")
        (tmp_path / "cwd").mkdir()
        monkeypatch.chdir(tmp_path / "cwd")
        assert _uris(str(tmp_path / "elsewhere"), "Measure: X") == ["m.pbip"]

    def test_no_path_gives_a_neutral_file_name(self):
        assert _uris("", "Measure: X") == ["report"]
