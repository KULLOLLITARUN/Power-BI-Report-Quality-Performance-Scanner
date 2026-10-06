"""Legacy report.json parser (sections / visualContainers with stringified config).

Returns raw parsed data only — no detection, scoring or recommendations.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from pbiscan.extraction.raw import (
    ParseError,
    RawPage,
    RawVisual,
    collect_extension_measures,
    expect_structure,
    extract_measure_names,
    load_json,
)

logger = logging.getLogger(__name__)


def parse_report_json(report_json: Path) -> list[RawPage]:
    """Parse the pages of a legacy report.json.

    Raises ParseError if the file is not valid JSON and SchemaError if it is
    JSON of the wrong shape.
    """
    raw = load_json(report_json)
    with expect_structure(report_json):
        return _parse_sections(raw)


def _parse_sections(raw: dict[str, Any]) -> list[RawPage]:
    pages: list[RawPage] = []
    for section in raw.get("sections", []):
        name = section.get("name", "")
        display_name = section.get("displayName", name)
        visibility = section.get("visibility", 0)

        visuals = parse_visual_containers(section.get("visualContainers", []))

        # Page-level filters and config are stringified JSON in report.json
        filter_refs = extract_measure_names(
            [decode_json_field(section.get(k)) for k in ("filters", "config")]
        )

        pages.append(RawPage(
            name=name,
            display_name=display_name,
            visibility=visibility,
            visuals=visuals,
            filter_measure_refs=sorted(filter_refs),
        ))
    return pages


def parse_report_json_level(report_json: Path, unread: list[str]) -> tuple[set[str], list[dict[str, Any]]]:
    """Measure refs in report-level filters/config, plus config.modelExtensions measures.

    If the file can't be read or isn't a JSON object, its path is appended to `unread`.
    """
    try:
        raw = load_json(report_json)
    except ParseError as exc:
        logger.warning("Skipping unreadable report file %s: %s", report_json, exc)
        unread.append(str(report_json))
        return set(), []
    if not isinstance(raw, dict):
        unread.append(str(report_json))
        return set(), []
    config = decode_json_field(raw.get("config"))
    refs = extract_measure_names([decode_json_field(raw.get("filters")), config])
    extensions: list[dict[str, Any]] = []
    if isinstance(config, dict):
        extensions = collect_extension_measures(config.get("modelExtensions", []))
    return refs, extensions


def decode_json_field(value: Any) -> Any:
    """Legacy report.json stores filters/config as JSON strings; decode them (or pass through)."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def parse_visual_containers(containers: list[dict[str, Any]]) -> list[RawVisual]:
    """Parse the visualContainers array of one report.json section."""
    visuals: list[RawVisual] = []
    for vc in containers:
        v = parse_visual_container(vc)
        if v:
            visuals.append(v)
    return visuals


def parse_visual_container(vc: dict[str, Any]) -> Optional[RawVisual]:
    """Parse one visualContainer entry from report.json."""
    config_str = vc.get("config", "{}")
    if isinstance(config_str, str):
        try:
            config = json.loads(config_str)
        except json.JSONDecodeError:
            logger.warning("Could not parse visual config JSON: %s…", config_str[:80])
            config = {}
    else:
        config = config_str  # already a dict (some variants)

    single_visual = config.get("singleVisual", {})
    visual_type = single_visual.get("visualType", "unknown")

    # Extract from prototypeQuery (most common in report.json)
    measure_refs: list[str] = []
    fields_used: list[str] = []

    pq = single_visual.get("prototypeQuery", {})
    for select_item in pq.get("Select", []):
        name = select_item.get("Name", "")
        if name:
            clean_name = name.split(".", 1)[-1] if "." in name else name
            fields_used.append(clean_name)
        if "Measure" in select_item:
            prop = select_item["Measure"].get("Property", "")
            if prop:
                measure_refs.append(prop)

    # Extract from projections (e.g. {"Values": [{"queryRef": "Sales.Net Sales"}]})
    projections = single_visual.get("projections", {})
    if isinstance(projections, dict):
        for _bucket, items in projections.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        qref = item.get("queryRef", "")
                        if qref:
                            clean_name = qref.split(".", 1)[-1] if "." in qref else qref
                            fields_used.append(clean_name)
                            measure_refs.append(clean_name)

    # Recursively harvest measure references from objects / visual container JSON,
    # plus the visual-level filter pane (a separate stringified `filters` field)
    ast_measures = extract_measure_names([config, decode_json_field(vc.get("filters"))])
    all_measure_refs = sorted(set(measure_refs) | ast_measures)
    all_fields_used = sorted(set(fields_used) | ast_measures)

    return RawVisual(
        visual_type=visual_type,
        x=float(vc.get("x", 0)),
        y=float(vc.get("y", 0)),
        width=float(vc.get("width", 0)),
        height=float(vc.get("height", 0)),
        fields_used=all_fields_used,
        measure_refs=all_measure_refs,
        is_slicer=(visual_type.lower() == "slicer"),
        hidden=vc.get("hidden", False),
    )
