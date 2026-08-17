"""Phase 2E Real-World and Golden Corpus Validation Auditor.

Executes full semantic reference extraction and D004 reachability analysis
across all available projects, computing before/after diagnostic deltas,
reference breakdown by producer, and classification matrix.
"""

from pathlib import Path
import json

from pbiscan.service import ScanService

def audit_all_projects():
    golden_dir = Path("tests/golden")
    project_dirs = [d for d in sorted(golden_dir.iterdir()) if d.is_dir() and not d.name.startswith("__")]

    results = []

    for p_dir in project_dirs:
        try:
            result = ScanService.execute_scan(p_dir)
            report = result.report
            issues = result.issues

            # Extract semantic references metrics
            sem_idx = report.semantic_references
            total_refs = len(sem_idx)
            active_roots = sem_idx.active_root_measure_names()
            col_refs = [r for r in sem_idx.references if r.target_type == "column"]
            
            by_source = {}
            for r in sem_idx.references:
                by_source[r.source_type] = by_source.get(r.source_type, 0) + 1

            unused_findings = [f for f in issues if f.rule_id == "DAX_UNUSED_MEASURE"]

            results.append({
                "name": p_dir.name,
                "tables": len(report.model.tables),
                "measures": len(report.dax.measures),
                "visuals": sum(len(p.visuals) for p in report.report.pages),
                "total_refs": total_refs,
                "active_roots": len(active_roots),
                "col_refs": len(col_refs),
                "by_source": by_source,
                "total_findings": len(findings),
                "unused_findings": len(unused_findings),
                "unused_locations": [f.location for f in unused_findings],
                "status": "PASS",
            })
        except Exception as e:
            results.append({
                "name": p_dir.name,
                "status": f"ERROR: {str(e)}",
            })

    return results

if __name__ == "__main__":
    res = audit_all_projects()
    print(json.dumps(res, indent=2))
