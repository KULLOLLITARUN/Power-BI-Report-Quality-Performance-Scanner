# CI/CD Governance & Drift Prevention Guide

PBIP Sentinel provides native **CI/CD Quality Gates** and **Historical Drift Detection** to prevent quality regressions, DAX antipatterns, and model bloat from entering production Power BI repositories.

---

## 1. Governance Architecture

```text
Feature Branch PR
       │
       ├── Baseline Scan (Target/Main Branch) ──► baseline_scan.json
       │
       └── Current Scan (PR Branch) ───────────► current_scan.json
                                                        │
                                                        ▼
                                             pbiscan diff BASELINE CURRENT
                                                        │
       ┌────────────────────────────────────────────────┼────────────────────────────────────────────────┐
       ▼                                                ▼                                                ▼
Score Drift (< 0.0)                         New HIGH/CRITICAL Findings                            Modified Severities
  └── Quality Gate FAIL                       └── Quality Gate FAIL                                 └── Transition Audit
       │                                                │                                                │
       └────────────────────────────────────────────────┼────────────────────────────────────────────────┘
                                                        ▼
                                       GitHub Actions / Azure DevOps
                                       ├── PR Comment (Sticky Markdown)
                                       ├── $GITHUB_STEP_SUMMARY Dashboard
                                       └── Exit Code 0 (PASS) or 1 (FAIL)
```

---

## 2. GitHub Actions Integration

### Automated Workflow (`.github/workflows/pbiscan-drift.yml`)

The workflow automatically compares your PR branch against `main` whenever `.pbip`, TMDL, or BIM model definitions are modified.

```yaml
name: PBIP Quality Gate

on:
  pull_request:
    paths:
      - '**/*.pbip'
      - '**/*.SemanticModel/**'
      - '**/*.Report/**'
      - '**/*.tmdl'
      - '**/*.bim'

jobs:
  quality-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          path: current_repo

      - uses: actions/checkout@v4
        with:
          ref: ${{ github.base_ref || 'main' }}
          path: base_repo

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install PBIP Sentinel
        run: |
          pip install pbiscan

      - name: Scan Baseline & Current Models
        run: |
          mkdir -p artifacts
          pbiscan scan base_repo/MyModel.pbip --out artifacts/base.json --format json || true
          pbiscan scan current_repo/MyModel.pbip --out artifacts/curr.json --format json || true

      - name: Evaluate Quality Gate
        run: |
          pbiscan diff artifacts/base.json artifacts/curr.json \
            --format markdown \
            --out artifacts/pr_drift.md \
            --fail-on-new HIGH \
            --fail-on-regression
```

---

## 3. Azure DevOps Pipeline Template (`azure-pipelines.yml`)

```yaml
trigger: none
pr:
  branches:
    include:
      - main
  paths:
    include:
      - '**/*.pbip'
      - '**/*.SemanticModel/**'

pool:
  vmImage: 'ubuntu-latest'

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.11'

  - script: |
      python -m pip install --upgrade pip
      pip install pbiscan
    displayName: 'Install PBIP Sentinel'

  - script: |
      mkdir -p $(Build.ArtifactStagingDirectory)/diff
      # Baseline scan from main
      git clone --depth 1 $(Build.Repository.Uri) -b main base_repo
      pbiscan scan base_repo/MyModel.pbip --out $(Build.ArtifactStagingDirectory)/diff/base.json --format json || true
      
      # PR scan
      pbiscan scan $(Build.SourcesDirectory)/MyModel.pbip --out $(Build.ArtifactStagingDirectory)/diff/curr.json --format json || true
      
      # Diff & Quality Gate
      pbiscan diff $(Build.ArtifactStagingDirectory)/diff/base.json $(Build.ArtifactStagingDirectory)/diff/curr.json \
        --fail-on-new HIGH \
        --fail-on-regression \
        --format markdown \
        --out $(Build.ArtifactStagingDirectory)/diff/summary.md
    displayName: 'Evaluate PBIP Quality Gate'

  - task: PublishBuildArtifacts@1
    condition: always()
    inputs:
      PathtoPublish: '$(Build.ArtifactStagingDirectory)/diff'
      ArtifactName: 'PBIP-Sentinel-Drift'
```

---

## 4. Quality Gate Policy Tuning

| CLI Flag | Policy Enforcement | Recommended Use |
| :--- | :--- | :--- |
| `--fail-on-regression` | Fails PR if overall health score drops ($\Delta < 0$). | Strict enterprise repositories. |
| `--max-score-drop FLOAT` | Fails PR only if score drop exceeds tolerance (e.g. `2.5`). | Large models undergoing iterative refactoring. |
| `--fail-on-new SEVERITY` | Fails PR if any new finding matches or exceeds severity (`CRITICAL`, `HIGH`, `WARNING`, `MEDIUM`). | Preventing hardcoded data sources or bidirectional relationships. |
| `--fail-on-category-regression CAT` | Fails PR if a specific category score degrades (`model`, `dax`, `report`). | Specialized semantic model reviews. |

---

## 5. Deterministic Exit Codes

* **`0` (PASS)**: Both scans evaluated and quality gate passed.
* **`1` (FAIL)**: Comparison completed, but quality gate policy was violated (e.g. score regressed or new high-severity finding introduced).
* **`2` (ERROR)**: Execution error, missing input path, or malformed artifact file.
