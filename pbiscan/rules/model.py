"""Model quality rules — M001 through M005.

Each function:
  - accepts a CanonicalReport
  - returns list[RuleFinding]
  - contains ONLY detection logic
  - does NOT import from pbiscan.extraction  (Contract 2)
  - does NOT contain recommendation prose    (Contract 3)
  - does NOT call external services          (Contract 6)
"""
from __future__ import annotations

from pbiscan.canonical.model import CanonicalReport, Table
from pbiscan.engine.issue import RuleFinding


# ---------------------------------------------------------------------------
# M001 — Bi-directional relationship
# ---------------------------------------------------------------------------

def check_bidirectional(report: CanonicalReport) -> list[RuleFinding]:
    """M001 — Detect relationships with bidirectional cross-filter direction."""
    findings: list[RuleFinding] = []
    for rel in report.model.relationships:
        if rel.cross_filter_direction.lower() in ("both", "bothdirections", "2"):
            findings.append(RuleFinding(
                rule_id="MODEL_BIDIRECTIONAL",
                category="model",
                severity="WARNING",
                confidence=100,
                evidence=(
                    f"{rel.from_table}[{rel.from_column}] ↔ "
                    f"{rel.to_table}[{rel.to_column}], "
                    f"crossFilterDirection={rel.cross_filter_direction}"
                ),
                location=(
                    f"{rel.from_table}[{rel.from_column}] ↔ "
                    f"{rel.to_table}[{rel.to_column}]"
                ),
            ))
    return findings


# ---------------------------------------------------------------------------
# M002 — Many-to-many relationship
# ---------------------------------------------------------------------------

def check_many_to_many(report: CanonicalReport) -> list[RuleFinding]:
    """M002 — Detect many-to-many cardinality relationships."""
    findings: list[RuleFinding] = []
    for rel in report.model.relationships:
        if rel.cardinality.lower() in ("manytomany", "many_to_many", "m:m", "many:many"):
            findings.append(RuleFinding(
                rule_id="MODEL_MANY_TO_MANY",
                category="model",
                severity="WARNING",
                confidence=100,
                evidence=(
                    f"{rel.from_table}[{rel.from_column}] → "
                    f"{rel.to_table}[{rel.to_column}], "
                    f"cardinality={rel.cardinality}"
                ),
                location=(
                    f"{rel.from_table}[{rel.from_column}] → "
                    f"{rel.to_table}[{rel.to_column}]"
                ),
            ))
    return findings


# ---------------------------------------------------------------------------
# M003 — No date table
# ---------------------------------------------------------------------------

def check_no_date_table(report: CanonicalReport) -> list[RuleFinding]:
    """M003 — Detect absence of a dedicated date dimension.

    Confidence: 70% (structural heuristic).
    Uses hedged language — does NOT claim the model definitely lacks a date table.
    """
    if not report.model.tables:
        return []

    has_date_table = any(
        t.is_date_table or _is_date_candidate(t)
        for t in report.model.tables
    )

    if not has_date_table:
        table_names = [t.name for t in report.model.tables]
        return [RuleFinding(
            rule_id="MODEL_NO_DATE_TABLE",
            category="model",
            severity="WARNING",
            confidence=70,
            evidence=(
                f"No table is marked as a Date Table and no table matches "
                f"date-dimension naming or data-category signals. "
                f"Tables found: {table_names}"
            ),
            location=None,
        )]
    return []


def _is_date_candidate(table: Table) -> bool:
    """Heuristic: does the table look like a date dimension?"""
    name_lower = table.name.lower()
    date_name_hints = (
        "date", "dim_date", "dimdate", "calendar",
        "dim_calendar", "time", "dim_time",
    )
    if any(hint in name_lower for hint in date_name_hints):
        return True
    # Check column data categories
    for col in table.columns:
        if col.data_category and col.data_category.lower() in ("time", "date"):
            return True
    return False


# ---------------------------------------------------------------------------
# M004 — High-cardinality column
# ---------------------------------------------------------------------------

def check_high_cardinality(report: CanonicalReport) -> list[RuleFinding]:
    """M004 — Detect potential high-cardinality columns.

    Confidence: 87% (structural signal).
    Cannot prove actual VertiPaq memory impact without runtime analysis.
    """
    findings: list[RuleFinding] = []
    for table in report.model.tables:
        for col in table.columns:
            if _is_high_cardinality_candidate(col):
                findings.append(RuleFinding(
                    rule_id="MODEL_HIGH_CARDINALITY",
                    category="model",
                    severity="ADVISORY",
                    confidence=87,
                    evidence=(
                        f"{table.name}[{col.name}]: "
                        f"dataType={col.data_type}, "
                        f"isUnique={col.is_unique}, "
                        f"inRelationship={col.in_relationship}"
                    ),
                    location=f"{table.name}[{col.name}]",
                ))
    return findings


def _is_high_cardinality_candidate(col) -> bool:
    """Structural heuristic: string column that is unique and not in a relationship."""
    if col.data_type.lower() not in ("string", "text"):
        return False
    if col.in_relationship:
        # Relationship keys are expected to repeat; not a cardinality concern
        return False
    return col.is_unique


# ---------------------------------------------------------------------------
# M005 — Fact-to-fact relationship
# ---------------------------------------------------------------------------

def check_fact_to_fact(report: CanonicalReport) -> list[RuleFinding]:
    """M005 — Detect potential fact-to-fact relationships.

    Confidence: 60% (naming + measure-presence heuristic).
    Does NOT claim certainty.
    """
    findings: list[RuleFinding] = []
    measure_tables = {m.table for m in report.dax.measures}
    dim_hints = ("dim", "dimension", "lookup", "ref", "reference", "bridge")

    for rel in report.model.relationships:
        from_has_measures = rel.from_table in measure_tables
        to_has_measures = rel.to_table in measure_tables

        if not (from_has_measures and to_has_measures):
            continue

        from_looks_like_dim = any(h in rel.from_table.lower() for h in dim_hints)
        to_looks_like_dim = any(h in rel.to_table.lower() for h in dim_hints)

        if not from_looks_like_dim and not to_looks_like_dim:
            findings.append(RuleFinding(
                rule_id="MODEL_FACT_TO_FACT",
                category="model",
                severity="ADVISORY",
                confidence=60,
                evidence=(
                    f"{rel.from_table} → {rel.to_table}: "
                    f"both tables contain measures and neither matches "
                    f"a dimension naming pattern."
                ),
                location=f"{rel.from_table} → {rel.to_table}",
            ))
    return findings


# ---------------------------------------------------------------------------
# Rule registry — used by the pipeline
# ---------------------------------------------------------------------------

MODEL_RULES = [
    check_bidirectional,
    check_many_to_many,
    check_no_date_table,
    check_high_cardinality,
    check_fact_to_fact,
]
