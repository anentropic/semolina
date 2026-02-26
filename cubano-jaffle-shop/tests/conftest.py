"""
Shared pytest fixtures for cubano-jaffle-shop integration tests.

Provides mock engine instances pre-loaded with jaffle-shop fixture data
for testing query builder logic without warehouse connections. Engines are
registered with cubano so tests use Model.query().execute() directly.
"""

from collections.abc import Iterator

import pytest
from fixtures.mock_data import customers_data, orders_data, products_data

import cubano
from cubano.engines.mock import MockEngine


@pytest.fixture
def orders_engine() -> Iterator[None]:
    """
    Register MockEngine with orders fixture data as default engine.

    Registers the engine under 'default' so tests can call
    Orders.query().execute() without specifying an engine name.
    Engine is unregistered after each test.
    """
    engine = MockEngine()
    engine.load("orders", orders_data)
    cubano.register("default", engine)
    yield
    cubano.unregister("default")


@pytest.fixture
def customers_engine() -> Iterator[None]:
    """
    Register MockEngine with customers fixture data as default engine.

    Registers the engine under 'default' so tests can call
    Customers.query().execute() without specifying an engine name.
    Engine is unregistered after each test.
    """
    engine = MockEngine()
    engine.load("customers", customers_data)
    cubano.register("default", engine)
    yield
    cubano.unregister("default")


@pytest.fixture
def products_engine() -> Iterator[None]:
    """
    Register MockEngine with products fixture data as default engine.

    Registers the engine under 'default' so tests can call
    Products.query().execute() without specifying an engine name.
    Engine is unregistered after each test.
    """
    engine = MockEngine()
    engine.load("products", products_data)
    cubano.register("default", engine)
    yield
    cubano.unregister("default")


@pytest.fixture
def jaffle_engine() -> Iterator[None]:
    """
    Register MockEngine with all jaffle-shop fixture data as default engine.

    Provides comprehensive fixture for tests that query across multiple
    views (orders, customers, products). Registers as 'default' and
    unregisters after each test.
    """
    engine = MockEngine()
    engine.load("orders", orders_data)
    engine.load("customers", customers_data)
    engine.load("products", products_data)
    cubano.register("default", engine)
    yield
    cubano.unregister("default")


@pytest.fixture
def snowflake_connection() -> Iterator[None]:
    """
    Register SnowflakeEngine as default engine for warehouse tests.

    Loads credentials via SnowflakeCredentials.load() which respects the full
    CUBANO_ENV_FILE priority chain (env vars > .env > .cubano.toml). Registers
    engine as 'default' and unregisters after each test. Tests are skipped if
    credentials are absent.
    """
    from cubano.engines.snowflake import SnowflakeEngine
    from cubano.testing.credentials import CredentialError, SnowflakeCredentials

    try:
        creds = SnowflakeCredentials.load()
    except CredentialError as e:
        pytest.skip(f"Snowflake credentials not available: {e}")

    engine = SnowflakeEngine(
        account=creds.account,
        user=creds.user,
        password=creds.password.get_secret_value(),
        warehouse=creds.warehouse,
        database=creds.database,
        role=creds.role,
    )
    cubano.register("default", engine)
    yield
    cubano.unregister("default")
