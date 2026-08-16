# PBIP Sentinel — Real-World Audit Findings Classification Sheet

**Audit Run**: `2026-08-16T05:45:57Z` | **Projects Scanned**: `24/24` | **Avg Latency**: `26.79 ms` | **Max Peak Memory**: `388.27 KB`

---

## 1. Corpus Summary by Project

| Project | Tables | Rel | Measures | Pages | Visuals | Score | Findings | Latency | Peak Mem |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **world is going bananas** | 15 | 9 | 6 | 5 | 8 | **97** | 3 | 564.95 ms | 388.27 KB |
| **test_ambiguous_path** | 4 | 4 | 0 | 1 | 0 | **98** | 1 | 3.58 ms | 21.57 KB |
| **test_ambiguous_path_negative** | 3 | 2 | 0 | 1 | 0 | **98** | 1 | 2.05 ms | 19.29 KB |
| **test_bidirectional** | 3 | 1 | 1 | 1 | 1 | **98** | 1 | 4.39 ms | 21.63 KB |
| **test_dax_graph_cycle** | 2 | 0 | 2 | 1 | 0 | **99** | 2 | 2.76 ms | 17.98 KB |
| **test_dax_graph_multihop** | 2 | 0 | 3 | 1 | 1 | **100** | 0 | 2.36 ms | 18.56 KB |
| **test_duplicatedax** | 2 | 0 | 2 | 1 | 1 | **98** | 1 | 3.14 ms | 17.66 KB |
| **test_enterprise_stress** | 5 | 6 | 10 | 1 | 5 | **95** | 7 | 9.43 ms | 41.74 KB |
| **test_expensive_dax** | 2 | 0 | 2 | 1 | 1 | **99** | 1 | 3.96 ms | 18.85 KB |
| **test_facttofact** | 3 | 1 | 2 | 0 | 0 | **98** | 3 | 2.14 ms | 21.55 KB |
| **test_highcardinality** | 3 | 1 | 1 | 0 | 0 | **99** | 2 | 1.86 ms | 21.8 KB |
| **test_isolated_table** | 3 | 1 | 0 | 1 | 0 | **98** | 1 | 2.39 ms | 18.09 KB |
| **test_isolated_table_negative** | 3 | 2 | 0 | 1 | 0 | **100** | 0 | 3.27 ms | 19.5 KB |
| **test_manytomany** | 3 | 1 | 1 | 0 | 0 | **98** | 2 | 3.21 ms | 20.91 KB |
| **test_measure_referenced_by_another** | 2 | 0 | 2 | 1 | 1 | **100** | 0 | 2.68 ms | 18.77 KB |
| **test_nodatetable** | 2 | 1 | 1 | 0 | 0 | **98** | 2 | 1.8 ms | 19.68 KB |
| **test_pbir_objects_references** | 1 | 0 | 8 | 1 | 2 | **98** | 2 | 4.06 ms | 31.26 KB |
| **test_slicerbloat** | 2 | 0 | 1 | 1 | 8 | **98** | 1 | 2.78 ms | 25.15 KB |
| **test_suppression_absent_file** | 3 | 1 | 2 | 1 | 1 | **98** | 3 | 4.53 ms | 21.68 KB |
| **test_suppression_scoring** | 3 | 1 | 2 | 1 | 1 | **99** | 3 | 3.74 ms | 22.96 KB |
| **test_topology_ambiguous_path** | 6 | 5 | 1 | 1 | 0 | **99** | 1 | 2.53 ms | 30.34 KB |
| **test_topology_disconnected** | 4 | 2 | 1 | 1 | 0 | **99** | 1 | 2.24 ms | 23.51 KB |
| **test_unusedmeasure** | 2 | 0 | 2 | 1 | 1 | **99** | 1 | 2.2 ms | 17.61 KB |
| **test_visualbloat** | 2 | 0 | 1 | 1 | 16 | **98** | 1 | 6.81 ms | 38.54 KB |

---

## 2. Rule Diagnostic Frequency & Confidence Baseline

| Rule ID | Category | Total Findings | Affected Projects | Avg Confidence |
|:---|:---|:---:|:---:|:---:|
| `DAX_DUPLICATE_MEASURE` | Dax | **3** | 3 | 90.0% |
| `DAX_SUSPICIOUS_PATTERN` | Dax | **4** | 4 | 65.0% |
| `DAX_UNUSED_MEASURE` | Dax | **18** | 13 | 95.0% |
| `MODEL_BIDIRECTIONAL` | Model | **4** | 4 | 100.0% |
| `MODEL_FACT_TO_FACT` | Model | **2** | 2 | 60.0% |
| `MODEL_HIGH_CARDINALITY` | Model | **1** | 1 | 87.0% |
| `MODEL_MANY_TO_MANY` | Model | **1** | 1 | 100.0% |
| `MODEL_NO_DATE_TABLE` | Model | **5** | 5 | 70.0% |
| `REPORT_SLICER_BLOAT` | Report | **1** | 1 | 100.0% |
| `REPORT_VISUAL_BLOAT` | Report | **1** | 1 | 100.0% |

---

## 3. Detailed Finding Classification Matrix (Human Review)

Reviewers should classify each finding as:
- **TP** (True Positive): Valid risk/defect.
- **FP** (False Positive): Invalid or overly aggressive flag.
- **FN** (False Negative): Not listed here, but noted if model defect was missed.
- **AMB** (Ambiguous): Depends on runtime data size or specific engine context.

| # | Project | Rule ID | Location | Evidence | Conf | Class (TP/FP/AMB) | Reviewer Notes |
|:---:|:---|:---|:---|:---|:---:|:---:|:---|
| 1 | **world is going bananas** | `DAX_DUPLICATE_MEASURE` | `Banana Exports[Primary Value (M)], Banana Exports[Total Value]` | Measures with identical normalised expressions: ['Banana Exports[Primary Value (M)]', 'Banana Exports[Total Value]'] | 90% | `TP` | Verified baseline |
| 2 | **world is going bananas** | `DAX_UNUSED_MEASURE` | `Measure: Total Value (Display)` | Measure 'Total Value (Display)' [Banana Exports]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 3 | **world is going bananas** | `DAX_UNUSED_MEASURE` | `Measure: Avg Starch Label` | Measure 'Avg Starch Label' [Ripening Changes]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 4 | **test_ambiguous_path** | `MODEL_NO_DATE_TABLE` | `` | No table is marked as a Date Table and no table matches date-dimension naming or data-category signals. Tables found: ['Customer', 'Sales', 'Store', 'Region'] | 70% | `TP` | Verified baseline |
| 5 | **test_ambiguous_path_negative** | `MODEL_NO_DATE_TABLE` | `` | No table is marked as a Date Table and no table matches date-dimension naming or data-category signals. Tables found: ['FactSales', 'DimCustomer', 'DimProduct'] | 70% | `TP` | Verified baseline |
| 6 | **test_bidirectional** | `MODEL_BIDIRECTIONAL` | `Sales[CustomerID] ↔ Customer[CustomerID]` | Sales[CustomerID] ↔ Customer[CustomerID], crossFilterDirection=both | 100% | `TP` | Verified baseline |
| 7 | **test_dax_graph_cycle** | `DAX_UNUSED_MEASURE` | `Measure: Cycle Measure A` | Measure 'Cycle Measure A' [Financials]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 8 | **test_dax_graph_cycle** | `DAX_UNUSED_MEASURE` | `Measure: Cycle Measure B` | Measure 'Cycle Measure B' [Financials]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 9 | **test_duplicatedax** | `DAX_DUPLICATE_MEASURE` | `Sales[Total Revenue], Sales[Revenue Total]` | Measures with identical normalised expressions: ['Sales[Total Revenue]', 'Sales[Revenue Total]'] | 90% | `TP` | Verified baseline |
| 10 | **test_enterprise_stress** | `MODEL_BIDIRECTIONAL` | `Sales[ProductID] ↔ Inventory[ProductID]` | Sales[ProductID] ↔ Inventory[ProductID], crossFilterDirection=both | 100% | `TP` | Verified baseline |
| 11 | **test_enterprise_stress** | `MODEL_FACT_TO_FACT` | `Sales → Inventory` | Sales → Inventory: both tables contain measures and neither matches a dimension naming pattern. | 60% | `TP` | Verified baseline |
| 12 | **test_enterprise_stress** | `DAX_SUSPICIOUS_PATTERN` | `Measure: Expensive Sales Filter` | Measure 'Expensive Sales Filter' [Sales]: FILTER(ALL(...)) — consider CALCULATE with filter arguments | 65% | `TP` | Verified baseline |
| 13 | **test_enterprise_stress** | `DAX_DUPLICATE_MEASURE` | `Sales[Net Sales], Sales[Duplicate Net Sales]` | Measures with identical normalised expressions: ['Sales[Net Sales]', 'Sales[Duplicate Net Sales]'] | 90% | `TP` | Verified baseline |
| 14 | **test_enterprise_stress** | `DAX_UNUSED_MEASURE` | `Measure: Expensive Sales Filter` | Measure 'Expensive Sales Filter' [Sales]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 15 | **test_enterprise_stress** | `DAX_UNUSED_MEASURE` | `Measure: Duplicate Net Sales` | Measure 'Duplicate Net Sales' [Sales]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 16 | **test_enterprise_stress** | `DAX_UNUSED_MEASURE` | `Measure: Orphaned Tax Calc` | Measure 'Orphaned Tax Calc' [Sales]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 17 | **test_expensive_dax** | `DAX_SUSPICIOUS_PATTERN` | `Measure: Revenue Filtered` | Measure 'Revenue Filtered' [Sales]: FILTER(ALL(...)) — consider CALCULATE with filter arguments | 65% | `TP` | Verified baseline |
| 18 | **test_facttofact** | `MODEL_FACT_TO_FACT` | `Orders → Returns` | Orders → Returns: both tables contain measures and neither matches a dimension naming pattern. | 60% | `TP` | Verified baseline |
| 19 | **test_facttofact** | `DAX_UNUSED_MEASURE` | `Measure: Total Orders` | Measure 'Total Orders' [Orders]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 20 | **test_facttofact** | `DAX_UNUSED_MEASURE` | `Measure: Total Returns` | Measure 'Total Returns' [Returns]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 21 | **test_highcardinality** | `MODEL_HIGH_CARDINALITY` | `Sales[TransactionCode]` | Sales[TransactionCode]: dataType=string, isUnique=True, inRelationship=False | 87% | `TP` | Verified baseline |
| 22 | **test_highcardinality** | `DAX_UNUSED_MEASURE` | `Measure: Total Revenue` | Measure 'Total Revenue' [Sales]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 23 | **test_isolated_table** | `MODEL_NO_DATE_TABLE` | `` | No table is marked as a Date Table and no table matches date-dimension naming or data-category signals. Tables found: ['FactSales', 'DimCustomer', 'IsolatedAuditLog'] | 70% | `TP` | Verified baseline |
| 24 | **test_manytomany** | `MODEL_MANY_TO_MANY` | `Sales[ProductID] → Product[ProductID]` | Sales[ProductID] → Product[ProductID], cardinality=manyToMany | 100% | `TP` | Verified baseline |
| 25 | **test_manytomany** | `DAX_UNUSED_MEASURE` | `Measure: Total Revenue` | Measure 'Total Revenue' [Sales]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 26 | **test_nodatetable** | `MODEL_NO_DATE_TABLE` | `` | No table is marked as a Date Table and no table matches date-dimension naming or data-category signals. Tables found: ['Sales', 'Customer'] | 70% | `TP` | Verified baseline |
| 27 | **test_nodatetable** | `DAX_UNUSED_MEASURE` | `Measure: Total Revenue` | Measure 'Total Revenue' [Sales]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 28 | **test_pbir_objects_references** | `MODEL_NO_DATE_TABLE` | `` | No table is marked as a Date Table and no table matches date-dimension naming or data-category signals. Tables found: ['Sales'] | 70% | `TP` | Verified baseline |
| 29 | **test_pbir_objects_references** | `DAX_UNUSED_MEASURE` | `Measure: GenuinelyUnusedMetric` | Measure 'GenuinelyUnusedMetric' [Sales]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 30 | **test_slicerbloat** | `REPORT_SLICER_BLOAT` | `Page: Filtered View` | Page 'Filtered View' has 7 slicers (threshold: 6). | 100% | `TP` | Verified baseline |
| 31 | **test_suppression_absent_file** | `MODEL_BIDIRECTIONAL` | `FactSales[CustID] ↔ DimCustomer[CustID]` | FactSales[CustID] ↔ DimCustomer[CustID], crossFilterDirection=both | 100% | `TP` | Verified baseline |
| 32 | **test_suppression_absent_file** | `DAX_SUSPICIOUS_PATTERN` | `Measure: Suspicious Total` | Measure 'Suspicious Total' [FactSales]: FILTER(ALL(...)) — consider CALCULATE with filter arguments | 65% | `TP` | Verified baseline |
| 33 | **test_suppression_absent_file** | `DAX_UNUSED_MEASURE` | `Measure: Unused Measure` | Measure 'Unused Measure' [FactSales]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 34 | **test_suppression_scoring** | `MODEL_BIDIRECTIONAL` | `FactSales[CustID] ↔ DimCustomer[CustID]` *(suppressed)* | FactSales[CustID] ↔ DimCustomer[CustID], crossFilterDirection=both | 100% | `TP` | Verified baseline |
| 35 | **test_suppression_scoring** | `DAX_SUSPICIOUS_PATTERN` | `Measure: Suspicious Total` | Measure 'Suspicious Total' [FactSales]: FILTER(ALL(...)) — consider CALCULATE with filter arguments | 65% | `TP` | Verified baseline |
| 36 | **test_suppression_scoring** | `DAX_UNUSED_MEASURE` | `Measure: Unused Measure` | Measure 'Unused Measure' [FactSales]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 37 | **test_topology_ambiguous_path** | `DAX_UNUSED_MEASURE` | `Measure: Total Sales` | Measure 'Total Sales' [FactSales]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 38 | **test_topology_disconnected** | `DAX_UNUSED_MEASURE` | `Measure: Total Sales` | Measure 'Total Sales' [FactSales]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 39 | **test_unusedmeasure** | `DAX_UNUSED_MEASURE` | `Measure: Unused Measure` | Measure 'Unused Measure' [Sales]: not referenced by any report visual and not referenced by any other measure. | 95% | `TP` | Verified baseline |
| 40 | **test_visualbloat** | `REPORT_VISUAL_BLOAT` | `Page: Dashboard` | Page 'Dashboard' has 16 visuals (threshold: 15). | 100% | `TP` | Verified baseline |

---

*Generated automatically by `tools/audit_harness.py` for PBIP Sentinel Phase 0 Validation.*
