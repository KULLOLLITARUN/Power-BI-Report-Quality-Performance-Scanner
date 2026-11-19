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
from pbiscan.rules.catalog import new_finding


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _walk_dax(expr: str, *, drop_comments: bool, blank: str) -> str:
    """Single pass over a DAX expression, aware of strings, names and comments.

    ``blank`` controls which literal contents are replaced by spaces (delimiters
    and length are kept): ``""`` none, ``"strings"`` only "text" literals,
    ``"all"`` also 'Table Names' and [Column Names].
    """
    out: list[str] = []
    i, n = 0, len(expr)
    while i < n:
        ch = expr[i]
        if ch in ('"', "'", "["):
            close = {'"': '"', "'": "'", "[": "]"}[ch]
            do_blank = blank == "all" or (blank == "strings" and ch == '"')
            out.append(ch)
            i += 1
            while i < n:
                c = expr[i]
                if c == close:
                    # A doubled quote ("" or '') is an escaped quote, not the end.
                    if close != "]" and i + 1 < n and expr[i + 1] == close:
                        out.append("  " if do_blank else c + c)
                        i += 2
                        continue
                    out.append(c)
                    i += 1
                    break
                out.append(" " if do_blank and c != "\n" else c)
                i += 1
        elif drop_comments and (expr.startswith("//", i) or expr.startswith("--", i)):
            while i < n and expr[i] != "\n":
                i += 1
            out.append(" ")
        elif drop_comments and expr.startswith("/*", i):
            end = expr.find("*/", i + 2)
            i = n if end == -1 else end + 2
            out.append(" ")
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def strip_dax_comments(expr: str) -> str:
    """Remove ``//``, ``--`` and ``/* */`` comments without touching string literals.

    Comment markers inside "text" literals (e.g. URLs), 'Table Names' and
    [Column Names] are preserved. A removed comment becomes a single space so
    adjacent tokens never fuse.
    """
    return _walk_dax(expr, drop_comments=True, blank="")


def dax_code_only(expr: str) -> str:
    """Comments removed and "text" literal contents blanked: safe to regex for code."""
    return _walk_dax(expr, drop_comments=True, blank="strings")


_CALCULATE_CALL = re.compile(r"\bCALCULATE\s*\(", re.IGNORECASE)


def has_nested_calculate(expr: str) -> bool:
    """True when a CALCULATE( call appears inside another CALCULATE's arguments.

    Sequential calls such as ``CALCULATE(a) + CALCULATE(b)`` are not nested.
    """
    code = _walk_dax(expr, drop_comments=True, blank="all")
    opens = [m.end() for m in _CALCULATE_CALL.finditer(code)]  # index just past "("
    for idx, start in enumerate(opens):
        depth = 1
        pos = start
        while pos < len(code) and depth:
            if code[pos] == "(":
                depth += 1
            elif code[pos] == ")":
                depth -= 1
            pos += 1
        end = pos if depth == 0 else len(code)
        if any(start <= later < end for later in opens[idx + 1:]):
            return True
    return False


# ---------------------------------------------------------------------------
# D001 — Suspicious DAX patterns
# ---------------------------------------------------------------------------

# Patterns are defined here but should ultimately be driven from rules.config.json.
# The pipeline passes config to rule functions via keyword arguments.
# The nested-CALCULATE regex is the shipped default (and what rules.config.json
# carries). A regex cannot tell nesting from sequential calls, so this exact
# pattern is evaluated with a parenthesis-depth check instead.
_NESTED_CALCULATE_PATTERN = r"CALCULATE\s*\(.*?CALCULATE\s*\("

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
        _NESTED_CALCULATE_PATTERN,
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
        # Match against code only: commented-out DAX must not raise findings.
        code = dax_code_only(measure.expression)
        for pattern, description in patterns:
            if pattern == _NESTED_CALCULATE_PATTERN:
                matched = has_nested_calculate(measure.expression)
            else:
                matched = re.search(pattern, code, re.IGNORECASE | re.DOTALL) is not None
            if matched:
                findings.append(new_finding(
                    "DAX_SUSPICIOUS_PATTERN",
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
            findings.append(new_finding(
                "DAX_EXCESSIVE_CALC_COLUMNS",
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
    # Strip comments (string-aware, so "https://x" keeps its //)
    expr = strip_dax_comments(expr)
    # Collapse whitespace
    expr = re.sub(r"\s+", " ", expr).strip()
    # Remove spaces immediately after ( and [ and before ) and ]
    expr = re.sub(r"\(\s+", "(", expr)
    expr = re.sub(r"\s+\)", ")", expr)
    expr = re.sub(r"\[\s+", "[", expr)
    expr = re.sub(r"\s+\]", "]", expr)
    return expr.lower()


# Normalised expressions this short are constants; the Studio scanner uses the same cutoff.
_MIN_DUPLICATE_LENGTH = 5


def check_duplicate_measures(report: CanonicalReport) -> list[RuleFinding]:
    """D003 — Detect measures with identical normalised expressions.

    Confidence: 90% (normalisation may occasionally over-match).
    Does NOT recommend deleting measures — context may matter.
    """
    findings: list[RuleFinding] = []
    hash_to_measures: dict[str, list[str]] = {}

    for measure in report.dax.measures:
        normalised = _normalise_expression(measure.expression)
        if len(normalised) <= _MIN_DUPLICATE_LENGTH:
            continue  # trivial constants (0, 1, BLANK()) are intentionally identical
        digest = hashlib.md5(normalised.encode("utf-8")).hexdigest()
        hash_to_measures.setdefault(digest, []).append(
            f"{measure.table}[{measure.name}]"
        )

    reported_hashes: set[str] = set()
    for digest, names in hash_to_measures.items():
        if len(names) > 1 and digest not in reported_hashes:
            reported_hashes.add(digest)
            findings.append(new_finding(
                "DAX_DUPLICATE_MEASURE",
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

    Returns nothing when any project file could not be read: a skipped file
    may be the only place a measure is used, and `pbiscan fix` deletes what
    this rule reports.

    Confidence: 95% (two-signal detection).
    """
    findings: list[RuleFinding] = []
    if report.unread_files:
        return findings

    # Collect all measure names referenced by report visuals and semantic reference index
    active_root_measures: set[str] = set()
    for page in report.report.pages:
        for visual in page.visuals:
            for ref in visual.measure_refs:
                active_root_measures.add(ref)

    if hasattr(report, "semantic_references") and report.semantic_references:
        active_root_measures = active_root_measures | report.semantic_references.active_root_measure_names()

    dax_graph = getattr(report, "dax_graph", None)

    for measure in report.dax.measures:
        if dax_graph and hasattr(dax_graph, "is_reachable_from_visual") and dax_graph.nodes:
            is_used = dax_graph.is_reachable_from_visual(measure.name, active_root_measures)
        else:
            in_visual = measure.name.lower() in {r.lower() for r in active_root_measures}
            referenced_by = _build_cross_measure_reference_map(report)
            in_measure = bool(referenced_by.get(measure.name))
            is_used = in_visual or in_measure

        if not is_used:
            findings.append(new_finding(
                "DAX_UNUSED_MEASURE",
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
