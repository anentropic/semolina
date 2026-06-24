"""
Unit tests for DuckDBEngine introspection over a real in-memory ADBC pool.

Phase 44 moves DuckDB introspection off the native ``duckdb`` module and onto
the Engine's ADBC pool: ``engine.introspect(view)`` checks out a connection via
``engine.connect()`` and runs ``DESCRIBE SEMANTIC VIEW`` / ``DESCRIBE SELECT``
through the ADBC cursor. The ``semantic_views`` community extension is loaded by
a ``connect`` event listener on the pool (Pitfall 2), so these tests build a
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
    from collections.abc import Iterator

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
        """Should strip schema prefix for DESCRIBE but preserve it in view_name."""
        result = duckdb_engine.introspect("main.orders")
        assert result.view_name == "main.orders"
        assert result.class_name == "Orders"


class TestDuckDBEngineIntrospectErrors:
    """
    Test DuckDBEngine.introspect() error translation over the ADBC pool.

    A DESCRIBE against a non-existent semantic view surfaces an ADBC error that
    introspect() must translate to SemolinaViewNotFoundError.
    """

    def test_missing_view_raises_view_not_found(self, duckdb_engine: Any) -> None:
        """Introspecting a non-existent view -> SemolinaViewNotFoundError."""
        with pytest.raises(SemolinaViewNotFoundError):
            duckdb_engine.introspect("does_not_exist_view")
