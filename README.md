# pbiscan

A static analysis and quality linter for Power BI Projects (`.pbip`).

`pbiscan` scans semantic model definitions (TMDL / TMSL) and report layout metadata (PBIR / JSON) to detect anti-patterns, performance risks, and DAX duplication before reports are published to production.

---

## Overview

Modern Power BI development uses Git and PBIP format, but reviewing raw TMDL and report JSON during pull requests is error-prone. `pbiscan` automates these checks in local development and CI/CD pipelines without requiring an active Power BI Desktop session or XMLA/Analysis Services connection.

### Key Capabilities
- **Format Support**: Parses both modern TMDL schemas (`definition/tables/*.tmdl`) and classic TMSL (`model.bim`), as well as PBIR page/visual definitions.
- **Evidence-Backed Reports**: Every finding contains the specific table, column, or measure formula location, technical impact, and remediation guidance.
- **Self-Contained HTML Audits**: Produces standalone, zero-dependency HTML audit reports with interactive category filters and health scoring.
- **CI/CD Ready**: Runs headlessly in GitHub Actions or Azure DevOps with JSON output and non-zero exit code thresholds.

---

## Built-in Rules

### Model Architecture
| Code | Rule | Severity | Rationale |
|---|---|---|---|
| `M001` | Bi-directional relationship | `WARNING` | Bidirectional filters introduce ambiguous filter paths, unexpected context propagation, and performance degradation on large dimensions. |
| `M002` | Many-to-many relationship | `WARNING` | M:M cardinality can yield non-additive totals and requires bridge table evaluation. |
| `M003` | Missing date dimension | `WARNING` | Identifies models lacking a designated date dimension, which prevents optimized time-intelligence calculations. |
| `M004` | High-cardinality text column | `ADVISORY` | Unique text columns not participating in relationships increase VertiPaq dictionary size without adding analytic value. |
| `M005` | Fact-to-fact relationship | `ADVISORY` | Direct relationships between fact tables violate star-schema principles and should be mediated by shared dimensions. |

### DAX & Calculations
| Code | Rule | Severity | Rationale |
|---|---|---|---|
| `D001` | Suspicious DAX patterns | `ADVISORY` | Flags patterns such as `FILTER(ALL(...))` and nested `CALCULATE()` transitions that often warrant optimization. |
| `D002` | Excessive calculated columns | `MEDIUM` | Calculated columns consume uncompressed memory and increase refresh time; prefers measures or upstream ETL computation. |
| `D003` | Duplicate measure logic | `MEDIUM` | Identifies identical normalized DAX expressions across different measure names to eliminate redundant business logic. |
| `D004` | Unused measures | `ADVISORY` | Two-signal scan flagging measures that are neither placed in report visuals nor referenced by downstream measures. |

### Report Layout & Density
| Code | Rule | Severity | Rationale |
|---|---|---|---|
| `R001` | Visual bloat (>15 visuals) | `MEDIUM` | Pages with excessive visuals trigger concurrent DAX queries that increase visual load times and capacity utilization. |
| `R002` | Slicer bloat (>6 slicers) | `MEDIUM` | Excessive slicers generate redundant query overhead on initial page render and cross-filtering events. |

---

## Installation

```bash
git clone https://github.com/KULLOLLITARUN/pbiscan.git
cd pbiscan
pip install -e .
```

---

## Usage

### Basic CLI Scan
```bash
pbiscan scan "path/to/SalesAnalytics.pbip"
```

### Generate Standalone HTML Audit
```bash
pbiscan scan "path/to/SalesAnalytics.pbip" --out "audit_report.html"
```

### Export Machine-Readable JSON for CI/CD
```bash
pbiscan scan "path/to/SalesAnalytics.pbip" --out "results.json" --format json
```

### Custom Configuration
Adjust deductions, category weights, and rule thresholds via `rules.config.json`:
```bash
pbiscan scan "path/to/SalesAnalytics.pbip" --config "rules.config.json"
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
              ┌───┴───┐
              ▼       ▼
         CLI Output  HTML / JSON
```

---

## Development & Testing

The test suite includes unit tests for every contract, integration tests for full pipeline execution, and isolated golden fixtures for each quality check.

```bash
# Run full test suite
pytest

# Run tests with coverage
pytest --cov=pbiscan
```

---

## License

Distributed under the [MIT License](LICENSE). Copyright (c) 2025-2026 Tarun Kullolli.
