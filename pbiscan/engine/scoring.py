"""Scoring engine — config-driven health score calculation.

Formula:
    Category Score = max(0, 100 - total_deductions)
    Overall Score  = weighted average of active category scores

Architecture decisions (v1):
    - Security category is EXCLUDED from weighted average when no security
      rules fire (Option A per design decision). This avoids artificially
      inflating scores with a perfect security score.
    - CRITICAL/HIGH/LOW deductions are defined in config but not used by v1
      rules. They are validated to ensure future rules work correctly.
    - Missing severity in config raises ConfigError (spec §19 requirement).
"""
from __future__ import annotations

import json
from pathlib import Path


class ConfigError(Exception):
    """Raised when the scoring configuration is invalid or incomplete."""
    error_type = "CONFIG_ERROR"


# Categories scored in v1 (security reserved for future)
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
        Integer score 0–100 (clamped at 0 from below).

    Raises:
        ConfigError: if an issue's severity has no deduction entry in config.
    """
    cat_issues = [i for i in issues if i.category == category]
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
    Weights are normalised against active categories (so excluding security
    does not cap the max score at 80).

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
    total_weight = sum(active_weights.values())
    if total_weight == 0:
        return 100.0

    weighted_sum = sum(
        category_scores[cat] * (w / total_weight)
        for cat, w in active_weights.items()
    )
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
