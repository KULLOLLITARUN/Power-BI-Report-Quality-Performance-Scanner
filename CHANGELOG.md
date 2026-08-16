# Changelog
All notable changes to PBIP Sentinel (`pbiscan`) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - 2026-08-16

### Added
- **Real-World Audit Harness & Benchmark Suite (`tools/audit_harness.py`)**:
  - Memory profiling (`tracemalloc`) and scan latency benchmarking across PBIP models.
  - Generates machine-readable classification reports (`tools/audit_corpus_results.json`) and audit classification workbooks (`tools/AUDIT_CLASSIFICATION_SHEET.md`).
- **Formal 10-Point Candidate Rule Promotion Gate**:
  - Establishes strict criteria (positive fixture, negative fixture, cycle safety, real-world evidence, regression guard) before candidate rules are promoted.
- **Candidate Topology Golden Fixtures**:
  - `tests/golden/test_isolated_table/` (Positive) & `test_isolated_table_negative/` (Negative) for candidate `M006`.
  - `tests/golden/test_ambiguous_path/` (Positive) & `test_ambiguous_path_negative/` (Negative) for candidate `M007`.
  - Cycle-safety and path deduplication contract tests (`tests/golden/test_candidate_rules_fixtures.py`).
  - Total test suite expanded to **156 passing tests** with 100% zero-regression fidelity.

### Changed
- **Calibrated Rule Recommendations & Context Hedging**:
  - **`D004` (`DAX_UNUSED_MEASURE`)**: Explicitly defines the local PBIP static analysis boundary and recommends verifying external XMLA/Analyze in Excel/downstream thin-report consumption before deletion.
  - **`M005` (`MODEL_FACT_TO_FACT`)**: Explains filter context ambiguity risks while clarifying that transactional or return links may legitimately connect fact tables.
  - **`D001` (`DAX_SUSPICIOUS_PATTERN`)**: Clarifies that static pattern flags are structural signals whose actual VertiPaq engine scan costs require DAX Studio Server Timings confirmation.
- **Governance & Matrix Stability**:
  - Candidates `M006` and `M007` remain preserved in `canonical/` query infrastructure and are deferred from the active rule matrix.
  - Active production rule matrix locked at **11 core diagnostic rules**.

---

## [1.1.0] - 2026-08-16

### Added
- **Transitive DAX Dependency Graph (`pbiscan.canonical.dax_graph`)**:
  - `DaxDependencyGraph` data structure with `DaxNode` representation.
  - Multi-hop transitive dependency resolution (`transitive_references` and `transitive_referenced_by`).
  - Cycle-safe visual reachability tracking (`is_reachable_from_visual`).
  - Circular reference detection (`find_cycles`).
- **ModelGraph Topology Queries (`pbiscan.canonical.model`)**:
  - `connected_components()`: Detects disconnected table islands.
  - `isolated_tables()`: Identifies unlinked tables with zero relationships.
  - `relationship_paths(from_table, to_table)`: Discovers all simple paths between tables to diagnose ambiguous cross-filtering paths.
- **Finding Suppression Engine (`pbiscan.engine.suppressions`)**:
  - Declarative suppression via `pbiscan.suppressions.json`.
  - Glob, wildcard, exact, and arrow-normalized (`↔` / `<->`) location matching.
  - Suppressed findings remain visible in reports for complete audit transparency while being excluded from health score deductions.
- **Golden Test Fixtures**:
  - Added 6 new golden test suites (`test_dax_graph_multihop`, `test_dax_graph_cycle`, `test_topology_disconnected`, `test_topology_ambiguous_path`, `test_suppression_scoring`, `test_suppression_absent_file`).
  - Test suite expanded from 118 to 151 passing tests with 100% regression stability.

### Changed
- **D004 (`DAX_UNUSED_MEASURE`) Refactor**:
  - Refactored to query `report.dax_graph.is_reachable_from_visual()` instead of an inline single-hop scan.
  - Base measures supporting upstream measures bound to visuals are now transitively preserved across unlimited dependency hops.
- **Scoring Engine**:
  - `score_category()` excludes `suppressed=True` findings from deduction calculations while preserving total finding counts.
- **CLI & Studio API**:
  - CLI prints `(suppressed)` indicators in findings summaries.
  - JSON outputs and Studio API responses include `suppressed` and `suppression_reason` attributes.

---

## [1.0.0] - 2026-08-15

### Added
- Initial production release of PBIP Sentinel (`pbiscan`).
- 11 built-in deterministic and heuristic quality rules across Model, DAX, and Report categories.
- 4-Part Diagnostic Contract: `Evidence → Impact → Remediation Guidance → Confidence Score`.
- Interactive Developer Studio with Model Map architecture visualizer and DAX Inspector.
- In-browser live workbench at `pbip-sentinel.netlify.app`.
- CLI scanner with `--fail-under` CI/CD quality gate and standalone HTML reporting.
