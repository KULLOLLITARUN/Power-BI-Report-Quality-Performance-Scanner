"""Golden contract tests: a measure used only inside the model itself is not unused.

`pbiscan fix` deletes what DAX_UNUSED_MEASURE reports, so each case below is a
data-loss bug if it is flagged:

- Orphan Calc Table: named only by a calculated table's expression
- Orphan Format:     only in another measure's dynamic format-string DAX
- Orphan KPI / Orphan Detail (model.bim): only in a KPI or detail-rows expression
- Margin [%]:        used as [Margin [%]]], the `]]` escape for a literal `]` in a name

Truly Unused is the true-positive control and must still be flagged.
"""
from pathlib import Path

import pytest

from pbiscan.remediation.engine import RemediationEngine
from pbiscan.service import ScanService

GOLDEN = Path(__file__).parent
BIM = GOLDEN / "test_unused_measure_model_expressions_bim"
TMDL = GOLDEN / "test_unused_measure_model_expressions_tmdl"


@pytest.fixture(scope="module", params=[BIM, TMDL], ids=["bim", "tmdl"])
def result(request):
    return ScanService.execute_scan(request.param)


def _model_expression_refs(result):
    return {
        (r.target_name, r.source_object)
        for r in result.report.semantic_references.references
        if r.source_type == "model_expression"
    }


def test_only_the_true_positive_control_is_unused(result):
    unused = {i.location for i in result.issues if i.rule_id == "DAX_UNUSED_MEASURE"}
    assert unused == {"Measure: Truly Unused"}


def test_calculated_table_expression_counts_as_a_use():
    for fixture in (BIM, TMDL):
        refs = _model_expression_refs(ScanService.execute_scan(fixture))
        assert ("Orphan Calc Table", "Summary partition") in refs


def test_bim_measure_properties_count_as_uses():
    refs = _model_expression_refs(ScanService.execute_scan(BIM))
    assert ("Orphan Format", "Sales[Total Revenue] properties") in refs
    assert ("Orphan Detail", "Sales[Total Revenue] properties") in refs
    assert ("Orphan KPI", "Sales[Revenue Filtered] properties") in refs


def test_tmdl_dynamic_format_string_is_a_dax_edge():
    edges = ScanService.execute_scan(TMDL).report.dax_graph.edges
    assert "Orphan Format" in edges["Revenue"]


def test_escaped_bracket_in_a_measure_name_is_a_dax_edge():
    edges = ScanService.execute_scan(BIM).report.dax_graph.edges
    assert "Margin [%]" in edges["Total Revenue"]


@pytest.mark.parametrize("fixture", [BIM, TMDL], ids=["bim", "tmdl"])
def test_fix_offers_to_delete_only_the_true_positive(fixture, tmp_path):
    import shutil
    project = tmp_path / "p"
    shutil.copytree(fixture, project)
    scan = RemediationEngine.analyze(project)
    plan = RemediationEngine.plan(project, scan, rule_filter="DAX_UNUSED_MEASURE")
    targets = [obj for p in plan.actionable_patches for obj in p.evidence.affected_objects]
    assert len(targets) == 1 and "Truly Unused" in targets[0], targets
