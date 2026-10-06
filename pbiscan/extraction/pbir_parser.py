"""PBIR report parser (definition/pages/<name>/page.json + visuals/<name>/visual.json).

Returns raw parsed data only — no detection, scoring or recommendations.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from pbiscan.extraction.raw import (
    ParseError,
    RawPage,
    RawVisual,
    collect_extension_measures,
    expect_structure,
    extract_entity_names,
    extract_measure_names,
    load_json,
)

logger = logging.getLogger(__name__)


def parse_pbir_pages(definition_dir: Path) -> list[RawPage]:
    """Parse every page under definition/pages/.

    Raises ParseError for a page or visual file that is not valid JSON and
    SchemaError for one of the wrong shape: a visual that can't be read could
    be the only user of a measure, so it is not silently dropped.
    """
    pages: list[RawPage] = []
    pages_dir = definition_dir / "pages"

    for page_dir in sorted(pages_dir.iterdir()):
        if not page_dir.is_dir():
            continue

        page_json_path = page_dir / "page.json"
        if not page_json_path.exists():
            continue

        page_data = load_json(page_json_path)
        with expect_structure(page_json_path):
            name = page_data.get("name", page_dir.name)
            display_name = page_data.get("displayName", name)
            visibility = page_visibility(page_data.get("visibility"))
            width, height = canvas_size(page_data)

        visuals: list[RawVisual] = []
        visuals_dir = page_dir / "visuals"
        if visuals_dir.exists():
            for visual_dir in sorted(visuals_dir.iterdir()):
                visual_json = visual_dir / "visual.json"
                if visual_json.exists():
                    visual_data = load_json(visual_json)
                    with expect_structure(visual_json):
                        v = parse_pbir_visual(visual_data)
                    if v:
                        visuals.append(v)

        pages.append(RawPage(
            name=name,
            display_name=display_name,
            visibility=visibility,
            width=width,
            height=height,
            visuals=visuals,
            # page.json filterConfig (page-level filter pane) and any other bindings
            filter_measure_refs=sorted(extract_measure_names(page_data)),
        ))

    return pages


def canvas_size(page: dict[str, Any]) -> tuple[float, float]:
    """Page canvas (width, height); falls back to the 1280 x 720 default for missing or bad values."""
    def num(key: str, default: float) -> float:
        value = page.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            return float(value)
        return default
    return num("width", 1280.0), num("height", 720.0)


def page_visibility(value: Any) -> int:
    """Map PBIR page visibility ("AlwaysVisible" / "HiddenInViewMode") to 0 = visible, 1 = hidden.

    Drillthrough and tooltip pages are usually HiddenInViewMode. Their visuals
    still count as measure usage; only the per-page bloat rules skip them.
    """
    if value == "HiddenInViewMode":
        return 1
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0


def parse_pbir_report_level(
    definition_dir: Path, unread: list[str]
) -> tuple[set[str], list[dict[str, Any]]]:
    """Measure refs in definition/report.json and bookmarks/, plus reportExtensions.json measures.

    Files that can't be read are skipped and their paths appended to `unread`.
    """
    def load(path: Path) -> Any:
        try:
            return load_json(path)
        except ParseError as exc:
            logger.warning("Skipping unreadable report file %s: %s", path, exc)
            unread.append(str(path))
            return None

    refs: set[str] = set()
    extensions: list[dict[str, Any]] = []

    pbir_report = definition_dir / "report.json"
    if pbir_report.exists():
        refs |= extract_measure_names(load(pbir_report))

    bookmarks_dir = definition_dir / "bookmarks"
    if bookmarks_dir.is_dir():
        for bookmark_file in sorted(bookmarks_dir.glob("*.json")):
            refs |= extract_measure_names(load(bookmark_file))

    extensions_file = definition_dir / "reportExtensions.json"
    if extensions_file.exists():
        extensions.extend(collect_extension_measures([load(extensions_file)]))

    return refs, extensions


def parse_pbir_visual(raw: dict[str, Any]) -> Optional[RawVisual]:
    """Parse a single PBIR visual.json document."""
    visual_node = raw.get("visual", {})
    visual_type = visual_node.get("visualType", "unknown")

    position = raw.get("position", {})

    query_measures, fields_used = _measure_refs_from_query(visual_node.get("query", {}))

    # Recursively harvest measure references across the complete visual AST
    # (objects.referenceLabel, objects.title, objects.subTitle, conditional formatting, filters)
    ast_measures = extract_measure_names(raw)

    return RawVisual(
        visual_type=visual_type,
        x=position.get("x", 0.0),
        y=position.get("y", 0.0),
        width=position.get("width", 0.0),
        height=position.get("height", 0.0),
        fields_used=sorted(set(fields_used) | ast_measures),
        measure_refs=sorted(set(query_measures) | ast_measures),
        table_refs=sorted(extract_entity_names(visual_node.get("query", {}))),
        is_slicer=(visual_type.lower() == "slicer"),
        hidden=raw.get("hidden", False),
    )


def _measure_refs_from_query(query: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Extract measure names from a PBIR visual's queryState projections."""
    measure_refs: list[str] = []
    fields_used: list[str] = []
    for _bucket_name, bucket in query.get("queryState", {}).items():
        for proj in bucket.get("projections", []):
            field = proj.get("field", {})
            if "Measure" in field:
                prop = field["Measure"].get("Property", "")
                if prop:
                    measure_refs.append(prop)
                    fields_used.append(prop)
    return measure_refs, fields_used
