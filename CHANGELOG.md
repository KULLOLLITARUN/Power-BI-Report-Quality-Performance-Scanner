# Changelog
All notable changes to PBIP Sentinel (`pbiscan`) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed
- **Studio redesign.** One indigo accent with orange only on problems, light and dark themes from a single token set, and Archivo, IBM Plex Sans and IBM Plex Mono (mono only for rule ids and code). Buttons are primary (filled), secondary (outlined, 3:1 border), quiet or danger (red outline). Severity is shown by shape as well as colour. The desktop shell has a rail with a project card and per-view counts; phones get a bottom tab bar and an "All views" menu grid. Every screen (Overview, Model, Measures, Report pages, Fixes, Compare scans, Agent and MCP, and the landing page) follows the new layouts. The 3D scenes are unchanged and read the new tokens.
- **Findings are grouped by rule** on the Overview, so thirteen hardcoded-path findings read as one row with its rule id, the lowest confidence in the group and a "Fix ready" or "Manual" chip. Selecting a group highlights every table it touches; "Suppress" on a group asks once, saves each finding and rescans once.
- **Fixes are grouped into one card per fix** (one rule, one diff per file) with a side panel showing the projected score, findings resolved, files touched and the backup and rollback guarantees.

### Added
- **New rule `REPORT_MISSING_MEASURE` (R003, Medium, 90%).** Flags a visual or page filter that uses a measure neither the model nor a report-level measure defines, which usually shows as a broken visual and was invisible to every other rule. It matches by name (case-insensitively), so a measure that exists on another table is not flagged, and it stays silent for thin reports with no local model and when a project file could not be read (the scan then says so). The browser engine has the same rule. It finds `Total Sugars Measure` on Page 1 of the in-repo sample project, which now scans at 52.8 with 18 findings (it was 54.1 with 17); that chart is hidden, and the evidence says so. Checked in Power BI Desktop: revealing the hidden chart shows "Something's wrong with one or more fields". The rule has no automatic fix.
- **A step-by-step guide to connect pbiscan to Claude** on the Agent & MCP screen, for Claude Desktop, Claude Code (command line and VS Code) and Cursor: install, a practice copy, the exact config to paste with a copy button, how to check it connected, first prompts, how to let it change files safely, and troubleshooting. It also shows on the hosted browser-only site. With the local engine connected it fills in the exact Python that runs pbiscan. The config text is built in `lib/mcpConfig.ts` and unit tested.
- **Richer 3D scenes in Studio.** The model map now shows comet trails behind the dots that travel along relationships, a pulsing ring and glow under every table that has findings (coloured by its worst severity), and soft studio lighting with a faint clear-coat sheen on the boxes. The 3D measure dependency graph gets the same lighting, a halo on unused measures and a selected node, and comets that run along the selected chain from what a measure uses up to the measure that uses it. With reduced motion on, rings and glows stay still and the trails are off. The effects live in `studio-ui/src/lib/fx.ts`; none of them can be picked with the mouse.
- **Only one `pbiscan fix` applies to a project at a time.** A second apply on the same project (another terminal, Studio, an MCP client) is refused with a clear message instead of interleaving writes with the first; it changes nothing and takes no backup. The lock is a `<project>.pbiscan.lock` file beside the project folder, replaced if it is over an hour old.
- **Quick test tier:** `python -m pytest -m "not slow and not parity"` (about 25 s) skips the randomised hypothesis tests, the MCP end-to-end tests and the Python-vs-TypeScript parity tests. Plain `pytest` and CI still run everything.
- **Property-based tests for the patchers and DAX scanners** (`tests/unit/test_patcher_properties.py`, hypothesis). They generate random models and check each patch against an independent oracle: a measure, relationship or data-source patch changes exactly its target; backups restore byte for byte and a failed restore changes nothing; nested `CALCULATE` detection agrees with the generated call tree. Each property was confirmed to fail against the code from before the corresponding fix.
- **Visual layout data for Studio**: every visual now carries its canvas position and size plus `table_refs` (the model tables its query reads), and every page its canvas width and height. `table_refs` is display-only; no rule reads it, and `measure_refs`/`fields_used` are unchanged. The browser scanner mirrors it, and the parity test compares page layouts across both engines.
- **Unused-measure evidence in Studio**: for every measure, and in the detail of each `DAX_UNUSED_MEASURE` finding, Studio lists what was checked and what was found: report visuals, page and report filters and bookmarks, report-level measures, calculation groups, field parameters, RLS roles, and other measures' DAX (marking referrers that are themselves unused). It reads `semantic_references` and `dax_graph` from the scan; rule logic is unchanged. A contract test replays every `DAX_UNUSED_MEASURE` decision from that exported data.
- **Browser-only scans now include `semantic_references` and `dax_graph`**, so the evidence above and measure dependencies also work without the local engine. A parity test compares both engines' references and graphs over every golden fixture.
- **Studio unit tests** (Vitest) for the model helpers, measure evidence, DAX graph serialization and map layout, run in CI.

### Fixed
- **Hidden PBIR visuals were never recognised as hidden.** The PBIR parser (both engines) read a visual's hidden state from `"hidden"`, but PBIR writes `"isHidden": true`, so Studio never showed those visuals as hidden. Both spellings are read now.
- **`pbiscan fix` crashed on Windows** with `UnicodeEncodeError` when its output went to a pipe or an older console (cp1252), because the plan view draws boxes. `fix` and `diff` now print through one helper that replaces unprintable characters with `?` instead of failing.
- **DAX rules read code, not text.** D001 (`DAX_SUSPICIOUS_PATTERN`) no longer fires on commented-out DAX or on pattern text inside string literals, and "Nested CALCULATE()" now means a `CALCULATE` inside another `CALCULATE`'s arguments (a parenthesis-depth check), so `CALCULATE(a) + CALCULATE(b)` is no longer flagged. D003 (`DAX_DUPLICATE_MEASURE`) keeps `//` and `--` inside string literals, so measures that differ only by a URL are no longer reported as duplicates, and skips constant expressions of 5 characters or fewer. The browser scanner mirrors all of it; new golden fixtures cover a true positive and a critical negative.
- **Date-table detection matches whole words.** `MODEL_NO_DATE_TABLE` treated any table whose name merely contained `date` or `time` (`Sales Updates`, `Candidates`, `Timesheet`) as a date dimension and stayed silent on models that have none. Python and the browser scanner now share one word-based check (`Dim Date`, `DimDate`, `dim_date`, `Calendar` and Power BI's auto date tables still match), and the model builder's name fallback uses it too, so `Datasets` is no longer marked as a Date Table.
- Duplicate-measure detection no longer calls MD5 as a security hash, which fails on FIPS-mode Python builds.
- **`pbiscan fix` could edit the wrong object.** Four patcher bugs, each reproduced before fixing:
  - Removing an unused measure from `model.bim` deleted the first object anywhere in the file with that name, so a same-named column in an earlier table was removed instead. It now removes only that table's measure, and emits a patch only if the patched file parses to the original model minus that one measure.
  - Removing an unused measure from TMDL also removed the hierarchy and table annotation that followed it, and left all but the last `///` doc line behind. The block now ends at the first line not indented deeper than the declaration.
  - Switching a bidirectional relationship to single direction matched by substring (`Sales.Date` also matched `ReturnSales.Date`) in TMDL, and by a 13-line window in `model.bim`, so it could flip a neighbouring relationship instead. Endpoints now match exactly, and a `model.bim` edit is accepted only if it changes that one relationship.
  - Parameterising a hardcoded file path in `model.bim` ignored which table the finding was for and rewrote the first table with a local path.
- **Patches that would leave a relationship pointing at a removed table are rejected.** Validation and the final post-apply scan roll back any patch whose result has a relationship naming a table that no longer exists; a patch may drop a relationship only together with a table the same plan removes.
- **Auto Date/Time cleanup removes everything that wires the tables in, so it now works on real models.** Power BI connects each `LocalDateTable_*` to its fact table with a relationship, a `variation` block on the date column and the model switch `__PBI_TimeIntelligenceEnabled`. The cleanup now removes the tables, those relationships (TMDL and `model.bim`), the date columns' variations, and turns the switch off so Power BI does not rebuild them. Verified on the sample project in `pbip_project/` (five files change, 13 tables and 8 relationships remain, the finding resolves). The cleaned sample project opens and renders in Power BI Desktop. The emptied `LocalDateTable_*` and `DateTableTemplate_*` files are now deleted instead of left at zero bytes. A relationship into an auto table that is not the auto-generated shape (fact table into its `Date` column) still blocks the cleanup.
- **The hardcoded-path fix now defines the `DataFolderPath` parameter it points at.** The patch rewrites paths to `DataFolderPath & "\file"`, but nothing created that parameter, so the patched model failed on load. In a TMDL project the fix now also writes the parameter into `expressions.tmdl` (created, or appended to) and adds `ref expression DataFolderPath` to `model.tmdl`. The parameter's value is the folder the paths pointed at, so every source resolves to the same file as before. This needs all hardcoded paths to share one folder; otherwise, and for `model.bim` without the parameter, no patch is planned and the finding is still reported. A patch can now create a file (`Patch.creates_file`), and a patch shared by several findings is planned once. Verified on the sample project in Power BI Desktop: the parameter is listed, the rewritten sources evaluate and the report visuals are unchanged.
- **`]]` in measure names is read correctly by the calculation-group, RLS and `NAMEOF` extractors** (Python and browser scanner). `[Margin [%]]]` was read as `Margin [%`, so a measure used only there looked unused and `pbiscan fix` would offer to delete it.
- **Patches to same-named files in different folders no longer collide.** `apply_patches_to_dir` matched files by name only, so two patched files sharing a name were merged and the apply failed. Each patch now resolves to its own file by path.
- **`DAX_UNUSED_MEASURE` no longer flags measures used only inside the model, so `pbiscan fix` cannot delete them.** Each case below was reproduced: the measure was reported unused and `fix` offered to delete it.
  - A measure named only in a calculated table's expression (or any partition source).
  - A measure named only in another measure's dynamic format-string, KPI or detail-rows DAX in `model.bim`. The new `model_expression` reference type covers these, and Studio lists them under "Calculated tables and measure properties".
  - A measure named only inside the browser engine's TMDL measure body (`formatStringDefinition = ...`), which that engine dropped as metadata.
  - A measure whose name contains `]`, written `[Margin [%]]]` in DAX; the bracket matcher stopped at the first `]`.
- **`pbiscan fix` now searches the whole model before deleting a measure.** For a `model.bim` project the file being patched is the whole model, and it was skipped by the safety scan; it is now searched too, minus the measure's own definition.
- **`pbiscan fix` refuses to delete a measure that a perspective, translation or Q&A (linguistic) metadata names.** These name a measure by plain name, with no `[brackets]`, so the existing scan never saw them: in TMDL and in `model.bim` Q&A metadata the measure would have been deleted and the reference left pointing at nothing (a `model.bim` perspective or translation was refused only by accident). The refusal is now explicit, with its own precondition, `zero_model_metadata_references`. Matching is by whole word, so it can over-refuse but never allow a deletion.
- **A `]` inside a bracketed name no longer starts a comment.** In `T[a]]--b]` (column `a]--b`) the DAX scanner ended the name at the first `]` and treated `--b] ...` as a comment, so D001 could miss a nested `CALCULATE` after such a name. `]]` is now read as an escape, like `""` and `''`, in both engines. Found by the new property-based tests.
- **`MODEL_FACT_TO_FACT` no longer reads `ref` inside a longer word.** Fact tables named `Refunds` or `Preferences` were taken for reference/dimension tables and the finding was hidden. Dimension names now match whole words (`DimCustomer`, `Customer Lookup`, `Product Reference`, `Bridge`) in both engines.
- **TMDL measure and calculated-column parsing:** a bare `isHidden` line is read as the property it is (the measure's `hidden` flag) instead of being appended to its DAX, and a `variation` block on a calculated date column is no longer folded into its expression. Both engines.
- **Backups and rollback are safer.**
  - A backup made in the same second as an earlier one overwrote it, destroying the earlier apply's only restore point. Backup folders now get a unique name and are never replaced.
  - A restore deleted the project folder before copying the backup in, so a failure partway (a file locked by Power BI Desktop or a sync client, a full disk) left it half deleted. The restored copy is now built beside the project and swapped in by rename, so a failed restore changes nothing.
  - A failed write with `--no-backup`, or a rollback that could not run, was still recorded as `ROLLED_BACK` with `rollback_executed: true`. The audit record now says `ROLLBACK_FAILED` and why, shows where the original files are, and Studio's history marks it in red. An unverifiable restore also no longer aborts `apply` without writing a record.

### Changed
- **Studio redesign.** New look (navy ink, cobalt accent, IBM Plex and Archivo, both themes), a mobile layout with a bottom tab bar and bottom sheets, and a 3D model map built with three.js: tables are blocks sized by column count and coloured by role, relationships are arcs with dots showing filter direction, and tables with findings carry a severity marker. Report pages can float above the model with a thread from each visual to the tables it reads. Fonts are bundled instead of loaded from Google Fonts.
- **Studio fixes**: `pbiscan studio <path>` scans the path on first load (it used to show a "needs the local engine" error); dropped folders with more than 100 entries are read completely; picking a folder with no project files shows an error instead of nothing; the Fixes tab no longer shows simulated patches in browser-only mode.
- **Faster model map on large models**: a 300-table, 600-relationship model now lays out in about 100 ms (it took about 470 ms). Models of 800+ tables use a Barnes-Hut repulsion step. Layouts stay deterministic. Maps with more than 28 tables keep at most 16 labels visible at rest (the most connected fact tables, then date tables); the rest show on hover or focus.
- **HTML export (`pbiscan scan --format html`) matches Studio**: same palette in light and dark, the same type stacks and severity shapes, a score ledger with per-area bars, findings ordered most severe first, suppressed findings listed separately, and scan warnings shown. It is now a static document with no JavaScript, so every finding is visible as rendered and when printed.
- **Studio ships WOFF2 fonts only** (364 KB smaller bundle and wheel); the system font fallbacks are unchanged.
- **Studio is type-checked in TypeScript strict mode**, and its UI code no longer uses `any`.
- **Drag and drop works visibly on every screen**: with a project open, dragging a folder over Studio now shows a full-window drop target (dropping already worked, but only the landing page showed it). The landing page says the folder can be dropped anywhere on the page.

### Fixed
- Studio's phone-only "More" menu no longer appears as unstyled buttons at the bottom of desktop pages.

## [1.11.1] - 2026-08-22

### Changed
- **Studio UI's Agent/MCP tab is now Groq-only, by explicit decision**: removed the multi-host client configuration material (Claude Desktop, Cursor, Claude Code CLI, VS Code Cline/Roo-Code snippets and the `/api/mcp/config-snippets` endpoint that generated them). The tab now covers only the actual pbiscan surface: environment status, the live tool safety matrix, the rule catalog explorer, and the interactive Groq DAX rewrite tester.
- **Fixed a display bug in the Groq DAX rewrite tester** (`AgentIntegrationPanel.tsx`): it read `daxOutput.recommendation`/`daxOutput.explanation`, which don't exist on the tool's actual response shape — so it always showed the static advisory text instead of the real AI-generated rewrite, and never showed the explanation at all. Now reads `suggested_rewrite`/`rewrite_explanation` when `ai_generated` is true, falling back to the static `recommendation` only when Groq wasn't used.

### Security
- **`/api/mcp/status` no longer exposes any fragment of the real `GROQ_API_KEY`.** It previously returned a `groq_masked_key` field built from the key's first 6 and last 4 characters — real key material served over a local HTTP endpoint. The endpoint now reports only a `groq_configured` boolean.

## [1.11.0] - 2026-08-22

### Added
- **`suggest_dax_rewrite` MCP tool now optionally calls Groq for a real, expression-specific DAX rewrite** (`pbiscan/mcp/groq_client.py`), in addition to its existing static, manually-reviewed advisory text.
  - **BYO API key, opt-in only**: activated purely by the presence of a `GROQ_API_KEY` environment variable on the machine running `pbiscan mcp` — the tool makes zero network calls, and every other tool in the server remains fully deterministic and AI-free, when it's unset. No key is bundled, stored, or required to install/use `pbiscan[mcp]`.
  - **Zero new dependencies**: the client uses only Python's standard library (`urllib`) — not even the `mcp` extra needs a new package for this.
  - **`.env` file support**: `pbiscan mcp` auto-loads `GROQ_API_KEY`/`GROQ_MODEL` from a `.env` file in the current working directory if present (hand-rolled, no `python-dotenv` dependency), without ever overriding a real environment variable that's already set. `.env.example` is the tracked template; `.env` itself is gitignored.
  - **Fails open to the deterministic fallback, never hard**: any network error, timeout, non-200 response, or malformed reply from Groq is caught and logged, and the tool returns the existing static recommendation exactly as before (`ai_generated: false`). A model can be selected via `GROQ_MODEL` (default `openai/gpt-oss-120b`, verified live against Groq's current model catalog — Groq's hosted-model lineup changes over time, so this may need updating again later).
  - Still strictly advisory: the tool remains `readOnlyHint: true` and has no write path — a suggested rewrite is text for a human (or the calling agent) to review, never something `pbiscan` applies itself.
  - Live-tested end-to-end against the real Groq API during development (not just mocked) to confirm the request format, headers, and model name actually work — this caught and fixed two real issues before release: api.groq.com's Cloudflare layer rejecting Python's default `urllib` User-Agent as a bot fingerprint (HTTP 403), and an initially-assumed default model name that no longer exists in Groq's current catalog (HTTP 404).
  - `tests/conftest.py` disables the `.env` auto-loader for the entire test session (`PBISCAN_DISABLE_DOTENV=1`), including subprocess-spawned E2E tests — a real local `.env` file (e.g. for manual testing) must never make the test suite non-deterministic or network-dependent.

---

## [1.10.0] - 2026-08-22

### Added
- **Studio UI "Agent / MCP" tab**: a new panel in the local Studio Workbench (`pbiscan studio`) for connecting an AI agent host to `pbiscan mcp` — no AI or `mcp` package required to render it.
  - **Environment check**: reports whether the optional `mcp` extra is installed, with a one-click `pip install 'pbiscan[mcp]'` copy button when it isn't.
  - **Copyable client configuration** for Claude Desktop, Cursor, Claude Code (CLI), and VS Code Cline/Roo-Code, generated from the actual `pbiscan mcp` command rather than hand-typed examples.
  - **Live tool safety matrix**: when `mcp` is installed, introspects a real, running server instance (`create_server().list_tools()`) for each tool's actual protocol-level `readOnlyHint`/`destructiveHint` — not a static description that could silently drift from the real registration. Falls back to a clearly-labeled static list (sourced from the same constants the real server registers from) when `mcp` isn't installed.
  - **Rule catalog explorer**: browses the same 13-rule catalog the MCP `pbiscan://rules` resource serves to an agent.
- **`pbiscan/mcp/server.py`**: extracted `READ_ONLY_TOOL_NAMES`/`DESTRUCTIVE_TOOL_NAMES` as module-level constants (the single source of truth for tool classification, usable without the `mcp` package installed) and added a build-time assertion in `create_server()` that fails loudly if a tool is ever registered without also being classified in one of these two lists — closing the exact drift class that caused the `v1.9.0` annotations gap.
- 4 new `/api/mcp/*` Studio endpoints (`status`, `tools`, `rules`, `config-snippets`) and test coverage, including a regression guard asserting the Studio API's tool list can never disagree with the real MCP server's registered tools.

---

## [1.9.1] - 2026-08-22

### Fixed
- **MCP dependency ceiling pinned to `mcp>=1.2.0,<2.0.0`**: Prevents installation of breaking `mcp 2.0.0` which renamed and restructured `FastMCP`.
- **Enforced protocol-level `ToolAnnotations`**: Added explicit `ToolAnnotations(readOnlyHint=True, destructiveHint=False)` on read-only tools and `ToolAnnotations(readOnlyHint=False, destructiveHint=True)` on destructive tools (`apply_remediation`, `add_suppression`), ensuring MCP host confirmation gates trigger natively.
- **Dev dependency inclusion & integration testing**: Added `mcp` to dev dependencies and added `test_tool_annotations_protocol_guarantees` in `tests/unit/test_mcp_server.py` to assert runtime tool annotation integrity directly against a running FastMCP server instance.

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
