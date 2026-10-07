"""The HTML export is a static document: no scripts, findings ordered like Studio."""
from __future__ import annotations

import re
from pathlib import Path

from pbiscan.engine.issue import AuditIssue
from pbiscan.render.html_report import HtmlRenderer, grade
from pbiscan.service import ScanService

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


def _issue(rule_id: str, severity: str, confidence: int = 90, **kw) -> AuditIssue:
    return AuditIssue(
        rule_id=rule_id, category=kw.pop("category", "dax"), severity=severity, title=f"{rule_id} title",
        issue="issue", evidence="evidence", impact="impact", recommendation="fix", confidence=confidence, **kw,
    )


def _render(issues, warnings=None) -> str:
    scores = {"overall": 72.5, "category_scores": {"model": 90.0, "dax": 55.0, "report": 100.0}}
    meta = {"report_name": "Sales", "scanner_version": "x", "source_path": "/p", "scan_timestamp": "now"}
    return HtmlRenderer().render(issues=issues, scores=scores, meta=meta, warnings=warnings)


def test_export_needs_no_javascript():
    html = ScanService.execute_scan(GOLDEN_DIR / "test_enterprise_stress").to_html(timestamp="t")
    assert "<script" not in html.lower()
    assert not re.search(r"\son[a-z]+\s*=", html), "inline event handlers need JavaScript"


def test_findings_are_ordered_most_severe_then_most_confident():
    html = _render([
        _issue("ADV", "ADVISORY", 95),
        _issue("MED_LOW_CONF", "MEDIUM", 60),
        _issue("CRIT", "CRITICAL"),
        _issue("MED_HIGH_CONF", "MEDIUM", 99),
    ])
    order = [m for m in re.findall(r"<span>([A-Z_]+)</span><span>·", html)]
    assert order == ["CRIT", "MED_HIGH_CONF", "MED_LOW_CONF", "ADV"]


def test_suppressed_findings_are_listed_apart_and_not_counted_as_open():
    html = _render([
        _issue("OPEN", "HIGH"),
        _issue("HUSHED", "CRITICAL", suppressed=True, suppression_reason="Accepted risk"),
    ])
    assert "1 open finding · 1 suppressed" in html
    findings, suppressed = html.split("<h2>Suppressed")
    assert "OPEN title" in findings and "HUSHED title" not in findings
    assert "HUSHED title" in suppressed and "Suppressed: Accepted risk" in suppressed


def test_scores_grade_warnings_and_escaping():
    html = _render([_issue("<b>X</b>", "LOW")], warnings=["Skipped a.tmdl"])
    assert ">72.5<" in html and ">C<" in html and ">55.0<" in html
    assert "Skipped a.tmdl" in html
    assert "&lt;b&gt;X&lt;/b&gt;" in html and "<b>X</b>" not in html


def test_empty_report():
    assert "No open findings" in _render([])


def test_grade_boundaries():
    assert [grade(s) for s in (100, 90, 89.9, 80, 70, 60, 59.9)] == ["A", "A", "B", "B", "C", "D", "F"]
