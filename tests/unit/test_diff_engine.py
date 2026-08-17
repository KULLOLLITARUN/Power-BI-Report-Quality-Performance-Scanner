"""Unit test suite for pbiscan diff engine, renderers, quality gates, and API."""

import json
from pathlib import Path
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from pbiscan.cli import main
from pbiscan.diff import (
    DiffResult,
    DiffService,
    FindingTransition,
    QualityGatePolicy,
    compute_finding_identity,
    normalize_location,
)
from pbiscan.engine.issue import AuditIssue
from pbiscan.render.diff_console import DiffConsoleRenderer
from pbiscan.render.diff_markdown import DiffMarkdownRenderer
from pbiscan.server import app
from pbiscan.service import ScanResult, ScanService

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_baseline_result():
    return ScanResult(
        report_name="Sales_Report",
        source_path="Sales_Report.pbip",
        report=None,
        issues=[
            AuditIssue(
                rule_id="DAX_UNUSED_MEASURE",
                category="dax",
                severity="ADVISORY",
                title="Unused measure",
                issue="Unused measure detected",
                evidence="Total Revenue",
                impact="Minor bloat",
                recommendation="Remove",
                confidence=100,
                location="Measure: Total Revenue",
            ),
            AuditIssue(
                rule_id="M_HARDCODED_DATA_SOURCE",
                category="model",
                severity="HIGH",
                title="Hardcoded source",
                issue="Local file path",
                evidence="C:/Users/test/data.xlsx",
                impact="Refresh failure",
                recommendation="Parameterize",
                confidence=100,
                location="Table: Sales",
            ),
            AuditIssue(
                rule_id="DAX_EXCESSIVE_CALC_COLUMNS",
                category="dax",
                severity="MEDIUM",
                title="Excessive calc columns",
                issue="Too many calc cols",
                evidence="5 columns",
                impact="Memory consumption",
                recommendation="Move upstream",
                confidence=100,
                location="Table: Customers",
            ),
        ],
        scores={"overall": 85.0, "category_scores": {"model": 80, "dax": 85, "report": 100}},
        config={},
    )


@pytest.fixture
def sample_current_result():
    return ScanResult(
        report_name="Sales_Report",
        source_path="Sales_Report.pbip",
        report=None,
        issues=[
            # Persistent: M_HARDCODED_DATA_SOURCE on Sales
            AuditIssue(
                rule_id="M_HARDCODED_DATA_SOURCE",
                category="model",
                severity="HIGH",
                title="Hardcoded source",
                issue="Local file path",
                evidence="C:/Users/test/data.xlsx",
                impact="Refresh failure",
                recommendation="Parameterize",
                confidence=100,
                location="Table: Sales",
            ),
            # Modified: DAX_EXCESSIVE_CALC_COLUMNS severity changed from MEDIUM -> HIGH
            AuditIssue(
                rule_id="DAX_EXCESSIVE_CALC_COLUMNS",
                category="dax",
                severity="HIGH",
                title="Excessive calc columns",
                issue="Too many calc cols",
                evidence="8 columns",
                impact="Memory consumption",
                recommendation="Move upstream",
                confidence=100,
                location="Table: Customers",
            ),
            # New: MODEL_BIDIRECTIONAL on Sales <-> Dates
            AuditIssue(
                rule_id="MODEL_BIDIRECTIONAL",
                category="model",
                severity="WARNING",
                title="Bidirectional relationship",
                issue="Both directions filter",
                evidence="Sales <-> Dates",
                impact="Filter ambiguity",
                recommendation="Single direction",
                confidence=100,
                location="Sales[Date] <-> Dates[Date]",
            ),
            # Resolved: DAX_UNUSED_MEASURE on Total Revenue was removed (not present here)
        ],
        scores={"overall": 79.5, "category_scores": {"model": 75, "dax": 80, "report": 100}},
        config={},
    )


class TestDiffEngineCore:
    """Test core diff engine logic, transitions, and score drift."""

    def test_identical_scans_returns_zero_delta_and_persistent_findings(self, sample_baseline_result):
        diff = DiffService.compare(sample_baseline_result, sample_baseline_result)
        assert diff.score_drift.overall_delta == 0.0
        assert diff.score_drift.direction == "UNCHANGED"
        assert len(diff.new_findings) == 0
        assert len(diff.resolved_findings) == 0
        assert len(diff.modified_findings) == 0
        assert len(diff.persistent_findings) == 3
        assert diff.verdict.passed is True

    def test_diff_detects_new_findings(self, sample_baseline_result, sample_current_result):
        diff = DiffService.compare(sample_baseline_result, sample_current_result)
        assert len(diff.new_findings) == 1
        new_f = diff.new_findings[0]
        assert new_f.rule_id == "MODEL_BIDIRECTIONAL"
        assert new_f.state == "NEW"
        assert "Dates" in new_f.location

    def test_diff_detects_resolved_findings(self, sample_baseline_result, sample_current_result):
        diff = DiffService.compare(sample_baseline_result, sample_current_result)
        assert len(diff.resolved_findings) == 1
        res_f = diff.resolved_findings[0]
        assert res_f.rule_id == "DAX_UNUSED_MEASURE"
        assert res_f.state == "RESOLVED"
        assert "Total Revenue" in res_f.location

    def test_diff_detects_severity_changes(self, sample_baseline_result, sample_current_result):
        diff = DiffService.compare(sample_baseline_result, sample_current_result)
        assert len(diff.modified_findings) == 1
        mod_f = diff.modified_findings[0]
        assert mod_f.rule_id == "DAX_EXCESSIVE_CALC_COLUMNS"
        assert mod_f.state == "MODIFIED"
        assert mod_f.baseline_severity == "MEDIUM"
        assert mod_f.severity == "HIGH"

    def test_finding_identity_normalization(self):
        id1 = compute_finding_identity("m_hardcoded_data_source", "  Table:  Sales  ")
        id2 = compute_finding_identity("M_HARDCODED_DATA_SOURCE", "Table: Sales")
        assert id1 == id2

    def test_finding_identity_collision_protection(self):
        id_sales = compute_finding_identity("M_HARDCODED_DATA_SOURCE", "Table: Sales")
        id_orders = compute_finding_identity("M_HARDCODED_DATA_SOURCE", "Table: Orders")
        assert id_sales != id_orders

    def test_score_drift_calculation(self, sample_baseline_result, sample_current_result):
        diff = DiffService.compare(sample_baseline_result, sample_current_result)
        assert diff.score_drift.baseline_score == 85.0
        assert diff.score_drift.current_score == 79.5
        assert diff.score_drift.overall_delta == -5.5
        assert diff.score_drift.direction == "DEGRADED"
        assert diff.score_drift.category_deltas["model"] == -5.0
        assert diff.score_drift.category_deltas["dax"] == -5.0
        assert diff.score_drift.category_deltas["report"] == 0.0

    def test_category_drift_improved(self, sample_baseline_result):
        improved = ScanResult(
            report_name="Sales_Report",
            source_path="Sales_Report.pbip",
            report=None,
            issues=[],
            scores={"overall": 100.0, "category_scores": {"model": 100, "dax": 100, "report": 100}},
            config={},
        )
        diff = DiffService.compare(sample_baseline_result, improved)
        assert diff.score_drift.overall_delta == 15.0
        assert diff.score_drift.direction == "IMPROVED"
        assert diff.score_drift.category_deltas["model"] == 20.0
        assert len(diff.resolved_findings) == 3


class TestQualityGatePolicies:
    """Test policy evaluation and failure triggers."""

    def test_fail_on_regression_triggers_on_score_drop(self, sample_baseline_result, sample_current_result):
        policy = QualityGatePolicy(fail_on_regression=True)
        diff = DiffService.compare(sample_baseline_result, sample_current_result, policy=policy)
        assert diff.verdict.passed is False
        assert any("regressed" in r for r in diff.verdict.reasons)

    def test_fail_on_regression_passes_on_improvement(self, sample_baseline_result):
        improved = ScanResult(
            report_name="Sales",
            source_path="Sales.pbip",
            report=None,
            issues=[],
            scores={"overall": 95.0, "category_scores": {}},
            config={},
        )
        policy = QualityGatePolicy(fail_on_regression=True)
        diff = DiffService.compare(sample_baseline_result, improved, policy=policy)
        assert diff.verdict.passed is True

    def test_max_score_drop_threshold(self, sample_baseline_result, sample_current_result):
        # Delta is -5.5
        policy_strict = QualityGatePolicy(max_score_drop=3.0)
        diff_strict = DiffService.compare(sample_baseline_result, sample_current_result, policy=policy_strict)
        assert diff_strict.verdict.passed is False

        policy_lenient = QualityGatePolicy(max_score_drop=10.0)
        diff_lenient = DiffService.compare(sample_baseline_result, sample_current_result, policy=policy_lenient)
        assert diff_lenient.verdict.passed is True

    def test_fail_on_new_severity_threshold(self, sample_baseline_result, sample_current_result):
        # New finding is WARNING
        policy_crit = QualityGatePolicy(fail_on_new="HIGH")
        diff_crit = DiffService.compare(sample_baseline_result, sample_current_result, policy=policy_crit)
        assert diff_crit.verdict.passed is True

        policy_warn = QualityGatePolicy(fail_on_new="WARNING")
        diff_warn = DiffService.compare(sample_baseline_result, sample_current_result, policy=policy_warn)
        assert diff_warn.verdict.passed is False
        assert any("MODEL_BIDIRECTIONAL" in r for r in diff_warn.verdict.reasons)

    def test_fail_on_category_regression(self, sample_baseline_result, sample_current_result):
        policy_model = QualityGatePolicy(fail_on_category_regression="model")
        diff_model = DiffService.compare(sample_baseline_result, sample_current_result, policy=policy_model)
        assert diff_model.verdict.passed is False

        policy_report = QualityGatePolicy(fail_on_category_regression="report")
        diff_report = DiffService.compare(sample_baseline_result, sample_current_result, policy=policy_report)
        assert diff_report.verdict.passed is True


class TestDiffInputParity:
    """Test PBIP vs JSON vs Dict parity across DiffService."""

    def test_json_artifact_vs_json_artifact(self, sample_baseline_result, sample_current_result, tmp_path):
        base_file = tmp_path / "baseline.json"
        curr_file = tmp_path / "current.json"

        base_file.write_text(sample_baseline_result.to_json(), encoding="utf-8")
        curr_file.write_text(sample_current_result.to_json(), encoding="utf-8")

        diff = DiffService.compare(base_file, curr_file)
        assert diff.score_drift.overall_delta == -5.5
        assert len(diff.new_findings) == 1
        assert len(diff.resolved_findings) == 1

    def test_pbip_vs_json_parity(self, tmp_path):
        fixture_path = GOLDEN_DIR / "test_calc_group_variants"
        scan_res = ScanService.execute_scan(fixture_path)

        json_file = tmp_path / "saved_scan.json"
        json_file.write_text(scan_res.to_json(), encoding="utf-8")

        # Diff PBIP with its own JSON export must yield 0 delta and 100% persistent findings
        diff = DiffService.compare(fixture_path, json_file)
        assert diff.score_drift.overall_delta == 0.0
        assert len(diff.new_findings) == 0
        assert len(diff.resolved_findings) == 0
        assert len(diff.persistent_findings) == len(scan_res.unsuppressed_issues)

    def test_pbip_vs_pbip_directory_diff(self):
        fixture1 = GOLDEN_DIR / "test_calc_group_variants"
        fixture2 = GOLDEN_DIR / "test_field_parameter_variants"

        diff = DiffService.compare(fixture1, fixture2)
        assert isinstance(diff.score_drift.overall_delta, float)
        assert isinstance(diff.transitions, list)


class TestDiffRenderers:
    """Test Console and Markdown renderers."""

    def test_console_renderer_output_structure(self, sample_baseline_result, sample_current_result):
        diff = DiffService.compare(sample_baseline_result, sample_current_result)
        rendered = DiffConsoleRenderer().render(diff)
        assert "PBIP SENTINEL DIFF" in rendered
        assert "Health Score" in rendered
        assert "Category Drift" in rendered
        assert "NEW" in rendered
        assert "RESOLVED" in rendered
        assert "PERSISTENT" in rendered
        assert "Quality Gate" in rendered

    def test_markdown_renderer_output_structure(self, sample_baseline_result, sample_current_result):
        diff = DiffService.compare(sample_baseline_result, sample_current_result)
        rendered = DiffMarkdownRenderer().render(diff)
        assert "## PBIP Sentinel Scan Diff" in rendered
        assert "### 📊 Health Score Drift" in rendered
        assert "### 🔍 Finding Transitions" in rendered
        assert "QUALITY GATE:" in rendered


class TestCliDiffCommand:
    """Test CLI pbiscan diff exit codes, options, and outputs."""

    def test_cli_diff_pass_exit_code_0(self, tmp_path):
        runner = CliRunner()
        fixture = GOLDEN_DIR / "test_calc_group_variants"

        result = runner.invoke(main, ["diff", str(fixture), str(fixture)])
        assert result.exit_code == 0
        assert "PBIP SENTINEL DIFF" in result.output
        assert "PASS" in result.output

    def test_cli_diff_fail_on_regression_exit_code_1(self, sample_baseline_result, sample_current_result, tmp_path):
        runner = CliRunner()
        base_f = tmp_path / "base.json"
        curr_f = tmp_path / "curr.json"
        base_f.write_text(sample_baseline_result.to_json(), encoding="utf-8")
        curr_f.write_text(sample_current_result.to_json(), encoding="utf-8")

        result = runner.invoke(main, ["diff", str(base_f), str(curr_f), "--fail-on-regression"])
        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_cli_diff_invalid_path_exit_code_2(self):
        runner = CliRunner()
        result = runner.invoke(main, ["diff", "nonexistent_base.json", "nonexistent_curr.json"])
        assert result.exit_code == 2

    def test_cli_diff_save_json_output(self, tmp_path):
        runner = CliRunner()
        fixture = GOLDEN_DIR / "test_calc_group_variants"
        out_json = tmp_path / "diff_out.json"

        result = runner.invoke(main, ["diff", str(fixture), str(fixture), "--format", "json", "--out", str(out_json)])
        assert result.exit_code == 0
        assert out_json.exists()
        data = json.loads(out_json.read_text(encoding="utf-8"))
        assert "score_drift" in data
        assert "transitions" in data

    def test_cli_diff_save_markdown_output(self, tmp_path):
        runner = CliRunner()
        fixture = GOLDEN_DIR / "test_calc_group_variants"
        out_md = tmp_path / "diff_out.md"

        result = runner.invoke(main, ["diff", str(fixture), str(fixture), "--format", "markdown", "--out", str(out_md)])
        assert result.exit_code == 0
        assert out_md.exists()
        content = out_md.read_text(encoding="utf-8")
        assert "PBIP Sentinel Scan Diff" in content


class TestApiDiffEndpoint:
    """Test FastAPI /api/diff endpoint."""

    def test_api_diff_success(self, client):
        fixture = str(GOLDEN_DIR / "test_calc_group_variants")
        resp = client.post(
            "/api/diff",
            json={
                "baseline_path": fixture,
                "current_path": fixture,
                "fail_on_regression": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "score_drift" in data
        assert "transitions" in data
        assert data["quality_gate"]["passed"] is True

    def test_api_diff_nonexistent_path_returns_404(self, client):
        resp = client.post(
            "/api/diff",
            json={
                "baseline_path": "non_existent_folder_1",
                "current_path": "non_existent_folder_2",
            },
        )
        assert resp.status_code == 404


class TestDirectRuleExecutionSafety:
    """Verify that diff engine does NOT invoke rules directly outside ScanService."""

    def test_no_direct_rule_execution_in_diff_module(self):
        import pbiscan.diff as diff_mod
        code = Path(diff_mod.__file__).read_text(encoding="utf-8")
        assert "MODEL_RULES" not in code
        assert "DAX_RULES" not in code
        assert "REPORT_RULES" not in code
        assert "ScanService.execute_scan" in code


class TestAdversarialDiffHardening:
    """Adversarial and boundary test cases for diff engine resilience."""

    def test_adversarial_whitespace_and_casing_resilience(self):
        id1 = compute_finding_identity("m_hardcoded_data_source", "Table:   Sales \n")
        id2 = compute_finding_identity("M_HARDCODED_DATA_SOURCE", "  table: sales  ")
        assert id1 == id2

    def test_adversarial_same_location_different_rules_no_collision(self):
        id_unused = compute_finding_identity("DAX_UNUSED_MEASURE", "Measure: Total Sales")
        id_suspicious = compute_finding_identity("DAX_SUSPICIOUS_PATTERN", "Measure: Total Sales")
        assert id_unused != id_suspicious

    def test_adversarial_same_rule_different_locations_no_collision(self):
        id1 = compute_finding_identity("M_HARDCODED_DATA_SOURCE", "Table: Orders")
        id2 = compute_finding_identity("M_HARDCODED_DATA_SOURCE", "Table: OrderDetails")
        assert id1 != id2

    def test_adversarial_suppressed_findings_excluded_from_transitions(self):
        base_issue = AuditIssue(
            rule_id="M_HARDCODED_DATA_SOURCE",
            category="model",
            severity="HIGH",
            title="Hardcoded",
            issue="Path",
            evidence="Path",
            impact="Impact",
            recommendation="Rec",
            confidence=100,
            location="Table: Sales",
            suppressed=True,
            suppression_reason="Accepted risk",
        )
        curr_issue = AuditIssue(
            rule_id="M_HARDCODED_DATA_SOURCE",
            category="model",
            severity="HIGH",
            title="Hardcoded",
            issue="Path",
            evidence="Path",
            impact="Impact",
            recommendation="Rec",
            confidence=100,
            location="Table: Sales",
            suppressed=False,
        )

        base_res = ScanResult("Rep", "path", None, [base_issue], {"overall": 100.0}, {})
        curr_res = ScanResult("Rep", "path", None, [curr_issue], {"overall": 90.0}, {})

        diff = DiffService.compare(base_res, curr_res)
        # Because base_issue was suppressed, unsuppressed_issues in baseline is empty, so curr_issue is NEW
        assert len(diff.new_findings) == 1
        assert diff.new_findings[0].state == "NEW"

    def test_adversarial_malformed_json_raises_clean_error(self, tmp_path):
        bad_json = tmp_path / "corrupted.json"
        bad_json.write_text("{\ninvalid_json: 123,", encoding="utf-8")
        good_res = ScanResult("Rep", "path", None, [], {"overall": 100.0}, {})

        with pytest.raises(ValueError) as excinfo:
            DiffService.compare(bad_json, good_res)
        assert "Invalid or malformed JSON artifact" in str(excinfo.value)

    def test_adversarial_non_dict_json_raises_clean_error(self, tmp_path):
        array_json = tmp_path / "array.json"
        array_json.write_text("[1, 2, 3]", encoding="utf-8")
        good_res = ScanResult("Rep", "path", None, [], {"overall": 100.0}, {})

        with pytest.raises(ValueError) as excinfo:
            DiffService.compare(array_json, good_res)
        assert "dictionary object" in str(excinfo.value)


class TestCiCdWorkflowScenarios:
    """Simulate real-world GitHub / Azure DevOps CI/CD pipeline pull-request decisions."""

    def test_ci_cd_pr_introducing_new_high_finding_fails_gate(self, sample_baseline_result, tmp_path):
        runner = CliRunner()
        base_file = tmp_path / "main_branch_scan.json"
        curr_file = tmp_path / "pr_branch_scan.json"

        # Baseline: score 85.0
        base_file.write_text(sample_baseline_result.to_json(), encoding="utf-8")

        # PR adds a new HIGH finding
        pr_result = ScanResult(
            report_name="Sales_Report",
            source_path="Sales_Report.pbip",
            report=None,
            issues=sample_baseline_result.issues + [
                AuditIssue(
                    rule_id="M_HARDCODED_DATA_SOURCE",
                    category="model",
                    severity="HIGH",
                    title="New Hardcoded Source",
                    issue="Local Path",
                    evidence="D:/dev/secret.xlsx",
                    impact="Refresh failure",
                    recommendation="Fix",
                    confidence=100,
                    location="Table: SecretData",
                )
            ],
            scores={"overall": 75.0, "category_scores": {"model": 70, "dax": 85, "report": 100}},
            config={},
        )
        curr_file.write_text(pr_result.to_json(), encoding="utf-8")

        # CI command: fail on new HIGH
        result = runner.invoke(main, ["diff", str(base_file), str(curr_file), "--fail-on-new", "HIGH"])
        assert result.exit_code == 1
        assert "FAIL" in result.output
        assert "New Hardcoded Source" in result.output or "M_HARDCODED_DATA_SOURCE" in result.output

    def test_ci_cd_pr_resolving_all_findings_passes_gate(self, sample_baseline_result, tmp_path):
        runner = CliRunner()
        base_file = tmp_path / "main_branch_scan.json"
        curr_file = tmp_path / "pr_branch_scan.json"

        base_file.write_text(sample_baseline_result.to_json(), encoding="utf-8")

        # PR fixes all issues -> clean 100.0 score
        clean_result = ScanResult(
            report_name="Sales_Report",
            source_path="Sales_Report.pbip",
            report=None,
            issues=[],
            scores={"overall": 100.0, "category_scores": {"model": 100, "dax": 100, "report": 100}},
            config={},
        )
        curr_file.write_text(clean_result.to_json(), encoding="utf-8")

        # CI command: fail on regression
        result = runner.invoke(main, ["diff", str(base_file), str(curr_file), "--fail-on-regression"])
        assert result.exit_code == 0
        assert "PASS" in result.output
        assert "RESOLVED" in result.output

    def test_ci_cd_pr_with_allowable_score_drop_passes_gate(self, sample_baseline_result, tmp_path):
        runner = CliRunner()
        base_file = tmp_path / "base.json"
        curr_file = tmp_path / "curr.json"

        # Baseline: 85.0
        base_file.write_text(sample_baseline_result.to_json(), encoding="utf-8")

        # Current: 83.5 (drop of 1.5 points)
        curr_res = ScanResult(
            report_name="Sales",
            source_path="Sales.pbip",
            report=None,
            issues=sample_baseline_result.issues,
            scores={"overall": 83.5, "category_scores": {}},
            config={},
        )
        curr_file.write_text(curr_res.to_json(), encoding="utf-8")

        # CI allows up to 2.0 point drop
        result = runner.invoke(main, ["diff", str(base_file), str(curr_file), "--max-score-drop", "2.0"])
        assert result.exit_code == 0
        assert "PASS" in result.output

    def test_ci_cd_pr_exceeding_max_score_drop_fails_gate(self, sample_baseline_result, tmp_path):
        runner = CliRunner()
        base_file = tmp_path / "base.json"
        curr_file = tmp_path / "curr.json"

        # Baseline: 85.0
        base_file.write_text(sample_baseline_result.to_json(), encoding="utf-8")

        # Current: 80.0 (drop of 5.0 points)
        curr_res = ScanResult(
            report_name="Sales",
            source_path="Sales.pbip",
            report=None,
            issues=sample_baseline_result.issues,
            scores={"overall": 80.0, "category_scores": {}},
            config={},
        )
        curr_file.write_text(curr_res.to_json(), encoding="utf-8")

        # CI allows up to 2.0 point drop
        result = runner.invoke(main, ["diff", str(base_file), str(curr_file), "--max-score-drop", "2.0"])
        assert result.exit_code == 1
        assert "FAIL" in result.output
        assert "maximum allowed drop" in result.output

