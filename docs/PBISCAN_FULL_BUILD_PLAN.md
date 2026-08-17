# pbiscan — Power BI Report Quality & Performance Scanner

## Master Build Specification

**Document status:** Final / Locked  
**Current target:** v1.0  
**Primary artifact:** PBIP  
**Secondary artifact:** PBIX (future)  
**Primary language:** Python  
**v1 AI/LLM usage:** None  
**v1 runtime connections:** None  
**v1 scope:** Static Power BI report analysis

---

# 1. Executive Summary

`pbiscan` is a Power BI static analysis tool that scans a PBIP report and produces an evidence-based quality audit.

The scanner must not simply report:

> "15 issues found."

It must produce structured findings containing:

```text
Issue
Evidence
Impact
Recommendation
Confidence
Severity
Location
Rule ID
```

The v1 product is deliberately deterministic/heuristic.

It does **not** use an LLM.

It does **not** connect to Analysis Services.

It does **not** inspect VertiPaq runtime statistics.

It does **not** automatically modify a report.

The architecture must, however, make future PBIX support, runtime analysis, historical regression analysis, LLM explanations, and remediation possible without rewriting the rule engine.

---

# 2. Product Vision

Long-term vision:

```text
Deterministic static evidence
            ↓
Structural intelligence
            ↓
Runtime evidence
            ↓
Historical/regression intelligence
            ↓
LLM-assisted explanation
            ↓
Validated remediation
            ↓
CI/CD quality gates
            ↓
Enterprise platform
```

The most important architectural principle is:

> The LLM must never become the source of truth for whether a Power BI issue exists.

The deterministic/runtime engines produce evidence.

Future LLM functionality may explain, contextualize, or propose remediation based on that evidence.

---

# 3. v1 Product Definition

## v1 Input

Primary:

```text
.pbip project directory
```

PBIX is explicitly out of the v1 implementation scope.

## v1 Output

Two output modes:

1. CLI summary
2. Self-contained HTML audit report

Example:

```text
pbiscan scan ./Sales.pbip --config rules.config.json --out report.html
```

---

# 4. v1 Scope Boundary

## Included

- PBIP extraction
- Canonical Power BI model
- Model analysis
- DAX static analysis
- Report layout analysis
- 11 quality checks
- Evidence generation
- Confidence values
- Severity classification
- Recommendations
- Category scoring
- Overall health score
- CLI output
- HTML output
- Golden fixtures
- Regression tests
- Real PBIP validation

## Explicitly excluded

- LLM
- AI explanations
- AI-generated fixes
- Auto-remediation
- TOM
- XMLA
- DMV runtime queries
- VertiPaq analysis
- Server Timings
- DAX Studio integration
- CI/CD gates
- SaaS
- Multi-tenancy
- Authentication
- Web application
- Baseline persistence
- Full DAX AST/dependency engine
- PBIX support in the initial implementation

Do not add these features during v1 unless explicitly requested.

---

# 5. Core Architecture

```text
                 PBIP Artifact
                      │
                      ▼
             ┌─────────────────┐
             │    Extraction   │
             │  extraction/    │
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │ Canonical Model │
             │   canonical/    │
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │   Rule Engine   │
             │     rules/      │
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │ Issue Generator │
             │     engine/     │
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │ Scoring Engine  │
             │     engine/     │
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │    Renderer     │
             │     render/     │
             └────────┬────────┘
                      │
              ┌───────┴────────┐
              ▼                ▼
            CLI              HTML
```

---

# 6. Non-Negotiable Architectural Contracts

## Contract 1 — Extraction isolation

`pbip_reader.py` only reads and parses artifacts.

It must not:

- detect issues
- calculate scores
- generate recommendations
- classify severity
- contain rule logic

It returns raw parsed data.

---

## Contract 2 — Canonical model isolation

Rules consume canonical model objects only.

Rules must never directly inspect raw PBIP structures.

Bad:

```python
from extraction.pbip_reader import ...
```

Good:

```python
from canonical.model import CanonicalReport
```

---

## Contract 3 — Rules contain detection only

Rules return structured detections.

Rules must not contain recommendation prose.

Bad:

```python
recommendation = "Change the relationship to single direction..."
```

Good:

```python
rule_id = "MODEL_BIDIRECTIONAL"
```

Recommendation text belongs in:

```text
engine/recommendations.py
```

---

## Contract 4 — Recommendations are reviewed

Every recommendation must be manually reviewed for Power BI/DAX semantic correctness.

Do not dynamically invent v1 recommendations.

---

## Contract 5 — Scoring is configuration-driven

Thresholds and deductions must not be hardcoded inside rules.

Use:

```text
rules.config.json
```

---

## Contract 6 — Deterministic v1

Given the same PBIP and configuration, the scanner should produce equivalent results.

No network calls.

No LLM.

No randomness.

No external AI dependency.

---

# 7. Repository Structure

Target structure:

```text
pbiscan/
│
├── extraction/
│   ├── __init__.py
│   └── pbip_reader.py
│
├── canonical/
│   ├── __init__.py
│   └── model.py
│
├── rules/
│   ├── __init__.py
│   ├── model.py
│   ├── dax.py
│   └── report.py
│
├── engine/
│   ├── __init__.py
│   ├── issue.py
│   ├── recommendations.py
│   └── scoring.py
│
├── render/
│   ├── __init__.py
│   ├── html_report.py
│   └── templates/
│       └── report.html.j2
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── golden/
│       ├── test_bidirectional/
│       ├── test_manytomany/
│       ├── test_nodatetable/
│       ├── test_highcardinality/
│       ├── test_facttofact/
│       ├── test_visualbloat/
│       ├── test_slicerbloat/
│       ├── test_duplicatedax/
│       ├── test_expensive_dax/
│       ├── test_unusedmeasure/
│       └── test_measure_referenced_by_another/
│
├── rules.config.json
├── cli.py
├── pyproject.toml
├── README.md
└── BUILD_PLAN.md
```

---

# 8. Canonical Model

The canonical model is the central abstraction of the application.

Recommended high-level structures:

```text
CanonicalReport
├── model
│   ├── tables
│   ├── columns
│   └── relationships
├── dax
│   ├── measures
│   └── calculated_columns
└── report
    ├── pages
    └── visuals
```

## ModelGraph

Represent:

### Table

- name
- hidden
- metadata
- columns

### Column

- name
- table
- data type
- hidden
- unique flag if available
- data category
- relationship participation

### Relationship

- from table
- from column
- to table
- to column
- cardinality
- cross-filter direction
- active state if available

---

# 9. DaxDictionary

Represent:

### Measure

- name
- table
- expression
- hidden
- location if available

### Calculated column

- name
- table
- expression
- data type if available

The v1 DAX reference scanner must be capable of checking whether a measure is referenced by another measure.

Example:

```text
[Revenue]
    ↓
[Revenue Growth]
    ↓
[Revenue Growth %]
```

If `[Revenue]` is not directly bound to a visual but is referenced by `[Revenue Growth]`, it must not be reported as unused.

---

# 10. ReportDOM

Represent:

### Page

- name
- display name if available
- visibility
- visuals

### Visual

- visual type
- page
- position
- size
- fields used
- measure references
- slicer classification
- hidden state if available

The exact PBIP schema may vary.

The extractor must fail gracefully when optional properties are missing.

---

# 11. Final v1 Rule Set

Exactly 11 checks.

---

## MODEL

### M001 — Bi-directional relationship

Detection:

```text
crossFilteringBehavior == Both
```

Classification:

```text
Severity: WARNING
Type: deterministic
Confidence: 100%
```

Important:

Do not call every bidirectional relationship a defect.

Use wording such as:

> Bidirectional filter propagation detected. Review whether the relationship is intentionally required.

---

## M002 — Many-to-many relationship

Detection:

```text
cardinality == ManyToMany
```

Classification:

```text
Severity: WARNING
Type: deterministic
Confidence: 100%
```

Language must remain contextual.

Do not claim that every M:M relationship is wrong.

---

## M003 — Potential date dimension issue

Detection is structural.

The rule may inspect available table metadata/data category information.

Classification:

```text
Severity: WARNING
Type: structural
Confidence: 70%
```

Use hedged wording:

> Potential date dimension concern detected.

Do not state:

> Your model definitely has a date-table problem.

---

## M004 — Potential high-cardinality column

Candidate conditions may include:

- string column
- uniqueness indicators
- not participating in a relationship
- GUID-like or identifier-like characteristics where available

Classification:

```text
Severity: ADVISORY
Type: structural
Confidence: 87%
```

The rule must clearly communicate that static analysis cannot prove actual VertiPaq memory impact.

---

## M005 — Potential fact-to-fact relationship

Use model structure and naming/metadata heuristics.

Classification:

```text
Severity: ADVISORY
Type: heuristic
Confidence: 60%
```

Do not claim certainty.

---

# 12. DAX Rules

## D001 — Suspicious DAX patterns

Initial v1 implementation is regex/pattern based.

Candidate patterns include:

```text
FILTER(ALL(
EARLIER(
nested CALCULATE(
```

The exact patterns must be configurable or centralized.

Classification:

```text
Severity: ADVISORY
Type: heuristic
Confidence: maximum 65%
```

Critical rule:

This rule indicates:

> Worth reviewing.

It does NOT mean:

> This measure is slow.

Only runtime analysis can prove actual performance.

---

## D002 — Excessive calculated columns

Count calculated columns per table.

Default threshold:

```text
4
```

Classification:

```text
Severity: MEDIUM
Type: deterministic
Confidence: 100%
```

The threshold is configurable.

---

## D003 — Duplicate measure logic

Normalize measure expressions:

- trim whitespace
- normalize case where semantically safe
- normalize formatting
- hash normalized expression

Detect identical expressions under different measure names.

Classification:

```text
Severity: MEDIUM
Type: structural
Confidence: 90%
```

Do not automatically recommend deleting one measure.

Context may matter.

---

## D004 — Unused measure

Use two signals:

1. report visual references
2. shallow cross-measure references

A measure is considered unused only when:

```text
NOT directly used by a visual
AND
NOT referenced by another measure
```

Classification:

```text
Severity: ADVISORY
Type: structural
Confidence: 95%
```

This rule is especially important because naive `fields_used` detection creates false positives.

---

# 13. REPORT Rules

## R001 — Visual bloat

Default threshold:

```text
15 visuals/page
```

Classification:

```text
Severity: MEDIUM
Type: deterministic
Confidence: 100%
```

---

## R002 — Slicer bloat

Default threshold:

```text
6 slicers/page
```

Classification:

```text
Severity: MEDIUM
Type: deterministic
Confidence: 100%
```

---

# 14. Rule Result Contract

Rules should return structured detection objects.

Conceptually:

```python
RuleFinding(
    rule_id="MODEL_BIDIRECTIONAL",
    category="model",
    severity="WARNING",
    confidence=100,
    location=...,
    evidence=...,
    metadata=...
)
```

Rules should not create final prose-heavy issue objects.

---

# 15. Issue Generator

The issue generator converts rule findings into final audit issues.

Every issue should contain:

```text
rule_id
category
severity
title
issue
evidence
impact
recommendation
confidence
location
```

Example:

```json
{
  "rule_id": "MODEL_BIDIRECTIONAL",
  "category": "model",
  "severity": "WARNING",
  "title": "Bi-directional relationship detected",
  "issue": "A relationship uses bidirectional filter propagation.",
  "evidence": "Customer[CustomerID] → Sales[CustomerID], direction=Both",
  "impact": "Bidirectional propagation can increase model complexity and make filter behavior harder to reason about.",
  "recommendation": "Review whether bidirectional filtering is intentionally required. Prefer single-direction filtering when possible.",
  "confidence": 100,
  "location": "Customer[CustomerID] \u2194 Sales[CustomerID]"
}
```

### Issue schema — required vs. optional

```text
rule_id        required
category       required
severity       required
title           required
issue           required
evidence        required
impact          required
recommendation  required
confidence      required
location        optional
```

`location` is optional because some findings are report-wide rather
than tied to a single object. Examples of valid `location` values:

```text
Sales[CustomerID]
Customer[CustomerID] \u2194 Sales[CustomerID]
Measure: Total Sales
Page: Sales Overview
Page: Sales Overview / Visual: 7
```

### Confidence vs. severity — independent dimensions

Confidence represents detection confidence only (how sure the scanner
is that the condition exists), not business impact. Severity
represents how concerning the finding is if true. These are separate
axes and MUST NOT be multiplied together in v1 (e.g. no
`severity \u00d7 confidence` composite score). The v1 scoring formula
remains:

```text
Category Score = max(0, 100 - total deductions)
Overall Score  = weighted average of category scores
```

---

# 16. Recommendation System

Create:

```text
engine/recommendations.py
```

Recommendation mapping:

```text
rule_id → reviewed recommendation
```

Do not generate recommendations using an LLM in v1.

Do not allow arbitrary rule prose.

---

# 17. Severity Model

Use:

```text
CRITICAL
HIGH
MEDIUM
WARNING
ADVISORY
```

However, v1 rules use only:

```text
WARNING
MEDIUM
ADVISORY
```

Avoid pretending that every detection is a defect.

---

# 18. Confidence Model

Confidence represents confidence in the detection logic, not business impact.

Examples:

```text
100% → deterministic structural check
95%  → shallow structural dependency check
90%  → normalized duplicate logic
87%  → structural high-cardinality signal
70%  → structural date signal
65%  → suspicious DAX heuristic
60%  → fact-to-fact heuristic
```

Do not multiply confidence into the health score in v1.

---

# 19. Scoring Engine

Configuration:

```json
{
  "weights": {
    "model": 0.35,
    "dax": 0.25,
    "report": 0.20,
    "security": 0.20
  },
  "deductions": {
    "CRITICAL": 15,
    "HIGH": 10,
    "MEDIUM": 5,
    "WARNING": 3,
    "ADVISORY": 1,
    "LOW": 2
  },
  "thresholds": {
    "maxVisualsPerPage": 15,
    "maxSlicersPerPage": 6,
    "maxCalculatedColumnsPerTable": 4
  }
}
```

Note:

Security is reserved in configuration for future expansion. v1 does not need to invent security rules.

For categories that do not have findings, define clear behavior.

Recommended v1 behavior:

> Calculate the weighted score across categories that are actually present in the scanner's configured scoring scope.

Document the exact behavior in code and tests.

### Severity deduction configuration (mandatory)

The scoring configuration MUST define a deduction for every severity a
rule can emit. v1 rules emit only `MEDIUM`, `WARNING`, and `ADVISORY` —
`CRITICAL`, `HIGH`, and `LOW` remain supported values reserved for
future rules.

The scoring engine MUST NOT silently treat a missing or unknown
severity as a zero deduction. If an issue carries a severity that has
no entry in `deductions`, scoring MUST fail with a clear configuration
error rather than silently under-penalizing the finding.

---

# 20. Scoring Formula

Category:

```text
Category Score =
max(0, 100 - total deductions)
```

Overall:

```text
Overall Score =
weighted average of category scores
```

Do not use:

```text
Severity × Confidence × Impact × Scope
```

in v1.

Do not introduce mathematically complicated scoring without empirical calibration.

---

# 21. Golden Test Strategy

Golden fixtures must be created before trusting the rule engine.

There are 11 fixtures:

```text
test_bidirectional/
test_manytomany/
test_nodatetable/
test_highcardinality/
test_facttofact/
test_visualbloat/
test_slicerbloat/
test_duplicatedax/
test_expensive_dax/
test_unusedmeasure/
test_measure_referenced_by_another/
```

---

# 22. Golden Test Expectations

## Deterministic fixtures

Target rule:

```text
count == 1
```

And preferably:

```text
all unrelated rules == 0
```

Example:

```text
test_bidirectional
MODEL_BIDIRECTIONAL = 1
MODEL_MANY_TO_MANY = 0
MODEL_HIGH_CARDINALITY = 0
...
```

---

## Heuristic fixtures

Example:

```text
test_expensive_dax
DAX_SUSPICIOUS_PATTERN >= 1
confidence <= 65
```

Do not demand arbitrary exact confidence values if implementation details can legitimately change.

---

# 23. Critical Regression Fixture

This fixture is mandatory:

```text
test_measure_referenced_by_another/
```

Example:

```text
Measure A = SUM(Sales[Amount])

Measure B = [Measure A] / 100
```

Neither is directly bound to a visual in the fixture.

Expected:

```text
DAX_UNUSED_MEASURE = 0
```

This protects against accidentally reverting to:

```text
measure not in fields_used → unused
```

---

# 24. PBIP Extraction Strategy

`pbip_reader.py` should:

1. validate input path
2. identify PBIP structure
3. locate relevant files
4. parse JSON/TMDL/BIM where supported
5. preserve raw structures
6. return structured raw extraction data
7. report parsing errors clearly

It should not:

- run rules
- build health scores
- classify findings
- produce recommendations

---

# 25. Canonical Builder Strategy

Separate:

```text
Raw extraction
      ↓
Canonical builder
      ↓
CanonicalReport
```

This ensures the extractor remains an adapter.

The builder may interpret raw Power BI schema into canonical concepts.

Rules consume only:

```text
CanonicalReport
```

---

# 26. Error Handling

The scanner must distinguish:

```text
INPUT_ERROR
PARSE_ERROR
SCHEMA_ERROR
UNSUPPORTED_ARTIFACT
RULE_ERROR
RENDER_ERROR
CONFIG_ERROR
```

Do not silently swallow errors.

For optional PBIP properties:

```text
missing optional field
        ↓
safe default / None
        ↓
continue
```

For required structural information:

```text
missing required artifact
        ↓
clear actionable error
```

---

# 27. Logging

Provide useful levels:

```text
DEBUG
INFO
WARNING
ERROR
```

Example:

```text
INFO  Loading PBIP: Sales.pbip
INFO  Extracted 8 tables
INFO  Extracted 42 measures
INFO  Extracted 6 pages
INFO  Running 11 rules
INFO  Found 7 findings
INFO  Health score: 84
INFO  Report written: report.html
```

---

# 28. CLI

Target interface:

```bash
python -m pbiscan scan ./Sales.pbip
```

With configuration:

```bash
python -m pbiscan scan ./Sales.pbip \
  --config rules.config.json \
  --out report.html
```

Useful commands/options:

```text
scan
--config
--out
--format
--verbose
--quiet
```

Potential future commands should not be implemented in v1 unless needed.

---

# 29. HTML Report

The HTML report should be self-contained.

No backend server.

No database.

No external runtime dependency.

Use:

```text
Jinja2
HTML
CSS
small inline JavaScript only where necessary
```

---

# 30. HTML Report Structure

Recommended:

```text
┌─────────────────────────────────────────────┐
│ pbiscan                                     │
│ Power BI Report Quality Audit               │
├─────────────────────────────────────────────┤
│ Overall Health                              │
│                  84                         │
├──────────────┬──────────────┬───────────────┤
│ Model        │ DAX          │ Report        │
│ 88           │ 76           │ 91            │
├──────────────┴──────────────┴───────────────┤
│ Findings                                    │
│                                             │
│ WARNING  Bi-directional relationship        │
│ Evidence: ...                               │
│ Impact: ...                                 │
│ Recommendation: ...                         │
│ Confidence: 100%                            │
└─────────────────────────────────────────────┘
```

Include filtering by:

- category
- severity
- rule
- page/table where available

---

# 31. HTML Report Requirements

Must include:

- report name
- scan timestamp
- scanner version
- overall score
- category scores
- finding counts
- severity counts
- issue details
- evidence
- impact
- recommendation
- confidence
- location
- rule ID

---

# 32. Versioning

Use semantic versioning.

Initial:

```text
0.x → development
1.0.0 → stable static scanner
```

The scanner should expose its version in CLI/report output.

---

# 33. Packaging

Use `pyproject.toml`.

Target:

```bash
pip install .
```

And eventually:

```bash
pipx install .
```

Command:

```bash
pbiscan scan ./Sales.pbip
```

The module invocation should also work:

```bash
python -m pbiscan scan ./Sales.pbip
```

---

# 34. Testing Layers

## Unit tests

Test:

- canonical objects
- individual rules
- normalization
- reference scanning
- scoring
- recommendation mapping

## Integration tests

Test:

```text
PBIP
 ↓
Extraction
 ↓
Canonical model
 ↓
Rules
 ↓
Issue generation
 ↓
Scoring
 ↓
Report
```

## Golden tests

Test known PBIP fixtures.

## Regression tests

Every discovered bug should receive a regression fixture/test.

---

# 35. Development Order

Follow this exact order for v1.

## Step 1

Verify repository scaffolding.

## Step 2

Verify `canonical/model.py`.

## Step 3

Verify issue/recommendation contracts.

## Step 4

Verify model rules.

## Step 5

Verify DAX rules.

## Step 6

Verify report rules.

## Step 7

Implement `extraction/pbip_reader.py`.

## Step 8

Implement canonical builders.

## Step 9

Create golden PBIP fixtures.

## Step 10

Implement pytest suite.

## Step 11

Fix all extraction/rule regressions.

## Step 12

Implement scoring.

## Step 13

Implement HTML renderer.

## Step 14

Implement CLI integration.

## Step 15

Run scanner against a real PBIP.

## Step 16

Review every finding manually.

## Step 17

Lock v1.0.

---

# 36. v1 Ship Gate

Do not call v1 complete until all are true:

```text
[ ] PBIP extraction works
[ ] Canonical model is populated correctly
[ ] All 11 rules execute
[ ] All 11 golden fixtures pass
[ ] Critical negative fixture passes
[ ] No rule imports extraction code
[ ] No rule contains recommendation prose
[ ] Scoring is config-driven
[ ] CLI works
[ ] HTML works
[ ] Recommendations manually reviewed
[ ] Real PBIP validated
[ ] No unexpected network/LLM dependency
[ ] Documentation updated
```

---

# 37. v1.1 Roadmap — Deeper Static Intelligence

After v1 is stable:

## DAX dependency graph

Move beyond shallow references.

Detect:

- dependency chains
- circular dependencies
- dependency depth
- highly reused measures
- dependency hotspots

## Model topology

Detect:

- disconnected tables
- ambiguous paths
- bridge patterns
- complex relationship paths
- better fact-to-fact analysis

## Governance

Add configurable rules for:

- naming
- descriptions
- display folders
- hidden objects
- documentation
- modeling conventions

## Issue lifecycle

Introduce:

```text
OPEN
ACKNOWLEDGED
SUPPRESSED
RESOLVED
```

Do not implement these during v1.

---

# 38. v1.5 — PBIX Support

Add:

```text
extraction/pbix_reader.py
```

Architecture:

```text
PBIP ──→ PBIP Reader ──┐
                       │
                       ▼
                Canonical Model
                       ▲
                       │
PBIX ──→ PBIX Reader ──┘
```

Rules remain unchanged.

This validates the architecture.

---

# 39. v2 — Runtime Analysis

Introduce:

```text
runtime/
├── connection.py
├── tom_client.py
├── xmla_client.py
├── dmv.py
└── vertipaq.py
```

Capabilities:

- TOM/XMLA
- DMV queries
- model metadata validation
- cardinality
- storage size
- partitions
- VertiPaq statistics

The runtime layer should enrich canonical/runtime evidence rather than rewrite static rules.

---

# 40. v2.1 — Real Performance Analysis

Add:

- Server Timings
- Formula Engine time
- Storage Engine time
- query duration
- SE query counts
- repeated scans
- expensive measures
- runtime performance evidence

Distinguish clearly:

```text
STATIC SIGNAL
```

from:

```text
RUNTIME EVIDENCE
```

---

# 41. v2.5 — Baseline and Regression

Persist scan results.

Example:

```text
Scan 001
Health: 91

Scan 002
Health: 86
```

Detect:

- new issues
- resolved issues
- score regression
- model-size regression
- DAX performance regression
- relationship changes
- visual changes

---

# 42. v3 — LLM Intelligence

LLM is introduced only after the evidence pipeline is reliable.

Architecture:

```text
PBIP / Runtime
      ↓
Evidence Engine
      ↓
Structured Findings
      ↓
LLM
      ↓
Explanation
```

LLM capabilities:

- explain technical findings
- explain business impact
- summarize report health
- prioritize findings
- contextualize recommendations
- answer questions about scan results

---

# 43. LLM Safety Boundary

The LLM must not directly mutate the report.

The LLM receives structured evidence.

Example:

```json
{
  "rule_id": "DAX_SUSPICIOUS_PATTERN",
  "confidence": 65,
  "evidence": "...",
  "runtime_metrics": {}
}
```

The LLM may say:

> This measure is worth reviewing because...

It must not claim:

> This measure definitely causes performance problems

unless runtime evidence supports that statement.

---

# 44. v3.1 — LLM DAX Reasoning

Provide the LLM with:

```text
DAX expression
Measure dependencies
Model relationships
Static findings
Runtime evidence
```

Capabilities:

- explain DAX
- identify potential bottlenecks
- explain context transitions
- explain filter propagation
- suggest alternatives

---

# 45. v3.2 — AI Remediation

Architecture:

```text
Finding
   ↓
LLM
   ↓
Proposed change
   ↓
Validation
   ↓
Diff
   ↓
Human approval
   ↓
Apply
```

Never directly apply an LLM-generated change without validation.

---

# 46. v4 — CI/CD Integration

Example:

```text
Git commit
    ↓
PBIP changed
    ↓
pbiscan
    ↓
Quality gate
```

Possible rules:

```text
overall score >= 80
no new critical findings
no new high findings
performance regression < 20%
```

Integrations may eventually include:

- GitHub Actions
- Azure DevOps
- other CI systems

---

# 47. v5 — Developer Experience

Potential integrations:

- VS Code
- GitHub pull requests
- Azure DevOps pull requests
- command-line workflows

Example PR comment:

```text
pbiscan result

Health: 84 → 79

New:
1 WARNING
2 MEDIUM

Performance:
+18%

Status:
PASS WITH WARNINGS
```

---

# 48. v6 — Enterprise Platform

Only build this if the scanner proves valuable.

Potential architecture:

```text
                    pbiscan Platform
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
    Scanner API       Web Dashboard       CI/CD
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                           ▼
                       Database
```

Potential features:

- users
- teams
- projects
- reports
- scan history
- ownership
- issue lifecycle
- permissions
- audit history
- dashboards

---

# 49. LLM Position in the Product

Final strategic position:

```text
                    v1
                     │
                     │ NO LLM
                     ▼
            Static evidence engine
                     │
                     ▼
                    v1.1
             Deeper static analysis
                     │
                     ▼
                    v2
              Runtime evidence
                     │
                     ▼
             Historical analysis
                     │
                     ▼
                    v3
                  LLM layer
```

The LLM is an intelligence layer, not the foundation.

---

# 50. Long-Term Product Architecture

The eventual architecture should look like:

```text
                         Power BI Artifacts
                       /        |         \
                    PBIP       PBIX      Runtime
                      \         |         /
                       \        |        /
                        ▼       ▼       ▼
                    Artifact Adapters
                            │
                            ▼
                    Canonical Model
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
          Static Rules   Runtime Rules   Graph Engine
              │             │             │
              └─────────────┼─────────────┘
                            ▼
                     Evidence Engine
                            │
                            ▼
                    Issue / Score Engine
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
             CLI           HTML          API
                            │
                            ▼
                         LLM Layer
                            │
                            ▼
                   Remediation Engine
                            │
                            ▼
                       CI/CD Gates
```

---

# 51. Engineering Principles

The implementation agent must follow these principles.

## Principle 1

Prefer correctness over feature count.

## Principle 2

Prefer evidence over assumptions.

## Principle 3

Never present heuristics as facts.

## Principle 4

Keep extraction independent from analysis.

## Principle 5

Keep rules independent from presentation.

## Principle 6

Keep recommendations independent from detection.

## Principle 7

Keep configuration outside rule code.

## Principle 8

Every bug discovered must become a regression test.

## Principle 9

Do not introduce an LLM just because a task can be solved with an LLM.

## Principle 10

Do not add future-phase functionality early.

---

# 52. What the Build Agent Must NOT Do

During v1, the implementation agent must not:

- add OpenAI/Claude/Gemini/Ollama dependencies
- call external LLM APIs
- implement autonomous remediation
- add XMLA
- add TOM
- add VertiPaq runtime analysis
- add SaaS infrastructure
- add authentication
- add a database
- implement CI/CD
- add PBIX before PBIP is proven
- add speculative rules without tests
- put recommendation prose inside rules
- bypass the canonical model
- hardcode scoring thresholds inside rule functions

If the agent believes a future feature is necessary, it should document the reason rather than silently expanding scope.

---

# 53. Definition of Done for Every Rule

A rule is not complete until it has:

```text
[ ] Stable rule ID
[ ] Category
[ ] Severity
[ ] Detection logic
[ ] Confidence
[ ] Evidence structure
[ ] Reviewed recommendation
[ ] Positive fixture
[ ] Negative behavior tested
[ ] Unit test
[ ] Integration test where applicable
[ ] Documentation
```

---

# 54. Definition of Done for v1

```text
PBIP
 ↓
Extraction
 ↓
Canonical Model
 ↓
11 Rules
 ↓
11 Golden Fixtures
 ↓
Issue Generator
 ↓
Scoring
 ↓
HTML
 ↓
CLI
 ↓
Real PBIP Validation
```

All stages must work together.

The scanner must be usable without an LLM or internet connection.

---

# 55. Immediate Implementation Task

The implementation agent should begin from the current repository state.

Current completed components:

```text
canonical/model.py
engine/issue.py
engine/recommendations.py
rules/model.py
rules/dax.py
rules/report.py
```

Next implementation priority:

```text
1. extraction/pbip_reader.py
2. canonical builders
3. golden PBIP fixtures
4. pytest suite
5. integration pipeline
6. scoring.py
7. HTML renderer
8. CLI
9. real PBIP validation
```

Do not rewrite completed components unless tests demonstrate a concrete defect.

---

# 56. Agent Execution Protocol

The coding agent should work incrementally.

For each task:

```text
1. Inspect existing repository.
2. Inspect existing implementation.
3. Identify the smallest required change.
4. Implement.
5. Add/update tests.
6. Run tests.
7. Fix failures.
8. Report changed files.
9. Report test results.
10. Continue to the next task only when the current task is stable.
```

The agent must not claim completion without running the relevant tests.

---

# 57. Final Product Roadmap

| Phase | Capability | LLM |
|---|---|---:|
| v0.1 | Foundation and architecture | No |
| v1.0 | PBIP static scanner + 11 rules | No |
| v1.1 | DAX dependency + topology + governance | No |
| v1.5 | PBIX adapter | No |
| v2.0 | TOM/XMLA + VertiPaq | No |
| v2.1 | Runtime DAX performance | No |
| v2.5 | Baseline/regression | No |
| v2.6 | Issue lifecycle | No |
| v3.0 | LLM explanations | Yes |
| v3.1 | LLM DAX/model reasoning | Yes |
| v3.2 | AI remediation proposals | Yes |
| v4.0 | CI/CD + developer integrations | Optional |
| v5.0 | Enterprise platform | Yes/Optional |

---

# 58. Final Rule

The most important rule for the entire project:

> **Do not build the AI before building the evidence.**

`pbiscan v1` must first prove that it can reliably answer:

```text
What is wrong or potentially concerning?
Where is it?
What evidence supports it?
How confident are we?
What should a developer review?
How much does it affect the health score?
```

Only after those answers are trustworthy should an LLM be allowed to explain or reason over them.

---

# 59. Final v1 Target

The first successful release is:

```text
                 PBIP
                  │
                  ▼
            pbiscan scan
                  │
                  ▼
         ┌─────────────────┐
         │  Static Engine  │
         │                 │
         │   11 Rules      │
         └────────┬────────┘
                  │
                  ▼
           Evidence Issues
                  │
                  ▼
            Health Score
                  │
             ┌────┴────┐
             ▼         ▼
            CLI       HTML
```

Expected user experience:

> Give `pbiscan` a PBIP → get a trustworthy, explainable Power BI quality audit.

That is the **locked v1 objective**.
