"""Field Parameter Semantic Reference Extractor (v1.4 Producer).

Extracts semantic references from Field Parameter calculated tables:
- Parses NAMEOF('Table'[Entity]) expressions.
- Performs strict entity discrimination: classifies references as 'measure' vs 'column'.
- Flags measure targets with activates_root=True and column targets with activates_root=False.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pbiscan.canonical.references import SemanticReference


# Regex pattern to match NAMEOF('Table'[Entity]) or NAMEOF(Table[Entity])
_NAMEOF_PATTERN = re.compile(
    r"\bNAMEOF\s*\(\s*(?:'([^']+)'\s*|([a-zA-Z_][a-zA-Z0-9_]*)\s*)?\[([^\]]+)\]\s*\)",
    re.IGNORECASE,
)


def extract_field_param_references(
    table_name: str,
    partition_expression: str,
    known_measure_names: Optional[set[str]] = None,
    known_column_names: Optional[set[str]] = None,
    source_file: str = "",
) -> list[SemanticReference]:
    """Extract semantic references from a field parameter calculated table definition.

    Args:
        table_name: Name of the field parameter table (e.g., "DynamicMetrics").
        partition_expression: DAX partition source (e.g., '{("Revenue", NAMEOF('Sales'[Revenue]), 0)}').
        known_measure_names: Set of canonical model measure names (case-insensitive) for entity discrimination.
        known_column_names: Set of canonical model column names (case-insensitive) for entity discrimination.
        source_file: Relative filepath for provenance audit.

    Returns:
        List of discovered SemanticReference records.
    """
    if not partition_expression or "NAMEOF" not in partition_expression.upper():
        return []

    meas_set = {m.lower() for m in known_measure_names} if known_measure_names else None
    col_set = {c.lower() for c in known_column_names} if known_column_names else None

    # Determine if 4-tuple grouped parameter table
    is_grouped = bool(re.search(r",\s*\"[^\"]+\"\s*\)\s*\}", partition_expression))
    source_type: Literal["field_parameter", "field_parameter_grouped"] = (
        "field_parameter_grouped" if is_grouped else "field_parameter"
    )

    references: list[SemanticReference] = []

    for match in _NAMEOF_PATTERN.finditer(partition_expression):
        tbl_quoted, tbl_unquoted, entity_name = match.groups()
        target_tbl = tbl_quoted or tbl_unquoted or ""
        entity_clean = entity_name.strip()
        entity_lower = entity_clean.lower()

        # Strict Entity Discrimination: Measure vs Column
        target_type: Literal["measure", "column", "table", "unresolved"]
        if meas_set and entity_lower in meas_set:
            target_type = "measure"
            activates_root = True
        elif col_set and entity_lower in col_set:
            target_type = "column"
            activates_root = False
        else:
            # If discrimination sets not provided or entity is not in columns, assume measure
            target_type = "measure"
            activates_root = True

        references.append(
            SemanticReference(
                target_name=entity_clean,
                target_table=target_tbl,
                target_type=target_type,
                source_type=source_type,
                source_object=table_name,
                source_file=source_file,
                source_expression=match.group(0),
                activates_root=activates_root,
                confidence=100,
            )
        )

    return references
