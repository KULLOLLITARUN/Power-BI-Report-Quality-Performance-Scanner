"""Finding Attribution & Classification Audit for top 3 real-world finding models."""

import json
from pathlib import Path
from pbiscan.extraction.pbip_reader import PBIPReader
from pbiscan.canonical.builder import CanonicalBuilder
from pbiscan.rules.dax import DAX_RULES
from pbiscan.rules.model import MODEL_RULES
from pbiscan.rules.report import REPORT_RULES

ALL_RULES = MODEL_RULES + DAX_RULES + REPORT_RULES

TARGET_MODELS = [
    Path(r"C:\Users\TARUN\Downloads\Test\1761793292566_02 email communication report challenge.pbip"),
    Path(r"C:\Users\TARUN\Downloads\test3\1756112919049_AC_Sales_Dashboard_adediran_a.pbip"),
    Path(r"C:\Users\TARUN\Downloads\test5\1756112919049_AC_Sales_Dashboard_ajay_s.pbip"),
]

def audit_top_models():
    records = []
    for model_path in TARGET_MODELS:
        reader = PBIPReader()
        raw = reader.read(model_path)
        builder = CanonicalBuilder()
        report = builder.build(raw)

        findings = []
        for rule in ALL_RULES:
            findings.extend(rule(report))

        measure_map = {m.name: m for m in report.dax.measures}
        sem_refs = report.semantic_references

        finding_details = []
        for f in findings:
            meas_name = f.location.replace("Measure: ", "").strip()
            meas_obj = measure_map.get(meas_name)
            dax_expr = meas_obj.expression if meas_obj else "N/A"

            # Check if referenced in semantic references
            target_refs = sem_refs.find_by_target(meas_name)

            finding_details.append({
                "rule_id": f.rule_id,
                "category": f.category,
                "severity": f.severity,
                "confidence": f.confidence,
                "location": f.location,
                "evidence": f.evidence,
                "dax_expression": dax_expr[:120] if dax_expr else "N/A",
                "sem_ref_count": len(target_refs),
                "sem_ref_sources": [r.source_type for r in target_refs],
            })

        records.append({
            "model_name": model_path.stem,
            "total_measures": len(report.dax.measures),
            "active_roots": len(sem_refs.active_root_measure_names()),
            "total_findings": len(findings),
            "findings": finding_details,
        })

    print(json.dumps(records, indent=2))

if __name__ == "__main__":
    audit_top_models()
