# PBIP Sentinel — v1.2 Post-Release Observation Ledger

**Purpose**: Systematic empirical observation logging for real-world PBIP projects scanned with `pbiscan v1.2.0`.  
**Governing Rule**: Do not write new rules or alter existing detection logic without documented real-world observations recorded in this ledger.

---

## Project Audit Log Entry Template

Copy and fill out the section below for every new PBIP project scanned during the post-release observation period:

```markdown
### Project Audit Entry: [<Project Name / Identifier>]

- **Date**: YYYY-MM-DD
- **Model Classification**: [Small Flat / Standard Star Schema / Enterprise Multi-Fact / Calculation-Heavy]
- **Size / Footprint**: [e.g. 12 MB, 14 Tables, 8 Relationships, 45 Measures, 8 Pages]
- **External Consumption Known?**: [Yes / No / Suspected (e.g. XMLA, Excel PivotTables, Thin Reports)]
- **Reviewer**: [<Name / Reviewer ID>]

#### Metrics & Performance
- **Scan Latency**: `XX.XX ms`
- **Peak Memory**: `XXX.XX KB`
- **Overall Health Score**: `XX.X`
- **Category Breakdown**: Model: `XX` | DAX: `XX` | Report: `XX`

#### Finding Breakdown by Rule
| Rule ID | Emitted Findings | TP | FP | AMB | FN Suspected | Reviewer Notes / Context |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `M001` (`MODEL_BIDIRECTIONAL`) | 0 | 0 | 0 | 0 | 0 | |
| `M002` (`MODEL_MANY_TO_MANY`) | 0 | 0 | 0 | 0 | 0 | |
| `M003` (`MODEL_NO_DATE_TABLE`) | 0 | 0 | 0 | 0 | 0 | |
| `M004` (`MODEL_HIGH_CARDINALITY`) | 0 | 0 | 0 | 0 | 0 | |
| `M005` (`MODEL_FACT_TO_FACT`) | 0 | 0 | 0 | 0 | 0 | |
| `D001` (`DAX_SUSPICIOUS_PATTERN`) | 0 | 0 | 0 | 0 | 0 | |
| `D002` (`DAX_EXCESSIVE_CALC_COLUMNS`) | 0 | 0 | 0 | 0 | 0 | |
| `D003` (`DAX_DUPLICATE_MEASURE`) | 0 | 0 | 0 | 0 | 0 | |
| `D004` (`DAX_UNUSED_MEASURE`) | 0 | 0 | 0 | 0 | 0 | |
| `R001` (`REPORT_VISUAL_BLOAT`) | 0 | 0 | 0 | 0 | 0 | |
| `R002` (`REPORT_SLICER_BLOAT`) | 0 | 0 | 0 | 0 | 0 | |

#### Candidate Infrastructure Observations
- **Isolated Tables Observed**: [e.g. Disconnected parameter table, What-If table, or unlinked orphan]
- **Multi-Path Topologies Observed**: [e.g. Diamond join paths, inactive userelationship paths]

#### False Negatives & Unflagged Risks
- *List any known modeling defects or performance bottlenecks present in this PBIP that pbiscan failed to flag:*
  1. None / [Describe unflagged pattern and expected detection]
```

---

## Log Entries

*(Entries will be appended below as external models are scanned during the v1.2 observation window.)*
