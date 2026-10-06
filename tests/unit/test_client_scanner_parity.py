"""Cross-engine parity between the Python ScanService and the browser-side
clientScanner.ts (used by the Netlify in-browser Studio Workbench).

The two engines must agree on which rule_ids fire for a given project, or the
in-browser demo silently shows different findings/scores than `pbiscan scan`.
This test builds clientScanner.ts to a small Node CLI harness with esbuild and
diffs its output against ScanService for every golden fixture.

clientScanner.ts ports the Python engine's DAX dependency graph
(studio-ui/src/engine/daxGraph.ts) and Unified Semantic Reference Index
(studio-ui/src/engine/semanticReferences.ts) — calc group calculationItem DAX,
field parameter NAMEOF() bindings, RLS tablePermission expressions, and a full
recursive PBIR `objects.*` AST walk — so DAX_UNUSED_MEASURE reachability is
computed identically on both engines, not just every other rule.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from pbiscan.engine.scoring import _SCORED_CATEGORIES, score_overall
from pbiscan.rules.catalog import RULE_CATALOG
from pbiscan.service import DEFAULT_CONFIG, ScanService

REPO_ROOT = Path(__file__).parent.parent.parent
STUDIO_UI_DIR = REPO_ROOT / "studio-ui"
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
HARNESS_SRC = STUDIO_UI_DIR / "scripts" / "parityHarness.ts"
HARNESS_BUNDLE = STUDIO_UI_DIR / "scripts" / "dist" / "parityHarness.cjs"

ESBUILD_SCRIPT = STUDIO_UI_DIR / "node_modules" / "esbuild" / "bin" / "esbuild"

NODE_AVAILABLE = shutil.which("node") is not None
NODE_MODULES_PRESENT = ESBUILD_SCRIPT.exists()

# CI sets PBISCAN_REQUIRE_PARITY=1 so a missing Node toolchain fails the run
# instead of silently skipping the only check that keeps the engines in sync.
REQUIRE_PARITY = os.environ.get("PBISCAN_REQUIRE_PARITY") == "1"

pytestmark = pytest.mark.skipif(
    not (NODE_AVAILABLE and NODE_MODULES_PRESENT) and not REQUIRE_PARITY,
    reason="Node or studio-ui node_modules (esbuild) not available — skipping cross-engine parity test",
)

@pytest.fixture(scope="module", autouse=True)
def build_harness():
    """Bundle parityHarness.ts once per test session with esbuild.

    Invokes node_modules/esbuild/bin/esbuild directly via `node` rather than
    through `npm run` — npm/npx's own package-bin resolution breaks when the
    repo path contains an `&` (as this one does), even though the underlying
    esbuild script runs fine when invoked directly.
    """
    assert NODE_AVAILABLE and NODE_MODULES_PRESENT, (
        "PBISCAN_REQUIRE_PARITY=1 but Node or studio-ui/node_modules is missing; run `npm ci` in studio-ui/"
    )
    subprocess.run(
        [
            "node", str(ESBUILD_SCRIPT),
            str(HARNESS_SRC.relative_to(STUDIO_UI_DIR)),
            "--bundle", "--platform=node", "--format=cjs",
            f"--outfile={HARNESS_BUNDLE.relative_to(STUDIO_UI_DIR)}",
        ],
        cwd=str(STUDIO_UI_DIR),
        check=True,
        capture_output=True,
        text=True,
    )
    assert HARNESS_BUNDLE.exists(), "parityHarness.cjs was not produced by the build"


def _fixture_dirs() -> list[Path]:
    return sorted(
        p for p in GOLDEN_DIR.iterdir()
        if p.is_dir() and (p / "fixture.pbip").exists()
    )


def _run_ts_scanner(fixture_dir: Path) -> dict:
    result = subprocess.run(
        ["node", str(HARNESS_BUNDLE), str(fixture_dir)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"parityHarness.cjs failed on {fixture_dir.name}: {result.stderr}"
    return json.loads(result.stdout)


@pytest.mark.parametrize("fixture_dir", _fixture_dirs(), ids=lambda p: p.name)
def test_rule_ids_match_python_engine(fixture_dir: Path):
    py_result = ScanService.execute_scan(fixture_dir)
    py_rule_ids = sorted(issue.rule_id for issue in py_result.issues)

    ts_result = _run_ts_scanner(fixture_dir)
    ts_rule_ids = ts_result["rule_ids"]

    assert ts_rule_ids == py_rule_ids, (
        f"clientScanner.ts diverges from ScanService on {fixture_dir.name}\n"
        f"  python: {py_rule_ids}\n"
        f"  ts:     {ts_rule_ids}"
    )


@pytest.mark.parametrize("fixture_dir", _fixture_dirs(), ids=lambda p: p.name)
def test_unused_measures_match_python_engine(fixture_dir: Path):
    """Same rule IDs isn't enough for D004: both engines must flag the same measures,
    since these are what `pbiscan fix` offers to delete."""
    py_unused = sorted(
        i.location for i in ScanService.execute_scan(fixture_dir).issues if i.rule_id == "DAX_UNUSED_MEASURE"
    )
    assert _run_ts_scanner(fixture_dir)["unused_measures"] == py_unused, fixture_dir.name


def test_unreadable_file_disables_unused_measures_in_both_engines(tmp_path: Path):
    """A bookmark that can't be parsed may be the only user of a measure, so neither
    engine may report unused measures for that scan, and both must say why."""
    project = tmp_path / "proj"
    shutil.copytree(GOLDEN_DIR / "test_pbir_filter_references", project)
    (project / "fixture.Report" / "definition" / "bookmarks" / "bm1.bookmark.json").write_text(
        "{not json", encoding="utf-8"
    )

    py_result = ScanService.execute_scan(project)
    ts_result = _run_ts_scanner(project)

    assert not [i for i in py_result.issues if i.rule_id == "DAX_UNUSED_MEASURE"]
    assert ts_result["unused_measures"] == []
    for warnings in (py_result.warnings, ts_result["warnings"]):
        assert any("DAX_UNUSED_MEASURE was not checked" in w for w in warnings)
        assert any("bm1.bookmark.json" in w for w in warnings)


@pytest.mark.parametrize("fixture_dir", _fixture_dirs(), ids=lambda p: p.name)
def test_finding_metadata_matches_python_engine(fixture_dir: Path):
    """Category, severity and confidence are hard-coded in clientScanner.ts;
    they must match the Python rule catalog for every finding."""
    py_findings = sorted(
        (i.rule_id, i.category, i.severity, i.confidence)
        for i in ScanService.execute_scan(fixture_dir).issues
    )
    ts_findings = sorted(tuple(f) for f in _run_ts_scanner(fixture_dir)["findings"])
    assert ts_findings == py_findings, fixture_dir.name


@pytest.mark.parametrize("fixture_dir", _fixture_dirs(), ids=lambda p: p.name)
def test_scores_match_python_engine(fixture_dir: Path):
    py_result = ScanService.execute_scan(fixture_dir, config=copy.deepcopy(DEFAULT_CONFIG))
    ts_result = _run_ts_scanner(fixture_dir)

    assert ts_result["category_scores"] == py_result.category_scores, fixture_dir.name
    assert ts_result["overall"] == py_result.overall_score, fixture_dir.name


def _py_page_layout(fixture_dir: Path) -> list:
    pages = ScanService.execute_scan(fixture_dir).to_dict().get("pages", [])
    layout = [
        [
            p["display_name"], p["width"], p["height"],
            sorted(
                ([v["visual_type"], v["x"], v["y"], v["width"], v["height"], "|".join(v["table_refs"]), v["is_slicer"]]
                 for v in p["visuals"]),
                key=lambda row: json.dumps(row, separators=(",", ":")),
            ),
        ]
        for p in pages
    ]
    return sorted(layout, key=lambda row: row[0])


@pytest.mark.parametrize("fixture_dir", _fixture_dirs(), ids=lambda p: p.name)
def test_page_layout_matches_python_engine(fixture_dir: Path):
    """Studio's report layer draws visuals from this data in both engines."""
    assert _run_ts_scanner(fixture_dir)["page_layout"] == _py_page_layout(fixture_dir), fixture_dir.name


def test_scoring_constants_match_python_defaults():
    """Every severity's deduction, scored weight and rule's catalog metadata must
    agree, including severities no current rule emits (fixtures alone would
    never catch those)."""
    result = subprocess.run(
        ["node", str(HARNESS_BUNDLE), "--scoring-constants"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    ts = json.loads(result.stdout)

    assert ts["deductions"] == DEFAULT_CONFIG["deductions"]
    assert ts["weights"] == {cat: DEFAULT_CONFIG["weights"][cat] for cat in _SCORED_CATEGORIES}
    assert ts["rules"] == {
        spec.rule_id: {"category": spec.category, "severity": spec.severity, "confidence": spec.confidence}
        for spec in RULE_CATALOG
    }


def test_overall_score_rounding_matches_python():
    """Both engines must round identically, including exact .x25/.x75 ties
    (Python rounds those half-to-even; JavaScript's toFixed rounds them up)."""
    triples = [(m, d, r) for m in range(0, 101, 3) for d in range(0, 101, 7) for r in range(0, 101, 9)]
    triples += [(99, 99, 100), (100, 98, 100), (97, 98, 100)]
    result = subprocess.run(
        ["node", str(HARNESS_BUNDLE), "--overall-scores"],
        input=json.dumps(triples), capture_output=True, text=True, timeout=30, check=True,
    )
    ts_scores = json.loads(result.stdout)
    weights = DEFAULT_CONFIG["weights"]
    mismatches = [
        (t, ts, py)
        for t, ts in zip(triples, ts_scores)
        if ts != (py := score_overall(dict(zip(_SCORED_CATEGORIES, t)), weights))
    ]
    assert not mismatches, mismatches[:10]
