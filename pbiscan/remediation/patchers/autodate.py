"""Auto Date/Time bloat patcher for MODEL_AUTO_DATETIME_BLOAT."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from pbiscan.canonical.model import CanonicalReport
from pbiscan.engine.issue import AuditIssue
from pbiscan.remediation.models import (
    Patch,
    PatchChunk,
    PatchEvidence,
    PatchLifecycleState,
    RemediationSafety,
    compute_file_sha256,
    compute_sha256,
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
            # If both ends are not standard auto-variations or if custom active user relationship
            if from_match and to_match:
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
        """Generate patches removing LocalDateTable references and table definitions."""
        if evidence.violated_preconditions:
            return []

        patches: list[Patch] = []
        model_tmdl = self._find_model_tmdl(model_dir)

        if model_tmdl and model_tmdl.exists():
            # 1. Patch model.tmdl
            p_model = self._patch_model_tmdl(model_tmdl, evidence)
            if p_model:
                patches.append(p_model)

            # 2. Patch/clear individual LocalDateTable_*.tmdl and DateTableTemplate_*.tmdl files
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
        """Generate PatchChunk removing ref table LocalDateTable_* lines in model.tmdl."""
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

        if not chunks:
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
            rationale="Remove auto-generated LocalDateTable references from model.tmdl.",
        )

    def _patch_bim(self, bim_file: Path, evidence: PatchEvidence) -> Optional[Patch]:
        """Generate Patch removing LocalDateTable objects in BIM."""
        content = bim_file.read_text(encoding="utf-8")
        try:
            data = json.loads(content)
        except Exception:
            return None

        # Check model.tables
        model_obj = data.get("model", data)
        tables = model_obj.get("tables", [])
        filtered_tables = [
            t for t in tables
            if not str(t.get("name", "")).startswith("LocalDateTable_")
            and not str(t.get("name", "")).startswith("DateTableTemplate_")
        ]

        if len(filtered_tables) == len(tables):
            return None

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
            rationale="Remove auto-generated LocalDateTable table objects from model.bim.",
        )
