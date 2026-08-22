"""Automated continuous regression test for real-world PBIP corpus.

Validates that real customer models scan without unhandled exceptions,
and that finding counts, score metrics, and active root counts remain deterministic.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from pbiscan.service import ScanService

REPO_ROOT = Path(__file__).parent.parent.parent

# In-repo tracked model
IN_REPO_MODELS = [
    REPO_ROOT / "pbip_project" / "world is going bananas.pbip",
]

# Optional local workstation corpus (if present)
WORKSTATION_MODELS = [
    Path(r"C:\Users\TARUN\Downloads\Financial_Report_PBIP\Financial_Report.pbip"),
    Path(r"C:\Users\TARUN\Downloads\HR_Analysis_PBIP\HR_Analysis_Dashboard.pbip"),
    Path(r"C:\Users\TARUN\Downloads\sales analysis - mirgrated\sales_analysis.pbip"),
    Path(r"C:\Users\TARUN\Downloads\TermAidReport_PBIV\TermAidReport_PBIV.pbip"),
    Path(r"C:\Users\TARUN\Downloads\Test\1761793292566_02 email communication report challenge.pbip"),
    Path(r"C:\Users\TARUN\Downloads\test2\1767842152777_1765180280123_03 Xmas Sales.pbip"),
    Path(r"C:\Users\TARUN\Downloads\test3\1756112919049_AC_Sales_Dashboard_adediran_a.pbip"),
    Path(r"C:\Users\TARUN\Downloads\test5\1756112919049_AC_Sales_Dashboard_ajay_s.pbip"),
    Path(r"C:\Users\TARUN\Downloads\test6\1760515551828_zepto.pbip"),
    Path(r"C:\Users\TARUN\Downloads\test7\Spotify_Dashboard.pbip"),
]


class TestRealWorldCorpusRegression:
    """Continuous automated regression test for real customer PBIP projects."""

    @pytest.mark.parametrize("model_path", IN_REPO_MODELS, ids=lambda p: p.stem)
    def test_in_repo_model_scan_stability(self, model_path: Path):
        """Verify the in-repo customer PBIP model executes cleanly and deterministically."""
        if not model_path.exists():
            pytest.skip(f"Model not found: {model_path}")

        result = ScanService.execute_scan(model_path)
        assert result is not None
        assert result.report is not None
        assert len(result.issues) == 17
        assert result.overall_score == 54.1
        assert len(result.report.model.tables) == 15
        assert len(result.report.dax.measures) == 6

    @pytest.mark.parametrize("model_path", WORKSTATION_MODELS, ids=lambda p: p.stem)
    def test_workstation_corpus_model_stability(self, model_path: Path):
        """Verify available workstation models scan without unhandled exceptions."""
        if not model_path.exists():
            pytest.skip(f"Workstation model not present on environment: {model_path.name}")

        result = ScanService.execute_scan(model_path)
        assert result is not None
        assert result.report is not None
        assert isinstance(result.overall_score, (int, float))
        assert 0.0 <= result.overall_score <= 100.0
        assert isinstance(result.issues, list)
