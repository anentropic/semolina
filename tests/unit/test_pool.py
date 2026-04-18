"""
Tests for MockPool, MockConnection, and MockCursor.

Tests cover:
- CONN-02: MockPool provides DBAPI 2.0-compatible cursor interface
- CONN-04: Full query-to-result pipeline via MockPool and pool registry

Test classes:
- TestMockPool: init, load, connect, close
- TestMockConnection: context manager protocol, cursor(), close()
- TestMockCursor: description, fetchall, fetchone, _execute_query
- TestMockPoolIntegration: full flow with real _Query objects and Sales model
"""

from __future__ import annotations

from typing import Any

from models import Sales

from semolina.pool import MockConnection, MockCursor, MockPool
from semolina.query import _Query

# ---------------------------------------------------------------------------
# TestMockPool: basic pool lifecycle
# ---------------------------------------------------------------------------


class TestMockPool:
    """Test MockPool initialization, loading, connect, and close."""

    def test_init_creates_empty_fixtures(self):
        """MockPool() creates a pool with no fixtures."""
        pool = MockPool()
        assert pool._fixtures == {}

    def test_load_stores_fixture_data(self):
        """MockPool.load() stores data keyed by view name."""
        pool = MockPool()
        data: list[dict[str, Any]] = [{"revenue": 100, "country": "US"}]
        pool.load("sales_view", data)
        assert pool._fixtures["sales_view"] == data

    def test_load_overwrites_existing_view(self):
        """Loading the same view name overwrites previous data."""
        pool = MockPool()
        pool.load("sales_view", [{"revenue": 100}])
        pool.load("sales_view", [{"revenue": 999}])
        assert pool._fixtures["sales_view"] == [{"revenue": 999}]

    def test_connect_returns_mock_connection(self):
        """MockPool.connect() returns a MockConnection."""
        pool = MockPool()
        conn = pool.connect()
        assert isinstance(conn, MockConnection)

    def test_close_is_noop(self):
        """MockPool.close() does not raise."""
        pool = MockPool()
        pool.close()  # Should not raise


# ---------------------------------------------------------------------------
# TestMockConnection: context manager and cursor
# ---------------------------------------------------------------------------


class TestMockConnection:
    """Test MockConnection context manager protocol, cursor(), close()."""

    def test_context_manager_enter_returns_self(self):
        """__enter__ returns the connection itself."""
        pool = MockPool()
        conn = pool.connect()
        with conn as ctx:
            assert ctx is conn

    def test_context_manager_exit_calls_close(self):
        """__exit__ calls close() (no-op, but must not raise)."""
        pool = MockPool()
        conn = pool.connect()
        with conn:
            pass  # Should not raise

    def test_cursor_returns_mock_cursor(self):
        """MockConnection.cursor() returns a MockCursor."""
        pool = MockPool()
        conn = pool.connect()
        cur = conn.cursor()
        assert isinstance(cur, MockCursor)

    def test_close_is_noop(self):
        """MockConnection.close() does not raise."""
        pool = MockPool()
        conn = pool.connect()
        conn.close()  # Should not raise


# ---------------------------------------------------------------------------
# TestMockCursor: DBAPI 2.0 interface
# ---------------------------------------------------------------------------


class TestMockCursor:
    """Test MockCursor description, fetchall, fetchone, close."""

    def test_description_none_before_execute(self):
        """cursor.description is None before _execute_query."""
        pool = MockPool()
        conn = pool.connect()
        cur = conn.cursor()
        assert cur.description is None

    def test_description_after_execute(self):
        """cursor.description returns 7-element tuples after _execute_query."""
        pool = MockPool()
        pool.load("sales_view", [{"revenue": 100, "country": "US"}])
        conn = pool.connect()
        cur = conn.cursor()
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        cur._execute_query(query)
        desc = cur.description
        assert desc is not None
        assert len(desc) == 2
        # 7-element tuples
        for item in desc:
            assert len(item) == 7
        # Column names present
        col_names = [d[0] for d in desc]
        assert "revenue" in col_names
        assert "country" in col_names

    def test_fetchall_returns_list_of_tuples(self):
        """fetchall() returns list[tuple], not list[dict]."""
        pool = MockPool()
        pool.load("sales_view", [{"revenue": 100, "country": "US"}])
        conn = pool.connect()
        cur = conn.cursor()
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        cur._execute_query(query)
        rows = cur.fetchall()
        assert isinstance(rows, list)
        assert len(rows) == 1
        assert isinstance(rows[0], tuple)

    def test_fetchall_values_match_fixture_data(self):
        """fetchall() tuple values match the fixture data."""
        pool = MockPool()
        pool.load("sales_view", [{"revenue": 100, "country": "US"}])
        conn = pool.connect()
        cur = conn.cursor()
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        cur._execute_query(query)
        rows = cur.fetchall()
        assert len(rows) == 1
        # Values should be (100, "US") or ("US", 100) depending on dict key order
        assert 100 in rows[0]
        assert "US" in rows[0]

    def test_fetchone_returns_single_tuple(self):
        """fetchone() returns a single tuple."""
        pool = MockPool()
        pool.load(
            "sales_view",
            [
                {"revenue": 100, "country": "US"},
                {"revenue": 200, "country": "CA"},
            ],
        )
        conn = pool.connect()
        cur = conn.cursor()
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        cur._execute_query(query)
        row = cur.fetchone()
        assert isinstance(row, tuple)

    def test_fetchone_returns_none_when_exhausted(self):
        """fetchone() returns None after all rows consumed."""
        pool = MockPool()
        pool.load("sales_view", [{"revenue": 100, "country": "US"}])
        conn = pool.connect()
        cur = conn.cursor()
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        cur._execute_query(query)
        cur.fetchone()  # consume the only row
        assert cur.fetchone() is None

    def test_empty_fixtures_return_empty_results(self):
        """When no fixtures loaded for view, fetchall returns empty list."""
        pool = MockPool()
        conn = pool.connect()
        cur = conn.cursor()
        query = _Query().metrics(Sales.revenue)
        cur._execute_query(query)
        rows = cur.fetchall()
        assert rows == []

    def test_close_is_noop(self):
        """MockCursor.close() does not raise."""
        pool = MockPool()
        conn = pool.connect()
        cur = conn.cursor()
        cur.close()  # Should not raise


# ---------------------------------------------------------------------------
# TestMockPoolIntegration: full flow with Sales model
# ---------------------------------------------------------------------------


class TestMockPoolIntegration:
    """Test full MockPool flow with real _Query objects and Sales model."""

    _fixture_data: list[dict[str, Any]] = [
        {"revenue": 100, "cost": 40, "country": "US", "region": "East"},
        {"revenue": 800, "cost": 200, "country": "US", "region": "West"},
        {"revenue": 300, "cost": 90, "country": "CA", "region": "North"},
    ]

    def _pool_with_fixtures(self) -> MockPool:
        pool = MockPool()
        pool.load("sales_view", self._fixture_data)
        return pool

    def test_full_flow_metrics_only(self):
        """Load fixtures, execute metrics-only query, get correct tuples."""
        pool = self._pool_with_fixtures()
        conn = pool.connect()
        cur = conn.cursor()
        query = _Query().metrics(Sales.revenue)
        cur._execute_query(query)
        rows = cur.fetchall()
        assert len(rows) == 3
        # All rows should be tuples
        assert all(isinstance(r, tuple) for r in rows)

    def test_full_flow_metrics_and_dimensions(self):
        """Load fixtures, execute query with metrics + dimensions, verify results."""
        pool = self._pool_with_fixtures()
        conn = pool.connect()
        cur = conn.cursor()
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        cur._execute_query(query)

        desc = cur.description
        assert desc is not None
        col_names = [d[0] for d in desc]

        rows = cur.fetchall()
        assert len(rows) == 3
        # Reconstruct dicts from description + tuples
        row_dicts = [dict(zip(col_names, row, strict=True)) for row in rows]
        revenues = [r["revenue"] for r in row_dicts]
        assert sorted(revenues) == [100, 300, 800]

    def test_where_filter_reduces_results(self):
        """Query with .where(country == 'US') returns only US rows."""
        pool = self._pool_with_fixtures()
        conn = pool.connect()
        cur = conn.cursor()
        query = _Query().dimensions(Sales.country).where(Sales.country == "US")
        cur._execute_query(query)

        desc = cur.description
        assert desc is not None
        col_names = [d[0] for d in desc]

        rows = cur.fetchall()
        assert len(rows) == 2
        row_dicts = [dict(zip(col_names, row, strict=True)) for row in rows]
        assert all(r["country"] == "US" for r in row_dicts)

    def test_where_filter_no_match_returns_empty(self):
        """Query with filter matching nothing returns empty results."""
        pool = self._pool_with_fixtures()
        conn = pool.connect()
        cur = conn.cursor()
        query = _Query().dimensions(Sales.country).where(Sales.country == "MX")
        cur._execute_query(query)
        rows = cur.fetchall()
        assert rows == []


# ---------------------------------------------------------------------------
# TestExecuteWithPool: end-to-end execute() via pool registry
# ---------------------------------------------------------------------------


class TestExecuteWithPool:
    """Test _Query.execute() wired through the pool registry path."""

    def test_execute_with_mock_pool_returns_cursor(self):
        """Register MockPool with dialect, execute query, get SemolinaCursor."""
        import semolina
        from semolina.cursor import SemolinaCursor

        pool = MockPool()
        pool.load("sales_view", [{"revenue": 100, "country": "US"}])
        semolina.register("default", pool, dialect="mock")

        cursor = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).execute()
        assert isinstance(cursor, SemolinaCursor)
        rows = cursor.fetchall_rows()
        assert len(rows) == 1
        assert rows[0].revenue == 100
        assert rows[0].country == "US"
        cursor.close()

    def test_execute_with_named_pool_using(self):
        """Register MockPool as named, .using('test') resolves it."""
        import semolina
        from semolina.cursor import SemolinaCursor

        pool = MockPool()
        pool.load("sales_view", [{"revenue": 42, "country": "CA"}])
        semolina.register("test", pool, dialect="mock")

        cursor = (
            Sales.query().metrics(Sales.revenue).dimensions(Sales.country).using("test").execute()
        )
        assert isinstance(cursor, SemolinaCursor)
        rows = cursor.fetchall_rows()
        assert len(rows) == 1
        assert rows[0].revenue == 42
        cursor.close()

    def test_execute_returns_all_fixture_data(self):
        """MockCursor.execute() returns all fixture data (no predicate filtering)."""
        import semolina

        pool = MockPool()
        pool.load(
            "sales_view",
            [
                {"revenue": 100, "country": "US"},
                {"revenue": 200, "country": "CA"},
                {"revenue": 300, "country": "US"},
            ],
        )
        semolina.register("default", pool, dialect="mock")

        cursor = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .where(Sales.country == "US")
            .execute()
        )
        # MockCursor.execute() returns all rows (no predicate filtering)
        rows = cursor.fetchall_rows()
        assert len(rows) == 3
        cursor.close()

    def test_execute_falls_back_to_engine_registry(self):
        """execute() falls back to engine registry when no pool registered."""
        import warnings

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

    def test_execute_cursor_lifecycle(self):
        """execute() returns cursor; closing cursor releases connection."""
        import semolina

        pool = MockPool()
        pool.load("sales_view", [{"revenue": 100, "country": "US"}])
        semolina.register("default", pool, dialect="mock")

        cursor = Sales.query().metrics(Sales.revenue).execute()
        rows = cursor.fetchall_rows()
        assert len(rows) == 1
        cursor.close()
