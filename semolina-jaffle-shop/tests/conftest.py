"""
Shared pytest fixtures for semolina-jaffle-shop tests.

Provides in-memory DuckDB connection pools pre-loaded with jaffle-shop
fixture data and real ``SEMANTIC VIEW`` definitions. Pools are registered
with semolina so tests call ``Model.query().execute()`` against a real
``semantic_view()`` execution -- aggregation, grouping, ordering, limiting,
and filtering all run for real.

The semantic views are (re)created on every new physical connection via a
SQLAlchemy ``connect`` event. ADBC poolhouse creates independent DuckDB
instances per physical connection (``source.adbc_clone``), so each new
connection must build its own tables and views.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from fixtures.mock_data import customers_data, orders_data, products_data

import semolina

# ---------------------------------------------------------------------------
# Semantic-view setup helpers (run on each new physical connection)
# ---------------------------------------------------------------------------


def _setup_orders(dbapi_conn: Any, _connection_record: Any) -> None:
    """Create the orders table and the ``orders`` semantic view."""
    cur = dbapi_conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER,
            order_total DECIMAL(10, 2),
            order_count INTEGER,
            tax_paid DECIMAL(10, 2),
            order_cost DECIMAL(10, 2),
            ordered_at TIMESTAMP,
            order_total_dim DECIMAL(10, 2),
            is_food_order BOOLEAN,
            is_drink_order BOOLEAN,
            customer_order_number INTEGER
        )
    """)
    cur.execute("DELETE FROM orders")
    for row_id, r in enumerate(orders_data, start=1):
        cur.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                row_id,
                r["order_total"],
                r["order_count"],
                r["tax_paid"],
                r["order_cost"],
                r["ordered_at"],
                r["order_total_dim"],
                r["is_food_order"],
                r["is_drink_order"],
                r["customer_order_number"],
            ],
        )
    cur.execute("""
        CREATE OR REPLACE SEMANTIC VIEW orders AS
        TABLES (
            o AS orders PRIMARY KEY (id)
        )
        DIMENSIONS (
            o.ordered_at AS o.ordered_at,
            o.order_total_dim AS o.order_total_dim,
            o.is_food_order AS o.is_food_order,
            o.is_drink_order AS o.is_drink_order,
            o.customer_order_number AS o.customer_order_number
        )
        METRICS (
            o.order_total AS SUM(o.order_total),
            o.order_count AS SUM(o.order_count),
            o.tax_paid AS SUM(o.tax_paid),
            o.order_cost AS SUM(o.order_cost)
        )
    """)
    cur.close()
    dbapi_conn.commit()


def _setup_customers(dbapi_conn: Any, _connection_record: Any) -> None:
    """Create the customers table and the ``customers`` semantic view."""
    cur = dbapi_conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER,
            customers INTEGER,
            count_lifetime_orders INTEGER,
            lifetime_spend_pretax DECIMAL(12, 2),
            lifetime_spend DECIMAL(12, 2),
            customer_name VARCHAR,
            customer_type VARCHAR,
            first_ordered_at TIMESTAMP,
            last_ordered_at TIMESTAMP
        )
    """)
    cur.execute("DELETE FROM customers")
    for row_id, r in enumerate(customers_data, start=1):
        cur.execute(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                row_id,
                r["customers"],
                r["count_lifetime_orders"],
                r["lifetime_spend_pretax"],
                r["lifetime_spend"],
                r["customer_name"],
                r["customer_type"],
                r["first_ordered_at"],
                r["last_ordered_at"],
            ],
        )
    cur.execute("""
        CREATE OR REPLACE SEMANTIC VIEW customers AS
        TABLES (
            c AS customers PRIMARY KEY (id)
        )
        DIMENSIONS (
            c.customer_name AS c.customer_name,
            c.customer_type AS c.customer_type,
            c.first_ordered_at AS c.first_ordered_at,
            c.last_ordered_at AS c.last_ordered_at
        )
        METRICS (
            c.customers AS SUM(c.customers),
            c.count_lifetime_orders AS SUM(c.count_lifetime_orders),
            c.lifetime_spend_pretax AS SUM(c.lifetime_spend_pretax),
            c.lifetime_spend AS SUM(c.lifetime_spend)
        )
    """)
    cur.close()
    dbapi_conn.commit()


def _setup_products(dbapi_conn: Any, _connection_record: Any) -> None:
    """
    Create the products table and the ``products`` semantic view.

    Products has no metrics. DuckDB allows a metric-less semantic view, so
    the numeric ``product_price`` is modelled as a FACT (a non-aggregated
    numeric column) and the rest as DIMENSIONS. A ``dimensions(...)`` query
    returns the distinct combinations of the selected dimensions.
    """
    cur = dbapi_conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER,
            product_name VARCHAR,
            product_type VARCHAR,
            product_description VARCHAR,
            is_food_item BOOLEAN,
            is_drink_item BOOLEAN,
            product_price DECIMAL(10, 2)
        )
    """)
    cur.execute("DELETE FROM products")
    for row_id, r in enumerate(products_data, start=1):
        cur.execute(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                row_id,
                r["product_name"],
                r["product_type"],
                r["product_description"],
                r["is_food_item"],
                r["is_drink_item"],
                r["product_price"],
            ],
        )
    cur.execute("""
        CREATE OR REPLACE SEMANTIC VIEW products AS
        TABLES (
            p AS products PRIMARY KEY (id)
        )
        FACTS (
            p.product_price AS p.product_price
        )
        DIMENSIONS (
            p.product_name AS p.product_name,
            p.product_type AS p.product_type,
            p.product_description AS p.product_description,
            p.is_food_item AS p.is_food_item,
            p.is_drink_item AS p.is_drink_item
        )
    """)
    cur.close()
    dbapi_conn.commit()


# ---------------------------------------------------------------------------
# DuckDB pool fixtures
# ---------------------------------------------------------------------------


def _make_pool(*setups: Any) -> Iterator[Any]:
    """
    Build an in-memory DuckDB engine, attach setup listeners, and register it.

    ``create_engine`` builds the DuckDB Engine (and already wires the
    ``semantic_views`` extension load on the pool ``connect`` event). Each
    ``setups`` listener is attached to the owned pool so it also runs on every
    new physical connection, then the engine is registered as ``"default"``.
    Yields the owned pool; unregisters and disposes the engine on teardown.
    """
    from adbc_poolhouse import DuckDBConfig
    from sqlalchemy import event

    from semolina.config import create_engine

    engine = create_engine(DuckDBConfig(database=":memory:", pool_size=1))
    for setup in setups:
        event.listen(engine._pool, "connect", setup)

    semolina.register("default", engine)
    yield engine._pool
    semolina.unregister("default")
    engine.dispose()


@pytest.fixture
def orders_pool() -> Iterator[Any]:
    """In-memory DuckDB pool with the ``orders`` semantic view registered as default."""
    pytest.importorskip("adbc_driver_duckdb")
    yield from _make_pool(_setup_orders)


@pytest.fixture
def customers_pool() -> Iterator[Any]:
    """In-memory DuckDB pool with the ``customers`` semantic view registered as default."""
    pytest.importorskip("adbc_driver_duckdb")
    yield from _make_pool(_setup_customers)


@pytest.fixture
def products_pool() -> Iterator[Any]:
    """In-memory DuckDB pool with the ``products`` semantic view registered as default."""
    pytest.importorskip("adbc_driver_duckdb")
    yield from _make_pool(_setup_products)


@pytest.fixture
def jaffle_pool() -> Iterator[Any]:
    """
    In-memory DuckDB pool with all three jaffle-shop semantic views.

    Sets up ``orders``, ``customers``, and ``products`` on each new physical
    connection so tests can query across multiple views.
    """
    pytest.importorskip("adbc_driver_duckdb")
    yield from _make_pool(_setup_orders, _setup_customers, _setup_products)


@pytest.fixture
def snowflake_connection() -> Iterator[None]:
    """
    Register a Snowflake engine as default for live warehouse tests.

    Loads connection config via :func:`semolina.config.warehouse_config`
    (``[connections.snowflake]`` in ``.semolina.toml`` with ``SNOWFLAKE_*`` env
    filling gaps). Tests are skipped when the config is unavailable, so the
    suite passes credential-free in CI. A live Snowflake ADBC engine is built
    via ``create_engine`` and registered as ``"default"``.
    """
    pytest.importorskip("adbc_driver_snowflake")
    from pydantic import ValidationError

    from semolina.config import create_engine, warehouse_config

    try:
        config = warehouse_config("snowflake")
    except ValidationError as e:
        pytest.skip(f"Snowflake connection config not available: {e}")

    engine = create_engine(config)
    semolina.register("default", engine)
    try:
        yield
    finally:
        semolina.unregister("default")
        engine.dispose()
