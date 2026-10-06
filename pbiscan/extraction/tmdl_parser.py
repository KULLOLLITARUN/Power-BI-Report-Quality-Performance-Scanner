"""TMDL semantic model parser (definition/tables/*.tmdl, roles/*.tmdl, relationships.tmdl).

Returns raw parsed data only — no detection, scoring or recommendations.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from pbiscan.extraction.raw import RawRelationship, RawTable

logger = logging.getLogger(__name__)

_COL_REF_RE = re.compile(r"^('([^']+)'|([^.]+))\.(.*)$")


def parse_tmdl_model(
    sm_dir: Path,
) -> tuple[list[RawTable], list[RawRelationship], list[dict[str, Any]]]:
    """Parse a TMDL semantic model directory into tables, relationships and raw role files."""
    definition_dir = sm_dir / "definition" if (sm_dir / "definition").exists() else sm_dir
    tables: list[RawTable] = []
    relationships: list[RawRelationship] = []
    tmdl_roles: list[dict[str, Any]] = []

    tables_dir = definition_dir / "tables"
    if tables_dir.exists():
        for tmdl_file in sorted(tables_dir.glob("*.tmdl")):
            t = parse_tmdl_table(tmdl_file)
            if t:
                tables.append(t)

    roles_dir = definition_dir / "roles"
    if roles_dir.exists():
        for role_file in sorted(roles_dir.glob("*.tmdl")):
            try:
                r_content = role_file.read_text(encoding="utf-8")
                tmdl_roles.append({
                    "name": role_file.stem,
                    "content": r_content,
                    "path": str(role_file),
                })
            except (OSError, UnicodeDecodeError):
                pass

    rel_file = definition_dir / "relationships.tmdl"
    if rel_file.exists():
        relationships = parse_tmdl_relationships(rel_file)

    return tables, relationships, tmdl_roles


def unquote(s: str) -> str:
    s = s.strip()
    if s.startswith("'") and s.endswith("'") and len(s) >= 2:
        return s[1:-1]
    return s


def parse_col_ref(ref_str: str) -> tuple[str, str]:
    """Parse 'Table Name'.ColumnName or TableName.ColumnName."""
    m = _COL_REF_RE.match(ref_str.strip())
    if m:
        tbl = m.group(2) or m.group(3)
        col = unquote(m.group(4))
        return tbl, col
    return "", ""


def parse_tmdl_table(file_path: Path) -> Optional[RawTable]:
    """Parse a single TMDL table file."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Could not read TMDL file %s: %s", file_path, exc)
        return None
    return parse_tmdl_table_text(content, str(file_path))


def parse_tmdl_table_text(content: str, source_file: str = "") -> Optional[RawTable]:
    """Parse the text of one TMDL table definition. Returns None if no `table` line is found."""
    lines = content.splitlines()
    table_name = ""
    hidden = False
    is_date_table = False
    columns: list[dict[str, Any]] = []
    measures: list[dict[str, Any]] = []
    calc_cols: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    calculation_items: list[dict[str, Any]] = []
    partition_source_lines: list[str] = []
    in_partition_source = False

    current_item_type: Optional[str] = None
    current_item_data: dict[str, Any] = {}
    current_expr_lines: list[str] = []

    def flush_current() -> None:
        nonlocal current_item_type, current_item_data, current_expr_lines
        if not current_item_type:
            return
        if current_item_type == "measure":
            current_item_data["expression"] = "\n".join(current_expr_lines).strip()
            current_item_data["_table"] = table_name
            measures.append(current_item_data)
        elif current_item_type == "calc_col":
            current_item_data["expression"] = "\n".join(current_expr_lines).strip()
            current_item_data["type"] = "calculated"
            current_item_data["_table"] = table_name
            calc_cols.append(current_item_data)
        elif current_item_type == "column":
            current_item_data["_table"] = table_name
            columns.append(current_item_data)
        elif current_item_type == "calc_item":
            current_item_data["expression"] = "\n".join(current_expr_lines).strip()
            current_item_data["_table"] = table_name
            calculation_items.append(current_item_data)
        current_item_type = None
        current_item_data = {}
        current_expr_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_item_type in ("measure", "calc_col", "calc_item"):
                current_expr_lines.append("")
            elif in_partition_source:
                partition_source_lines.append("")
            continue

        if line.startswith("///") or stripped.startswith("///"):
            flush_current()
            continue
        elif line.startswith("table "):
            flush_current()
            table_name = unquote(line[6:].strip())
            if "DateTable" in table_name or "LocalDateTable" in table_name:
                is_date_table = True
        elif current_item_type is None and stripped in ("isHidden", "isHidden: true"):
            hidden = True
        elif stripped.startswith("calculationItem "):
            flush_current()
            in_partition_source = False
            current_item_type = "calc_item"
            item_sig = stripped[16:].strip()
            if "=" in item_sig:
                parts = item_sig.split("=", 1)
                item_name = unquote(parts[0].strip())
                inline_expr = parts[1].strip()
                current_item_data = {"name": item_name, "format_string": ""}
                current_expr_lines = [inline_expr] if inline_expr else []
            else:
                item_name = unquote(item_sig)
                current_item_data = {"name": item_name, "format_string": ""}
                current_expr_lines = []
        elif stripped.startswith("measure "):
            flush_current()
            in_partition_source = False
            current_item_type = "measure"
            measure_sig = stripped[8:].strip()
            if "=" in measure_sig:
                parts = measure_sig.split("=", 1)
                m_name = unquote(parts[0].strip())
                inline_expr = parts[1].strip()
                current_item_data = {"name": m_name, "annotations": []}
                current_expr_lines = [inline_expr] if inline_expr else []
            else:
                m_name = unquote(measure_sig)
                current_item_data = {"name": m_name, "annotations": []}
                current_expr_lines = []
        elif stripped.startswith("column ") and "=" in stripped:
            flush_current()
            in_partition_source = False
            current_item_type = "calc_col"
            col_sig = stripped[7:].strip()
            parts = col_sig.split("=", 1)
            col_name = unquote(parts[0].strip())
            inline_expr = parts[1].strip()
            current_item_data = {"name": col_name, "dataType": "string", "annotations": []}
            current_expr_lines = [inline_expr] if inline_expr else []
        elif stripped.startswith("column "):
            flush_current()
            in_partition_source = False
            current_item_type = "column"
            col_name = unquote(stripped[7:].strip())
            current_item_data = {"name": col_name, "dataType": "string", "annotations": []}
        elif stripped.startswith("partition "):
            flush_current()
            in_partition_source = True
        elif stripped.startswith("annotation "):
            ann_str = stripped[11:].strip()
            if "=" in ann_str:
                k, v = ann_str.split("=", 1)
                ann_dict = {"name": k.strip(), "value": v.strip().strip('"')}
            else:
                ann_dict = {"name": ann_str, "value": "true"}
            if ann_dict["name"] in ("PBI_IsDateTable", "__PBI_LocalDateTable"):
                is_date_table = True
            if current_item_type in ("column", "calc_col", "measure"):
                current_item_data.setdefault("annotations", []).append(ann_dict)
            else:
                annotations.append(ann_dict)
        elif current_item_type == "calc_item":
            if stripped.startswith("formatStringDefinition =") or stripped.startswith("formatStringDefinition:"):
                sep = "=" if "=" in stripped else ":"
                current_item_data["format_string"] = stripped.split(sep, 1)[1].strip()
            else:
                current_expr_lines.append(stripped)
        elif current_item_type in ("measure", "calc_col"):
            if ":" in stripped and any(stripped.startswith(p) for p in ("formatString:", "lineageTag:", "dataType:", "summarizeBy:", "displayFolder:", "isHidden:")):
                k, v = stripped.split(":", 1)
                current_item_data[k.strip()] = v.strip()
            else:
                current_expr_lines.append(stripped)
        elif current_item_type == "column":
            if ":" in stripped:
                k, v = stripped.split(":", 1)
                current_item_data[k.strip()] = v.strip()
            elif stripped == "isHidden":
                current_item_data["isHidden"] = True
        elif in_partition_source:
            if stripped.startswith("source ="):
                partition_source_lines.append(stripped[8:].strip())
            else:
                partition_source_lines.append(stripped)

    flush_current()
    if not table_name:
        return None

    return RawTable(
        name=table_name,
        hidden=hidden,
        is_date_table=is_date_table,
        columns=columns,
        measures=measures,
        calculated_columns=calc_cols,
        annotations=annotations,
        calculation_items=calculation_items,
        partition_source="\n".join(partition_source_lines).strip(),
        source_file=source_file,
    )


def parse_tmdl_relationships(rel_file: Path) -> list[RawRelationship]:
    """Parse a TMDL relationships.tmdl file."""
    try:
        content = rel_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return parse_tmdl_relationships_text(content)


def parse_tmdl_relationships_text(content: str) -> list[RawRelationship]:
    """Parse the text of a relationships.tmdl file."""
    result: list[RawRelationship] = []
    for block in content.split("relationship "):
        if not block.strip():
            continue
        props: dict[str, str] = {}
        for line in block.splitlines():
            line_s = line.strip()
            if ":" in line_s:
                k, v = line_s.split(":", 1)
                props[k.strip()] = v.strip()

        f_t, f_c = parse_col_ref(props.get("fromColumn", ""))
        t_t, t_c = parse_col_ref(props.get("toColumn", ""))

        if f_t and f_c and t_t and t_c:
            raw_dict: dict[str, Any] = {
                "fromTable": f_t,
                "fromColumn": f_c,
                "toTable": t_t,
                "toColumn": t_c,
                "fromCardinality": props.get("fromCardinality", "many"),
                "toCardinality": props.get("toCardinality", "one"),
                "crossFilteringBehavior": props.get("crossFilteringBehavior", "oneDirection"),
                "isActive": props.get("isActive", "true").lower() != "false",
            }
            result.append(RawRelationship(
                from_table=f_t,
                from_column=f_c,
                to_table=t_t,
                to_column=t_c,
                raw=raw_dict,
            ))

    return result
