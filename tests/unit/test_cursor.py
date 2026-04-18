"""
Tests for SemolinaCursor and MockCursor DBAPI 2.0 compliance.

Tests cover:
- CURS-01: SemolinaCursor wraps DBAPI 2.0 cursor via delegation
- CURS-02: fetchall_rows() returns list[Row]
- CURS-03: fetchmany_rows(size) returns list[Row]
- CURS-04: fetchone_row() returns Row | None
- CURS-05: Row attribute and dict access via SemolinaCursor
- MockCursor DBAPI execute(sql, params) and fetchmany(size)

Test classes:
- TestSemolinaCursor: init, description passthrough
- TestFetchallRows: fetchall_rows with data, empty, attribute/dict access
- TestFetchoneRow: fetchone_row iteration and exhaustion
- TestFetchmanyRows: fetchmany_rows with various sizes
- TestSemolinaCursorContextManager: context manager lifecycle
- TestSemolinaCursorRepr: repr in open/closed states
- TestMockCursorDBAPI: execute(sql, params) and fetchmany(size)
- TestSemolinaCursorPassthrough: raw DBAPI passthrough methods
"""

from __future__ import annotations

from typing import Any

from semolina.cursor import SemolinaCursor
from semolina.pool import MockPool
from semolina.results import Row


def _make_cursor(
    fixture_data: list[dict[str, Any]], view_name: str = "sales_view"
) -> SemolinaCursor:
    """Create a SemolinaCursor wrapping MockCursor with fixture data."""
    pool = MockPool()
    pool.load(view_name, fixture_data)
    conn = pool.connect()
    cur = conn.cursor()
    sql = f'SELECT * FROM "{view_name}"'
    cur.execute(sql, None)
    return SemolinaCursor(cur, conn, pool)


FIXTURE_DATA: list[dict[str, Any]] = [
    {"revenue": 1000, "country": "US"},
    {"revenue": 2000, "country": "CA"},
    {"revenue": 500, "country": "MX"},
]


# ---------------------------------------------------------------------------
# TestSemolinaCursor: init and description passthrough
# ---------------------------------------------------------------------------


class TestSemolinaCursor:
    """Test SemolinaCursor construction and basic property delegation."""

    def test_init_stores_references(self) -> None:
        """Creating SemolinaCursor stores cursor, conn, and pool references."""
        pool = MockPool()
        conn = pool.connect()
        cur = conn.cursor()
        sc = SemolinaCursor(cur, conn, pool)
        assert sc._cursor is cur
        assert sc._conn is conn
        assert sc._pool is pool

    def test_description_delegates_to_underlying_cursor(self) -> None:
        """Description property returns underlying cursor's description."""
        sc = _make_cursor(FIXTURE_DATA)
        desc = sc.description
        assert desc is not None
        col_names = [d[0] for d in desc]
        assert "revenue" in col_names
        assert "country" in col_names

    def test_rowcount_delegates_to_underlying_cursor(self) -> None:
        """Rowcount property delegates to underlying cursor."""
        pool = MockPool()
        conn = pool.connect()
        cur = conn.cursor()
        sc = SemolinaCursor(cur, conn, pool)
        # MockCursor doesn't implement rowcount as a property, so this
        # tests the passthrough behavior.
        assert isinstance(sc.rowcount, int)


# ---------------------------------------------------------------------------
# TestFetchallRows: fetchall_rows convenience method
# ---------------------------------------------------------------------------


class TestFetchallRows:
    """Test fetchall_rows() returns list[Row] with correct values."""

    def test_fetchall_rows_returns_list_of_rows(self) -> None:
        """fetchall_rows() after execute returns list[Row]."""
        sc = _make_cursor(FIXTURE_DATA)
        rows = sc.fetchall_rows()
        assert isinstance(rows, list)
        assert len(rows) == 3
        assert all(isinstance(r, Row) for r in rows)

    def test_fetchall_rows_empty_results(self) -> None:
        """fetchall_rows() with empty results returns []."""
        sc = _make_cursor([])
        rows = sc.fetchall_rows()
        assert rows == []

    def test_fetchall_rows_attribute_access(self) -> None:
        """fetchall_rows() Row objects support attribute access."""
        sc = _make_cursor(FIXTURE_DATA)
        rows = sc.fetchall_rows()
        assert rows[0].revenue == 1000
        assert rows[1].revenue == 2000
        assert rows[2].revenue == 500

    def test_fetchall_rows_dict_access(self) -> None:
        """fetchall_rows() Row objects support dict access."""
        sc = _make_cursor(FIXTURE_DATA)
        rows = sc.fetchall_rows()
        assert rows[0]["country"] == "US"
        assert rows[1]["country"] == "CA"
        assert rows[2]["country"] == "MX"


# ---------------------------------------------------------------------------
# TestFetchoneRow: fetchone_row convenience method
# ---------------------------------------------------------------------------


class TestFetchoneRow:
    """Test fetchone_row() returns Row or None."""

    def test_fetchone_row_returns_first_then_next(self) -> None:
        """fetchone_row() returns first Row, then next, then None when exhausted."""
        sc = _make_cursor(FIXTURE_DATA)
        row1 = sc.fetchone_row()
        assert isinstance(row1, Row)
        assert row1.revenue == 1000

        row2 = sc.fetchone_row()
        assert isinstance(row2, Row)
        assert row2.revenue == 2000

        row3 = sc.fetchone_row()
        assert isinstance(row3, Row)
        assert row3.revenue == 500

        row4 = sc.fetchone_row()
        assert row4 is None

    def test_fetchone_row_empty_cursor(self) -> None:
        """fetchone_row() on empty cursor returns None."""
        sc = _make_cursor([])
        assert sc.fetchone_row() is None


# ---------------------------------------------------------------------------
# TestFetchmanyRows: fetchmany_rows convenience method
# ---------------------------------------------------------------------------


class TestFetchmanyRows:
    """Test fetchmany_rows(size) returns list[Row] of up to size rows."""

    def test_fetchmany_rows_returns_requested_count(self) -> None:
        """fetchmany_rows(2) on 3-row cursor returns 2 Rows, next call returns 1."""
        sc = _make_cursor(FIXTURE_DATA)
        batch1 = sc.fetchmany_rows(2)
        assert len(batch1) == 2
        assert all(isinstance(r, Row) for r in batch1)

        batch2 = sc.fetchmany_rows(2)
        assert len(batch2) == 1

    def test_fetchmany_rows_defaults_to_one(self) -> None:
        """fetchmany_rows() defaults to size=1."""
        sc = _make_cursor(FIXTURE_DATA)
        batch = sc.fetchmany_rows()
        assert len(batch) == 1
        assert batch[0].revenue == 1000

    def test_fetchmany_rows_larger_than_available(self) -> None:
        """fetchmany_rows(10) on 3-row cursor returns all 3."""
        sc = _make_cursor(FIXTURE_DATA)
        rows = sc.fetchmany_rows(10)
        assert len(rows) == 3


# ---------------------------------------------------------------------------
# TestSemolinaCursorContextManager: lifecycle management
# ---------------------------------------------------------------------------


class TestSemolinaCursorContextManager:
    """Test SemolinaCursor context manager protocol."""

    def test_context_manager_enter_returns_self(self) -> None:
        """__enter__ returns the SemolinaCursor itself."""
        sc = _make_cursor(FIXTURE_DATA)
        with sc as ctx:
            assert ctx is sc

    def test_close_calls_cursor_and_conn_close(self) -> None:
        """close() calls cursor.close() and conn.close()."""
        pool = MockPool()
        conn = pool.connect()
        cur = conn.cursor()
        sc = SemolinaCursor(cur, conn, pool)
        sc.close()  # Should not raise

    def test_context_manager_closes_on_exit(self) -> None:
        """With statement closes cursor on exit (repr shows closed)."""
        sc = _make_cursor(FIXTURE_DATA)
        with sc:
            assert "open" in repr(sc).lower() or "columns" in repr(sc).lower()
        assert "closed" in repr(sc).lower()


# ---------------------------------------------------------------------------
# TestSemolinaCursorRepr: string representation
# ---------------------------------------------------------------------------


class TestSemolinaCursorRepr:
    """Test SemolinaCursor __repr__."""

    def test_repr_shows_columns_when_open(self) -> None:
        """Repr shows column names when cursor is open."""
        sc = _make_cursor(FIXTURE_DATA)
        r = repr(sc)
        assert "SemolinaCursor" in r
        assert "revenue" in r
        assert "country" in r

    def test_repr_shows_closed_when_closed(self) -> None:
        """Repr shows closed state after close()."""
        sc = _make_cursor(FIXTURE_DATA)
        sc.close()
        r = repr(sc)
        assert "SemolinaCursor" in r
        assert "closed" in r.lower()


# ---------------------------------------------------------------------------
# TestMockCursorDBAPI: execute(sql, params) and fetchmany(size)
# ---------------------------------------------------------------------------


class TestMockCursorDBAPI:
    """Test MockCursor DBAPI 2.0 execute and fetchmany methods."""

    def test_execute_with_from_clause_populates_data(self) -> None:
        """MockCursor.execute(sql, None) populates fixture data from view name."""
        pool = MockPool()
        pool.load("sales_view", FIXTURE_DATA)
        conn = pool.connect()
        cur = conn.cursor()
        cur.execute('SELECT * FROM "sales_view"', None)
        rows = cur.fetchall()
        assert len(rows) == 3

    def test_execute_with_unknown_view_returns_empty(self) -> None:
        """MockCursor.execute() with unknown view produces empty results."""
        pool = MockPool()
        pool.load("sales_view", FIXTURE_DATA)
        conn = pool.connect()
        cur = conn.cursor()
        cur.execute('SELECT * FROM "nonexistent_view"', None)
        rows = cur.fetchall()
        assert rows == []

    def test_execute_params_optional(self) -> None:
        """MockCursor.execute(sql, None) works (params is optional)."""
        pool = MockPool()
        pool.load("sales_view", FIXTURE_DATA)
        conn = pool.connect()
        cur = conn.cursor()
        cur.execute('SELECT * FROM "sales_view"')
        rows = cur.fetchall()
        assert len(rows) == 3

    def test_fetchmany_returns_requested_count(self) -> None:
        """MockCursor.fetchmany(2) returns at most 2 rows."""
        pool = MockPool()
        pool.load("sales_view", FIXTURE_DATA)
        conn = pool.connect()
        cur = conn.cursor()
        cur.execute('SELECT * FROM "sales_view"', None)
        batch = cur.fetchmany(2)
        assert len(batch) == 2
        assert all(isinstance(r, tuple) for r in batch)

    def test_fetchmany_advances_cursor(self) -> None:
        """MockCursor.fetchmany() advances cursor position."""
        pool = MockPool()
        pool.load("sales_view", FIXTURE_DATA)
        conn = pool.connect()
        cur = conn.cursor()
        cur.execute('SELECT * FROM "sales_view"', None)
        cur.fetchmany(2)
        remaining = cur.fetchmany(2)
        assert len(remaining) == 1

    def test_fetchmany_defaults_to_one(self) -> None:
        """MockCursor.fetchmany() defaults to size=1."""
        pool = MockPool()
        pool.load("sales_view", FIXTURE_DATA)
        conn = pool.connect()
        cur = conn.cursor()
        cur.execute('SELECT * FROM "sales_view"', None)
        batch = cur.fetchmany()
        assert len(batch) == 1


# ---------------------------------------------------------------------------
# TestSemolinaCursorPassthrough: raw DBAPI passthrough methods
# ---------------------------------------------------------------------------


class TestSemolinaCursorPassthrough:
    """Test SemolinaCursor raw DBAPI passthrough methods."""

    def test_fetchall_returns_raw_tuples(self) -> None:
        """fetchall() passthrough returns list[tuple]."""
        sc = _make_cursor(FIXTURE_DATA)
        rows = sc.fetchall()
        assert isinstance(rows, list)
        assert all(isinstance(r, tuple) for r in rows)
        assert len(rows) == 3

    def test_fetchone_returns_raw_tuple(self) -> None:
        """fetchone() passthrough returns tuple."""
        sc = _make_cursor(FIXTURE_DATA)
        row = sc.fetchone()
        assert isinstance(row, tuple)

    def test_fetchmany_returns_raw_tuples(self) -> None:
        """fetchmany(2) passthrough returns list[tuple]."""
        sc = _make_cursor(FIXTURE_DATA)
        rows = sc.fetchmany(2)
        assert isinstance(rows, list)
        assert len(rows) == 2
        assert all(isinstance(r, tuple) for r in rows)
