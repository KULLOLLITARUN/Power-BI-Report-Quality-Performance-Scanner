"""Scoring engine — config-driven health score calculation.

Formula:
    Category Score = max(0, 100 - total_deductions)
    Overall Score  = weighted average of active category scores

Architecture decisions:
    - Only model, dax and report are scored. Their weights are renormalised
      so the maximum overall score is 100; weights for any other key (such as
      "security" in older configs) are ignored.
    - Severities emitted by current rules: HIGH, MEDIUM, WARNING, ADVISORY.
      CRITICAL and LOW stay in the severity vocabulary because diff quality
      gates (--fail-on-new), SARIF and imported JSON artifacts use them, so
      they keep deduction entries.
    - Missing severity in config raises ConfigError (spec §19 requirement).
"""
from __future__ import annotations

import json
from pathlib import Path


class ConfigError(Exception):
    """Raised when the scoring configuration is invalid or incomplete."""
    error_type = "CONFIG_ERROR"


# Scored categories
_SCORED_CATEGORIES = ("model", "dax", "report")


def load_config(config_path: str | Path) -> dict:
    """Load and validate rules.config.json.

    Raises ConfigError if required keys are missing.
    """
    path = Path(config_path)
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise ConfigError(f"Cannot load config from {path}: {exc}") from exc

    # Validate required keys
    for key in ("weights", "deductions", "thresholds"):
        if key not in raw:
            raise ConfigError(f"Missing required config key: '{key}' in {path}")

    return raw


def score_category(issues: list, category: str, deductions: dict[str, int]) -> int:
    """Calculate the health score for a single category.

    Args:
        issues:     list of AuditIssue objects for ALL categories
        category:   the category to score ('model', 'dax', 'report')
        deductions: severity → deduction points mapping from config

    Returns:
        Integer score 0–100 (clamped at 0 from below). Suppressed issues
        (suppressed=True) are excluded from deductions.

    Raises:
        ConfigError: if an issue's severity has no deduction entry in config.
    """
    cat_issues = [
        i for i in issues 
        if i.category == category and not getattr(i, "suppressed", False)
    ]
    total = 0
    for issue in cat_issues:
        sev = issue.severity
        if sev not in deductions:
            raise ConfigError(
                f"Severity '{sev}' has no deduction entry in rules.config.json. "
                "Add it to the 'deductions' section before running. "
                "(The scoring engine must not silently treat missing severities as 0.)"
            )
        total += deductions[sev]
    return max(0, 100 - total)


def score_overall(
    category_scores: dict[str, int],
    weights: dict[str, float],
    active_categories: tuple[str, ...] = _SCORED_CATEGORIES,
) -> float:
    """Calculate the overall weighted health score.

    Only categories in `active_categories` are included.
    Weights are normalised against active categories, so the maximum is
    always 100 regardless of the raw weight total.

    Args:
        category_scores:   category → integer score
        weights:           category → weight (from config)
        active_categories: tuple of category names to include

    Returns:
        Float overall score 0.0–100.0, rounded to 1 decimal place.
    """
    active_weights = {
        cat: weights.get(cat, 0.0)
        for cat in active_categories
        if cat in category_scores
    }
    # Plain left-to-right float additions, not sum(): Python 3.12 made sum()
    # use compensated summation, which can change the last digit between
    # Python versions. clientScanner.ts repeats exactly these operations.
    total_weight = 0.0
    for w in active_weights.values():
        total_weight += w
    if total_weight == 0:
        return 100.0

    weighted_sum = 0.0
    for cat, w in active_weights.items():
        weighted_sum += category_scores[cat] * (w / total_weight)
    return round(weighted_sum, 1)


def calculate_scores(issues: list, config: dict) -> dict:
    """Run the full scoring pipeline.

    Args:
        issues: list of AuditIssue objects
        config: parsed rules.config.json dict

    Returns:
        {
            "category_scores": {"model": int, "dax": int, "report": int},
            "overall": float,
        }
    """
    deductions = config["deductions"]
    weights = config["weights"]

    category_scores = {
        cat: score_category(issues, cat, deductions)
        for cat in _SCORED_CATEGORIES
    }

    overall = score_overall(category_scores, weights, _SCORED_CATEGORIES)

    return {
        "category_scores": category_scores,
        "overall": overall,
    }
