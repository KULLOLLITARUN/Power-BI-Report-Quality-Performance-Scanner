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

## 3. Evaluated External Models (v1.4 Phase)

| Entry | Project Name | Target Domain | Findings | TP | FP | AMB | FN | Candidate IDs Logged |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **10** | **Financial Report** (`Financial_Report.pbip`) | `DOM-05` (DAX Measures + Date Links) | **1** | **1** | **0** | **0** | **0** | None (All diagnostics TP) |
| **11** | **HR Analysis Dashboard** (`HR_Analysis_Dashboard.pbip`) | `DOM-06` (22 Visuals Layout Density) | **1** | **1** | **0** | **0** | **0** | None (All diagnostics TP) |

---

## 4. Candidate Backlog & Ranking Matrix

| Candidate ID | Domain | Summary | Frequency | Diagnostic Value | FP Risk | Testability | Ranking Score | Status |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| *Awaiting candidates...* | | | | | | | | |
