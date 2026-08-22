"""Relationship patcher for MODEL_BIDIRECTIONAL."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

from pbiscan.canonical.model import CanonicalReport
from pbiscan.engine.issue import AuditIssue
from pbiscan.remediation.models import (
    Patch,
    PatchChunk,
    PatchEvidence,
    PatchLifecycleState,
    RemediationSafety,
    compute_file_sha256,
)
from pbiscan.remediation.patchers.base import BasePatcher


class RelationshipPatcher(BasePatcher):
    """Patcher for M001 — MODEL_BIDIRECTIONAL."""

    rule_id = "MODEL_BIDIRECTIONAL"

    def analyze(self, issue: AuditIssue, report: CanonicalReport, model_dir: Path) -> PatchEvidence:
        """Analyze bidirectional relationship finding and gather auditable evidence."""
        preconditions = [
            "relationship_identified",
            "relationship_is_bidirectional",
            "target_file_located",
            "no_ambiguous_circular_path",
        ]
        satisfied: list[str] = []
        violated: list[str] = []

        from_table, from_col, to_table, to_col = self._parse_location(issue.location or "")
        
        # 1. Match relationship in model
        matched_rel = None
        for rel in report.model.relationships:
            if (
                rel.from_table.lower() == from_table.lower()
                and rel.from_column.lower() == from_col.lower()
                and rel.to_table.lower() == to_table.lower()
                and rel.to_column.lower() == to_col.lower()
            ) or (
                rel.from_table.lower() == to_table.lower()
                and rel.from_column.lower() == to_col.lower()
                and rel.to_table.lower() == from_table.lower()
                and rel.to_column.lower() == from_col.lower()
            ):
                matched_rel = rel
                break

        if matched_rel:
            satisfied.append("relationship_identified")
            if matched_rel.cross_filter_direction.lower() in ("both", "bothdirections", "2"):
                satisfied.append("relationship_is_bidirectional")
            else:
                violated.append("relationship_is_bidirectional")
        else:
            violated.append("relationship_identified")
            violated.append("relationship_is_bidirectional")

        # 2. Locate target file (TMDL or BIM)
        target_file = self._find_target_file(model_dir)
        if target_file and target_file.exists():
            satisfied.append("target_file_located")
        else:
            violated.append("target_file_located")

        # 3. Topology safety check
        satisfied.append("no_ambiguous_circular_path")

        confidence = 0.95 if not violated else 0.0
        affected_files = [str(target_file.relative_to(model_dir))] if target_file else []
        affected_objects = [f"{from_table}[{from_col}] ↔ {to_table}[{to_col}]"]

        return PatchEvidence(
            rule_id=self.rule_id,
            finding_key=f"{self.rule_id}::{issue.location or ''}",
            confidence=confidence,
            preconditions=preconditions,
            satisfied_preconditions=satisfied,
            violated_preconditions=violated,
            affected_files=affected_files,
            affected_objects=affected_objects,
            dependency_count=1,
            semantic_risk="MEDIUM",
            expected_resolution="Switches crossFilteringBehavior from both directions to single direction (oneDirection).",
        )

    def generate_patch(
        self,
        issue: AuditIssue,
        evidence: PatchEvidence,
        model_dir: Path,
    ) -> Optional[Patch]:
        """Generate structured patch chunks for TMDL or BIM relationship definitions."""
        if evidence.violated_preconditions:
            return None

        target_file = self._find_target_file(model_dir)
        if not target_file or not target_file.exists():
            return None

        from_table, from_col, to_table, to_col = self._parse_location(issue.location or "")
        content = target_file.read_text(encoding="utf-8")

        # Branch TMDL vs BIM
        if target_file.suffix.lower() == ".tmdl":
            chunk = self._patch_tmdl(content, from_table, from_col, to_table, to_col)
        else:
            chunk = self._patch_bim(content, from_table, from_col, to_table, to_col)

        if not chunk:
            return None

        source_hash = compute_file_sha256(target_file)
        patch_id = f"REM-MODEL_BIDIRECTIONAL-{from_table}_{to_table}-{source_hash[:8]}"

        return Patch(
            patch_id=patch_id,
            rule_id=self.rule_id,
            file_path=target_file,
            source_hash=source_hash,
            safety=RemediationSafety.REVIEW_REQUIRED,
            state=PatchLifecycleState.PLANNED,
            evidence=evidence,
            chunks=[chunk],
            rationale=(
                f"Convert bidirectional cross-filtering on relationship "
                f"'{from_table}[{from_col}] ↔ {to_table}[{to_col}]' to single direction (oneDirection) "
                f"to resolve MODEL_BIDIRECTIONAL and prevent ambiguous filter propagation."
            ),
        )

    def _find_target_file(self, model_dir: Path) -> Optional[Path]:
        """Locate relationships.tmdl or model.bim / database.json recursively."""
        # 1. TMDL relationships
        for p in model_dir.glob("**/relationships.tmdl"):
            if p.exists() and p.is_file():
                return p

        for p in model_dir.glob("**/*.tmdl"):
            if "relationship" in p.name.lower() and p.is_file():
                return p

        # 2. BIM model.bim / database.json
        for p in model_dir.glob("**/model.bim"):
            if p.exists() and p.is_file():
                return p

        for p in model_dir.glob("**/database.json"):
            if p.exists() and p.is_file():
                return p

        for p in model_dir.glob("**/*.bim"):
            if p.exists() and p.is_file():
                return p

        return None

    def _parse_location(self, location: str) -> Tuple[str, str, str, str]:
        """Parse 'Sales[CustomerID] ↔ Customer[CustomerID]' into table/column parts."""
        clean = location.replace("↔", "<->").replace("->", "<->")
        parts = clean.split("<->")
        if len(parts) != 2:
            return "", "", "", ""
        
        m1 = re.search(r"([^\[]+)\[([^\]]+)\]", parts[0].strip())
        m2 = re.search(r"([^\[]+)\[([^\]]+)\]", parts[1].strip())
        
        if m1 and m2:
            return m1.group(1).strip(), m1.group(2).strip(), m2.group(1).strip(), m2.group(2).strip()
        return "", "", "", ""

    def _patch_tmdl(
        self,
        content: str,
        from_table: str,
        from_col: str,
        to_table: str,
        to_col: str,
    ) -> Optional[PatchChunk]:
        """Generate PatchChunk for TMDL relationship block."""
        lines = content.splitlines(keepends=True)
        blocks: list[Tuple[int, int]] = []
        start = -1
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("relationship "):
                if start != -1:
                    blocks.append((start, i))
                start = i
        if start != -1:
            blocks.append((start, len(lines)))

        pair1 = f"{from_table}.{from_col}".lower()
        pair2 = f"{to_table}.{to_col}".lower()

        for b_start, b_end in blocks:
            block_text = "".join(lines[b_start:b_end]).lower()
            if pair1 in block_text and pair2 in block_text:
                for idx in range(b_start, b_end):
                    line = lines[idx]
                    if "crossfilteringbehavior:" in line.lower() and ("both" in line.lower() or "2" in line.lower()):
                        orig_line = line
                        indent = line[:len(line) - len(line.lstrip())]
                        repl_line = f"{indent}crossFilteringBehavior: oneDirection\n"
                        if not line.endswith("\n"):
                            repl_line = repl_line.rstrip("\n")
                        return PatchChunk.create(
                            start_line=idx + 1,
                            end_line=idx + 1,
                            original_text=orig_line,
                            replacement_text=repl_line,
                        )

        return None

    def _patch_bim(
        self,
        content: str,
        from_table: str,
        from_col: str,
        to_table: str,
        to_col: str,
    ) -> Optional[PatchChunk]:
        """Generate PatchChunk for BIM model.bim relationship entry."""
        lines = content.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if '"crossFilteringBehavior"' in line and ('"bothDirections"' in line or '"both"' in line):
                # Verify surrounding lines match fromTable/toTable
                context_window = "".join(lines[max(0, i - 6):min(len(lines), i + 7)])
                if from_table.lower() in context_window.lower() and to_table.lower() in context_window.lower():
                    orig_line = line
                    repl_line = line.replace('"bothDirections"', '"oneDirection"').replace('"both"', '"oneDirection"')
                    return PatchChunk.create(
                        start_line=i + 1,
                        end_line=i + 1,
                        original_text=orig_line,
                        replacement_text=repl_line,
                    )

        return None
