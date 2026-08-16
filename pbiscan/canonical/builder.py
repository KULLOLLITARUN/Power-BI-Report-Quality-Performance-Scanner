"""Canonical builder — converts RawExtraction → CanonicalReport.

This is the adapter between the extraction layer and the rule engine.
Rules consume only CanonicalReport; they never see RawExtraction.

The builder:
  - interprets raw PBIP schema into canonical concepts
  - computes derived fields (in_relationship, is_unique signals)
  - handles schema version differences safely
"""
from __future__ import annotations

from pbiscan.canonical.model import (
    CanonicalReport,
    Column,
    CalculatedColumn,
    DaxDictionary,
    Measure,
    ModelGraph,
    Page,
    Relationship,
    ReportDOM,
    Table,
    Visual,
)
from pbiscan.extraction.pbip_reader import RawExtraction, RawTable, RawRelationship


from pbiscan.canonical.dax_graph import build_dax_graph


# Cardinality string normalisation: model.bim values → canonical strings
_CARDINALITY_MAP: dict[str, str] = {
    "manytomany":  "manyToMany",
    "many_to_many": "manyToMany",
    "m:m":         "manyToMany",
    "many:many":   "manyToMany",
    "onetomany":   "oneToMany",
    "one_to_many": "oneToMany",
    "1:m":         "oneToMany",
    "one:many":    "oneToMany",
    "onetoone":    "oneToOne",
    "one_to_one":  "oneToOne",
    "1:1":         "oneToOne",
    "one:one":     "oneToOne",
}

# Cross-filter direction string normalisation
_CROSS_FILTER_MAP: dict[str, str] = {
    "bothdirections": "both",
    "both":           "both",
    "2":              "both",
    "onedirection":   "single",
    "single":         "single",
    "1":              "single",
    "automatic":      "single",  # treat as single for analysis
}


from pbiscan.canonical.references import SemanticReference, SemanticReferenceIndex
from pbiscan.extraction.calc_group_extractor import extract_calc_group_references
from pbiscan.extraction.field_param_extractor import extract_field_param_references
from pbiscan.extraction.rls_extractor import extract_rls_tmdl_references, extract_rls_bim_references


class CanonicalBuilder:
    """Converts a RawExtraction into a CanonicalReport."""

    def build(self, raw: RawExtraction) -> CanonicalReport:
        """Build the canonical model from raw extraction data."""
        # Compute which columns appear in relationships (for M004 signal)
        relationship_columns = self._compute_relationship_columns(raw.relationships)

        tables = self._build_tables(raw.tables, relationship_columns)
        relationships = self._build_relationships(raw.relationships)
        model = ModelGraph(tables=tables, relationships=relationships)

        measures, calc_cols = self._build_dax(raw.tables)
        dax = DaxDictionary(measures=measures, calculated_columns=calc_cols)
        dax_graph = build_dax_graph(dax)

        pages = self._build_pages(raw)
        report_dom = ReportDOM(pages=pages)

        # Build Unified Semantic Reference Index (v1.4)
        semantic_references = self._build_semantic_references(
            raw=raw,
            pages=pages,
            tables=tables,
            measures=measures,
        )

        return CanonicalReport(
            model=model,
            dax=dax,
            dax_graph=dax_graph,
            report=report_dom,
            semantic_references=semantic_references,
            source_path=raw.source_path,
            report_name=raw.report_name,
        )

    def _build_semantic_references(
        self,
        raw: RawExtraction,
        pages: list[Page],
        tables: list[Table],
        measures: list[Measure],
    ) -> SemanticReferenceIndex:
        """Extract and aggregate all semantic references across visuals, calc groups, field params, and RLS."""
        index = SemanticReferenceIndex()

        # 1. PBIR Visual references
        for page in pages:
            for visual in page.visuals:
                for ref in visual.measure_refs:
                    index.add(
                        SemanticReference(
                            target_name=ref,
                            target_type="measure",
                            source_type="visual_projection",
                            source_object=f"{page.label}.{visual.visual_type}",
                            activates_root=True,
                        )
                    )

        # 2. Calculation Group references (DOM-01)
        for raw_tbl in raw.tables:
            if raw_tbl.calculation_items:
                calc_refs = extract_calc_group_references(
                    table_name=raw_tbl.name,
                    calc_items=raw_tbl.calculation_items,
                    source_file=raw_tbl.source_file,
                )
                index.add_many(calc_refs)

        # 3. Field Parameter references (DOM-02)
        known_measures = {m.name for m in measures}
        known_columns = {col.name for t in tables for col in t.columns}

        for raw_tbl in raw.tables:
            if raw_tbl.partition_source:
                fp_refs = extract_field_param_references(
                    table_name=raw_tbl.name,
                    partition_expression=raw_tbl.partition_source,
                    known_measure_names=known_measures,
                    known_column_names=known_columns,
                    source_file=raw_tbl.source_file,
                )
                index.add_many(fp_refs)

        # 4. Row-Level Security (RLS) references (DOM-03)
        if hasattr(raw, "tmdl_roles") and raw.tmdl_roles:
            for role_dict in raw.tmdl_roles:
                rls_refs = extract_rls_tmdl_references(
                    role_name=role_dict.get("name", ""),
                    tmdl_content=role_dict.get("content", ""),
                    source_file=role_dict.get("path", ""),
                )
                index.add_many(rls_refs)

        if hasattr(raw, "roles") and raw.roles:
            bim_rls_refs = extract_rls_bim_references(raw.roles)
            index.add_many(bim_rls_refs)

        return index

    # ------------------------------------------------------------------
    # Model graph
    # ------------------------------------------------------------------

    def _compute_relationship_columns(
        self, raw_rels: list[RawRelationship]
    ) -> set[tuple[str, str]]:
        """Return a set of (table, column) pairs that participate in relationships."""
        result: set[tuple[str, str]] = set()
        for rel in raw_rels:
            result.add((rel.from_table.lower(), rel.from_column.lower()))
            result.add((rel.to_table.lower(), rel.to_column.lower()))
        return result

    def _build_tables(
        self,
        raw_tables: list[RawTable],
        rel_columns: set[tuple[str, str]],
    ) -> list[Table]:
        """Convert RawTable objects to canonical Table objects."""
        result: list[Table] = []
        for raw in raw_tables:
            columns = self._build_columns(raw, rel_columns)
            result.append(Table(
                name=raw.name,
                hidden=raw.hidden,
                columns=columns,
                is_date_table=raw.is_date_table or self._is_date_table_by_name(raw.name),
                partition_source=raw.partition_source,
            ))
        return result

    def _is_date_table_by_name(self, name: str) -> bool:
        """Fallback heuristic: table name strongly suggests a date dimension."""
        name_lower = name.lower()
        date_hints = ("date", "dim_date", "dimdate", "calendar", "dim_calendar")
        return any(h == name_lower or name_lower.startswith(h) for h in date_hints)

    def _build_columns(
        self,
        raw_table: RawTable,
        rel_columns: set[tuple[str, str]],
    ) -> list[Column]:
        """Convert raw column dicts to canonical Column objects."""
        result: list[Column] = []
        for raw_col in raw_table.columns:
            name = raw_col.get("name", "")
            if not name:
                continue

            data_type = self._normalise_data_type(raw_col.get("dataType", "string"))
            in_rel = (raw_table.name.lower(), name.lower()) in rel_columns
            is_unique = self._detect_is_unique(raw_col)
            data_category = raw_col.get("dataCategory", None)

            result.append(Column(
                name=name,
                table=raw_table.name,
                data_type=data_type,
                hidden=raw_col.get("isHidden", False),
                is_unique=is_unique,
                data_category=data_category,
                in_relationship=in_rel,
            ))
        return result

    def _normalise_data_type(self, raw_type: str) -> str:
        """Normalise model.bim dataType values to canonical strings."""
        mapping = {
            "int64":    "int64",
            "decimal":  "decimal",
            "double":   "decimal",
            "string":   "string",
            "boolean":  "boolean",
            "datetime": "dateTime",
            "date":     "dateTime",
            "binary":   "binary",
            "variant":  "variant",
        }
        return mapping.get(raw_type.lower(), raw_type.lower())

    def _detect_is_unique(self, raw_col: dict) -> bool:
        """Detect whether a column has a uniqueness signal.

        Signals:
          - isUnique == true in the raw column dict
          - isKey == true (Power BI primary key property)
          - A PBI_IsUnique annotation
        """
        if raw_col.get("isUnique", False) or raw_col.get("isKey", False):
            return True
        for ann in raw_col.get("annotations", []):
            if ann.get("name") == "PBI_IsUnique" and str(ann.get("value", "")).lower() == "true":
                return True
        return False

    def _build_relationships(
        self, raw_rels: list[RawRelationship]
    ) -> list[Relationship]:
        """Convert RawRelationship objects to canonical Relationship objects."""
        result: list[Relationship] = []
        for raw in raw_rels:
            r = raw.raw

            # Determine cardinality from fromCardinality + toCardinality
            cardinality = self._parse_cardinality(r)

            # Determine cross-filter direction
            raw_direction = r.get("crossFilteringBehavior", "oneDirection")
            cross_filter = _CROSS_FILTER_MAP.get(raw_direction.lower(), "single")

            result.append(Relationship(
                from_table=raw.from_table,
                from_column=raw.from_column,
                to_table=raw.to_table,
                to_column=raw.to_column,
                cardinality=cardinality,
                cross_filter_direction=cross_filter,
                is_active=r.get("isActive", True),
            ))
        return result

    def _parse_cardinality(self, r: dict) -> str:
        """Determine canonical cardinality from model.bim fields."""
        # Check for explicit many-to-many markers
        from_card = r.get("fromCardinality", "many").lower()
        to_card = r.get("toCardinality", "one").lower()

        if from_card == "many" and to_card == "many":
            return "manyToMany"
        if from_card == "one" and to_card == "one":
            return "oneToOne"

        # Check the crossFilteringBehavior for legacy M:M signal
        # (some older model.bim files use this instead)
        raw_key = r.get("fromCardinality", "")
        mapped = _CARDINALITY_MAP.get(raw_key.lower(), "")
        if mapped:
            return mapped

        return "oneToMany"  # default

    # ------------------------------------------------------------------
    # DAX dictionary
    # ------------------------------------------------------------------

    def _build_dax(
        self, raw_tables: list[RawTable]
    ) -> tuple[list[Measure], list[CalculatedColumn]]:
        """Extract all measures and calculated columns from raw tables."""
        measures: list[Measure] = []
        calc_cols: list[CalculatedColumn] = []

        for raw_table in raw_tables:
            for m in raw_table.measures:
                name = m.get("name", "")
                expr = m.get("expression", "")
                if name and expr:
                    measures.append(Measure(
                        name=name,
                        table=raw_table.name,
                        expression=expr if isinstance(expr, str) else "\n".join(expr),
                        hidden=m.get("isHidden", False),
                    ))

            for cc in raw_table.calculated_columns:
                name = cc.get("name", "")
                expr = cc.get("expression", "")
                if name and expr:
                    calc_cols.append(CalculatedColumn(
                        name=name,
                        table=raw_table.name,
                        expression=expr if isinstance(expr, str) else "\n".join(expr),
                        data_type=self._normalise_data_type(cc.get("dataType", "string")),
                    ))

        return measures, calc_cols

    # ------------------------------------------------------------------
    # Report DOM
    # ------------------------------------------------------------------

    def _build_pages(self, raw: RawExtraction) -> list[Page]:
        """Convert raw pages to canonical Page objects."""
        pages: list[Page] = []
        for raw_page in raw.pages:
            visuals = [
                Visual(
                    visual_type=rv.visual_type,
                    page=raw_page.name,
                    x=rv.x,
                    y=rv.y,
                    width=rv.width,
                    height=rv.height,
                    fields_used=rv.fields_used,
                    measure_refs=rv.measure_refs,
                    is_slicer=rv.is_slicer,
                    hidden=rv.hidden,
                )
                for rv in raw_page.visuals
            ]
            pages.append(Page(
                name=raw_page.name,
                display_name=raw_page.display_name,
                visibility=raw_page.visibility,
                visuals=visuals,
            ))
        return pages
