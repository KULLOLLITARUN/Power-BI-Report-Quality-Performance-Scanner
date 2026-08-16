"""Semantic Reference Data Models (v1.4 Reference Architecture).

Pure data contracts representing discovered semantic references across PBIR visuals,
Calculation Groups, Field Parameters, and Row-Level Security (RLS) role expressions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


ReferenceSourceType = Literal[
    "visual_projection",       # Direct measure in visual queryState/projections
    "visual_filter",           # Measure in visual/page filter pane
    "visual_property",         # Measure in visual title, subtitle, card label, conditional format
    "calc_item_dax",           # Explicit [Measure] reference in calculationItem DAX
    "calc_item_predicate",     # Target measure in ISSELECTEDMEASURE([Measure]) predicate
    "field_parameter",         # Measure in calculated table NAMEOF('Table'[Measure])
    "field_parameter_grouped", # Measure in 4-tuple grouped calculated table
    "rls_table_permission",    # Measure in roles/Role.tmdl or model.bim tablePermission DAX
]

ReferenceTargetType = Literal[
    "measure",                 # Activates DAX measure reachability root
    "column",                  # Physical or calculated table column (non-measure entity)
    "table",                   # Entire table entity
    "unresolved",              # Ambiguous or malformed expression entity
]


@dataclass(frozen=True)
class SemanticReference:
    """Immutable record of a semantic reference discovered in a PBIP project."""

    target_name: str                           # Canonical measure or column name (e.g., "NetRevenue")
    target_table: Optional[str] = None         # Qualifying table name if available (e.g., "Sales")
    target_type: ReferenceTargetType = "measure"
    source_type: ReferenceSourceType = "visual_projection"
    source_object: str = ""                    # Container name (e.g., "TimeCalcGroup['vs Budget %']", "ManagerRole")
    source_file: str = ""                      # Relative path to source file
    source_expression: Optional[str] = None    # Surrounding DAX or AST fragment (for audit provenance)
    activates_root: bool = True                # True if target_type == "measure" and container is active
    confidence: int = 100                      # Confidence score (1-100)


@dataclass
class SemanticReferenceIndex:
    """In-memory index aggregating all discovered semantic references across all producers."""

    references: list[SemanticReference] = field(default_factory=list)

    def add(self, ref: SemanticReference) -> None:
        """Add a discovered semantic reference to the index."""
        self.references.append(ref)

    def add_many(self, refs: list[SemanticReference]) -> None:
        """Add multiple semantic references to the index."""
        self.references.extend(refs)

    def active_root_measure_names(self) -> set[str]:
        """Return the deduplicated, case-preserved set of measure names that activate graph reachability."""
        roots: set[str] = set()
        for ref in self.references:
            if ref.activates_root and ref.target_type == "measure":
                roots.add(ref.target_name)
        return roots

    def find_by_target(self, target_name: str) -> list[SemanticReference]:
        """Lookup all references targeting a specific entity name (case-insensitive)."""
        target_lower = target_name.lower()
        return [r for r in self.references if r.target_name.lower() == target_lower]

    def find_by_source_type(self, source_type: ReferenceSourceType) -> list[SemanticReference]:
        """Lookup all references originating from a specific syntactic producer."""
        return [r for r in self.references if r.source_type == source_type]

    def __len__(self) -> int:
        return len(self.references)
