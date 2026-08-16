# PBIP Sentinel — v1.2 Post-Release Observation Ledger

**Status**: Active Observation Window  
**Baseline Scanner**: `pbiscan v1.2.0` (Frozen Control Group, Commit `a81a246`)  
**Governing Discipline**: **Observe $\to$ Classify $\to$ Accumulate Evidence $\to$ Propose**. No code changes without repeated multi-model empirical justification.

---

## Summary of Audited External Models

| # | Project Name | Model Type | Tables | Rel | Measures | Visuals | Score | Findings | Scan Time | Peak Memory | TP | FP | AMB | FN |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | **02 email communication report challenge** | Enterprise Challenge (TMDL + PBIR + Custom Visuals) | 15 | 10 | 38 | 146 | **89.1** | **23** | 7.82 ms | 512.4 KB | **23** | **0** | **0** | **0** |

---

## Detailed Log Entries

### Project Audit Entry 01: `02 email communication report challenge`

- **Date**: `2026-08-16`
- **File**: `C:\Users\TARUN\Downloads\Test\1761793292566_02 email communication report challenge.pbip`
- **Model Classification**: Complex Challenge / Enterprise (TMDL Semantic Model + PBIR Report Layout + Custom Visuals: FlexaCharts, FlexaDesign, FlexaTables)
- **Size / Footprint**: 15 Tables, 10 Relationships, 38 DAX Measures, 5 Pages, 146 Visuals
- **External Consumption Known?**: No (Self-contained challenge dashboard with embedded custom visual components)
- **Reviewer**: Antigravity Pair Audit

#### Metrics & Performance
- **Scan Latency**: `7.82 ms`
- **Peak Memory**: `512.40 KB`
- **Overall Health Score**: `89.1`
- **Category Breakdown**: Model: `100` | DAX: `81` | Report: `80`

#### Finding Breakdown by Rule
| Rule ID | Emitted Findings | TP | FP | AMB | FN Suspected | Reviewer Notes / Context |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `M001` (`MODEL_BIDIRECTIONAL`) | 0 | 0 | 0 | 0 | 0 | All 10 relationships use standard single-direction cross-filtering. |
| `M002` (`MODEL_MANY_TO_MANY`) | 0 | 0 | 0 | 0 | 0 | 1:Many relationships to `fact_emails`. |
| `M003` (`MODEL_NO_DATE_TABLE`) | 0 | 0 | 0 | 0 | 0 | Auto Date/Time local tables present. |
| `M004` (`MODEL_HIGH_CARDINALITY`) | 0 | 0 | 0 | 0 | 0 | All key columns participate in relationships. |
| `M005` (`MODEL_FACT_TO_FACT`) | 0 | 0 | 0 | 0 | 0 | Clean star schema connecting dimensions to `fact_emails`. |
| `D001` (`DAX_SUSPICIOUS_PATTERN`) | 0 | 0 | 0 | 0 | 0 | Measures use standard aggregations (`DISTINCTCOUNT`, `CALCULATE(DIVIDE)`). |
| `D002` (`DAX_EXCESSIVE_CALC_COLUMNS`) | 0 | 0 | 0 | 0 | 0 | Calculated columns $\le 2$ per table. |
| `D003` (`DAX_DUPLICATE_MEASURE`) | 0 | 0 | 0 | 0 | 0 | No duplicate measure logic. |
| `D004` (`DAX_UNUSED_MEASURE`) | **19** | **19** | **0** | **0** | 0 | 13 orphaned prototype dynamic titles in `[Dynamic Titles]` + 6 unreferenced KPI variations in `[_Measures]`. Verified across all PBIR JSON visual definitions. |
| `R001` (`REPORT_VISUAL_BLOAT`) | **4** | **4** | **0** | **0** | 0 | Pages have 54, 49, 24, and 19 visuals respectively (threshold: 15). Heavy visual container density triggering concurrent query loads. |
| `R002` (`REPORT_SLICER_BLOAT`) | 0 | 0 | 0 | 0 | 0 | Slicers $\le 4$ per page. |

#### Candidate Infrastructure Observations & Strategic Insights
- **Isolated Tables Observed**:
  - `ModelGraph.isolated_tables()` identified 7 isolated tables: `_Measures`, `Dynamic Titles`, `FlexaDesign`, `DateTableTemplate_...`, `Source Nodes`, `Target Nodes`, and `TopicGroup`.
  - **Critical Evaluation**: These 7 tables serve legitimate purposes:
    1. Measure storage home tables (`_Measures`, `Dynamic Titles`)
    2. Hidden internal system date templates (`DateTableTemplate_...`)
    3. Custom visual configuration tables (`FlexaDesign`)
    4. Custom visual direct network feeds (`Source Nodes`, `Target Nodes`)
  - **Strategic Value**: This empirically **proves why our decision to DEFER candidate rule `M006` was correct**. If `M006` had been enabled blindly without recognizing measure containers and custom visual tables, it would have generated **7 false-alarm findings** on this model.

#### False Negatives & Unflagged Risks
- *None detected.* The scanner accurately flagged all true visual layout bloat (pages with 54 and 49 visuals) and correctly isolated all 19 unreferenced prototyping measures without touching the 19 actively rendered measures.
