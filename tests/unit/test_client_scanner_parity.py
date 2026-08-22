"""Cross-engine parity between the Python ScanService and the browser-side
clientScanner.ts (used by the Netlify in-browser Studio Workbench).

The two engines must agree on which rule_ids fire for a given project, or the
in-browser demo silently shows different findings/scores than `pbiscan scan`.
This test builds clientScanner.ts to a small Node CLI harness with esbuild and
diffs its output against ScanService for every golden fixture.

Known gap (tracked, not a regression): clientScanner.ts does not implement the
Python engine's DAX dependency graph or Unified Semantic Reference Index
(calc group SELECTEDMEASURE bindings, field parameter tables, RLS filter
expressions, and PBIR nested `objects.*` expression traversal). This means
DAX_UNUSED_MEASURE counts can diverge on fixtures that exercise those features
— TS treats a measure as "used" only via a one-hop reference from another
measure or a naive visual-reference-bracket scan. Full parity there requires
porting DaxDependencyGraph + SemanticReferenceIndex to TypeScript, which is
out of scope for this test. Every OTHER rule_id must match exactly.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pbiscan.service import ScanService

REPO_ROOT = Path(__file__).parent.parent.parent
STUDIO_UI_DIR = REPO_ROOT / "studio-ui"
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
HARNESS_SRC = STUDIO_UI_DIR / "scripts" / "parityHarness.ts"
HARNESS_BUNDLE = STUDIO_UI_DIR / "scripts" / "dist" / "parityHarness.cjs"

ESBUILD_SCRIPT = STUDIO_UI_DIR / "node_modules" / "esbuild" / "bin" / "esbuild"

NODE_AVAILABLE = shutil.which("node") is not None
NODE_MODULES_PRESENT = ESBUILD_SCRIPT.exists()

pytestmark = pytest.mark.skipif(
    not (NODE_AVAILABLE and NODE_MODULES_PRESENT),
    reason="Node or studio-ui node_modules (esbuild) not available — skipping cross-engine parity test",
)

# rule_ids intentionally excluded from the equality check for these fixtures,
# because they exercise the DAX reachability gap described above.
KNOWN_DAX_REACHABILITY_GAP_FIXTURES = {
    "test_calc_group_variants",
    "test_calc_groups_selectedmeasure",
    "test_dax_graph_cycle",
    "test_deep_dax_dependency_tree",
    "test_directquery_composite_storage",
    "test_enterprise_diamond_topology",
    "test_field_parameter_variants",
    "test_field_parameters_usage",
    "test_pbir_objects_references",
    "test_rls_ols_security",
    "test_rls_variants",
}


@pytest.fixture(scope="module", autouse=True)
def build_harness():
    """Bundle parityHarness.ts once per test session with esbuild.

    Invokes node_modules/esbuild/bin/esbuild directly via `node` rather than
    through `npm run` — npm/npx's own package-bin resolution breaks when the
    repo path contains an `&` (as this one does), even though the underlying
    esbuild script runs fine when invoked directly.
    """
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

    if fixture_dir.name in KNOWN_DAX_REACHABILITY_GAP_FIXTURES:
        py_rule_ids = [r for r in py_rule_ids if r != "DAX_UNUSED_MEASURE"]
        ts_rule_ids = [r for r in ts_rule_ids if r != "DAX_UNUSED_MEASURE"]

    assert ts_rule_ids == py_rule_ids, (
        f"clientScanner.ts diverges from ScanService on {fixture_dir.name}\n"
        f"  python: {py_rule_ids}\n"
        f"  ts:     {ts_rule_ids}"
    )
