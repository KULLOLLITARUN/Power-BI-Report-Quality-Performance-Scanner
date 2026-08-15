"""Unit tests — canonical model objects."""
from __future__ import annotations
import pytest
from pbiscan.canonical.model import (
    CanonicalReport, Column, CalculatedColumn, DaxDictionary,
    Measure, ModelGraph, Page, Relationship, ReportDOM, Table, Visual,
)


class TestColumn:
    def test_defaults(self):
        col = Column(name="Amount", table="Sales")
        assert col.data_type == "string"
        assert col.hidden is False
        assert col.is_unique is False
        assert col.data_category is None
        assert col.in_relationship is False

    def test_fields(self):
        col = Column(name="ID", table="Dim", data_type="int64", is_unique=True, in_relationship=True)
        assert col.data_type == "int64"
        assert col.is_unique is True
        assert col.in_relationship is True


class TestTable:
    def test_defaults(self):
        t = Table(name="Sales")
        assert t.hidden is False
        assert t.columns == []
        assert t.is_date_table is False

    def test_with_columns(self):
        col = Column(name="ID", table="Sales")
        t = Table(name="Sales", columns=[col])
        assert len(t.columns) == 1


class TestRelationship:
    def test_defaults(self):
        r = Relationship(
            from_table="Sales", from_column="CID",
            to_table="Customer", to_column="CID"
        )
        assert r.cardinality == "oneToMany"
        assert r.cross_filter_direction == "single"
        assert r.is_active is True


class TestVisual:
    def test_slicer_auto_flag(self):
        v = Visual(visual_type="slicer", page="Page1")
        assert v.is_slicer is True

    def test_non_slicer(self):
        v = Visual(visual_type="barChart", page="Page1")
        assert v.is_slicer is False

    def test_slicer_case_insensitive(self):
        v = Visual(visual_type="Slicer", page="Page1")
        assert v.is_slicer is True


class TestPage:
    def _make_page(self, n_visuals=3, n_slicers=2, hidden=False):
        visuals = [Visual(visual_type="barChart", page="P") for _ in range(n_visuals)]
        visuals += [Visual(visual_type="slicer", page="P") for _ in range(n_slicers)]
        return Page(name="P", display_name="Page 1", visibility=1 if hidden else 0, visuals=visuals)

    def test_visual_count(self):
        p = self._make_page(n_visuals=5, n_slicers=3)
        assert p.visual_count == 8

    def test_slicer_count(self):
        p = self._make_page(n_visuals=5, n_slicers=3)
        assert p.slicer_count == 3

    def test_hidden(self):
        p = self._make_page(hidden=True)
        assert p.is_hidden is True

    def test_visible(self):
        p = self._make_page(hidden=False)
        assert p.is_hidden is False

    def test_label_uses_display_name(self):
        p = Page(name="RS1", display_name="Sales Overview")
        assert p.label == "Sales Overview"

    def test_label_falls_back_to_name(self):
        p = Page(name="RS1", display_name="")
        assert p.label == "RS1"


class TestCanonicalReport:
    def test_empty(self):
        r = CanonicalReport()
        assert r.model.tables == []
        assert r.dax.measures == []
        assert r.report.pages == []

    def test_get_measure(self):
        m = Measure(name="Total Revenue", table="Sales", expression="SUM(Sales[Amount])")
        dax = DaxDictionary(measures=[m])
        r = CanonicalReport(dax=dax)
        assert r.dax.get_measure("Total Revenue") is m
        assert r.dax.get_measure("total revenue") is m  # case-insensitive
        assert r.dax.get_measure("Missing") is None
