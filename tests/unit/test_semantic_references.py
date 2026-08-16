"""Unit tests for SemanticReference and SemanticReferenceIndex data contracts."""

from pbiscan.canonical.references import SemanticReference, SemanticReferenceIndex


class TestSemanticReferenceIndex:
    """Test suite for SemanticReference and SemanticReferenceIndex data structure."""

    def test_semantic_reference_immutability(self):
        ref = SemanticReference(
            target_name="NetRevenue",
            target_table="Sales",
            target_type="measure",
            source_type="field_parameter",
            source_object="DynamicMetrics",
            source_file="definition/tables/DynamicMetrics.tmdl",
            source_expression="NAMEOF('Sales'[NetRevenue])",
            activates_root=True,
            confidence=100,
        )
        assert ref.target_name == "NetRevenue"
        assert ref.target_table == "Sales"
        assert ref.activates_root is True

    def test_active_root_measure_names_deduplication(self):
        index = SemanticReferenceIndex()
        # Add measure reference that activates root
        index.add(SemanticReference(target_name="TotalSales", target_type="measure", activates_root=True))
        # Add duplicate from another source
        index.add(SemanticReference(target_name="TotalSales", target_type="measure", source_type="rls_table_permission", activates_root=True))
        # Add column reference that does NOT activate measure root
        index.add(SemanticReference(target_name="Category", target_type="column", activates_root=False))
        # Add measure with activates_root=False
        index.add(SemanticReference(target_name="InactiveMeasure", target_type="measure", activates_root=False))

        roots = index.active_root_measure_names()
        assert roots == {"TotalSales"}
        assert len(index) == 4

    def test_find_by_target_and_source_type(self):
        index = SemanticReferenceIndex()
        index.add(SemanticReference(target_name="BudgetSales", target_type="measure", source_type="calc_item_dax"))
        index.add(SemanticReference(target_name="TargetMargin", target_type="measure", source_type="calc_item_predicate"))

        assert len(index.find_by_target("budgetsales")) == 1
        assert len(index.find_by_source_type("calc_item_dax")) == 1
        assert len(index.find_by_source_type("rls_table_permission")) == 0
