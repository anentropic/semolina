"""
Unit tests for DuckDBEngine introspection using unittest.mock.

Tests cover:
- Lazy import and initialization
- Two-step introspection (DESCRIBE SEMANTIC VIEW + DESCRIBE SELECT)
- Field type mapping (dimension, metric, fact)
- PRIVATE field exclusion
- Type resolution via duckdb_type_to_python()
- Description from COMMENT property
- PascalCase class name derivation
- Schema-qualified name stripping
- Error handling and translation
- NotImplementedError for to_sql and execute

All tests use unittest.mock to simulate duckdb module behavior without
requiring an actual DuckDB database with semantic views.
"""

from __future__ import annotations

import builtins
import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from semolina.codegen.introspector import IntrospectedField, IntrospectedView
from semolina.engines.base import SemolinaConnectionError, SemolinaViewNotFoundError

if TYPE_CHECKING:
    from semolina.engines.duckdb import DuckDBEngine


def _create_mock_duckdb() -> tuple[MagicMock, type, type, type]:
    """
    Create a properly structured mock for the duckdb module.

    Returns:
        Tuple of (mock_duckdb, CatalogException, IOException, Error).
    """
    Error = type("Error", (Exception,), {})
    CatalogException = type("CatalogException", (Error,), {})
    IOException = type("IOException", (Error,), {})

    mock_duckdb = MagicMock()
    mock_duckdb.Error = Error
    mock_duckdb.CatalogException = CatalogException
    mock_duckdb.IOException = IOException

    return mock_duckdb, CatalogException, IOException, Error


def _make_describe_semantic_view_rows(
    fields: list[dict[str, str]],
    view_name: str = "orders",
) -> list[tuple[str, str, str, str, str]]:
    """
    Build mock DESCRIBE SEMANTIC VIEW rows from a simplified field list.

    Each field dict should have keys: name, kind, expression, and optionally
    access_modifier and comment.
    """
    rows: list[tuple[str, str, str, str, str]] = []
    for f in fields:
        kind = f["kind"].upper()
        name = f["name"]
        rows.append((kind, name, view_name, "TABLE", view_name))
        rows.append((kind, name, view_name, "EXPRESSION", f.get("expression", name)))
        rows.append((kind, name, view_name, "DATA_TYPE", ""))
        if "access_modifier" in f:
            rows.append((kind, name, view_name, "ACCESS_MODIFIER", f["access_modifier"]))
        if "comment" in f:
            rows.append((kind, name, view_name, "COMMENT", f["comment"]))
    return rows


def _make_describe_select_rows(
    fields: list[tuple[str, str]],
) -> list[tuple[str, str, str, None, None, None]]:
    """
    Build mock DESCRIBE SELECT rows.

    Args:
        fields: List of (column_name, column_type) tuples.
    """
    return [(name, dtype, "YES", None, None, None) for name, dtype in fields]


class TestDuckDBEngineInit:
    """
    Test DuckDBEngine initialization and lazy import behavior.

    Verifies that __init__ stores the database path without establishing
    a connection and raises helpful ImportError when duckdb is not installed.
    """

    def test_init_stores_database_path(self) -> None:
        """Should store database path without creating connection."""
        mock_duckdb, *_ = _create_mock_duckdb()

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            from semolina.engines.duckdb import DuckDBEngine

            engine = DuckDBEngine(database="/path/to/db")
            assert engine._database == "/path/to/db"
            mock_duckdb.connect.assert_not_called()

    def test_init_defaults_to_memory(self) -> None:
        """Should default database to ':memory:' when not specified."""
        mock_duckdb, *_ = _create_mock_duckdb()

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            from semolina.engines.duckdb import DuckDBEngine

            engine = DuckDBEngine()
            assert engine._database == ":memory:"

    def test_lazy_import_raises_helpful_error(self) -> None:
        """Should raise helpful ImportError when duckdb is not installed."""
        mock_duckdb, *_ = _create_mock_duckdb()

        # First import DuckDBEngine with duckdb available
        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            from semolina.engines.duckdb import DuckDBEngine

        # Now simulate duckdb not being importable
        original_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "duckdb":
                raise ImportError("No module named 'duckdb'")
            return original_import(name, *args, **kwargs)  # type: ignore[reportUnknownArgumentType]

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(ImportError) as exc_info:
                DuckDBEngine(database=":memory:")

            error_msg = str(exc_info.value)
            assert "duckdb" in error_msg
            assert "pip install semolina[duckdb]" in error_msg


class TestDuckDBEngineIntrospect:
    """
    Test DuckDBEngine.introspect() with mocked duckdb module.

    Verifies two-step introspection: DESCRIBE SEMANTIC VIEW for field structure
    and DESCRIBE SELECT for type resolution.
    """

    def _setup_engine_and_conn(
        self,
        mock_duckdb: MagicMock,
    ) -> tuple[DuckDBEngine, MagicMock]:
        """Set up DuckDBEngine and mock connection."""
        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            from semolina.engines.duckdb import DuckDBEngine

            engine = DuckDBEngine(database="/path/to/db")
        return engine, mock_conn

    def test_introspect_basic_dimension_and_metric(self) -> None:
        """Should parse dimensions and metrics into IntrospectedView."""
        mock_duckdb, *_ = _create_mock_duckdb()
        engine, mock_conn = self._setup_engine_and_conn(mock_duckdb)

        describe_sv_rows = _make_describe_semantic_view_rows(
            [
                {"name": "region", "kind": "DIMENSION"},
                {
                    "name": "revenue",
                    "kind": "METRIC",
                    "expression": "SUM(o.amount)",
                    "access_modifier": "PUBLIC",
                },
            ]
        )
        describe_select_rows = _make_describe_select_rows(
            [
                ("region", "VARCHAR"),
                ("revenue", "DOUBLE"),
            ]
        )

        call_count = 0

        def execute_side_effect(sql: str) -> MagicMock:
            nonlocal call_count
            result = MagicMock()
            if "DESCRIBE SEMANTIC VIEW" in sql:
                result.fetchall.return_value = describe_sv_rows
            else:
                result.fetchall.return_value = describe_select_rows
            call_count += 1
            return result

        mock_conn.execute.side_effect = execute_side_effect

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            result = engine.introspect("orders")

        assert isinstance(result, IntrospectedView)
        assert result.view_name == "orders"
        assert result.class_name == "Orders"
        assert len(result.fields) == 2

        region = result.fields[0]
        assert isinstance(region, IntrospectedField)
        assert region.name == "region"
        assert region.field_type == "dimension"
        assert region.data_type == "str"

        revenue = result.fields[1]
        assert revenue.name == "revenue"
        assert revenue.field_type == "metric"
        assert revenue.data_type == "float"

    def test_introspect_fact_fields(self) -> None:
        """Should handle fact fields with separate DESCRIBE SELECT query."""
        mock_duckdb, *_ = _create_mock_duckdb()
        engine, mock_conn = self._setup_engine_and_conn(mock_duckdb)

        describe_sv_rows = _make_describe_semantic_view_rows(
            [
                {"name": "region", "kind": "DIMENSION"},
                {
                    "name": "item_price",
                    "kind": "FACT",
                    "expression": "o.price",
                    "access_modifier": "PUBLIC",
                },
            ]
        )

        def execute_side_effect(sql: str) -> MagicMock:
            result = MagicMock()
            if "DESCRIBE SEMANTIC VIEW" in sql:
                result.fetchall.return_value = describe_sv_rows
            elif "facts" in sql:
                result.fetchall.return_value = _make_describe_select_rows(
                    [
                        ("item_price", "DOUBLE"),
                    ]
                )
            else:
                result.fetchall.return_value = _make_describe_select_rows(
                    [
                        ("region", "VARCHAR"),
                    ]
                )
            return result

        mock_conn.execute.side_effect = execute_side_effect

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            result = engine.introspect("orders")

        fact = next(f for f in result.fields if f.name == "item_price")
        assert fact.field_type == "fact"
        assert fact.data_type == "float"

    def test_introspect_private_fields_excluded(self) -> None:
        """Should exclude PRIVATE fields from output."""
        mock_duckdb, *_ = _create_mock_duckdb()
        engine, mock_conn = self._setup_engine_and_conn(mock_duckdb)

        describe_sv_rows = _make_describe_semantic_view_rows(
            [
                {"name": "region", "kind": "DIMENSION"},
                {
                    "name": "revenue",
                    "kind": "METRIC",
                    "expression": "SUM(o.amount)",
                    "access_modifier": "PUBLIC",
                },
                {
                    "name": "internal_cost",
                    "kind": "METRIC",
                    "expression": "SUM(o.cost)",
                    "access_modifier": "PRIVATE",
                },
            ]
        )
        describe_select_rows = _make_describe_select_rows(
            [
                ("region", "VARCHAR"),
                ("revenue", "DOUBLE"),
            ]
        )

        def execute_side_effect(sql: str) -> MagicMock:
            result = MagicMock()
            if "DESCRIBE SEMANTIC VIEW" in sql:
                result.fetchall.return_value = describe_sv_rows
            else:
                result.fetchall.return_value = describe_select_rows
            return result

        mock_conn.execute.side_effect = execute_side_effect

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            result = engine.introspect("orders")

        field_names = [f.name for f in result.fields]
        assert "internal_cost" not in field_names
        assert "region" in field_names
        assert "revenue" in field_names

    def test_introspect_unmappable_type_returns_todo(self) -> None:
        """Should produce data_type with TODO prefix for unmappable types."""
        mock_duckdb, *_ = _create_mock_duckdb()
        engine, mock_conn = self._setup_engine_and_conn(mock_duckdb)

        describe_sv_rows = _make_describe_semantic_view_rows(
            [
                {"name": "tags", "kind": "DIMENSION"},
            ]
        )
        describe_select_rows = _make_describe_select_rows(
            [
                ("tags", "STRUCT(a INTEGER, b VARCHAR)"),
            ]
        )

        def execute_side_effect(sql: str) -> MagicMock:
            result = MagicMock()
            if "DESCRIBE SEMANTIC VIEW" in sql:
                result.fetchall.return_value = describe_sv_rows
            else:
                result.fetchall.return_value = describe_select_rows
            return result

        mock_conn.execute.side_effect = execute_side_effect

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            result = engine.introspect("orders")

        assert result.fields[0].data_type is not None
        assert result.fields[0].data_type.startswith("TODO:")

    def test_introspect_comment_populates_description(self) -> None:
        """Should populate field description from COMMENT property."""
        mock_duckdb, *_ = _create_mock_duckdb()
        engine, mock_conn = self._setup_engine_and_conn(mock_duckdb)

        describe_sv_rows = _make_describe_semantic_view_rows(
            [
                {
                    "name": "revenue",
                    "kind": "METRIC",
                    "expression": "SUM(o.amount)",
                    "access_modifier": "PUBLIC",
                    "comment": "Total revenue in USD",
                },
            ]
        )
        describe_select_rows = _make_describe_select_rows(
            [
                ("revenue", "DOUBLE"),
            ]
        )

        def execute_side_effect(sql: str) -> MagicMock:
            result = MagicMock()
            if "DESCRIBE SEMANTIC VIEW" in sql:
                result.fetchall.return_value = describe_sv_rows
            else:
                result.fetchall.return_value = describe_select_rows
            return result

        mock_conn.execute.side_effect = execute_side_effect

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            result = engine.introspect("orders")

        assert result.fields[0].description == "Total revenue in USD"

    def test_introspect_schema_qualified_name_stripped(self) -> None:
        """Should strip schema prefix for DESCRIBE SEMANTIC VIEW."""
        mock_duckdb, *_ = _create_mock_duckdb()
        engine, mock_conn = self._setup_engine_and_conn(mock_duckdb)

        describe_sv_rows = _make_describe_semantic_view_rows(
            [{"name": "region", "kind": "DIMENSION"}],
            view_name="orders",
        )
        describe_select_rows = _make_describe_select_rows(
            [
                ("region", "VARCHAR"),
            ]
        )

        executed_sqls: list[str] = []

        def execute_side_effect(sql: str) -> MagicMock:
            executed_sqls.append(sql)
            result = MagicMock()
            if "DESCRIBE SEMANTIC VIEW" in sql:
                result.fetchall.return_value = describe_sv_rows
            else:
                result.fetchall.return_value = describe_select_rows
            return result

        mock_conn.execute.side_effect = execute_side_effect

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            result = engine.introspect("main.orders")

        # DESCRIBE SEMANTIC VIEW should use unqualified name
        describe_sql = next(sql for sql in executed_sqls if "DESCRIBE SEMANTIC VIEW" in sql)
        assert "DESCRIBE SEMANTIC VIEW orders" in describe_sql
        assert "main.orders" not in describe_sql

        # But the view_name in the result preserves the original
        assert result.view_name == "main.orders"

    def test_introspect_pascal_case_class_name(self) -> None:
        """Should convert snake_case view name to PascalCase class name."""
        mock_duckdb, *_ = _create_mock_duckdb()
        engine, mock_conn = self._setup_engine_and_conn(mock_duckdb)

        describe_sv_rows = _make_describe_semantic_view_rows(
            [{"name": "region", "kind": "DIMENSION"}],
            view_name="sales_revenue_view",
        )
        describe_select_rows = _make_describe_select_rows(
            [
                ("region", "VARCHAR"),
            ]
        )

        def execute_side_effect(sql: str) -> MagicMock:
            result = MagicMock()
            if "DESCRIBE SEMANTIC VIEW" in sql:
                result.fetchall.return_value = describe_sv_rows
            else:
                result.fetchall.return_value = describe_select_rows
            return result

        mock_conn.execute.side_effect = execute_side_effect

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            result = engine.introspect("sales_revenue_view")

        assert result.class_name == "SalesRevenueView"

    def test_introspect_pascal_case_schema_qualified(self) -> None:
        """Should derive class name from last segment of schema-qualified name."""
        mock_duckdb, *_ = _create_mock_duckdb()
        engine, mock_conn = self._setup_engine_and_conn(mock_duckdb)

        describe_sv_rows = _make_describe_semantic_view_rows(
            [{"name": "region", "kind": "DIMENSION"}],
            view_name="sales_view",
        )
        describe_select_rows = _make_describe_select_rows(
            [
                ("region", "VARCHAR"),
            ]
        )

        def execute_side_effect(sql: str) -> MagicMock:
            result = MagicMock()
            if "DESCRIBE SEMANTIC VIEW" in sql:
                result.fetchall.return_value = describe_sv_rows
            else:
                result.fetchall.return_value = describe_select_rows
            return result

        mock_conn.execute.side_effect = execute_side_effect

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            result = engine.introspect("main.sales_view")

        assert result.class_name == "SalesView"
        assert result.view_name == "main.sales_view"

    def test_introspect_connects_with_correct_database(self) -> None:
        """Should pass database path and read_only=True to duckdb.connect."""
        mock_duckdb, *_ = _create_mock_duckdb()
        engine, mock_conn = self._setup_engine_and_conn(mock_duckdb)

        describe_sv_rows = _make_describe_semantic_view_rows(
            [
                {"name": "region", "kind": "DIMENSION"},
            ]
        )
        describe_select_rows = _make_describe_select_rows(
            [
                ("region", "VARCHAR"),
            ]
        )

        def execute_side_effect(sql: str) -> MagicMock:
            result = MagicMock()
            if "DESCRIBE SEMANTIC VIEW" in sql:
                result.fetchall.return_value = describe_sv_rows
            else:
                result.fetchall.return_value = describe_select_rows
            return result

        mock_conn.execute.side_effect = execute_side_effect

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            engine.introspect("orders")

        mock_duckdb.connect.assert_called_once_with(database="/path/to/db", read_only=True)

    def test_introspect_loads_semantic_views_extension_before_describe(self) -> None:
        """Should load semantic_views on the introspection connection before queries."""
        mock_duckdb, *_ = _create_mock_duckdb()
        engine, mock_conn = self._setup_engine_and_conn(mock_duckdb)

        describe_sv_rows = _make_describe_semantic_view_rows(
            [
                {"name": "region", "kind": "DIMENSION"},
            ]
        )
        describe_select_rows = _make_describe_select_rows(
            [
                ("region", "VARCHAR"),
            ]
        )

        executed_sqls: list[str] = []

        def execute_side_effect(sql: str) -> MagicMock:
            executed_sqls.append(sql)
            result = MagicMock()
            if sql == "LOAD semantic_views":
                result.fetchall.return_value = []
            elif "DESCRIBE SEMANTIC VIEW" in sql:
                result.fetchall.return_value = describe_sv_rows
            else:
                result.fetchall.return_value = describe_select_rows
            return result

        mock_conn.execute.side_effect = execute_side_effect

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            engine.introspect("orders")

        assert executed_sqls[0] == "LOAD semantic_views"
        assert "DESCRIBE SEMANTIC VIEW orders" in executed_sqls[1]

    def test_introspect_dimensions_without_access_modifier(self) -> None:
        """Dimensions do not have access modifiers and should always be included."""
        mock_duckdb, *_ = _create_mock_duckdb()
        engine, mock_conn = self._setup_engine_and_conn(mock_duckdb)

        describe_sv_rows = _make_describe_semantic_view_rows(
            [
                {"name": "region", "kind": "DIMENSION"},
                {"name": "country", "kind": "DIMENSION"},
            ]
        )
        describe_select_rows = _make_describe_select_rows(
            [
                ("region", "VARCHAR"),
                ("country", "VARCHAR"),
            ]
        )

        def execute_side_effect(sql: str) -> MagicMock:
            result = MagicMock()
            if "DESCRIBE SEMANTIC VIEW" in sql:
                result.fetchall.return_value = describe_sv_rows
            else:
                result.fetchall.return_value = describe_select_rows
            return result

        mock_conn.execute.side_effect = execute_side_effect

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            result = engine.introspect("orders")

        assert len(result.fields) == 2
        assert all(f.field_type == "dimension" for f in result.fields)

    def test_introspect_field_without_type_in_describe_select(self) -> None:
        """Should handle fields not found in DESCRIBE SELECT with None data_type."""
        mock_duckdb, *_ = _create_mock_duckdb()
        engine, mock_conn = self._setup_engine_and_conn(mock_duckdb)

        describe_sv_rows = _make_describe_semantic_view_rows(
            [
                {"name": "region", "kind": "DIMENSION"},
                {
                    "name": "private_metric",
                    "kind": "METRIC",
                    "expression": "SUM(o.amount)",
                    "access_modifier": "PRIVATE",
                },
            ]
        )
        describe_select_rows = _make_describe_select_rows(
            [
                ("region", "VARCHAR"),
            ]
        )

        def execute_side_effect(sql: str) -> MagicMock:
            result = MagicMock()
            if "DESCRIBE SEMANTIC VIEW" in sql:
                result.fetchall.return_value = describe_sv_rows
            else:
                result.fetchall.return_value = describe_select_rows
            return result

        mock_conn.execute.side_effect = execute_side_effect

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            result = engine.introspect("orders")

        # PRIVATE metric excluded
        assert len(result.fields) == 1
        assert result.fields[0].name == "region"


class TestDuckDBEngineErrorHandling:
    """
    Test DuckDBEngine error handling for introspect().

    Verifies that duckdb exceptions are mapped to semolina exception types.
    """

    def test_catalog_exception_raises_view_not_found(self) -> None:
        """CatalogException from DESCRIBE SEMANTIC VIEW -> SemolinaViewNotFoundError."""
        mock_duckdb, CatalogException, _, _ = _create_mock_duckdb()
        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn
        mock_conn.execute.side_effect = CatalogException("Semantic view not found")

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            from semolina.engines.duckdb import DuckDBEngine

            engine = DuckDBEngine(database=":memory:")

            with pytest.raises(SemolinaViewNotFoundError) as exc_info:
                engine.introspect("nonexistent_view")

            assert "not found" in str(exc_info.value).lower()

    def test_io_exception_raises_connection_error(self) -> None:
        """IOException from connect -> SemolinaConnectionError."""
        mock_duckdb, _, IOException, _ = _create_mock_duckdb()
        mock_duckdb.connect.side_effect = IOException("Cannot open database")

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            from semolina.engines.duckdb import DuckDBEngine

            engine = DuckDBEngine(database="/nonexistent/path.db")

            with pytest.raises(SemolinaConnectionError) as exc_info:
                engine.introspect("orders")

            assert "connection" in str(exc_info.value).lower()

    def test_generic_error_raises_runtime_error(self) -> None:
        """Generic duckdb.Error raises RuntimeError."""
        mock_duckdb, _, _, Error = _create_mock_duckdb()
        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn
        mock_conn.execute.side_effect = Error("Unexpected error")

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            from semolina.engines.duckdb import DuckDBEngine

            engine = DuckDBEngine(database=":memory:")

            with pytest.raises(RuntimeError) as exc_info:
                engine.introspect("orders")

            assert "Unexpected error" in str(exc_info.value)

    def test_connection_closed_after_error(self) -> None:
        """Connection should be closed even after an error."""
        mock_duckdb, CatalogException, _, _ = _create_mock_duckdb()
        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn
        mock_conn.execute.side_effect = CatalogException("View not found")

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            from semolina.engines.duckdb import DuckDBEngine

            engine = DuckDBEngine(database=":memory:")

            with pytest.raises(SemolinaViewNotFoundError):
                engine.introspect("orders")

        mock_conn.close.assert_called_once()


class TestDuckDBEngineNotImplemented:
    """
    Test DuckDBEngine to_sql() and execute() raise NotImplementedError.

    DuckDBEngine is introspection-only; query execution uses the pool path.
    """

    def test_to_sql_raises_not_implemented(self) -> None:
        """to_sql() should raise NotImplementedError."""
        mock_duckdb, *_ = _create_mock_duckdb()

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            from semolina.engines.duckdb import DuckDBEngine

            engine = DuckDBEngine(database=":memory:")

            with pytest.raises(NotImplementedError) as exc_info:
                engine.to_sql(MagicMock())

            assert "introspection only" in str(exc_info.value).lower()

    def test_execute_raises_not_implemented(self) -> None:
        """execute() should raise NotImplementedError."""
        mock_duckdb, *_ = _create_mock_duckdb()

        with patch.dict(sys.modules, {"duckdb": mock_duckdb}):
            from semolina.engines.duckdb import DuckDBEngine

            engine = DuckDBEngine(database=":memory:")

            with pytest.raises(NotImplementedError) as exc_info:
                engine.execute(MagicMock())

            assert "introspection only" in str(exc_info.value).lower()
