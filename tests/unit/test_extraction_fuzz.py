"""Property-based tests for the extraction layer.

Two guarantees:
  1. Nothing crashes. Arbitrary text, bytes or wrongly shaped JSON either
     parses, or fails with a PBIScanError that names the file. Never a raw
     AttributeError/TypeError/UnicodeDecodeError traceback.
  2. Well-formed TMDL parses the same however it is laid out: tabs or spaces,
     LF or CRLF, with or without a byte-order mark, and with names that need
     quoting ('Bob''s Sales', 'a = b', 'Dim.Customer').
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pbiscan.extraction.pbip_reader import PBIPReader, PBIScanError
from pbiscan.extraction.raw import decode_text
from pbiscan.extraction.tmdl_parser import (
    parse_col_ref,
    parse_tmdl_relationships_text,
    parse_tmdl_table_text,
    split_declaration,
    unquote,
)

FUZZ = settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
FUZZ_IO = settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_KEYWORDS = [
    "table", "measure", "column", "calculationItem", "partition", "annotation",
    "relationship", "formatString:", "lineageTag:", "dataType:", "isHidden",
    "source =", "fromColumn:", "toColumn:", "///", "```", "=", "'",
]

_indent = st.sampled_from(["", "\t", "\t\t", "\t\t\t", "  ", "    ", " \t", "\t  "])
_word = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\r\n"),
    max_size=20,
)
_tmdl_line = st.builds(
    lambda ind, kw, sep, rest: f"{ind}{kw}{sep}{rest}",
    _indent, st.sampled_from(_KEYWORDS), st.sampled_from([" ", "\t", "", " = "]), _word,
)
_tmdl_noise = st.builds(
    lambda lines, nl: nl.join(lines),
    st.lists(_tmdl_line | _word, max_size=30),
    st.sampled_from(["\n", "\r\n", "\r"]),
)

# Object names as Power BI allows them: no line breaks, no surrounding whitespace.
_name = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc", "Zl", "Zp")),
    min_size=1, max_size=25,
).map(str.strip).filter(bool)
# A single-line DAX-ish expression.
_expression = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc", "Zl", "Zp")),
    min_size=1, max_size=40,
).map(str.strip).filter(lambda e: bool(e) and not e.startswith("```"))

_json_scalar = st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(max_size=10)
_json = st.recursive(
    _json_scalar,
    lambda children: st.lists(children, max_size=4)
    | st.dictionaries(
        st.sampled_from([
            "model", "tables", "name", "columns", "measures", "relationships", "partitions",
            "source", "expression", "visual", "visualType", "query", "queryState",
            "projections", "field", "Measure", "Property", "position", "sections",
            "visualContainers", "config", "filters", "displayName", "entities",
        ]) | st.text(max_size=5),
        children,
        max_size=5,
    ),
    max_leaves=25,
)


def _quote(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"


# ---------------------------------------------------------------------------
# 1. Nothing crashes
# ---------------------------------------------------------------------------

@FUZZ
@given(st.text())
def test_table_parser_never_crashes_on_arbitrary_text(text: str) -> None:
    table = parse_tmdl_table_text(text)
    assert table is None or isinstance(table.name, str)


@FUZZ
@given(_tmdl_noise)
def test_table_parser_never_crashes_on_tmdl_shaped_noise(text: str) -> None:
    table = parse_tmdl_table_text(text)
    if table is not None:
        for m in table.measures:
            assert isinstance(m["name"], str) and isinstance(m["expression"], str)


@FUZZ
@given(_tmdl_noise)
def test_relationship_parser_never_crashes(text: str) -> None:
    for rel in parse_tmdl_relationships_text(text):
        assert rel.from_table and rel.from_column and rel.to_table and rel.to_column


@FUZZ
@given(st.binary(max_size=200))
def test_decode_text_only_raises_parse_error(data: bytes) -> None:
    try:
        decode_text(data)
    except PBIScanError:
        pass


def _write_project(root: Path, files: dict[str, bytes]) -> Path:
    project = root / "proj"
    for rel, content in files.items():
        path = project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return project


def _read_or_clean_error(files: dict[str, bytes]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project = _write_project(Path(tmp), files)
        try:
            PBIPReader().read(project)
        except PBIScanError:
            pass


@FUZZ_IO
@given(st.binary(max_size=300) | _tmdl_noise.map(lambda t: t.encode("utf-8")))
def test_reader_survives_any_tmdl_table_bytes(data: bytes) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project = _write_project(Path(tmp), {
            "fixture.SemanticModel/definition/tables/Good.tmdl": b"table Good\n\tmeasure M = 1\n",
            "fixture.SemanticModel/definition/tables/Fuzz.tmdl": data,
        })
        raw = PBIPReader().read(project)
        # The readable table always survives; an unusable one is reported, not dropped silently.
        assert "Good" in [t.name for t in raw.tables]
        fuzz_file = str(project / "fixture.SemanticModel/definition/tables/Fuzz.tmdl")
        parsed_names = [t.source_file for t in raw.tables]
        assert (fuzz_file in parsed_names) != (fuzz_file in raw.unread_files)


@FUZZ_IO
@given(_json)
def test_reader_survives_any_model_bim_shape(doc: Any) -> None:
    _read_or_clean_error({"fixture.SemanticModel/model.bim": json.dumps(doc).encode()})


@FUZZ_IO
@given(_json, _json)
def test_reader_survives_any_pbir_page_and_visual_shape(page: Any, visual: Any) -> None:
    _read_or_clean_error({
        "fixture.SemanticModel/definition/tables/T.tmdl": b"table T\n",
        "fixture.Report/definition/pages/p1/page.json": json.dumps(page).encode(),
        "fixture.Report/definition/pages/p1/visuals/v1/visual.json": json.dumps(visual).encode(),
    })


@FUZZ_IO
@given(_json, _json)
def test_reader_survives_any_legacy_report_shape(report: Any, bookmark: Any) -> None:
    _read_or_clean_error({
        "fixture.SemanticModel/definition/tables/T.tmdl": b"table T\n",
        "fixture.Report/report.json": json.dumps(report).encode(),
        "fixture.Report/definition/bookmarks/b.bookmark.json": json.dumps(bookmark).encode(),
    })


# ---------------------------------------------------------------------------
# 2. Layout does not change meaning
# ---------------------------------------------------------------------------

@FUZZ
@given(_name)
def test_quoted_names_round_trip(name: str) -> None:
    assert unquote(_quote(name)) == name
    assert split_declaration(f"{_quote(name)} = 1") == (name, "1")
    assert split_declaration(_quote(name)) == (name, None)


@FUZZ
@given(_name, _name)
def test_column_refs_round_trip(table: str, column: str) -> None:
    assert parse_col_ref(f"{_quote(table)}.{_quote(column)}") == (table, column)


@FUZZ
@given(
    table=_name,
    measures=st.lists(st.tuples(_name, _expression), min_size=1, max_size=5, unique_by=lambda m: m[0]),
    columns=st.lists(_name, max_size=4),
    indent=st.sampled_from(["\t", "  ", "    "]),
    newline=st.sampled_from(["\n", "\r\n"]),
    encoding=st.sampled_from(["utf-8", "utf-8-sig", "utf-16"]),
    with_properties=st.booleans(),
)
def test_well_formed_table_parses_identically_in_any_layout(
    table: str,
    measures: list[tuple[str, str]],
    columns: list[str],
    indent: str,
    newline: str,
    encoding: str,
    with_properties: bool,
) -> None:
    lines = [f"table {_quote(table)}"]
    for name, expr in measures:
        lines.append(f"{indent}measure {_quote(name)} = {expr}")
        if with_properties:
            lines.append(f"{indent * 2}formatString: 0.00")
            lines.append(f"{indent * 2}lineageTag: 00000000-0000-0000-0000-000000000000")
        lines.append("")
    for col in columns:
        lines.append(f"{indent}column {_quote(col)}")
        lines.append(f"{indent * 2}dataType: string")
        lines.append("")
    text = decode_text(newline.join(lines).encode(encoding))

    parsed = parse_tmdl_table_text(text)

    assert parsed is not None
    assert parsed.name == table
    assert [(m["name"], m["expression"]) for m in parsed.measures] == measures
    assert [c["name"] for c in parsed.columns] == columns


@FUZZ
@given(
    body=st.lists(_expression, min_size=1, max_size=4),
    indent=st.sampled_from(["\t", "    "]),
)
def test_fenced_expression_is_taken_verbatim(body: list[str], indent: str) -> None:
    """Inside ``` ... ``` lines that look like properties are expression text."""
    body = body + ["lineageTag: inside-the-fence"]
    lines = ["table T", f"{indent}measure M = ```"]
    lines += [f"{indent * 3}{b}" for b in body]
    lines += [f"{indent * 3}```", f"{indent * 2}formatString: 0"]

    parsed = parse_tmdl_table_text("\n".join(lines))

    assert parsed is not None
    (measure,) = parsed.measures
    assert measure["expression"] == "\n".join(body)
    assert measure["formatString"] == "0"


@FUZZ
@given(
    rels=st.lists(st.tuples(_name, _name, _name, _name), min_size=1, max_size=4),
    newline=st.sampled_from(["\n", "\r\n"]),
)
def test_relationships_round_trip(rels: list[tuple[str, str, str, str]], newline: str) -> None:
    lines: list[str] = []
    for i, (ft, fc, tt, tc) in enumerate(rels):
        lines += [
            f"relationship r{i}",
            f"\tfromColumn: {_quote(ft)}.{_quote(fc)}",
            f"\ttoColumn: {_quote(tt)}.{_quote(tc)}",
            "",
        ]
    parsed = parse_tmdl_relationships_text(newline.join(lines))
    assert [(r.from_table, r.from_column, r.to_table, r.to_column) for r in parsed] == rels
