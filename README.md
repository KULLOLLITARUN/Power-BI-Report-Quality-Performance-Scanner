# pbiscan

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 111 Passed](https://img.shields.io/badge/tests-111%20passed-brightgreen.svg)](tests/)

**Power BI Report Quality & Performance Scanner**

`pbiscan` is a fast, deterministic static analysis scanner for Power BI Projects (`.pbip`). It inspects semantic models and report layouts to produce structured, evidence-based quality audits.

---

## ✨ Features

- **TMDL & TMSL Support**: Natively parses modern TMDL definitions (`definition/tables/*.tmdl`) as well as legacy `model.bim` schemas.
- **PBIR & Classic Report Layouts**: Scans visual counts, slicer densities, and field bindings across report pages.
- **Evidence-Based Findings**: Every finding provides the exact formula or table location, impact analysis, and practical recommendations.
- **Interactive Dark-Mode HTML Report**: Standalone single-file HTML audit reports with category health scores and interactive filters.
- **100% Deterministic**: Operates locally with zero cloud dependencies, external connections, or LLMs.

---

## 📋 Quality Rules (v1 — 11 Checks)

### 📐 Semantic Model
| ID | Rule | Default Severity | Description |
|---|---|---|---|
| **M001** | Bi-directional relationship | `WARNING` | Detects relationships with bidirectional cross-filtering. |
| **M002** | Many-to-many relationship | `WARNING` | Detects M:M cardinality relationships. |
| **M003** | Missing date dimension | `WARNING` | Flags models lacking a designated date dimension. |
| **M004** | High-cardinality column | `ADVISORY` | Identifies unique text columns not participating in relationships. |
| **M005** | Fact-to-fact relationship | `ADVISORY` | Heuristic detection of direct relationships between fact tables. |

### ⚡ DAX Calculations
| ID | Rule | Default Severity | Description |
|---|---|---|---|
| **D001** | Suspicious DAX patterns | `ADVISORY` | Detects patterns like `FILTER(ALL(...))` and nested `CALCULATE()`. |
| **D002** | Excessive calculated columns | `MEDIUM` | Flags tables containing >4 calculated columns (skipping internal tables). |
| **D003** | Duplicate measure logic | `MEDIUM` | Detects identical normalized DAX expressions across measures. |
| **D004** | Unused measures | `ADVISORY` | Flags measures neither bound to visuals nor referenced by other measures. |

### 📊 Report Layout
| ID | Rule | Default Severity | Description |
|---|---|---|---|
| **R001** | Visual bloat | `MEDIUM` | Flags pages containing >15 visuals. |
| **R002** | Slicer bloat | `MEDIUM` | Flags pages containing >6 slicers. |

---

## 🚀 Quick Start

### Installation

```bash
# Clone and install locally
git clone https://github.com/your-username/pbiscan.git
cd pbiscan
pip install -e .
```

### Running a Scan

```bash
# Scan a PBIP project and view CLI output
pbiscan scan "./MyReport.pbip"

# Generate an interactive HTML report
pbiscan scan "./MyReport.pbip" --out "audit_report.html"

# Export audit results as JSON
pbiscan scan "./MyReport.pbip" --out "audit_report.json" --format json
```

---

## 🏗 Architecture

```
PBIP Artifact (.pbip / TMDL / TMSL)
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
  Scoring Engine (engine/scoring.py)
              │
      ┌───────┴───────┐
      ▼               ▼
 CLI Summary    HTML Report (render/)
```

---

## 🧪 Testing

```bash
# Run the complete test suite (111 unit, integration, and golden tests)
pytest
```

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for architectural guidelines and testing instructions.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
