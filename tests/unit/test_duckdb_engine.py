"""
Unit tests for DuckDBEngine introspection over a real in-memory ADBC pool.

DuckDB introspection runs over the Engine's ADBC pool rather than the native
``duckdb`` module: ``engine.introspect(view)`` checks out a connection via
``engine.connect()`` and runs ``DESCRIBE SEMANTIC VIEW`` / ``DESCRIBE SELECT``
through the ADBC cursor. The ``semantic_views`` community extension is loaded by
a ``connect`` event listener on the pool, so these tests build a
real in-memory DuckDB Engine via ``create_engine(DuckDBConfig(...))`` and
introspect a real semantic view rather than monkeypatching the native module.

The fixtures reach the pool through ``engine._pool`` for teardown; the
per-rule scope-disable below keeps basedpyright strict quiet on that private
access without a ``# type: ignore``.
"""
# Test-only: the introspection fixtures reach the owned pool via engine._pool
# for close_pool teardown. Scope-disable the private-access rule that triggers
# (intentionally not a `# type: ignore`).
# pyright: reportPrivateUsage=false

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from semolina.codegen.introspector import IntrospectedField, IntrospectedView
from semolina.engines.base import SemolinaViewNotFoundError

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator

pytest.importorskip("adbc_driver_duckdb")


def _create_view_sql(view_name: str = "orders") -> list[str]:
    """
    Build DDL for a small DuckDB semantic view used by the introspection tests.

    Produces one dimension (region: VARCHAR -> str) and one PUBLIC metric
    (revenue: SUM -> float), plus a PRIVATE metric that introspection must
    exclude.
    """
    return [
        "CREATE TABLE orders_data (id INTEGER, region VARCHAR, amount DOUBLE, cost DOUBLE)",
        "INSERT INTO orders_data VALUES (1, 'US', 100.0, 10.0), (2, 'CA', 200.0, 20.0)",
        f"""
        CREATE OR REPLACE SEMANTIC VIEW {view_name} AS
        TABLES (o AS orders_data PRIMARY KEY (id))
        DIMENSIONS (o.region AS o.region)
        METRICS (
            o.revenue AS SUM(o.amount),
            PRIVATE o.internal_cost AS SUM(o.cost)
        )
        """,
    ]


@pytest.fixture
def duckdb_engine() -> Iterator[Any]:
    """
    Build a real in-memory DuckDB Engine with the semantic_views extension.

    Mirrors the ``duckdb_pool`` conftest analog: ``create_engine(DuckDBConfig)``
    owns an ADBC pool whose ``connect`` event loads ``semantic_views``. The
    semantic view DDL is created on the live connection so ``introspect`` runs
    the real two-pass DESCRIBE path. Teardown closes the pool through the engine.
    """
    from adbc_poolhouse import DuckDBConfig, close_pool

    from semolina.config import create_engine

    engine = create_engine(DuckDBConfig(database=":memory:", pool_size=1))
    with engine.connect() as conn:
        cur = conn.cursor()
        for stmt in _create_view_sql():
            cur.execute(stmt)
        cur.close()
        conn.commit()
    try:
        yield engine
    finally:
        close_pool(engine._pool)


class TestDuckDBEngineIntrospect:
    """
    Test DuckDBEngine.introspect() over a real in-memory ADBC pool.

    Verifies the two-pass introspection (DESCRIBE SEMANTIC VIEW for structure +
    DESCRIBE SELECT for types), PUBLIC/PRIVATE access handling, type mapping,
    PascalCase class names, and schema-qualified name stripping.
    """

    def test_introspect_basic_dimension_and_metric(self, duckdb_engine: Any) -> None:
        """Should parse dimensions and metrics into IntrospectedView."""
        result = duckdb_engine.introspect("orders")

        assert isinstance(result, IntrospectedView)
        assert result.view_name == "orders"
        assert result.class_name == "Orders"

        by_name = {f.name: f for f in result.fields}
        region = by_name["region"]
        assert isinstance(region, IntrospectedField)
        assert region.field_type == "dimension"
        assert region.data_type == "str"

        revenue = by_name["revenue"]
        assert revenue.field_type == "metric"
        assert revenue.data_type == "float"

    def test_introspect_private_fields_excluded(self, duckdb_engine: Any) -> None:
        """Should exclude PRIVATE metric fields from the output."""
        result = duckdb_engine.introspect("orders")
        field_names = [f.name for f in result.fields]
        assert "internal_cost" not in field_names
        assert "region" in field_names
        assert "revenue" in field_names

    def test_introspect_pascal_case_class_name(self) -> None:
        """Should convert snake_case view name to PascalCase class name."""
        from adbc_poolhouse import DuckDBConfig, close_pool

        from semolina.config import create_engine

        engine = create_engine(DuckDBConfig(database=":memory:", pool_size=1))
        with engine.connect() as conn:
            cur = conn.cursor()
            for stmt in _create_view_sql(view_name="sales_revenue_view"):
                cur.execute(stmt)
            cur.close()
            conn.commit()
        try:
            result = engine.introspect("sales_revenue_view")
            assert result.class_name == "SalesRevenueView"
        finally:
            close_pool(engine._pool)

    def test_introspect_schema_qualified_name_preserved(self, duckdb_engine: Any) -> None:
        """A schema-qualified name is kept whole in ``view_name``; the class takes its tail."""
        result = duckdb_engine.introspect("main.orders")
        assert result.view_name == "main.orders"
        assert result.class_name == "Orders"


class TestDuckDBIntrospectNamesTheViewItWasGiven:
    """
    ``introspect()`` describes the view its name names: schema and quoting included (FILT-05).

    Before phase 54 it stripped the schema, so ``analytics.orders`` described ``main.orders``
    whenever both existed, and it pasted the bare name into ``DESCRIBE SEMANTIC VIEW``
    unquoted, so a name with a space was a syntax error.
    """

    @pytest.fixture
    def two_schemas(self, duckdb_engine: Any) -> Any:
        """Add ``analytics.orders``, with a ``channel`` where ``main.orders`` has ``region``."""
        with duckdb_engine.connect() as conn:
            cur = conn.cursor()
            for stmt in [
                "CREATE SCHEMA analytics",
                "CREATE TABLE analytics.orders_data (id INTEGER, channel VARCHAR, amount DOUBLE)",
                "INSERT INTO analytics.orders_data VALUES (1, 'web', 5.0)",
                """
                CREATE SEMANTIC VIEW analytics.orders AS
                TABLES (o AS analytics.orders_data PRIMARY KEY (id))
                DIMENSIONS (o.channel AS o.channel)
                METRICS (o.revenue AS SUM(o.amount))
                """,
            ]:
                cur.execute(stmt)
            cur.close()
            conn.commit()
        return duckdb_engine

    def test_a_schema_prefix_selects_that_schemas_view(self, two_schemas: Any) -> None:
        """``analytics.orders`` is the analytics view, not ``main.orders``."""
        fields = {f.name for f in two_schemas.introspect("analytics.orders").fields}
        assert fields == {"channel", "revenue"}

    def test_a_bare_name_is_still_the_default_schemas_view(self, two_schemas: Any) -> None:
        """Without a prefix, the search path decides, as it does for a query."""
        fields = {f.name for f in two_schemas.introspect("orders").fields}
        assert fields == {"region", "revenue"}

    @pytest.fixture
    def spaced_view(self, duckdb_engine: Any) -> Any:
        """Add a view whose name has a space, so it needs quoting everywhere it is written."""
        with duckdb_engine.connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE SEMANTIC VIEW "Order Book" AS
                TABLES (o AS orders_data PRIMARY KEY (id))
                DIMENSIONS (o.region AS o.region)
                METRICS (o.revenue AS SUM(o.amount))
                """
            )
            cur.close()
            conn.commit()
        return duckdb_engine

    @pytest.mark.parametrize("name", ["Order Book", '"Order Book"'])
    def test_a_name_needing_quotes_is_introspected(self, spaced_view: Any, name: str) -> None:
        """A space in the name is quoted, whether or not the caller quoted it."""
        result = spaced_view.introspect(name)
        assert {f.name for f in result.fields} == {"region", "revenue"}
        assert result.class_name == "OrderBook"

    def test_a_name_needing_quotes_round_trips_through_codegen(self, spaced_view: Any) -> None:
        """
        The generated model is valid Python and queries the view it was generated from.

        ``"Order Book"`` used to become the class name ``Order book``, which is not one.
        """
        import sys
        import types

        import semolina
        from semolina.codegen.python_renderer import render_views

        source = render_views([spaced_view.introspect('"Order Book"')])
        module = types.ModuleType("_generated_model_under_test")
        sys.modules[module.__name__] = module
        try:
            exec(compile(source, module.__name__, "exec"), module.__dict__)  # noqa: S102
        finally:
            sys.modules.pop(module.__name__, None)
        model = module.__dict__["OrderBook"]

        semolina.register("default", spaced_view)
        try:
            cursor = (
                model.query()
                .metrics(model.revenue)
                .dimensions(model.region)
                .order_by(model.region)
                .execute()
            )
            rows = [(row.region, row.revenue) for row in cursor.fetchall_rows()]
            cursor.close()
        finally:
            semolina.unregister("default")
        assert rows == [("CA", 200.0), ("US", 100.0)]


class TestDuckDBEngineIntrospectErrors:
    """
    Test DuckDBEngine.introspect() error translation over the ADBC pool.

    A DESCRIBE against a non-existent semantic view surfaces an ADBC error that
    introspect() must translate to SemolinaViewNotFoundError.
    """

    @pytest.mark.parametrize("name", ["nosuch.sales_view", "nosuchdb.main.sales_view"])
    def test_a_missing_schema_or_catalog_raises_view_not_found(
        self, duckdb_engine: Any, name: str
    ) -> None:
        """A typo in the schema or catalog part is a missing view, not a connection failure."""
        from semolina.engines.base import SemolinaViewNotFoundError

        with pytest.raises(SemolinaViewNotFoundError):
            duckdb_engine.introspect(name)

    def test_missing_view_raises_view_not_found(self, duckdb_engine: Any) -> None:
        """Introspecting a non-existent view -> SemolinaViewNotFoundError."""
        with pytest.raises(SemolinaViewNotFoundError):
            duckdb_engine.introspect("does_not_exist_view")

    @pytest.mark.parametrize(
        ("error_class", "message"),
        [
            ("OperationalError", "IO Error: database file not found"),
            ("InterfaceError", "driver does not exist in the search path"),
            ("DataError", "Conversion Error: did you mean INTEGER?"),
        ],
        ids=["operational", "interface", "data"],
    )
    def test_the_driver_error_type_decides_before_the_message(
        self, error_class: str, message: str
    ) -> None:
        """
        A connection-level error is a connection error, whatever its message says (FILT-08).

        Before phase 54 any message containing "not found", "does not exist" or "did you
        mean" was reported as a missing view, so a missing database file read as a missing
        view.
        """
        from contextlib import contextmanager
        from unittest.mock import MagicMock, patch

        import adbc_driver_manager as adbc
        from adbc_poolhouse import DuckDBConfig, close_pool

        from semolina.config import create_engine
        from semolina.engines.base import SemolinaConnectionError

        error = getattr(adbc, error_class)(message, status_code=adbc.AdbcStatusCode.IO)

        @contextmanager
        def failing_connect() -> Generator[Any]:
            conn = MagicMock(name="conn")
            conn.cursor.return_value.execute.side_effect = error
            yield conn

        engine = create_engine(DuckDBConfig(database=":memory:", pool_size=1))
        try:
            with (
                patch.object(engine, "connect", side_effect=failing_connect),
                pytest.raises(SemolinaConnectionError) as raised,
            ):
                engine.introspect("orders")
        finally:
            close_pool(engine._pool)
        assert raised.value.__cause__ is error


class TestSqlStrLiteral:
    """Test the introspection SQL-string-literal escaping helper."""

    def test_plain_value_is_quoted(self) -> None:
        """A quote-free value is wrapped in single quotes unchanged."""
        from semolina.engines.duckdb import _sql_str_literal

        assert _sql_str_literal("revenue") == "'revenue'"

    def test_embedded_single_quote_is_doubled(self) -> None:
        """An embedded single quote is doubled so it cannot break the literal."""
        from semolina.engines.duckdb import _sql_str_literal

        assert _sql_str_literal("o'brien") == "'o''brien'"

    def test_injection_attempt_stays_inside_literal(self) -> None:
        """A quote-and-paren payload is fully contained within the literal."""
        from semolina.engines.duckdb import _sql_str_literal

        assert _sql_str_literal("x') --") == "'x'') --'"
