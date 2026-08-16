# Changelog
All notable changes to PBIP Sentinel (`pbiscan`) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
