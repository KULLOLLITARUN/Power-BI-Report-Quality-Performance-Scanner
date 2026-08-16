"""Row-Level Security (RLS) Semantic Reference Extractor (v1.4 Producer).

Extracts semantic references from TMDL / TMSL Role tablePermission DAX filter expressions:
- Scans definition/roles/*.tmdl files and model.bim roles[].
- Extracts measure references used in security expressions.
- Emits SemanticReference records with source_type='rls_table_permission'.
"""

from __future__ import annotations

import re
from typing import Any

from pbiscan.canonical.references import SemanticReference


# Regex pattern to match bracket references in DAX security filter expressions
_BRACKET_REF_PATTERN = re.compile(
    r"(?:'([^']+)'|\b([a-zA-Z_][a-zA-Z0-9_]*))?\[([^\]]+)\]",
    re.IGNORECASE,
)

# DAX function tokens to ignore
_IGNORED_TOKENS = {
    "userprincipalname", "userobjectid", "username", "customdata",
    "true", "false", "blank", "value",
}


def extract_rls_tmdl_references(
    role_name: str,
    tmdl_content: str,
    source_file: str = "",
) -> list[SemanticReference]:
    """Extract semantic references from a TMDL role definition file.

    Args:
        role_name: Name of the role (e.g., "RegionalManagerRole").
        tmdl_content: String content of the role TMDL file.
        source_file: Relative filepath for provenance audit.

    Returns:
        List of discovered SemanticReference records.
    """
    if not tmdl_content or "tablePermission" not in tmdl_content:
        return []

    references: list[SemanticReference] = []

    # Match each tablePermission line: tablePermission TableName = DAX Expression
    # Handles multi-line DAX expressions until the next TMDL block
    perm_pattern = re.compile(
        r"tablePermission\s+([^\s=]+)\s*=\s*(.+?)(?=(?:\n\s*tablePermission|\n\s*role|\n\s*member|\Z))",
        re.DOTALL,
    )

    for match in perm_pattern.finditer(tmdl_content):
        perm_table = match.group(1).strip().strip("'")
        dax_expr = match.group(2).strip()

        for ref_match in _BRACKET_REF_PATTERN.finditer(dax_expr):
            tbl_quoted, tbl_unquoted, entity_name = ref_match.groups()
            entity_clean = entity_name.strip()
            if entity_clean.lower() in _IGNORED_TOKENS:
                continue

            target_tbl = tbl_quoted or tbl_unquoted or perm_table
            references.append(
                SemanticReference(
                    target_name=entity_clean,
                    target_table=target_tbl,
                    target_type="measure",
                    source_type="rls_table_permission",
                    source_object=f"{role_name}.tablePermission['{perm_table}']",
                    source_file=source_file,
                    source_expression=ref_match.group(0),
                    activates_root=True,
                    confidence=100,
                )
            )

    return references


def extract_rls_bim_references(
    roles: list[dict[str, Any]],
    source_file: str = "model.bim",
) -> list[SemanticReference]:
    """Extract semantic references from model.bim roles array.

    Args:
        roles: List of TMSL role dictionaries.
        source_file: Relative filepath for provenance audit.

    Returns:
        List of discovered SemanticReference records.
    """
    if not roles:
        return []

    references: list[SemanticReference] = []

    for role in roles:
        if not isinstance(role, dict):
            continue
        role_name = str(role.get("name") or "UnknownRole")
        table_perms = role.get("tablePermissions") or []
        if not isinstance(table_perms, list):
            continue

        for perm in table_perms:
            if not isinstance(perm, dict):
                continue
            perm_table = str(perm.get("name") or "UnknownTable")
            raw_expr = perm.get("filterExpression")
            dax_expr = str(raw_expr) if raw_expr is not None else ""

            for ref_match in _BRACKET_REF_PATTERN.finditer(dax_expr):
                tbl_quoted, tbl_unquoted, entity_name = ref_match.groups()
                entity_clean = entity_name.strip()
                if entity_clean.lower() in _IGNORED_TOKENS:
                    continue

                target_tbl = tbl_quoted or tbl_unquoted or perm_table
                references.append(
                    SemanticReference(
                        target_name=entity_clean,
                        target_table=target_tbl,
                        target_type="measure",
                        source_type="rls_table_permission",
                        source_object=f"{role_name}.tablePermissions['{perm_table}']",
                        source_file=source_file,
                        source_expression=ref_match.group(0),
                        activates_root=True,
                        confidence=100,
                    )
                )

    return references
