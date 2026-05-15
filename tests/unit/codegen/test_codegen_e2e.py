"""End-to-end codegen test against a file-backed DuckDB database."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from semolina.cli import app

if TYPE_CHECKING:
    from pathlib import Path

    from syrupy.assertion import SnapshotAssertion

runner = CliRunner()


def test_codegen_file_backed_duckdb(
    duckdb_file_backed_db: "Path",
    snapshot: "SnapshotAssertion",
) -> None:
    """
    Codegen against an on-disk DuckDB ``.db`` produces the expected model class.

    Drives the full CLI surface end-to-end (DKGEN-04 success criterion #1):
    ``_resolve_backend`` -> path normalization -> real ``DuckDBEngine`` ->
    real introspection of a generated semantic view -> renderer.
    """
    result = runner.invoke(
        app,
        [
            "codegen",
            "sales_view",
            "--backend",
            "duckdb",
            "--database",
            str(duckdb_file_backed_db),
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.output == snapshot
