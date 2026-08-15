"""PBIP Extraction layer — reads and parses PBIP artifact files.

This module returns raw parsed data ONLY.

It must NOT:
  - detect issues
  - calculate scores
  - generate recommendations
  - classify severity
  - contain rule logic

Error taxonomy:
  INPUT_ERROR          — bad path, not a directory, etc.
  PARSE_ERROR          — JSON decode failure
  SCHEMA_ERROR         — required field missing in a parsed file
  UNSUPPORTED_ARTIFACT — file format not yet supported (e.g. pure TMDL)
  RULE_ERROR           — (used by engine, not here)
  RENDER_ERROR         — (used by renderer, not here)
  CONFIG_ERROR         — (used by scoring, not here)
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class PBIScanError(Exception):
    """Base error for all pbiscan errors."""
    error_type: str = "UNKNOWN_ERROR"


class InputError(PBIScanError):
    """Bad input path or directory."""
    error_type = "INPUT_ERROR"


class ParseError(PBIScanError):
    """JSON or file parsing failure."""
    error_type = "PARSE_ERROR"


class SchemaError(PBIScanError):
    """Required field missing in a parsed artifact."""
    error_type = "SCHEMA_ERROR"


class UnsupportedArtifactError(PBIScanError):
    """File format not yet supported."""
    error_type = "UNSUPPORTED_ARTIFACT"


# ---------------------------------------------------------------------------
# Raw extraction result
# ---------------------------------------------------------------------------

@dataclass
class RawTable:
    name: str
    hidden: bool = False
    is_date_table: bool = False
    columns: list[dict[str, Any]] = field(default_factory=list)
    measures: list[dict[str, Any]] = field(default_factory=list)
    calculated_columns: list[dict[str, Any]] = field(default_factory=list)
    annotations: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RawRelationship:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawVisual:
    visual_type: str
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    fields_used: list[str] = field(default_factory=list)
    measure_refs: list[str] = field(default_factory=list)
    is_slicer: bool = False
    hidden: bool = False


@dataclass
class RawPage:
    name: str
    display_name: str = ""
    visibility: int = 0
    visuals: list[RawVisual] = field(default_factory=list)


@dataclass
class RawExtraction:
    """Everything parsed from a PBIP directory — no analysis, no scoring."""
    report_name: str
    source_path: str
    tables: list[RawTable] = field(default_factory=list)
    relationships: list[RawRelationship] = field(default_factory=list)
    pages: list[RawPage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

class PBIPReader:
    """Reads a PBIP project directory and returns a RawExtraction.

    Supported semantic model format: model.bim (TMSL JSON).
    TMDL (split .tmdl files) is not yet supported in v1.

    Supported report format: report.json (legacy PBIP report format).
    PBIR (split page/visual JSON files) support is planned for v1.1.
    """

    def read(self, path: str | Path) -> RawExtraction:
        """Parse a PBIP directory.

        Args:
            path: Path to the PBIP project directory.

        Returns:
            RawExtraction with all parsed data.

        Raises:
            InputError: if the path is invalid.
            ParseError: if a file cannot be parsed.
            SchemaError: if a required field is missing.
        """
        root = Path(path)
        logger.info("Loading PBIP: %s", root)

        if not root.exists():
            raise InputError(f"Path does not exist: {root}")
        if root.is_file():
            # If the user passed the .pbip file directly, use its stem
            report_name = root.stem
            root = root.parent
        else:
            # If a folder was passed, check for any .pbip file inside to name the report
            pbip_files = list(root.glob("*.pbip"))
            if pbip_files:
                report_name = pbip_files[0].stem
            else:
                report_name = root.name

        if not root.is_dir():
            raise InputError(f"Path is not a directory: {root}")

        # Locate sub-directories
        semantic_model_dir = self._find_semantic_model_dir(root)
        report_dir = self._find_report_dir(root)

        # Parse model
        tables, relationships, warnings = [], [], []
        if semantic_model_dir:
            tables, relationships, w = self._parse_semantic_model(semantic_model_dir)
            warnings.extend(w)
        else:
            warnings.append("No SemanticModel directory found — model analysis skipped.")

        # Parse report
        pages: list[RawPage] = []
        if report_dir:
            pages, w = self._parse_report(report_dir)
            warnings.extend(w)
        else:
            warnings.append("No Report directory found — report analysis skipped.")

        logger.info(
            "Extracted %d tables, %d relationships, %d pages",
            len(tables), len(relationships), len(pages),
        )

        return RawExtraction(
            report_name=report_name,
            source_path=str(root),
            tables=tables,
            relationships=relationships,
            pages=pages,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Directory discovery
    # ------------------------------------------------------------------

    def _find_semantic_model_dir(self, root: Path) -> Optional[Path]:
        """Find the .SemanticModel directory inside the PBIP root."""
        for item in root.iterdir():
            if item.is_dir() and item.name.endswith(".SemanticModel"):
                logger.debug("SemanticModel dir: %s", item)
                return item
        return None

    def _find_report_dir(self, root: Path) -> Optional[Path]:
        """Find the .Report directory inside the PBIP root."""
        for item in root.iterdir():
            if item.is_dir() and item.name.endswith(".Report"):
                logger.debug("Report dir: %s", item)
                return item
        return None

    # ------------------------------------------------------------------
    # Semantic model parsing
    # ------------------------------------------------------------------

    def _parse_semantic_model(
        self, sm_dir: Path
    ) -> tuple[list[RawTable], list[RawRelationship], list[str]]:
        """Parse the semantic model directory."""
        warnings: list[str] = []
        model_bim = sm_dir / "model.bim"

        if model_bim.exists():
            logger.info("Parsing model.bim: %s", model_bim)
            raw_model = self._load_json(model_bim)
            model_node = raw_model.get("model", raw_model)
            tables = self._parse_tables(model_node.get("tables", []))
            relationships = self._parse_relationships(model_node.get("relationships", []))
            return tables, relationships, warnings

        # Check for TMDL format
        tmdl_files = list(sm_dir.rglob("*.tmdl"))
        if tmdl_files:
            logger.info("Parsing TMDL semantic model in: %s", sm_dir)
            tables, relationships = self._parse_tmdl_semantic_model(sm_dir)
            return tables, relationships, warnings

        raise SchemaError(f"No model.bim or TMDL definitions found in {sm_dir}")

    def _parse_tmdl_semantic_model(
        self, sm_dir: Path
    ) -> tuple[list[RawTable], list[RawRelationship]]:
        """Parse TMDL semantic model format (definition/tables/*.tmdl and relationships.tmdl)."""
        definition_dir = sm_dir / "definition" if (sm_dir / "definition").exists() else sm_dir
        tables: list[RawTable] = []
        relationships: list[RawRelationship] = []

        # Parse tables
        tables_dir = definition_dir / "tables"
        if tables_dir.exists():
            for tmdl_file in sorted(tables_dir.glob("*.tmdl")):
                t = self._parse_single_tmdl_table(tmdl_file)
                if t:
                    tables.append(t)

        # Parse relationships
        rel_file = definition_dir / "relationships.tmdl"
        if rel_file.exists():
            relationships = self._parse_tmdl_relationships(rel_file)

        return tables, relationships

    def _unquote_tmdl(self, s: str) -> str:
        s = s.strip()
        if s.startswith("'") and s.endswith("'") and len(s) >= 2:
            return s[1:-1]
        return s

    def _parse_tmdl_col_ref(self, ref_str: str) -> tuple[str, str]:
        """Parse 'Table Name'.ColumnName or TableName.ColumnName."""
        ref_str = ref_str.strip()
        import re
        m = re.match(r"^('([^']+)'|([^.]+))\.(.*)$", ref_str)
        if m:
            tbl = m.group(2) or m.group(3)
            col = self._unquote_tmdl(m.group(4))
            return tbl, col
        return "", ""

    def _parse_single_tmdl_table(self, file_path: Path) -> Optional[RawTable]:
        """Parse a single TMDL table file."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not read TMDL file %s: %exc", file_path, exc)
            return None

        lines = content.splitlines()
        table_name = ""
        hidden = False
        is_date_table = False
        columns: list[dict[str, Any]] = []
        measures: list[dict[str, Any]] = []
        calc_cols: list[dict[str, Any]] = []
        annotations: list[dict[str, Any]] = []

        current_item_type: Optional[str] = None
        current_item_data: dict[str, Any] = {}
        current_expr_lines: list[str] = []

        def flush_current():
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
            current_item_type = None
            current_item_data = {}
            current_expr_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current_item_type in ("measure", "calc_col"):
                    current_expr_lines.append("")
                continue

            if line.startswith("///") or stripped.startswith("///"):
                flush_current()
                continue
            elif line.startswith("table "):
                flush_current()
                table_name = self._unquote_tmdl(line[6:].strip())
                if "DateTable" in table_name or "LocalDateTable" in table_name:
                    is_date_table = True
            elif current_item_type is None and stripped in ("isHidden", "isHidden: true"):
                hidden = True
            elif stripped.startswith("measure "):
                flush_current()
                current_item_type = "measure"
                measure_sig = stripped[8:].strip()
                if "=" in measure_sig:
                    parts = measure_sig.split("=", 1)
                    m_name = self._unquote_tmdl(parts[0].strip())
                    inline_expr = parts[1].strip()
                    current_item_data = {"name": m_name, "annotations": []}
                    current_expr_lines = [inline_expr] if inline_expr else []
                else:
                    m_name = self._unquote_tmdl(measure_sig)
                    current_item_data = {"name": m_name, "annotations": []}
                    current_expr_lines = []
            elif stripped.startswith("column ") and "=" in stripped:
                flush_current()
                current_item_type = "calc_col"
                col_sig = stripped[7:].strip()
                parts = col_sig.split("=", 1)
                col_name = self._unquote_tmdl(parts[0].strip())
                inline_expr = parts[1].strip()
                current_item_data = {"name": col_name, "dataType": "string", "annotations": []}
                current_expr_lines = [inline_expr] if inline_expr else []
            elif stripped.startswith("column "):
                flush_current()
                current_item_type = "column"
                col_name = self._unquote_tmdl(stripped[7:].strip())
                current_item_data = {"name": col_name, "dataType": "string", "annotations": []}
            elif stripped.startswith("partition "):
                flush_current()
                current_item_type = "partition"
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
        )

    def _parse_tmdl_relationships(self, rel_file: Path) -> list[RawRelationship]:
        """Parse TMDL relationships.tmdl file."""
        try:
            content = rel_file.read_text(encoding="utf-8")
        except OSError:
            return []

        result: list[RawRelationship] = []
        blocks = content.split("relationship ")
        for block in blocks:
            if not block.strip():
                continue
            props: dict[str, str] = {}
            for line in block.splitlines():
                line_s = line.strip()
                if ":" in line_s:
                    k, v = line_s.split(":", 1)
                    props[k.strip()] = v.strip()

            from_col_ref = props.get("fromColumn", "")
            to_col_ref = props.get("toColumn", "")
            f_t, f_c = self._parse_tmdl_col_ref(from_col_ref)
            t_t, t_c = self._parse_tmdl_col_ref(to_col_ref)

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

    def _parse_tables(self, raw_tables: list[dict]) -> list[RawTable]:
        """Parse raw table definitions from model.bim."""
        result: list[RawTable] = []
        for raw in raw_tables:
            name = raw.get("name", "")
            if not name:
                continue

            # Detect date table via annotation
            annotations = raw.get("annotations", [])
            is_date_table = self._is_date_table_annotation(annotations)

            # Separate regular columns, measures, and calculated columns
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

            result.append(RawTable(
                name=name,
                hidden=raw.get("isHidden", False),
                is_date_table=is_date_table,
                columns=raw_columns,
                measures=raw_measures,
                calculated_columns=raw_calc_cols,
                annotations=annotations,
            ))
        return result

    def _is_date_table_annotation(self, annotations: list[dict]) -> bool:
        """Check if annotations mark this as a date table."""
        date_table_annotation_names = (
            "PBI_IsDateTable",           # pbiscan convention
            "__PBI_LocalDateTable",      # Power BI auto date/time
            "PBI_TemporalTable",         # alternate Power BI marker
        )
        for ann in annotations:
            if ann.get("name", "") in date_table_annotation_names:
                value = str(ann.get("value", "")).lower()
                if value in ("true", "1", "yes"):
                    return True
        return False

    def _parse_relationships(self, raw_rels: list[dict]) -> list[RawRelationship]:
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

    # ------------------------------------------------------------------
    # Report parsing
    # ------------------------------------------------------------------

    def _parse_report(
        self, report_dir: Path
    ) -> tuple[list[RawPage], list[str]]:
        """Parse the report directory.

        Tries legacy report.json first, then PBIR format.
        """
        warnings: list[str] = []

        # Legacy format: single report.json
        report_json = report_dir / "report.json"
        if report_json.exists():
            logger.info("Parsing report.json: %s", report_json)
            pages = self._parse_report_json(report_json)
            return pages, warnings

        # PBIR format: definition/ folder with pages/ subfolder
        definition_dir = report_dir / "definition"
        if definition_dir.exists() and (definition_dir / "pages").exists():
            logger.info("Parsing PBIR format: %s", definition_dir)
            pages = self._parse_pbir_format(definition_dir)
            return pages, warnings

        warnings.append(
            f"No supported report format found in {report_dir}. "
            "Expected: report.json or definition/pages/ (PBIR)."
        )
        return [], warnings

    def _parse_report_json(self, report_json: Path) -> list[RawPage]:
        """Parse legacy report.json format."""
        raw = self._load_json(report_json)
        pages: list[RawPage] = []

        sections = raw.get("sections", [])
        for section in sections:
            name = section.get("name", "")
            display_name = section.get("displayName", name)
            visibility = section.get("visibility", 0)

            visuals = self._parse_visual_containers(
                section.get("visualContainers", [])
            )

            pages.append(RawPage(
                name=name,
                display_name=display_name,
                visibility=visibility,
                visuals=visuals,
            ))
        return pages

    def _parse_pbir_format(self, definition_dir: Path) -> list[RawPage]:
        """Parse PBIR format: definition/pages/<name>/page.json + visuals/."""
        pages: list[RawPage] = []
        pages_dir = definition_dir / "pages"

        for page_dir in sorted(pages_dir.iterdir()):
            if not page_dir.is_dir():
                continue

            page_json_path = page_dir / "page.json"
            if not page_json_path.exists():
                continue

            page_data = self._load_json(page_json_path)
            name = page_data.get("name", page_dir.name)
            display_name = page_data.get("displayName", name)
            visibility = page_data.get("visibility", 0)

            visuals: list[RawVisual] = []
            visuals_dir = page_dir / "visuals"
            if visuals_dir.exists():
                for visual_dir in sorted(visuals_dir.iterdir()):
                    visual_json = visual_dir / "visual.json"
                    if visual_json.exists():
                        v = self._parse_pbir_visual(self._load_json(visual_json))
                        if v:
                            visuals.append(v)

            pages.append(RawPage(
                name=name,
                display_name=display_name,
                visibility=visibility,
                visuals=visuals,
            ))

        return pages

    def _parse_pbir_visual(self, raw: dict) -> Optional[RawVisual]:
        """Parse a single PBIR visual.json file."""
        visual_node = raw.get("visual", {})
        visual_type = visual_node.get("visualType", "unknown")

        position = raw.get("position", {})
        x = position.get("x", 0.0)
        y = position.get("y", 0.0)
        width = position.get("width", 0.0)
        height = position.get("height", 0.0)

        # Extract measure references from query state
        measure_refs, fields_used = self._extract_measure_refs_from_pbir_query(
            visual_node.get("query", {})
        )

        return RawVisual(
            visual_type=visual_type,
            x=x, y=y, width=width, height=height,
            fields_used=fields_used,
            measure_refs=measure_refs,
            is_slicer=(visual_type.lower() == "slicer"),
            hidden=raw.get("hidden", False),
        )

    def _extract_measure_refs_from_pbir_query(
        self, query: dict
    ) -> tuple[list[str], list[str]]:
        """Extract measure names from PBIR query state."""
        measure_refs: list[str] = []
        fields_used: list[str] = []
        query_state = query.get("queryState", {})
        for _bucket_name, bucket in query_state.items():
            for proj in bucket.get("projections", []):
                field = proj.get("field", {})
                if "Measure" in field:
                    measure = field["Measure"]
                    prop = measure.get("Property", "")
                    if prop:
                        measure_refs.append(prop)
                        fields_used.append(prop)
        return measure_refs, fields_used

    def _parse_visual_containers(
        self, containers: list[dict]
    ) -> list[RawVisual]:
        """Parse visualContainers array from legacy report.json."""
        visuals: list[RawVisual] = []
        for vc in containers:
            v = self._parse_single_visual_container(vc)
            if v:
                visuals.append(v)
        return visuals

    def _parse_single_visual_container(self, vc: dict) -> Optional[RawVisual]:
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

        return RawVisual(
            visual_type=visual_type,
            x=float(vc.get("x", 0)),
            y=float(vc.get("y", 0)),
            width=float(vc.get("width", 0)),
            height=float(vc.get("height", 0)),
            fields_used=fields_used,
            measure_refs=measure_refs,
            is_slicer=(visual_type.lower() == "slicer"),
            hidden=vc.get("hidden", False),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_json(self, path: Path) -> dict:
        """Load and parse a JSON file, raising ParseError on failure."""
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            raise ParseError(f"JSON parse error in {path}: {exc}") from exc
        except OSError as exc:
            raise ParseError(f"Cannot read {path}: {exc}") from exc
