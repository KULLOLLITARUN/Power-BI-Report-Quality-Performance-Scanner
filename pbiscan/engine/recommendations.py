"""Recommendation registry — manually reviewed text for every v1 rule.

All entries have been reviewed for Power BI / DAX semantic correctness
per Contract 4 of the build specification.

Structure per entry:
    rule_id → {
        "title":          short display title (≤60 chars)
        "issue":          one-sentence description of the detected condition
        "impact":         why this matters in Power BI (2–4 sentences)
        "recommendation": what the developer should review or do (2–4 sentences)
    }

Do NOT:
  - generate recommendations dynamically
  - allow arbitrary prose from rule functions
  - add entries without manual review
"""
from __future__ import annotations

RECOMMENDATIONS: dict[str, dict[str, str]] = {

    # ------------------------------------------------------------------
    # MODEL rules
    # ------------------------------------------------------------------

    "MODEL_BIDIRECTIONAL": {
        "title": "Bi-directional relationship detected",
        "issue": (
            "A relationship uses bidirectional cross-filter propagation."
        ),
        "impact": (
            "Bidirectional propagation can increase model complexity, make "
            "filter behaviour harder to reason about, and may introduce "
            "ambiguous filter paths when multiple such relationships exist "
            "in the same model. It can also create circular dependency "
            "risks in larger schemas."
        ),
        "recommendation": (
            "Review whether bidirectional filtering is intentionally required "
            "for this relationship. Prefer single-direction filtering where "
            "possible. If bidirectional filtering is needed for specific "
            "measures, consider using CROSSFILTER() within those measures "
            "rather than enabling it at the relationship level."
        ),
    },

    "MODEL_MANY_TO_MANY": {
        "title": "Many-to-many relationship detected",
        "issue": (
            "A relationship has many-to-many (M:M) cardinality."
        ),
        "impact": (
            "Many-to-many relationships can produce unexpected aggregation "
            "behaviour, make DAX more difficult to write correctly, and may "
            "degrade query performance when large fact tables are involved. "
            "They are sometimes used intentionally (e.g. shared dimension "
            "patterns) but require careful validation."
        ),
        "recommendation": (
            "Review whether the many-to-many cardinality is intentionally "
            "required. Consider whether an intermediate bridge table or a "
            "shared dimension table would produce clearer model semantics. "
            "Validate that measure results are correct when this relationship "
            "is active."
        ),
    },

    "MODEL_NO_DATE_TABLE": {
        "title": "Potential date dimension concern",
        "issue": (
            "No table appears to be marked or identified as a date dimension "
            "in the model."
        ),
        "impact": (
            "Without a proper date table, Power BI cannot use optimised "
            "time-intelligence functions correctly. Auto date/time may be "
            "active, which increases model size and can produce unexpected "
            "hierarchy behaviour. This is a structural signal — actual impact "
            "depends on report requirements."
        ),
        "recommendation": (
            "Review whether the model contains a dedicated date dimension "
            "table. If it does, ensure it is marked as a Date Table via "
            "Table Tools → Mark as Date Table in Power BI Desktop. Consider "
            "disabling Auto date/time in File → Options if a manual date "
            "table is in use."
        ),
    },

    "MODEL_HIGH_CARDINALITY": {
        "title": "Potential high-cardinality column",
        "issue": (
            "A column shows structural signals suggesting high cardinality "
            "(string type, unique-value indicators, identifier-like naming, "
            "not participating in a relationship)."
        ),
        "impact": (
            "High-cardinality text columns can significantly increase the "
            "VertiPaq dictionary size and overall model memory footprint. "
            "This is a static structural signal only — actual memory impact "
            "can only be confirmed through runtime VertiPaq analysis."
        ),
        "recommendation": (
            "Review whether this column needs to be imported into the model. "
            "If it is used only as a unique row identifier, consider excluding "
            "it from the import query. If it must be present, evaluate whether "
            "the data type can be changed to an integer surrogate key, which "
            "compresses significantly better than strings."
        ),
    },

    "MODEL_FACT_TO_FACT": {
        "title": "Potential fact-to-fact relationship",
        "issue": (
            "A relationship between two tables shows structural signals "
            "suggesting both may be fact tables (both contain measures and "
            "neither has a dimension naming pattern)."
        ),
        "impact": (
            "Direct fact-to-fact relationships are not natively supported in "
            "Power BI star-schema modelling and are often a modelling error. "
            "Filter propagation may not behave as expected. This is a "
            "heuristic detection — review is required to confirm."
        ),
        "recommendation": (
            "Review the relationship and confirm the intended role of each "
            "table. If both are truly fact tables, consider introducing a "
            "shared dimension or bridge table to mediate the relationship. "
            "Validate measure results to confirm filter behaviour is correct."
        ),
    },

    # ------------------------------------------------------------------
    # DAX rules
    # ------------------------------------------------------------------

    "DAX_SUSPICIOUS_PATTERN": {
        "title": "Suspicious DAX pattern detected",
        "issue": (
            "A measure expression contains a DAX pattern commonly associated "
            "with potential performance concerns."
        ),
        "impact": (
            "These patterns are worth reviewing but cannot be confirmed as "
            "performance problems without runtime analysis. Context and intent "
            "matter — not every instance of these patterns is a defect. Only "
            "Server Timings data can confirm actual performance impact."
        ),
        "recommendation": (
            "Review the flagged measure. Consider whether FILTER(ALL(...)) "
            "can be rewritten using CALCULATE with explicit filter arguments, "
            "or whether EARLIER() can be replaced with a VAR/RETURN pattern. "
            "Nested CALCULATE() calls should be checked for unintended "
            "context-transition side effects."
        ),
    },

    "DAX_EXCESSIVE_CALC_COLUMNS": {
        "title": "Excessive calculated columns on table",
        "issue": (
            "A table contains more calculated columns than the configured "
            "threshold."
        ),
        "impact": (
            "Calculated columns are materialised at refresh time and stored "
            "in VertiPaq compressed memory. A large number increases refresh "
            "duration, model size, and can reduce VertiPaq compression "
            "efficiency on adjacent columns."
        ),
        "recommendation": (
            "Review whether calculated columns can be moved upstream to the "
            "data source (Power Query / SQL / dataflow) where they are "
            "computed before import. Prefer DAX measures over calculated "
            "columns for values used only in report visuals."
        ),
    },

    "DAX_DUPLICATE_MEASURE": {
        "title": "Duplicate measure logic detected",
        "issue": (
            "Two or more measures have normalised expressions that are "
            "identical, indicating possible duplicate logic."
        ),
        "impact": (
            "Duplicate measure logic creates maintenance overhead — updating "
            "business rules requires updating all copies. It may also cause "
            "confusion for report authors navigating the field list. Confidence "
            "is 90% as normalisation may occasionally produce false positives."
        ),
        "recommendation": (
            "Review the flagged measures. If they are genuinely identical, "
            "consider consolidating into a single canonical measure and "
            "removing the duplicate. Be cautious — table placement, naming "
            "conventions, or display folder requirements may legitimately "
            "justify separate measures with the same logic."
        ),
    },

    "DAX_UNUSED_MEASURE": {
        "title": "Potentially unused measure",
        "issue": (
            "A measure does not appear to be used by any report visual and "
            "is not referenced by any other measure in the model."
        ),
        "impact": (
            "Unused measures add unnecessary complexity to the model, making "
            "the field list harder to navigate for report authors. They are "
            "still validated and compiled at refresh time."
        ),
        "recommendation": (
            "Verify whether the measure is used in hidden visuals, bookmarks, "
            "subscriptions, or external tools (Analyse in Excel, paginated "
            "reports, XMLA endpoints). If it is genuinely unused, consider "
            "removing it to reduce model complexity. Confidence is 95% — "
            "confirm before deleting."
        ),
    },

    # ------------------------------------------------------------------
    # REPORT rules
    # ------------------------------------------------------------------

    "REPORT_VISUAL_BLOAT": {
        "title": "Excessive visuals on page",
        "issue": (
            "A report page contains more visuals than the configured threshold."
        ),
        "impact": (
            "Pages with many visuals issue more DAX queries per render, "
            "increasing initial load time and interaction latency. Dense "
            "pages also reduce readability and can overwhelm report consumers."
        ),
        "recommendation": (
            "Review the page layout and consider splitting content across "
            "multiple focused pages. Use bookmarks or drill-through pages "
            "to surface detail on demand rather than displaying everything "
            "simultaneously. A tooltip page pattern can also reduce density."
        ),
    },

    "REPORT_SLICER_BLOAT": {
        "title": "Excessive slicers on page",
        "issue": (
            "A report page contains more slicers than the configured threshold."
        ),
        "impact": (
            "Each slicer issues its own DAX query on page load and on every "
            "cross-filter interaction. Pages with many slicers produce high "
            "query volumes, increasing render time and Premium / Fabric "
            "capacity utilisation."
        ),
        "recommendation": (
            "Consider consolidating slicers using a collapsible filter pane, "
            "a dedicated slicer page with bookmarks, or a pop-out panel "
            "pattern. Review whether all slicers are necessary or whether "
            "some filters can be applied at the page or report level instead."
        ),
    },
}


def get_recommendation(rule_id: str) -> dict[str, str]:
    """Return the recommendation entry for a given rule_id.

    Raises KeyError if rule_id is not registered.
    This is intentional: unreviewed rules must not silently emit empty text.
    """
    if rule_id not in RECOMMENDATIONS:
        raise KeyError(
            f"No recommendation registered for rule_id '{rule_id}'. "
            "All v1 rule IDs must have a manually reviewed entry in "
            "engine/recommendations.py before they can emit findings."
        )
    return RECOMMENDATIONS[rule_id]
