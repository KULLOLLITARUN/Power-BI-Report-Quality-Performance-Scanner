"""extract_column_refs: (table, column) pairs from PBIR and legacy report JSON."""
from __future__ import annotations

import json

from pbiscan.extraction.pbir_parser import parse_pbir_visual
from pbiscan.extraction.raw import extract_column_refs
from pbiscan.extraction.report_parser import parse_visual_container


def col(entity: str, prop: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def test_pbir_projection_and_nested_aggregation():
    node = {
        "queryState": {"Values": {"projections": [
            {"field": col("Sales", "Region")},
            {"field": {"Aggregation": {"Expression": col("Sales", "Amount"), "Function": 0}}},
        ]}},
    }
    assert extract_column_refs(node) == [("Sales", "Amount"), ("Sales", "Region")]


def test_measures_and_hierarchy_levels_are_not_columns():
    node = [
        {"Measure": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": "Total"}},
        {"HierarchyLevel": {"Expression": {"Hierarchy": {"Expression": {"SourceRef": {"Entity": "Date"}}, "Hierarchy": "H"}}, "Level": "Year"}},
    ]
    assert extract_column_refs(node) == []


def test_alias_is_resolved_through_the_surrounding_from():
    query = {
        "From": [{"Name": "s", "Entity": "Sales", "Type": 0}],
        "Select": [{"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": "Region"}, "Name": "Sales.Region"}],
        "Where": [{"Condition": {"In": {"Expressions": [
            {"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": "Year"}}]}}}],
    }
    assert extract_column_refs(query) == [("Sales", "Region"), ("Sales", "Year")]


def test_alias_with_no_matching_from_is_left_out():
    node = {"Column": {"Expression": {"SourceRef": {"Source": "x"}}, "Property": "Region"}}
    assert extract_column_refs(node) == []


def test_alias_does_not_leak_to_a_sibling_scope():
    node = [
        {"From": [{"Name": "s", "Entity": "Sales"}],
         "Where": [{"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": "A"}}]},
        {"Where": [{"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": "B"}}]},
    ]
    assert extract_column_refs(node) == [("Sales", "A")]


def test_odd_shapes_are_ignored_not_raised():
    for node in (None, "text", 3, {"Column": "x"}, {"Column": {"Property": 5}}, {"From": "nope"}, [[], {}]):
        assert extract_column_refs(node) == []


def test_pbir_visual_collects_query_filters_and_formatting():
    visual = {
        "position": {"x": 0, "y": 0, "width": 100, "height": 100},
        "visual": {
            "visualType": "clusteredBarChart",
            "query": {"queryState": {"Category": {"projections": [{"field": col("Sales", "Region")}]}}},
            "objects": {"dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": {"FillRule": {"Input": col("Sales", "Margin")}}}}}}}]},
        },
        "filterConfig": {"filters": [{"field": col("Product", "Category")}]},
    }
    v = parse_pbir_visual(visual)
    assert v is not None
    assert v.column_refs == [("Product", "Category"), ("Sales", "Margin"), ("Sales", "Region")]


def test_legacy_visual_collects_prototype_query_and_visual_filters():
    config = {"singleVisual": {"visualType": "tableEx", "prototypeQuery": {
        "From": [{"Name": "s", "Entity": "Sales"}],
        "Select": [{"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": "Region"}, "Name": "Sales.Region"}],
    }}}
    filters = [{"expression": col("Date", "Year")}]
    v = parse_visual_container({"config": json.dumps(config), "filters": json.dumps(filters), "x": 0, "y": 0, "width": 10, "height": 10})
    assert v is not None
    assert v.column_refs == [("Date", "Year"), ("Sales", "Region")]
