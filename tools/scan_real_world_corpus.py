"""Scan all 11 external real-world PBIP models with PBIP Sentinel v1.4.0."""

import json
from pathlib import Path
from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.rules.dax import DAX_RULES
from pbiscan.rules.model import MODEL_RULES
from pbiscan.rules.report import REPORT_RULES

ALL_RULES = MODEL_RULES + DAX_RULES + REPORT_RULES

EXTERNAL_MODELS = [
    Path(r"d:\Projects\Powerbi\Power_BI_Report_Quality_&_Performance_Scanner\pbip_project\world is going bananas.pbip"),
    Path(r"C:\Users\TARUN\Downloads\Financial_Report_PBIP\Financial_Report.pbip"),
    Path(r"C:\Users\TARUN\Downloads\HR_Analysis_PBIP\HR_Analysis_Dashboard.pbip"),
    Path(r"C:\Users\TARUN\Downloads\sales analysis - mirgrated\sales_analysis.pbip"),
    Path(r"C:\Users\TARUN\Downloads\TermAidReport_PBIV\TermAidReport_PBIV.pbip"),
    Path(r"C:\Users\TARUN\Downloads\Test\1761793292566_02 email communication report challenge.pbip"),
    Path(r"C:\Users\TARUN\Downloads\test2\1767842152777_1765180280123_03 Xmas Sales.pbip"),
    Path(r"C:\Users\TARUN\Downloads\test3\1756112919049_AC_Sales_Dashboard_adediran_a.pbip"),
    Path(r"C:\Users\TARUN\Downloads\test5\1756112919049_AC_Sales_Dashboard_ajay_s.pbip"),
    Path(r"C:\Users\TARUN\Downloads\test6\1760515551828_zepto.pbip"),
    Path(r"C:\Users\TARUN\Downloads\test7\Spotify_Dashboard.pbip"),
]

def scan_models():
    records = []
    for model_path in EXTERNAL_MODELS:
        if not model_path.exists():
            records.append({"path": str(model_path), "status": "FILE_NOT_FOUND"})
            continue

        try:
            reader = PBIPReader()
            raw = reader.read(model_path)
            builder = CanonicalBuilder()
            report = builder.build(raw)

            findings = []
            for rule in ALL_RULES:
                findings.extend(rule(report))

            by_category = {}
            for f in findings:
                by_category[f.rule_id] = by_category.get(f.rule_id, 0) + 1

            sem_refs = report.semantic_references
            by_source = {}
            for r in sem_refs.references:
                by_source[r.source_type] = by_source.get(r.source_type, 0) + 1

            records.append({
                "model_name": model_path.stem,
                "path": str(model_path),
                "tables": len(report.model.tables),
                "columns": sum(len(t.columns) for t in report.model.tables),
                "relationships": len(report.model.relationships),
                "measures": len(report.dax.measures),
                "pages": len(report.report.pages),
                "visuals": sum(len(p.visuals) for p in report.report.pages),
                "total_findings": len(findings),
                "findings_breakdown": by_category,
                "total_semantic_refs": len(sem_refs),
                "active_roots": len(sem_refs.active_root_measure_names()),
                "refs_by_source": by_source,
                "status": "PASS",
            })
        except Exception as exc:
            records.append({
                "model_name": model_path.stem,
                "path": str(model_path),
                "status": f"FAIL: {type(exc).__name__}: {str(exc)}",
            })

    print(json.dumps(records, indent=2))

if __name__ == "__main__":
    scan_models()
