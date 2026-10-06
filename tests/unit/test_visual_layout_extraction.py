"""Visual layout data for the Studio report layer: positions, page canvas size, table_refs.

table_refs is display-only. These tests also pin that adding it leaves
measure_refs / fields_used (which drive DAX_UNUSED_MEASURE and `pbiscan fix`
deletions) exactly as they were.
"""
from __future__ import annotations

import json
from pathlib import Path

from pbiscan.extraction.pbir_parser import canvas_size, parse_pbir_visual
from pbiscan.extraction.raw import extract_entity_names
from pbiscan.extraction.report_parser import parse_visual_container
from pbiscan.service import ScanService

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


def _pbir_visual() -> dict:
    return {
        "name": "matrixVisual",
        "position": {"x": 40, "y": 96.5, "width": 600, "height": 320},
        "visual": {
            "visualType": "matrix",
            "query": {"queryState": {
                "Rows": {"projections": [{
                    "queryRef": "Calendar.Year",
                    "field": {"Column": {"Expression": {"SourceRef": {"Entity": "Calendar"}}, "Property": "Year"}},
                }]},
                "Values": {"projections": [{
                    "queryRef": "Sales.Total Sales",
                    "field": {"Measure": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": "Total Sales"}},
                }]},
            }},
        },
    }


class TestPbirVisual:
    def test_position_and_table_refs(self):
        v = parse_pbir_visual(_pbir_visual())
        assert (v.x, v.y, v.width, v.height) == (40, 96.5, 600, 320)
        assert v.table_refs == ["Calendar", "Sales"]

    def test_table_refs_do_not_change_measure_refs_or_fields_used(self):
        v = parse_pbir_visual(_pbir_visual())
        assert v.measure_refs == ["Total Sales"]
        assert v.fields_used == ["Total Sales"]

    def test_no_query_means_no_table_refs(self):
        v = parse_pbir_visual({"visual": {"visualType": "textbox"}})
        assert v.table_refs == []


class TestLegacyVisualContainer:
    def _container(self) -> dict:
        config = {"singleVisual": {
            "visualType": "clusteredColumnChart",
            "prototypeQuery": {
                "From": [{"Name": "s", "Entity": "Sales", "Type": 0}, {"Name": "d", "Entity": "Dates", "Type": 0}],
                "Select": [
                    {"Measure": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": "Revenue"}, "Name": "Sales.Revenue"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "Month"}, "Name": "Dates.Month"},
                ],
            },
        }}
        return {"x": 10, "y": 20, "width": 300, "height": 200, "config": json.dumps(config)}

    def test_position_and_table_refs_from_prototype_query(self):
        v = parse_visual_container(self._container())
        assert (v.x, v.y, v.width, v.height) == (10, 20, 300, 200)
        assert v.table_refs == ["Dates", "Sales"]

    def test_measure_refs_unchanged(self):
        v = parse_visual_container(self._container())
        assert v.measure_refs == ["Revenue"]
        assert sorted(v.fields_used) == ["Month", "Revenue"]


class TestHelpers:
    def test_extract_entity_names_walks_nested_json(self):
        tree = {"a": [{"SourceRef": {"Entity": "T1"}}, {"b": {"SourceRef": {"Entity": "T2"}}}],
                "c": {"SourceRef": {"Source": "alias-only"}}}
        assert extract_entity_names(tree) == {"T1", "T2"}

    def test_canvas_size_defaults(self):
        assert canvas_size({}) == (1280.0, 720.0)
        assert canvas_size({"width": 1920, "height": 1080}) == (1920.0, 1080.0)
        assert canvas_size({"width": "wide", "height": -5, }) == (1280.0, 720.0)
        assert canvas_size({"width": True}) == (1280.0, 720.0)


class TestScanApiOutput:
    def test_pages_carry_canvas_and_visual_layout(self):
        data = ScanService.execute_scan(GOLDEN_DIR / "test_calc_groups_selectedmeasure").to_dict()
        page = data["pages"][0]
        assert page["width"] > 0 and page["height"] > 0
        visual = page["visuals"][0]
        for key in ("x", "y", "width", "height", "table_refs", "measure_refs", "fields_used"):
            assert key in visual
        assert "Sales" in visual["table_refs"]

    def test_legacy_report_json_pages_carry_layout(self):
        data = ScanService.execute_scan(GOLDEN_DIR / "test_ambiguous_path").to_dict()
        assert data["pages"], "fixture should have pages"
        for page in data["pages"]:
            assert page["width"] > 0 and page["height"] > 0
            for visual in page["visuals"]:
                assert isinstance(visual["table_refs"], list)
