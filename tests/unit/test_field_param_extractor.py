"""Unit tests for isolated Field Parameter semantic reference extractor."""

from pbiscan.extraction.field_param_extractor import extract_field_param_references


class TestFieldParamExtractor:
    """Test suite for extract_field_param_references."""

    def test_extracts_pure_measure_parameters(self):
        expr = """
        {
            ("Net Revenue", NAMEOF('Sales'[NetRevenue]), 0),
            ("Units", NAMEOF('Sales'[UnitsSold]), 1)
        }
        """
        known_measures = {"NetRevenue", "UnitsSold"}
        known_columns = {"Revenue", "Units"}

        refs = extract_field_param_references(
            table_name="DynamicMetrics",
            partition_expression=expr,
            known_measure_names=known_measures,
            known_column_names=known_columns,
        )

        assert len(refs) == 2
        assert {r.target_name for r in refs} == {"NetRevenue", "UnitsSold"}
        assert all(r.target_type == "measure" for r in refs)
        assert all(r.activates_root is True for r in refs)

    def test_strict_entity_discrimination_column_vs_measure(self):
        expr = """
        {
            ("Net Revenue", NAMEOF('Sales'[NetRevenue]), 0),
            ("Category", NAMEOF('DimProduct'[Category]), 1)
        }
        """
        known_measures = {"NetRevenue"}
        known_columns = {"Category"}

        refs = extract_field_param_references(
            table_name="MixedParams",
            partition_expression=expr,
            known_measure_names=known_measures,
            known_column_names=known_columns,
        )

        assert len(refs) == 2

        meas_ref = next(r for r in refs if r.target_name == "NetRevenue")
        assert meas_ref.target_type == "measure"
        assert meas_ref.activates_root is True

        col_ref = next(r for r in refs if r.target_name == "Category")
        assert col_ref.target_type == "column"
        assert col_ref.activates_root is False  # Column does not activate measure root

    def test_grouped_4_tuple_field_parameter(self):
        expr = """
        {
            ("Profitability", NAMEOF('Sales'[ProfitMargin]), 0, "Finance"),
            ("Operations", NAMEOF('Sales'[SlicerActivatedMetric]), 1, "Logistics")
        }
        """
        refs = extract_field_param_references(
            table_name="GroupedSelector",
            partition_expression=expr,
        )
        assert len(refs) == 2
        assert all(r.source_type == "field_parameter_grouped" for r in refs)
        assert all(r.activates_root is True for r in refs)
