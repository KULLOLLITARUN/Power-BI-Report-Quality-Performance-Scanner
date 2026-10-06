"""PBIP Extraction layer — locates the artifacts in a PBIP project and dispatches to
the format parsers:

  tmdl_parser    — TMDL semantic model (definition/*.tmdl)
  bim_parser     — model.bim (TMSL JSON)
  report_parser  — legacy report.json
  pbir_parser    — PBIR (definition/pages/*/page.json + visuals/)

This layer returns raw parsed data ONLY. It must NOT detect issues, calculate
scores, generate recommendations, classify severity or contain rule logic.

The error types and Raw* dataclasses live in `raw.py` and are re-exported here.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from pbiscan.extraction.bim_parser import parse_bim_model
from pbiscan.extraction.pbir_parser import parse_pbir_pages, parse_pbir_report_level
from pbiscan.extraction.raw import (
    InputError,
    ParseError,
    PBIScanError,
    RawExtraction,
    RawPage,
    RawRelationship,
    RawTable,
    RawVisual,
    SchemaError,
    UnsupportedArtifactError,
)
from pbiscan.extraction.report_parser import parse_report_json, parse_report_json_level
from pbiscan.extraction.tmdl_parser import parse_tmdl_model

__all__ = [
    "InputError",
    "PBIPReader",
    "PBIScanError",
    "ParseError",
    "RawExtraction",
    "RawPage",
    "RawRelationship",
    "RawTable",
    "RawVisual",
    "SchemaError",
    "UnsupportedArtifactError",
]

logger = logging.getLogger(__name__)


class PBIPReader:
    """Reads a PBIP project directory and returns a RawExtraction.

    Semantic model formats: model.bim (TMSL JSON) and TMDL
    (definition/*.tmdl, including tables/, relationships.tmdl and roles/).

    Report formats: legacy report.json (sections/visualContainers) and PBIR
    (definition/pages/*/page.json + visuals/*/visual.json), plus report-level
    filters, bookmarks and reportExtensions.json for measure-usage tracking.
    """

    def read(self, path: str | Path) -> RawExtraction:
        """Parse a PBIP directory.

        Args:
            path: Path to the PBIP project directory (or its .pbip file).

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
            report_name = pbip_files[0].stem if pbip_files else root.name

        if not root.is_dir():
            raise InputError(f"Path is not a directory: {root}")

        semantic_model_dir = _find_dir(root, ".SemanticModel")
        report_dir = _find_dir(root, ".Report")

        tables: list[RawTable] = []
        relationships: list[RawRelationship] = []
        roles: list[dict[str, Any]] = []
        tmdl_roles: list[dict[str, Any]] = []
        warnings: list[str] = []
        if semantic_model_dir:
            tables, relationships, roles, tmdl_roles = self._parse_semantic_model(semantic_model_dir)
        else:
            warnings.append("No SemanticModel directory found — model analysis skipped.")

        pages: list[RawPage] = []
        report_measure_refs: list[str] = []
        report_extension_measures: list[dict[str, Any]] = []
        if report_dir:
            pages, w = self._parse_report(report_dir)
            warnings.extend(w)
            report_measure_refs, report_extension_measures = self._parse_report_level(report_dir)
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
            roles=roles,
            tmdl_roles=tmdl_roles,
            report_measure_refs=report_measure_refs,
            report_extension_measures=report_extension_measures,
            warnings=warnings,
        )

    def _parse_semantic_model(
        self, sm_dir: Path
    ) -> tuple[list[RawTable], list[RawRelationship], list[dict[str, Any]], list[dict[str, Any]]]:
        """Parse model.bim if present, otherwise TMDL. Returns (tables, relationships, bim_roles, tmdl_roles)."""
        model_bim = sm_dir / "model.bim"
        if model_bim.exists():
            logger.info("Parsing model.bim: %s", model_bim)
            tables, relationships, roles = parse_bim_model(model_bim)
            return tables, relationships, roles, []

        if any(sm_dir.rglob("*.tmdl")):
            logger.info("Parsing TMDL semantic model in: %s", sm_dir)
            tables, relationships, tmdl_roles = parse_tmdl_model(sm_dir)
            return tables, relationships, [], tmdl_roles

        raise SchemaError(f"No model.bim or TMDL definitions found in {sm_dir}")

    def _parse_report(self, report_dir: Path) -> tuple[list[RawPage], list[str]]:
        """Parse report pages. Tries legacy report.json first, then PBIR."""
        report_json = report_dir / "report.json"
        if report_json.exists():
            logger.info("Parsing report.json: %s", report_json)
            return parse_report_json(report_json), []

        definition_dir = report_dir / "definition"
        if definition_dir.exists() and (definition_dir / "pages").exists():
            logger.info("Parsing PBIR format: %s", definition_dir)
            return parse_pbir_pages(definition_dir), []

        return [], [
            f"No supported report format found in {report_dir}. "
            "Expected: report.json or definition/pages/ (PBIR)."
        ]

    def _parse_report_level(self, report_dir: Path) -> tuple[list[str], list[dict[str, Any]]]:
        """Collect report-wide measure references and report-level measures.

        Covers report-level filters, report config and bookmarks (legacy
        report.json and PBIR definition/report.json + bookmarks/), plus
        report-level "thin report" measures (legacy config.modelExtensions and
        PBIR definition/reportExtensions.json), whose DAX can depend on model
        measures that no visual binds directly.
        """
        refs: set[str] = set()
        extensions: list[dict[str, Any]] = []

        legacy_json = report_dir / "report.json"
        if legacy_json.exists():
            legacy_refs, legacy_ext = parse_report_json_level(legacy_json)
            refs |= legacy_refs
            extensions.extend(legacy_ext)

        definition_dir = report_dir / "definition"
        if definition_dir.is_dir():
            pbir_refs, pbir_ext = parse_pbir_report_level(definition_dir)
            refs |= pbir_refs
            extensions.extend(pbir_ext)

        return sorted(refs), extensions


def _find_dir(root: Path, suffix: str) -> Optional[Path]:
    """Return the first child directory of `root` whose name ends with `suffix`."""
    for item in root.iterdir():
        if item.is_dir() and item.name.endswith(suffix):
            logger.debug("%s dir: %s", suffix, item)
            return item
    return None
