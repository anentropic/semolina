"""
End-to-end codegen tests against DuckDB, Snowflake, and Databricks backends.

The DuckDB case drives the full CLI (it takes ``--database`` and needs no
credentials). The Snowflake case drives ``engine.introspect()`` over a mocked
ADBC-cursor seam (built via ``create_engine(SnowflakeConfig(...))`` with a mocked
``create_pool``), so it runs fully offline. The Databricks case still drives the
pre-Phase-44 native ``DatabricksEngine`` constructor and is migrated alongside
the Databricks ADBC introspect path in Plan 04.
"""
# The Databricks case below still references the pre-Phase-44 native
# ``DatabricksEngine(server_hostname=...)`` constructor (Databricks ADBC
# introspection is Plan 04). Scope-disable the rule that call triggers under
# basedpyright strict (intentionally not a `# type: ignore`). Plan 04 REMOVES
# this pragma when the Databricks case is migrated.
# pyright: reportCallIssue=false

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from semolina.cli import app

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from syrupy.assertion import SnapshotAssertion

runner = CliRunner()


def _create_mock_databricks() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Create a properly structured mock for the databricks.sql module."""
    mock_exc = MagicMock()
    mock_exc.DatabaseError = type("DatabaseError", (Exception,), {})
    mock_exc.OperationalError = type("OperationalError", (Exception,), {})
    mock_exc.Error = type("Error", (Exception,), {})

    mock_sql = MagicMock()
    mock_sql.exc = mock_exc

    mock_databricks = MagicMock()
    mock_databricks.sql = mock_sql

    return mock_databricks, mock_sql, mock_exc


def test_codegen_file_backed_duckdb(
    duckdb_file_backed_db: Path,
    snapshot: SnapshotAssertion,
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


def test_codegen_snowflake_field_types(snapshot: SnapshotAssertion) -> None:
    """
    Offline Snowflake introspect -> render emits Metric, Dimension, and Fact.

    Drives ``SnowflakeEngine.introspect`` over a mocked ADBC-cursor seam (the
    engine is built via ``create_engine(SnowflakeConfig(...))`` with a mocked
    ``create_pool``, then ``connect()`` is patched to yield the cursor), so the
    test runs fully offline. The synthetic ``SHOW COLUMNS`` rows exercise all
    three Snowflake roles: METRIC -> Metric[int], DIMENSION -> Dimension[str],
    FACT -> Fact[datetime.date].

    The column names are UPPERCASE (``REVENUE``, ``COUNTRY``, ``DATE_KEY``) —
    the default Snowflake casing that round-trips through ``name.lower().upper()``
    back to the original, so no ``source=`` kwarg is emitted. This is the common
    path; the quoted-lowercase path that *does* set ``source=`` is covered by
    ``test_source_name_set_emits_source_kwarg`` in ``test_python_renderer.py``.
    """
    from adbc_poolhouse import SnowflakeConfig

    from semolina.codegen.python_renderer import render_and_format
    from semolina.config import create_engine

    mock_cursor = MagicMock()
    mock_cursor.description = [
        ("column_name",),
        ("kind",),
        ("data_type",),
        ("comment",),
    ]
    mock_cursor.fetchall.return_value = [
        ("REVENUE", "METRIC", json.dumps({"type": "FIXED", "scale": 0}), ""),
        ("COUNTRY", "DIMENSION", json.dumps({"type": "TEXT"}), ""),
        ("DATE_KEY", "FACT", json.dumps({"type": "DATE"}), ""),
    ]
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)

    @contextmanager
    def _connect() -> Generator[Any]:
        conn = MagicMock(name="conn")
        conn.cursor.return_value = mock_cursor
        yield conn

    with patch("semolina.config.create_pool", return_value=MagicMock(name="pool")):
        engine = create_engine(SnowflakeConfig(account="test", user="user"))
    with patch.object(engine, "connect", side_effect=_connect):
        view = engine.introspect("sales_view")

    assert render_and_format([view]) == snapshot


def test_codegen_databricks_field_types(snapshot: SnapshotAssertion) -> None:
    """
    Offline Databricks introspect -> render emits Metric and Dimension only.

    The absence of a Fact field is intentional: Databricks metric views have no
    native Fact concept, so non-measure columns map to Dimension. This is not a
    coverage gap. The synthetic schema exercises both roles: is_measure True ->
    Metric[float], is_measure False -> Dimension[str].
    """
    mock_databricks, mock_sql, mock_exc = _create_mock_databricks()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    schema_json = json.dumps(
        {
            "columns": [
                {"name": "revenue", "is_measure": True, "type": {"name": "double"}, "comment": ""},
                {
                    "name": "country",
                    "is_measure": False,
                    "type": {"name": "string"},
                    "comment": "",
                },
            ]
        }
    )
    mock_cursor.fetchone.return_value = (schema_json,)

    with patch.dict(
        sys.modules,
        {
            "databricks": mock_databricks,
            "databricks.sql": mock_sql,
            "databricks.sql.exc": mock_exc,
        },
    ):
        from semolina.codegen.python_renderer import render_and_format
        from semolina.engines.databricks import DatabricksEngine

        mock_sql.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        engine = DatabricksEngine(
            server_hostname="test",
            http_path="/sql/1.0/warehouses/abc",
            access_token="token",
        )
        view = engine.introspect("sales_view")

    assert render_and_format([view]) == snapshot
