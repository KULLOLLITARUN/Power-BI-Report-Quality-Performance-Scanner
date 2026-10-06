"""model.bim (TMSL JSON) semantic model parser.

Returns raw parsed data only — no detection, scoring or recommendations.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pbiscan.extraction.raw import RawModel, RawRelationship, RawTable, expect_structure, load_json

logger = logging.getLogger(__name__)

_DATE_TABLE_ANNOTATIONS = (
    "PBI_IsDateTable",           # pbiscan convention
    "__PBI_LocalDateTable",      # Power BI auto date/time
    "PBI_TemporalTable",         # alternate Power BI marker
)


def parse_bim_model(model_bim: Path) -> RawModel:
    """Parse model.bim into tables, relationships and roles.

    Raises ParseError if the file is not valid JSON and SchemaError if it is
    JSON of the wrong shape.
    """
    raw_model = load_json(model_bim)
    with expect_structure(model_bim):
        model_node = raw_model.get("model", raw_model)
        return RawModel(
            tables=parse_tables(model_node.get("tables", [])),
            relationships=parse_relationships(model_node.get("relationships", [])),
            roles=model_node.get("roles", []),
        )


def parse_tables(raw_tables: list[dict[str, Any]]) -> list[RawTable]:
    """Parse raw table definitions from model.bim."""
    result: list[RawTable] = []
    for raw in raw_tables:
        name = raw.get("name", "")
        if not name:
            continue

        annotations = raw.get("annotations", [])
        is_date_table = is_date_table_annotation(annotations)

        raw_columns = []
        raw_measures = []
        raw_calc_cols = []

        for col in raw.get("columns", []):
            col_type = col.get("type", "").lower()
            if col_type == "calculated":
                raw_calc_cols.append({**col, "_table": name})
            else:
                raw_columns.append({**col, "_table": name})

        for m in raw.get("measures", []):
            raw_measures.append({**m, "_table": name})

        calc_group = raw.get("calculationGroup", {})
        calc_items = calc_group.get("calculationItems", []) if calc_group else []
        partitions = raw.get("partitions", [])
        part_source = ""
        if partitions:
            src = partitions[0].get("source", {})
            if isinstance(src, dict):
                part_source = src.get("expression", "")
                if isinstance(part_source, list):
                    part_source = "\n".join(part_source)
            elif isinstance(src, str):
                part_source = src

        result.append(RawTable(
            name=name,
            hidden=raw.get("isHidden", False),
            is_date_table=is_date_table,
            columns=raw_columns,
            measures=raw_measures,
            calculated_columns=raw_calc_cols,
            annotations=annotations,
            calculation_items=calc_items,
            partition_source=part_source,
            source_file="model.bim",
        ))
    return result


def is_date_table_annotation(annotations: list[dict[str, Any]]) -> bool:
    """Check if annotations mark this as a date table."""
    for ann in annotations:
        if ann.get("name", "") in _DATE_TABLE_ANNOTATIONS:
            value = str(ann.get("value", "")).lower()
            if value in ("true", "1", "yes"):
                return True
    return False


def parse_relationships(raw_rels: list[dict[str, Any]]) -> list[RawRelationship]:
    """Parse raw relationship definitions from model.bim."""
    result: list[RawRelationship] = []
    for raw in raw_rels:
        from_table = raw.get("fromTable", "")
        from_col = raw.get("fromColumn", "")
        to_table = raw.get("toTable", "")
        to_col = raw.get("toColumn", "")
        if not all([from_table, from_col, to_table, to_col]):
            logger.warning("Skipping incomplete relationship: %s", raw)
            continue
        result.append(RawRelationship(
            from_table=from_table,
            from_column=from_col,
            to_table=to_table,
            to_column=to_col,
            raw=raw,
        ))
    return result
