"""
Guards on the committed type-fidelity artifact.

Two things are policed here. First, staleness: the artifact is Phase 48's specification, so a
committed file that no longer matches what the generator produces is a wrong specification
shipping silently. Second, circularity: RESEARCH.md defence 3 says the result column must
never be sourced from Semolina's own type map, and two disjoint vocabularies make an
accidental crossover visible without anyone having to read the generator.

Record/replay contract: this module reads the committed file and calls the probe module, which
runs a **live** in-memory DuckDB. It records nothing and must never carry
``pytest.mark.adbc_cassette`` — see ``tests/unit/test_type_fidelity_duckdb.py`` for why.
"""

from __future__ import annotations

import pytest
from type_fidelity_probe import (
    ARTIFACT_PATH,
    FidelityRow,
    collect_duckdb_rows,
    main,
    render_artifact,
)

pytest.importorskip("adbc_driver_duckdb")

TABLE_HEADING = "## Field type comparison"

MAPPED_COLUMN = "Mapped annotation"
RESULT_COLUMN = "Result Arrow type"

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


def _parse_comparison_table(markdown: str) -> tuple[list[str], list[list[str]]]:
    """
    Split the artifact's comparison table into its header cells and data cells.

    Parses the table's structure rather than regexing the whole file, so the guards describe
    the table and not the prose around it. The section is bounded at the next ``##`` heading:
    later sections carry tables of their own, and swallowing their rows would feed
    differently-shaped rows into the column guards below.

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
    header = [cell.strip() for cell in pipe_lines[0].strip("|").split("|")]
    rows = [
        [cell.strip() for cell in line.strip("|").split("|")]
        for line in pipe_lines[2:]  # line 1 is the |---|---| separator
    ]
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


def test_artifact_has_no_value_column() -> None:
    """Neither the table nor the row model can carry warehouse row values (threat T-47-01)."""
    header, _rows = _parse_comparison_table(ARTIFACT_PATH.read_text(encoding="utf-8"))
    normalised = {cell.strip().lower().replace("_", " ") for cell in header}

    assert normalised.isdisjoint(FORBIDDEN_VALUE_HEADERS), (
        f"Artifact table carries a sample-value column: "
        f"{sorted(normalised & FORBIDDEN_VALUE_HEADERS)}"
    )

    # The generator has no path from row data to the file either: FidelityRow declares no
    # value-bearing field, so no future renderer change can start emitting one.
    row_fields = {name.lower().replace("_", " ") for name in FidelityRow.__dataclass_fields__}
    assert row_fields.isdisjoint(FORBIDDEN_VALUE_HEADERS)
