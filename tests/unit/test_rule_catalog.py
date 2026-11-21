"""The rule catalog (pbiscan/rules/catalog.py) is the single source of truth.

These tests fail when the README rule table, the recommendation registry, the
MCP rules resource or the golden fixtures drift away from it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from pbiscan.engine.recommendations import RECOMMENDATIONS
from pbiscan.mcp.resources import get_rules_catalog_json
from pbiscan.rules.catalog import RULE_CATALOG, RULES_BY_ID
from pbiscan.service import ScanService

REPO_ROOT = Path(__file__).parent.parent.parent
README = REPO_ROOT / "README.md"
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"

ROW_RE = re.compile(r"^\| `(?P<rule_id>[A-Z_]+)` \| (?P<severity>[A-Za-z]+) \| (?P<confidence>\d+)% \|")
CODE_PREFIX = {"model": "M", "dax": "D", "report": "R"}


def _readme_catalog() -> dict[str, dict]:
    """Parse the README "## Rules" table: one row per rule, keyed by rule_id."""
    text = README.read_text(encoding="utf-8")
    start = re.search(r"^## Rules$", text, re.MULTILINE)
    assert start, "README is missing the '## Rules' heading"
    rules_text = text[start.end():].split("\n## ", 1)[0]

    rows: dict[str, dict] = {}
    for line in rules_text.splitlines():
        row = ROW_RE.match(line)
        if row:
            assert row["rule_id"] not in rows, f"{row['rule_id']} listed twice in README"
            rows[row["rule_id"]] = {"severity": row["severity"].upper(), "confidence": int(row["confidence"])}
    return rows


class TestReadmeTable:

    def test_lists_exactly_the_catalog_rules(self):
        assert sorted(_readme_catalog()) == sorted(RULES_BY_ID)

    @pytest.mark.parametrize("spec", RULE_CATALOG, ids=lambda s: s.rule_id)
    def test_row_matches_catalog(self, spec):
        row = _readme_catalog()[spec.rule_id]
        assert (row["severity"], row["confidence"]) == (spec.severity, spec.confidence)


class TestCatalogConsistency:

    def test_codes_are_unique_and_prefixed_by_category(self):
        assert len({s.code for s in RULE_CATALOG}) == len(RULE_CATALOG)
        for spec in RULE_CATALOG:
            assert spec.code[0] == CODE_PREFIX[spec.category], spec

    def test_every_rule_has_reviewed_recommendation_text(self):
        assert set(RECOMMENDATIONS) == set(RULES_BY_ID)

    def test_mcp_catalog_uses_catalog_metadata(self):
        served = json.loads(get_rules_catalog_json())["rules"]
        assert set(served) == set(RULES_BY_ID)
        for rule_id, entry in served.items():
            spec = RULES_BY_ID[rule_id]
            assert (entry["category"], entry["severity"], entry["confidence"], entry["code"]) == (
                spec.category, spec.severity, spec.confidence, spec.code,
            )

    def test_every_rule_fires_on_some_golden_fixture(self):
        """Each rule needs a true-positive golden fixture, and what it emits
        must carry the catalog's metadata."""
        fired: dict[str, set[tuple[str, str, int]]] = {}
        for fixture in sorted(GOLDEN_DIR.iterdir()):
            if not (fixture / "fixture.pbip").exists():
                continue
            for issue in ScanService.execute_scan(fixture).issues:
                fired.setdefault(issue.rule_id, set()).add((issue.category, issue.severity, issue.confidence))

        assert set(RULES_BY_ID) <= set(fired), f"no golden fixture triggers: {sorted(set(RULES_BY_ID) - set(fired))}"
        for rule_id, seen in fired.items():
            spec = RULES_BY_ID[rule_id]
            assert seen == {(spec.category, spec.severity, spec.confidence)}, rule_id
