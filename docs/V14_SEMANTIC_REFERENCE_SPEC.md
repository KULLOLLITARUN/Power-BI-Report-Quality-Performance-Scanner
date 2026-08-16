# PBIP Sentinel v1.4 — Semantic Reference Index Specification

**Status**: SPECIFICATION LOCKED (Phase 2B Design Milestone)  
**Baseline Control**: `PBIP Sentinel v1.3.0` (181/181 Passing Regression Tests)  
**Architectural Scope**: Generalized Reference Discovery & Provenance Model for Calculation Groups, Field Parameters, and Row-Level Security.

---

## 1. Architectural Motivation & Boundary Principle

Empirical Phase 1 observation and Phase 2A variant testing conclusively demonstrated that `D004` (Unused Measure Detection) fails in modern Power BI models not due to dependency graph traversal errors, but due to **upstream reference producer omissions**.

```text
                                  CURRENT v1.3.0 FLOW
    PBIR Visual Projections ──► Root Reference Set ──► DaxDependencyGraph ──► D004 Unused Decision
                                       ▲
                                       │ (MISSING PRODUCERS)
                                       ├── Calculation Groups (SELECTEDMEASURE, calc items)
                                       ├── Field Parameters (NAMEOF calculated tables)
                                       └── Row-Level Security (tablePermission DAX)
```

### Architectural Contract:
1. **Separation of Concerns**: `D004` remains purely a graph reachability and diagnostic decision rule. It shall not contain feature-specific heuristics (e.g. no `if is_calc_group: ignore`).
2. **Unified Indexing Layer**: All reference sources (PBIR visuals, Calculation Groups, Field Parameters, and RLS roles) produce standardized `SemanticReference` objects into a unified `SemanticReferenceIndex`.
3. **Deterministic Root Activation**: Only references whose `target_type == "measure"` activate roots in `DaxDependencyGraph`. Non-measure references (e.g. dimension columns in field parameters) are preserved in the index for provenance and future rules, but do not trigger measure reachability.

---

## 2. Semantic Reference Data Model

Every discovered reference in the model metadata or visual AST is encapsulated in an immutable `SemanticReference` record:

```python
from dataclasses import dataclass
from typing import Literal, Optional

ReferenceSourceType = Literal[
    "visual_projection",      # Direct measure in visual queryState/projections
    "visual_filter",          # Measure in visual/page filter pane
    "visual_property",        # Measure in visual title, subtitle, card label, conditional format
    "calc_item_dax",          # Explicit [Measure] reference in calculationItem DAX
    "calc_item_predicate",    # Target measure in ISSELECTEDMEASURE([Measure]) predicate
    "field_parameter",        # Measure in calculated table NAMEOF('Table'[Measure])
    "field_parameter_grouped",# Measure in 4-tuple grouped calculated table
    "rls_table_permission",   # Measure in roles/Role.tmdl tablePermission DAX filter
]

ReferenceTargetType = Literal[
    "measure",                # Activates DAX measure reachability root
    "column",                 # Physical or calculated table column (non-measure root)
    "table",                  # Entire table entity
    "unresolved",             # Ambiguous or malformed expression entity
]

@dataclass(frozen=True)
class SemanticReference:
    """Immutable record of a semantic reference discovered in a PBIP project."""
    target_name: str                           # Canonical measure or column name (e.g., "NetRevenue")
    target_table: Optional[str]                # Qualifying table name if available (e.g., "Sales")
    target_type: ReferenceTargetType           # "measure" | "column" | "table" | "unresolved"
    source_type: ReferenceSourceType           # Exact originating syntactic producer
    source_object: str                         # Container name (e.g., "TimeCalcGroup['vs Budget %']", "RegionalManagerRole")
    source_file: str                           # Relative path to source file (e.g., "definition/roles/Manager.tmdl")
    source_expression: Optional[str]           # Surrounding DAX or AST fragment (for provenance & audit)
    activates_root: bool                       # True if target_type == "measure" and source container is active
    confidence: int                            # Confidence score (1-100), default 100 for verified syntactic references
```

---

## 3. Producer Reference Extraction Rules

### 3.1. Producer 1: Calculation Groups (`DOM-01`)
- **Calculation Item DAX Bracket Parser**:
  - Scans all `calculationItem` DAX expressions in `tables/*.tmdl` or `model.bim.tables[].calculationGroup`.
  - Extracts all explicit `[MeasureName]` or `'Table'[MeasureName]` bracket tokens.
  - Emits: `source_type="calc_item_dax"`, `target_type="measure"`, `activates_root=True`.
- **Introspection Predicate Parser**:
  - Matches `ISSELECTEDMEASURE([MeasureName], ...)` or `SELECTEDMEASURENAME() == "MeasureName"`.
  - Emits: `source_type="calc_item_predicate"`, `target_type="measure"`, `activates_root=True`.
- **Format String Expressions**:
  - Scans `formatStringDefinition` inside calculation items for measure references.
  - Emits: `source_type="calc_item_dax"`, `target_type="measure"`, `activates_root=True`.

### 3.2. Producer 2: Field Parameters (`DOM-02`)
- **Calculated Table Partition Parser**:
  - Detects calculated tables defining tuples with `NAMEOF(...)`.
  - Syntax pattern: `NAMEOF('Table'[EntityName])` or `NAMEOF(Table[EntityName])`.
- **Entity Discrimination Requirement**:
  - Cross-references `EntityName` against `report.model.tables[Table].measures` vs `columns`.
  - If `EntityName` matches a measure $\to$ `target_type="measure"`, `activates_root=True`.
  - If `EntityName` matches a column $\to$ `target_type="column"`, `activates_root=False`.
- **Visual Slicer & Axis Reachability**:
  - If any column of the Field Parameter table is referenced in a visual (slicer, chart axis, values), all measure targets defined in the table's `NAMEOF()` partition are activated as roots.

### 3.3. Producer 3: Row-Level Security Roles (`DOM-03`)
- **TMDL Role Parser**:
  - Parses `definition/roles/*.tmdl` files and `model.tmdl` `ref role ...` declarations.
- **TMSL / BIM Role Parser**:
  - Parses `model.bim.roles[].tablePermissions[].filterExpression`.
- **Table Permission Expression Extraction**:
  - Scans `tablePermission TableName = <DAX Expression>` for `[MeasureName]` references.
  - Emits: `source_type="rls_table_permission"`, `target_type="measure"`, `activates_root=True`.

---

## 4. Transitive Closure & Graph Interaction

```text
    ┌────────────────────────────────────────────────────────┐
    │                SemanticReferenceIndex                  │
    │  - Visual Projections:        {"ActualSales"}          │
    │  - Calc Item DAX:             {"BudgetSales"}          │
    │  - Field Parameter NAMEOF():  {"NetRevenue", "Units"}  │
    │  - RLS Table Permissions:     {"IsUserAuthorized"}     │
    └───────────────────────────┬────────────────────────────┘
                                │
                                ▼
        active_root_measures = {ref.target_name for ref in index if ref.activates_root}
                                │
                                ▼
                       DaxDependencyGraph
         (Resolves multi-hop transitive base measures)
         e.g., NetRevenue -> BaseRevenue (Auto-Activated)
         e.g., IsUserAuthorized -> CurrentUserRegion -> UserSecurityHash (Auto-Activated)
                                │
                                ▼
                    Unused Decision in D004
          unused = all_measures - reachable_measures
```

---

## 5. Deduplication, Determinism & Resilience Guarantees

1. **Deduplication**: If a measure is referenced by both a visual and an RLS role (e.g. `TotalSales`), the index preserves both references with distinct provenance, and yields a single deduplicated string entry in `active_root_measures`.
2. **Case Insensitivity**: Matching between discovered reference names and measure definitions is strictly case-insensitive (`measure.name.lower() == ref.target_name.lower()`), preserving canonical casing in diagnostic evidence.
3. **Malformed Syntax Safety**: If an RLS or Field Parameter DAX expression contains syntax errors, the parser logs a warning, skips the malformed token, and never crashes.
4. **Compatibility Invariant**: For PBIP projects containing no Calculation Groups, Field Parameters, or RLS roles, the extracted root reference set is **100% byte-for-byte identical to the v1.3.0 visual reference set**.

---

## 6. Phase 2 Governance Sign-Off Matrix

| Component | Design Status | Golden Fixture Contract | Target Module |
|---|:---:|---|---|
| **Data Structures** | ✅ Locked | `tests/unit/test_semantic_reference_index.py` | `pbiscan/canonical/references.py` |
| **Calc Group Parser** | ✅ Locked | `tests/golden/test_calc_group_variant_fixtures.py` | `pbiscan/extraction/calc_group_extractor.py` |
| **Field Parameter Parser** | ✅ Locked | `tests/golden/test_field_parameter_variant_fixtures.py` | `pbiscan/extraction/field_param_extractor.py` |
| **RLS Role Parser** | ✅ Locked | `tests/golden/test_rls_variant_fixtures.py` | `pbiscan/extraction/rls_extractor.py` |
| **Unified Index Builder**| ✅ Locked | `tests/golden/test_semantic_index_fixtures.py` | `pbiscan/canonical/builder.py` |
| **D004 Ingestion** | ✅ Locked | `tests/unit/test_rules_dax.py` (All 181 Tests Pass) | `pbiscan/rules/dax.py` |
