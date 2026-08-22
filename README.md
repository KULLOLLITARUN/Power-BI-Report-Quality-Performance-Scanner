# PBIP Sentinel (`pbiscan`)

[![Live Demo](https://img.shields.io/badge/Live_Workbench-pbip--sentinel.netlify.app-C88B3A?style=for-the-badge&logo=netlify&logoColor=white)](https://pbip-sentinel.netlify.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Tests: 411 Passing](https://img.shields.io/badge/Tests-411%20Passing-brightgreen?style=for-the-badge)](https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner)
[![Python: 3.10 | 3.11 | 3.12](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?style=for-the-badge&logo=python&logoColor=white)](https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner)
[![SARIF: OASIS v2.1.0](https://img.shields.io/badge/SARIF-OASIS%20v2.1.0-blueviolet?style=for-the-badge)](https://sarifweb.azurewebsites.net/)

**PBIP Sentinel** is an enterprise static analysis diagnostic engine, CI/CD quality gate, and interactive developer studio for Microsoft Power BI Projects (`.pbip`).

👉 **Try the Live In-Browser Studio Workbench:** **[https://pbip-sentinel.netlify.app/](https://pbip-sentinel.netlify.app/)**  
*(100% In-Browser & Private — drag & drop any `.pbip` folder locally in browser memory, zero files uploaded to any server)*

It inspects semantic model definitions (**TMDL** / **TMSL**), DAX calculation expressions, and report layout schemas (**PBIR** / JSON) to detect anti-patterns, orphaned measures, gateway refresh blockers, and memory bloat before reports are merged or deployed to production.

---

## ⚡ Key Capabilities

- 🛡️ **OASIS SARIF v2.1.0 & JUnit XML Native**: Integrates directly with **GitHub Code Scanning** security alerts, **Azure DevOps**, and **Jenkins**.
- 🚦 **CI/CD Quality Gates**: Enforce automated branch-merge policies with `--fail-under <score>` and `--fail-on <severity>`.
- 🩹 **Safe Remediation Engine** (`pbiscan fix`): Plans and, on request, applies reversible fixes for `MODEL_BIDIRECTIONAL`, `DAX_UNUSED_MEASURE`, `M_HARDCODED_DATA_SOURCE`, and `MODEL_AUTO_DATETIME_BLOAT` — with automatic timestamped backups, an interactive review mode, and a `--fail-on-remediation-available` CI gate.
- 🔀 **Historical Scan Diff** (`pbiscan diff`): Compares two scans and reports new/resolved/persistent findings plus score drift, with `--fail-on-regression` and related quality-gate flags for PR checks.
- 🕸️ **Transitive DAX Graph Reachability**: Cycle-safe dependency DAG that distinguishes truly unreferenced measures from internal calculation building blocks.
- 📑 **Unified Semantic Reference Index**: Accurately tracks measure usage across PBIR Visuals, Calculation Groups (`SELECTEDMEASURE`), Field Parameters, and Row-Level Security (RLS) filters.
- 💻 **Interactive Studio Web UI**: Fast local web application (`pbiscan studio`) featuring an interactive DAX canvas DAG, Model Topology explorer, before/after TMDL remediation diff previews, and 1-click suppressions.
- 🔕 **Transparent Suppressions**: Suppress approved business exceptions via `pbiscan.suppressions.json` without altering findings auditability.
- 🐍 **Zero-Prerequisite Pure Python**: Runs headlessly on Linux, macOS, and Windows with zero external binary or .NET dependencies.

---

## 📊 Real-World Empirical Baseline (11-Model Corpus)

PBIP Sentinel follows a strict **Observation $\to$ Proof $\to$ Implementation** governance gate:

| Metric | Result | Description |
| :--- | :--- | :--- |
| **Real Customer Models Audited** | **11 Models** | Enterprise models across Sales, HR, Finance, and Retail |
| **Classified Findings** | **94 / 94 True Positives** | 100% precision with **0 false positives** |
| **Crash Rate** | **0.00%** | Zero crashes or unhandled exceptions across the corpus |
| **Automated Test Suite** | **411 / 411 Passing** | Unit tests, golden fixtures, cross-engine parity, and API contracts (`~13s` execution) |

---

## 🔍 Built-in Rule Catalog (13 Rules)

### Model & Data Source Architecture (7 Rules)
| Code | Rule ID | Severity | Confidence | Description & Impact |
|:---|:---|:---:|:---:|:---|
| `M001` | `MODEL_BIDIRECTIONAL` | `WARNING` | 100% | Detects bidirectional relationship cross-filtering that risks ambiguous filter paths. |
| `M002` | `MODEL_MANY_TO_MANY` | `HIGH` | 100% | Flags many-to-many cardinality relationships that degrade VertiPaq performance. |
| `M003` | `MODEL_NO_DATE_TABLE` | `ADVISORY` | 70% | Warns if the model lacks a dedicated marked Date dimension table. |
| `M004` | `MODEL_HIGH_CARDINALITY` | `ADVISORY` | 87% | Identifies high-cardinality string columns inflating memory footprint. |
| `M005` | `MODEL_FACT_TO_FACT` | `ADVISORY` | 60% | Heuristic detection of direct relationships between transactional fact tables. |
| `M006` | `M_HARDCODED_DATA_SOURCE` | `HIGH` | 95% | Detects hardcoded developer machine file paths (`C:\Users\...`) in M-partitions that break scheduled gateway refresh. |
| `M007` | `MODEL_AUTO_DATETIME_BLOAT` | `MEDIUM` | 100% | Detects hidden `LocalDateTable_*` tables generated by default Auto Date/Time. |

### DAX & Calculations (4 Rules)
| Code | Rule ID | Severity | Confidence | Description & Impact |
|:---|:---|:---:|:---:|:---|
| `D001` | `DAX_SUSPICIOUS_PATTERN` | `ADVISORY` | ≤65% | Flags suboptimal DAX patterns (e.g. `FILTER(ALL(...))`) needing review. |
| `D002` | `DAX_EXCESSIVE_CALC_COLUMNS` | `MEDIUM` | 100% | Warns on tables with >4 calculated columns consuming uncompressed memory. |
| `D003` | `DAX_DUPLICATE_MEASURE` | `MEDIUM` | 90% | Identifies duplicate normalized DAX formulas across different measures. |
| `D004` | `DAX_UNUSED_MEASURE` | `HIGH` | 95% | Multi-hop transitive scan flagging measures not bound to visuals, calc groups, field params, or RLS. |

### Report Layout & Density (2 Rules)
| Code | Rule ID | Severity | Confidence | Description & Impact |
|:---|:---|:---:|:---:|:---|
| `R001` | `REPORT_VISUAL_BLOAT` | `MEDIUM` | 100% | Detects report pages with >15 visuals that trigger excessive concurrent queries. |
| `R002` | `REPORT_SLICER_BLOAT` | `MEDIUM` | 100% | Flags pages with >6 slicers causing redundant query evaluation overhead. |

---

## 🚀 Quick Start

### Installation

```bash
# Install from source or repository
git clone https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner.git
cd Power-BI-Report-Quality-Performance-Scanner
pip install -e .
```

---

## 🖥️ Usage

### 1. Launch Interactive Studio Workbench
```bash
pbiscan studio "path/to/my_report.pbip"
```
Opens the local developer workspace at `http://127.0.0.1:8000`:
- **Overview Dashboard**: Radial health score gauge and severity breakdown.
- **Findings & Remediation**: Interactive cards with before/after TMDL diffs and 1-click suppression.
- **Interactive DAX DAG**: Canvas-based dependency visualizer with zoom/pan and measure inspector.
- **Model Topology & Provenance**: Table schema inspector, relationships, and RLS/Calc Group bindings.
- **Instant Export**: 1-click download of HTML, SARIF, JUnit XML, or JSON reports.

### 2. Standard Terminal Scan
```bash
pbiscan scan "path/to/my_report.pbip"
```

### 3. Generate Standalone HTML Report
```bash
pbiscan scan "path/to/my_report.pbip" --format html --out "audit_report.html"
```

### 4. CI/CD Quality Gates & Automation
```bash
# Fail CI build if score is below 85 or any HIGH/CRITICAL finding is detected
pbiscan scan "path/to/my_report.pbip" \
  --format sarif \
  --out "results.sarif" \
  --fail-under 85 \
  --fail-on HIGH
```

### 5. Historical Diff Between Two Scans
```bash
# Fail if the overall score regresses, or a new HIGH+ finding was introduced
pbiscan diff "baseline_scan.json" "path/to/my_report.pbip" \
  --fail-on-regression \
  --fail-on-new HIGH \
  --format markdown --out "pr_comment.md"
```

### 6. Safe Remediation (`pbiscan fix`)
```bash
# Preview a remediation plan (dry-run, no files touched)
pbiscan fix "path/to/my_report.pbip"

# Interactively review and apply only the patches you approve
pbiscan fix "path/to/my_report.pbip" --interactive --apply

# CI governance gate: fail the build if any safe fix is available but unapplied
pbiscan fix "path/to/my_report.pbip" --fail-on-remediation-available --quiet
```
Supports `MODEL_BIDIRECTIONAL`, `DAX_UNUSED_MEASURE`, `M_HARDCODED_DATA_SOURCE`, and `MODEL_AUTO_DATETIME_BLOAT`. Applying patches creates a timestamped backup directory first and validates each patch against a fresh scan fingerprint before touching disk.

---

## ⚙️ CI/CD Integration Examples

### GitHub Actions (with Code Scanning Alerts)
```yaml
name: Power BI Quality Gate
on: [push, pull_request]

jobs:
  pbi-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install PBIP Sentinel
        run: pip install .

      - name: Scan PBIP Model
        run: |
          pbiscan scan my_project.pbip \
            --format sarif \
            --out results.sarif \
            --fail-under 80

      - name: Upload SARIF to GitHub Code Scanning
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: results.sarif
```

### Azure DevOps Pipelines
```yaml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.11'

  - script: |
      pip install .
      pbiscan scan my_project.pbip --format junit --out test-results.xml --fail-under 85
    displayName: 'Run PBIP Sentinel Quality Gate'

  - task: PublishTestResults@2
    condition: always()
    inputs:
      testResultsFormat: 'JUnit'
      testResultsFiles: 'test-results.xml'
```

---

## 🔕 Suppression System (`pbiscan.suppressions.json`)

To mark an approved architectural exception without disabling rules or deleting findings:

```json
{
  "suppressions": [
    {
      "rule_id": "M_HARDCODED_DATA_SOURCE",
      "location": "Table: LocalDevLookup",
      "reason": "Approved local lookup for isolated dev environment"
    },
    {
      "rule_id": "DAX_UNUSED_MEASURE",
      "location": "Measure: StagedKPI",
      "reason": "Staged for upcoming Q4 executive release"
    }
  ]
}
```

---

## 🏗️ Architecture

```text
PBIP Project (.pbip / TMDL / TMSL / PBIR)
                  │
                  ▼
         Extraction Layer (pbip_reader.py)
                  │
                  ▼
         Canonical Model (canonical/model.py, dax_graph.py)
         ├── ModelGraph (Topology: connected_components, relationships)
         ├── DaxDependencyGraph (Transitive DAG, cycle-safe reachability)
         └── SemanticReferenceIndex (Visuals, Calc Groups, Field Params, RLS)
                  │
                  ▼
         Rule Engine (rules/model.py, dax.py, report.py)
                  │
                  ▼
         Issue Generator & Recommendations (engine/issue.py, recommendations.py)
                  │
                  ▼
         Suppression Filter (engine/suppressions.py)
                  │
                  ▼
         Scoring & Multi-Target Renderers (engine/scoring.py, render/)
         ┌────────────┬──────────────┬─────────────┬──────────────┐
         ▼            ▼              ▼             ▼              ▼
     CLI Text    HTML Report    SARIF v2.1.0   JUnit XML    Studio Web UI
```

---

## 🧪 Automated Testing

```bash
# Run all 377 unit, golden contract, and integration tests
pytest tests/ -v
```

If Node.js and `studio-ui`'s dependencies (`npm install` inside `studio-ui/`) are available, an additional 34 cross-engine parity tests run automatically, diffing the in-browser `clientScanner.ts` engine's findings against the Python `ScanService` for every golden fixture — this is what keeps the Netlify Studio Workbench's results honest against `pbiscan scan`.

---

## 📄 License

MIT License — Copyright (c) 2026 Tarun Kulloolli
