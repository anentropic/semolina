"""
Unit tests for Snowflake introspection over the ADBC-cursor seam.

Phase 44 moves introspection off the native Snowflake driver and onto the
Engine's ADBC pool: ``engine.introspect(view)`` checks out a connection via
``engine.connect()`` and runs ``SHOW COLUMNS IN VIEW`` through the ADBC cursor.
The live spike proved the ADBC cursor returns the identical 13-column
``SHOW COLUMNS`` result the existing parser expects (CONTEXT decision 3), so the
mock here feeds those same rows through a mocked ``connect()`` / ``cursor()``
seam rather than a native-driver module stub.

The engine is built with ``create_engine(SnowflakeConfig(...))`` (D1). The mocks
are deliberately untyped (``MagicMock`` cursors and a patched ``connect()``), so
the per-rule scope-disables below keep basedpyright strict quiet on the mock
seam without a ``# type: ignore``.
"""
# Test-only mock seam: MagicMock cursors and patch.object(engine, "connect", ...)
# are untyped by construction. Scope-disable the rules the mock seam triggers
# under basedpyright strict (intentionally not a `# type: ignore`).
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


def _make_snowflake_engine(**overrides: Any) -> Any:
    """
    Build a SnowflakeEngine via the Phase 44 create_engine factory.

    The engine owns an ADBC pool (mocked at create_pool below) plus the
    Snowflake dialect derived from the config type. Tests then patch
    ``engine.connect`` to drive introspection through a mocked ADBC cursor.
    """
    from adbc_poolhouse import SnowflakeConfig

    from semolina.config import create_engine

    params: dict[str, Any] = {
        "account": "test",
        "user": "user",
        "password": "pass",
    }
    params.update(overrides)
    # Avoid a live ADBC connect: create_pool returns a mock pool. The Engine
    # still owns it; introspection is driven through engine.connect() below.
    with patch("semolina.config.create_pool", return_value=MagicMock(name="pool")):
        return create_engine(SnowflakeConfig(**params))


def _patch_connect(engine: Any, cursor: Any) -> Any:
    """
    Patch ``engine.connect()`` to yield a connection whose cursor is ``cursor``.

    Mirrors the real ADBC checkout seam: ``with engine.connect() as conn:`` then
    ``conn.cursor()``. Both the connection and the cursor support the context
    manager protocol so the engine's ``with`` blocks work unchanged.
    """

    @contextmanager
    def _connect() -> Generator[Any]:
        conn = MagicMock(name="conn")
        conn.cursor.return_value = cursor
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        yield conn

    return patch.object(engine, "connect", side_effect=_connect)


def _show_columns_cursor(rows: list[tuple[Any, ...]]) -> MagicMock:
    """
    Build a mock ADBC cursor returning SHOW COLUMNS IN VIEW rows.

    The ADBC cursor exposes ``.description`` (column_name, kind, data_type,
    comment) and ``.fetchall()`` returning the same row shape the existing
    Snowflake parser consumes.
    """
    cursor = MagicMock(name="cursor")
    cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
    cursor.fetchall.return_value = rows
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


class TestSnowflakeEngineIntrospect:
    """
    Test SnowflakeEngine.introspect() driven through the ADBC-cursor seam.

    Verifies that introspect() executes SHOW COLUMNS IN VIEW over the Engine's
    pooled ADBC connection, parses the 13-column result into IntrospectedView,
    handles kind casing, maps data_type JSON, and qualifies the view name with
    the configured database.
    """

    def test_introspect_basic_metric_dimension_fact(self) -> None:
        """Should parse one metric, one dimension, one fact into IntrospectedView."""
        from semolina.codegen.introspector import IntrospectedField, IntrospectedView

        cursor = _show_columns_cursor(
            [
                ("revenue", "METRIC", json.dumps({"type": "FIXED", "scale": 0}), ""),
                ("country", "DIMENSION", json.dumps({"type": "TEXT"}), ""),
                ("date_key", "FACT", json.dumps({"type": "DATE"}), ""),
            ]
        )
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            result = engine.introspect("sales_view")

        assert isinstance(result, IntrospectedView)
        assert result.view_name == "sales_view"
        assert result.class_name == "SalesView"
        assert len(result.fields) == 3

        revenue = result.fields[0]
        assert isinstance(revenue, IntrospectedField)
        assert revenue.name == "revenue"
        assert revenue.field_type == "metric"
        assert revenue.data_type == "int"

        country = result.fields[1]
        assert country.name == "country"
        assert country.field_type == "dimension"
        assert country.data_type == "str"

        date_key = result.fields[2]
        assert date_key.name == "date_key"
        assert date_key.field_type == "fact"
        assert date_key.data_type == "datetime.date"

    def test_introspect_kind_lowercase_conversion(self) -> None:
        """Should lowercase uppercase METRIC/DIMENSION kind values."""
        cursor = _show_columns_cursor(
            [
                ("total_sales", "METRIC", json.dumps({"type": "FIXED", "scale": 0}), ""),
                ("region", "DIMENSION", json.dumps({"type": "TEXT"}), ""),
            ]
        )
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            result = engine.introspect("report_view")

        assert result.fields[0].field_type == "metric"
        assert result.fields[1].field_type == "dimension"

    def test_introspect_fixed_scale_zero_maps_to_int(self) -> None:
        """Should map FIXED with scale=0 to 'int'."""
        cursor = _show_columns_cursor(
            [("count", "METRIC", json.dumps({"type": "FIXED", "scale": 0}), "")]
        )
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            result = engine.introspect("count_view")

        assert result.fields[0].data_type == "int"

    def test_introspect_fixed_nonzero_scale_maps_to_float(self) -> None:
        """Should map FIXED with scale=2 to 'float'."""
        cursor = _show_columns_cursor(
            [("revenue", "METRIC", json.dumps({"type": "FIXED", "scale": 2}), "")]
        )
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            result = engine.introspect("revenue_view")

        assert result.fields[0].data_type == "float"

    def test_introspect_geography_produces_todo(self) -> None:
        """Should produce data_type starting with 'TODO:' for GEOGRAPHY type."""
        cursor = _show_columns_cursor(
            [("location", "DIMENSION", json.dumps({"type": "GEOGRAPHY"}), "")]
        )
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            result = engine.introspect("geo_view")

        assert result.fields[0].data_type is not None
        assert result.fields[0].data_type.startswith("TODO:")

    def test_introspect_populates_description_from_comment(self) -> None:
        """Should populate field description from 'comment' column when present."""
        cursor = _show_columns_cursor(
            [("revenue", "METRIC", json.dumps({"type": "FIXED", "scale": 0}), "Total revenue")]
        )
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            result = engine.introspect("sales_view")

        assert result.fields[0].description == "Total revenue"

    def test_introspect_executes_correct_sql(self) -> None:
        """Should execute SHOW COLUMNS IN VIEW {view_name} via the ADBC cursor."""
        cursor = _show_columns_cursor([])
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            engine.introspect("my_sales_view")

        executed_sql = cursor.execute.call_args[0][0]
        assert "SHOW COLUMNS IN VIEW" in executed_sql
        assert "my_sales_view" in executed_sql

    def test_introspect_sql_uses_in_view_not_semantic_view(self) -> None:
        """
        Should use SHOW COLUMNS IN VIEW, not SHOW COLUMNS IN SEMANTIC VIEW.

        'SHOW COLUMNS IN SEMANTIC VIEW' is invalid Snowflake SQL. The correct
        syntax is 'SHOW COLUMNS IN VIEW', which works for standard, materialized,
        and semantic views alike.
        """
        cursor = _show_columns_cursor([])
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            engine.introspect("my_sales_view")

        executed_sql = cursor.execute.call_args[0][0]
        assert "SHOW COLUMNS IN VIEW" in executed_sql
        assert "IN SEMANTIC VIEW" not in executed_sql
        assert "my_sales_view" in executed_sql

    def test_introspect_pascal_case_class_name_simple(self) -> None:
        """Should convert snake_case view name to PascalCase class name."""
        cursor = _show_columns_cursor([])
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            result = engine.introspect("sales_revenue_view")

        assert result.class_name == "SalesRevenueView"

    def test_introspect_pascal_case_schema_qualified_name(self) -> None:
        """Should use last segment after '.' for class name derivation."""
        cursor = _show_columns_cursor([])
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            result = engine.introspect("my_db.my_schema.sales_view")

        assert result.class_name == "SalesView"
        assert result.view_name == "my_db.my_schema.sales_view"

    def test_introspect_auto_qualifies_two_part_name_with_database(self) -> None:
        """
        Should prepend the configured database to a two-part schema.view name.

        SHOW COLUMNS IN VIEW requires a fully-qualified three-part identifier.
        When the caller passes schema.view, introspect() prepends the database
        from the Engine's SnowflakeConfig.
        """
        cursor = _show_columns_cursor([])
        engine = _make_snowflake_engine(database="MY_DB")
        with _patch_connect(engine, cursor):
            engine.introspect("dev.sem_orders")

        executed_sql = cursor.execute.call_args[0][0]
        assert "MY_DB.dev.sem_orders" in executed_sql

    def test_introspect_auto_qualifies_one_part_name_with_database(self) -> None:
        """Should prepend the configured database to a bare view name."""
        cursor = _show_columns_cursor([])
        engine = _make_snowflake_engine(database="MY_DB")
        with _patch_connect(engine, cursor):
            engine.introspect("sem_orders")

        executed_sql = cursor.execute.call_args[0][0]
        assert "MY_DB.sem_orders" in executed_sql

    def test_introspect_three_part_name_used_as_is(self) -> None:
        """Should not modify a fully-qualified three-part name even when database is set."""
        cursor = _show_columns_cursor([])
        engine = _make_snowflake_engine(database="MY_DB")
        with _patch_connect(engine, cursor):
            engine.introspect("OTHER_DB.dev.sem_orders")

        executed_sql = cursor.execute.call_args[0][0]
        assert "OTHER_DB.dev.sem_orders" in executed_sql
        assert "MY_DB" not in executed_sql

    def test_introspect_uppercase_column_lowercased_no_source_name(self) -> None:
        """
        Standard UPPERCASE column (ORDER_ID) -> name='order_id', source_name=None.

        For standard Snowflake UPPERCASE columns the Python field name is the
        lowercased version; normalize_identifier round-trips it, so source_name
        is not needed.
        """
        cursor = _show_columns_cursor(
            [("ORDER_ID", "DIMENSION", json.dumps({"type": "FIXED", "scale": 0}), "")]
        )
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            result = engine.introspect("orders_view")

        field = result.fields[0]
        assert field.name == "order_id"
        assert field.source_name is None

    def test_introspect_quoted_lowercase_column_gets_source_name(self) -> None:
        """
        Quoted-lowercase column ('order_id') -> name='order_id', source_name='order_id'.

        A column created with a quoted identifier is stored lowercase, so
        upper() != original and source_name preserves the warehouse column name.
        """
        cursor = _show_columns_cursor(
            [("order_id", "DIMENSION", json.dumps({"type": "FIXED", "scale": 0}), "")]
        )
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            result = engine.introspect("orders_view")

        field = result.fields[0]
        assert field.name == "order_id"
        assert field.source_name == "order_id"


class TestSnowflakeEngineIntrospectErrors:
    """
    Test introspect() error translation over the ADBC cursor.

    Over ADBC, warehouse errors surface as ``adbc_driver_manager.Error``
    subclasses (PEP-249) rather than the native-driver error classes. The
    introspector must still raise SemolinaViewNotFoundError /
    SemolinaConnectionError.
    """

    def test_introspect_missing_view_raises_view_not_found(self) -> None:
        """A warehouse error for an unknown view -> SemolinaViewNotFoundError."""
        pytest.importorskip("adbc_driver_manager")
        from adbc_driver_manager import (  # pyright: ignore[reportMissingImports]
            AdbcStatusCode,
            ProgrammingError,
        )

        from semolina.engines.base import SemolinaViewNotFoundError

        cursor = _show_columns_cursor([])
        cursor.execute.side_effect = ProgrammingError(
            "Semantic view 'nonexistent_view' does not exist",
            status_code=AdbcStatusCode.NOT_FOUND,
        )
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor), pytest.raises(SemolinaViewNotFoundError):
            engine.introspect("nonexistent_view")
