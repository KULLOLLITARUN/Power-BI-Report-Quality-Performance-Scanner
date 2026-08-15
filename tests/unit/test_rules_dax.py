"""Unit tests — DAX rules D001–D004."""
from __future__ import annotations
import pytest
from pbiscan.canonical.model import (
    CanonicalReport, CalculatedColumn, DaxDictionary,
    Measure, ModelGraph, Page, ReportDOM, Table, Visual,
)
from pbiscan.rules.dax import (
    check_suspicious_dax, check_excessive_calc_columns,
    check_duplicate_measures, check_unused_measures,
    _normalise_expression, DAX_RULES,
)


def _make_report(measures=None, calc_cols=None, pages=None) -> CanonicalReport:
    return CanonicalReport(
        model=ModelGraph(),
        dax=DaxDictionary(
            measures=measures or [],
            calculated_columns=calc_cols or [],
        ),
        report=ReportDOM(pages=pages or []),
    )


def _measure(name, expr, table="Sales") -> Measure:
    return Measure(name=name, table=table, expression=expr)


def _page_with_measures(*measure_names) -> Page:
    visuals = [
        Visual(
            visual_type="barChart", page="P",
            measure_refs=list(measure_names),
        )
    ]
    return Page(name="P", display_name="Page", visuals=visuals)


# ---------------------------------------------------------------------------
# D001 — suspicious DAX
# ---------------------------------------------------------------------------
class TestCheckSuspiciousDax:
    def test_detects_filter_all(self):
        m = _measure("Rev", "CALCULATE(SUM(Sales[Amount]), FILTER(ALL(Sales), Sales[Amount] > 0))")
        r = _make_report(measures=[m], pages=[_page_with_measures("Rev")])
        findings = check_suspicious_dax(r)
        assert len(findings) == 1
        assert findings[0].rule_id == "DAX_SUSPICIOUS_PATTERN"
        assert findings[0].confidence <= 65

    def test_detects_earlier(self):
        m = _measure("Rank", "EARLIER(Sales[Amount])")
        r = _make_report(measures=[m], pages=[_page_with_measures("Rank")])
        findings = check_suspicious_dax(r)
        assert len(findings) == 1

    def test_clean_measure_no_finding(self):
        m = _measure("Rev", "SUM(Sales[Amount])")
        r = _make_report(measures=[m], pages=[_page_with_measures("Rev")])
        assert check_suspicious_dax(r) == []

    def test_one_finding_per_measure(self):
        """A measure matching multiple patterns should produce one finding."""
        m = _measure(
            "Complex",
            "CALCULATE(SUM(Sales[Amount]), FILTER(ALL(Sales), EARLIER(Sales[A]) > 0))"
        )
        r = _make_report(measures=[m], pages=[_page_with_measures("Complex")])
        assert len(check_suspicious_dax(r)) == 1

    def test_case_insensitive(self):
        m = _measure("Rev", "filter(all(Sales), Sales[A] > 0)")
        r = _make_report(measures=[m], pages=[_page_with_measures("Rev")])
        assert len(check_suspicious_dax(r)) == 1


# ---------------------------------------------------------------------------
# D002 — excessive calculated columns
# ---------------------------------------------------------------------------
class TestCheckExcessiveCalcColumns:
    def test_fires_above_threshold(self):
        calc_cols = [
            CalculatedColumn(name=f"CC{i}", table="Sales", expression=f"Sales[Amount] * {i}")
            for i in range(5)
        ]
        r = _make_report(calc_cols=calc_cols)
        findings = check_excessive_calc_columns(r, threshold=4)
        assert len(findings) == 1
        assert findings[0].rule_id == "DAX_EXCESSIVE_CALC_COLUMNS"
        assert findings[0].confidence == 100

    def test_at_threshold_no_finding(self):
        calc_cols = [
            CalculatedColumn(name=f"CC{i}", table="Sales", expression=f"Sales[Amount]")
            for i in range(4)
        ]
        r = _make_report(calc_cols=calc_cols)
        assert check_excessive_calc_columns(r, threshold=4) == []

    def test_different_tables_independent(self):
        calc_cols = [
            CalculatedColumn(name=f"CC{i}", table="TableA", expression="x") for i in range(5)
        ] + [
            CalculatedColumn(name=f"CC{i}", table="TableB", expression="x") for i in range(5)
        ]
        r = _make_report(calc_cols=calc_cols)
        findings = check_excessive_calc_columns(r, threshold=4)
        assert len(findings) == 2  # both tables over threshold


# ---------------------------------------------------------------------------
# D003 — duplicate measures
# ---------------------------------------------------------------------------
class TestCheckDuplicateMeasures:
    def test_detects_identical_expressions(self):
        measures = [
            _measure("Total Revenue", "SUM(Sales[Amount])"),
            _measure("Revenue Total", "SUM(Sales[Amount])"),
        ]
        r = _make_report(measures=measures)
        findings = check_duplicate_measures(r)
        assert len(findings) == 1
        assert findings[0].rule_id == "DAX_DUPLICATE_MEASURE"
        assert findings[0].confidence == 90

    def test_detects_normalised_duplicates(self):
        """Whitespace differences should not prevent detection."""
        measures = [
            _measure("M1", "SUM(Sales[Amount])"),
            _measure("M2", "SUM( Sales[Amount] )"),
        ]
        r = _make_report(measures=measures)
        assert len(check_duplicate_measures(r)) == 1

    def test_distinct_expressions_no_finding(self):
        measures = [
            _measure("Revenue", "SUM(Sales[Amount])"),
            _measure("Cost", "SUM(Sales[Cost])"),
        ]
        r = _make_report(measures=measures)
        assert check_duplicate_measures(r) == []

    def test_normalise_strips_comments(self):
        e1 = "-- my measure\nSUM(Sales[Amount])"
        e2 = "SUM(Sales[Amount])"
        assert _normalise_expression(e1) == _normalise_expression(e2)


# ---------------------------------------------------------------------------
# D004 — unused measures (including critical negative)
# ---------------------------------------------------------------------------
class TestCheckUnusedMeasures:
    def test_detects_unused(self):
        measures = [
            _measure("Total Revenue", "SUM(Sales[Amount])"),
            _measure("Unused", "SUM(Sales[Amount]) * 2"),
        ]
        r = _make_report(
            measures=measures,
            pages=[_page_with_measures("Total Revenue")],  # Unused not in visual
        )
        findings = check_unused_measures(r)
        assert len(findings) == 1
        assert findings[0].rule_id == "DAX_UNUSED_MEASURE"
        assert "Unused" in findings[0].evidence

    def test_no_finding_when_all_used(self):
        measures = [_measure("Total Revenue", "SUM(Sales[Amount])")]
        r = _make_report(
            measures=measures,
            pages=[_page_with_measures("Total Revenue")],
        )
        assert check_unused_measures(r) == []

    def test_critical_negative_referenced_by_another(self):
        """CRITICAL: A measure referenced by another measure must NOT be flagged.

        Base Revenue is not in any visual.
        Revenue Per Unit references [Base Revenue] and IS in a visual.
        Expected: D004 = 0 for both measures.
        """
        measures = [
            _measure("Base Revenue", "SUM(Sales[Amount])"),
            _measure("Revenue Per Unit", "[Base Revenue] / SUM(Sales[Units])"),
        ]
        r = _make_report(
            measures=measures,
            pages=[_page_with_measures("Revenue Per Unit")],
        )
        findings = check_unused_measures(r)
        unused_names = [f.location for f in findings]
        assert "Measure: Base Revenue" not in unused_names, (
            "Base Revenue must not be flagged — it is referenced by Revenue Per Unit"
        )
        # Revenue Per Unit is in a visual, also must not be flagged
        assert "Measure: Revenue Per Unit" not in unused_names
        assert findings == [], f"Expected 0 findings, got: {findings}"

    def test_case_insensitive_visual_matching(self):
        """Measure ref lookup must be case-insensitive."""
        measures = [_measure("Total Revenue", "SUM(Sales[Amount])")]
        page = Page(name="P", visuals=[
            Visual(visual_type="card", page="P", measure_refs=["total revenue"])
        ])
        r = _make_report(measures=measures, pages=[page])
        assert check_unused_measures(r) == []

    def test_empty_report_all_unused(self):
        """No pages → all measures are unused."""
        measures = [_measure("M", "SUM(Sales[Amount])")]
        r = _make_report(measures=measures, pages=[])
        findings = check_unused_measures(r)
        assert len(findings) == 1


# ---------------------------------------------------------------------------
# Registry test
# ---------------------------------------------------------------------------
def test_dax_rules_registry():
    assert len(DAX_RULES) == 4
