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
import os
from pathlib import Path
from typing import Any, Optional

from pbiscan.extraction.bim_parser import parse_bim_model
from pbiscan.extraction.pbir_parser import parse_pbir_pages, parse_pbir_report_level
from pbiscan.extraction.raw import (
    InputError,
    ParseError,
    PBIScanError,
    RawExtraction,
    RawModel,
    RawPage,
    RawRelationship,
    RawTable,
    RawVisual,
    SchemaError,
    UnsupportedArtifactError,
    load_json,
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
        pbip_file: Optional[Path] = None
        if root.is_file():
            # If the user passed the .pbip file directly, use its stem
            report_name = root.stem
            pbip_file = root if root.suffix.lower() == ".pbip" else None
            root = root.parent
        else:
            # If a folder was passed, use the first .pbip file in name order to name the report
            pbip_files = sorted(root.glob("*.pbip"))
            pbip_file = pbip_files[0] if pbip_files else None
            report_name = pbip_file.stem if pbip_file else root.name

        if not root.is_dir():
            raise InputError(f"Path is not a directory: {root}")

        report_dir, semantic_model_dir = resolve_project_dirs(root, pbip_file)

        warnings: list[str] = []
        unread_files: list[str] = []
        if semantic_model_dir:
            model = self._parse_semantic_model(semantic_model_dir)
            warnings.extend(model.warnings)
            unread_files.extend(model.unread_files)
        else:
            model = RawModel()
            warnings.append("No SemanticModel directory found — model analysis skipped.")

        pages: list[RawPage] = []
        report_measure_refs: list[str] = []
        report_extension_measures: list[dict[str, Any]] = []
        if report_dir:
            pages, w = self._parse_report(report_dir)
            warnings.extend(w)
            report_unread: list[str] = []
            report_measure_refs, report_extension_measures = self._parse_report_level(report_dir, report_unread)
            warnings.extend(f"Skipped {path}: not readable as a JSON object" for path in report_unread)
            unread_files.extend(report_unread)
        else:
            warnings.append("No Report directory found — report analysis skipped.")

        logger.info(
            "Extracted %d tables, %d relationships, %d pages",
            len(model.tables), len(model.relationships), len(pages),
        )

        return RawExtraction(
            report_name=report_name,
            source_path=str(root),
            tables=model.tables,
            relationships=model.relationships,
            pages=pages,
            roles=model.roles,
            tmdl_roles=model.tmdl_roles,
            report_measure_refs=report_measure_refs,
            report_extension_measures=report_extension_measures,
            warnings=warnings,
            unread_files=unread_files,
        )

    def _parse_semantic_model(self, sm_dir: Path) -> RawModel:
        """Parse model.bim if present, otherwise TMDL."""
        model_bim = sm_dir / "model.bim"
        if model_bim.exists():
            logger.info("Parsing model.bim: %s", model_bim)
            return parse_bim_model(model_bim)

        if any(sm_dir.rglob("*.tmdl")):
            logger.info("Parsing TMDL semantic model in: %s", sm_dir)
            return parse_tmdl_model(sm_dir)

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

    def _parse_report_level(
        self, report_dir: Path, unread: list[str]
    ) -> tuple[list[str], list[dict[str, Any]]]:
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
            legacy_refs, legacy_ext = parse_report_json_level(legacy_json, unread)
            refs |= legacy_refs
            extensions.extend(legacy_ext)

        definition_dir = report_dir / "definition"
        if definition_dir.is_dir():
            pbir_refs, pbir_ext = parse_pbir_report_level(definition_dir, unread)
            refs |= pbir_refs
            extensions.extend(pbir_ext)

        return sorted(refs), extensions


def _load_json_object(path: Path) -> dict[str, Any]:
    """The JSON object in `path`, or {} when the file is missing, unreadable or not an object."""
    try:
        data = load_json(path)
    except (ParseError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _dir_inside(path: Path, root: Path) -> bool:
    """True when `path` is an existing directory at or below `root`."""
    try:
        path.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return path.is_dir()


def resolve_project_dirs(root: Path, pbip_file: Optional[Path]) -> tuple[Optional[Path], Optional[Path]]:
    """The (report folder, semantic model folder) this project means, the way Power BI finds them.

    Follows the .pbip file to its report (`artifacts[0].report.path`), then that report's
    `definition.pbir` to its model (`datasetReference.byPath.path`). A link that does not exist or
    leaves the project folder is not followed. Whatever cannot be resolved falls back to the first
    matching folder in name order, so a folder holding several reports or models gives the same
    answer on every machine. Mirrored by selectProjectFiles in studio-ui/src/engine/clientScanner.ts.
    """
    report_dir: Optional[Path] = None
    model_dir: Optional[Path] = None
    if pbip_file is not None:
        artifacts = _load_json_object(pbip_file).get("artifacts")
        first = artifacts[0] if isinstance(artifacts, list) and artifacts else None
        report = first.get("report") if isinstance(first, dict) else None
        report_path = report.get("path") if isinstance(report, dict) else None
        if isinstance(report_path, str):
            candidate = Path(os.path.normpath(root / report_path))
            if _dir_inside(candidate, root):
                report_dir = candidate
    if report_dir is not None:
        reference = _load_json_object(report_dir / "definition.pbir").get("datasetReference")
        by_path = reference.get("byPath") if isinstance(reference, dict) else None
        model_path = by_path.get("path") if isinstance(by_path, dict) else None
        if isinstance(model_path, str):
            candidate = Path(os.path.normpath(report_dir / model_path))
            if _dir_inside(candidate, root):
                model_dir = candidate
    return report_dir or _find_dir(root, ".Report"), model_dir or _find_dir(root, ".SemanticModel")


def _find_dir(root: Path, suffix: str) -> Optional[Path]:
    """Return the first child directory of `root` whose name ends with `suffix`, in name order."""
    for item in sorted(root.iterdir(), key=lambda p: p.name):
        if item.is_dir() and item.name.endswith(suffix):
            logger.debug("%s dir: %s", suffix, item)
            return item
    return None
