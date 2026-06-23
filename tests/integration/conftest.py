"""
Fixtures for warehouse integration tests (pytest-adbc-replay).

Two backends (Snowflake, Databricks) are exercised through one parametrized
fixture. Both modes build a *real* adbc-poolhouse pool; the pytest-adbc-replay
plugin decides whether each query hits a live warehouse or a recorded cassette:

- **Replay (default, incl. CI):** the plugin (configured in pyproject.toml via
  ``adbc_auto_patch``) intercepts the ADBC ``connect()`` and serves recorded
  results from ``tests/integration/cassettes/``. The pool is built with
  placeholder config — no credentials, no warehouse, no network. Every test
  here carries ``@pytest.mark.adbc_cassette`` (applied module-wide) so the
  plugin wraps its connections.
- **Record (``pytest --adbc-record=once tests/integration`` + creds):** a temp
  schema with a real ``sales_data`` table and ``sales_view`` semantic / metric
  view is created via the native connector, then a real ADBC pool queries it and
  the plugin records the generated SQL + Arrow results into cassettes. Commit the
  cassettes; CI then replays them with no credentials.

Recording credentials come from the same source as the rest of Semolina: the
``[connections.<backend>]`` section of ``.semolina.toml`` (see
:func:`semolina.config.pool_from_config`), with ``SNOWFLAKE_*`` / ``DATABRICKS_*``
environment variables filling any gaps. The adbc-poolhouse config is the single
source of truth — it supports password and key-pair auth — and the native
connector used for DDL setup derives its arguments from it.

The synthetic dataset (recorded against, and asserted on in test_queries.py):

    revenue  cost  country  region
    1000     100   US       West
    2000     200   CA       East
    500      50    US       East
    1500     150   MX       South
    800      80    CA       West
"""

from __future__ import annotations

import uuid
import warnings
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import SecretStr, ValidationError

if TYPE_CHECKING:
    from collections.abc import Generator


def _is_recording(request: pytest.FixtureRequest) -> bool:
    """
    Return True when pytest-adbc-replay is in a recording mode.

    Recording happens when ``--adbc-record`` is anything other than ``none``
    (the default). In recording mode the fixtures provision a live warehouse;
    otherwise they build a placeholder pool whose connections the plugin
    intercepts and replays from cassettes.
    """
    # --adbc-record is always registered by the pytest-adbc-replay plugin.
    mode = request.config.getoption("--adbc-record")
    return mode not in (None, "none")


@pytest.fixture
def snowflake_engine(
    request: pytest.FixtureRequest,
) -> Generator[Any, None, None]:
    """
    Provide a Snowflake-dialect pool for integration tests.

    Replay (default): a poolhouse ``SnowflakeConfig`` pool built with placeholder
    credentials. The plugin intercepts ``adbc_driver_snowflake.dbapi.connect``
    and replays recorded cassettes, so no real account is contacted.

    Record (``--adbc-record`` + creds): the ``[connections.snowflake]`` config
    (plus ``SNOWFLAKE_*`` env) drives a temp schema with a real ``sales_data``
    table and ``sales_view`` semantic view, then a real pool pointed at that
    schema is registered. Skips if the connection config is unavailable.

    Yields the registered pool.
    """
    from adbc_poolhouse import SnowflakeConfig, close_pool

    import semolina
    from semolina.config import create_engine

    if _is_recording(request):
        import snowflake.connector  # type: ignore[import-not-found]

        from semolina.config import snowflake_connect_kwargs, warehouse_config

        try:
            base_config = warehouse_config("snowflake")
        except ValidationError as e:
            pytest.skip(
                "Snowflake connection config not available for recording "
                f"([connections.snowflake] in .semolina.toml or SNOWFLAKE_* env): {e}"
            )

        schema_name = f"TEST_{uuid.uuid4().hex[:8].upper()}"
        native_kwargs = snowflake_connect_kwargs(base_config)

        # Setup: create temp schema, staging table, and semantic view (DDL via
        # the native connector; the ADBC pool below is used only for queries, so
        # only the query SQL — not this DDL — is recorded). All identifiers are
        # created *unquoted* — the realistic Snowflake setup — so they are stored
        # UPPERCASE and resolve against the dialect's folded, double-quoted
        # queries (FROM "SALES_VIEW", AGG("REVENUE"), "COUNTRY"). The view name is
        # unqualified in queries (schema set on the connection), keeping recorded
        # SQL stable across record runs.
        try:
            with (
                snowflake.connector.connect(**native_kwargs) as conn,  # type: ignore[attr-defined]
                conn.cursor() as cur,
            ):
                cur.execute(f"CREATE SCHEMA {schema_name}")  # type: ignore[attr-defined]
                cur.execute(f"USE SCHEMA {schema_name}")  # type: ignore[attr-defined]
                cur.execute(  # type: ignore[attr-defined]
                    "CREATE TABLE sales_data"
                    " (revenue NUMBER, cost NUMBER, country VARCHAR, region VARCHAR)"
                )
                cur.execute(  # type: ignore[attr-defined]
                    "INSERT INTO sales_data VALUES"
                    " (1000, 100, 'US', 'West'), (2000, 200, 'CA', 'East'),"
                    " (500, 50, 'US', 'East'), (1500, 150, 'MX', 'South'),"
                    " (800, 80, 'CA', 'West')"
                )
                cur.execute(  # type: ignore[attr-defined]
                    "CREATE SEMANTIC VIEW sales_view"
                    " TABLES (sales_data)"
                    " DIMENSIONS"
                    " (sales_data.country AS country,"
                    " sales_data.region AS region)"
                    " METRICS"
                    " (sales_data.revenue AS SUM(revenue),"
                    " sales_data.cost AS SUM(cost))"
                )
        except Exception as e:
            pytest.fail(f"Failed to create Snowflake integration test schema/objects: {e}")

        warnings.warn(f"[integration] Snowflake temp schema: {schema_name}", stacklevel=2)

        engine = create_engine(base_config.model_copy(update={"schema_": schema_name}))
        semolina.register("test", engine)
        try:
            yield engine
        finally:
            semolina.unregister("test")
            close_pool(engine._pool)
            try:
                with (
                    snowflake.connector.connect(**native_kwargs) as conn,  # type: ignore[attr-defined]
                    conn.cursor() as cur,
                ):
                    cur.execute(  # type: ignore[attr-defined]
                        f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"
                    )
            except Exception as e:
                print(f"Warning: Failed to drop Snowflake temp schema {schema_name}: {e}")
    else:
        # Replay: placeholder config — connections are intercepted by the plugin.
        config = SnowflakeConfig(
            account="replay",
            user="replay",
            password=SecretStr("replay"),
            warehouse="replay",
            database="replay",
            role="replay",
            schema="REPLAY",  # type: ignore[call-arg]  # populated via field alias
        )
        engine = create_engine(config)
        semolina.register("test", engine)
        try:
            yield engine
        finally:
            semolina.unregister("test")
            close_pool(engine._pool)


@pytest.fixture
def databricks_engine(
    request: pytest.FixtureRequest,
) -> Generator[Any, None, None]:
    """
    Provide a Databricks-dialect pool for integration tests.

    Replay (default): a poolhouse ``DatabricksConfig`` pool built with
    placeholder credentials. adbc-poolhouse routes Databricks through
    ``adbc_driver_manager.dbapi``, which the plugin intercepts and replays from
    cassettes.

    Record (``--adbc-record`` + creds): the ``[connections.databricks]`` config
    (plus ``DATABRICKS_*`` env) drives a temp schema with a real ``sales_data``
    table and ``sales_view`` metric view (YAML), then a real pool pointed at that
    schema is registered. Skips if the connection config is unavailable.

    Yields the registered pool.
    """
    from adbc_poolhouse import DatabricksConfig, close_pool

    import semolina
    from semolina.config import create_engine

    if _is_recording(request):
        import databricks.sql  # type: ignore[import-not-found]

        from semolina.config import databricks_connect_kwargs, warehouse_config

        try:
            base_config = warehouse_config("databricks")
        except ValidationError as e:
            pytest.skip(
                "Databricks connection config not available for recording "
                f"([connections.databricks] in .semolina.toml or DATABRICKS_* env): {e}"
            )

        schema_name = f"TEST_{uuid.uuid4().hex[:8].upper()}"
        catalog = base_config.catalog
        native_kwargs = databricks_connect_kwargs(base_config)

        try:
            with (
                databricks.sql.connect(**native_kwargs) as conn,  # type: ignore[attr-defined]
                conn.cursor() as cur,  # type: ignore[attr-defined]
            ):
                cur.execute(f"CREATE SCHEMA {catalog}.{schema_name}")  # type: ignore[attr-defined]
                cur.execute(  # type: ignore[attr-defined]
                    f"CREATE TABLE {catalog}.{schema_name}.sales_data"
                    " (revenue BIGINT, cost BIGINT, country STRING, region STRING)"
                )
                cur.execute(  # type: ignore[attr-defined]
                    f"INSERT INTO {catalog}.{schema_name}.sales_data VALUES"
                    " (1000, 100, 'US', 'West'), (2000, 200, 'CA', 'East'),"
                    " (500, 50, 'US', 'East'), (1500, 150, 'MX', 'South'),"
                    " (800, 80, 'CA', 'West')"
                )
                cur.execute(  # type: ignore[attr-defined]
                    f"CREATE OR REPLACE VIEW {catalog}.{schema_name}.sales_view"
                    " WITH METRICS LANGUAGE YAML AS $$\n"
                    "version: 1.1\n"
                    f"source: {catalog}.{schema_name}.sales_data\n"
                    "dimensions:\n"
                    "  - name: country\n"
                    "    expr: country\n"
                    "  - name: region\n"
                    "    expr: region\n"
                    "measures:\n"
                    "  - name: revenue\n"
                    "    expr: SUM(revenue)\n"
                    "  - name: cost\n"
                    "    expr: SUM(cost)\n"
                    "$$"
                )
        except Exception as e:
            pytest.fail(f"Failed to create Databricks integration test schema/objects: {e}")

        warnings.warn(
            f"[integration] Databricks temp schema: {catalog}.{schema_name}", stacklevel=2
        )

        engine = create_engine(base_config.model_copy(update={"schema_": schema_name}))
        semolina.register("test", engine)
        try:
            yield engine
        finally:
            semolina.unregister("test")
            close_pool(engine._pool)
            try:
                with (
                    databricks.sql.connect(**native_kwargs) as conn,  # type: ignore[attr-defined]
                    conn.cursor() as cur,  # type: ignore[attr-defined]
                ):
                    cur.execute(  # type: ignore[attr-defined]
                        f"DROP SCHEMA IF EXISTS {catalog}.{schema_name} CASCADE"
                    )
            except Exception as e:
                print(
                    f"Warning: Failed to drop Databricks temp schema {catalog}.{schema_name}: {e}"
                )
    else:
        # Replay: placeholder config — connections are intercepted by the plugin.
        config = DatabricksConfig(
            host="replay.cloud.databricks.com",
            http_path="/sql/1.0/warehouses/replay",
            token=SecretStr("replay"),
            catalog="replay",
            schema="REPLAY",  # type: ignore[call-arg]  # populated via field alias
        )
        engine = create_engine(config)
        semolina.register("test", engine)
        try:
            yield engine
        finally:
            semolina.unregister("test")
            close_pool(engine._pool)


@pytest.fixture(params=["snowflake_engine", "databricks_engine"])
def backend_engine(
    request: pytest.FixtureRequest,
) -> Generator[Any, None, None]:
    """
    Run integration tests against both Snowflake and Databricks.

    pytest creates ``[snowflake_engine]`` and ``[databricks_engine]`` variants
    for each test. Cassettes are stored per test+backend (the cassette name is
    derived from the node id, which includes the parameter), so the two backends
    never share a recording.

    Yields the registered pool.
    """
    yield request.getfixturevalue(request.param)
