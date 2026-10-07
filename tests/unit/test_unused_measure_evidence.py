"""The scan output must carry enough to explain every DAX_UNUSED_MEASURE decision.

Studio's measure evidence (studio-ui/src/lib/usage.ts) recomputes "is this measure
used?" from ScanResult.to_dict()'s semantic_references.active_roots and dax_graph.
If that ever disagreed with the rule, Studio would show a flagged measure as used
(or the reverse), so this test replays the decision from the exported data alone.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pbiscan.service import ScanService

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


def _fixture_dirs() -> list[Path]:
    return sorted(p for p in GOLDEN_DIR.iterdir() if p.is_dir() and (p / "fixture.pbip").exists())


def _used_from_export(data: dict) -> dict[str, bool]:
    roots = {n.lower() for n in data["semantic_references"]["active_roots"]}
    referenced_by = {n["name"].lower(): [r.lower() for r in n["referenced_by"]] for n in data["dax_graph"]["nodes"]}

    def used(name: str) -> bool:
        seen: set[str] = set()
        stack = [name.lower()]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            if cur in roots:
                return True
            stack.extend(referenced_by.get(cur, []))
        return False

    return {m["name"]: used(m["name"]) for m in data["measures"]}


@pytest.mark.parametrize("fixture_dir", _fixture_dirs(), ids=lambda p: p.name)
def test_exported_references_reproduce_unused_measure_findings(fixture_dir: Path):
    result = ScanService.execute_scan(fixture_dir)
    data = result.to_dict()
    flagged = {i.location for i in result.issues if i.rule_id == "DAX_UNUSED_MEASURE"}
    replayed = {f"Measure: {name}" for name, is_used in _used_from_export(data).items() if not is_used}
    assert replayed == flagged


def test_fixtures_cover_flagged_and_used_measures():
    """True-positive control: the replay above is only meaningful if some fixtures flag
    measures and some measures are kept alive only through another measure."""
    flagged = through_dax = 0
    for fixture_dir in _fixture_dirs():
        data = ScanService.execute_scan(fixture_dir).to_dict()
        roots = {n.lower() for n in data["semantic_references"]["active_roots"]}
        for name, is_used in _used_from_export(data).items():
            flagged += not is_used
            through_dax += is_used and name.lower() not in roots
    assert flagged > 0
    assert through_dax > 0
