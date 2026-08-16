"""Canonical model — the central abstraction consumed by every pbiscan rule.

Architectural contracts (from build spec):
  - Rules MUST import from this module only.
  - Rules MUST NOT import from pbiscan.extraction.
  - This module MUST NOT import from pbiscan.rules or pbiscan.engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from pbiscan.canonical.dax_graph import DaxDependencyGraph


# ---------------------------------------------------------------------------
# Model layer
# ---------------------------------------------------------------------------

@dataclass
class Column:
    """A single column in a Power BI table."""
    name: str
    table: str
    data_type: str = "string"         # int64, decimal, string, dateTime, boolean, …
    hidden: bool = False
    is_unique: bool = False            # structural signal only; not proven at runtime
    data_category: Optional[str] = None   # e.g. "time", "date", "barcode"
    in_relationship: bool = False      # True if this column is a key in any relationship


@dataclass
class Table:
    """A Power BI table (fact, dimension, or calculated)."""
    name: str
    hidden: bool = False
    columns: list[Column] = field(default_factory=list)
    is_date_table: bool = False        # True if marked as a Date Table in the model
    partition_source: str = ""         # Raw M-expression or DAX source query


@dataclass
class Relationship:
    """A Power BI relationship between two tables."""
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: str = "oneToMany"          # oneToOne | oneToMany | manyToMany
    cross_filter_direction: str = "single"  # single | both
    is_active: bool = True


@dataclass
class ModelGraph:
    """All tables and relationships extracted from the semantic model."""
    tables: list[Table] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)

    def get_table(self, name: str) -> Optional[Table]:
        for t in self.tables:
            if t.name.lower() == name.lower():
                return t
        return None

    def connected_components(self) -> list[set[str]]:
        """Groups of table names connected by any relationship (active or
        inactive, either direction). A model with 2+ components has at
        least one disconnected island of tables."""
        all_table_names = {t.name for t in self.tables}
        adj: dict[str, set[str]] = {name: set() for name in all_table_names}
        for rel in self.relationships:
            if rel.from_table in adj and rel.to_table in adj:
                adj[rel.from_table].add(rel.to_table)
                adj[rel.to_table].add(rel.from_table)

        visited: set[str] = set()
        components: list[set[str]] = []

        for name in sorted(all_table_names):
            if name not in visited:
                comp: set[str] = set()
                queue = [name]
                visited.add(name)
                while queue:
                    curr = queue.pop(0)
                    comp.add(curr)
                    for nxt in adj.get(curr, set()):
                        if nxt not in visited:
                            visited.add(nxt)
                            queue.append(nxt)
                components.append(comp)

        return components

    def isolated_tables(self) -> list[str]:
        """Table names with zero relationships - a specific, common case
        of a disconnected component containing exactly one table."""
        rel_tables = set()
        for rel in self.relationships:
            rel_tables.add(rel.from_table.lower())
            rel_tables.add(rel.to_table.lower())

        isolated: list[str] = []
        for t in self.tables:
            if t.name.lower() not in rel_tables:
                isolated.append(t.name)
        return sorted(isolated)

    def relationship_paths(
        self, from_table: str, to_table: str, active_only: bool = True
    ) -> list[list[str]]:
        """All distinct simple paths between two tables through relationships.

        If active_only=True (default), considers only active relationships.
        Returns list of paths, e.g. [['FactSales', 'DimStore', 'DimRegion'], ['FactSales', 'DimRegion']].
        """
        from_lower = from_table.lower()
        to_lower = to_table.lower()

        canonical_names = {t.name.lower(): t.name for t in self.tables}
        if from_lower not in canonical_names or to_lower not in canonical_names:
            return []

        adj: dict[str, set[str]] = {t.name: set() for t in self.tables}
        for rel in self.relationships:
            if active_only and not rel.is_active:
                continue
            if rel.from_table in adj and rel.to_table in adj:
                adj[rel.from_table].add(rel.to_table)
                adj[rel.to_table].add(rel.from_table)

        start_name = canonical_names[from_lower]
        target_name = canonical_names[to_lower]

        paths: list[list[str]] = []

        def dfs_paths(current: str, target: str, current_path: list[str], visited: set[str]):
            if current == target:
                paths.append(list(current_path))
                return

            for neighbor in sorted(adj.get(current, set())):
                if neighbor not in visited:
                    visited.add(neighbor)
                    current_path.append(neighbor)
                    dfs_paths(neighbor, target, current_path, visited)
                    current_path.pop()
                    visited.remove(neighbor)

        dfs_paths(start_name, target_name, [start_name], {start_name})
        return paths


# ---------------------------------------------------------------------------
# DAX layer
# ---------------------------------------------------------------------------

@dataclass
class Measure:
    """A DAX measure defined in the semantic model."""
    name: str
    table: str
    expression: str
    hidden: bool = False


@dataclass
class CalculatedColumn:
    """A DAX calculated column defined in the semantic model."""
    name: str
    table: str
    expression: str
    data_type: str = "string"


@dataclass
class DaxDictionary:
    """All measures and calculated columns extracted from the model."""
    measures: list[Measure] = field(default_factory=list)
    calculated_columns: list[CalculatedColumn] = field(default_factory=list)

    def get_measure(self, name: str) -> Optional[Measure]:
        for m in self.measures:
            if m.name.lower() == name.lower():
                return m
        return None


# ---------------------------------------------------------------------------
# Report layer
# ---------------------------------------------------------------------------

@dataclass
class Visual:
    """A single visual on a report page."""
    visual_type: str
    page: str
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    fields_used: list[str] = field(default_factory=list)   # e.g. ["Sales.Total Revenue"]
    measure_refs: list[str] = field(default_factory=list)  # e.g. ["Total Revenue"]
    is_slicer: bool = False
    hidden: bool = False

    def __post_init__(self) -> None:
        # Normalise slicer detection from visual type
        if self.visual_type.lower() == "slicer":
            self.is_slicer = True


@dataclass
class Page:
    """A report page containing zero or more visuals."""
    name: str
    display_name: str = ""
    visibility: int = 0   # 0 = visible, 1 = hidden

    visuals: list[Visual] = field(default_factory=list)

    @property
    def is_hidden(self) -> bool:
        return self.visibility != 0

    @property
    def visual_count(self) -> int:
        """Total number of visuals (including slicers)."""
        return len(self.visuals)

    @property
    def slicer_count(self) -> int:
        """Number of slicer visuals on the page."""
        return sum(1 for v in self.visuals if v.is_slicer)

    @property
    def label(self) -> str:
        """Human-readable page identifier for evidence strings."""
        return self.display_name or self.name


@dataclass
class ReportDOM:
    """The complete report structure (all pages and visuals)."""
    pages: list[Page] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Root canonical object
# ---------------------------------------------------------------------------

from pbiscan.canonical.references import SemanticReferenceIndex


@dataclass
class CanonicalReport:
    """The single object consumed by all pbiscan rules.

    Rules accept a CanonicalReport and return list[RuleFinding].
    No rule should ever inspect raw PBIP structures.
    """
    model: ModelGraph = field(default_factory=ModelGraph)
    dax: DaxDictionary = field(default_factory=DaxDictionary)
    dax_graph: DaxDependencyGraph = field(default_factory=DaxDependencyGraph)
    report: ReportDOM = field(default_factory=ReportDOM)
    semantic_references: SemanticReferenceIndex = field(default_factory=SemanticReferenceIndex)
    source_path: str = ""
    report_name: str = ""

