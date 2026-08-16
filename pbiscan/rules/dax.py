"""DAX quality rules — D001 through D004.

Each function:
  - accepts a CanonicalReport
  - returns list[RuleFinding]
  - contains ONLY detection logic
  - does NOT import from pbiscan.extraction
  - does NOT contain recommendation prose
"""
from __future__ import annotations

import hashlib
import re

from pbiscan.canonical.model import CanonicalReport
from pbiscan.engine.issue import RuleFinding


# ---------------------------------------------------------------------------
# D001 — Suspicious DAX patterns
# ---------------------------------------------------------------------------

# Patterns are defined here but should ultimately be driven from rules.config.json.
# The pipeline passes config to rule functions via keyword arguments.
_DEFAULT_SUSPICIOUS_PATTERNS: list[tuple[str, str]] = [
    (
        r"FILTER\s*\(\s*ALL\s*\(",
        "FILTER(ALL(...)) — consider CALCULATE with filter arguments",
    ),
    (
        r"\bEARLIER\s*\(",
        "EARLIER() — legacy iterator function; consider VAR/RETURN instead",
    ),
    (
        r"CALCULATE\s*\(.*?CALCULATE\s*\(",
        "Nested CALCULATE() — verify context-transition behaviour",
    ),
]


def check_suspicious_dax(
    report: CanonicalReport,
    patterns: list[tuple[str, str]] | None = None,
) -> list[RuleFinding]:
    """D001 — Detect suspicious DAX patterns in measure expressions.

    Confidence: max 65% (heuristic).
    This indicates 'worth reviewing', NOT 'this measure is slow'.
    Only runtime analysis can prove actual performance impact.
    """
    if patterns is None:
        patterns = _DEFAULT_SUSPICIOUS_PATTERNS

    findings: list[RuleFinding] = []
    for measure in report.dax.measures:
        for pattern, description in patterns:
            if re.search(pattern, measure.expression, re.IGNORECASE | re.DOTALL):
                findings.append(RuleFinding(
                    rule_id="DAX_SUSPICIOUS_PATTERN",
                    category="dax",
                    severity="ADVISORY",
                    confidence=65,
                    evidence=(
                        f"Measure '{measure.name}' [{measure.table}]: "
                        f"{description}"
                    ),
                    location=f"Measure: {measure.name}",
                    metadata={"matched_pattern": pattern},
                ))
                break  # one finding per measure; first match wins
    return findings


# ---------------------------------------------------------------------------
# D002 — Excessive calculated columns
# ---------------------------------------------------------------------------

def check_excessive_calc_columns(
    report: CanonicalReport,
    threshold: int = 4,
) -> list[RuleFinding]:
    """D002 — Detect tables with more than `threshold` calculated columns.

    Confidence: 100% (deterministic count).
    Threshold is passed from rules.config.json by the pipeline.
    """
    findings: list[RuleFinding] = []

    # Group calculated columns by table
    table_calc_cols: dict[str, list[str]] = {}
    for cc in report.dax.calculated_columns:
        table_calc_cols.setdefault(cc.table, []).append(cc.name)

    # Map table names to Table objects for metadata checks
    table_map = {t.name.lower(): t for t in report.model.tables}

    for table_name, col_names in table_calc_cols.items():
        table_obj = table_map.get(table_name.lower())
        # Skip hidden/internal tables (e.g. LocalDateTable, DateTableTemplate)
        if table_obj and table_obj.hidden:
            continue

        if len(col_names) > threshold:
            findings.append(RuleFinding(
                rule_id="DAX_EXCESSIVE_CALC_COLUMNS",
                category="dax",
                severity="MEDIUM",
                confidence=100,
                evidence=(
                    f"Table '{table_name}' has {len(col_names)} calculated "
                    f"columns (threshold: {threshold}). "
                    f"Columns: {col_names}"
                ),
                location=f"Table: {table_name}",
            ))
    return findings


# ---------------------------------------------------------------------------
# D003 — Duplicate measure logic
# ---------------------------------------------------------------------------

def _normalise_expression(expr: str) -> str:
    """Normalise a DAX expression for duplicate detection.

    Normalisation steps:
      1. Strip single-line comments (-- ...)
      2. Strip block comments (/* ... */)
      3. Collapse all whitespace to single spaces
      4. Strip spaces around ( ) [ ] to make formatting-only diffs identical
      5. Lowercase
    """
    # Strip // and -- single-line comments
    expr = re.sub(r"(//|--)[^\n]*", "", expr)
    # Strip /* */ block comments
    expr = re.sub(r"/\*.*?\*/", "", expr, flags=re.DOTALL)
    # Collapse whitespace
    expr = re.sub(r"\s+", " ", expr).strip()
    # Remove spaces immediately after ( and [ and before ) and ]
    expr = re.sub(r"\(\s+", "(", expr)
    expr = re.sub(r"\s+\)", ")", expr)
    expr = re.sub(r"\[\s+", "[", expr)
    expr = re.sub(r"\s+\]", "]", expr)
    return expr.lower()


def check_duplicate_measures(report: CanonicalReport) -> list[RuleFinding]:
    """D003 — Detect measures with identical normalised expressions.

    Confidence: 90% (normalisation may occasionally over-match).
    Does NOT recommend deleting measures — context may matter.
    """
    findings: list[RuleFinding] = []
    hash_to_measures: dict[str, list[str]] = {}

    for measure in report.dax.measures:
        normalised = _normalise_expression(measure.expression)
        digest = hashlib.md5(normalised.encode("utf-8")).hexdigest()
        hash_to_measures.setdefault(digest, []).append(
            f"{measure.table}[{measure.name}]"
        )

    reported_hashes: set[str] = set()
    for digest, names in hash_to_measures.items():
        if len(names) > 1 and digest not in reported_hashes:
            reported_hashes.add(digest)
            findings.append(RuleFinding(
                rule_id="DAX_DUPLICATE_MEASURE",
                category="dax",
                severity="MEDIUM",
                confidence=90,
                evidence=(
                    f"Measures with identical normalised expressions: {names}"
                ),
                location=", ".join(names),
            ))
    return findings


# ---------------------------------------------------------------------------
# D004 — Unused measure
# ---------------------------------------------------------------------------

def _build_cross_measure_reference_map(
    report: CanonicalReport,
) -> dict[str, set[str]]:
    """Build a map: measure_name → set of other measures that reference it.

    This is a shallow (one-level) scan using regex pattern matching.
    It detects direct references of the form [MeasureName] within
    another measure's expression.

    This is critical for D004 correctness: a measure is NOT unused if
    it is referenced by another measure, even if not directly bound to
    a visual.
    """
    all_measure_names = {m.name for m in report.dax.measures}
    # Map: measure_name → set of measure_names that reference it
    referenced_by: dict[str, set[str]] = {n: set() for n in all_measure_names}

    for measure in report.dax.measures:
        for other_name in all_measure_names:
            if other_name == measure.name:
                continue
            # Match [OtherMeasureName] in the expression (case-insensitive)
            pattern = r"\[" + re.escape(other_name) + r"\]"
            if re.search(pattern, measure.expression, re.IGNORECASE):
                referenced_by[other_name].add(measure.name)

    return referenced_by


def check_unused_measures(report: CanonicalReport) -> list[RuleFinding]:
    """D004 — Detect measures unused in visuals AND not referenced by other measures.

    A measure is considered unused ONLY when BOTH conditions are true:
      1. NOT directly used by any report visual (not in any measure_refs)
      2. NOT referenced (directly or transitively) by any measure used in visuals

    This prevents false positives for base measures that are building blocks
    for higher-level measures but not directly bound to visuals.

    Confidence: 95% (two-signal detection).
    """
    findings: list[RuleFinding] = []

    # Collect all measure names referenced by report visuals
    visual_measure_refs: set[str] = set()
    for page in report.report.pages:
        for visual in page.visuals:
            for ref in visual.measure_refs:
                visual_measure_refs.add(ref)

    dax_graph = getattr(report, "dax_graph", None)

    for measure in report.dax.measures:
        if dax_graph and hasattr(dax_graph, "is_reachable_from_visual") and dax_graph.nodes:
            is_used = dax_graph.is_reachable_from_visual(measure.name, visual_measure_refs)
        else:
            in_visual = measure.name.lower() in {r.lower() for r in visual_measure_refs}
            referenced_by = _build_cross_measure_reference_map(report)
            in_measure = bool(referenced_by.get(measure.name))
            is_used = in_visual or in_measure

        if not is_used:
            findings.append(RuleFinding(
                rule_id="DAX_UNUSED_MEASURE",
                category="dax",
                severity="ADVISORY",
                confidence=95,
                evidence=(
                    f"Measure '{measure.name}' [{measure.table}]: "
                    f"not referenced by any report visual and not "
                    f"referenced by any other measure."
                ),
                location=f"Measure: {measure.name}",
            ))
    return findings


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

DAX_RULES = [
    check_suspicious_dax,
    check_excessive_calc_columns,
    check_duplicate_measures,
    check_unused_measures,
]
