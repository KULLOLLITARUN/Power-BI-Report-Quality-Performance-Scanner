"""Checks that a patched file still parses and that a patch changed only what it meant to.

A post-patch rescan alone does not prove this. The TMDL parser is lenient by
design (an unreadable table is skipped so one bad file doesn't sink a scan),
so a patch that corrupts a table file can make that table's findings vanish,
and the rescan would count them as resolved. These checks re-parse each
edited file and compare it with the original, and compare the set of files
the whole project could not read before and after.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pbiscan.extraction.raw import RawTable
from pbiscan.extraction.tmdl_parser import parse_tmdl_relationships_text, parse_tmdl_table_text
from pbiscan.service import ScanResult

_JSON_SUFFIXES = {".json", ".bim", ".pbir", ".pbism", ".pbip"}


def check_patched_text(path: Path, before: str, after: str) -> list[str]:
    """Return problems with replacing `before` by `after` in `path`; empty means OK.

    JSON files must still parse. A TMDL table file must either be emptied
    entirely (a whole-table removal) or still declare the same table with the
    same columns and calculation items, and every measure left in it must keep
    its exact expression: a measure deleted without its body would otherwise
    leave that body attached to the measure above it. relationships.tmdl must
    keep every relationship's endpoints.
    """
    name = path.name
    suffix = path.suffix.lower()
    # Patchers read files as plain UTF-8, which keeps a byte-order mark as text.
    before, after = before.lstrip("﻿"), after.lstrip("﻿")

    if suffix in _JSON_SUFFIXES:
        try:
            json.loads(after)
        except json.JSONDecodeError as exc:
            return [f"{name} is no longer valid JSON after patching: {exc}"]
        return []

    if suffix != ".tmdl":
        return []

    if name.lower() == "relationships.tmdl":
        return _check_relationships(name, before, after)

    original = parse_tmdl_table_text(before)
    if original is None:
        return []  # not a table file (model.tmdl, expressions.tmdl, ...)
    if not after.strip():
        return []
    patched = parse_tmdl_table_text(after)
    if patched is None:
        return [f"{name} no longer declares table '{original.name}' after patching"]
    return _check_table(name, original, patched)


def _check_table(name: str, before: RawTable, after: RawTable) -> list[str]:
    problems: list[str] = []
    if after.name != before.name:
        problems.append(f"{name}: table renamed from '{before.name}' to '{after.name}' by the patch")

    def names(items: list[dict[str, Any]]) -> list[str]:
        return [str(i.get("name")) for i in items]

    def exprs(items: list[dict[str, Any]]) -> dict[str, str]:
        return {str(i.get("name")): str(i.get("expression", "")) for i in items}

    if names(after.columns) != names(before.columns):
        problems.append(f"{name}: columns changed by the patch")
    if exprs(after.calculated_columns) != exprs(before.calculated_columns):
        problems.append(f"{name}: calculated columns changed by the patch")
    if exprs(after.calculation_items) != exprs(before.calculation_items):
        problems.append(f"{name}: calculation items changed by the patch")

    before_measures = exprs(before.measures)
    for measure, expression in exprs(after.measures).items():
        if measure not in before_measures:
            problems.append(f"{name}: patch introduced unexpected measure '{measure}'")
        elif expression != before_measures[measure]:
            problems.append(f"{name}: expression of measure '{measure}' changed by the patch")
    return problems


def _check_relationships(name: str, before: str, after: str) -> list[str]:
    def endpoints(text: str) -> list[tuple[str, str, str, str]]:
        return sorted(
            (r.from_table, r.from_column, r.to_table, r.to_column)
            for r in parse_tmdl_relationships_text(text)
        )

    if endpoints(after) != endpoints(before):
        return [f"{name}: relationship endpoints changed by the patch"]
    return []


def new_unread_files(before: ScanResult, after: ScanResult) -> list[str]:
    """Project files (relative paths) that `after` could not read but `before` could."""
    def relative(scan: ScanResult) -> set[str]:
        root = Path(scan.source_path)
        out: set[str] = set()
        for f in (scan.report.unread_files if scan.report else []):
            try:
                out.add(Path(f).relative_to(root).as_posix())
            except ValueError:
                out.add(Path(f).as_posix())
        return out

    return sorted(relative(after) - relative(before))
