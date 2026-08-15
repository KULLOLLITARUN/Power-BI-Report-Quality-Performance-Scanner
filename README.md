# pbiscan

A static analysis and quality linter for Power BI Projects (`.pbip`).

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
| **Interactive Studio** | Desktop application | Local web workbench with Model Map graph & DAX Inspector |

---

## Built-in Rules (Locked v1 Matrix)

### Model Architecture (5 Rules)
| Code | Rule ID | Severity | Confidence | Rationale |
|---|---|---|---|---|
| `M001` | `MODEL_BIDIRECTIONAL` | `WARNING` | 100% | Bidirectional filters introduce ambiguous filter paths, unexpected context propagation, and memory overhead. |
| `M002` | `MODEL_MANY_TO_MANY` | `WARNING` | 100% | M:M cardinality can yield non-additive totals and requires bridge table evaluation. |
| `M003` | `MODEL_NO_DATE_TABLE` | `WARNING` | 70% | Identifies models lacking a designated date dimension, preventing optimized time-intelligence calculations. |
| `M004` | `MODEL_HIGH_CARDINALITY` | `ADVISORY` | 87% | Unique text columns not participating in relationships increase dictionary size without adding analytic value. |
| `M005` | `MODEL_FACT_TO_FACT` | `ADVISORY` | 60% | Direct relationships between fact tables violate star-schema principles and should be mediated by shared dimensions. |

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
# Core CLI and HTML Reporter
pip install pbiscan

# With Interactive Web Studio workbench
pip install "pbiscan[studio]"
```

---

## Usage

### 1. Launch Interactive Studio Workbench
```bash
pbiscan studio
```
Opens the local developer workbench at `http://127.0.0.1:8000` with the **Model Map architecture graph**, **DAX Inspector**, and **Diagnostic Findings stream**.

### 2. Basic CLI Scan
```bash
pbiscan scan "path/to/SalesAnalytics.pbip"
```

### 3. Generate Standalone HTML Audit Report
```bash
pbiscan scan "path/to/SalesAnalytics.pbip" --out "audit_report.html"
```

### 4. CI/CD Pipeline Automation
```bash
# Enforce a quality threshold (exits with non-zero code if score < 85)
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

The test suite includes unit tests for every contract, integration tests for the FastAPI Studio server, and golden fixtures for TMDL and TMSL models.

```bash
# Run full test suite (117 tests)
pytest -v
```

---

## License

Distributed under the [MIT License](LICENSE). Copyright (c) 2025-2026 Tarun Kullolli.
