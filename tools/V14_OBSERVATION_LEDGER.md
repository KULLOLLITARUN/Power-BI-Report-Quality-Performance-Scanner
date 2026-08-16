# PBIP Sentinel — v1.4 Observation Ledger & Candidate Backlog

**Baseline Control**: `PBIP Sentinel v1.3.0` (Tag `v1.3.0`, Commit `577d5a8`, 162/162 Passing Tests)  
**Governance Protocol**: Zero-mutation data collection across targeted architectural categories.  
**Classification Taxonomy**: `TP` (True Positive) | `FP` (False Positive) | `FN` (False Negative) | `AMB` (Ambiguous) | `CAP_GAP` (Capability Gap).

---

## 1. Targeted Architectural Domains for v1.4

| Domain Code | Architectural Surface | Description / Potential Blind Spot | Status |
|:---:|---|---|:---:|
| **`DOM-01`** | **Calculation Groups & Calculation Items** | `SELECTEDMEASURE()`, `SELECTEDMEASUREFORMATSTRING()`, dynamic measure replacement | Queued |
| **`DOM-02`** | **Field Parameters** | Dynamic dimension & measure switching tables in PBIR visual fields | Queued |
| **`DOM-03`** | **Row-Level Security (RLS) / OLS** | Table filter DAX expressions & role definitions | Queued |
| **`DOM-04`** | **Composite & DirectQuery Models** | Mixed storage modes (`DirectQuery`, `Dual`, `Import`), remote partitions | Queued |
| **`DOM-05`** | **Complex DAX Dependency Chains** | Deeply nested iterator trees, multi-hop variable tables, window functions | Queued |
| **`DOM-06`** | **Large Enterprise Topologies** | Fact-to-fact diamond schemas, active/inactive relationship chains | Queued |

---

## 2. v1.4 Candidate Observation Record Template

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

---

## 4. Candidate Backlog & Detailed Observation Records

### Candidate Record: `V14-CAND-01`

```text
CANDIDATE ID: V14-CAND-01
Domain: DOM-01 (Calculation Groups & Calculation Items)
Fixture Target: tests/golden/test_calc_groups_selectedmeasure/
Contract Tests: tests/golden/test_calc_group_fixtures.py
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
v1.4 Promotion Viability: HIGH
```

---

## 5. Candidate Backlog & Ranking Matrix

| Candidate ID | Domain | Summary | Frequency | Diagnostic Value | FP Risk | Testability | Ranking Score | Status |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **`V14-CAND-01`** | **`DOM-01`** | Calculation Group `SELECTEDMEASURE()` false positive on dynamically invoked measures | High | High | Very High | High | **9.2 / 10** | **REPRODUCED & LOCKED** |
