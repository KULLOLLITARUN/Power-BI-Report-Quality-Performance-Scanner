# PBIP Sentinel — v1.4 Observation Ledger & Candidate Backlog

**Baseline Control**: `PBIP Sentinel v1.3.0` (Tag `v1.3.0`, Commit `577d5a8`, 162/162 Passing Tests)  
**Governance Protocol**: Zero-mutation data collection across targeted architectural categories.  
**Classification Taxonomy**: `TP` (True Positive) | `FP` (False Positive) | `FN` (False Negative) | `AMB` (Ambiguous) | `CAP_GAP` (Capability Gap).

---

## 1. Targeted Architectural Domains for v1.4

| Domain Code | Architectural Surface | Description / Potential Blind Spot | Status |
|:---:|---|---|:---:|
| **`DOM-01`** | **Calculation Groups & Calculation Items** | `SELECTEDMEASURE()`, `ISSELECTEDMEASURE`, calc item DAX | **Phase 2A Locked (V14-CAND-01)** |
| **`DOM-02`** | **Field Parameters** | `NAMEOF()` measure/column switching tables in visual projections | **Phase 2A Locked (V14-CAND-02)** |
| **`DOM-03`** | **Row-Level Security (RLS) / OLS** | Multi-role `tablePermission` DAX filters and cascading measures | **Phase 2A Locked (V14-CAND-03)** |
| **`DOM-04`** | **Composite & DirectQuery Models** | Mixed storage modes (`DirectQuery`, `Dual`, `Import`), remote partitions | **Clean Pass (Closed)** |
| **`DOM-05`** | **Complex DAX Dependency Chains** | Deeply nested iterator trees, multi-hop variable tables, window functions | **Clean Pass (Closed)** |
| **`DOM-06`** | **Large Enterprise Topologies** | Fact-to-fact diamond schemas, active/inactive relationship chains | **Clean Pass (Closed)** |

---

## 2. Phase 2 Governance & Architecture Milestones

- **Phase 1 Observation**: Completed across 6 domains (3 Clean Passes, 3 Candidates).
- **Phase 2A Variant Scoping**: Completed across 16 structural variants (181/181 passing tests, zero production code edits).
- **Phase 2B Semantic Specification**: Locked in [`docs/V14_SEMANTIC_REFERENCE_SPEC.md`](file:///d:/Projects/Powerbi/Power_BI_Report_Quality_&_Performance_Scanner/docs/V14_SEMANTIC_REFERENCE_SPEC.md).
- **Phase 2C Implementation**: Isolated Reference Extractors & Test Suite Complete (198/198 passing tests).
- **Phase 2D Integration**: Full Semantic Reference Index Integration & Golden Resolution Complete (206/206 passing tests, 0 regressions, all 16 structural variants resolved with 0 False Positives).

Each observed gap, FP, or FN candidate is recorded using this formal schema:

```text
CANDIDATE ID: V14-CANDIDATE-XXX
Domain: [DOM-01 .. DOM-06]
Model Reference: [Project Path / Name]
Architecture: [TMDL / TMSL / PBIR / Classic]
Observed Engine Behavior (v1.3.0): [Exact emitted finding or missed defect]
Expected Behavior: [Ideal diagnostic outcome]
Classification: [FP / FN / AMB / CAP_GAP]
Root Cause / AST Location: [Underlying DAX expression, TMDL node, or PBIR object]
Reproducibility: [Confirmed / Unreproduced]
Golden Fixture Target: [tests/golden/test_v14_...]
v1.4 Promotion Viability: [High / Medium / Low / Deferred]
```

---

## 3. Evaluated External Models & Golden Fixtures (v1.4 Phase)

| Entry | Project Name | Target Domain | Findings | TP | FP | AMB | FN | Candidate IDs Logged |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **10** | **Financial Report** (`Financial_Report.pbip`) | `DOM-05` (DAX Measures + Date Links) | **1** | **1** | **0** | **0** | **0** | None (All diagnostics TP) |
| **11** | **HR Analysis Dashboard** (`HR_Analysis_Dashboard.pbip`) | `DOM-06` (22 Visuals Layout Density) | **1** | **1** | **0** | **0** | **0** | None (All diagnostics TP) |
| **12** | **Adversarial Calc Group Fixture** (`test_calc_groups_selectedmeasure`) | `DOM-01` (Calc Groups & Deep DAX) | **2** | **1** | **1** | **0** | **0** | `V14-CAND-01` (Calc Group `SELECTEDMEASURE()`) |
| **13** | **Field Parameters Usage Fixture** (`test_field_parameters_usage`) | `DOM-02` (Field Parameters `NAMEOF()`) | **4** | **2** | **2** | **0** | **0** | `V14-CAND-02` (Field Parameter `NAMEOF()`) |
| **14** | **Row-Level Security Fixture** (`test_rls_ols_security`) | `DOM-03` (RLS Role Table Permissions) | **2** | **1** | **1** | **0** | **0** | `V14-CAND-03` (RLS `tablePermission` DAX) |
| **15** | **DirectQuery Composite Fixture** (`test_directquery_composite_storage`) | `DOM-04` (Mixed Storage Modes) | **1** | **1** | **0** | **0** | **0** | **CLEAN PASS** (No defect candidate required) |
| **16** | **10-Level Deep DAX Tree Fixture** (`test_deep_dax_dependency_tree`) | `DOM-05` (Deep Lineage & Multi-Tier Orphans) | **4** | **4** | **0** | **0** | **0** | **CLEAN PASS** (No defect candidate required) |
| **17** | **Diamond Topology & Bridge Fixture** (`test_enterprise_diamond_topology`) | `DOM-06` (Diamond Paths & Bridge Tables) | **2** | **2** | **0** | **0** | **0** | **CLEAN PASS** (No defect candidate required) |
| **18** | **Calc Group Variants Fixture** (`test_calc_group_variants`) | `DOM-01` (Precedence, `ISSELECTEDMEASURE`, Calc Item DAX) | **4** | **2** | **2** | **0** | **0** | `V14-CAND-01-VAR` (Calc Item DAX & Introspection) |
| **19** | **Field Parameter Variants Fixture** (`test_field_parameter_variants`) | `DOM-02` (Mixed Params, 4-Tuples, Slicer Only, Cascading) | **7** | **2** | **5** | **0** | **0** | `V14-CAND-02-VAR` (Field Param Cascading Lineage) |
| **20** | **RLS Structural Variants Fixture** (`test_rls_variants`) | `DOM-03` (Multi-Role, Multi-Table, Cascading Security) | **5** | **1** | **4** | **0** | **0** | `V14-CAND-03-VAR` (RLS Filter Cascading Lineage) |

---

## 4. Candidate Backlog & Detailed Observation Records

### Candidate Record: `V14-CAND-01`

```text
CANDIDATE ID: V14-CAND-01
Domain: DOM-01 (Calculation Groups & Calculation Items)
Fixture Target: tests/golden/test_calc_groups_selectedmeasure/
Contract Tests: tests/golden/test_calc_group_fixtures.py (3 tests)
Architecture: TMDL Semantic Model (calculationGroup + calculationItems + PBIR Matrix Column Selector)
Observed Engine Behavior (v1.3.0 Baseline):
  - Flags 'Raw Margin' as DAX_UNUSED_MEASURE at 95% confidence.
  - Correctly validates 5-level deep DAX dependency chain (Base Amount -> Net Amount -> Net Amount YTD -> Net Amount YTD (Ship Date) -> Growth vs Prior Ship-Date YTD %) with 0 FP.
  - Inactive USERELATIONSHIP produces 0 spurious relationship findings.
Expected Behavior:
  - 'Raw Margin' is invoked dynamically via SELECTEDMEASURE() inside the 'Margin View' calculation item when selected in matrix/slicer columns.
  - Emitting an unused measure warning on measures reachable via calculation groups represents a confirmed False Positive.
Classification: CONFIRMED FALSE POSITIVE (Capability Gap in Dynamic Measure Lineage)
Root Cause / AST Location:
  - Calculation items defer measure evaluation to runtime via SELECTEDMEASURE().
  - Static text-bracket [MeasureName] parser cannot see implicit runtime measure binding without calculation-group-aware dependency analysis.
Reproducibility: 100% REPRODUCED (Locked in test_calc_group_fixtures.py)
Status: EMPIRICALLY CONFIRMED & LOCKED
```

---

### Candidate Record: `V14-CAND-02`

```text
CANDIDATE ID: V14-CAND-02
Domain: DOM-02 (Field Parameters & NAMEOF() Dynamic Projections)
Fixture Target: tests/golden/test_field_parameters_usage/
Contract Tests: tests/golden/test_field_parameter_fixtures.py (1 test)
Architecture: TMDL Semantic Model (Calculated Table with NAMEOF('Sales'[Measure]) + PBIR Visual Projection)
Observed Engine Behavior (v1.3.0 Baseline):
  - Flags 'ParameterMeasureA' and 'ParameterMeasureB' as DAX_UNUSED_MEASURE at 95% confidence.
  - Correctly identifies 'UnusedKPI' as DAX_UNUSED_MEASURE (1 TP).
  - Correctly identifies MODEL_NO_DATE_TABLE (1 TP).
Expected Behavior:
  - Visual binds to MeasureSelector[MeasureSelector Fields] column.
  - MeasureSelector table defines dynamic lineage to 'ParameterMeasureA' and 'ParameterMeasureB' via NAMEOF().
  - Emitting unused measure warnings on measures projected through Field Parameters represents a confirmed False Positive.
Classification: CONFIRMED FALSE POSITIVE (Capability Gap in Calculated Table NAMEOF() Lineage)
Root Cause / AST Location:
  - Visual projects the Field Parameter column name (e.g. MeasureSelector[MeasureSelector Fields]).
  - Extractor / DAX graph does not trace table partition source expressions containing NAMEOF('Table'[Measure]) back to the underlying measure references.
Reproducibility: 100% REPRODUCED (Locked in test_field_parameter_fixtures.py)
Status: EMPIRICALLY CONFIRMED & LOCKED
```

---

### Candidate Record: `V14-CAND-03`

```text
CANDIDATE ID: V14-CAND-03
Domain: DOM-03 (Row-Level Security & Role Table Permissions)
Fixture Target: tests/golden/test_rls_ols_security/
Contract Tests: tests/golden/test_rls_security_fixtures.py (2 tests)
Architecture: TMDL Semantic Model (roles/RoleName.tmdl tablePermission DAX Filter + PBIR Visual)
Observed Engine Behavior (v1.3.0 Baseline):
  - Flags 'SalesRegionSecurityMeasure' as DAX_UNUSED_MEASURE at 95% confidence.
  - Correctly identifies 'UnusedKPI' as DAX_UNUSED_MEASURE (1 TP).
  - Correctly validates security table relationships without spurious model findings.
Expected Behavior:
  - Role 'RegionalManagerRole' enforces tablePermission Sales = [SalesRegionSecurityMeasure] == 1.
  - Security measure is actively consumed on the server by the Power BI Engine during role evaluation.
  - Emitting an unused measure warning on measures referenced in active RLS role expressions represents a confirmed False Positive.
Classification: CONFIRMED FALSE POSITIVE (Capability Gap in Role Definition Extraction)
Root Cause / AST Location:
  - PBIPReader parses tables/, relationships/, and pages/, but does not parse roles/ definitions in TMDL or model.bim roles.
  - Measures referenced exclusively in security filter expressions are omitted from root visual/system references.
Reproducibility: 100% REPRODUCED (Locked in test_rls_security_fixtures.py)
Status: EMPIRICALLY CONFIRMED & LOCKED
```

---

## 5. Candidate Backlog & Ranking Matrix

| Candidate ID | Domain | Summary | Frequency | Diagnostic Value | FP Risk | Testability | Status |
|---|---|---|:---:|:---:|:---:|:---:|:---:|
| **`V14-CAND-01`** | **`DOM-01`** | Calculation Group `SELECTEDMEASURE()` false positive on dynamically invoked measures | High | High | Very High | High | **REPRODUCED & LOCKED** |
| **`V14-CAND-02`** | **`DOM-02`** | Field Parameter `NAMEOF()` false positive on dynamically switched measures | High | High | Very High | High | **REPRODUCED & LOCKED** |
| **`V14-CAND-03`** | **`DOM-03`** | RLS `tablePermission` filter expression false positive on security measures | Medium | High | High | High | **REPRODUCED & LOCKED** |
