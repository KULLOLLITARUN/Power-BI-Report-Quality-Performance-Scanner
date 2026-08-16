"""Unit tests for DaxDependencyGraph (canonical/dax_graph.py)."""
from __future__ import annotations
import pytest
from pbiscan.canonical.model import DaxDictionary, Measure, CalculatedColumn
from pbiscan.canonical.dax_graph import DaxDependencyGraph, DaxNode, build_dax_graph


class TestDaxDependencyGraph:
    def test_empty_graph(self):
        dax = DaxDictionary()
        graph = build_dax_graph(dax)
        assert len(graph.nodes) == 0
        assert graph.references("NonExistent") == set()
        assert graph.referenced_by("NonExistent") == set()
        assert graph.transitive_references("NonExistent") == set()
        assert graph.transitive_referenced_by("NonExistent") == set()
        assert not graph.is_reachable_from_visual("NonExistent", {"SomeVisual"})
        assert graph.find_cycles() == []

    def test_direct_single_hop_references(self):
        m1 = Measure(name="Base Revenue", table="Sales", expression="SUM(Sales[Amount])")
        m2 = Measure(name="Tax Amount", table="Sales", expression="[Base Revenue] * 0.1")
        dax = DaxDictionary(measures=[m1, m2])
        graph = build_dax_graph(dax)

        assert graph.references("Tax Amount") == {"Base Revenue"}
        assert graph.references("Base Revenue") == set()

        assert graph.referenced_by("Base Revenue") == {"Tax Amount"}
        assert graph.referenced_by("Tax Amount") == set()

    def test_multi_hop_transitive_references(self):
        # Chain: A <- B <- C (C references B references A)
        m_a = Measure(name="Base Margin", table="Sales", expression="SUM(Sales[Profit])")
        m_b = Measure(name="Net Margin", table="Sales", expression="[Base Margin] - 50")
        m_c = Measure(name="Margin Pct", table="Sales", expression="DIVIDE([Net Margin], 100)")
        m_unrelated = Measure(name="Headcount", table="HR", expression="COUNTROWS(Employees)")

        dax = DaxDictionary(measures=[m_a, m_b, m_c, m_unrelated])
        graph = build_dax_graph(dax)

        # Outgoing transitive references from Margin Pct
        assert graph.transitive_references("Margin Pct") == {"Net Margin", "Base Margin"}
        assert graph.transitive_references("Net Margin") == {"Base Margin"}
        assert graph.transitive_references("Base Margin") == set()

        # Incoming transitive references to Base Margin
        assert graph.transitive_referenced_by("Base Margin") == {"Net Margin", "Margin Pct"}
        assert graph.transitive_referenced_by("Net Margin") == {"Margin Pct"}
        assert graph.transitive_referenced_by("Margin Pct") == set()

        # Unrelated measure
        assert graph.transitive_references("Headcount") == set()
        assert graph.transitive_referenced_by("Headcount") == set()

    def test_is_reachable_from_visual(self):
        m_a = Measure(name="Base Revenue", table="Sales", expression="SUM(Sales[Amount])")
        m_b = Measure(name="Net Revenue", table="Sales", expression="[Base Revenue] * 0.9")
        m_c = Measure(name="Executive KPI", table="Sales", expression="[Net Revenue] / 100")
        m_unused = Measure(name="Legacy Measure", table="Sales", expression="100")

        dax = DaxDictionary(measures=[m_a, m_b, m_c, m_unused])
        graph = build_dax_graph(dax)

        # Visual only contains Executive KPI
        visual_refs = {"Executive KPI"}

        # Executive KPI is directly in visual
        assert graph.is_reachable_from_visual("Executive KPI", visual_refs)
        # Net Revenue and Base Revenue are transitively reachable
        assert graph.is_reachable_from_visual("Net Revenue", visual_refs)
        assert graph.is_reachable_from_visual("Base Revenue", visual_refs)
        # Legacy Measure is not reachable
        assert not graph.is_reachable_from_visual("Legacy Measure", visual_refs)

    def test_case_insensitive_matching(self):
        m_base = Measure(name="Base Revenue", table="Sales", expression="SUM(Sales[Amount])")
        # Reference in lowercase: [base revenue]
        m_ratio = Measure(name="Revenue Ratio", table="Sales", expression="[base revenue] / 10")
        dax = DaxDictionary(measures=[m_base, m_ratio])
        graph = build_dax_graph(dax)

        assert graph.references("Revenue Ratio") == {"Base Revenue"}
        assert graph.referenced_by("Base Revenue") == {"Revenue Ratio"}
        assert graph.is_reachable_from_visual("Base Revenue", {"revenue ratio"})

    def test_cycle_detection_and_safety(self):
        # A -> B -> A (circular reference)
        m_a = Measure(name="Measure A", table="Sales", expression="[Measure B] + 1")
        m_b = Measure(name="Measure B", table="Sales", expression="[Measure A] - 1")
        dax = DaxDictionary(measures=[m_a, m_b])
        graph = build_dax_graph(dax)

        cycles = graph.find_cycles()
        assert len(cycles) > 0

        # Must not hang or crash in transitive queries
        trans_a = graph.transitive_references("Measure A")
        assert "Measure B" in trans_a

        trans_b = graph.transitive_references("Measure B")
        assert "Measure A" in trans_b

        # is_reachable_from_visual must terminate cleanly
        assert graph.is_reachable_from_visual("Measure A", {"Measure B"})

    def test_calculated_column_references(self):
        cc1 = CalculatedColumn(name="GrossPrice", table="Sales", expression="Sales[UnitCost] * 1.2")
        m1 = Measure(name="Total Gross", table="Sales", expression="SUM(Sales[GrossPrice])")
        dax = DaxDictionary(measures=[m1], calculated_columns=[cc1])
        graph = build_dax_graph(dax)

        assert "GrossPrice" in graph.nodes
        assert graph.nodes["GrossPrice"].kind == "calculated_column"
        assert graph.references("Total Gross") == {"GrossPrice"}
