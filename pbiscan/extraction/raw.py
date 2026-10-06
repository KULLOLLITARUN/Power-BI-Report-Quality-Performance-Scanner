"""Raw extraction types, error taxonomy and JSON helpers shared by the format parsers.

Everything here is format-agnostic: the TMDL, model.bim, report.json and PBIR
parsers all produce these dataclasses, and PBIPReader assembles them into a
RawExtraction.

Error taxonomy:
  INPUT_ERROR          — bad path, not a directory, etc.
  PARSE_ERROR          — JSON decode failure
  SCHEMA_ERROR         — required field missing in a parsed file
  UNSUPPORTED_ARTIFACT — reserved for unrecognised artifact formats (not currently raised)
  RULE_ERROR           — (used by engine, not here)
  RENDER_ERROR         — (used by renderer, not here)
  CONFIG_ERROR         — (used by scoring, not here)
"""
from __future__ import annotations

import codecs
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
    """Unrecognised artifact format. Reserved; not currently raised by PBIPReader."""
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
    calculation_items: list[dict[str, Any]] = field(default_factory=list)
    partition_source: str = ""
    source_file: str = ""


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
    # Measures referenced by page-level filters / page config (not by any one visual)
    filter_measure_refs: list[str] = field(default_factory=list)


@dataclass
class RawExtraction:
    """Everything parsed from a PBIP directory — no analysis, no scoring."""
    report_name: str
    source_path: str
    tables: list[RawTable] = field(default_factory=list)
    relationships: list[RawRelationship] = field(default_factory=list)
    pages: list[RawPage] = field(default_factory=list)
    roles: list[dict[str, Any]] = field(default_factory=list)
    tmdl_roles: list[dict[str, Any]] = field(default_factory=list)
    # Measures referenced by report-level filters, report config and bookmarks
    report_measure_refs: list[str] = field(default_factory=list)
    # Report-level ("thin report") measures: {"name", "table", "expression"}
    report_extension_measures: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Files that exist but could not be read or understood. Any of them could
    # define or reference measures, so unused-measure detection is unsafe
    # while this is non-empty.
    unread_files: list[str] = field(default_factory=list)


@dataclass
class RawModel:
    """What a semantic model parser (TMDL or model.bim) returns."""
    tables: list[RawTable] = field(default_factory=list)
    relationships: list[RawRelationship] = field(default_factory=list)
    roles: list[dict[str, Any]] = field(default_factory=list)
    tmdl_roles: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unread_files: list[str] = field(default_factory=list)

    def skip(self, path: Path, reason: str) -> None:
        """Record a file that was left out of the model, and why."""
        self.warnings.append(f"Skipped {path}: {reason}")
        self.unread_files.append(str(path))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def decode_text(data: bytes, path: Path | str = "<bytes>") -> str:
    """Decode file bytes as UTF-8, honoring a UTF-8 or UTF-16 byte-order mark.

    Editors on Windows often save with a BOM; without this, a BOM makes the
    first TMDL line unrecognizable and makes json.loads reject the file.
    """
    try:
        if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            return data.decode("utf-16")
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ParseError(f"Cannot decode {path} as UTF-8: {exc}") from exc


def read_text(path: Path) -> str:
    """Read a text artifact, raising ParseError if it cannot be read or decoded."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ParseError(f"Cannot read {path}: {exc}") from exc
    return decode_text(data, path)


def load_json(path: Path) -> Any:
    """Load and parse a JSON file, raising ParseError on failure."""
    text = read_text(path)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParseError(f"JSON parse error in {path}: {exc}") from exc


@contextmanager
def expect_structure(path: Path | str) -> Iterator[None]:
    """Turn a wrong-shaped document (a list where an object belongs, etc.) into SchemaError.

    The parsers index into JSON with .get() chains; on a valid file of the wrong
    shape those raise AttributeError/TypeError deep inside. This names the file
    instead of surfacing a traceback.
    """
    try:
        yield
    except (AttributeError, TypeError, KeyError) as exc:
        raise SchemaError(f"Unexpected structure in {path}: {exc}") from exc


def extract_measure_names(obj: Any) -> set[str]:
    """Recursively traverse any JSON subtree and collect every Measure.Property name."""
    refs: set[str] = set()
    if isinstance(obj, dict):
        # Direct Measure expression object, e.g. {"Measure": {"Property": "TotalSales"}}
        if "Measure" in obj and isinstance(obj["Measure"], dict):
            prop = obj["Measure"].get("Property", "")
            if prop and isinstance(prop, str):
                refs.add(prop)
        for v in obj.values():
            refs.update(extract_measure_names(v))
    elif isinstance(obj, list):
        for item in obj:
            refs.update(extract_measure_names(item))
    return refs


def collect_extension_measures(model_extensions: Any) -> list[dict[str, Any]]:
    """Flatten `[{entities: [{name, measures: [{name, expression}]}]}]` into measure dicts."""
    measures: list[dict[str, Any]] = []
    if not isinstance(model_extensions, list):
        return measures
    for ext in model_extensions:
        if not isinstance(ext, dict):
            continue
        for entity in ext.get("entities", []) or []:
            if not isinstance(entity, dict):
                continue
            for m in entity.get("measures", []) or []:
                if isinstance(m, dict) and m.get("name"):
                    expr = m.get("expression", "")
                    measures.append({
                        "name": m["name"],
                        "table": entity.get("name", ""),
                        "expression": "\n".join(expr) if isinstance(expr, list) else str(expr or ""),
                    })
    return measures
