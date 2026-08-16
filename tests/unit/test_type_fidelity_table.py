"""
Guards on the committed type-fidelity artifact.

Two things are policed here. First, staleness: the artifact is Phase 48's specification, so a
committed file that no longer matches what the generator produces is a wrong specification
shipping silently. Second, circularity: RESEARCH.md defence 3 says the result column must
never be sourced from Semolina's own type map, and two disjoint vocabularies make an
accidental crossover visible without anyone having to read the generator.

The circularity guard has two halves, because the contract it polices now spans two files.
:func:`test_result_and_mapped_vocabularies_are_disjoint` reads the committed artifact;
:func:`test_promoted_probe_does_not_import_the_type_map` reads the shipped probe module that
produces its result column.

Record/replay contract: this module reads the committed file and calls the probe module, which
runs a **live** in-memory DuckDB. It records nothing and must never carry
``pytest.mark.adbc_cassette`` — see ``tests/unit/test_type_fidelity_duckdb.py`` for why.
"""

from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path

import pytest
from type_fidelity_probe import (
    ARTIFACT_FILENAME,
    ARTIFACT_PATH,
    ARTIFACT_PHASE_DIR,
    FidelityRow,
    collect_duckdb_rows,
    main,
    render_artifact,
    resolve_artifact_path,
)

pytest.importorskip("adbc_driver_duckdb")

TABLE_HEADING = "## Field type comparison"

MAPPED_COLUMN = "Mapped annotation"
RESULT_COLUMN = "Result Arrow type"
RAW_COLUMN = "Warehouse type"

PATHOLOGICAL_TYPE = "UNION(a INTEGER | b VARCHAR)"
"""
A synthetic warehouse type carrying a literal ``|``.

Deliberately not a measured value — no field in the artifact has this type today. It stands
in for the shapes the metadata column already renders verbatim: a DuckDB composite type, or
the ``json.dumps`` descriptor the Snowflake and Databricks collectors emit, either of which
could carry a pipe the first time a field needs one.
"""

FORBIDDEN_VALUE_HEADERS = frozenset(
    {
        "value",
        "values",
        "sample",
        "sample value",
        "sample values",
        "example value",
        "example values",
        "row value",
        "row values",
        "sample row",
        "sample data",
    }
)
"""
Header texts that would make the artifact carry warehouse row data (threat T-47-01).

The artifact is committed and public; it records types only. ``Python value type`` names a
*type*, not a value, and is deliberately absent from this set.
"""


UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
"""
Matches a ``|`` that is not backslash-escaped — a real column boundary.

The mirror of ``type_fidelity_probe.escape_cell``. Splitting on every ``|`` instead would
undo the escaping the generator applies and re-open the column-shift this parser exists to be
immune to.
"""


def _split_row(line: str) -> list[str]:
    """
    Split one markdown table row into its cells, honouring the generator's escaping.

    Args:
        line: A table row, leading and trailing ``|`` included.

    Returns:
        The row's cells, stripped, with each backslash-escaped pipe restored to a literal
        ``|``.

    Raises:
        AssertionError: If the line is not delimited by a leading and trailing pipe.
    """
    body = line.strip()
    assert body.startswith("|") and body.endswith("|"), f"Not a table row: {line!r}"
    return [cell.strip().replace("\\|", "|") for cell in UNESCAPED_PIPE.split(body[1:-1])]


def _parse_comparison_table(markdown: str) -> tuple[list[str], list[list[str]]]:
    """
    Split the artifact's comparison table into its header cells and data cells.

    Parses the table's structure rather than regexing the whole file, so the guards describe
    the table and not the prose around it. The section is bounded at the next ``##`` heading:
    later sections carry tables of their own, and swallowing their rows would feed
    differently-shaped rows into the column guards below.

    Cells are split on unescaped pipes only, mirroring ``type_fidelity_probe.escape_cell``.
    Splitting on every ``|`` would let a pipe inside a measured type shift the row one column
    to the right, which would quietly misalign the positional column guards below rather than
    failing anywhere near the cause.

    The heading is matched as a whole *line*, not as a substring. Earlier sections cite
    ``## Field type comparison`` by name in their prose — the driver-capability section says
    in so many words which claims live in which table — and a substring match would open the
    section at that citation, then close it again at the real heading, leaving no rows.

    Args:
        markdown: The full artifact text.

    Returns:
        The header cells and one list of cells per data row.

    Raises:
        AssertionError: If the artifact carries no ``## Field type comparison`` heading line.
    """
    lines = markdown.splitlines()
    starts = [index for index, line in enumerate(lines) if line.strip() == TABLE_HEADING]
    assert starts, f"Artifact has no {TABLE_HEADING!r} heading line"

    section_lines: list[str] = []
    for line in lines[starts[0] + 1 :]:
        if line.startswith("## "):
            break
        section_lines.append(line)
    pipe_lines = [line.strip() for line in section_lines if line.strip().startswith("|")]
    header = _split_row(pipe_lines[0])
    rows = [_split_row(line) for line in pipe_lines[2:]]  # line 1 is the |---|---| separator
    return header, rows


def _column(header: list[str], rows: list[list[str]], name: str) -> list[str]:
    """
    Read one column out of the parsed table, by header name.

    Looked up by name rather than by a hard-coded index so a future column reorder cannot
    silently pass.

    Args:
        header: The table's header cells.
        rows: The table's data rows.
        name: The header text to select.

    Returns:
        That column's cell values, one per data row.
    """
    assert name in header, f"Artifact table has no {name!r} column; headers are {header}"
    index = header.index(name)
    return [row[index] for row in rows]


PROMOTED_PROBE_MODULE = "semolina.codegen.probe"
"""The shipped home of the probe's result half, after Phase 48 promoted it out of ``tests/``."""

FORBIDDEN_PROBE_IMPORT = "type_map"
"""
The substring that identifies Semolina's type map in any spelling of an import.

Matched as a substring rather than against the full dotted path so
``from semolina.codegen.type_map import x``, ``from semolina.codegen import type_map``,
``import semolina.codegen.type_map`` and a relative ``from .type_map import x`` are all
caught by one rule.
"""


def _promoted_probe_source() -> str:
    """
    Read the shipped probe module's source without importing it.

    Located through ``importlib.util.find_spec`` rather than by joining a hard-coded path, so
    the text inspected is the file the interpreter would actually import. ``find_spec``
    resolves the parent package only; the probe module's own top-level code never runs.

    Returns:
        The full source text of :data:`PROMOTED_PROBE_MODULE`.

    Raises:
        AssertionError: If the module is not importable, which means the probe is still
            living in the test tree where a shipped ``--check`` cannot reach it.
    """
    spec = importlib.util.find_spec(PROMOTED_PROBE_MODULE)
    assert spec is not None and spec.origin is not None, (
        f"{PROMOTED_PROBE_MODULE} is not importable. The probe's result half must ship from "
        "src/, because a `semolina codegen --check` cannot import from tests/."
    )
    return Path(spec.origin).read_text(encoding="utf-8")


def _imported_module_names(source: str) -> list[str]:
    """
    Collect every module name the source imports, by any import form.

    Both node kinds are walked. ``ast.ImportFrom`` also contributes its *alias* names, since
    ``from semolina.codegen import type_map`` records the offending name there and not in
    ``node.module``.

    Args:
        source: Python source text.

    Returns:
        Every module or imported-name string the source mentions in an import statement.
    """
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
            names.extend(alias.name for alias in node.names)
    return names


def test_promoted_probe_does_not_import_the_type_map() -> None:
    """The shipped probe never imports the type map (RESEARCH.md defence 3, new location)."""
    # Circularity guard, not an import-hygiene check. The probe is the artifact's *result*
    # half: its schema comes from the driver's own answer. If it ever reached for Semolina's
    # type map, the mapped column and the result column would share a source, and a
    # comparison that cannot produce a mismatch is not measuring anything.
    #
    # Read as text and parsed, rather than imported and inspected through `sys.modules`:
    # importing would execute the module's top-level code, and a *lazy* import inside a
    # function body would stay invisible to a `sys.modules` check while being perfectly
    # visible here.
    imported = _imported_module_names(_promoted_probe_source())
    offenders = sorted({name for name in imported if FORBIDDEN_PROBE_IMPORT in name})

    assert not offenders, (
        f"{PROMOTED_PROBE_MODULE} imports {offenders} — the probe's result half would then be "
        "sourced from the type map it exists to measure against, and the artifact would "
        "become a restatement of Semolina's own mapping."
    )


def test_artifact_path_follows_the_phase_directory_into_the_archive(tmp_path: Path) -> None:
    """`gsd-cleanup` archiving the phase directory does not lose the artifact."""
    archived = tmp_path / ".planning" / "milestones" / "v0.7-phases" / ARTIFACT_PHASE_DIR
    archived.mkdir(parents=True)
    expected = archived / ARTIFACT_FILENAME
    _ = expected.write_text("committed", encoding="utf-8")

    assert resolve_artifact_path(tmp_path) == expected


def test_artifact_path_prefers_the_live_phase_directory(tmp_path: Path) -> None:
    """While the phase is still live, an archived copy is never consulted."""
    live = tmp_path / ".planning" / "phases" / ARTIFACT_PHASE_DIR / ARTIFACT_FILENAME
    live.parent.mkdir(parents=True)
    _ = live.write_text("live", encoding="utf-8")
    archived = tmp_path / ".planning" / "milestones" / "v0.7-phases" / ARTIFACT_PHASE_DIR
    archived.mkdir(parents=True)
    _ = (archived / ARTIFACT_FILENAME).write_text("stale", encoding="utf-8")

    assert resolve_artifact_path(tmp_path) == live


def test_missing_artifact_fails_loudly_rather_than_comparing_against_nothing(
    tmp_path: Path,
) -> None:
    """
    An artifact in neither location raises, instead of degrading to an empty document.

    Reading "not found" as "nothing committed yet" would make `--check` report drift for a
    reason that has nothing to do with the generator, which is how a staleness guard stops
    being believed.
    """
    with pytest.raises(FileNotFoundError, match=ARTIFACT_FILENAME):
        _ = resolve_artifact_path(tmp_path)


def test_committed_table_is_not_stale() -> None:
    """Regenerating the artifact reproduces the committed bytes exactly."""
    assert main(["--check"]) == 0, (
        f"{ARTIFACT_PATH} is stale. Run `just type-fidelity` and commit the result — "
        "a stale artifact ships as Phase 48's specification."
    )


def test_regeneration_is_deterministic() -> None:
    """Rendering twice in one process gives identical bytes, so row order cannot drift."""
    first = render_artifact(collect_duckdb_rows())
    second = render_artifact(collect_duckdb_rows())

    assert first == second


def test_result_and_mapped_vocabularies_are_disjoint() -> None:
    """The result column and the mapped column never share a value (RESEARCH.md defence 3)."""
    # Circularity guard, not a formatting check. Arrow type names (`decimal128(38, 2)`,
    # `int64`, `double`) and Python annotation strings (`int`, `float`, `datetime.date`) are
    # two vocabularies. An overlap means one column is being sourced from the other, which
    # would make the whole artifact a restatement of Semolina's own type map.
    header, rows = _parse_comparison_table(ARTIFACT_PATH.read_text(encoding="utf-8"))
    mapped = set(_column(header, rows, MAPPED_COLUMN))
    result = set(_column(header, rows, RESULT_COLUMN))

    assert mapped.isdisjoint(result), (
        f"Result and mapped vocabularies overlap on {sorted(mapped & result)} — "
        "one column is being sourced from the other."
    )


def test_a_pipe_in_a_cell_cannot_shift_the_table_columns() -> None:
    """
    A cell holding a literal ``|`` stays one cell, so the circularity guard stays aligned.

    :func:`_column` reads the mapped and result columns by position. An unescaped pipe would
    push every later cell of that row along by one, and
    :func:`test_result_and_mapped_vocabularies_are_disjoint` would then compare two columns it
    was never meant to compare — masking a real overlap, or inventing one that is not there.
    Round-tripping the value proves the escape is reversible rather than lossy.
    """
    row = FidelityRow(
        backend="duckdb",
        field_name="pathological",
        role="metric",
        metadata_raw_type=PATHOLOGICAL_TYPE,
        metadata_provenance="live",
        mapped_annotation="str",
        result_arrow_type="string",
        result_provenance="live (execute-schema)",
        python_value_type="str",
        verdict="match",
    )

    header, rows = _parse_comparison_table(render_artifact([row]))

    assert len(rows) == 1
    assert len(rows[0]) == len(header), (
        f"A `|` in a cell shifted the row: {len(rows[0])} cells against {len(header)} columns"
    )
    assert _column(header, rows, RAW_COLUMN) == [PATHOLOGICAL_TYPE]
    assert _column(header, rows, MAPPED_COLUMN) == ["str"]
    assert _column(header, rows, RESULT_COLUMN) == ["string"]


def test_artifact_has_no_value_column() -> None:
    """Neither the table nor the row model can carry warehouse row values (threat T-47-01)."""
    header, _rows = _parse_comparison_table(ARTIFACT_PATH.read_text(encoding="utf-8"))
    normalized = {cell.strip().lower().replace("_", " ") for cell in header}

    assert normalized.isdisjoint(FORBIDDEN_VALUE_HEADERS), (
        f"Artifact table carries a sample-value column: "
        f"{sorted(normalized & FORBIDDEN_VALUE_HEADERS)}"
    )

    # The generator has no path from row data to the file either: FidelityRow declares no
    # value-bearing field, so no future renderer change can start emitting one.
    row_fields = {name.lower().replace("_", " ") for name in FidelityRow.__dataclass_fields__}
    assert row_fields.isdisjoint(FORBIDDEN_VALUE_HEADERS)
