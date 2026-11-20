# pbiscan

**Static analysis for Power BI projects (`.pbip`).** pbiscan reads your semantic model, DAX and report files, and reports the problems that usually cause slow reports, broken refreshes and dead weight, before they reach production. It can also fix some of them safely.

[![CI](https://img.shields.io/github/actions/workflow/status/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner/ci.yml?branch=main&label=CI)](https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](pyproject.toml)

**Try it without installing anything:**
[in-browser Studio](https://pbip-sentinel.netlify.app/) (drop a `.pbip` folder on it; scanning happens in your browser and nothing is uploaded) ·
[hosted Studio](https://power-bi-report-quality-performance.onrender.com/) (the free host can take a minute to wake up)

## What it does

- **Scans** a `.pbip` project against 14 rules for the model, DAX and report layout, and gives a health score from 0 to 100.
- **Gates CI.** Fail a build when the score drops or a severity appears. Output as HTML, JSON, SARIF (GitHub Code Scanning) or JUnit XML.
- **Fixes** four kinds of finding with a reviewable plan, a sandbox check and a backup (`pbiscan fix`).
- **Compares** two scans and reports what is new, resolved or worse (`pbiscan diff`).
- **Opens a local Studio** with a findings view, a measure dependency graph, a model map and before/after diffs (`pbiscan studio`).
- **Connects to AI agents** such as Claude and Cursor through an MCP server (`pbiscan mcp`).

pbiscan works on the files in the project folder. It never connects to Power BI or to a dataset, and it runs on Windows, macOS and Linux.

## Install

pbiscan is not on PyPI yet, so install it from source (Python 3.10 or newer):

```bash
git clone https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner.git
cd Power-BI-Report-Quality-Performance-Scanner
pip install -e ".[studio,mcp]"
```

The base install is enough for `scan`, `fix` and `diff`. The `studio` extra adds the local web app, and the `mcp` extra adds the agent server.

## Quick start

```bash
pbiscan scan path/to/Report.pbip                      # score and findings in the terminal
pbiscan scan path/to/Report.pbip --format html --out report.html
pbiscan studio path/to/Report.pbip                    # local web app
```

You can pass either the `.pbip` file or the project folder.

## Rules

| Rule | Severity | Confidence | What it flags |
|:---|:---:|:---:|:---|
| `MODEL_BIDIRECTIONAL` | Warning | 100% | Relationships that filter in both directions, which can make filter paths ambiguous. |
| `MODEL_MANY_TO_MANY` | Warning | 100% | Many-to-many relationships. |
| `MODEL_NO_DATE_TABLE` | Warning | 70% | No table is marked as a date table, and none is named like a calendar. |
| `MODEL_HIGH_CARDINALITY` | Advisory | 87% | Columns likely to have very many distinct values, which inflate memory. |
| `MODEL_FACT_TO_FACT` | Advisory | 60% | A many-to-many or one-to-one link between two tables that both hold measures. |
| `M_HARDCODED_DATA_SOURCE` | High | 95% | File paths such as `C:\Users\...` in Power Query, which break scheduled refresh. |
| `MODEL_AUTO_DATETIME_BLOAT` | Medium | 100% | Hidden `LocalDateTable_*` tables created by Auto Date/Time. |
| `DAX_SUSPICIOUS_PATTERN` | Advisory | 65% | Patterns worth a second look, such as `FILTER(ALL(...))` and nested `CALCULATE`. |
| `DAX_EXCESSIVE_CALC_COLUMNS` | Medium | 100% | Tables with many calculated columns. |
| `DAX_DUPLICATE_MEASURE` | Medium | 90% | Measures with the same formula. |
| `DAX_UNUSED_MEASURE` | Advisory | 95% | Measures that no visual, filter, bookmark, calculation group, field parameter, role or other measure uses. |
| `REPORT_VISUAL_BLOAT` | Medium | 100% | Pages with too many visuals. |
| `REPORT_SLICER_BLOAT` | Medium | 100% | Pages with too many slicers. |
| `REPORT_MISSING_MEASURE` | Medium | 90% | A visual or page filter that uses a measure nothing defines. |

Rules below 100% confidence are heuristics. They can flag a design that is intentional. Suppress those (see [Suppressions](#suppressions)) rather than ignoring the report.

## Use it in CI

```bash
# Fail the build if the score is under 85 or any High finding exists
pbiscan scan path/to/Report.pbip --format sarif --out results.sarif --fail-under 85 --fail-on HIGH
```

GitHub Actions, with results shown in Code Scanning:

```yaml
name: Power BI quality gate
on: [push, pull_request]

jobs:
  pbiscan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install "git+https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner.git"
      - run: pbiscan scan path/to/Report.pbip --format sarif --out results.sarif --fail-under 80
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: results.sarif
```

For Azure DevOps or Jenkins, use `--format junit --out test-results.xml` and publish the file as test results.

## Fix findings: `pbiscan fix`

```bash
pbiscan fix path/to/Report.pbip                       # plan only, nothing is written
pbiscan fix path/to/Report.pbip --interactive --apply # review each patch, then apply
pbiscan fix path/to/Report.pbip --fail-on-remediation-available --quiet   # CI: fail if a safe fix is waiting
```

It can fix `MODEL_BIDIRECTIONAL`, `DAX_UNUSED_MEASURE`, `M_HARDCODED_DATA_SOURCE` and `MODEL_AUTO_DATETIME_BLOAT`.

Every plan is applied to a copy first and rescanned. A patch is rejected if any file would no longer parse. Applying makes a timestamped backup, writes all files or none, and restores the backup if the final rescan fails. A plan exits with code 3 when there are patches to review.

Before it deletes an unused measure, pbiscan checks the model files again for any other mention of it, including perspectives and translations. If a file cannot be read, it refuses to delete.

## Compare two scans: `pbiscan diff`

```bash
pbiscan scan path/to/Report.pbip --format json --out baseline.json
# ... change the report ...
pbiscan diff baseline.json path/to/Report.pbip --fail-on-regression --fail-on-new HIGH
```

## Studio

`pbiscan studio path/to/Report.pbip` opens a local app at `http://127.0.0.1:8000` with an overview of findings grouped by rule, the fixes with before/after diffs, a measure dependency graph, a model map, a page-by-page report view and a scan comparison. You can export HTML, SARIF, JUnit or JSON from it.

Studio answers only on your own machine, rejects requests from other websites, and uses a random access token that is part of the URL it prints.

## Use it from an AI agent (MCP)

```bash
claude mcp add pbiscan -- python -m pbiscan mcp
```

For Claude Desktop or Cursor, add this to the client's MCP config file (`claude_desktop_config.json`, or `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "pbiscan": { "command": "python", "args": ["-m", "pbiscan", "mcp"] }
  }
}
```

If `python` is not the Python where you installed pbiscan, use the full path to that Python. Studio's **Agent & MCP** screen has a step-by-step guide that fills this in for you.

The server has 8 tools. Six only read: `scan_model`, `diff_models`, `get_measure_lineage`, `plan_remediation`, `list_suppressions` and `suggest_dax_rewrite`. Two change files: `apply_remediation` and `add_suppression`. Try them on a copy of a project first.

## Suppressions

To accept a finding on purpose, add it to `pbiscan.suppressions.json` next to the project. The finding stays in the audit trail and is marked suppressed.

```json
{
  "suppressions": [
    {
      "rule_id": "DAX_UNUSED_MEASURE",
      "location": "Measure: StagedKPI",
      "reason": "Staged for the Q4 release"
    }
  ]
}
```

## Limits worth knowing

- **Static analysis only.** pbiscan cannot measure real query speed or memory. Its performance rules point at patterns worth reviewing.
- **"Unused" means unused in this project.** Other reports, Excel workbooks and tools that use the same semantic model are invisible to it. Check before you delete a measure from a shared model.
- **A file that cannot be read turns off unused-measure detection** for that scan, because the unread file might be the only place a measure is used. The scan warnings name the file.
- **Heuristic rules are labelled** by their confidence below 100%. Expect some false positives and use suppressions.
- It has been run against about 75 public PBIP projects from GitHub. That turned up several false positives, which are fixed and covered by tests. Others may remain. If you find one, please [open an issue](https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner/issues).

## Privacy

Scanning, `fix`, `diff`, Studio and the MCP server run on your machine and make no network calls. The one exception is the optional DAX rewrite advisor (the `suggest_dax_rewrite` tool, and the Measures screen in Studio). Only if you set your own `GROQ_API_KEY` is the DAX you ask it to rewrite sent to Groq. Without the key, nothing is sent.

## How it works

```text
.pbip project (TMDL / TMSL / PBIR / report.json)
  → extraction            parse the model and the report
  → canonical model       tables, relationships, DAX dependency graph, reference index
  → rules                 detect only
  → issues                evidence and recommendations
  → suppressions
  → scoring and output    terminal, HTML, JSON, SARIF, JUnit, Studio
```

The in-browser Studio runs a TypeScript port of the same engine. A parity test compares both engines on every test fixture, so the browser and the command line agree.

## Development

```bash
pip install -e ".[dev]"
python -m pytest                          # everything, about 3 minutes (what CI runs)
python -m pytest -m "not slow and not parity"   # quick loop, about 25 seconds
ruff check pbiscan tests
mypy pbiscan
```

The Studio source is in `studio-ui/`. The built app in `pbiscan/studio/dist` is committed because it ships in the package, so rebuild it after any change there:

```bash
cd studio-ui
npm ci
node node_modules/typescript/bin/tsc --noEmit -p .
node node_modules/vite/bin/vite.js build
```

Call the tools through `node` as shown, because `npx` and `npm run` break when the repository path contains `&`. New detection needs a golden fixture under `tests/golden/` and a test with a true-positive control. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
