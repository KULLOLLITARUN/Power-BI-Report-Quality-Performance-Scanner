"""TMDL measure and calculated-column bodies: properties are not DAX, and fact-to-fact naming.

The browser engine mirrors these (studio-ui/src/engine/clientScanner.test.ts).
"""
from __future__ import annotations

import pytest

from pbiscan.canonical.model import (
    CanonicalReport, DaxDictionary, Measure, ModelGraph, ReportDOM, Relationship, Table,
    looks_like_dimension_name,
)
from pbiscan.extraction.tmdl_parser import parse_tmdl_table_text
from pbiscan.rules.model import check_fact_to_fact


def _table(text: str):
    table = parse_tmdl_table_text(text)
    assert table is not None
    return table


class TestBareFlagsAreProperties:
    def test_bare_is_hidden_is_a_flag_not_dax(self):
        table = _table("table T\n\tmeasure A = 1\n\t\tisHidden\n\t\tformatString: 0\n\n\tmeasure B = 2\n")
        a, b = table.measures
        assert a["expression"] == "1"
        assert a["isHidden"] is True
        assert "isHidden" not in b

    def test_is_hidden_false_is_not_hidden(self):
        table = _table("table T\n\tmeasure A = 1\n\t\tisHidden: false\n")
        assert table.measures[0]["isHidden"] is False

    def test_bare_flags_on_a_calculated_column_stay_out_of_its_expression(self):
        table = _table('table T\n\tcolumn C = "x"\n\t\tdataType: string\n\t\tisHidden\n\t\tisKey\n')
        assert table.calculated_columns[0]["expression"] == '"x"'
        assert table.calculated_columns[0]["isHidden"] is True


class TestVariationBlocksAreProperties:
    def test_variation_block_on_a_calculated_date_column_is_not_dax(self):
        table = _table(
            'table T\n\tcolumn D = "2024-01-01"\n\t\tdataType: dateTime\n\n'
            "\t\tvariation Variation\n\t\t\tisDefault\n\t\t\trelationship: abc\n"
            "\t\t\tdefaultHierarchy: LocalDateTable_1.'Date Hierarchy'\n\n"
            "\t\tannotation X = 1\n\n\tmeasure M = 1 + 1\n"
        )
        assert table.calculated_columns[0]["expression"] == '"2024-01-01"'
        assert table.measures[0]["expression"] == "1 + 1"

    def test_dax_after_a_variation_block_at_a_shallower_indent_is_kept(self):
        table = _table("table T\n\tmeasure M =\n\t\t\tVAR x = 1\n\t\tvariation V\n\t\t\tisDefault\n\t\tformatString: 0\n")
        assert table.measures[0]["expression"] == "VAR x = 1"

    def test_a_measure_that_merely_starts_with_variation_is_not_skipped(self):
        table = _table("table T\n\tmeasure Variance = 1\n\t\tVARIATION_RATE + 1\n")
        assert "VARIATION_RATE" in table.measures[0]["expression"]


class TestDimensionNames:
    @pytest.mark.parametrize("name", [
        "DimCustomer", "dim_customer", "dimcustomer", "Dim Date", "Customer Lookup",
        "Product Reference", "Bridge Table", "RefData", "Dimensions",
    ])
    def test_dimension_names(self, name):
        assert looks_like_dimension_name(name)

    @pytest.mark.parametrize("name", ["Refunds", "Preferences", "Sales", "Orders", "ReferSales Fact"])
    def test_fact_names_that_only_contain_the_letters(self, name):
        assert not looks_like_dimension_name(name)


def _report(tables: list[str], measure_tables: list[str], rels: list[tuple[str, str]]) -> CanonicalReport:
    return CanonicalReport(
        model=ModelGraph(
            tables=[Table(name=t) for t in tables],
            # Many-to-many: fact-to-fact only considers links that can join two fact tables.
            relationships=[
                Relationship(from_table=a, from_column="K", to_table=b, to_column="K", cardinality="manyToMany")
                for a, b in rels
            ],
        ),
        dax=DaxDictionary(measures=[Measure(name=f"M {t}", table=t, expression="1") for t in measure_tables]),
        report=ReportDOM(pages=[]),
    )


class TestFactToFactUsesWholeWords:
    def test_facts_named_with_the_letters_ref_are_still_facts(self):
        report = _report(["Refunds", "Preferences"], ["Refunds", "Preferences"], [("Refunds", "Preferences")])
        assert len(check_fact_to_fact(report)) == 1

    def test_a_dimension_table_is_not_a_fact(self):
        for dim in ("DimProduct", "Product Lookup", "Region Reference", "Bridge"):
            report = _report(["Sales", dim], ["Sales", dim], [("Sales", dim)])
            assert check_fact_to_fact(report) == [], dim
