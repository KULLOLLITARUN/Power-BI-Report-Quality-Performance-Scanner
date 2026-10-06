"""TMDL semantic model parser (definition/tables/*.tmdl, roles/*.tmdl, relationships.tmdl).

Returns raw parsed data only — no detection, scoring or recommendations.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from pbiscan.extraction.raw import ParseError, RawModel, RawRelationship, RawTable, read_text

logger = logging.getLogger(__name__)

# A table reference: 'Quoted Name' (with '' as an escaped quote) or a bare name.
_COL_REF_RE = re.compile(r"^(?:'((?:[^']|'')*)'|([^.']+))\.(.*)$")
_FENCE = "```"


def parse_tmdl_model(sm_dir: Path) -> RawModel:
    """Parse a TMDL semantic model directory into tables, relationships and raw role files.

    A file that cannot be read, or a table file with no `table` declaration, is
    skipped with a warning and listed in `unread_files` instead of failing the
    whole scan.
    """
    definition_dir = sm_dir / "definition" if (sm_dir / "definition").exists() else sm_dir
    model = RawModel()

    tables_dir = definition_dir / "tables"
    if tables_dir.exists():
        for tmdl_file in sorted(tables_dir.glob("*.tmdl")):
            try:
                t = parse_tmdl_table(tmdl_file)
            except ParseError as exc:
                logger.warning("%s", exc)
                model.skip(tmdl_file, str(exc))
                continue
            if t is None:
                model.skip(tmdl_file, "no `table` declaration found")
            else:
                model.tables.append(t)

    roles_dir = definition_dir / "roles"
    if roles_dir.exists():
        for role_file in sorted(roles_dir.glob("*.tmdl")):
            try:
                content = read_text(role_file)
            except ParseError as exc:
                logger.warning("%s", exc)
                model.skip(role_file, str(exc))
                continue
            model.tmdl_roles.append({
                "name": role_file.stem,
                "content": content,
                "path": str(role_file),
            })

    rel_file = definition_dir / "relationships.tmdl"
    if rel_file.exists():
        try:
            model.relationships = parse_tmdl_relationships(rel_file)
        except ParseError as exc:
            logger.warning("%s", exc)
            model.skip(rel_file, str(exc))

    return model


def unquote(s: str) -> str:
    """Strip TMDL single quotes from a name, un-escaping doubled quotes ('' -> ')."""
    s = s.strip()
    if s.startswith("'") and s.endswith("'") and len(s) >= 2:
        return s[1:-1].replace("''", "'")
    return s


def split_declaration(sig: str) -> tuple[str, Optional[str]]:
    """Split `Name = expression` at the first `=` outside a quoted name.

    Returns (unquoted name, expression), with expression None when there is no `=`.
    """
    in_quote = False
    for i, ch in enumerate(sig):
        if ch == "'":
            in_quote = not in_quote
        elif ch == "=" and not in_quote:
            return unquote(sig[:i]), sig[i + 1:].strip()
    return unquote(sig), None


def parse_col_ref(ref_str: str) -> tuple[str, str]:
    """Parse 'Table Name'.ColumnName or TableName.ColumnName."""
    m = _COL_REF_RE.match(ref_str.strip())
    if m:
        tbl = m.group(1).replace("''", "'") if m.group(1) is not None else m.group(2)
        return tbl, unquote(m.group(3))
    return "", ""


def _keyword(stripped: str, keyword: str) -> Optional[str]:
    """If `stripped` is `keyword` followed by a space or tab, return the rest of the line."""
    if stripped.startswith(keyword) and stripped[len(keyword):len(keyword) + 1] in (" ", "\t"):
        return stripped[len(keyword) + 1:].strip()
    return None


def _strip_fence(expr: str) -> str:
    """Remove the ``` delimiters TMDL puts around verbatim multi-line expressions."""
    if expr.startswith(_FENCE):
        expr = expr[len(_FENCE):].rstrip()
        if expr.endswith(_FENCE):
            expr = expr[:-len(_FENCE)]
    return expr.strip()


def parse_tmdl_table(file_path: Path) -> Optional[RawTable]:
    """Parse a single TMDL table file. Raises ParseError if it cannot be read or decoded."""
    return parse_tmdl_table_text(read_text(file_path), str(file_path))


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
    in_fence = False

    current_item_type: Optional[str] = None
    current_item_data: dict[str, Any] = {}
    current_expr_lines: list[str] = []

    def flush_current() -> None:
        nonlocal current_item_type, current_item_data, current_expr_lines
        if not current_item_type:
            return
        expression = _strip_fence("\n".join(current_expr_lines).strip())
        if current_item_type == "measure":
            current_item_data["expression"] = expression
            current_item_data["_table"] = table_name
            measures.append(current_item_data)
        elif current_item_type == "calc_col":
            current_item_data["expression"] = expression
            current_item_data["type"] = "calculated"
            current_item_data["_table"] = table_name
            calc_cols.append(current_item_data)
        elif current_item_type == "column":
            current_item_data["_table"] = table_name
            columns.append(current_item_data)
        elif current_item_type == "calc_item":
            current_item_data["expression"] = expression
            current_item_data["_table"] = table_name
            calculation_items.append(current_item_data)
        current_item_type = None
        current_item_data = {}
        current_expr_lines = []

    def start_expression(inline_expr: Optional[str]) -> None:
        nonlocal current_expr_lines, in_fence
        current_expr_lines = [inline_expr] if inline_expr else []
        in_fence = inline_expr == _FENCE

    for line in lines:
        stripped = line.strip()
        if in_fence:
            # Inside ``` ... ``` every line is expression text, even one that
            # looks like a property or a declaration.
            current_expr_lines.append(stripped)
            if stripped.endswith(_FENCE):
                in_fence = False
            continue

        if not stripped:
            if current_item_type in ("measure", "calc_col", "calc_item"):
                current_expr_lines.append("")
            elif in_partition_source:
                partition_source_lines.append("")
            continue

        if stripped.startswith("///"):
            flush_current()
            continue
        elif (table_sig := _keyword(stripped, "table")) is not None and (
            line[0] not in " \t" or not table_name
        ):
            # `table` is a top-level declaration. An indented one is accepted only
            # as the first declaration, so expression text can't rename the table.
            flush_current()
            table_name = unquote(table_sig)
            if "DateTable" in table_name or "LocalDateTable" in table_name:
                is_date_table = True
        elif current_item_type is None and stripped in ("isHidden", "isHidden: true"):
            hidden = True
        elif (item_sig := _keyword(stripped, "calculationItem")) is not None:
            flush_current()
            in_partition_source = False
            current_item_type = "calc_item"
            item_name, inline_expr = split_declaration(item_sig)
            current_item_data = {"name": item_name, "format_string": ""}
            start_expression(inline_expr)
        elif (measure_sig := _keyword(stripped, "measure")) is not None:
            flush_current()
            in_partition_source = False
            current_item_type = "measure"
            m_name, inline_expr = split_declaration(measure_sig)
            current_item_data = {"name": m_name, "annotations": []}
            start_expression(inline_expr)
        elif (col_sig := _keyword(stripped, "column")) is not None:
            flush_current()
            in_partition_source = False
            col_name, inline_expr = split_declaration(col_sig)
            current_item_data = {"name": col_name, "dataType": "string", "annotations": []}
            if inline_expr is None:
                current_item_type = "column"
            else:
                current_item_type = "calc_col"
                start_expression(inline_expr)
        elif _keyword(stripped, "partition") is not None:
            flush_current()
            in_partition_source = True
        elif (ann_str := _keyword(stripped, "annotation")) is not None:
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
    """Parse a TMDL relationships.tmdl file. Raises ParseError if it cannot be read or decoded."""
    return parse_tmdl_relationships_text(read_text(rel_file))


def parse_tmdl_relationships_text(content: str) -> list[RawRelationship]:
    """Parse the text of a relationships.tmdl file.

    Each `relationship <id>` line starts a block, and the `key: value`
    property lines after it belong to that block.
    """
    blocks: list[dict[str, str]] = []
    for line in content.splitlines():
        line_s = line.strip()
        if _keyword(line_s, "relationship") is not None:
            blocks.append({})
        elif blocks and ":" in line_s:
            k, v = line_s.split(":", 1)
            blocks[-1][k.strip()] = v.strip()

    result: list[RawRelationship] = []
    for props in blocks:
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
