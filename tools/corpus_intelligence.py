"""Track 3A: Extended Corpus Intelligence & Feature Coverage Scanner.

Analyzes the combined 25 real-world PBIP models:
- Governance Corpus (11 models - locked baseline)
- Extended Validation Corpus (14 models)

Generates:
1. Model-by-model structural & quality inventory
2. Rule x Model execution matrix
3. Parser & canonical construct coverage map
4. Candidate signal discovery log
"""

import json
from pathlib import Path
from pbiscan.service import ScanService

GOVERNANCE_CORPUS = [
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

# Discover all 14 extended models dynamically
EXTENDED_ROOTS = [
    Path(r"C:\Users\TARUN\Downloads\ExcelPBIP_Template_SM\ExcelPBIP_Template_SM"),
    Path(r"C:\Users\TARUN\Downloads\output\output"),
]

ALL_RULES = [
    "MODEL_BIDIRECTIONAL",
    "MODEL_MANY_TO_MANY",
    "MODEL_INACTIVE_RELATIONSHIP",
    "MODEL_NO_DATE_TABLE",
    "MODEL_HIGH_CARDINALITY",
    "MODEL_FACT_TO_FACT",
    "M_HARDCODED_DATA_SOURCE",
    "MODEL_AUTO_DATETIME_BLOAT",
    "DAX_SUSPICIOUS_PATTERN",
    "DAX_EXCESSIVE_CALC_COLUMNS",
    "DAX_DUPLICATE_MEASURE",
    "DAX_UNUSED_MEASURE",
    "REPORT_VISUAL_BLOAT",
    "REPORT_SLICER_BLOAT",
]

def run_corpus_intelligence():
    extended_paths = []
    for root in EXTENDED_ROOTS:
        if root.exists():
            extended_paths.extend(sorted(list(root.rglob("*.pbip"))))

    sections = [("Gov-11", GOVERNANCE_CORPUS), ("Ext-14", extended_paths)]
    
    total_tables = 0
    total_cols = 0
    total_meas = 0
    total_rels = 0
    total_pages = 0
    total_visuals = 0
    total_semrefs = 0
    
    format_counts = {"TMDL": 0, "BIM": 0}
    constructs = {
        "calc_groups": 0,
        "field_parameters": 0,
        "rls_roles": 0,
        "m_partitions": 0,
        "bidirectional_rels": 0,
        "many_to_many_rels": 0,
    }

    rule_counts = {r: 0 for r in ALL_RULES}
    matrix = []

    for tag, paths in sections:
        for p in paths:
            if not p.exists():
                print(f"MISSING: {p}")
                continue
            
            res = ScanService.execute_scan(p)
            rep = res.report
            issues = res.issues

            # Format detection
            sm_dir = next((d for d in p.parent.iterdir() if d.is_dir() and d.name.endswith(".SemanticModel")), p.parent)
            is_bim = (sm_dir / "model.bim").exists() or (sm_dir / "database.json").exists()
            fmt = "BIM" if is_bim else "TMDL"
            format_counts[fmt] += 1

            # Metric totals
            t_cnt = len(rep.model.tables)
            c_cnt = sum(len(t.columns) for t in rep.model.tables)
            m_cnt = len(rep.dax.measures)
            r_cnt = len(rep.model.relationships)
            pg_cnt = len(rep.report.pages)
            v_cnt = sum(len(pg.visuals) for pg in rep.report.pages)
            s_cnt = len(rep.semantic_references)

            total_tables += t_cnt
            total_cols += c_cnt
            total_meas += m_cnt
            total_rels += r_cnt
            total_pages += pg_cnt
            total_visuals += v_cnt
            total_semrefs += s_cnt

            # Constructs detection
            if any(r.source_type == "calc_group" for r in rep.semantic_references.references):
                constructs["calc_groups"] += 1
            if any(r.source_type == "field_parameter" for r in rep.semantic_references.references):
                constructs["field_parameters"] += 1
            if any(r.source_type == "rls" for r in rep.semantic_references.references):
                constructs["rls_roles"] += 1
            if any(bool(t.partition_source) for t in rep.model.tables):
                constructs["m_partitions"] += 1

            if len(rep.model.relationships) > 0:
                if any(rel.cross_filter_direction == "both" for rel in rep.model.relationships):
                    constructs["bidirectional_rels"] += 1
                if any(rel.cardinality in ["manyToMany", "ManyToMany", "Many-to-Many"] for rel in rep.model.relationships):
                    constructs["many_to_many_rels"] += 1

            # Rule breakdown for matrix
            breakdown = {r: 0 for r in ALL_RULES}
            for iss in issues:
                rid = iss.rule_id
                if rid in breakdown:
                    breakdown[rid] += 1
                    rule_counts[rid] += 1

            row = {
                "corpus": tag,
                "model_name": res.report_name,
                "format": fmt,
                "tables": t_cnt,
                "measures": m_cnt,
                "rels": r_cnt,
                "pages": pg_cnt,
                "visuals": v_cnt,
                "score": res.overall_score,
                "findings": len(issues),
                "breakdown": breakdown,
            }
            matrix.append(row)

    output_data = {
        "total_models": len(matrix),
        "total_tables": total_tables,
        "total_columns": total_cols,
        "total_measures": total_meas,
        "total_relationships": total_rels,
        "total_pages": total_pages,
        "total_visuals": total_visuals,
        "total_semantic_references": total_semrefs,
        "format_counts": format_counts,
        "constructs": constructs,
        "rule_frequencies": rule_counts,
        "matrix": matrix,
    }
    
    with open("corpus_intelligence.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"Scanned {len(matrix)} / 25 models successfully. Saved to corpus_intelligence.json")

if __name__ == "__main__":
    run_corpus_intelligence()
