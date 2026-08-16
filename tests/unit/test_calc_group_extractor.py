"""Unit tests for isolated Calculation Group semantic reference extractor."""

from pbiscan.extraction.calc_group_extractor import extract_calc_group_references


class TestCalcGroupExtractor:
    """Test suite for extract_calc_group_references."""

    def test_extracts_explicit_bracket_references(self):
        calc_items = [
            {
                "name": "vs Budget %",
                "expression": "DIVIDE(SELECTEDMEASURE() - [BudgetSales], [BudgetSales])",
                "format_string": "0.0%",
            }
        ]
        refs = extract_calc_group_references("TimeCalcGroup", calc_items, "tables/TimeCalcGroup.tmdl")
        assert len(refs) == 2  # Two instances of [BudgetSales]
        assert all(r.target_name == "BudgetSales" for r in refs)
        assert all(r.source_type == "calc_item_dax" for r in refs)
        assert all(r.activates_root is True for r in refs)

    def test_extracts_isselectedmeasure_predicates(self):
        calc_items = [
            {
                "name": "Custom Logic",
                "expression": "IF(ISSELECTEDMEASURE([TargetMargin]), SELECTEDMEASURE() * 1.05, SELECTEDMEASURE())",
            }
        ]
        refs = extract_calc_group_references("TimeCalcGroup", calc_items)
        assert len(refs) == 1
        assert refs[0].target_name == "TargetMargin"
        assert refs[0].source_type == "calc_item_predicate"
        assert refs[0].activates_root is True

    def test_extracts_selectedmeasurename_predicates(self):
        calc_items = [
            {
                "name": "Named Check",
                "expression": "IF(SELECTEDMEASURENAME() = \"GrossProfit\", SELECTEDMEASURE() * 0.9, SELECTEDMEASURE())",
            }
        ]
        refs = extract_calc_group_references("TimeCalcGroup", calc_items)
        assert len(refs) == 1
        assert refs[0].target_name == "GrossProfit"
        assert refs[0].source_type == "calc_item_predicate"

    def test_format_string_definition_references(self):
        calc_items = [
            {
                "name": "FormattedItem",
                "expression": "SELECTEDMEASURE()",
                "format_string_definition": "IF(ISSELECTEDMEASURE([ActualSales]), \"$#,##0\", \"0.0%\")",
            }
        ]
        refs = extract_calc_group_references("TimeCalcGroup", calc_items)
        assert any(r.target_name == "ActualSales" for r in refs)

    def test_ignores_reserved_bracket_names(self):
        calc_items = [
            {
                "name": "ItemWithAlias",
                "expression": "CALCULATE(SELECTEDMEASURE(), 'Table'[Value] > 0, [Name] = \"Test\")",
            }
        ]
        refs = extract_calc_group_references("TimeCalcGroup", calc_items)
        assert len(refs) == 0  # [Value] and [Name] are ignored
