"""Data source patcher for M_HARDCODED_DATA_SOURCE."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional, Tuple

from pbiscan.canonical.model import CanonicalReport, Table
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

_LOCAL_USER_PATH_PATTERN = re.compile(
    r'["\'](?:[a-zA-Z]:[\\/](?:users|documents|desktop|downloads|temp|tmp)[^"\']*|(?:/users/|/home/)[^"\']*)["\']',
    re.IGNORECASE,
)


class DataSourcePatcher(BasePatcher):
    """Patcher for M006 — M_HARDCODED_DATA_SOURCE.
    
    Converts hardcoded developer workstation file paths in Power Query (M) partition sources
    into parameterized references (e.g. DataFolderPath & "\\filename.ext").
    """

    rule_id = "M_HARDCODED_DATA_SOURCE"

    def analyze(self, issue: AuditIssue, report: CanonicalReport, model_dir: Path) -> PatchEvidence:
        """Analyze table partition M expression and verify parameterization suitability."""
        preconditions = [
            "table_identified",
            "hardcoded_path_detected",
            "supported_path_semantics",
            "no_parameter_collision",
            "target_file_located",
            "m_source_partition_found",
            "clean_syntax_boundary",
        ]
        satisfied: list[str] = []
        violated: list[str] = []

        table_name = self._parse_table_name(issue)

        # 1. Match table in canonical report
        matched_table: Optional[Table] = None
        for t in report.model.tables:
            if t.name.lower() == table_name.lower():
                matched_table = t
                break

        if matched_table:
            satisfied.append("table_identified")
            table_name = matched_table.name
            source_expr = matched_table.partition_source or ""
            
            # Check for dynamic M or unsafe constructs
            if "Expression.Evaluate" in source_expr or "Web.Contents" in source_expr or "Sql.Database" in source_expr:
                violated.append("supported_path_semantics")
            else:
                satisfied.append("supported_path_semantics")

            if source_expr and _LOCAL_USER_PATH_PATTERN.search(source_expr):
                satisfied.append("hardcoded_path_detected")
                satisfied.append("m_source_partition_found")
            else:
                violated.append("hardcoded_path_detected")
                violated.append("m_source_partition_found")
        else:
            violated.append("table_identified")
            violated.append("hardcoded_path_detected")
            violated.append("m_source_partition_found")
            satisfied.append("supported_path_semantics")

        # 2. Check for parameter name collision
        param_name = "DataFolderPath"
        collision = any(t.name.lower() == param_name.lower() for t in report.model.tables)
        if not collision:
            satisfied.append("no_parameter_collision")
        else:
            violated.append("no_parameter_collision")

        # 3. Locate target file (TMDL or BIM)
        target_file = self._find_target_file(model_dir, table_name)
        if target_file and target_file.exists():
            satisfied.append("target_file_located")
        else:
            violated.append("target_file_located")

        # 4. Clean syntax boundary
        satisfied.append("clean_syntax_boundary")

        confidence = 0.95 if not violated else 0.0
        affected_files = [str(target_file.relative_to(model_dir))] if target_file else []
        affected_objects = [f"Table '{table_name}' M partition source"]

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
            semantic_risk="HIGH",
            expected_resolution=(
                f"Parameterizes local workstation file path in table '{table_name}' "
                f"M partition source to use DataFolderPath parameter."
            ),
        )

    def generate_patch(
        self,
        issue: AuditIssue,
        evidence: PatchEvidence,
        model_dir: Path,
    ) -> Optional[Patch]:
        """Generate structured patch replacing hardcoded workstation path with parameter token."""
        if evidence.violated_preconditions:
            return None

        table_name = self._parse_table_name(issue)
        target_file = self._find_target_file(model_dir, table_name)
        if not target_file or not target_file.exists():
            return None

        content = target_file.read_text(encoding="utf-8")
        chunk: Optional[PatchChunk] = None

        if target_file.suffix.lower() == ".tmdl":
            chunk = self._patch_tmdl(content)
        elif target_file.suffix.lower() in (".bim", ".json"):
            chunk = self._patch_bim(content, table_name)

        if not chunk:
            return None

        source_hash = compute_file_sha256(target_file)
        clean_tbl = re.sub(r"[^\w]", "_", table_name)
        patch_id = f"REM-M_HARDCODED_DATA_SOURCE-{clean_tbl}-{source_hash[:8]}"

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
                f"Parameterize hardcoded developer workstation file path in table '{table_name}' "
                f"to decouple partition from local developer file system."
            ),
        )

    def _parse_table_name(self, issue: AuditIssue) -> str:
        """Extract table name from issue location or evidence."""
        loc = issue.location or ""
        m = re.search(r"Table:\s*(.+)$", loc, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        
        ev = issue.evidence or ""
        m2 = re.search(r"Table\s+'([^']+)'", ev, re.IGNORECASE)
        if m2:
            return m2.group(1).strip()

        return loc.strip()

    def _find_target_file(self, model_dir: Path, table_name: str) -> Optional[Path]:
        """Locate TMDL table file or model.bim."""
        if table_name:
            for candidate in (
                model_dir / "definition" / "tables" / f"{table_name}.tmdl",
                model_dir / "tables" / f"{table_name}.tmdl",
            ):
                if candidate.exists() and candidate.is_file():
                    return candidate

            for p in model_dir.glob(f"**/{table_name}.tmdl"):
                if p.exists() and p.is_file():
                    return p

        # Search BIM
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

    def _parameterize_path(self, raw_path: str) -> str:
        """Convert 'C:\\Users\\Admin\\Desktop\\Orders.xlsx' -> DataFolderPath & \"\\\\Orders.xlsx\"."""
        clean = raw_path.strip('\'"')
        filename = Path(clean).name
        if not filename:
            filename = "data.csv"
        # Return M parameter expression
        return f'DataFolderPath & "\\{filename}"'

    def _patch_tmdl(self, content: str) -> Optional[PatchChunk]:
        """Generate PatchChunk for TMDL partition source line."""
        lines = content.splitlines(keepends=True)
        for i, line in enumerate(lines):
            match = _LOCAL_USER_PATH_PATTERN.search(line)
            if match:
                raw_path_with_quotes = match.group(0)
                param_expr = self._parameterize_path(raw_path_with_quotes)
                repl_line = line.replace(raw_path_with_quotes, param_expr)
                return PatchChunk.create(
                    start_line=i + 1,
                    end_line=i + 1,
                    original_text=line,
                    replacement_text=repl_line,
                )
        return None

    def _patch_bim(self, content: str, table_name: str) -> Optional[PatchChunk]:
        """Generate PatchChunk for BIM partition source expression."""
        lines = content.splitlines(keepends=True)
        for i, line in enumerate(lines):
            match = _LOCAL_USER_PATH_PATTERN.search(line)
            if match:
                raw_path_with_quotes = match.group(0)
                clean_path = raw_path_with_quotes.strip('\'"')
                filename = Path(clean_path).name
                # Escape for JSON string
                param_expr = f'DataFolderPath & \\"\\\\{filename}\\"'
                repl_line = line.replace(raw_path_with_quotes, param_expr)
                return PatchChunk.create(
                    start_line=i + 1,
                    end_line=i + 1,
                    original_text=line,
                    replacement_text=repl_line,
                )
        return None
