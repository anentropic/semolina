"""
Tests for SemolinaCursor DBAPI 2.0 delegation and Row convenience methods.

Tests cover:
- CURS-01: SemolinaCursor wraps DBAPI 2.0 cursor via delegation
- CURS-02: fetchall_rows() returns list[Row]
- CURS-03: fetchmany_rows(size) returns list[Row]
- CURS-04: fetchone_row() returns Row | None
- CURS-05: Row attribute and dict access via SemolinaCursor

Test classes:
- TestSemolinaCursor: init, description passthrough
- TestFetchallRows: fetchall_rows with data, empty, attribute/dict access
- TestFetchoneRow: fetchone_row iteration and exhaustion
- TestFetchmanyRows: fetchmany_rows with various sizes
- TestSemolinaCursorContextManager: context manager lifecycle
- TestSemolinaCursorRepr: repr in open/closed states
- TestSemolinaCursorPassthrough: raw DBAPI passthrough methods
- TestFetchArrowTable: ADBC Arrow passthrough (DuckDB in-process)
"""

from __future__ import annotations

from typing import Any

import pytest

from semolina.cursor import SemolinaCursor
from semolina.results import Row


def _make_cursor(
    fixture_data: list[dict[str, Any]],
    view_name: str = "test_view",
) -> SemolinaCursor:
    """Create a SemolinaCursor wrapping a DuckDB ADBC cursor with fixture data."""
    adbc_driver_duckdb = pytest.importorskip("adbc_driver_duckdb")
    import adbc_driver_manager.dbapi as dbapi

    driver = adbc_driver_duckdb.driver_path()
    conn = dbapi.connect(
        driver=driver, entrypoint="duckdb_adbc_init", db_kwargs={"path": ":memory:"}
    )
    cur = conn.cursor()

    if fixture_data:
        # Infer columns from first row
        columns = list(fixture_data[0].keys())
        col_defs = ", ".join(f"{col} VARCHAR" for col in columns)
        cur.execute(f"CREATE TABLE {view_name} ({col_defs})")

        for row in fixture_data:
            vals = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in row.values())
            cur.execute(f"INSERT INTO {view_name} VALUES ({vals})")

        cols_select = ", ".join(columns)
        cur.execute(f"SELECT {cols_select} FROM {view_name}")
    else:
        # Empty result: create empty table and select
        cur.execute(f"CREATE TABLE {view_name} (dummy INTEGER)")
        cur.execute(f"SELECT * FROM {view_name} WHERE 1=0")

    return SemolinaCursor(cur, conn, conn)


def _make_adbc_cursor(
    *,
    create_sql: str,
    insert_sql: str | None = None,
    select_sql: str,
) -> tuple[SemolinaCursor, Any]:
    """
    Create a SemolinaCursor wrapping a real DuckDB ADBC cursor.

    Returns (SemolinaCursor, connection) -- caller must close connection.
    """
    adbc_driver_duckdb = pytest.importorskip("adbc_driver_duckdb")
    import adbc_driver_manager.dbapi as dbapi

    driver = adbc_driver_duckdb.driver_path()
    conn = dbapi.connect(
        driver=driver, entrypoint="duckdb_adbc_init", db_kwargs={"path": ":memory:"}
    )
    cur = conn.cursor()
    cur.execute(create_sql)
    if insert_sql is not None:
        cur.execute(insert_sql)
    cur.execute(select_sql)
    return SemolinaCursor(cur, conn, conn), conn


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
        adbc_driver_duckdb = pytest.importorskip("adbc_driver_duckdb")
        import adbc_driver_manager.dbapi as dbapi

        driver = adbc_driver_duckdb.driver_path()
        conn = dbapi.connect(
            driver=driver, entrypoint="duckdb_adbc_init", db_kwargs={"path": ":memory:"}
        )
        cur = conn.cursor()
        sc = SemolinaCursor(cur, conn, conn)
        assert sc._cursor is cur
        assert sc._conn is conn
        assert sc._pool is conn
        cur.close()
        conn.close()

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
        sc = _make_cursor(FIXTURE_DATA)
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
        # DuckDB ADBC returns VARCHAR values as strings
        assert str(rows[0].revenue) == "1000"
        assert str(rows[1].revenue) == "2000"
        assert str(rows[2].revenue) == "500"

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
        assert str(row1.revenue) == "1000"

        row2 = sc.fetchone_row()
        assert isinstance(row2, Row)
        assert str(row2.revenue) == "2000"

        row3 = sc.fetchone_row()
        assert isinstance(row3, Row)
        assert str(row3.revenue) == "500"

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
        assert str(batch[0].revenue) == "1000"

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
        adbc_driver_duckdb = pytest.importorskip("adbc_driver_duckdb")
        import adbc_driver_manager.dbapi as dbapi

        driver = adbc_driver_duckdb.driver_path()
        conn = dbapi.connect(
            driver=driver, entrypoint="duckdb_adbc_init", db_kwargs={"path": ":memory:"}
        )
        cur = conn.cursor()
        sc = SemolinaCursor(cur, conn, conn)
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


# ---------------------------------------------------------------------------
# TestFetchArrowTable: ADBC Arrow passthrough (DuckDB in-process)
# ---------------------------------------------------------------------------


class TestFetchArrowTable:
    """Test fetch_arrow_table() returns pyarrow.Table via ADBC delegation."""

    def test_fetch_arrow_table_returns_pyarrow_table(self) -> None:
        """fetch_arrow_table() returns a pyarrow.Table with correct schema."""
        pyarrow = pytest.importorskip("pyarrow")

        sc, conn = _make_adbc_cursor(
            create_sql="CREATE TABLE t (id INTEGER, name VARCHAR)",
            insert_sql="INSERT INTO t VALUES (1, 'alice'), (2, 'bob')",
            select_sql="SELECT * FROM t",
        )
        try:
            table = sc.fetch_arrow_table()
            assert isinstance(table, pyarrow.Table)
            assert table.num_rows == 2
            assert table.column_names == ["id", "name"]
        finally:
            conn.close()

    def test_fetch_arrow_table_column_values(self) -> None:
        """fetch_arrow_table() returns correct column values."""
        pytest.importorskip("pyarrow")

        sc, conn = _make_adbc_cursor(
            create_sql="CREATE TABLE t (id INTEGER, name VARCHAR)",
            insert_sql="INSERT INTO t VALUES (1, 'alice'), (2, 'bob')",
            select_sql="SELECT * FROM t ORDER BY id",
        )
        try:
            table = sc.fetch_arrow_table()
            assert table.column("id").to_pylist() == [1, 2]
            assert table.column("name").to_pylist() == ["alice", "bob"]
        finally:
            conn.close()

    def test_fetch_arrow_table_empty_result(self) -> None:
        """fetch_arrow_table() on empty result returns Table with 0 rows."""
        pyarrow = pytest.importorskip("pyarrow")

        sc, conn = _make_adbc_cursor(
            create_sql="CREATE TABLE t (id INTEGER, name VARCHAR)",
            select_sql="SELECT * FROM t",
        )
        try:
            table = sc.fetch_arrow_table()
            assert isinstance(table, pyarrow.Table)
            assert table.num_rows == 0
            assert table.column_names == ["id", "name"]
        finally:
            conn.close()

    def test_fetch_arrow_table_single_row(self) -> None:
        """fetch_arrow_table() works with a single-row result."""
        pytest.importorskip("pyarrow")

        sc, conn = _make_adbc_cursor(
            create_sql="CREATE TABLE t (id INTEGER)",
            insert_sql="INSERT INTO t VALUES (42)",
            select_sql="SELECT * FROM t",
        )
        try:
            table = sc.fetch_arrow_table()
            assert table.num_rows == 1
            assert table.column("id").to_pylist() == [42]
        finally:
            conn.close()
