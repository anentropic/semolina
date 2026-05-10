"""
Tests for DuckDB pool lifecycle and extension loading.

Tests cover:
- DUCK-06: DuckDB pool auto-loads semantic_views extension
- TEST-02: DuckDB pool replaces MockPool for pool lifecycle tests

Test classes:
- TestDuckDBPoolLifecycle: pool creation, connect, cursor, close
- TestExtensionLoading: INSTALL + LOAD via connect event
- TestDuckDBPoolIntegration: full query execution flow with Sales model
- TestExecuteWithPool: end-to-end execute() via pool registry
"""

from __future__ import annotations

import warnings
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
        """Register DuckDB pool as named, .using('test') resolves it."""
        from adbc_poolhouse import DuckDBConfig, close_pool, create_pool
        from sqlalchemy import event

        import semolina
        from semolina.config import _load_semantic_views
        from semolina.cursor import SemolinaCursor

        config = DuckDBConfig(database=":memory:", pool_size=1)
        pool = create_pool(config)
        event.listen(pool, "connect", _load_semantic_views)

        with pool.connect() as conn:
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
                DIMENSIONS (s.country AS s.country, s.region AS s.region)
                METRICS (s.revenue AS SUM(s.revenue), s.cost AS SUM(s.cost))
            """)
            cur.close()
            conn.commit()

        semolina.register("test", pool, dialect="duckdb")
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
            close_pool(pool)

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

    def test_execute_falls_back_to_engine_registry(self):
        """execute() falls back to engine registry when no pool registered."""
        import semolina
        from semolina.engines.mock import MockEngine

        engine = MockEngine()
        engine.load("sales_view", [{"revenue": 999, "country": "MX"}])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            semolina.register("default", engine)

        cursor = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).execute()
        rows = cursor.fetchall_rows()
        assert len(rows) == 1
        assert rows[0].revenue == 999
        assert rows[0].country == "MX"
        cursor.close()

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
