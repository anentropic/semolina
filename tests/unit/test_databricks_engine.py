"""
Unit tests for DatabricksEngine on the Phase 44 Engine API.

Phase 44 moves every backend onto the ``create_engine`` / ADBC-pool contract:
the engine is built with ``create_engine(DatabricksConfig(...))`` (D1), owns one
ADBC pool plus the Databricks dialect, and executes queries through the
inherited :meth:`~semolina.engines.base.Engine.execute` pool path.

Databricks *introspection* over ADBC is UNVALIDATED and ships as a marked
``NotImplementedError`` fallback (44-04): the Foundry-distributed Databricks
ADBC driver is not installed and the recording hangs on warehouse cold-start.
These tests therefore assert the new-API construction, the dialect selection,
SQL generation, and that ``introspect()`` raises ``NotImplementedError`` with a
spike-pointer message -- rather than driving a (non-existent) ADBC introspection
path. The native-driver ``sys.modules`` mocks the pre-Phase-44 suite used are
removed; run ``scripts/spike_databricks_adbc_introspect.py`` to validate the
real ADBC path before replacing the fallback.

The mocks are deliberately untyped (``MagicMock`` pool / cursor and a patched
``connect()``), so the per-rule scope-disable below keeps basedpyright strict
quiet on the mock seam without a ``# type: ignore``.
"""
# Test-only mock seam: MagicMock pool/cursor and patch.object(engine, "connect")
# are untyped by construction. Scope-disable the rules the mock seam triggers
# under basedpyright strict (intentionally not a `# type: ignore`).
# pyright: reportUnknownMemberType=false

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from models import Sales

from semolina.query import _Query


def _make_databricks_engine(**overrides: Any) -> Any:
    """
    Build a DatabricksEngine via the Phase 44 ``create_engine`` factory.

    The engine owns an ADBC pool (mocked at ``create_pool`` below) plus the
    Databricks dialect derived from the config type. Tests then patch
    ``engine.connect`` to drive execution through a mocked ADBC cursor.
    """
    from adbc_poolhouse import DatabricksConfig
    from pydantic import SecretStr

    from semolina.config import create_engine

    params: dict[str, Any] = {
        "host": "workspace.cloud.databricks.com",
        "http_path": "/sql/1.0/warehouses/abc123",
        "token": SecretStr("dapi-test-token"),
    }
    params.update(overrides)
    # Avoid a live ADBC connect: create_pool returns a mock pool. The Engine
    # still owns it; execution is driven through engine.connect() below.
    with patch("semolina.config.create_pool", return_value=MagicMock(name="pool")):
        return create_engine(DatabricksConfig(**params))


def _patch_connect(engine: Any, cursor: Any) -> Any:
    """
    Patch ``engine.connect()`` to return a connection whose cursor is ``cursor``.

    Mirrors the real ADBC checkout seam used by
    :meth:`~semolina.engines.base.Engine.execute`: ``conn = self.connect()``
    then ``conn.cursor()`` (``connect()`` returns the pooled connection
    directly, not a context manager).
    """
    conn = MagicMock(name="conn")
    conn.cursor.return_value = cursor
    return patch.object(engine, "connect", return_value=conn)


class TestDatabricksEngineConstruction:
    """
    DatabricksEngine is built via create_engine and owns pool + dialect.

    Verifies the Phase 44 construction contract: create_engine selects the
    DatabricksEngine subclass, supplies the ADBC pool and the DatabricksDialect,
    and never connects at construction time.
    """

    def test_create_engine_returns_databricks_engine(self) -> None:
        """Should build a DatabricksEngine from a DatabricksConfig."""
        from semolina.engines.databricks import DatabricksEngine

        engine = _make_databricks_engine()
        assert isinstance(engine, DatabricksEngine)

    def test_engine_uses_databricks_dialect(self) -> None:
        """Should attach a DatabricksDialect derived from the config type."""
        from semolina.engines.sql import DatabricksDialect

        engine = _make_databricks_engine()
        assert isinstance(engine.dialect, DatabricksDialect)

    def test_engine_owns_pool_without_connecting(self) -> None:
        """Should hold the pool without checking out a connection at build time."""
        engine = _make_databricks_engine()
        # The mock pool is owned but connect() is not called during construction.
        engine._pool.connect.assert_not_called()  # noqa: SLF001  (test inspects owned pool)


class TestDatabricksEngineSQLGeneration:
    """
    DatabricksEngine generates SQL via its Databricks dialect builder.

    Phase 44 removed the per-engine ``to_sql`` shim; SQL is built through
    ``engine.dialect.create_builder().build_select_with_params``. Verifies
    MEASURE() wrapping for metrics and backtick identifier quoting.
    """

    def _build_sql(self, engine: Any, query: _Query) -> str:
        """Build the SELECT SQL the engine would execute for ``query``."""
        sql, _params = engine.dialect.create_builder().build_select_with_params(query)
        return sql

    def test_generates_measure_syntax(self) -> None:
        """Should wrap metrics in MEASURE()."""
        engine = _make_databricks_engine()
        query = _Query().metrics(Sales.revenue, Sales.cost)
        sql = self._build_sql(engine, query)

        assert "MEASURE(`revenue`)" in sql
        assert "MEASURE(`cost`)" in sql

    def test_quotes_identifiers_with_backticks(self) -> None:
        """Should use backticks for identifier quoting."""
        engine = _make_databricks_engine()
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        sql = self._build_sql(engine, query)

        assert "`revenue`" in sql
        assert "`country`" in sql
        assert "`sales_view`" in sql

    def test_dialect_escapes_backticks(self) -> None:
        """Should escape backticks in field names."""
        from semolina.engines.sql import DatabricksDialect

        dialect = DatabricksDialect()
        assert dialect.quote_identifier("my`field") == "`my``field`"


class TestDatabricksEngineExecute:
    """
    DatabricksEngine.execute runs through the inherited ADBC pool path.

    Verifies that execution checks a connection out of the owned pool, runs the
    generated SQL through the ADBC cursor, and maps result rows -- using the
    base Engine.execute path (no native databricks.sql connector).
    """

    def test_execute_runs_sql_over_pooled_cursor(self) -> None:
        """Should execute generated SQL through the ADBC cursor from connect()."""
        engine = _make_databricks_engine()

        cursor = MagicMock(name="cursor")
        with _patch_connect(engine, cursor):
            query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
            expected_sql, expected_params = (
                engine.dialect.create_builder().build_select_with_params(query)
            )
            engine.execute(query)

        cursor.execute.assert_called_once_with(expected_sql, expected_params)

    def test_execute_returns_semolina_cursor(self) -> None:
        """Should wrap the post-execute ADBC cursor in a SemolinaCursor."""
        from semolina.cursor import SemolinaCursor

        engine = _make_databricks_engine()

        cursor = MagicMock(name="cursor")
        with _patch_connect(engine, cursor):
            query = _Query().metrics(Sales.revenue)
            result = engine.execute(query)

        assert isinstance(result, SemolinaCursor)


class TestDatabricksEngineIntrospectFallback:
    """
    DatabricksEngine.introspect is a marked NotImplementedError fallback (44-04).

    Databricks ADBC introspection is unvalidated (Foundry driver absent, the
    recording hangs), so introspect() raises NotImplementedError pointing at the
    standalone validation spike rather than running an unvalidated ADBC path.
    """

    def test_introspect_raises_not_implemented(self) -> None:
        """Should raise NotImplementedError for any view name."""
        engine = _make_databricks_engine()
        with pytest.raises(NotImplementedError):
            engine.introspect("main.analytics.sales_view")

    def test_introspect_message_points_at_spike(self) -> None:
        """Should explain the Foundry-driver gap and name the spike script."""
        engine = _make_databricks_engine()
        with pytest.raises(NotImplementedError) as exc_info:
            engine.introspect("sales_view")

        message = str(exc_info.value)
        assert "scripts/spike_databricks_adbc_introspect.py" in message
        assert "Foundry" in message
        # The offending view name is echoed so the operator knows what to spike.
        assert "sales_view" in message

    def test_introspect_does_not_connect(self) -> None:
        """Should fail fast without checking a connection out of the pool."""
        engine = _make_databricks_engine()
        with pytest.raises(NotImplementedError):
            engine.introspect("sales_view")
        engine._pool.connect.assert_not_called()  # noqa: SLF001  (test inspects owned pool)
