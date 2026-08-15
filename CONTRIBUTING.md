# Contributing to pbiscan

We welcome contributions to `pbiscan`, whether it's adding new rules, improving TMDL/PBIR parsing, or refining developer documentation.

---

## Architecture Principles

`pbiscan` relies on a few core design constraints to keep the scanner fast, predictable, and maintainable:

1. **Extraction Decoupling**: Rules in `pbiscan/rules/` only inspect the typed dataclasses in `pbiscan.canonical.model`. They must never import from or interact directly with `pbiscan.extraction`.
2. **Prose Separation**: Rule functions only perform detection logic and return `RuleFinding` instances with structural evidence. All user-facing explanations, impact descriptions, and fix recommendations belong in `pbiscan/engine/recommendations.py`.
3. **External Independence**: `pbiscan` operates strictly on local project files. It does not invoke runtime engines, external network endpoints, or cloud services.
4. **Config-Driven Weights**: Scoring penalties and thresholds are loaded from `rules.config.json` rather than hardcoded in rule definitions.

---

## Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/KULLOLLITARUN/pbiscan.git
cd pbiscan

# 2. Set up virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1

# 3. Install in editable mode with development dependencies
pip install -e ".[dev]"

# 4. Run tests
pytest
```

---

## Adding a New Rule

1. **Implement Detection Logic**:
   Add your check to the appropriate category module (`pbiscan/rules/model.py`, `dax.py`, or `report.py`):
   ```python
   def check_example_rule(report: CanonicalReport) -> list[RuleFinding]:
       findings = []
       # Evaluate conditions against report.model, report.dax, or report.report
       return findings
   ```

2. **Register Recommendation Text**:
   Add an entry in `pbiscan/engine/recommendations.py`:
   ```python
   "CATEGORY_RULE_NAME": {
       "title": "Short descriptive title",
       "issue": "Specific condition detected in the model or report.",
       "impact": "Why this condition matters in Power BI.",
       "recommendation": "Actionable guidance on how to address it.",
   }
   ```

3. **Register the Rule**:
   Append your function to `MODEL_RULES`, `DAX_RULES`, or `REPORT_RULES`.

4. **Add Tests**:
   - Add unit tests in `tests/unit/` testing true-positive and false-positive edge cases.
   - Add a golden PBIP fixture in `tests/golden/` if applicable.

---

## Submitting Pull Requests

- Ensure `pytest` passes with 100% success.
- Follow PEP 8 conventions and maintain strict type annotations where applicable.
- Keep PRs focused on a single feature, bugfix, or rule addition.
