"""Property-based tests (hypothesis) for the remediation patchers and the DAX scanners.

Each property generates a random model, runs one patcher, and compares the result with an
oracle built independently of the code under test (the generator knows what it asked for):

- a measure patch removes exactly that measure and nothing else;
- a relationship patch changes exactly that relationship, even among look-alike names;
- a data-source patch changes exactly that table;
- a backup restores byte for byte, and a failed restore leaves the project untouched;
- nested CALCULATE is found exactly when the generated tree nests one, and comment stripping
  never touches a string literal.

Examples that once failed in real use are pinned in test_remediation_engine.py; these cover the
space around them.
"""
from __future__ import annotations

import copy
import json
import string
import tempfile
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from pbiscan.canonical.model import looks_like_date_table_name
from pbiscan.extraction.tmdl_parser import parse_tmdl_relationships_text
from pbiscan.remediation.backup import BackupManager
from pbiscan.remediation.models import PatchChunk
from pbiscan.remediation.patchers.datasource import DataSourcePatcher
from pbiscan.remediation.patchers.measure import MeasurePatcher
from pbiscan.remediation.patchers.relationship import RelationshipPatcher
from pbiscan.rules.dax import has_nested_calculate, strip_dax_comments

# Randomised: left out of the quick tier (`-m "not slow"`).
pytestmark = pytest.mark.slow

PROPERTY = settings(max_examples=120, deadline=None, suppress_health_check=[HealthCheck.too_slow])
BOM = chr(0xFEFF)


def apply_chunk(content: str, chunk: PatchChunk) -> str:
    """Apply a chunk by its line range, the way the engine does (never by text search)."""
    lines = content.splitlines(keepends=True)
    assert "".join(lines[chunk.start_line - 1:chunk.end_line]) == chunk.original_text
    return "".join(lines[:chunk.start_line - 1]) + chunk.replacement_text + "".join(lines[chunk.end_line:])


# --------------------------------------------------------------------------- names
_IDENT = st.text(alphabet=string.ascii_letters + string.digits + "_", min_size=1, max_size=7).filter(
    lambda s: not s[0].isdigit()
)
_SPACED = st.builds(lambda a, b: f"{a} {b}", _IDENT, _IDENT)
NAME = st.one_of(_IDENT, _SPACED)


def unique_names(min_size: int = 1, max_size: int = 5, strategy=NAME):
    return st.lists(strategy, min_size=min_size, max_size=max_size, unique_by=lambda s: s.lower())


# ---------------------------------------------------------------------- BIM measures
@st.composite
def bim_models(draw):
    """A model.bim with measures unique across the model and columns that may share a measure's name."""
    table_names = draw(unique_names(1, 4))
    pool = draw(unique_names(1, 6))
    owner = draw(st.lists(st.integers(0, len(table_names) - 1), min_size=len(pool), max_size=len(pool)))
    tables = []
    for ti, tname in enumerate(table_names):
        measures = [{"name": m, "expression": f"{i + 1}"} for i, (m, o) in enumerate(zip(pool, owner)) if o == ti]
        taken = {m["name"].lower() for m in measures}
        col_names = [c for c in draw(st.lists(st.sampled_from(pool + ["Id", "Key"]), max_size=4, unique_by=str.lower))
                     if c.lower() not in taken]
        table: dict[str, Any] = {
            "name": tname,
            "columns": [{"name": c, "dataType": "string", "sourceColumn": c} for c in col_names],
            "partitions": [{"name": tname, "source": {"type": "m", "expression": "let Source = 1 in Source"}}],
        }
        if measures or draw(st.booleans()):
            table["measures"] = measures
        if draw(st.booleans()):
            table["annotations"] = [{"name": "note", "value": "x"}]
        tables.append(table)
    targets = [(t["name"], m["name"]) for t in tables for m in t.get("measures", [])]
    assume(targets)
    return {"model": {"culture": "en-US", "tables": tables, "relationships": []}}, draw(st.sampled_from(targets))


@PROPERTY
@given(bim_models(), st.booleans(), st.booleans())
def test_bim_measure_patch_removes_exactly_that_measure(case, with_bom, trailing_newline):
    model, (table_name, measure_name) = case
    content = json.dumps(model, indent=2) + ("\n" if trailing_newline else "")
    if with_bom:
        content = BOM + content

    chunk = MeasurePatcher()._patch_bim(content, table_name, measure_name)
    assert chunk is not None, "a well-formed model with a unique measure name must be patchable"

    expected = copy.deepcopy(model)
    for t in expected["model"]["tables"]:
        if t["name"] == table_name:
            t["measures"] = [m for m in t["measures"] if m["name"] != measure_name]
    assert json.loads(apply_chunk(content, chunk).lstrip(BOM)) == expected


# --------------------------------------------------------------------- TMDL measures
def _q(name: str) -> str:
    return f"'{name}'" if " " in name else name


@st.composite
def tmdl_tables(draw):
    """A table file built from member blocks; the target measure's block is known exactly."""
    names = draw(unique_names(2, 6))
    kinds = draw(st.lists(st.sampled_from(["measure", "measure", "column", "hierarchy", "annotation"]),
                          min_size=len(names), max_size=len(names)))
    assume("measure" in kinds)
    blocks: list[tuple[str, str]] = []  # (kind, text)
    for kind, name in zip(kinds, names):
        docs = "".join(f"\t/// doc {i}\n" for i in range(draw(st.integers(0, 3))))
        if kind == "measure":
            head = f"\tmeasure {_q(name)} = " + draw(st.sampled_from(["1", "SUM(T[x])", "[Other] + 1"])) + "\n"
            body = ""
            if draw(st.booleans()):
                body += "\t\tformatString: 0\n"
            if draw(st.booleans()):
                body += "\t\tformatStringDefinition = IF([A] > 0, \"0.0\", \"0\")\n"
            if draw(st.booleans()):
                body += f"\t\tannotation Note = {name.replace(' ', '_')}\n"
            if draw(st.booleans()):
                head = f"\tmeasure {_q(name)} =\n\t\t\tVAR x = 1\n\t\t\tRETURN x\n"
            text = docs + head + body
        elif kind == "column":
            text = docs + f"\tcolumn {_q(name)}\n\t\tdataType: string\n"
        elif kind == "hierarchy":
            text = docs + f"\thierarchy {_q(name)}\n\t\tlevel L1\n\t\t\tcolumn: {_q(names[0])}\n"
        else:
            text = f"\tannotation {name.replace(' ', '_')} = Table\n"
        blocks.append((kind, text))
    measure_ids = [i for i, (k, _) in enumerate(blocks) if k == "measure"]
    target = draw(st.sampled_from(measure_ids))
    separator = "\n"
    return names, blocks, target, separator


@PROPERTY
@given(tmdl_tables())
def test_tmdl_measure_patch_removes_exactly_that_measure_block(case):
    names, blocks, target, sep = case
    # A blank line follows every member except the last, so a block's trailing blank line goes with it.
    texts = [text + (sep if i < len(blocks) - 1 else "") for i, (_, text) in enumerate(blocks)]
    content = "table T\n" + sep + "".join(texts)
    target_name = names[target]

    chunk = MeasurePatcher()._patch_tmdl(content, target_name)
    assert chunk is not None

    # Sibling members (hierarchies, table annotations, other measures) must survive untouched,
    # and every doc-comment line above the target goes with it.
    expected = "table T\n" + sep + "".join(t for i, t in enumerate(texts) if i != target)
    assert apply_chunk(content, chunk) == expected


# ------------------------------------------------------------------- relationships
_TABLES = ["Sales", "ReturnSales", "SalesPlan", "Calendar", "Product", "Sales2", "sales_old"]
_COLS = ["Date", "Id", "DateKey", "Product"]


@st.composite
def relationship_sets(draw):
    endpoints = st.tuples(st.sampled_from(_TABLES), st.sampled_from(_COLS), st.sampled_from(_TABLES), st.sampled_from(_COLS))
    rels = draw(st.lists(endpoints, min_size=1, max_size=8, unique=True))
    seen: set[frozenset] = set()
    unique = []
    for ft, fc, tt, tc in rels:
        key = frozenset({(ft.lower(), fc.lower()), (tt.lower(), tc.lower())})
        if (ft.lower(), fc.lower()) == (tt.lower(), tc.lower()) or key in seen:
            continue
        seen.add(key)
        unique.append((ft, fc, tt, tc))
    assume(unique)
    behaviours = draw(st.lists(st.sampled_from(["bothDirections", "oneDirection"]), min_size=len(unique), max_size=len(unique)))
    both = [i for i, b in enumerate(behaviours) if b == "bothDirections"]
    assume(both)
    target = draw(st.sampled_from(both))
    if draw(st.booleans()):
        # Plant a bidirectional look-alike ("ReturnSales" for "Sales") just before the target:
        # substring or nearby-line matching picks it instead of the real one.
        ft, fc, tt, tc = unique[target]
        look = ("Return" + ft, fc, tt, tc)
        key = frozenset({(look[0].lower(), fc.lower()), (tt.lower(), tc.lower())})
        if key not in seen:
            unique.insert(target, look)
            behaviours.insert(target, "bothDirections")
            target += 1
    return unique, behaviours, target


@PROPERTY
@given(relationship_sets())
def test_bim_relationship_patch_flips_exactly_one_relationship(case):
    rels, behaviours, target = case
    entries = [
        {"name": f"r{i}", "fromTable": ft, "fromColumn": fc, "toTable": tt, "toColumn": tc, "crossFilteringBehavior": b}
        for i, ((ft, fc, tt, tc), b) in enumerate(zip(rels, behaviours))
    ]
    content = json.dumps({"model": {"relationships": entries}}, indent=2)
    ft, fc, tt, tc = rels[target]

    chunk = RelationshipPatcher()._patch_bim(content, ft, fc, tt, tc)
    assert chunk is not None

    expected = copy.deepcopy(entries)
    expected[target]["crossFilteringBehavior"] = "oneDirection"
    assert json.loads(apply_chunk(content, chunk))["model"]["relationships"] == expected


@PROPERTY
@given(relationship_sets())
def test_tmdl_relationship_patch_flips_exactly_one_relationship(case):
    rels, behaviours, target = case
    content = "".join(
        f"relationship rel{i}\n\tcrossFilteringBehavior: {b}\n\tfromColumn: {ft}.{fc}\n\ttoColumn: {tt}.{tc}\n\n"
        for i, ((ft, fc, tt, tc), b) in enumerate(zip(rels, behaviours))
    )
    ft, fc, tt, tc = rels[target]

    chunk = RelationshipPatcher()._patch_tmdl(content, ft, fc, tt, tc)
    assert chunk is not None

    after = parse_tmdl_relationships_text(apply_chunk(content, chunk))
    got = [r.raw["crossFilteringBehavior"] for r in after]
    want = list(behaviours)
    want[target] = "oneDirection"
    assert got == want


# ------------------------------------------------------------------------ data source
_FILE = st.text(alphabet=string.ascii_letters + string.digits + "_-", min_size=1, max_size=8)


@st.composite
def datasource_models(draw):
    names = draw(unique_names(1, 4))
    flags = draw(st.lists(st.booleans(), min_size=len(names), max_size=len(names)))
    assume(any(flags))
    tables = []
    for name, local in zip(names, flags):
        if local:
            expr = (f'let Source = Excel.Workbook(File.Contents("C:\\Users\\a\\Desktop\\{draw(_FILE)}.xlsx")) in Source')
        else:
            expr = "let Source = Sql.Database(\"srv\", \"db\") in Source"
        tables.append({"name": name, "partitions": [{"name": name, "source": {"type": "m", "expression": expr}}]})
    targets = [t["name"] for t, local in zip(tables, flags) if local]
    return {"model": {"tables": tables}}, draw(st.sampled_from(targets))


@PROPERTY
@given(datasource_models())
def test_datasource_patch_changes_exactly_the_named_table(case):
    model, target = case
    content = json.dumps(model, indent=2)

    chunk = DataSourcePatcher()._patch_bim(content, target)
    assert chunk is not None

    patched = json.loads(apply_chunk(content, chunk))
    for before, after in zip(model["model"]["tables"], patched["model"]["tables"]):
        if before["name"] == target:
            assert before != after
            assert "DataFolderPath" in after["partitions"][0]["source"]["expression"]
        else:
            assert before == after


# --------------------------------------------------------------------- backup/restore
_TREE = st.dictionaries(
    keys=st.lists(st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=4), min_size=1, max_size=3)
        .map(lambda parts: "/".join(parts)),
    values=st.binary(max_size=40),
    min_size=1, max_size=6,
)


def _write_tree(root: Path, tree: dict[str, bytes]) -> None:
    for rel, data in tree.items():
        path = root / rel
        if path.exists() and path.is_dir():
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except (FileExistsError, NotADirectoryError):
            continue  # a generated path used as both a file and a folder


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


@PROPERTY
@given(_TREE, _TREE)
def test_restore_returns_the_project_to_the_backed_up_state(original, damage):
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "proj"
        project.mkdir()
        _write_tree(project, original)
        before = _snapshot(project)
        backup = BackupManager.create_backup(project)
        assert _snapshot(backup) == before

        for p in list(project.rglob("*")):  # damage: wipe some files, then write new ones
            if p.is_file() and ord(p.name[0]) % 2 == 0:
                p.unlink()
        _write_tree(project, damage)

        assert BackupManager.restore_backup(backup, project) is True
        assert _snapshot(project) == before
        assert BackupManager.verify_restoration(backup, project)
        assert [p.name for p in Path(tmp).iterdir() if p.name.startswith("proj.restore")] == []


@PROPERTY
@given(_TREE, _TREE)
def test_a_failed_restore_never_changes_the_project(original, changed):
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "proj"
        project.mkdir()
        _write_tree(project, original)
        backup = BackupManager.create_backup(project)
        _write_tree(project, changed)
        snapshot = _snapshot(project)

        real_rename = Path.rename

        def locked(self, target):
            if self == project:
                raise PermissionError("locked")
            return real_rename(self, target)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(Path, "rename", locked)
            with pytest.raises(PermissionError):
                BackupManager.restore_backup(backup, project)

        assert _snapshot(project) == snapshot
        assert [p.name for p in Path(tmp).iterdir() if p.name.startswith("proj.restore")] == []


@PROPERTY
@given(st.integers(2, 6))
def test_backups_never_overwrite_each_other(count):
    import datetime as real_dt
    from unittest import mock
    from pbiscan.remediation import backup as backup_module

    class Frozen(real_dt.datetime):
        @classmethod
        def utcnow(cls):
            return cls(2026, 1, 1, 0, 0, 0)

    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(backup_module, "datetime", Frozen):
        project = Path(tmp) / "proj"
        project.mkdir()
        made = []
        for i in range(count):
            (project / "a.txt").write_text(f"state {i}", encoding="utf-8")
            made.append(BackupManager.create_backup(project))
        assert len(set(made)) == count
        assert [(b / "a.txt").read_text(encoding="utf-8") for b in made] == [f"state {i}" for i in range(count)]


# ------------------------------------------------------------------------ DAX scanning
@st.composite
def calc_trees(draw, depth: int = 3):
    """('CALCULATE'|'SUM'|'FILTER', [children]) trees plus decoy leaves that mention CALCULATE( harmlessly."""
    leaf = st.sampled_from([
        ("leaf", "SUM(T[x])"),
        ("leaf", '"CALCULATE(1)"'),
        ("leaf", "T[CALCULATE(x)]"),
        ("leaf", "'CALCULATE(' [a (b)]"),
        ("leaf", "[Margin [%]]]"),
        ("leaf", "1 /* CALCULATE(2) */"),
        ("leaf", "2 -- CALCULATE(3)\n"),
    ])
    if depth == 0:
        return draw(leaf)
    kind = draw(st.sampled_from(["CALCULATE", "CALCULATE", "SUM", "FILTER", "leaf"]))
    if kind == "leaf":
        return draw(leaf)
    children = draw(st.lists(calc_trees(depth=depth - 1), min_size=0, max_size=3))
    return (kind, children)


def _render(tree) -> str:
    kind, payload = tree
    if kind == "leaf":
        return payload
    return f"{kind}(" + ", ".join(_render(c) for c in payload) + ")"


def _nested(tree, inside_calculate: bool = False) -> bool:
    kind, payload = tree
    if kind == "leaf":
        return False
    if kind == "CALCULATE" and inside_calculate:
        return True
    return any(_nested(c, inside_calculate or kind == "CALCULATE") for c in payload)


@PROPERTY
@given(calc_trees(), st.lists(calc_trees(), max_size=2))
def test_nested_calculate_matches_the_generated_tree(tree, siblings):
    roots = [tree, *siblings]
    expression = " + ".join(_render(r) for r in roots)
    assert has_nested_calculate(expression) == any(_nested(r) for r in roots)


_LITERAL = st.text(alphabet=string.ascii_letters + " /-*:.,()[]'", max_size=20)


@PROPERTY
@given(_LITERAL, _LITERAL)
def test_comment_stripping_never_alters_a_string_literal(inside, outside_comment):
    literal = '"' + inside.replace('"', '""') + '"'
    expression = f"{literal} & 1 // {outside_comment}\n"
    stripped = strip_dax_comments(expression)
    assert stripped.startswith(literal)
    assert "//" not in stripped.split(literal, 1)[1]


# Names built from DAX-meaningful tokens: single characters almost never put `]` right before
# a comment marker, which is exactly the case that matters.
_NAME_WITH_MARKERS = st.lists(
    st.sampled_from(["a", "B", " ", "]", "[", "--", "//", "/*", "*/", "'", '"', "(", ")"]), min_size=1, max_size=8
).map("".join)


@PROPERTY
@given(_NAME_WITH_MARKERS)
def test_comment_markers_inside_an_escaped_column_name_are_not_comments(name):
    expression = "T[" + name.replace("]", "]]") + "] + 1"
    assert strip_dax_comments(expression) == expression


@PROPERTY
@given(_NAME_WITH_MARKERS)
def test_a_calculate_after_an_escaped_column_name_is_still_seen(name):
    column = "T[" + name.replace("]", "]]") + "]"
    assert has_nested_calculate(f"CALCULATE({column} + CALCULATE(1))")
    assert not has_nested_calculate(f"CALCULATE({column}) + CALCULATE(1)")


@PROPERTY
@given(st.text(alphabet=string.ascii_letters + string.digits + " \n\"'[]/-*(),", max_size=60))
def test_comment_stripping_is_idempotent_and_never_adds_text(expression):
    once = strip_dax_comments(expression)
    assert strip_dax_comments(once) == once
    assert len(once) <= len(expression) + expression.count("/*") + expression.count("//") + expression.count("--")


# ---------------------------------------------------------------------------- date names
_WORDS = st.sampled_from(["Date", "Dates", "Calendar", "Time", "DimDate", "Dim_Date", "Fiscal Calendar", "date table"])
_NOISE = st.sampled_from(["Sales", "Updates", "Candidates", "Timesheet", "Datasets", "Orders", "Sometimes"])


@PROPERTY
@given(_NOISE, _WORDS, st.sampled_from([" ", "_", ""]))
def test_date_words_are_found_and_lookalikes_are_not(noise, word, sep):
    assert looks_like_date_table_name(f"{noise}{sep or ' '}{word}")
    assert not looks_like_date_table_name(noise)
