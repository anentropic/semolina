"""
End-to-end codegen tests against DuckDB, Snowflake, and Databricks backends.

The DuckDB case drives the full CLI (it takes ``--database`` and needs no
credentials). The Snowflake case drives ``engine.introspect()`` over a mocked
ADBC-cursor seam (built via ``create_engine(SnowflakeConfig(...))`` with a mocked
``create_pool``), so it runs fully offline. The Databricks case asserts the
Phase 44 / 44-04 introspection fallback: Databricks ADBC introspection is
unvalidated (the Foundry ADBC driver is not installed and the recording hangs),
so ``DatabricksEngine.introspect()`` raises ``NotImplementedError`` and there is
no rendered Databricks model to snapshot until the spike validates the real path.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from semolina.cli import app

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from syrupy.assertion import SnapshotAssertion

runner = CliRunner()


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


def test_codegen_databricks_introspect_not_implemented() -> None:
    """
    Databricks codegen raises NotImplementedError pending the Foundry ADBC path.

    Phase 44 / 44-04 ships Databricks ADBC introspection as a marked
    ``NotImplementedError`` fallback: the Foundry-distributed Databricks ADBC
    driver is not installed and the recording hangs on warehouse cold-start, so
    ``DESCRIBE TABLE EXTENDED ... AS JSON`` has never been run over ADBC. The
    engine is built via the Phase 44 ``create_engine(DatabricksConfig(...))``
    factory (mocked ``create_pool``); ``introspect()`` raises before any render,
    pointing the operator at the validation spike.
    """
    from adbc_poolhouse import DatabricksConfig
    from pydantic import SecretStr

    from semolina.config import create_engine

    with patch("semolina.config.create_pool", return_value=MagicMock(name="pool")):
        engine = create_engine(
            DatabricksConfig(
                host="workspace.cloud.databricks.com",
                http_path="/sql/1.0/warehouses/abc",
                token=SecretStr("dapi-test-token"),
            )
        )

    with pytest.raises(NotImplementedError) as exc_info:
        engine.introspect("sales_view")

    assert "scripts/spike_databricks_adbc_introspect.py" in str(exc_info.value)
