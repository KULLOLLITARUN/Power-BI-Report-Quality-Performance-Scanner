"""Auto Date/Time bloat patcher for MODEL_AUTO_DATETIME_BLOAT."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from pbiscan.canonical.model import CanonicalReport
from pbiscan.engine.issue import AuditIssue
from pbiscan.extraction.tmdl_parser import parse_tmdl_relationships_text
from pbiscan.remediation.models import (
    Patch,
    PatchChunk,
    PatchEvidence,
    PatchLifecycleState,
    RemediationSafety,
    compute_file_sha256,
)
from pbiscan.remediation.patchers.base import BasePatcher


class AutoDatePatcher(BasePatcher):
    """Patcher for M007 — MODEL_AUTO_DATETIME_BLOAT.
    
    Removes auto-generated hidden LocalDateTable_* and DateTableTemplate_* tables
    from model.tmdl and tables definitions in TMDL or model.bim.
    """

    rule_id = "MODEL_AUTO_DATETIME_BLOAT"

    def analyze(self, issue: AuditIssue, report: CanonicalReport, model_dir: Path) -> PatchEvidence:
        """Analyze auto date/time bloat tables and verify lack of direct visual dependencies."""
        preconditions = [
            "model_identified",
            "local_date_tables_detected",
            "target_files_located",
            "zero_direct_visual_bindings",
            "zero_custom_relationship_dependencies",
            "zero_semantic_reference_consumers",
            "clean_syntax_boundary",
        ]
        satisfied: list[str] = []
        violated: list[str] = []

        local_date_tables = [t.name for t in report.model.tables if t.name.startswith("LocalDateTable_")]
        if not local_date_tables:
            violated.append("local_date_tables_detected")
        else:
            satisfied.append("local_date_tables_detected")

        satisfied.append("model_identified")

        # 1. Check visual bindings to LocalDateTable columns
        direct_bindings = False
        for page in report.report.pages:
            for visual in page.visuals:
                for f_used in visual.fields_used:
                    if any(t.lower() in f_used.lower() for t in local_date_tables):
                        direct_bindings = True
                        break
                if direct_bindings:
                    break
            if direct_bindings:
                break

        if not direct_bindings:
            satisfied.append("zero_direct_visual_bindings")
        else:
            violated.append("zero_direct_visual_bindings")

        # 2. Check custom non-variation relationships
        custom_rel = False
        for rel in report.model.relationships:
            from_match = any(t.lower() == rel.from_table.lower() for t in local_date_tables)
            to_match = any(t.lower() == rel.to_table.lower() for t in local_date_tables)
            # Power BI's own relationship runs fact table -> auto table's Date column, and is
            # removed with the table. Anything else touching an auto table was built by a person.
            if (from_match or to_match) and not _is_auto_relationship(rel.from_table, rel.to_table, rel.to_column):
                custom_rel = True
                break

        if not custom_rel:
            satisfied.append("zero_custom_relationship_dependencies")
        else:
            violated.append("zero_custom_relationship_dependencies")

        # 3. Check semantic references
        sem_refs = getattr(report, "semantic_references", None)
        has_sem_ref = False
        if sem_refs and hasattr(sem_refs, "find_by_target"):
            for t in local_date_tables:
                if sem_refs.find_by_target(t):
                    has_sem_ref = True
                    break

        if not has_sem_ref:
            satisfied.append("zero_semantic_reference_consumers")
        else:
            violated.append("zero_semantic_reference_consumers")

        # 4. Locate target files
        model_tmdl = self._find_model_tmdl(model_dir)
        bim_file = self._find_bim_file(model_dir)

        if model_tmdl or bim_file:
            satisfied.append("target_files_located")
        else:
            violated.append("target_files_located")

        satisfied.append("clean_syntax_boundary")

        confidence = 0.95 if not violated else 0.0
        affected_files = []
        if model_tmdl:
            affected_files.append(str(model_tmdl.relative_to(model_dir)))
        elif bim_file:
            affected_files.append(str(bim_file.relative_to(model_dir)))

        affected_objects = [f"Auto Date/Time tables: {', '.join(local_date_tables[:3])}"]

        return PatchEvidence(
            rule_id=self.rule_id,
            finding_key=f"{self.rule_id}::Model",
            confidence=confidence,
            preconditions=preconditions,
            satisfied_preconditions=satisfied,
            violated_preconditions=violated,
            affected_files=affected_files,
            affected_objects=affected_objects,
            dependency_count=len(local_date_tables),
            semantic_risk="MEDIUM",
            expected_resolution=(
                f"Removes {len(local_date_tables)} auto-generated local date table(s) "
                f"and their model references to eliminate model bloat."
            ),
        )

    def generate_patches(
        self,
        issue: AuditIssue,
        evidence: PatchEvidence,
        model_dir: Path,
    ) -> list[Patch]:
        """Generate patches removing the auto date/time tables and everything that wires them in.

        Power BI connects each auto date table to its fact table with a relationship, a
        `variation` block on the fact table's date column, and a `ref table` line in model.tmdl;
        and it re-creates the tables unless `__PBI_TimeIntelligenceEnabled` is switched off. All
        of those go together, so the model is never left pointing at a table that is gone.
        """
        if evidence.violated_preconditions:
            return []

        patches: list[Patch] = []
        model_tmdl = self._find_model_tmdl(model_dir)

        if model_tmdl and model_tmdl.exists():
            # 1. Patch model.tmdl
            p_model = self._patch_model_tmdl(model_tmdl, evidence)
            if p_model:
                patches.append(p_model)

            # 2. Relationships into the auto tables, and the variation blocks that name them
            removed_ids: set[str] = set()
            for rel_file in sorted(model_dir.glob("**/relationships.tmdl")):
                p_rel, ids = self._patch_relationships_tmdl(rel_file, evidence)
                removed_ids |= ids
                if p_rel:
                    patches.append(p_rel)
            patches.extend(self._patch_variations_tmdl(model_dir, removed_ids, evidence))

            # 3. Patch/clear individual LocalDateTable_*.tmdl and DateTableTemplate_*.tmdl files
            for tmdl_file in model_dir.glob("**/*.tmdl"):
                if tmdl_file.name.startswith("LocalDateTable_") or tmdl_file.name.startswith("DateTableTemplate_"):
                    content = tmdl_file.read_text(encoding="utf-8")
                    if content.strip():
                        source_hash = compute_file_sha256(tmdl_file)
                        chunk = PatchChunk.create(
                            start_line=1,
                            end_line=len(content.splitlines(keepends=True)),
                            original_text=content,
                            replacement_text="",
                        )
                        patch_id = f"REM-MODEL_AUTO_DATETIME_BLOAT-{tmdl_file.stem}-{source_hash[:8]}"
                        patches.append(Patch(
                            patch_id=patch_id,
                            rule_id=self.rule_id,
                            file_path=tmdl_file,
                            source_hash=source_hash,
                            safety=RemediationSafety.REVIEW_REQUIRED,
                            state=PatchLifecycleState.PLANNED,
                            evidence=evidence,
                            chunks=[chunk],
                            rationale=f"Clear auto-generated date table definition in {tmdl_file.name}.",
                        ))
            return patches

        bim_file = self._find_bim_file(model_dir)
        if bim_file and bim_file.exists():
            p_bim = self._patch_bim(bim_file, evidence)
            return [p_bim] if p_bim else []

        return []

    def _find_model_tmdl(self, model_dir: Path) -> Optional[Path]:
        """Locate definition/model.tmdl or model.tmdl."""
        for candidate in (
            model_dir / "definition" / "model.tmdl",
            model_dir / "model.tmdl",
        ):
            if candidate.exists() and candidate.is_file():
                return candidate
        for p in model_dir.glob("**/model.tmdl"):
            if p.exists() and p.is_file():
                return p
        return None

    def _find_bim_file(self, model_dir: Path) -> Optional[Path]:
        """Locate model.bim or database.json."""
        for p in model_dir.glob("**/model.bim"):
            if p.exists() and p.is_file():
                return p
        for p in model_dir.glob("**/database.json"):
            if p.exists() and p.is_file():
                return p
        return None

    def _patch_model_tmdl(self, model_tmdl: Path, evidence: PatchEvidence) -> Optional[Patch]:
        """Remove the auto tables' `ref table` lines and switch auto date/time off in model.tmdl."""
        content = model_tmdl.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        chunks: list[PatchChunk] = []

        for i, line in enumerate(lines):
            if re.match(r"^\s*ref\s+table\s+(LocalDateTable_|DateTableTemplate_)", line):
                chunks.append(PatchChunk.create(
                    start_line=i + 1,
                    end_line=i + 1,
                    original_text=line,
                    replacement_text="",
                ))
            elif _TIME_INTELLIGENCE_ON.match(line):
                # Left on, Power BI would generate the tables again the next time the model opens.
                chunks.append(PatchChunk.create(
                    start_line=i + 1,
                    end_line=i + 1,
                    original_text=line,
                    replacement_text=_TIME_INTELLIGENCE_ON.sub(r"\g<1>0\g<2>", line),
                ))

        if not any(c.replacement_text == "" for c in chunks):
            return None

        source_hash = compute_file_sha256(model_tmdl)
        patch_id = f"REM-MODEL_AUTO_DATETIME_BLOAT-model_tmdl-{source_hash[:8]}"

        return Patch(
            patch_id=patch_id,
            rule_id=self.rule_id,
            file_path=model_tmdl,
            source_hash=source_hash,
            safety=RemediationSafety.REVIEW_REQUIRED,
            state=PatchLifecycleState.PLANNED,
            evidence=evidence,
            chunks=chunks,
            rationale=(
                "Remove auto-generated LocalDateTable references from model.tmdl and turn Auto Date/Time "
                "off (__PBI_TimeIntelligenceEnabled = 0) so Power BI does not recreate them."
            ),
        )

    def _patch_relationships_tmdl(self, rel_file: Path, evidence: PatchEvidence) -> tuple[Optional[Patch], set[str]]:
        """Remove each relationship from a fact table into an auto date table; return their ids."""
        content = rel_file.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        chunks: list[PatchChunk] = []
        removed_ids: set[str] = set()

        for i, line in enumerate(lines):
            header = re.match(r"^relationship\s+(.+?)\s*$", line.rstrip("\r\n"))
            if not header:
                continue
            end = _block_end(lines, i)
            parsed = parse_tmdl_relationships_text("".join(lines[i:end]))
            if len(parsed) != 1:
                continue
            rel = parsed[0]
            if not _is_auto_relationship(rel.from_table, rel.to_table, rel.to_column):
                continue
            removed_ids.add(header.group(1).strip().strip("'"))
            chunks.append(PatchChunk.create(
                start_line=i + 1,
                end_line=end,
                original_text="".join(lines[i:end]),
                replacement_text="",
            ))

        if not chunks:
            return None, set()

        source_hash = compute_file_sha256(rel_file)
        return Patch(
            patch_id=f"REM-MODEL_AUTO_DATETIME_BLOAT-relationships-{source_hash[:8]}",
            rule_id=self.rule_id,
            file_path=rel_file,
            source_hash=source_hash,
            safety=RemediationSafety.REVIEW_REQUIRED,
            state=PatchLifecycleState.PLANNED,
            evidence=evidence,
            chunks=chunks,
            rationale=f"Remove {len(chunks)} relationship(s) that connect date columns to auto-generated date tables.",
        ), removed_ids

    def _patch_variations_tmdl(self, model_dir: Path, removed_ids: set[str], evidence: PatchEvidence) -> list[Patch]:
        """Remove the `variation` blocks on date columns that point at an auto date table."""
        patches: list[Patch] = []
        for tmdl in sorted(model_dir.glob("**/*.tmdl")):
            if tmdl.name.startswith(_AUTO_PREFIXES) or tmdl.name in ("model.tmdl", "relationships.tmdl"):
                continue
            lines = tmdl.read_text(encoding="utf-8").splitlines(keepends=True)
            chunks: list[PatchChunk] = []
            for i, line in enumerate(lines):
                if not re.match(r"^\s*variation\b", line):
                    continue
                end = _block_end(lines, i)
                block = "".join(lines[i:end])
                if any(rid in block for rid in removed_ids) or re.search(r"\b(LocalDateTable_|DateTableTemplate_)", block):
                    chunks.append(PatchChunk.create(
                        start_line=i + 1, end_line=end, original_text=block, replacement_text="",
                    ))
            if chunks:
                source_hash = compute_file_sha256(tmdl)
                patches.append(Patch(
                    patch_id=f"REM-MODEL_AUTO_DATETIME_BLOAT-variations-{tmdl.stem}-{source_hash[:8]}",
                    rule_id=self.rule_id,
                    file_path=tmdl,
                    source_hash=source_hash,
                    safety=RemediationSafety.REVIEW_REQUIRED,
                    state=PatchLifecycleState.PLANNED,
                    evidence=evidence,
                    chunks=chunks,
                    rationale=f"Remove the date-hierarchy variation(s) on {tmdl.stem} that point at auto-generated date tables.",
                ))
        return patches

    def _patch_bim(self, bim_file: Path, evidence: PatchEvidence) -> Optional[Patch]:
        """Generate Patch removing the auto date tables, their relationships and variations in BIM."""
        content = bim_file.read_text(encoding="utf-8")
        try:
            data = json.loads(content.lstrip(_BOM))
        except json.JSONDecodeError:
            return None

        # Check model.tables
        model_obj = data.get("model", data)
        tables = model_obj.get("tables", [])
        auto_names = {str(t.get("name", "")) for t in tables if str(t.get("name", "")).startswith(_AUTO_PREFIXES)}
        filtered_tables = [t for t in tables if str(t.get("name", "")) not in auto_names]

        if len(filtered_tables) == len(tables):
            return None

        removed_rel_names: set[str] = set()
        kept_rels = []
        for rel in model_obj.get("relationships", []):
            if _is_auto_relationship(str(rel.get("fromTable", "")), str(rel.get("toTable", "")), str(rel.get("toColumn", ""))):
                removed_rel_names.add(str(rel.get("name", "")))
            else:
                kept_rels.append(rel)
        if "relationships" in model_obj:
            model_obj["relationships"] = kept_rels

        for table in filtered_tables:
            for column in table.get("columns", []):
                variations = column.get("variations")
                if not isinstance(variations, list):
                    continue
                kept = [
                    v for v in variations
                    if str(v.get("relationship", "")) not in removed_rel_names
                    and not any(name in json.dumps(v.get("defaultHierarchy", "")) for name in auto_names)
                ]
                if kept:
                    column["variations"] = kept
                else:
                    column.pop("variations")

        for annotation in model_obj.get("annotations", []):
            if annotation.get("name") == "__PBI_TimeIntelligenceEnabled" and str(annotation.get("value")) == "1":
                annotation["value"] = "0"  # otherwise Power BI recreates the tables

        model_obj["tables"] = filtered_tables
        new_content = json.dumps(data, indent=2) + "\n"
        source_hash = compute_file_sha256(bim_file)

        chunk = PatchChunk.create(
            start_line=1,
            end_line=len(content.splitlines(keepends=True)),
            original_text=content,
            replacement_text=new_content,
        )

        patch_id = f"REM-MODEL_AUTO_DATETIME_BLOAT-bim-{source_hash[:8]}"
        return Patch(
            patch_id=patch_id,
            rule_id=self.rule_id,
            file_path=bim_file,
            source_hash=source_hash,
            safety=RemediationSafety.REVIEW_REQUIRED,
            state=PatchLifecycleState.PLANNED,
            evidence=evidence,
            chunks=[chunk],
            rationale=(
                "Remove auto-generated LocalDateTable tables, the relationships and variations that use them, "
                "and turn Auto Date/Time off, from model.bim."
            ),
        )


_BOM = chr(0xFEFF)  # patchers read files as plain UTF-8, which keeps a byte-order mark as text
_AUTO_PREFIXES = ("LocalDateTable_", "DateTableTemplate_")
_TIME_INTELLIGENCE_ON = re.compile(r"^(\s*annotation\s+__PBI_TimeIntelligenceEnabled\s*=\s*)1(\s*)$")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def _block_end(lines: list[str], start: int) -> int:
    """End (exclusive) of the TMDL block starting at `start`: the lines indented deeper than its
    first line, plus the blank separator lines that follow."""
    base = _indent(lines[start])
    end = start + 1
    while end < len(lines) and lines[end].strip() and _indent(lines[end]) > base:
        end += 1
    while end < len(lines) and not lines[end].strip():
        end += 1
    return end


def _is_auto_relationship(from_table: str, to_table: str, to_column: str) -> bool:
    """The relationship Power BI creates for auto date/time: fact table -> auto table's Date column."""
    return (
        to_table.startswith(_AUTO_PREFIXES)
        and not from_table.startswith(_AUTO_PREFIXES)
        and to_column.strip("'").lower() == "date"
    )
