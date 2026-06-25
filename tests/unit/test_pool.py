"""
Tests for DuckDB pool lifecycle and extension loading.

Tests cover:
- DUCK-06: DuckDB pool auto-loads semantic_views extension
- TEST-02: DuckDB pool drives pool lifecycle tests

Test classes:
- TestDuckDBPoolLifecycle: pool creation, connect, cursor, close
- TestExtensionLoading: INSTALL + LOAD via connect event
- TestDuckDBPoolIntegration: full query execution flow with Sales model
- TestExecuteWithPool: end-to-end execute() via pool registry
"""
# RED-first (Phase 44 Wave 0): create_engine() and the 2-arg register() land in
# Plan 02. Until then basedpyright strict cannot see them, so scope-disable the
# two rules the not-yet-built API triggers. Plan 02 REMOVES this pragma when the
# tests go GREEN (it is intentionally not a `# type: ignore`).
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false

from __future__ import annotations

from typing import Any

import pytest
from models import Sales

pytest.importorskip("adbc_driver_duckdb")


# ---------------------------------------------------------------------------
# TestDuckDBPoolLifecycle: pool creation, connect, cursor, close
# ---------------------------------------------------------------------------


class TestDuckDBPoolLifecycle:
    """Test DuckDB pool creation, connection, cursor, and close."""

    def test_pool_connect_returns_connection(self, duckdb_pool: Any):
        """pool.connect() returns a context-manager connection."""
        conn = duckdb_pool.connect()
        assert conn is not None
        assert hasattr(conn, "cursor")
        assert hasattr(conn, "close")
        conn.close()

    def test_connection_cursor_returns_dbapi_cursor(self, duckdb_pool: Any):
        """conn.cursor() returns a cursor with execute() method."""
        with duckdb_pool.connect() as conn:
            cur = conn.cursor()
            assert cur is not None
            assert hasattr(cur, "execute")
            assert hasattr(cur, "fetchall")
            cur.close()

    def test_cursor_execute_returns_results(self, duckdb_pool: Any):
        """cursor.execute('SELECT 1 AS val') returns results via fetchall()."""
        with duckdb_pool.connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 AS val")
            rows = cur.fetchall()
            assert len(rows) == 1
            assert rows[0][0] == 1
            cur.close()

    def test_connection_context_manager(self, duckdb_pool: Any):
        """'with pool.connect() as conn:' works as context manager."""
        with duckdb_pool.connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 42 AS answer")
            rows = cur.fetchall()
            assert rows[0][0] == 42
            cur.close()


# ---------------------------------------------------------------------------
# TestExtensionLoading: INSTALL + LOAD via connect event
# ---------------------------------------------------------------------------


class TestExtensionLoading:
    """Test DuckDB semantic_views extension auto-loading (DUCK-06)."""

    def test_extension_installed_and_loaded(self, duckdb_pool: Any):
        """semantic_views extension is installed and loaded after pool connect."""
        with duckdb_pool.connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT installed, loaded FROM duckdb_extensions()"
                " WHERE extension_name = 'semantic_views'"
            )
            row = cur.fetchone()
            assert row is not None, "semantic_views extension not found"
            installed, loaded = row
            assert installed, "semantic_views extension not installed"
            assert loaded, "semantic_views extension not loaded"
            cur.close()

    def test_extension_auto_loads_on_new_connection(self):
        """Fresh DuckDB pool with event listener loads extension automatically."""
        from adbc_poolhouse import DuckDBConfig, close_pool, create_pool
        from sqlalchemy import event

        from semolina.config import _load_semantic_views

        config = DuckDBConfig(database=":memory:", pool_size=1)
        pool = create_pool(config)
        event.listen(pool, "connect", _load_semantic_views)

        try:
            with pool.connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT installed, loaded FROM duckdb_extensions()"
                    " WHERE extension_name = 'semantic_views'"
                )
                row = cur.fetchone()
                assert row is not None, "semantic_views extension not found"
                installed, loaded = row
                assert installed
                assert loaded
                cur.close()
        finally:
            close_pool(pool)

    def test_semantic_view_ddl_works(self, duckdb_pool: Any):
        """CREATE SEMANTIC VIEW DDL succeeds (extension is loaded)."""
        with duckdb_pool.connect() as conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE sv_ddl_test (id INTEGER, val INTEGER)")
            cur.execute("INSERT INTO sv_ddl_test VALUES (1, 100)")
            cur.execute("""
                CREATE OR REPLACE SEMANTIC VIEW sv_ddl_test_view AS
                TABLES (t AS sv_ddl_test PRIMARY KEY (id))
                DIMENSIONS (t.val AS t.val)
                METRICS (t.val AS SUM(t.val))
            """)
            # DDL succeeds -- extension is loaded and functional
            cur.close()


# ---------------------------------------------------------------------------
# TestDuckDBPoolIntegration: query execution with raw SQL on pool
# ---------------------------------------------------------------------------


class TestDuckDBPoolIntegration:
    """Test DuckDB pool with SQL execution, verifying real data aggregation."""

    def test_raw_sql_aggregation(self, duckdb_pool: Any):
        """Execute raw aggregation SQL on pool, verify SUM grouping works."""
        with duckdb_pool.connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT country, SUM(revenue) AS revenue"
                " FROM sales_data GROUP BY country ORDER BY country"
            )
            rows = cur.fetchall()
            # DuckDB aggregates: CA (2000), US (1000+500=1500)
            assert len(rows) == 2

            desc = cur.description
            assert desc is not None
            col_names = [d[0] for d in desc]
            row_dicts = [dict(zip(col_names, row, strict=True)) for row in rows]

            revenues_by_country = {r["country"]: int(r["revenue"]) for r in row_dicts}
            assert revenues_by_country["US"] == 1500
            assert revenues_by_country["CA"] == 2000
            cur.close()

    def test_where_filter_reduces_results(self, duckdb_pool: Any):
        """Execute query with WHERE country = 'US', verify only US results."""
        with duckdb_pool.connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT country, SUM(revenue) AS revenue"
                " FROM sales_data WHERE country = 'US' GROUP BY country"
            )
            rows = cur.fetchall()
            assert len(rows) == 1

            desc = cur.description
            assert desc is not None
            col_names = [d[0] for d in desc]
            row_dict = dict(zip(col_names, rows[0], strict=True))
            assert row_dict["country"] == "US"
            assert int(row_dict["revenue"]) == 1500
            cur.close()

    def test_cursor_description_matches_columns(self, duckdb_pool: Any):
        """cursor.description contains correct column metadata."""
        with duckdb_pool.connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT country, revenue, cost FROM sales_data LIMIT 1")
            desc = cur.description
            assert desc is not None
            col_names = [d[0] for d in desc]
            assert "country" in col_names
            assert "revenue" in col_names
            assert "cost" in col_names
            # DBAPI 2.0: each description entry has 7 elements
            for item in desc:
                assert len(item) == 7
            cur.close()


# ---------------------------------------------------------------------------
# TestExecuteWithPool: end-to-end execute() via pool registry
# ---------------------------------------------------------------------------


class TestExecuteWithPool:
    """Test _Query.execute() wired through the pool registry path."""

    def test_execute_with_duckdb_pool_returns_cursor(self, duckdb_pool: Any):
        """Register DuckDB pool, execute query, get SemolinaCursor with Rows."""
        from semolina.cursor import SemolinaCursor

        cursor = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).execute()
        assert isinstance(cursor, SemolinaCursor)
        rows = cursor.fetchall_rows()
        # DuckDB aggregates: 2 rows (US, CA)
        assert len(rows) == 2
        cursor.close()

    def test_execute_with_named_pool_using(self):
        """Build a DuckDB Engine, register it by name, .using('test') resolves it."""
        from adbc_poolhouse import DuckDBConfig, close_pool

        import semolina
        from semolina.config import create_engine
        from semolina.cursor import SemolinaCursor

        engine = create_engine(DuckDBConfig(database=":memory:", pool_size=1))

        with engine.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE sales_data (
                    id INTEGER, revenue INTEGER, cost INTEGER,
                    country VARCHAR, region VARCHAR, unit_price INTEGER
                )
            """)
            cur.execute("""
                INSERT INTO sales_data VALUES
                (1, 42, 10, 'CA', 'West', 5)
            """)
            cur.execute("""
                CREATE OR REPLACE SEMANTIC VIEW sales_view AS
                TABLES (s AS sales_data PRIMARY KEY (id))
                DIMENSIONS (s.country AS country, s.region AS region)
                METRICS (s.revenue AS SUM(s.revenue), s.cost AS SUM(s.cost))
            """)
            cur.close()
            conn.commit()

        semolina.register("test", engine)
        try:
            cursor = (
                Sales.query()
                .metrics(Sales.revenue)
                .dimensions(Sales.country)
                .using("test")
                .execute()
            )
            assert isinstance(cursor, SemolinaCursor)
            rows = cursor.fetchall_rows()
            assert len(rows) == 1
            assert int(rows[0].revenue) == 42
            cursor.close()
        finally:
            semolina.unregister("test")
            close_pool(engine._pool)

    def test_execute_returns_aggregated_data(self, duckdb_pool: Any):
        """DuckDB actually aggregates metrics (SUM) and groups by dimensions."""
        cursor = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).execute()
        rows = cursor.fetchall_rows()

        # DuckDB aggregates: US (1000+500=1500), CA (2000)
        assert len(rows) == 2
        revenues = {r.country: int(r.revenue) for r in rows}
        assert revenues["US"] == 1500
        assert revenues["CA"] == 2000
        cursor.close()

    def test_execute_with_no_engine_registered_raises(self):
        """execute() raises ValueError when no engine is registered."""
        query = Sales.query().metrics(Sales.revenue).dimensions(Sales.country)
        with pytest.raises(ValueError, match="No engine registered"):
            query.execute()

    def test_execute_cursor_lifecycle(self, duckdb_pool: Any):
        """execute() returns cursor; close() releases connection."""
        cursor = Sales.query().metrics(Sales.revenue).execute()
        rows = cursor.fetchall_rows()
        assert len(rows) >= 1
        cursor.close()

    def test_pool_wiring_generates_correct_sql(self, duckdb_pool: Any):
        """Verify execute() path generates correct DuckDB semantic_view() SQL."""
        from semolina.engines.sql import DuckDBDialect

        query = Sales.query().metrics(Sales.revenue).dimensions(Sales.country)
        dialect = DuckDBDialect()
        builder = dialect.create_builder()
        sql, params = builder.build_select_with_params(query)

        assert "semantic_view(" in sql
        assert "'sales_view'" in sql
        assert "dimensions" in sql
        assert "metrics" in sql
        assert params == []


# ---------------------------------------------------------------------------
# TestExecuteErrorPathReleasesConnection: CR-01 connection-leak regression
# ---------------------------------------------------------------------------


class _RaisingCursor:
    """DBAPI-shaped cursor whose execute() always raises (simulates a SQL error)."""

    def execute(self, sql: Any, params: Any = None) -> None:
        """Raise to simulate a backend execution failure (bad SQL, expired session)."""
        raise RuntimeError("boom from cursor.execute")


class _CursorRaisingConn:
    """Connection whose cursor() raises (simulates failure before execute())."""

    def __init__(self) -> None:
        """Track whether close() (pool checkin) was called."""
        self.closed = False

    def cursor(self) -> Any:
        """Raise to simulate failure at the conn.cursor() step."""
        raise RuntimeError("boom from conn.cursor")

    def close(self) -> None:
        """Mark the connection as returned to the pool (mirrors SemolinaCursor.close)."""
        self.closed = True


class _ExecuteRaisingConn:
    """Connection that hands out a cursor whose execute() raises."""

    def __init__(self) -> None:
        """Track whether close() (pool checkin) was called."""
        self.closed = False

    def cursor(self) -> _RaisingCursor:
        """Return a cursor that raises on execute()."""
        return _RaisingCursor()

    def close(self) -> None:
        """Mark the connection as returned to the pool (mirrors SemolinaCursor.close)."""
        self.closed = True


class TestExecuteErrorPathReleasesConnection:
    """
    CR-01: Engine.execute() must return the pooled connection on the error path.

    The connection checked out by ``Engine.connect()`` is otherwise only returned
    via ``SemolinaCursor.close()`` -> ``self._conn.close()``, which is unreachable
    when ``conn.cursor()`` or ``cur.execute()`` raises. With ``pool_size=1`` a
    single failed query would permanently consume the only slot. These tests patch
    ``connect()`` to yield a tracking connection and assert ``close()`` is called.
    """

    def _engine(self, monkeypatch: pytest.MonkeyPatch, conn: Any) -> Any:
        """Build a real DuckDB Engine but patch connect() to yield the given conn."""
        from adbc_poolhouse import DuckDBConfig

        from semolina.config import create_engine

        engine = create_engine(DuckDBConfig(database=":memory:", pool_size=1))
        monkeypatch.setattr(engine, "connect", lambda: conn)
        return engine

    def test_connection_returned_when_cursor_execute_raises(self, monkeypatch: pytest.MonkeyPatch):
        """If cur.execute() raises, the connection is returned to the pool."""
        from adbc_poolhouse import close_pool

        from semolina.query import _Query

        conn = _ExecuteRaisingConn()
        engine = self._engine(monkeypatch, conn)
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        try:
            with pytest.raises(RuntimeError, match="boom from cursor.execute"):
                engine.execute(query)
            assert conn.closed, "connection was not returned to the pool on execute() failure"
        finally:
            close_pool(engine._pool)

    def test_connection_returned_when_conn_cursor_raises(self, monkeypatch: pytest.MonkeyPatch):
        """If conn.cursor() raises, the connection is returned to the pool."""
        from adbc_poolhouse import close_pool

        from semolina.query import _Query

        conn = _CursorRaisingConn()
        engine = self._engine(monkeypatch, conn)
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        try:
            with pytest.raises(RuntimeError, match="boom from conn.cursor"):
                engine.execute(query)
            assert conn.closed, "connection was not returned to the pool on cursor() failure"
        finally:
            close_pool(engine._pool)


class TestEngineDispose:
    """WR-06: Engine.dispose() is the public pool-teardown entry point."""

    def test_dispose_uses_close_pool_for_adbc_pools(self):
        """dispose() routes an ADBC-backed pool through adbc_poolhouse.close_pool."""
        from unittest.mock import MagicMock, patch

        from semolina.engines.duckdb import DuckDBEngine
        from semolina.engines.sql import DuckDBDialect

        pool = MagicMock()
        pool._adbc_source = MagicMock()  # mark as an ADBC pool
        engine = DuckDBEngine(pool=pool, dialect=DuckDBDialect())

        with patch("adbc_poolhouse.close_pool") as mock_close_pool:
            engine.dispose()
            mock_close_pool.assert_called_once_with(pool)
            pool.close.assert_not_called()

    def test_dispose_disposes_a_real_pool(self):
        """dispose() tears down a real DuckDB engine's pool without error."""
        from adbc_poolhouse import DuckDBConfig

        from semolina.config import create_engine

        engine = create_engine(DuckDBConfig(database=":memory:", pool_size=1))
        # Smoke-test: a real ADBC pool disposes cleanly via the public method.
        engine.dispose()
