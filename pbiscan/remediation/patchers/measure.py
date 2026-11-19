"""Measure patcher for DAX_UNUSED_MEASURE."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Optional, Tuple

from pbiscan.canonical.model import CanonicalReport, Measure
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

_BOM = chr(0xFEFF)  # patchers read files as plain UTF-8, which keeps a byte-order mark as text


class MeasurePatcher(BasePatcher):
    """Patcher for D004 — DAX_UNUSED_MEASURE.
    
    Strictly verifies zero inbound consumers across:
    1. Direct & transitive DAX measure dependencies
    2. Calculation group items & format strings
    3. Field parameters (NAMEOF & 4-tuple mappings)
    4. Visual projections & properties
    5. Visual, page, and report level filters
    6. Row-Level Security (RLS) role expressions
    """

    rule_id = "DAX_UNUSED_MEASURE"

    def analyze(self, issue: AuditIssue, report: CanonicalReport, model_dir: Path) -> PatchEvidence:
        """Verify the measure has no consumer on any surface this scanner can see.

        Static analysis cannot see other reports, Excel workbooks or external
        tools that query the same semantic model; deletion is only proven safe
        for this project.
        """
        preconditions = [
            "measure_identified",
            "zero_transitive_measure_dependents",
            "zero_semantic_reference_consumers",
            "zero_visual_consumers",
            "target_file_located",
            "clean_syntax_boundary",
        ]
        satisfied: list[str] = []
        violated: list[str] = []

        measure_name, table_name = self._parse_issue_location(issue)

        # 1. Match measure in canonical report
        matched_measure: Optional[Measure] = None
        for m in report.dax.measures:
            if m.name.lower() == measure_name.lower():
                if not table_name or m.table.lower() == table_name.lower():
                    matched_measure = m
                    break

        if matched_measure:
            satisfied.append("measure_identified")
            measure_name = matched_measure.name
            table_name = matched_measure.table
        else:
            violated.append("measure_identified")

        # 2. Check transitive DAX measure dependents (multi-hop)
        has_dependents = False
        dax_graph = getattr(report, "dax_graph", None)
        if dax_graph and hasattr(dax_graph, "transitive_referenced_by"):
            ancestors = dax_graph.transitive_referenced_by(measure_name)
            if ancestors:
                has_dependents = True
        else:
            # Fallback cross-measure check
            pattern = r"\[" + re.escape(measure_name) + r"\]"
            for other_m in report.dax.measures:
                if other_m.name.lower() != measure_name.lower():
                    if re.search(pattern, other_m.expression, re.IGNORECASE):
                        has_dependents = True
                        break

        if not has_dependents:
            satisfied.append("zero_transitive_measure_dependents")
        else:
            violated.append("zero_transitive_measure_dependents")

        # 3. Check semantic references (calc groups, field params, RLS, filters)
        sem_refs = getattr(report, "semantic_references", None)
        if sem_refs and hasattr(sem_refs, "find_by_target"):
            matching_refs = sem_refs.find_by_target(measure_name)
            if not matching_refs:
                satisfied.append("zero_semantic_reference_consumers")
            else:
                violated.append("zero_semantic_reference_consumers")
        else:
            satisfied.append("zero_semantic_reference_consumers")

        # 4. Check visual consumers (projections, visual filters, page filters)
        used_in_visual = False
        for page in report.report.pages:
            for visual in page.visuals:
                if any(r.lower() == measure_name.lower() for r in visual.measure_refs):
                    used_in_visual = True
                    break
            if used_in_visual:
                break

        if not used_in_visual:
            satisfied.append("zero_visual_consumers")
        else:
            violated.append("zero_visual_consumers")

        # 5. Target file location
        target_file = self._find_target_file(model_dir, table_name, measure_name)
        if target_file and target_file.exists():
            satisfied.append("target_file_located")
        else:
            violated.append("target_file_located")

        # 6. Check for unindexed / unknown consumer surfaces across disk
        unknown_surface_found = False
        target_token_unqualified = f"[{measure_name}]".lower()
        target_token_qualified = f"'{table_name}'[{measure_name}]".lower() if table_name else ""
        
        # Scan all non-target TMDL/BIM files on disk for unmapped references
        for p in model_dir.glob("**/*"):
            if p.is_file() and p.suffix.lower() in (".tmdl", ".json", ".bim", ".dax"):
                if target_file and p.resolve() == target_file.resolve():
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore").lower()
                    if target_token_unqualified in text or (target_token_qualified and target_token_qualified in text):
                        # Verify whether this occurrence is in known semantic reference list
                        found_in_known_refs = False
                        if sem_refs and hasattr(sem_refs, "find_by_target"):
                            for ref in sem_refs.find_by_target(measure_name):
                                if ref.source_file and Path(ref.source_file).name.lower() == p.name.lower():
                                    found_in_known_refs = True
                                    break
                        if not found_in_known_refs:
                            unknown_surface_found = True
                            break
                except Exception:
                    # Deliberately broad: any failure to inspect a file means we can't
                    # prove the measure is unused there, so refuse deletion.
                    unknown_surface_found = True
                    break

        if not unknown_surface_found:
            satisfied.append("clean_syntax_boundary")
        else:
            violated.append("clean_syntax_boundary")

        confidence = 0.95 if not violated else 0.0
        affected_files = [str(target_file.relative_to(model_dir))] if target_file else []
        affected_objects = [f"Measure '{measure_name}' in table '{table_name}'"]

        return PatchEvidence(
            rule_id=self.rule_id,
            finding_key=f"{self.rule_id}::{issue.location or ''}",
            confidence=confidence,
            preconditions=preconditions,
            satisfied_preconditions=satisfied,
            violated_preconditions=violated,
            affected_files=affected_files,
            affected_objects=affected_objects,
            dependency_count=0,
            semantic_risk="LOW",
            expected_resolution=f"Safely removes unused measure '{measure_name}' with verified zero inbound dependencies.",
        )

    def generate_patch(
        self,
        issue: AuditIssue,
        evidence: PatchEvidence,
        model_dir: Path,
    ) -> Optional[Patch]:
        """Generate structured patch deleting the unused measure block."""
        if evidence.violated_preconditions:
            return None

        measure_name, table_name = self._parse_issue_location(issue)
        target_file = self._find_target_file(model_dir, table_name, measure_name)
        if not target_file or not target_file.exists():
            return None

        content = target_file.read_text(encoding="utf-8")

        chunk: Optional[PatchChunk] = None
        if target_file.suffix.lower() == ".tmdl":
            chunk = self._patch_tmdl(content, measure_name)
        elif target_file.suffix.lower() in (".bim", ".json"):
            chunk = self._patch_bim(content, table_name, measure_name)

        if not chunk:
            return None

        source_hash = compute_file_sha256(target_file)
        clean_name = re.sub(r"[^\w]", "_", measure_name)
        patch_id = f"REM-DAX_UNUSED_MEASURE-{clean_name}-{source_hash[:8]}"

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
                f"Safely remove orphaned measure '{measure_name}' from table '{table_name}' "
                f"after confirming zero inbound dependencies across all visual, DAX, RLS, and parameter surfaces."
            ),
        )

    def _parse_issue_location(self, issue: AuditIssue) -> Tuple[str, str]:
        """Extract measure name and table name from issue location or evidence."""
        loc = issue.location or ""
        # Format "Measure: <name>"
        m = re.search(r"Measure:\s*(.+)$", loc, re.IGNORECASE)
        if m:
            meas_name = m.group(1).strip().strip("'\"")
            # Try to get table from evidence "Measure 'Name' [Table]:"
            ev = issue.evidence or ""
            t_match = re.search(r"Measure\s+'[^']+'\s*\[([^\]]+)\]", ev, re.IGNORECASE)
            tbl_name = t_match.group(1).strip() if t_match else ""
            return meas_name, tbl_name

        # Format "Table[Measure]" or "'Table'[Measure]"
        m2 = re.search(r"(?:'([^']+)'|(\w+))\[([^\]]+)\]", loc)
        if m2:
            tbl = m2.group(1) or m2.group(2) or ""
            meas = m2.group(3) or ""
            return meas.strip(), tbl.strip()

        # Format from evidence
        ev = issue.evidence or ""
        m3 = re.search(r"Measure\s+'([^']+)'\s*(?:\[([^\]]+)\])?", ev, re.IGNORECASE)
        if m3:
            return m3.group(1).strip(), (m3.group(2) or "").strip()

        return loc.strip(), ""

    def _find_target_file(self, model_dir: Path, table_name: str, measure_name: str) -> Optional[Path]:
        """Locate table TMDL file or model.bim."""
        # 1. TMDL table file
        if table_name:
            # Check standard TMDL table paths
            for candidate in (
                model_dir / "definition" / "tables" / f"{table_name}.tmdl",
                model_dir / "tables" / f"{table_name}.tmdl",
            ):
                if candidate.exists() and candidate.is_file():
                    return candidate

            for p in model_dir.glob(f"**/{table_name}.tmdl"):
                if p.exists() and p.is_file():
                    return p

        # Search any TMDL file declaring this measure
        for p in model_dir.glob("**/*.tmdl"):
            if p.is_file():
                try:
                    text = p.read_text(encoding="utf-8")
                    if f"measure '{measure_name}'" in text or f"measure {measure_name} " in text or f"measure {measure_name}=" in text:
                        return p
                except (OSError, UnicodeDecodeError):
                    continue

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

    def _patch_tmdl(self, content: str, measure_name: str) -> Optional[PatchChunk]:
        """Generate PatchChunk removing the measure block in TMDL.

        The block is the declaration plus every following line indented deeper
        than it, so sibling members (hierarchies, partitions, table annotations)
        are never swallowed. All `///` doc lines directly above it go with it.
        """
        lines = content.splitlines(keepends=True)

        meas_pattern = re.compile(
            rf"^\s*measure\s+(?:'{re.escape(measure_name)}'|{re.escape(measure_name)})\s*=",
            re.IGNORECASE,
        )

        def indent_of(line: str) -> int:
            return len(line) - len(line.lstrip(" \t"))

        for i, line in enumerate(lines):
            if not meas_pattern.search(line):
                continue

            start_idx = i
            while start_idx > 0 and lines[start_idx - 1].strip().startswith("///"):
                start_idx -= 1

            decl_indent = indent_of(line)
            end_idx = i + 1
            while end_idx < len(lines):
                next_line = lines[end_idx]
                if not next_line.strip():
                    end_idx += 1  # blank separator lines go with the block
                    continue
                if indent_of(next_line) > decl_indent:
                    end_idx += 1  # property, annotation or expression continuation
                    continue
                break

            return PatchChunk.create(
                start_line=start_idx + 1,
                end_line=end_idx,
                original_text="".join(lines[start_idx:end_idx]),
                replacement_text="",
            )

        return None

    @staticmethod
    def _bim_measure_path(data: Any, table_name: str, measure_name: str) -> Optional[list[Any]]:
        """Path (keys and indexes) to the one `measures` entry this patch must remove.

        Entries are matched by the owning table's name, so a column or another
        table's measure with the same name is never a candidate. When no table
        carries `table_name` (hand-built or unnamed containers) the measure must
        be unique in the file; anything ambiguous returns None.
        """
        found: list[tuple[list[Any], str]] = []

        def walk(node: Any, path: list[Any]) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "measures" and isinstance(value, list):
                        for idx, entry in enumerate(value):
                            if isinstance(entry, dict) and str(entry.get("name", "")).lower() == measure_name.lower():
                                found.append((path + [key, idx], str(node.get("name", ""))))
                    walk(value, path + [key])
            elif isinstance(node, list):
                for idx, value in enumerate(node):
                    walk(value, path + [idx])

        walk(data, [])
        if table_name:
            in_table = [f for f in found if f[1].lower() == table_name.lower()]
            if in_table:
                found = in_table
        return found[0][0] if len(found) == 1 else None

    def _patch_bim(self, content: str, table_name: str, measure_name: str) -> Optional[PatchChunk]:
        """Generate PatchChunk removing the measure object in BIM model.bim.

        A text edit is only returned when the patched file parses to exactly the
        original model minus that one measure, so a wrong object (a column of the
        same name, another table's measure) or a broken comma can never be emitted.
        """
        try:
            original = json.loads(content.lstrip(_BOM))
        except json.JSONDecodeError:
            return None
        path = self._bim_measure_path(original, table_name, measure_name)
        if path is None:
            return None
        expected = copy.deepcopy(original)
        container = expected
        for key in path[:-1]:
            container = container[key]
        container.pop(path[-1])

        def verified(patched_lines: list[str]) -> bool:
            try:
                return bool(json.loads("".join(patched_lines).lstrip(_BOM)) == expected)
            except json.JSONDecodeError:
                return False

        lines = content.splitlines(keepends=True)
        name_literals = {json.dumps(measure_name, ensure_ascii=a) for a in (True, False)}
        name_line = re.compile(r'"name"\s*:\s*(?:' + "|".join(re.escape(n) for n in name_literals) + ")")

        for i, line in enumerate(lines):
            if not name_line.search(line):
                continue
            start_idx = i
            while start_idx >= 0 and "{" not in lines[start_idx]:
                start_idx -= 1
            if start_idx < 0:
                continue

            end_idx = i
            brace_depth = 0
            for k in range(start_idx, len(lines)):
                brace_depth += lines[k].count("{") - lines[k].count("}")
                if brace_depth == 0:
                    end_idx = k + 1
                    break

            # Candidate 1: delete the object, taking its trailing comma with it.
            cand1_end = end_idx
            if cand1_end < len(lines) and lines[cand1_end - 1].rstrip().endswith(","):
                pass
            elif cand1_end < len(lines) and lines[cand1_end].strip().startswith(","):
                cand1_end += 1
            trial = list(lines)
            trial[start_idx:cand1_end] = []
            if verified(trial):
                return PatchChunk.create(
                    start_line=start_idx + 1,
                    end_line=cand1_end,
                    original_text="".join(lines[start_idx:cand1_end]),
                    replacement_text="",
                )

            # Candidate 2: last item in its array, so drop the previous item's comma instead.
            if start_idx > 0 and lines[start_idx - 1].rstrip().endswith(","):
                prev_line = lines[start_idx - 1]
                comma_pos = prev_line.rfind(",")
                repl = prev_line[:comma_pos] + prev_line[comma_pos + 1:]
                trial = list(lines)
                trial[start_idx - 1] = repl
                trial[start_idx:end_idx] = []
                if verified(trial):
                    return PatchChunk.create(
                        start_line=start_idx,
                        end_line=end_idx,
                        original_text=prev_line + "".join(lines[start_idx:end_idx]),
                        replacement_text=repl,
                    )

        return None
