"""Unit tests for ModelGraph topology methods (canonical/model.py)."""
from __future__ import annotations
from pbiscan.canonical.model import ModelGraph, Table, Relationship


class TestModelTopology:
    def test_empty_model(self):
        mg = ModelGraph()
        assert mg.connected_components() == []
        assert mg.isolated_tables() == []
        assert mg.relationship_paths("A", "B") == []

    def test_isolated_tables_and_components(self):
        t1 = Table(name="FactSales")
        t2 = Table(name="DimCustomer")
        t3 = Table(name="IsolatedLog")
        r1 = Relationship(from_table="FactSales", from_column="CustID", to_table="DimCustomer", to_column="CustID")
        
        mg = ModelGraph(tables=[t1, t2, t3], relationships=[r1])

        # Isolated tables
        assert mg.isolated_tables() == ["IsolatedLog"]

        # Connected components
        comps = mg.connected_components()
        assert len(comps) == 2
        # One component is {FactSales, DimCustomer}
        assert {"FactSales", "DimCustomer"} in comps
        # Second component is {IsolatedLog}
        assert {"IsolatedLog"} in comps

    def test_relationship_paths_single_path(self):
        # FactSales -> DimCustomer -> DimCity
        t1 = Table(name="FactSales")
        t2 = Table(name="DimCustomer")
        t3 = Table(name="DimCity")
        r1 = Relationship(from_table="FactSales", from_column="CustID", to_table="DimCustomer", to_column="CustID")
        r2 = Relationship(from_table="DimCustomer", from_column="CityID", to_table="DimCity", to_column="CityID")

        mg = ModelGraph(tables=[t1, t2, t3], relationships=[r1, r2])

        paths = mg.relationship_paths("FactSales", "DimCity")
        assert len(paths) == 1
        assert paths[0] == ["FactSales", "DimCustomer", "DimCity"]

    def test_relationship_paths_ambiguous_multiple_paths(self):
        # FactSales -> DimStore -> DimRegion
        # FactSales -> DimRegion (Direct)
        t_sales = Table(name="FactSales")
        t_store = Table(name="DimStore")
        t_region = Table(name="DimRegion")

        r1 = Relationship(from_table="FactSales", from_column="StoreID", to_table="DimStore", to_column="StoreID")
        r2 = Relationship(from_table="DimStore", from_column="RegionID", to_table="DimRegion", to_column="RegionID")
        r3 = Relationship(from_table="FactSales", from_column="RegionID", to_table="DimRegion", to_column="RegionID")

        mg = ModelGraph(tables=[t_sales, t_store, t_region], relationships=[r1, r2, r3])

        paths = mg.relationship_paths("FactSales", "DimRegion")
        assert len(paths) == 2
        path_tuples = [tuple(p) for p in paths]
        assert ("FactSales", "DimRegion") in path_tuples
        assert ("FactSales", "DimStore", "DimRegion") in path_tuples

    def test_relationship_paths_inactive_filtering(self):
        # FactSales -> DimDate (Active on OrderDate, Inactive on ShipDate)
        t_sales = Table(name="FactSales")
        t_date = Table(name="DimDate")

        r_active = Relationship(from_table="FactSales", from_column="OrderDate", to_table="DimDate", to_column="Date", is_active=True)
        r_inactive = Relationship(from_table="FactSales", from_column="ShipDate", to_table="DimDate", to_column="Date", is_active=False)

        mg = ModelGraph(tables=[t_sales, t_date], relationships=[r_active, r_inactive])

        # Default active_only=True
        active_paths = mg.relationship_paths("FactSales", "DimDate", active_only=True)
        assert len(active_paths) == 1

        # active_only=False
        all_paths = mg.relationship_paths("FactSales", "DimDate", active_only=False)
        assert len(all_paths) == 1  # only 1 simple path in undirected graph between the 2 tables directly
