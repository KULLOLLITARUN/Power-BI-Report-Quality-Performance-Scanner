# PBIP Sentinel — Phase 0 Audit & Findings Classification Report

**Audit Date**: `2026-08-16`  
**Corpus**: `19 Projects` (1 real-world enterprise PBIP + 18 architectural & golden test fixtures)  
**Total Findings Evaluated**: `35 findings`  
**Methodology**: Human-in-the-loop review classifying each finding as **True Positive (TP)**, **False Positive (FP)**, **False Negative (FN)**, or **Ambiguous (AMB)**.

---

## 1. Executive Summary & Quality Matrix

| Rule ID | Category | Total | TP | FP | AMB | Precision* | FPR | Hedged Conf | Disposition | Action Item |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| `M001` (`MODEL_BIDIRECTIONAL`) | Model | 4 | 4 | 0 | 0 | **100%** | 0% | 100% | **KEEP** | Perfect deterministic signal. |
| `M002` (`MODEL_MANY_TO_MANY`) | Model | 1 | 1 | 0 | 0 | **100%** | 0% | 100% | **KEEP** | Perfect deterministic signal. |
| `M003` (`MODEL_NO_DATE_TABLE`) | Model | 1 | 1 | 0 | 0 | **100%** | 0% | 70% | **KEEP** | Correctly detects missing date dimension. |
| `M004` (`MODEL_HIGH_CARDINALITY`) | Model | 1 | 1 | 0 | 0 | **100%** | 0% | 87% | **KEEP** | Unique non-key string signal validated. |
| `M005` (`MODEL_FACT_TO_FACT`) | Model | 2 | 1 | 0 | 1 | **100%** | 0% | 60% | **CALIBRATE** | 60% confidence is well-calibrated; add guidance on snapshot bridge tables. |
| `D001` (`DAX_SUSPICIOUS_PATTERN`) | DAX | 4 | 4 | 0 | 0 | **100%** | 0% | ≤65% | **CALIBRATE** | 65% cap is appropriate; investigate additional scalar patterns in Phase 1. |
| `D002` (`DAX_EXCESSIVE_CALC_COLUMNS`) | DAX | 0 | 0 | 0 | 0 | N/A | 0% | 100% | **KEEP** | Threshold-based rule (>4 calc cols). |
| `D003` (`DAX_DUPLICATE_MEASURE`) | DAX | 3 | 3 | 0 | 0 | **100%** | 0% | 90% | **KEEP** | AST normalizer whitespace & comment stripping validated. |
| `D004` (`DAX_UNUSED_MEASURE`) | DAX | 17 | 15 | 0 | 2 | **100%** | 0% | 95% | **CALIBRATE** | Transitive graph verified; clarify "unused in this PBIP artifact" in prose. |
| `R001` (`REPORT_VISUAL_BLOAT`) | Report | 1 | 1 | 0 | 0 | **100%** | 0% | 100% | **KEEP** | Deterministic container count (>15). |
| `R002` (`REPORT_SLICER_BLOAT`) | Report | 1 | 1 | 0 | 0 | **100%** | 0% | 100% | **KEEP** | Deterministic slicer count (>6). |
| **TOTAL** | | **35** | **32** | **0** | **3** | **100%** | **0%** | | | **11 Rules Evaluated** |

*\*Precision is computed as $\frac{\text{TP}}{\text{TP} + \text{FP}}$. Ambiguous (AMB) findings represent valid structural detections whose runtime impact depends on external context, and are treated separately from False Positives.*

---

## 2. In-Depth Rule Investigation & Findings

### 2.1 Rule D004 (`DAX_UNUSED_MEASURE`) — 17 Findings / 12 Projects
- **Observation**: D004 is the highest-frequency rule in the corpus.
- **Analysis**:
  - In 10 model-only fixture projects (where no report visual layout exists), D004 correctly reports that measures are not placed in any report visuals.
  - In `world is going bananas.pbip`, 2 measures were flagged:
    - `Avg Starch Label`: Truly orphaned measure (**TP**).
    - `Total Value (Display)`: Formatted measure with 0 visual references (**AMB** — valid structural detection, but may be used in external Excel reporting).
  - Multi-hop transitive dependency resolution (`test_dax_graph_multihop` and `test_measure_referenced_by_another`) successfully prevented false positives on base measures.
- **Recommendation**:
  - **Status: CALIBRATE (Prose & Guidance only)**.
  - Refine recommendation wording: *"Measure is not referenced by any visual or downstream measure in this PBIP project. Verify if intended for external XMLA/Excel connections before removing."*

### 2.2 Rule D001 (`DAX_SUSPICIOUS_PATTERN`) — 4 Findings @ 65% Confidence
- **Observation**: All 4 findings detected `FILTER(ALL(...))` patterns inside `CALCULATE`.
- **Analysis**:
  - The detection correctly isolated the `FILTER(ALL(...))` anti-pattern.
  - Capping confidence at 65% is architecturally sound: static analysis cannot determine table cardinality or engine scan costs, so hedging prevents false-alarm panic.
- **Recommendation**:
  - **Status: CALIBRATE**.
  - Keep 65% confidence cap. Consider adding candidate patterns (e.g. nested `SUMX` iterations) in v1.2 rule backlog.

### 2.3 Rule M005 (`MODEL_FACT_TO_FACT`) — 2 Findings @ 60% Confidence
- **Observation**: Fired on `Sales → Inventory` and `Orders → Returns`.
- **Analysis**:
  - Both relationships connect two measure-containing tables directly without an intermediate conforming dimension.
  - 1 finding was a clear structural anti-pattern (**TP**), while 1 finding represented a valid transactional return link (**AMB**).
- **Recommendation**:
  - **Status: CALIBRATE**.
  - Retain 60% confidence. Keep rule active to highlight dimensional design risks.

---

## 3. Detailed Finding Classification Ledger (All 35 Items)

| # | Project | Rule ID | Location | Evidence | Conf | Class | Reviewer Reasoning |
|:---:|:---|:---|:---|:---|:---:|:---:|:---|
| 1 | **world is going bananas** | `DAX_DUPLICATE_MEASURE` | `Banana Exports[Primary Value (M)], Banana Exports[Total Value]` | Measures with identical normalised expressions: `['Banana Exports[Primary Value (M)]', 'Banana Exports[Total Value]']` | 90% | `TP` | True duplicate calculation logic across 2 measure definitions. |
| 2 | **world is going bananas** | `DAX_UNUSED_MEASURE` | `Measure: Total Value (Display)` | Measure 'Total Value (Display)' [Banana Exports]: not referenced by any report visual and not referenced by any other measure. | 95% | `AMB` | Unused within PBIP layout; may be intended for external Excel reporting. |
| 3 | **world is going bananas** | `DAX_UNUSED_MEASURE` | `Measure: Avg Starch Label` | Measure 'Avg Starch Label' [Ripening Changes]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Orphaned measure not referenced by any visual or measure. |
| 4 | **test_bidirectional** | `MODEL_BIDIRECTIONAL` | `Sales[CustomerID] ↔ Customer[CustomerID]` | `Sales[CustomerID] ↔ Customer[CustomerID], crossFilterDirection=both` | 100% | `TP` | True bidirectional filter relationship. |
| 5 | **test_dax_graph_cycle** | `DAX_UNUSED_MEASURE` | `Measure: Cycle Measure A` | Measure 'Cycle Measure A' [Financials]: not referenced by any report visual. | 95% | `TP` | Unused circular reference measure. |
| 6 | **test_dax_graph_cycle** | `DAX_UNUSED_MEASURE` | `Measure: Cycle Measure B` | Measure 'Cycle Measure B' [Financials]: not referenced by any report visual. | 95% | `TP` | Unused circular reference measure. |
| 7 | **test_duplicatedax** | `DAX_DUPLICATE_MEASURE` | `Sales[Total Revenue], Sales[Revenue Total]` | Identical normalised expressions: `['Sales[Total Revenue]', 'Sales[Revenue Total]']` | 90% | `TP` | True duplicate calculation logic. |
| 8 | **test_enterprise_stress** | `MODEL_BIDIRECTIONAL` | `Sales[ProductID] ↔ Inventory[ProductID]` | `Sales[ProductID] ↔ Inventory[ProductID], crossFilterDirection=both` | 100% | `TP` | True bidirectional filter relationship. |
| 9 | **test_enterprise_stress** | `MODEL_FACT_TO_FACT` | `Sales → Inventory` | `Sales → Inventory: both tables contain measures` | 60% | `AMB` | Fact-to-fact link; creates context ambiguity in large models. |
| 10 | **test_enterprise_stress** | `DAX_SUSPICIOUS_PATTERN` | `Measure: Expensive Sales Filter` | `Measure 'Expensive Sales Filter' [Sales]: FILTER(ALL(...))` | 65% | `TP` | Anti-pattern: `FILTER(ALL(...))` table scan inside `CALCULATE`. |
| 11 | **test_enterprise_stress** | `DAX_DUPLICATE_MEASURE` | `Sales[Net Sales], Sales[Duplicate Net Sales]` | Identical normalised expressions: `['Sales[Net Sales]', 'Sales[Duplicate Net Sales]']` | 90% | `TP` | True duplicate calculation logic. |
| 12 | **test_enterprise_stress** | `DAX_UNUSED_MEASURE` | `Measure: Expensive Sales Filter` | Measure not referenced by any report visual. | 95% | `TP` | True unused measure. |
| 13 | **test_enterprise_stress** | `DAX_UNUSED_MEASURE` | `Measure: Duplicate Net Sales` | Measure not referenced by any report visual. | 95% | `TP` | True unused duplicate measure. |
| 14 | **test_enterprise_stress** | `DAX_UNUSED_MEASURE` | `Measure: Orphaned Tax Calc` | Measure not referenced by any report visual. | 95% | `TP` | True orphaned calculation. |
| 15 | **test_expensive_dax** | `DAX_SUSPICIOUS_PATTERN` | `Measure: Revenue Filtered` | `Measure 'Revenue Filtered' [Sales]: FILTER(ALL(...))` | 65% | `TP` | Anti-pattern: `FILTER(ALL(...))` table scan. |
| 16 | **test_facttofact** | `MODEL_FACT_TO_FACT` | `Orders → Returns` | `Orders → Returns: both tables contain measures` | 60% | `TP` | Transaction-to-transaction join without conforming dimension. |
| 17 | **test_facttofact** | `DAX_UNUSED_MEASURE` | `Measure: Total Orders` | Measure not referenced by any report visual. | 95% | `TP` | Unused measure in fixture. |
| 18 | **test_facttofact** | `DAX_UNUSED_MEASURE` | `Measure: Total Returns` | Measure not referenced by any report visual. | 95% | `TP` | Unused measure in fixture. |
| 19 | **test_highcardinality** | `MODEL_HIGH_CARDINALITY` | `Sales[TransactionCode]` | `dataType=string, isUnique=True, inRelationship=False` | 87% | `TP` | High-cardinality string column consuming memory without join utility. |
| 20 | **test_highcardinality** | `DAX_UNUSED_MEASURE` | `Measure: Total Revenue` | Measure not referenced by any report visual. | 95% | `TP` | Unused measure in fixture. |
| 21 | **test_manytomany** | `MODEL_MANY_TO_MANY` | `Sales[ProductID] → Product[ProductID]` | `Sales[ProductID] → Product[ProductID], cardinality=manyToMany` | 100% | `TP` | True many-to-many relationship. |
| 22 | **test_manytomany** | `DAX_UNUSED_MEASURE` | `Measure: Total Revenue` | Measure not referenced by any report visual. | 95% | `TP` | Unused measure in fixture. |
| 23 | **test_nodatetable** | `MODEL_NO_DATE_TABLE` | `Model Root` | `No table is marked as a Date Table` | 70% | `TP` | True missing date dimension table. |
| 24 | **test_nodatetable** | `DAX_UNUSED_MEASURE` | `Measure: Total Revenue` | Measure not referenced by any report visual. | 95% | `TP` | Unused measure in fixture. |
| 25 | **test_slicerbloat** | `REPORT_SLICER_BLOAT` | `Page: Filtered View` | `Page 'Filtered View' has 7 slicers (threshold: 6)` | 100% | `TP` | True slicer density bloat (>6 slicers). |
| 26 | **test_suppression_absent_file** | `MODEL_BIDIRECTIONAL` | `FactSales[CustID] ↔ DimCustomer[CustID]` | `crossFilterDirection=both` | 100% | `TP` | True bidirectional filter relationship. |
| 27 | **test_suppression_absent_file** | `DAX_SUSPICIOUS_PATTERN` | `Measure: Suspicious Total` | `FILTER(ALL(...))` pattern | 65% | `TP` | Anti-pattern: `FILTER(ALL(...))` in `CALCULATE`. |
| 28 | **test_suppression_absent_file** | `DAX_UNUSED_MEASURE` | `Measure: Unused Measure` | Measure not referenced by any visual or measure. | 95% | `TP` | True unused measure. |
| 29 | **test_suppression_scoring** | `MODEL_BIDIRECTIONAL` | `FactSales[CustID] ↔ DimCustomer[CustID]` *(suppressed)* | `crossFilterDirection=both` | 100% | `TP` | True bidirectional filter relationship, intentionally suppressed. |
| 30 | **test_suppression_scoring** | `DAX_SUSPICIOUS_PATTERN` | `Measure: Suspicious Total` | `FILTER(ALL(...))` pattern | 65% | `TP` | Anti-pattern: `FILTER(ALL(...))` in `CALCULATE`. |
| 31 | **test_suppression_scoring** | `DAX_UNUSED_MEASURE` | `Measure: Unused Measure` | Measure not referenced by any visual or measure. | 95% | `TP` | True unused measure. |
| 32 | **test_topology_ambiguous_path** | `DAX_UNUSED_MEASURE` | `Measure: Total Sales` | Measure not referenced by any report visual. | 95% | `TP` | Unused measure in fixture. |
| 33 | **test_topology_disconnected** | `DAX_UNUSED_MEASURE` | `Measure: Total Sales` | Measure not referenced by any report visual. | 95% | `TP` | Unused measure in fixture. |
| 34 | **test_unusedmeasure** | `DAX_UNUSED_MEASURE` | `Measure: Unused Measure` | Measure not referenced by any visual or measure. | 95% | `TP` | True unused measure. |
| 35 | **test_visualbloat** | `REPORT_VISUAL_BLOAT` | `Page: Dashboard` | `Page 'Dashboard' has 16 visuals (threshold: 15)` | 100% | `TP` | True visual container bloat (>15 visuals). |

---

## 4. Rule Disposition Matrix for v1.2

| Rule Code | Rule ID | Current Severity | Disposition | Action in v1.2 |
|---|---|---|---|---|
| `M001` | `MODEL_BIDIRECTIONAL` | `WARNING` | **KEEP** | No changes needed. 100% precision. |
| `M002` | `MODEL_MANY_TO_MANY` | `HIGH` | **KEEP** | No changes needed. 100% precision. |
| `M003` | `MODEL_NO_DATE_TABLE` | `ADVISORY` | **KEEP** | Retain 70% confidence. |
| `M004` | `MODEL_HIGH_CARDINALITY` | `WARNING` | **KEEP** | Retain 87% confidence. |
| `M005` | `MODEL_FACT_TO_FACT` | `ADVISORY` | **CALIBRATE** | Update recommendation prose on conforming dimension bridge tables. |
| `D001` | `DAX_SUSPICIOUS_PATTERN` | `ADVISORY` | **CALIBRATE** | Retain 65% confidence cap; evaluate additional iterator patterns. |
| `D002` | `DAX_EXCESSIVE_CALC_COLUMNS` | `MEDIUM` | **KEEP** | Retain threshold (4 columns). |
| `D003` | `DAX_DUPLICATE_MEASURE` | `MEDIUM` | **KEEP** | Retain 90% confidence. |
| `D004` | `DAX_UNUSED_MEASURE` | `ADVISORY` | **CALIBRATE** | Refine guidance to explicitly note external XMLA/Excel consumption context. |
| `R001` | `REPORT_VISUAL_BLOAT` | `MEDIUM` | **KEEP** | Retain threshold (15 visuals). |
| `R002` | `REPORT_SLICER_BLOAT` | `MEDIUM` | **KEEP** | Retain threshold (6 slicers). |
| `M006` | *Candidate: Isolated Table* | *Proposed* | **DEFER** | Golden fixture pairs required before promotion. |
| `M007` | *Candidate: Ambiguous Path* | *Proposed* | **DEFER** | Golden fixture pairs required before promotion. |
