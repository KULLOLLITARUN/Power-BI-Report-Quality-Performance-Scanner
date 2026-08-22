"""Regression tests: a single file with a non-UTF-8 byte anywhere in a PBIP project
must never crash the whole scan.

pbip_reader.py's per-file TMDL parsers (`_parse_single_tmdl_table`,
`_parse_tmdl_relationships`, and the roles-folder loop) previously only caught
`OSError` around their `read_text(encoding="utf-8")` calls. A malformed-encoding
byte anywhere in a table, relationships, or RLS role file raises
`UnicodeDecodeError` (a `ValueError` subclass, not an `OSError`), which propagated
uncaught and crashed `pbiscan scan` outright for the entire project — even though
every OTHER file was perfectly readable. `_load_json` (used for the required
model.bim/report.json/.pbir/.pbism structural files) had the same gap, surfacing
a raw `UnicodeDecodeError` instead of the clean `ParseError` its docstring
promises for every other failure mode.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from pbiscan.extraction.pbip_reader import PBIPReader, ParseError
from pbiscan.service import ScanService

GOLDEN_DIR = Path(__file__).parent.parent / "golden"


class TestTmdlEncodingResilience:
    def test_malformed_table_tmdl_is_skipped_not_fatal(self, tmp_path: Path):
        reader = PBIPReader()
        bad_file = tmp_path / "BadTable.tmdl"
        bad_file.write_bytes(b"table BadTable\n\t/// legacy byte: \xcb\n")

        # Previously raised UnicodeDecodeError; must now return None (skip) cleanly.
        result = reader._parse_single_tmdl_table(bad_file)
        assert result is None

    def test_malformed_relationships_tmdl_returns_empty_not_fatal(self, tmp_path: Path):
        reader = PBIPReader()
        bad_file = tmp_path / "relationships.tmdl"
        bad_file.write_bytes(b"relationship Rel1\n\t/// legacy byte: \xcb\n")

        result = reader._parse_tmdl_relationships(bad_file)
        assert result == []

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


class TestLoadJsonEncodingResilience:
    def test_malformed_bim_raises_clean_parse_error_not_raw_unicode_error(self, tmp_path: Path):
        reader = PBIPReader()
        bad_file = tmp_path / "model.bim"
        bad_file.write_bytes(b'{"model": {"tables": []}} /* legacy byte: \xcb */')

        try:
            reader._load_json(bad_file)
            assert False, "expected ParseError"
        except ParseError as exc:
            assert "UTF-8" in str(exc) or "decode" in str(exc).lower()
        except UnicodeDecodeError:
            raise AssertionError(
                "_load_json leaked a raw UnicodeDecodeError instead of wrapping it in ParseError"
            )
