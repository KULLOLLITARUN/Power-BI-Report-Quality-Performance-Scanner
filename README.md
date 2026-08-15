# PBIP Sentinel (pbiscan)

[![Live Demo](https://img.shields.io/badge/Live_Workbench-pbip--sentinel.netlify.app-C88B3A?style=for-the-badge&logo=netlify&logoColor=white)](https://pbip-sentinel.netlify.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Tests: Passing](https://img.shields.io/badge/Tests-118%20Passing-brightgreen?style=for-the-badge)](https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner)

**PBIP Sentinel** is a static analysis diagnostic engine and quality linter for Power BI Projects (`.pbip`).

👉 **Try the Live In-Browser Workbench:** **[https://pbip-sentinel.netlify.app/](https://pbip-sentinel.netlify.app/)**  
*(100% In-Browser & Private — drag & drop any `.pbip` folder locally in memory, zero files uploaded to any server)*

`pbiscan` scans semantic model definitions (TMDL / TMSL) and report layout metadata (PBIR / JSON) to detect anti-patterns, performance risks, and DAX duplication before reports are published to production.

---

## Why pbiscan?

Traditional BI linters provide pass/fail checklists that assume you already know VertiPaq internals and DAX filter propagation mechanics. 

`pbiscan` provides an **explainable 4-part diagnostic contract**:

$$\text{Evidence} \longrightarrow \text{Architectural Impact} \longrightarrow \text{Remediation Guidance} \longrightarrow \text{Confidence Score}$$

- **Hedged Confidence**: Rules explicitly state confidence percentages (e.g. 60% for heuristic joins, 100% for bidirectional links) to eliminate false-alarm panic.
- **Explainable Diagnostics**: Junior developers and cross-functional teams learn *why* a pattern is problematic and *how* to resolve it.
- **Multi-Platform & Pure Python**: Runs headlessly in Linux/macOS/Windows CI/CD pipelines with zero external binary or .NET framework prerequisites.

---

## Comparison

| Dimension | Rule Checklists (e.g. Tabular Editor BPA) | `pbiscan` Static Audit Engine |
| :--- | :--- | :--- |
| **Primary Audience** | Experienced Tabular/DAX Model Architects | Cross-functional Teams, Analytics Engineers & BI Devs |
| **Output Contract** | Object violation checklist (Pass / Fail) | 4-Part Diagnostic Contract (`Evidence → Impact → Remediation → Confidence`) |
| **Severity Model** | Fixed rule priority | Context-hedged language (`WARNING`, `ADVISORY`, % Confidence) |
| **Runtime Requirements** | Requires Tabular Editor (.NET / Windows binary) | Pure Python (`pip install`), cross-platform on Linux, macOS, Windows |
| **Interactive Studio** | Desktop application | Local & Web workbench with Model Map graph & DAX Inspector |

---

## Built-in Rules (Locked v1 Matrix)

### Model Architecture (5 Rules)
| Code | Rule ID | Severity | Confidence | Rationale |
|---|---|---|---|---|
| `M001` | `MODEL_BIDIRECTIONAL` | `WARNING` | 100% | Bidirectional filters introduce ambiguous filter paths, unexpected context propagation, and memory overhead. |
| `M002` | `MODEL_MANY_TO_MANY` | `HIGH` | 100% | Many-to-many relationships bypass standard index structures and increase query evaluation latency. |
| `M003` | `MODEL_INACTIVE_RELATIONSHIP` | `ADVISORY` | 100% | Inactive relationships require `USERELATIONSHIP` to activate; unreferenced inactive links create cognitive clutter. |
| `M004` | `MODEL_AUTO_DATE_TIME` | `WARNING` | 100% | Built-in Auto Date/Time generates hidden tables per date column, significantly bloating memory footprint. |
| `M005` | `MODEL_NO_RELATIONSHIPS` | `ADVISORY` | 100% | Multiple independent tables with zero relationships often signal unmodeled dimensional structures. |

### DAX & Calculations (4 Rules)
| Code | Rule ID | Severity | Confidence | Rationale |
|---|---|---|---|---|
| `D001` | `DAX_SUSPICIOUS_PATTERN` | `ADVISORY` | ≤65% | Flags patterns such as `FILTER(ALL(...))` and `EARLIER()` that often warrant optimization. |
| `D002` | `DAX_EXCESSIVE_CALC_COLUMNS` | `MEDIUM` | 100% | Calculated columns consume uncompressed memory and increase refresh time; prefers measures or upstream ETL. |
| `D003` | `DAX_DUPLICATE_MEASURE` | `MEDIUM` | 90% | Identifies identical normalized DAX expressions across different measure names to eliminate redundant logic. |
| `D004` | `DAX_UNUSED_MEASURE` | `ADVISORY` | 95% | Deep reference scan flagging measures that are neither placed in report visuals nor referenced by downstream measures. |

### Report Layout & Density (2 Rules)
| Code | Rule ID | Severity | Confidence | Rationale |
|---|---|---|---|---|
| `R001` | `REPORT_VISUAL_BLOAT` | `MEDIUM` | 100% | Pages with >15 visuals trigger concurrent DAX queries that increase visual load times and capacity utilization. |
| `R002` | `REPORT_SLICER_BLOAT` | `MEDIUM` | 100% | Pages with >6 slicers generate redundant query overhead on initial page render and cross-filtering events. |

---

## Installation

```bash
# Install directly from GitHub
pip install "git+https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner.git"

# With Interactive Web Studio workbench
pip install "pbiscan[studio] @ git+https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner.git"

# Or clone and install locally for development
git clone https://github.com/KULLOLLITARUN/Power-BI-Report-Quality-Performance-Scanner.git
cd Power-BI-Report-Quality-Performance-Scanner
pip install -e ".[studio,dev]"
```

---

## Usage

### 1. Web Version (Zero Install)
Open **[https://pbip-sentinel.netlify.app/](https://pbip-sentinel.netlify.app/)** to drag & drop your `.pbip` project directory directly in the browser or explore interactive sample reports.

### 2. Launch Local Interactive Studio Workbench
```bash
# Using CLI:
pbiscan studio

# Or double-click the 1-click Windows launcher:
run_studio.bat
```
Opens the local developer workbench at `http://127.0.0.1:8000` with the **Model Map architecture graph**, **DAX Inspector**, and **Diagnostic Findings stream**.

### 3. Basic CLI Scan
```bash
pbiscan scan "path/to/SalesAnalytics.pbip"
```

### 4. Generate Standalone HTML Audit Report
```bash
pbiscan scan "path/to/SalesAnalytics.pbip" --out "audit_report.html"
```

### 5. CI/CD Pipeline Automation Gate
```bash
# Enforce a quality threshold (exits with exit code 1 if score < 85)
pbiscan scan "path/to/SalesAnalytics.pbip" --fail-under 85 --format json --out "results.json"
```

---

## Architecture

`pbiscan` enforces a strict separation between extraction, canonical representations, and rule evaluation:

```text
PBIP Project (.pbip / TMDL / TMSL / PBIR)
                  │
                  ▼
         Extraction Layer (pbip_reader.py)
                  │
                  ▼
         Canonical Model (canonical/model.py)
                  │
                  ▼
         Rule Engine (rules/model.py, dax.py, report.py)
                  │
                  ▼
         Issue Generator (engine/issue.py)
                  │
                  ▼
         Scoring & Reporting (engine/scoring.py, render/)
              ┌───┴────────────────┐
              ▼                    ▼
         CLI Output       HTML / JSON / Studio UI
```

---

## Testing

Run the automated test suite across all 118 unit, integration, and golden fixture tests:

```bash
pytest tests/ -v
```

---

## License

MIT License — Copyright (c) 2026 Tarun Kulloolli
