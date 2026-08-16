# PBIP Sentinel — v1.2 Post-Release Observation Ledger

**Status**: Active Observation Window  
**Baseline Scanner**: `pbiscan v1.2.0` (Frozen Control Group, Commit `a81a246`)  
**Governing Discipline**: **Observe $\to$ Classify $\to$ Accumulate Evidence $\to$ Propose**. No code changes without repeated multi-model empirical justification.

---

## Summary of Audited External Models

| # | Project Name | Model Type | Tables | Rel | Measures | Visuals | Score | Findings | Scan Time | Peak Memory | TP | FP | AMB | FN |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | **02 email communication report challenge** | Enterprise Challenge (TMDL + PBIR + Custom Visuals) | 15 | 10 | 38 | 146 | **89.1** | **23** | 7.82 ms | 512.4 KB | **23** | **0** | **0** | **0** |
| 2 | **03 Xmas Sales** | Sales Analytics (TMDL + PBIR + Reference Label Cards) | 4 | 1 | 20 | 69 | **95.6** | **8** | 59.64 ms | 287.2 KB | **3** | **5** | **0** | **0** |

---

## Cumulative Observation Statistics across External Models

- **Total External Projects Scanned**: `2`
- **Total External Findings Evaluated**: `31`
- **True Positives (TP)**: `26` (83.9%)
- **False Positives (FP)**: `5` (16.1%) — *All 5 on D004 via modern PBIR `objects.referenceLabel` bindings*
- **Ambiguous (AMB)**: `0`
- **Suspected False Negatives (FN)**: `0`

---

## Detailed Log Entries

### Project Audit Entry 02: `03 Xmas Sales`

- **Date**: `2026-08-16`
- **File**: `C:\Users\TARUN\Downloads\test2\1767842152777_1765180280123_03 Xmas Sales.pbip`
- **Model Classification**: Sales Analytics (TMDL Semantic Model + PBIR Report Layout with Modern New Card Visual Reference Labels)
- **Size / Footprint**: 4 Tables, 1 Relationship, 20 DAX Measures, 9 Calc Columns, 2 Pages, 69 Visuals
- **External Consumption Known?**: No
- **Reviewer**: Antigravity Pair Audit

#### Metrics & Performance
- **Scan Latency**: `59.64 ms`
- **Peak Memory**: `287.20 KB`
- **Overall Health Score**: `95.6`
- **Category Breakdown**: Model: `100` | DAX: `94` | Report: `90`

#### Finding Breakdown by Rule
| Rule ID | Emitted Findings | TP | FP | AMB | FN Suspected | Reviewer Notes / Context |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `M001` (`MODEL_BIDIRECTIONAL`) | 0 | 0 | 0 | 0 | 0 | Single relationship is 1-direction (`Xmas Dataset` &rarr; `Dim_Date`). |
| `M002` (`MODEL_MANY_TO_MANY`) | 0 | 0 | 0 | 0 | 0 | No M:M relationships. |
| `M003` (`MODEL_NO_DATE_TABLE`) | 0 | 0 | 0 | 0 | 0 | `Dim_Date` table present. |
| `M004` (`MODEL_HIGH_CARDINALITY`) | 0 | 0 | 0 | 0 | 0 | No unlinked unique text columns. |
| `M005` (`MODEL_FACT_TO_FACT`) | 0 | 0 | 0 | 0 | 0 | Single fact table (`Xmas Dataset`). |
| `D001` (`DAX_SUSPICIOUS_PATTERN`) | 0 | 0 | 0 | 0 | 0 | Clean time-intelligence / scalar DAX. |
| `D002` (`DAX_EXCESSIVE_CALC_COLUMNS`) | 0 | 0 | 0 | 0 | 0 | Calc columns split across tables ($\le 5$). |
| `D003` (`DAX_DUPLICATE_MEASURE`) | 0 | 0 | 0 | 0 | 0 | Distinct DAX expressions. |
| `D004` (`DAX_UNUSED_MEASURE`) | **6** | **1** | **5** | **0** | 0 | **1 TP**: `Sales Index` is truly unreferenced. **5 FP**: `Profit 20`, `Delta Profit 21 20`, `Delta Sales 21 18`, `Delta Unit Sold 21 20`, `Unit Sold 20` are actively rendered in the new Card visual via `objects.referenceLabel` and `objects.referenceLabelDetail` properties in PBIR layout. |
| `R001` (`REPORT_VISUAL_BLOAT`) | **2** | **2** | **0** | **0** | 0 | `Customer Segment` (40 visuals) and `Pricing & Promotion` (29 visuals) exceed 15-visual threshold. |
| `R002` (`REPORT_SLICER_BLOAT`) | 0 | 0 | 0 | 0 | 0 | Slicers $\le 3$ per page. |

#### Empirical Discovery & Technical Gap Identified (for future v1.3 backlog)
- **Extraction Limitation Identified**:
  - `PBIPReader._extract_pbir_visual()` extracts measure references from `prototypeQuery.Select`, `dataRoles`, and visual filter payloads.
  - In modern Power BI Desktop (New Card visual / Reference Labels / Subtitles / Visual Tooltip cards), measures can be assigned inside `objects.referenceLabel[].properties.value.expr.Measure` and `objects.referenceLabelDetail[].properties.detailValue.expr.Measure`.
  - Because `PBIPReader` did not deeply traverse the `objects` block of PBIR JSON, 5 measures bound inside reference labels were not captured in `visual.measure_refs`, causing `D004` to emit false-positive unused warnings.
- **Actionable v1.3 Target**:
  - Add recursive AST/JSON object traversal in `PBIPReader` to extract measure expressions inside `objects.*.properties.*.expr.Measure`.
  - **Operating Rule**: In accordance with v1.2 immutability, **no code is modified now**. This observation is formally recorded as empirical evidence for the v1.3 planning backlog.

---

### Project Audit Entry 01: `02 email communication report challenge`

- **Date**: `2026-08-16`
- **File**: `C:\Users\TARUN\Downloads\Test\1761793292566_02 email communication report challenge.pbip`
- **Model Classification**: Complex Challenge / Enterprise (TMDL Semantic Model + PBIR Report Layout + Custom Visuals: FlexaCharts, FlexaDesign, FlexaTables)
- **Size / Footprint**: 15 Tables, 10 Relationships, 38 DAX Measures, 5 Pages, 146 Visuals
- **External Consumption Known?**: No
- **Reviewer**: Antigravity Pair Audit

#### Metrics & Performance
- **Scan Latency**: `7.82 ms`
- **Peak Memory**: `512.40 KB`
- **Overall Health Score**: `89.1`
- **Category Breakdown**: Model: `100` | DAX: `81` | Report: `80`

#### Finding Breakdown by Rule
| Rule ID | Emitted Findings | TP | FP | AMB | FN Suspected | Reviewer Notes / Context |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `D004` (`DAX_UNUSED_MEASURE`) | **19** | **19** | **0** | **0** | 0 | 13 orphaned prototype dynamic titles + 6 unreferenced KPI variations. 0 references in PBIR JSON. |
| `R001` (`REPORT_VISUAL_BLOAT`) | **4** | **4** | **0** | **0** | 0 | Pages with 54, 49, 24, and 19 visuals vs. 15 threshold. |
| `Other Rules` | **0** | - | - | - | 0 | Clean single-direction star schema. |

#### Candidate Infrastructure Observations
- **Isolated Tables Observed**: 7 isolated tables (`_Measures`, `Dynamic Titles`, `FlexaDesign`, `DateTableTemplate_...`, `Source Nodes`, `Target Nodes`, `TopicGroup`). Confirmed that structural isolation does not imply a defect, validating the deferral of `M006`.
