# Contributing to pbiscan

Thank you for your interest in contributing to `pbiscan`!

`pbiscan` is built on a strict, modular contract architecture to guarantee deterministic, reproducible, and noise-free static analysis for Power BI projects.

---

## 🏛 Architectural Contracts

When submitting rules or modifying existing components, please adhere to these core design rules:

1. **Extraction Decoupling**: Rule functions (`pbiscan/rules/`) must **only** import from `pbiscan.canonical.model` and never from `pbiscan.extraction`.
2. **Prose Separation**: Rule functions must return detection data only (`RuleFinding`). Never hardcode recommendation prose inside rule functions. All developer recommendations belong in `pbiscan/engine/recommendations.py`.
3. **Config-Driven Scoring**: Thresholds, deductions, and category weights live in `rules.config.json` — never hardcode numerical penalties in rule logic.
4. **Deterministic Analysis**: `pbiscan` operates strictly on local project artifacts (`.pbip`, TMDL, TMSL, PBIR). No external API calls, runtime connections, or LLMs.

---

## 🛠 Local Development Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-username/pbiscan.git
cd pbiscan

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1

# 3. Install in editable mode with development dependencies
pip install -e ".[dev]"

# 4. Run the test suite
pytest
```

---

## ➕ Adding a New Rule

To add a new quality rule (e.g. `M006` or `D005`):

1. **Define the Rule Function** in `pbiscan/rules/<category>.py`:
   ```python
   def check_my_new_rule(report: CanonicalReport) -> list[RuleFinding]:
       findings = []
       # Detection logic using canonical report only
       return findings
   ```
2. **Register the Recommendation** in `pbiscan/engine/recommendations.py`:
   ```python
   "MY_NEW_RULE_ID": {
       "title": "Short Title",
       "issue": "What was detected.",
       "impact": "Why this matters in Power BI.",
       "recommendation": "What the developer should review or change.",
   }
   ```
3. **Register the Function** in the category rule list (`MODEL_RULES`, `DAX_RULES`, or `REPORT_RULES`).
4. **Add Unit & Golden Tests** in `tests/unit/` and `tests/golden/`.

---

## 🧪 Testing Checklist

Before opening a Pull Request:
- [ ] Run `pytest` and ensure all 111+ tests pass without errors.
- [ ] Run `pbiscan scan <fixture>` against golden fixtures to verify CLI output.
- [ ] Ensure any new rule includes both positive and negative test cases.

---

## 📄 License

By contributing to `pbiscan`, you agree that your contributions will be licensed under the [MIT License](LICENSE).
