"""Regression tests: a single file with a non-UTF-8 byte anywhere in a PBIP project
must never crash the whole scan.

The per-file TMDL parsers (`parse_tmdl_table`, `parse_tmdl_relationships`,
and the roles-folder loop in tmdl_parser.py) previously only caught
`OSError` around their `read_text(encoding="utf-8")` calls. A malformed-encoding
byte anywhere in a table, relationships, or RLS role file raises
`UnicodeDecodeError` (a `ValueError` subclass, not an `OSError`), which propagated
uncaught and crashed `pbiscan scan` outright for the entire project — even though
every OTHER file was perfectly readable. `load_json` (used for the required
model.bim/report.json/.pbir/.pbism structural files) had the same gap, surfacing
a raw `UnicodeDecodeError` instead of the clean `ParseError` its docstring
promises for every other failure mode.

A skipped file is now reported: it appears in the scan warnings and in
`unread_files`, and unused-measure detection is turned off for that scan,
because the skipped file could be the only place a measure is used.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pbiscan.extraction.raw import ParseError, load_json
from pbiscan.extraction.tmdl_parser import parse_tmdl_model, parse_tmdl_relationships, parse_tmdl_table
from pbiscan.service import ScanService

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


class TestTmdlEncodingResilience:
    def test_malformed_table_tmdl_raises_parse_error(self, tmp_path: Path):
        bad_file = tmp_path / "BadTable.tmdl"
        bad_file.write_bytes(b"table BadTable\n\t/// legacy byte: \xcb\n")

        with pytest.raises(ParseError, match="UTF-8"):
            parse_tmdl_table(bad_file)

    def test_malformed_relationships_tmdl_raises_parse_error(self, tmp_path: Path):
        bad_file = tmp_path / "relationships.tmdl"
        bad_file.write_bytes(b"relationship Rel1\n\t/// legacy byte: \xcb\n")

        with pytest.raises(ParseError, match="UTF-8"):
            parse_tmdl_relationships(bad_file)

    def test_model_skips_and_reports_each_unreadable_file(self, tmp_path: Path):
        definition = tmp_path / "definition"
        (definition / "tables").mkdir(parents=True)
        (definition / "roles").mkdir()
        (definition / "tables" / "Good.tmdl").write_text("table Good\n\tmeasure M = 1\n", encoding="utf-8")
        bad_table = definition / "tables" / "Bad.tmdl"
        bad_table.write_bytes(b"table Bad\n\t/// \xcb\n")
        no_decl = definition / "tables" / "Empty.tmdl"
        no_decl.write_text("/// just a comment\n", encoding="utf-8")
        bad_role = definition / "roles" / "Reader.tmdl"
        bad_role.write_bytes(b"role Reader\n\t/// \xcb\n")
        bad_rels = definition / "relationships.tmdl"
        bad_rels.write_bytes(b"relationship R\n\t/// \xcb\n")

        model = parse_tmdl_model(tmp_path)

        assert [t.name for t in model.tables] == ["Good"]
        assert sorted(model.unread_files) == sorted(str(p) for p in (bad_table, no_decl, bad_role, bad_rels))
        assert len(model.warnings) == 4
        assert any(str(no_decl) in w and "no `table` declaration" in w for w in model.warnings)

    @pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16"])
    def test_byte_order_marks_are_honored(self, tmp_path: Path, encoding: str):
        """A BOM used to make the first line unrecognizable and drop the whole table."""
        f = tmp_path / "Sales.tmdl"
        f.write_bytes("table Sales\n\tmeasure Total = 1\n".encode(encoding))

        table = parse_tmdl_table(f)
        assert table is not None
        assert table.name == "Sales"
        assert [m["name"] for m in table.measures] == ["Total"]

    def test_scan_survives_one_corrupted_table_among_many(self, tmp_path: Path):
        """End-to-end: a real multi-table TMDL project where ONE table file has a
        bad byte must still scan successfully and report findings for every other
        table, rather than crashing the whole scan."""
        src = GOLDEN_DIR / "test_m_hardcoded_datasource"
        dest = tmp_path / "test_m_hardcoded_datasource"
        shutil.copytree(src, dest)

        corrupted = dest / "fixture.SemanticModel" / "definition" / "tables" / "LocalOrders.tmdl"
        corrupted.write_bytes(b"table LocalOrders\n\t/// legacy byte: \xcb\n")

        # Must not raise — this is the exact regression.
        result = ScanService.execute_scan(dest)

        # The corrupted table is dropped, but findings from the other 3 tables
        # (CloudSales, DownloadsCustomers, SqlDatabase) still surface normally.
        assert any(i.rule_id == "M_HARDCODED_DATA_SOURCE" for i in result.issues)
        table_names = [t.name for t in result.report.model.tables]
        assert "LocalOrders" not in table_names
        assert "DownloadsCustomers" in table_names

        # ...and the user is told, and nothing is reported as unused on partial data.
        assert any("LocalOrders.tmdl" in w for w in result.warnings)
        assert any("DAX_UNUSED_MEASURE was not checked" in w for w in result.warnings)
        assert not any(i.rule_id == "DAX_UNUSED_MEASURE" for i in result.issues)


class TestLoadJsonEncodingResilience:
    def test_malformed_bim_raises_clean_parse_error_not_raw_unicode_error(self, tmp_path: Path):
        bad_file = tmp_path / "model.bim"
        bad_file.write_bytes(b'{"model": {"tables": []}} /* legacy byte: \xcb */')

        with pytest.raises(ParseError, match="UTF-8"):
            load_json(bad_file)

    def test_json_with_utf8_bom_loads(self, tmp_path: Path):
        f = tmp_path / "model.bim"
        f.write_bytes(b'\xef\xbb\xbf{"model": {"tables": []}}')
        assert load_json(f) == {"model": {"tables": []}}
