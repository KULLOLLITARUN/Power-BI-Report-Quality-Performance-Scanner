# Changelog
All notable changes to PBIP Sentinel (`pbiscan`) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.9.0] - 2026-08-22

### Added
- **Model Context Protocol (MCP) Server integration (`pbiscan mcp`)**: Exposes PBIP Sentinel to external AI agents (Claude Desktop, Cursor, Claude Code, Antigravity) over standard stdio JSON-RPC.
  - **Static Resources**: Exposes the complete 13-rule quality and governance catalog at `pbiscan://rules` and single-rule metadata at `pbiscan://rules/{rule_id}` without LLM round-trips.
  - **7 Typed Tools**:
    - Read-only tools (`readOnlyHint: true`): `scan_model`, `diff_models`, `get_measure_lineage`, `plan_remediation`, `list_suppressions`, and `suggest_dax_rewrite`.
    - Destructive tools (`destructiveHint: true`): `apply_remediation` and `add_suppression` (triggers host approval prompt).
  - **Pre-Registered Guided Prompts**: `audit-model`, `remediate-safely`, and `inspect-dax-measure`.
  - **Optional extra**: Install via `pip install 'pbiscan[mcp]'`. Core scanner retains 100% deterministic, zero-AI, zero-telemetry guarantee.

---

## [1.8.1] - 2026-08-22

### Added
- **`mypy` static type checking gate in CI** (`pbiscan/` — no `[tool.mypy]` strict-mode config yet, so this runs under mypy's default settings, not `--strict`). Fixed the type errors it surfaced across `service.py`, `cli.py`, `server.py`, `planner.py`, `issue.py`, `pbip_reader.py`, and `field_param_extractor.py` (no `# type: ignore` suppressions used — all genuine fixes).
- **Studio UI production bundle code-splitting**: `studio-ui/vite.config.ts` now splits `vendor-xyflow`, `vendor-icons`, and `vendor-react` into separate chunks. Main application chunk dropped from 560KB to 138KB; the Rollup bundle-size warning is gone.
- **Continuous real-world corpus regression suite** (`tests/integration/test_real_world_corpus_regression.py`): scans the in-repo tracked model plus an optional local workstation corpus of real customer PBIP projects on every test run, asserting zero unhandled exceptions and (for the in-repo model) deterministic finding counts and scores. Workstation-only models `pytest.skip()` gracefully when not present, so this doesn't fail on CI or another contributor's machine.
- **Remediation patcher coverage pushed to 95%+ on the two remaining weak files**: `relationship.py` 88%→100%, `measure.py` 84%→96% (package-wide: 89%→93%). New tests cover: non-bidirectional/unmatched relationship preconditions, all `_find_target_file` fallback tiers (TMDL name-glob, `database.json`, generic `*.bim`) for both patchers, `_parse_location`/`_parse_issue_location` malformed-input fallbacks, the dax-graph-absent and semantic-references-absent regex fallback paths in `MeasurePatcher.analyze`, a non-UTF-8 file correctly skipped (not crashing) during `MeasurePatcher._find_target_file`'s glob scan, and all three comma-repair candidate branches in `_patch_bim`'s JSON measure deletion.

---

## [1.8.0] - 2026-08-22

### Added
- **Full DAX reachability parity between the browser Studio Workbench and `pbiscan scan`.** `studio-ui/src/engine/clientScanner.ts` now ports the Python engine's `DaxDependencyGraph` and Unified Semantic Reference Index in full:
  - `studio-ui/src/engine/daxGraph.ts`: a TypeScript port of `pbiscan.canonical.dax_graph` — a directed graph of `[Name]` references between measures and calculated columns, with cycle-safe multi-hop transitive reachability (`isReachableFromVisual`), replacing the previous shallow one-hop cross-measure regex scan.
  - `studio-ui/src/engine/semanticReferences.ts`: a TypeScript port of `pbiscan.canonical.references` + the `calc_group_extractor` / `field_param_extractor` / `rls_extractor` producers — Calculation Group `calculationItem` DAX (including `ISSELECTEDMEASURE()`/`SELECTEDMEASURENAME()` predicates), Field Parameter `NAMEOF()` bindings, and Row-Level Security `tablePermission` filter expressions all now activate DAX reachability roots in the browser exactly as they do server-side.
  - `clientScanner.ts`'s report/visual parsing was rewritten to use a full recursive AST walk (`extractMeasureNamesFromExprTree`, mirroring `PBIPReader._extract_measure_names_from_expr_tree`) across both legacy `report.json` and modern PBIR `page.json`/`visual.json` files, replacing a crude bracket-text regex scan that didn't understand the modern PBIR visual format at all.
  - `DAX_UNUSED_MEASURE` on the browser engine now reflects the same graph-reachability semantics as the CLI: a base measure consumed only by another measure that's itself bound to a visual is correctly treated as used, at any depth.
  - `tests/unit/test_client_scanner_parity.py`'s `KNOWN_DAX_REACHABILITY_GAP_FIXTURES` exclusion list has been removed entirely — all 34 golden fixtures now assert exact `rule_id` equality between the two engines with zero exceptions.
- Hidden-page exclusion for `REPORT_VISUAL_BLOAT`/`REPORT_SLICER_BLOAT` in the browser engine, matching the CLI's `visibility != 0` skip (previously derived from the wrong JSON fields and never actually excluded hidden pages).

---

## [1.7.3] - 2026-08-22

### Fixed
- **`pbiscan fix`/Studio "Apply Selected Patches" crashed on any project containing a file with a non-UTF-8 byte anywhere**, even a file completely unrelated to the findings being remediated: `BackupManager.get_backup_metadata()` hashes every file under the project to fingerprint the backup, and `compute_file_sha256()` decoded each one as UTF-8 text before hashing. Fixed by hashing raw bytes directly — identical output for every valid-UTF-8 file (no behavior change), no longer requires every file in the project to be valid UTF-8.
- **A single malformed-encoding table, relationships, or RLS role file crashed `pbiscan scan` for the entire project**, not just remediation: `pbip_reader.py`'s per-file TMDL parsers only caught `OSError` around their reads, so a `UnicodeDecodeError` (raised for any non-UTF-8 byte) propagated uncaught. Now caught and the single malformed file is skipped (matching existing behavior for a missing/unreadable file), while every other table/relationship/role still extracts normally. `_load_json` (used for the required model.bim/report.json/.pbir/.pbism files) had the same gap — a `UnicodeDecodeError` there now surfaces as the same clean `ParseError` every other parse failure already produces, instead of a raw traceback.
- **One patcher crashing while planning a remediation aborted the whole plan**, hiding every other otherwise-fixable finding: `RemediationPlanner.plan()` called each patcher's `analyze()`/`generate_patches()` with no exception handling. A crash on one finding (e.g. from the encoding issues above, or any other patcher-internal error) is now caught and recorded as a skipped finding with a clear reason, while every other finding in the same project still gets planned normally.
- **Studio UI: clicking "Apply Selected Patches" bounced you off the Safe Remediation tab back to the Audit Overview dashboard.** The panel's post-apply refresh reused the same `scanPath()` function used for loading a brand-new project, which always force-switches to the dashboard tab. `scanPath()` now takes an explicit `preserveTab` flag; the remediation refresh path uses it, every other caller (selecting a new project) is unaffected.

### Added
- Regression tests for all of the above, including an end-to-end test proving a scan survives one corrupted table among several others, and a planner test proving one patcher crash doesn't hide other findings' patches.

---

## [1.7.2] - 2026-08-22

### Fixed
- **`pbiscan fix` silently failed to remediate `M_HARDCODED_DATA_SOURCE` in any BIM-format project**: `DataSourcePatcher.analyze()` correctly detects a hardcoded path via the JSON-parsed (single-backslash) partition source, but `generate_patch()` re-matched the same regex against the raw, still-JSON-escaped file text (where `json.dumps` doubles every backslash), so the match always failed and the patch was silently skipped. Fixed with a dedicated JSON-escape-aware pattern in `remediation/patchers/datasource.py` whose match spans the full escape-boundary tokens, so the replacement can safely own both ends instead of leaving a stray unescaped backslash that corrupted the JSON on write.
- **Dead code with a latent `NameError`** (`pbiscan/server.py::_get_config`): referenced `load_config` without importing it; unreachable (nothing called it) but would have crashed and been silently swallowed by its own `except Exception: pass` if it ever had been. Removed.
- Added `ruff` (pyflakes + core pycodestyle errors) as a required CI lint job; fixed the ~30 real issues it surfaced across `pbiscan/` and `tests/` (unused imports, unused locals, a missing `typing.Optional` import in `cli.py` relied on only being safe because of deferred annotation evaluation).

### Added
- **Remediation patcher test coverage**: `pbiscan/remediation` package coverage raised from 82% to 88% — `engine.py` 73%→92%, `datasource.py` 70%→88%, `autodate.py` 76%→93% — by adding tests for the previously-unexercised transactional rollback paths (disk-write failure, final-verification crash/regression, audit-persistence failure) and the previously-untested BIM code paths for `DataSourcePatcher` and `AutoDatePatcher` (the existing suite only exercised their TMDL paths). The BIM `DataSourcePatcher` gap is what surfaced the fix above.

---

## [1.7.1] - 2026-08-22

### Fixed
- **Browser/CLI Scan Parity (`studio-ui/src/engine/clientScanner.ts`)**:
  - The in-browser Netlify Studio Workbench scanner had drifted from the authoritative Python `ScanService` engine, silently producing different findings and health scores than `pbiscan scan` on the same project.
  - Removed `MODEL_INACTIVE_RELATIONSHIP`, which does not exist in the Python rule catalog.
  - Implemented the 3 missing model rules to match `pbiscan.rules.model` exactly: `MODEL_FACT_TO_FACT`, `MODEL_NO_DATE_TABLE`, `MODEL_HIGH_CARDINALITY`.
  - Fixed a TMDL measure-parsing bug where the multi-line expression continuation scanner never stopped at a sibling `measure` declaration, silently concatenating every subsequent measure's DAX into the previous measure's expression — the root cause of most remaining cross-engine divergence.
  - Fixed `MODEL_AUTO_DATETIME_BLOAT` false-positives on any table with "date" in its name (e.g. `DimDate`); narrowed to `LocalDateTable_*` prefix only, per the actual rule.
  - Fixed `M_HARDCODED_DATA_SOURCE` false-positives where the naive drive-letter regex matched URL schemes (`https://...`); replaced with the exact pattern used server-side.
  - Fixed `DAX_SUSPICIOUS_PATTERN` false-positives from ad hoc "naked division" / `/0` heuristics with no server-side equivalent; replaced with the 3 config-driven regex patterns Python actually uses.
  - Fixed a pre-existing `tsc` type error (`summary.tables_count` vs. the `ScanResult` type's `table_count`) that meant `npm run build` was failing before ever reaching `vite build`.
- **Studio Server Version**: `tests/unit/test_studio_server.py` now asserts against `pbiscan.__version__` instead of a hardcoded string, preventing this kind of drift on future releases.

### Added
- **Cross-Engine Parity Test (`tests/unit/test_client_scanner_parity.py`)**: Bundles `clientScanner.ts` with esbuild and diffs its `rule_id` output against `ScanService` across all 34 golden fixtures on every test run. One documented, tracked exception remains: `DAX_UNUSED_MEASURE` counts on fixtures exercising calc groups, field parameters, RLS, or PBIR `objects.*` expressions, since the browser engine does not implement the full DAX dependency graph / Unified Semantic Reference Index — a separate, larger feature port, not a bug.

---

## [1.7.0] - 2026-08-22

### Added
- **Safe Remediation Framework (`pbiscan fix`)**: A new CLI command that plans and (optionally) applies validated, reversible fixes for a subset of findings, with `--apply`, `--interactive`, `--patch-id`, `--rule`, and `--backup/--no-backup` controls.
  - Patchers for 4 rules: `MODEL_BIDIRECTIONAL` (relationship direction), `DAX_UNUSED_MEASURE` (dependency-safe removal), `M_HARDCODED_DATA_SOURCE` (parameterization), and `MODEL_AUTO_DATETIME_BLOAT` (auto date-table removal).
  - Timestamped backup directories before any on-disk mutation, with a validation pass and scan-fingerprint checks to prevent applying a stale plan against a since-modified project.
  - Persistent, transactional remediation audit store with formalized manifest schemas.
  - Interactive review UX for selectively approving/rejecting individual patches, plus deterministic JSON/markdown export of the remediation plan.
  - PR-ready markdown proposals and a `--fail-on-remediation-available` CI governance gate for a zero-mutation "flag it, don't touch it" pipeline mode.
- **Studio Remediation Panel**: Interactive before/after diff previews, one-click safe-patch application, and an audit log view in the web Studio.

---

## [1.6.0] - 2026-08-17

### Added
- **CI/CD Governance Drift Workflow**: A GitHub Actions workflow (`pbiscan-drift.yml`) that runs `pbiscan diff` between the base and head of a PR to flag score regressions automatically.
- **CI/CD Governance Documentation** (`docs/ci_cd_governance.md`) describing recommended quality-gate policies for teams adopting `pbiscan` in a merge pipeline.

---

## [1.5.0] - 2026-08-17

### Added
- **Historical Scan Diff Engine (`pbiscan diff`)**: Compares a baseline scan against a current scan and reports `NEW` / `RESOLVED` / `PERSISTENT` / `MODIFIED` finding transitions, an overall score-drift summary, and per-category deltas.
  - Quality-gate flags: `--fail-on-regression`, `--max-score-drop`, `--fail-on-new <severity>`, `--fail-on-category-regression <category>`.
  - `console`, `json`, and `markdown` (PR-comment-ready) output formats.
- **Studio Compare UI**: A dedicated view for exploring diff results interactively in the web Studio.
- **CI/CD Integration Suite**: Native SARIF v2.1.0 and JUnit XML renderers, a pre-commit hook (`.pre-commit-hooks.yaml`), and a reusable GitHub Action (`action.yml`).
- **Interactive Studio Web Frontend**: DAX DAG explorer with zoom/pan, model topology and provenance visualizers, export dropdown (HTML/SARIF/JUnit/JSON), and one-click suppressions.
- **`M_HARDCODED_DATA_SOURCE` and `MODEL_AUTO_DATETIME_BLOAT` Rules**: Bringing the active rule catalog to 13 rules, validated against the 94-finding real-world corpus.
- **Mobile Responsiveness**: Hamburger navigation drawer and responsive layout for the Studio UI.

### Changed
- **Canonical `ScanService` Consolidation**: All CLI, Studio API, and pipeline entry points now route through a single `ScanService.execute_scan()` implementation, removing several parallel ad hoc scan code paths and enforcing an explicit Demo Mode distinction.
- **Release Hardening**: Expanded release-hardening test suite (262 passing tests, 94/94 corpus findings verified) covering the consolidated scan pipeline.

---

## [1.4.0] - 2026-08-16

### Added
- **Semantic Reference Index (Phase 2 series)**: Unified tracking of measure usage across PBIR visuals, Calculation Groups (`SELECTEDMEASURE`), Field Parameters (`NAMEOF`), and Row-Level Security filter expressions, closing several classes of `DAX_UNUSED_MEASURE` false positives that a visual-only reference scan would miss.
- **Golden Fixture Coverage for Structural Variants**: Calculation groups, field parameters, RLS, DirectQuery/composite models, deep and cyclic DAX dependency trees, and enterprise diamond topologies.
- **Adversarial Extraction & CLI Resilience Tests**: 10-surface adversarial extraction coverage and edge-case CLI hardening tests.

### Changed
- **Release Hardening**: Test suite expanded to 213 passing tests as part of the Phase 3 hardening pass ahead of the v1.4.0 tag.

---

## [1.3.0] - 2026-08-16

### Added
- **Recursive Visual AST Expression Harvesting (`PBIPReader`)**:
  - Implemented `_extract_measure_names_from_expr_tree()` to recursively traverse nested PBIR and legacy report visual property trees.
  - Full automatic coverage across all modern visual property expression surfaces:
    - Card visual reference labels (`objects.referenceLabel[].properties.value.expr.Measure`)
    - Card reference details (`objects.referenceLabelDetail[].properties.detailValue.expr.Measure`)
    - Dynamic DAX titles (`objects.title[].properties.text.expr.Measure`)
    - Dynamic subtitles (`objects.subTitle[].properties.text.expr.Measure`)
    - Conditional color formatting (`objects.*[].properties.*.solid.color.expr.Measure`)
    - Dynamic Axis Min/Max bounds (`objects.valueAxis[].properties.max.expr.Measure`)
    - Visual header tooltips & filters (`visualContainerObjects` & `filters`).
- **Golden Contract Test Suite & Dedicated Fixture**:
  - Added `tests/golden/test_pbir_objects_references/` and `tests/golden/test_pbir_objects_fixtures.py` validating that measures bound exclusively in `objects` expressions are recognized as active references while preserving accurate detection for genuinely unused measures.
  - Test suite expanded to **158 passing tests** with 100% regression fidelity.

### Changed
- **Empirical Re-Audit Across Real-World PBIP Models**:
  - Eliminated all **34 observed false positives** across 4 independent external PBIP projects while preserving **73 true positives**.
  - Average scan latency increased from 4.32 ms to 26.79 ms due to recursive PBIR expression traversal, remaining well within the sub-50ms target. Peak memory increased by only 0.41 KB (387.86 KB $\to$ 388.27 KB).
  - All 10 non-D004 production diagnostic rules remain 100% behaviorally invariant.

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
