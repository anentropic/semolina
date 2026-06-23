"""
End-to-end codegen tests against DuckDB, Snowflake, and Databricks backends.

The DuckDB case drives the full CLI (it takes ``--database`` and needs no
credentials). The Snowflake and Databricks cases drive ``engine.introspect()``
directly with offline ``sys.modules`` connector mocks — routing them through the
CLI / ``_resolve_backend`` would trip the credentials loader.
"""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from semolina.cli import app

if TYPE_CHECKING:
    from pathlib import Path

    from syrupy.assertion import SnapshotAssertion

runner = CliRunner()


class _SnowflakeProgrammingError(Exception):
    """Minimal stub for snowflake.connector.errors.ProgrammingError."""


class _SnowflakeDatabaseError(Exception):
    """Minimal stub for snowflake.connector.errors.DatabaseError."""


@pytest.fixture
def _mock_snowflake_in_sys_modules():  # pyright: ignore[reportUnusedFunction]
    """Pre-populate sys.modules with snowflake mocks for offline introspection."""
    mock_sf = MagicMock(name="snowflake")
    mock_connector = MagicMock(name="snowflake.connector")
    mock_errors = MagicMock(name="snowflake.connector.errors")
    mock_errors.ProgrammingError = _SnowflakeProgrammingError
    mock_errors.DatabaseError = _SnowflakeDatabaseError
    mock_sf.connector = mock_connector
    mock_connector.errors = mock_errors
    with patch.dict(
        sys.modules,
        {
            "snowflake": mock_sf,
            "snowflake.connector": mock_connector,
            "snowflake.connector.errors": mock_errors,
        },
    ):
        yield


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


@pytest.mark.usefixtures("_mock_snowflake_in_sys_modules")
def test_codegen_snowflake_field_types(snapshot: SnapshotAssertion) -> None:
    """
    Offline Snowflake introspect -> render emits Metric, Dimension, and Fact.

    Drives ``SnowflakeEngine.introspect`` directly against a mocked connector
    (no CLI, no ``_resolve_backend``, no live credential loading) so the
    test runs fully offline. The synthetic ``SHOW COLUMNS`` rows exercise all
    three Snowflake roles: METRIC -> Metric[int], DIMENSION -> Dimension[str],
    FACT -> Fact[datetime.date].

    The column names are UPPERCASE (``REVENUE``, ``COUNTRY``, ``DATE_KEY``) —
    the default Snowflake casing that round-trips through ``name.lower().upper()``
    back to the original, so no ``source=`` kwarg is emitted. This is the common
    path; the quoted-lowercase path that *does* set ``source=`` is covered by
    ``test_source_name_set_emits_source_kwarg`` in ``test_python_renderer.py``.
    """
    mock_conn = MagicMock()
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

    with patch("snowflake.connector.connect") as mock_connect:
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        from semolina.codegen.python_renderer import render_and_format
        from semolina.engines.snowflake import SnowflakeEngine

        engine = SnowflakeEngine(account="test", user="user", password="pass")
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
