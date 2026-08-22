"""Unit tests — report rules R001 and R002."""
from __future__ import annotations
from pbiscan.canonical.model import CanonicalReport, DaxDictionary, ModelGraph, Page, ReportDOM, Visual
from pbiscan.rules.report import check_visual_bloat, check_slicer_bloat, REPORT_RULES


def _make_report(pages) -> CanonicalReport:
    return CanonicalReport(
        model=ModelGraph(),
        dax=DaxDictionary(),
        report=ReportDOM(pages=pages),
    )


def _page(n_visuals=0, n_slicers=0, hidden=False, name="P1") -> Page:
    visuals = [Visual(visual_type="barChart", page=name) for _ in range(n_visuals)]
    visuals += [Visual(visual_type="slicer", page=name) for _ in range(n_slicers)]
    return Page(name=name, display_name=name, visibility=1 if hidden else 0, visuals=visuals)


# ---------------------------------------------------------------------------
# R001 — visual bloat
# ---------------------------------------------------------------------------
class TestCheckVisualBloat:
    def test_at_threshold_no_finding(self):
        r = _make_report([_page(n_visuals=15)])
        assert check_visual_bloat(r, max_visuals=15) == []

    def test_one_above_threshold_fires(self):
        r = _make_report([_page(n_visuals=16)])
        findings = check_visual_bloat(r, max_visuals=15)
        assert len(findings) == 1
        assert findings[0].rule_id == "REPORT_VISUAL_BLOAT"
        assert findings[0].confidence == 100

    def test_hidden_page_excluded(self):
        r = _make_report([_page(n_visuals=20, hidden=True)])
        assert check_visual_bloat(r, max_visuals=15) == []

    def test_slicers_count_toward_total(self):
        r = _make_report([_page(n_visuals=10, n_slicers=6)])
        findings = check_visual_bloat(r, max_visuals=15)
        assert len(findings) == 1  # 16 total > 15

    def test_multiple_pages_independent(self):
        pages = [_page(n_visuals=16, name="P1"), _page(n_visuals=16, name="P2")]
        r = _make_report(pages)
        assert len(check_visual_bloat(r, max_visuals=15)) == 2

    def test_one_page_over_one_under(self):
        pages = [_page(n_visuals=16, name="P1"), _page(n_visuals=5, name="P2")]
        r = _make_report(pages)
        assert len(check_visual_bloat(r, max_visuals=15)) == 1

    def test_location_mentions_page(self):
        r = _make_report([_page(n_visuals=16, name="Sales")])
        f = check_visual_bloat(r, max_visuals=15)[0]
        assert "Sales" in f.location


# ---------------------------------------------------------------------------
# R002 — slicer bloat
# ---------------------------------------------------------------------------
class TestCheckSlicerBloat:
    def test_at_threshold_no_finding(self):
        r = _make_report([_page(n_slicers=6)])
        assert check_slicer_bloat(r, max_slicers=6) == []

    def test_one_above_threshold_fires(self):
        r = _make_report([_page(n_slicers=7)])
        findings = check_slicer_bloat(r, max_slicers=6)
        assert len(findings) == 1
        assert findings[0].rule_id == "REPORT_SLICER_BLOAT"
        assert findings[0].confidence == 100

    def test_hidden_page_excluded(self):
        r = _make_report([_page(n_slicers=10, hidden=True)])
        assert check_slicer_bloat(r, max_slicers=6) == []

    def test_non_slicer_visuals_not_counted(self):
        r = _make_report([_page(n_visuals=20, n_slicers=4)])
        assert check_slicer_bloat(r, max_slicers=6) == []

    def test_evidence_mentions_count(self):
        r = _make_report([_page(n_slicers=7, name="Overview")])
        f = check_slicer_bloat(r, max_slicers=6)[0]
        assert "7" in f.evidence
        assert "6" in f.evidence  # threshold mentioned


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def test_report_rules_registry():
    assert len(REPORT_RULES) == 2
