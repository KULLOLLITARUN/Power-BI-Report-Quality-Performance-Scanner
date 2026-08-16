"""Calculation Group Semantic Reference Extractor (v1.4 Producer).

Extracts semantic measure references from Calculation Group tables and Calculation Items:
- Explicit [MeasureName] references inside calculation item DAX formulas.
- Introspection predicates: ISSELECTEDMEASURE([MeasureName]) and SELECTEDMEASURENAME().
- formatStringDefinition expressions referencing measures.
"""

from __future__ import annotations

import re
from typing import Any

from pbiscan.canonical.references import SemanticReference


# Regex patterns for calculation item DAX parsing
_BRACKET_REF_PATTERN = re.compile(
    r"(?:'([^']+)'|\b([a-zA-Z_][a-zA-Z0-9_]*))?\[([^\]]+)\]",
    re.IGNORECASE,
)
_ISSELECTEDMEASURE_PATTERN = re.compile(
    r"\bISSELECTEDMEASURE\s*\(\s*(?:'([^']+)'\s*|([a-zA-Z_][a-zA-Z0-9_]*)\s*)?\[([^\]]+)\]",
    re.IGNORECASE,
)
_SELECTEDMEASURENAME_PATTERN = re.compile(
    r"\bSELECTEDMEASURENAME\s*\(\s*\)\s*(?:==?|=)\s*\"([^\"]+)\"",
    re.IGNORECASE,
)

# Reserved keywords and column aliases inside calculation groups to ignore
_IGNORED_BRACKET_NAMES = {
    "name", "value", "value1", "value2", "value3", "value4", "ordinal",
    "selectedmeasure", "selectedmeasureformatstring",
}


def extract_calc_group_references(
    table_name: str,
    calc_items: list[dict[str, Any]],
    source_file: str = "",
) -> list[SemanticReference]:
    """Extract semantic references from a calculation group's calculation items.

    Args:
        table_name: Name of the calculation group table (e.g., "TimeCalcGroup").
        calc_items: List of dicts representing calculation items, e.g.:
                    [{"name": "vs Budget %", "expression": "...", "format_string": "..."}]
        source_file: Relative filepath for provenance audit.

    Returns:
        List of discovered SemanticReference records.
    """
    references: list[SemanticReference] = []

    for item in calc_items:
        item_name = item.get("name", "UnknownItem")
        item_dax = item.get("expression", "") or ""
        format_dax = item.get("format_string", "") or item.get("format_string_definition", "") or ""
        source_obj = f"{table_name}['{item_name}']"

        # 1. Check ISSELECTEDMEASURE([Measure]) predicates
        for match in _ISSELECTEDMEASURE_PATTERN.finditer(item_dax):
            tbl_quoted, tbl_unquoted, meas_name = match.groups()
            target_tbl = tbl_quoted or tbl_unquoted
            if meas_name.strip().lower() not in _IGNORED_BRACKET_NAMES:
                references.append(
                    SemanticReference(
                        target_name=meas_name.strip(),
                        target_table=target_tbl,
                        target_type="measure",
                        source_type="calc_item_predicate",
                        source_object=source_obj,
                        source_file=source_file,
                        source_expression=match.group(0),
                        activates_root=True,
                        confidence=100,
                    )
                )

        # 2. Check SELECTEDMEASURENAME() == "MeasureName" predicates
        for match in _SELECTEDMEASURENAME_PATTERN.finditer(item_dax):
            meas_name = match.group(1).strip()
            if meas_name.lower() not in _IGNORED_BRACKET_NAMES:
                references.append(
                    SemanticReference(
                        target_name=meas_name,
                        target_table=None,
                        target_type="measure",
                        source_type="calc_item_predicate",
                        source_object=source_obj,
                        source_file=source_file,
                        source_expression=match.group(0),
                        activates_root=True,
                        confidence=100,
                    )
                )

        # 3. Extract explicit bracket references from calculation item DAX
        # Note: Avoid double-counting matches already captured by ISSELECTEDMEASURE
        for match in _BRACKET_REF_PATTERN.finditer(item_dax):
            tbl_quoted, tbl_unquoted, prop_name = match.groups()
            prop_clean = prop_name.strip()
            if prop_clean.lower() in _IGNORED_BRACKET_NAMES:
                continue

            # Check if this bracket is part of ISSELECTEDMEASURE
            prefix = item_dax[max(0, match.start() - 25) : match.start()]
            if "ISSELECTEDMEASURE" in prefix.upper():
                continue

            target_tbl = tbl_quoted or tbl_unquoted
            references.append(
                SemanticReference(
                    target_name=prop_clean,
                    target_table=target_tbl,
                    target_type="measure",
                    source_type="calc_item_dax",
                    source_object=source_obj,
                    source_file=source_file,
                    source_expression=match.group(0),
                    activates_root=True,
                    confidence=100,
                )
            )

        # 4. Extract bracket references from format string DAX definition
        if format_dax:
            for match in _BRACKET_REF_PATTERN.finditer(format_dax):
                tbl_quoted, tbl_unquoted, prop_name = match.groups()
                prop_clean = prop_name.strip()
                if prop_clean.lower() in _IGNORED_BRACKET_NAMES:
                    continue

                target_tbl = tbl_quoted or tbl_unquoted
                references.append(
                    SemanticReference(
                        target_name=prop_clean,
                        target_table=target_tbl,
                        target_type="measure",
                        source_type="calc_item_dax",
                        source_object=f"{source_obj}.formatStringDefinition",
                        source_file=source_file,
                        source_expression=match.group(0),
                        activates_root=True,
                        confidence=100,
                    )
                )

    return references
