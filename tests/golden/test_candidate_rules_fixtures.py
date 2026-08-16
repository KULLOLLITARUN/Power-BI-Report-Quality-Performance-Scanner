"""Contract and golden tests for candidate topology rules (M006 & M007).

Phase 1E of v1.2 Roadmap:
  - Verifies positive/negative golden fixtures for M006 (Isolated Table).
  - Verifies positive/negative golden fixtures for M007 (Ambiguous Path).
  - Verifies cycle safety and path deduplication.
  - Does NOT register M006/M007 in production rule matrix.
"""
from pathlib import Path
import pytest

from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.canonical.model import ModelGraph, Table, Relationship
from pbiscan.extraction.pbip_reader import PBIPReader


FIXTURES_DIR = Path(__file__).parent


def _build_report_from_fixture(fixture_name: str):
    fixture_dir = FIXTURES_DIR / fixture_name
    reader = PBIPReader()
    raw = reader.read(fixture_dir / "fixture.pbip")
    builder = CanonicalBuilder()
    return builder.build(raw)


# ---------------------------------------------------------------------------
# M006 Candidate — Isolated Table Golden Tests
# ---------------------------------------------------------------------------

class TestM006CandidateGoldenFixtures:
    def test_m006_positive_fixture_detects_isolated_table(self):
        """Positive fixture: IsolatedAuditLog has 0 relationships."""
        report = _build_report_from_fixture("test_isolated_table")
        isolated = report.model.isolated_tables()
        assert isolated == ["IsolatedAuditLog"]

    def test_m006_negative_fixture_returns_no_isolated_tables(self):
        """Negative fixture: Clean star schema where all tables participate in relationships."""
        report = _build_report_from_fixture("test_isolated_table_negative")
        isolated = report.model.isolated_tables()
        assert isolated == []


# ---------------------------------------------------------------------------
# M007 Candidate — Ambiguous Path Golden Tests
# ---------------------------------------------------------------------------

class TestM007CandidateGoldenFixtures:
    def test_m007_positive_fixture_detects_multiple_paths(self):
        """Positive fixture: Customer -> Region has 2 distinct active simple paths."""
        report = _build_report_from_fixture("test_ambiguous_path")
        paths = report.model.relationship_paths("Customer", "Region")
        assert len(paths) == 2

        # Paths should be ["Customer", "Sales", "Region"] and ["Customer", "Store", "Region"]
        assert ["Customer", "Sales", "Region"] in paths
        assert ["Customer", "Store", "Region"] in paths

    def test_m007_negative_fixture_has_single_paths_only(self):
        """Negative fixture: Standard star schema has at most 1 path between any pair."""
        report = _build_report_from_fixture("test_ambiguous_path_negative")
        tables = [t.name for t in report.model.tables]
        
        for i, t1 in enumerate(tables):
            for t2 in tables[i + 1:]:
                paths = report.model.relationship_paths(t1, t2)
                assert len(paths) <= 1, f"Expected at most 1 path between {t1} and {t2}, found {len(paths)}"

    def test_m007_cycle_safety_and_deduplication(self):
        """Cycle safety: Cyclic topology A -> B -> C -> A terminates safely with unique simple paths."""
        tables = [Table(name="A"), Table(name="B"), Table(name="C")]
        rels = [
            Relationship(from_table="A", from_column="id", to_table="B", to_column="id", is_active=True),
            Relationship(from_table="B", from_column="id", to_table="C", to_column="id", is_active=True),
            Relationship(from_table="C", from_column="id", to_table="A", to_column="id", is_active=True),
        ]
        graph = ModelGraph(tables=tables, relationships=rels)

        # Between A and C in cyclic graph: Path 1: ['A', 'C'], Path 2: ['A', 'B', 'C']
        paths = graph.relationship_paths("A", "C")
        assert len(paths) == 2
        assert ["A", "C"] in paths
        assert ["A", "B", "C"] in paths
        
        # Verify no cycles or infinite recursion
        for p in paths:
            assert len(p) == len(set(p)), "Path must be simple (no repeat nodes)"
