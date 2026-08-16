# PBIP Sentinel — Phase 3 Validation & Calibration Impact Report

**Milestone**: v1.2 Calibration Review  
**Date**: `2026-08-16`  
**Test Baseline**: **156/156 Tests Passing** (151 baseline regression + 5 candidate fixture contract tests)  
**Corpus Audited**: 23 PBIP Projects (1 enterprise PBIP + 22 architectural fixtures)

---

## 1. Executive Summary: Before vs. After Calibration

| Metric | Before Calibration (v1.1.0 Baseline) | After Calibration (v1.2 Phase 2) | Variance / Delta |
|---|---|---|:---:|
| **Active Production Rules** | 11 rules | 11 rules | **0 (Matrix Locked)** |
| **Total Corpus Findings** | 35 findings | 35 findings | **0 (Invariance Maintained)** |
| **Candidate Infrastructure** | `canonical/model.py` topology API | `canonical/` API + 4 golden fixture pairs | +4 Golden Test Suites |
| **Candidate Promotion Status** | `M006`/`M007` Proposed | `M006`/`M007` **DEFERRED** | Preserved in Infrastructure |
| **Observed Corpus Precision** | 100% (32 TP, 0 FP, 3 AMB) | 100% (32 TP, 0 FP, 3 AMB) | **Stable** |
| **Average Scan Latency** | 4.26 ms | 4.32 ms | +0.06 ms (Noise margin) |
| **Max Peak Memory** | 387.12 KB | 387.86 KB | +0.74 KB |
| **Pytest Suite Passing** | 151 passed | **156 passed** | **+5 Contract Tests** |

---

## 2. Finding Count Invariance Verification

Calibration intentionally refined recommendation prose, context hedging, and diagnostic contracts without modifying detection heuristics or thresholds. As verified by `tools/audit_harness.py`, finding counts per rule remain 100% invariant:

| Rule Code | Rule ID | Category | Findings Before | Findings After | Detection Logic Delta |
|---|---|---|:---:|:---:|:---:|
| `M001` | `MODEL_BIDIRECTIONAL` | Model | 4 | 4 | None (Deterministic) |
| `M002` | `MODEL_MANY_TO_MANY` | Model | 1 | 1 | None (Deterministic) |
| `M003` | `MODEL_NO_DATE_TABLE` | Model | 1 | 1 | None (Heuristic 70%) |
| `M004` | `MODEL_HIGH_CARDINALITY` | Model | 1 | 1 | None (Structural 87%) |
| `M005` | `MODEL_FACT_TO_FACT` | Model | 2 | 2 | None (Heuristic 60%) |
| `D001` | `DAX_SUSPICIOUS_PATTERN` | DAX | 4 | 4 | None (Capped ≤65%) |
| `D002` | `DAX_EXCESSIVE_CALC_COLUMNS` | DAX | 0 | 0 | None (Threshold >4) |
| `D003` | `DAX_DUPLICATE_MEASURE` | DAX | 3 | 3 | None (Normalized 90%) |
| `D004` | `DAX_UNUSED_MEASURE` | DAX | 17 | 17 | None (Transitive 95%) |
| `R001` | `REPORT_VISUAL_BLOAT` | Report | 1 | 1 | None (Threshold >15) |
| `R002` | `REPORT_SLICER_BLOAT` | Report | 1 | 1 | None (Threshold >6) |
| **TOTAL** | | | **35** | **35** | **100% Behavioral Invariance** |

---

## 3. Detailed Prose & Recommendation Diff

### 3.1 `D004` (`DAX_UNUSED_MEASURE`) — Calibrated
- **Before**: Advised checking hidden visuals, bookmarks, subscriptions, and external tools without clarifying the static PBIP boundary.
- **After**: Explicitly specifies that static analysis operates strictly on the local PBIP artifact, advising authors to confirm external XMLA, Analyze in Excel, paginated report, or thin-report consumption before deletion.
- **Confidence Rating**: Preserved at **95%**.

```diff
- "Verify whether the measure is used in hidden visuals, bookmarks, subscriptions, or external tools (Analyse in Excel, paginated reports, XMLA endpoints). If it is genuinely unused, consider removing it to reduce model complexity. Confidence is 95% — confirm before deleting."
+ "Verify whether the measure is referenced in external tools (e.g. Analyze in Excel, XMLA endpoints, paginated reports, or downstream thin reports) or bookmarks. If it is genuinely unreferenced, consider deprecating or removing it. Confidence is 95% within this PBIP artifact — confirm external consumption before deleting."
```

---

### 3.2 `M005` (`MODEL_FACT_TO_FACT`) — Calibrated
- **Before**: Asserted that direct fact-to-fact relationships are generally a modeling error.
- **After**: Clarified that while direct fact joins bypass star-schema conventions and can create filter context ambiguity, transactional or snapshot return links may legitimately connect fact tables. Recommends shared conforming dimensions or bridge tables where ambiguity exists.
- **Confidence Rating**: Preserved at **60%** (hedged heuristic).

```diff
- "Direct fact-to-fact relationships are not natively supported in Power BI star-schema modelling and are often a modelling error. Filter propagation may not behave as expected. This is a heuristic detection — review is required to confirm."
+ "Direct fact-to-fact relationships bypass standard star-schema conventions and can create filter context ambiguity or many-to-many evaluation overhead. This is a heuristic detection (60% confidence) — transactional or snapshot bridge tables may legitimately connect facts."
```

---

### 3.3 `D001` (`DAX_SUSPICIOUS_PATTERN`) — Calibrated
- **Before**: General note on performance review.
- **After**: Explicitly clarifies that static pattern matching flags structural syntax signals (e.g. `FILTER(ALL(...))` or `EARLIER()`), but only DAX Studio Server Timings can prove actual VertiPaq engine scan costs.
- **Confidence Rating**: Preserved at **≤65%** cap.

```diff
- "These patterns are worth reviewing but cannot be confirmed as performance problems without runtime analysis. Context and intent matter — not every instance of these patterns is a defect. Only Server Timings data can confirm actual performance impact."
+ "These patterns warrant review but cannot be confirmed as performance bottlenecks without runtime analysis. Context and data cardinality matter — not every flagged pattern degrades query speed. Confidence is intentionally capped at ≤65% as only DAX Studio Server Timings can confirm actual VertiPaq engine scan costs."
```

---

## 4. Candidate Rule Governance Decision (M006 & M007)

```text
CANDIDATE M006 (Isolated Table)
├── Infrastructure: ModelGraph.isolated_tables() (Verified)
├── Golden Fixtures: test_isolated_table (Positive) & test_isolated_table_negative (Negative) (Passing)
├── Real-World Corpus: Disconnected tables can represent valid What-If parameters / calculation slicers
└── Decision: DEFERRED (Preserved as query infrastructure; not added to active rule matrix)

CANDIDATE M007 (Ambiguous Path)
├── Infrastructure: ModelGraph.relationship_paths() (Verified)
├── Golden Fixtures: test_ambiguous_path (Positive) & test_ambiguous_path_negative (Negative) (Passing)
├── Safety: Cyclic graph termination (A -> B -> C -> A) verified without infinite recursion
├── Real-World Corpus: Multi-path networks in complex schemas require runtime filter context
└── Decision: DEFERRED (Preserved as query infrastructure; not added to active rule matrix)
```

---

## 5. Regression & Quality Verification

```bash
python -m pytest tests/ -v --tb=short
```

- **156 passed, 0 failed** in 0.99s.
- **118 v1.0 baseline tests** pass unchanged.
- **33 v1.1 golden/unit tests** pass unchanged.
- **5 candidate contract tests** pass cleanly.
- **0 regression failures across the entire repository.**
