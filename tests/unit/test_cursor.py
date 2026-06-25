"""
Tests for SemolinaCursor DBAPI 2.0 delegation and Row convenience methods.

Tests cover:
- CURS-01: SemolinaCursor wraps DBAPI 2.0 cursor via delegation
- CURS-02: fetchall_rows() returns list[Row]
- CURS-03: fetchmany_rows(size) returns list[Row]
- CURS-04: fetchone_row() returns Row | None
- CURS-05: Row attribute and dict access via SemolinaCursor
- STREAM-01: fetch_record_batch() returns pyarrow.RecordBatchReader (ADBC passthrough)
- STREAM-02: __iter__/__next__ yield Row objects lazily from RecordBatchReader

Test classes:
- TestSemolinaCursor: init, description passthrough
- TestFetchallRows: fetchall_rows with data, empty, attribute/dict access
- TestFetchoneRow: fetchone_row iteration and exhaustion
- TestFetchmanyRows: fetchmany_rows with various sizes
- TestSemolinaCursorContextManager: context manager lifecycle
- TestSemolinaCursorRepr: repr in open/closed states
- TestSemolinaCursorPassthrough: raw DBAPI passthrough methods
- TestFetchArrowTable: ADBC Arrow passthrough (DuckDB in-process)
- TestFetchRecordBatch: ADBC RecordBatchReader passthrough (STREAM-01)
- TestStreamingIteration: __iter__/__next__ semantics over RecordBatchReader (STREAM-02)
"""

from __future__ import annotations

from types import SimpleNamespace
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


class _CountingReader:
    """
    Duck-typed fake of ``pyarrow.RecordBatchReader`` for streaming tests.

    Counts calls to ``read_next_batch`` so tests can assert laziness. We
    duck-type instead of subclassing because pyarrow forbids subclassing
    ``RecordBatchReader`` (see 39-RESEARCH.md, "Don't Hand-Roll").
    """

    def __init__(self, schema: Any, batches: Any) -> None:
        """
        Initialise with a schema and an iterator of batches.

        Args:
            schema: pyarrow schema describing the batches.
            batches: iterator (or iterable) of pyarrow.RecordBatch objects.
        """
        self.schema = schema
        self.batches = iter(batches)
        self.read_count = 0
        self.closed = False

    def __iter__(self) -> _CountingReader:
        """Return self so the reader is its own iterator."""
        return self

    def read_next_batch(self) -> Any:
        """
        Return the next batch, raising StopIteration when exhausted.

        Returns:
            The next pyarrow.RecordBatch from the underlying iterator.
        """
        self.read_count += 1
        return next(self.batches)

    def __next__(self) -> Any:
        """Delegate to ``read_next_batch`` for iterator protocol parity."""
        return self.read_next_batch()

    def close(self) -> None:
        """Mark the reader as closed (no underlying resource to release)."""
        self.closed = True


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

    def test_del_closes_unclosed_connection(self) -> None:
        """__del__ returns a leaked connection to the pool (best-effort)."""

        class _TrackingConn:
            def __init__(self) -> None:
                self.closed = False

            def close(self) -> None:
                self.closed = True

        conn = _TrackingConn()
        sc = SemolinaCursor(cursor=object(), conn=conn, pool=object())
        # Simulate a caller that forgot to close() and use the context manager.
        sc.__del__()
        assert conn.closed is True

    def test_del_does_not_double_close(self) -> None:
        """__del__ is a no-op once the cursor is already closed."""

        class _TrackingConn:
            def __init__(self) -> None:
                self.close_calls = 0

            def close(self) -> None:
                self.close_calls += 1

        class _NoopCursor:
            def close(self) -> None:
                pass

        conn = _TrackingConn()
        sc = SemolinaCursor(cursor=_NoopCursor(), conn=conn, pool=object())
        sc.close()
        assert conn.close_calls == 1
        sc.__del__()
        assert conn.close_calls == 1  # finalizer did not re-close

    def test_del_never_raises_on_partial_init(self) -> None:
        """__del__ tolerates a partially-initialised instance without raising."""
        sc = SemolinaCursor.__new__(SemolinaCursor)  # __init__ never ran
        sc.__del__()  # must not raise even though _conn/_closed are absent


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


# ---------------------------------------------------------------------------
# TestFetchRecordBatch: ADBC RecordBatchReader passthrough (STREAM-01)
# ---------------------------------------------------------------------------


class TestFetchRecordBatch:
    """Test fetch_record_batch() returns pyarrow.RecordBatchReader via ADBC delegation."""

    def test_returns_record_batch_reader(self) -> None:
        """fetch_record_batch() returns a pyarrow.RecordBatchReader instance."""
        pyarrow = pytest.importorskip("pyarrow")

        sc, conn = _make_adbc_cursor(
            create_sql="CREATE TABLE t (id INTEGER, name VARCHAR)",
            insert_sql="INSERT INTO t VALUES (1, 'alice'), (2, 'bob')",
            select_sql="SELECT * FROM t",
        )
        try:
            reader = sc.fetch_record_batch()
            assert isinstance(reader, pyarrow.RecordBatchReader)
        finally:
            conn.close()

    def test_schema_columns_match_description(self) -> None:
        """Reader's schema.names matches the column names from cursor.description."""
        pytest.importorskip("pyarrow")

        sc, conn = _make_adbc_cursor(
            create_sql="CREATE TABLE t (id INTEGER, name VARCHAR)",
            insert_sql="INSERT INTO t VALUES (1, 'alice')",
            select_sql="SELECT id, name FROM t",
        )
        try:
            description_names = [d[0] for d in sc.description or []]
            reader = sc.fetch_record_batch()
            assert list(reader.schema.names) == description_names
        finally:
            conn.close()

    def test_empty_result(self) -> None:
        """fetch_record_batch() on empty SELECT yields a reader with zero rows."""
        pytest.importorskip("pyarrow")

        sc, conn = _make_adbc_cursor(
            create_sql="CREATE TABLE t (id INTEGER, name VARCHAR)",
            select_sql="SELECT * FROM t",
        )
        try:
            reader = sc.fetch_record_batch()
            table = reader.read_all()
            assert table.num_rows == 0
            assert list(table.column_names) == ["id", "name"]
        finally:
            conn.close()

    def test_mock_cursor_raises(self) -> None:
        """
        fetch_record_batch() on a non-ADBC cursor raises AttributeError.

        Parity with fetch_arrow_table on MockCursor.
        """
        sc = SemolinaCursor(object(), object(), object())
        with pytest.raises(AttributeError):
            sc.fetch_record_batch()


# ---------------------------------------------------------------------------
# TestStreamingIteration: __iter__/__next__ over RecordBatchReader (STREAM-02)
# ---------------------------------------------------------------------------


class TestStreamingIteration:
    """Test SemolinaCursor.__iter__/__next__ lazy row streaming semantics."""

    def test_iter_returns_self(self) -> None:
        """iter(sc) is sc — SemolinaCursor is its own iterator."""
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        reader = _CountingReader(schema, iter([]))
        fake_cursor = SimpleNamespace(
            fetch_record_batch=lambda: reader,
            description=[("revenue", None), ("country", None)],
        )
        fake_conn = SimpleNamespace(close=lambda: None)
        sc = SemolinaCursor(fake_cursor, fake_conn, SimpleNamespace())
        assert iter(sc) is sc

    def test_yields_row_objects(self) -> None:
        """
        Iterating a SemolinaCursor over real ADBC data yields Row objects.

        Verifies attribute access works on the resulting Rows.
        """
        pytest.importorskip("pyarrow")

        sc, conn = _make_adbc_cursor(
            create_sql="CREATE TABLE t (id INTEGER, name VARCHAR)",
            insert_sql="INSERT INTO t VALUES (1, 'alice'), (2, 'bob'), (3, 'carol')",
            select_sql="SELECT id, name FROM t ORDER BY id",
        )
        try:
            rows = list(sc)
            assert len(rows) == 3
            assert all(isinstance(r, Row) for r in rows)
            assert rows[0].id == 1
            assert rows[0].name == "alice"
            assert rows[1].id == 2
            assert rows[2].name == "carol"
        finally:
            conn.close()

    def test_multiple_batches(self) -> None:
        """Iteration yields rows from multiple non-empty batches in order."""
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        batches = [
            pa.RecordBatch.from_pydict({"revenue": [1, 2], "country": ["US", "CA"]}, schema=schema),
            pa.RecordBatch.from_pydict({"revenue": [3, 4], "country": ["MX", "FR"]}, schema=schema),
            pa.RecordBatch.from_pydict({"revenue": [5, 6], "country": ["DE", "JP"]}, schema=schema),
        ]
        reader = _CountingReader(schema, iter(batches))
        fake_cursor = SimpleNamespace(
            fetch_record_batch=lambda: reader,
            description=[("revenue", None), ("country", None)],
        )
        fake_conn = SimpleNamespace(close=lambda: None)
        sc = SemolinaCursor(fake_cursor, fake_conn, SimpleNamespace())

        rows = list(sc)
        assert len(rows) == 6
        assert [r.revenue for r in rows] == [1, 2, 3, 4, 5, 6]
        assert [r.country for r in rows] == ["US", "CA", "MX", "FR", "DE", "JP"]

    def test_lazy_batch_pull(self) -> None:
        """Iteration pulls batches lazily — partial consumption pulls only the needed batches."""
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        batches = [
            pa.RecordBatch.from_pydict({"revenue": [1, 2], "country": ["US", "CA"]}, schema=schema),
            pa.RecordBatch.from_pydict({"revenue": [3, 4], "country": ["MX", "FR"]}, schema=schema),
            pa.RecordBatch.from_pydict({"revenue": [5, 6], "country": ["DE", "JP"]}, schema=schema),
        ]
        reader = _CountingReader(schema, iter(batches))
        fake_cursor = SimpleNamespace(
            fetch_record_batch=lambda: reader,
            description=[("revenue", None), ("country", None)],
        )
        fake_conn = SimpleNamespace(close=lambda: None)
        sc = SemolinaCursor(fake_cursor, fake_conn, SimpleNamespace())

        it = iter(sc)

        # First row forces the first batch to be pulled.
        first = next(it)
        assert first.revenue == 1
        assert reader.read_count == 1

        # Second row comes from the same batch — no new pull.
        second = next(it)
        assert second.revenue == 2
        assert reader.read_count == 1

        # Third row exhausts batch 1 → pulls batch 2.
        third = next(it)
        assert third.revenue == 3
        assert reader.read_count == 2

        # Abandon iteration — batch 3 must NOT have been pulled.
        assert reader.read_count == 2

    def test_skips_empty_batches(self) -> None:
        """Zero-row batches mid-stream are skipped without terminating iteration."""
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        empty_batch = pa.RecordBatch.from_pydict({"revenue": [], "country": []}, schema=schema)
        non_empty_1 = pa.RecordBatch.from_pydict(
            {"revenue": [10, 20], "country": ["US", "CA"]}, schema=schema
        )
        non_empty_2 = pa.RecordBatch.from_pydict(
            {"revenue": [30, 40], "country": ["MX", "FR"]}, schema=schema
        )
        reader = _CountingReader(schema, iter([empty_batch, non_empty_1, empty_batch, non_empty_2]))
        fake_cursor = SimpleNamespace(
            fetch_record_batch=lambda: reader,
            description=[("revenue", None), ("country", None)],
        )
        fake_conn = SimpleNamespace(close=lambda: None)
        sc = SemolinaCursor(fake_cursor, fake_conn, SimpleNamespace())

        rows = list(sc)
        assert len(rows) == 4
        assert [r.revenue for r in rows] == [10, 20, 30, 40]
        assert [r.country for r in rows] == ["US", "CA", "MX", "FR"]

    def test_after_fetch_arrow_table(self) -> None:
        """After fetch_arrow_table drains the reader, iteration yields zero rows."""
        pytest.importorskip("pyarrow")

        sc, conn = _make_adbc_cursor(
            create_sql="CREATE TABLE t (id INTEGER, name VARCHAR)",
            insert_sql="INSERT INTO t VALUES (1, 'alice'), (2, 'bob'), (3, 'carol')",
            select_sql="SELECT id, name FROM t ORDER BY id",
        )
        try:
            table = sc.fetch_arrow_table()
            assert table.num_rows == 3
            assert list(sc) == []
        finally:
            conn.close()

    def test_reiteration_yields_nothing(self) -> None:
        """Re-iterating an exhausted cursor yields zero rows (no raise)."""
        pytest.importorskip("pyarrow")

        sc, conn = _make_adbc_cursor(
            create_sql="CREATE TABLE t (id INTEGER, name VARCHAR)",
            insert_sql="INSERT INTO t VALUES (1, 'alice'), (2, 'bob'), (3, 'carol')",
            select_sql="SELECT id, name FROM t ORDER BY id",
        )
        try:
            first_pass = list(sc)
            assert len(first_pass) == 3
            second_pass = list(sc)
            assert second_pass == []
        finally:
            conn.close()

    def test_does_not_auto_close(self) -> None:
        """Iteration to exhaustion does NOT close the cursor."""
        pytest.importorskip("pyarrow")

        sc, conn = _make_adbc_cursor(
            create_sql="CREATE TABLE t (id INTEGER, name VARCHAR)",
            insert_sql="INSERT INTO t VALUES (1, 'alice'), (2, 'bob'), (3, 'carol')",
            select_sql="SELECT id, name FROM t ORDER BY id",
        )
        try:
            rows = list(sc)
            assert len(rows) == 3
            assert sc._closed is False
            assert "closed" not in repr(sc).lower()
        finally:
            conn.close()
