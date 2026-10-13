"""
Unit tests for Snowflake introspection over the ADBC-cursor seam.

Snowflake introspection runs over the Engine's ADBC pool rather than the native
Snowflake driver: ``engine.introspect(view)`` checks out a connection via
``engine.connect()`` and runs ``SHOW COLUMNS IN VIEW`` through the ADBC cursor.
A live measurement showed the ADBC cursor returns the identical 13-column
``SHOW COLUMNS`` result the existing parser expects, so the
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
    Build a SnowflakeEngine via the create_engine factory.

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


def _show_columns_cursor(
    rows: list[tuple[Any, ...]],
    session: tuple[str | None, str | None] = ("SESSION_DB", "SESSION_SCHEMA"),
) -> MagicMock:
    """
    Build a mock ADBC cursor returning SHOW COLUMNS IN VIEW rows.

    The ADBC cursor exposes ``.description`` (column_name, kind, data_type,
    comment) and ``.fetchall()`` returning the same row shape the existing
    Snowflake parser consumes. ``.fetchone()`` answers the
    ``SELECT CURRENT_DATABASE(), CURRENT_SCHEMA()`` that qualifies a name given
    with fewer than three parts.
    """
    cursor = MagicMock(name="cursor")
    cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
    cursor.fetchall.return_value = rows
    cursor.fetchone.return_value = session
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


class TestSnowflakeEngineIntrospect:
    """
    Test SnowflakeEngine.introspect() driven through the ADBC-cursor seam.

    Verifies that introspect() executes SHOW COLUMNS IN VIEW over the Engine's
    pooled ADBC connection, parses the 13-column result into IntrospectedView,
    handles kind casing, maps data_type JSON, and qualifies the view name from
    the session's current database and schema.
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
        assert revenue.data_type == "decimal.Decimal"

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

    def test_introspect_fixed_scale_zero_maps_to_decimal(self) -> None:
        """
        Should map FIXED with scale=0 to 'decimal.Decimal'.

        The Decimal policy covers the whole FIXED family: the driver returns Decimal128 for
        every FIXED column, scale 0 included.
        """
        cursor = _show_columns_cursor(
            [("count", "METRIC", json.dumps({"type": "FIXED", "scale": 0}), "")]
        )
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            result = engine.introspect("count_view")

        assert result.fields[0].data_type == "decimal.Decimal"

    def test_introspect_fixed_nonzero_scale_maps_to_decimal(self) -> None:
        """Should map FIXED with scale=2 to 'decimal.Decimal'."""
        cursor = _show_columns_cursor(
            [("revenue", "METRIC", json.dumps({"type": "FIXED", "scale": 2}), "")]
        )
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            result = engine.introspect("revenue_view")

        assert result.fields[0].data_type == "decimal.Decimal"

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
        """Should execute SHOW COLUMNS IN VIEW on the quoted, folded name via the cursor."""
        cursor = _show_columns_cursor([])
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            engine.introspect("my_sales_view")

        executed_sql = cursor.execute.call_args[0][0]
        assert "SHOW COLUMNS IN VIEW" in executed_sql
        assert executed_sql.endswith('."MY_SALES_VIEW"')

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
        assert executed_sql.endswith('."MY_SALES_VIEW"')

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

    def test_introspect_qualifies_a_bare_name_from_the_session(self) -> None:
        """
        A bare view name takes the session's current database and schema.

        SHOW COLUMNS IN VIEW refuses anything short of database.schema.view. Measured live
        in 53-04: a bare name prefixed with the configured database alone
        (``MY_DB.sem_orders``) is read as schema.view and refused with ``Must specify the
        full search path starting from database``. The session answers both parts, and
        its answer replays from a cassette where a config value would not.
        """
        cursor = _show_columns_cursor([], session=("SESSION_DB", "SESSION_SCHEMA"))
        engine = _make_snowflake_engine(database="MY_DB")
        with _patch_connect(engine, cursor):
            engine.introspect("sem_orders")

        executed = [c[0][0] for c in cursor.execute.call_args_list]
        assert executed == [
            "SELECT CURRENT_DATABASE(), CURRENT_SCHEMA()",
            'SHOW COLUMNS IN VIEW "SESSION_DB"."SESSION_SCHEMA"."SEM_ORDERS"',
        ]

    def test_introspect_qualifies_a_two_part_name_with_the_session_database(self) -> None:
        """A schema.view name takes only the database from the session."""
        cursor = _show_columns_cursor([], session=("SESSION_DB", "SESSION_SCHEMA"))
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            engine.introspect("dev.sem_orders")

        executed_sql = cursor.execute.call_args[0][0]
        assert executed_sql == 'SHOW COLUMNS IN VIEW "SESSION_DB"."DEV"."SEM_ORDERS"'

    def test_introspect_three_part_name_used_as_is(self) -> None:
        """A fully-qualified three-part name needs no session query; it is only quoted."""
        cursor = _show_columns_cursor([])
        engine = _make_snowflake_engine(database="MY_DB")
        with _patch_connect(engine, cursor):
            engine.introspect("OTHER_DB.dev.sem_orders")

        executed = [c[0][0] for c in cursor.execute.call_args_list]
        assert executed == ['SHOW COLUMNS IN VIEW "OTHER_DB"."DEV"."SEM_ORDERS"']

    def test_introspect_quotes_a_name_that_needs_it(self) -> None:
        """
        Each part is quoted, so a space parses and a pre-quoted part keeps its case (FILT-05).

        The session's own names are quoted as the session returned them: they are already
        the stored names, and folding a case-sensitive ``my_db`` would name another database.
        """
        cursor = _show_columns_cursor([], session=("my_db", "SESSION_SCHEMA"))
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor):
            engine.introspect('dev."Order Book"')

        executed_sql = cursor.execute.call_args[0][0]
        assert executed_sql == 'SHOW COLUMNS IN VIEW "my_db"."DEV"."Order Book"'

    @pytest.mark.parametrize("session", [(None, None), ("SESSION_DB", None)])
    def test_introspect_without_a_session_schema_says_to_qualify(
        self, session: tuple[str | None, str | None]
    ) -> None:
        """No current schema to fill in: the error names the view and says to qualify it."""
        from semolina.engines.base import SemolinaViewNotFoundError

        cursor = _show_columns_cursor([], session=session)
        engine = _make_snowflake_engine()
        with (
            _patch_connect(engine, cursor),
            pytest.raises(SemolinaViewNotFoundError, match=r"sem_orders.*database\.schema"),
        ):
            engine.introspect("sem_orders")

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

    @pytest.mark.parametrize(
        "error_class",
        [
            "InterfaceError",
            "DatabaseError",
            "DataError",
            "OperationalError",
            "IntegrityError",
            "InternalError",
            "NotSupportedError",
        ],
    )
    def test_every_other_adbc_error_is_a_connection_error(self, error_class: str) -> None:
        """
        No ADBC error escapes ``introspect()`` untranslated (FILT-08).

        Only ``ProgrammingError`` means the view is missing. Before phase 54 only
        ``OperationalError`` was translated as well, so the other five reached the caller as
        raw driver errors.
        """
        adbc = pytest.importorskip("adbc_driver_manager")
        from semolina.engines.base import SemolinaConnectionError

        cls = getattr(adbc, error_class)
        # NotSupportedError takes no status code: the driver manager fixes it at NOT_IMPLEMENTED.
        error = (
            cls("boom")
            if cls is adbc.NotSupportedError
            else cls("boom", status_code=adbc.AdbcStatusCode.UNKNOWN)
        )
        cursor = _show_columns_cursor([])
        cursor.execute.side_effect = error
        engine = _make_snowflake_engine()
        with _patch_connect(engine, cursor), pytest.raises(SemolinaConnectionError) as raised:
            engine.introspect("DB.S.SALES_VIEW")
        assert raised.value.__cause__ is error
