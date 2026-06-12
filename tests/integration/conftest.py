"""
Fixtures for warehouse integration tests.

Two backends (Snowflake, Databricks) are exercised through one parametrized
fixture. Each runs in one of two modes:

- **Replay (default, CI):** a test-local fake DBAPI pool (``_ReplayPool``)
  returns the raw ``TEST_DATA`` rows for every query. No credentials, no
  warehouse, no DuckDB. The mock does not aggregate or filter, so replay
  snapshots are smoke-level — they prove the query path executes and the
  result-to-``Row`` plumbing works, not that the warehouse SQL is correct.
- **Record (``--warehouse-record`` + creds):** a real ADBC pool built via
  adbc-poolhouse, pointed at a temp schema containing a real semantic /
  metric view. This is the path that validates generated SQL against a live
  warehouse and regenerates the snapshots with real aggregated results.

``--warehouse-record`` is decoupled from syrupy's ``--snapshot-update`` on
purpose: ``--snapshot-update`` regenerates the *mock* snapshots in CI (no
creds), while ``--warehouse-record`` is what opts into the real warehouse.
"""

from __future__ import annotations

import uuid
import warnings
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from syrupy.assertion import SnapshotAssertion

from semolina.testing.credentials import (
    CredentialError,
    DatabricksCredentials,
    SnowflakeCredentials,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Register the ``--warehouse-record`` flag.

    When passed (and credentials load), the Snowflake / Databricks fixtures
    run in record mode against a real warehouse. Without it, they run in
    replay mode against the fake DBAPI pool. This is deliberately separate
    from syrupy's ``--snapshot-update`` so the mock snapshots can be
    regenerated in CI without any warehouse credentials.
    """
    parser.addoption(
        "--warehouse-record",
        action="store_true",
        default=False,
        help="Run integration tests against real Snowflake/Databricks warehouses "
        "(requires credentials). Without this flag, tests use a fake DBAPI pool (replay).",
    )


@pytest.fixture(scope="session")
def snowflake_credentials() -> SnowflakeCredentials:
    """
    Load Snowflake credentials, skip tests if unavailable.

    Attempts to load credentials from environment variables, .env file, or config files.
    If credentials are not available, skips tests that depend on this fixture.

    Returns:
        SnowflakeCredentials instance cached for the test session

    Raises:
        pytest.skip: When credentials cannot be loaded from any source
    """
    try:
        return SnowflakeCredentials.load()
    except CredentialError as e:
        pytest.skip(f"Snowflake credentials not available: {e}")


@pytest.fixture(scope="session")
def databricks_credentials() -> DatabricksCredentials:
    """
    Load Databricks credentials, skip tests if unavailable.

    Attempts to load credentials from environment variables, .env file, or config files.
    If credentials are not available, skips tests that depend on this fixture.

    Returns:
        DatabricksCredentials instance cached for the test session

    Raises:
        pytest.skip: When credentials cannot be loaded from any source
    """
    try:
        return DatabricksCredentials.load()
    except CredentialError as e:
        pytest.skip(f"Databricks credentials not available: {e}")


# ---------------------------------------------------------------------------
# Integration test data and syrupy configuration
# ---------------------------------------------------------------------------

# Synthetic dataset loaded into the warehouse view during --warehouse-record recording,
# and returned verbatim by the replay mock pool.
# Must match the rows inserted into the temp table in snowflake_engine / databricks_engine.
# Integer values avoid Decimal precision drift across warehouse backends.
TEST_DATA: list[dict[str, Any]] = [
    {"revenue": 1000, "cost": 100, "country": "US", "region": "West"},
    {"revenue": 2000, "cost": 200, "country": "CA", "region": "East"},
    {"revenue": 500, "cost": 50, "country": "US", "region": "East"},
    {"revenue": 1500, "cost": 150, "country": "MX", "region": "South"},
    {"revenue": 800, "cost": 80, "country": "CA", "region": "West"},
]

# Column order the replay mock projects every result row into. The fake cursor
# does not inspect the SQL — it always returns these four columns, so replay
# snapshots reflect the full TEST_DATA shape regardless of the query.
TEST_COLUMNS: list[str] = ["revenue", "cost", "country", "region"]


# ---------------------------------------------------------------------------
# Replay mock: a test-local fake DBAPI 2.0 pool
# ---------------------------------------------------------------------------
#
# Resurrected from the (now-deleted) _LegacyResultCursor / _NoOpConn / _NoOpPool
# shapes that backed the old engine-registry execute path. SemolinaCursor only
# needs: cursor.description (7-tuples), fetchall/fetchone/fetchmany (tuples),
# rowcount, close(); conn.cursor()/close(); pool.connect()/close().


class _ReplayCursor:
    """Fake DBAPI cursor returning fixed rows, projected into ``columns`` order."""

    def __init__(self, rows: list[dict[str, Any]], columns: list[str]) -> None:
        self._columns = columns
        self._tuples: list[tuple[Any, ...]] = [tuple(r[c] for c in columns) for r in rows]
        self._pos = 0
        # 7-tuple per DBAPI 2.0; only element [0] (the column name) is consumed.
        self.description: list[tuple[Any, ...]] | None = [
            (c, None, None, None, None, None, None) for c in columns
        ] or None
        self.rowcount: int = len(self._tuples)

    def execute(self, sql: str, params: Any = None) -> None:  # noqa: ARG002
        """No-op: the mock ignores the SQL and always returns the fixed rows."""

    def fetchall(self) -> list[tuple[Any, ...]]:
        """Fetch all remaining rows as tuples."""
        result = self._tuples[self._pos :]
        self._pos = len(self._tuples)
        return result

    def fetchone(self) -> tuple[Any, ...] | None:
        """Fetch next row as a tuple, or None if exhausted."""
        if self._pos >= len(self._tuples):
            return None
        row = self._tuples[self._pos]
        self._pos += 1
        return row

    def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        """Fetch up to ``size`` rows as tuples."""
        result = self._tuples[self._pos : self._pos + size]
        self._pos += len(result)
        return result

    def close(self) -> None:
        """No-op close."""


class _ReplayConn:
    """Fake DBAPI connection handing out fresh ``_ReplayCursor`` instances."""

    def __init__(self, rows: list[dict[str, Any]], columns: list[str]) -> None:
        self._rows = rows
        self._columns = columns

    def cursor(self) -> _ReplayCursor:
        """Return a fresh replay cursor."""
        return _ReplayCursor(self._rows, self._columns)

    def close(self) -> None:
        """No-op close."""


class _ReplayPool:
    """
    Fake DBAPI pool standing in for a real ADBC pool in replay mode.

    Carries ``_is_replay_mock = True`` so tests can detect replay (real ADBC
    pools do not have this attribute).
    """

    _is_replay_mock = True

    def __init__(self, rows: list[dict[str, Any]], columns: list[str]) -> None:
        self._rows = rows
        self._columns = columns

    def connect(self) -> _ReplayConn:
        """Return a fake connection."""
        return _ReplayConn(self._rows, self._columns)

    def close(self) -> None:
        """No-op close."""


def _redact_credential(_data: object, _matched: object) -> str:
    """Replacer for credential scrubbing in snapshot assertions."""
    return "[REDACTED]"


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """
    Override syrupy snapshot fixture with defensive credential scrubbing.

    Applies path_value matchers to redact any string values at paths whose
    name contains 'password', 'token', or 'secret'. For warehouse query results
    (business data rows), this is a belt-and-suspenders measure -- credentials
    do not appear in query result columns by design.
    """
    from syrupy.matchers import path_value

    return snapshot.with_defaults(
        matcher=path_value(
            mapping={
                ".*password.*": r".+",
                ".*token.*": r".+",
                ".*secret.*": r".+",
            },
            replacer=_redact_credential,
            types=(str,),
            regex=True,
        )
    )


@pytest.fixture
def snowflake_engine(
    request: pytest.FixtureRequest,
) -> Generator[Any, None, None]:
    """
    Provide a Snowflake-dialect pool for integration tests.

    Replay mode (default, incl. CI): a fake DBAPI pool (``_ReplayPool``)
    seeded with ``TEST_DATA``, registered with ``dialect="snowflake"``. No
    credentials or warehouse needed.

    Record mode (``--warehouse-record`` + creds): a temp schema with a real
    ``sales_data`` table and ``sales_view`` semantic view is created via the
    Snowflake connector, then a real ADBC pool (adbc-poolhouse
    ``SnowflakeConfig``) pointed at that schema is registered with
    ``dialect="snowflake"``. Skips if credentials are unavailable.

    Yields the registered pool.
    """
    import semolina

    is_recording: bool = bool(request.config.getoption("--warehouse-record", default=False))

    pool: Any

    if is_recording:
        # NOTE: This branch is structurally correct but UNTESTED here — it
        # requires live Snowflake credentials, which are not available in this
        # environment. It follows pool_from_config / the jaffle-shop
        # snowflake_connection fixture pattern.
        import snowflake.connector  # type: ignore[import-not-found]
        from adbc_poolhouse import SnowflakeConfig, close_pool, create_pool

        from semolina.testing.credentials import CredentialError as _CredentialError
        from semolina.testing.credentials import SnowflakeCredentials as _SnowflakeCredentials

        try:
            creds = _SnowflakeCredentials.load()
        except _CredentialError as e:
            pytest.skip(f"Snowflake credentials not available for recording: {e}")

        schema_name = f"TEST_{uuid.uuid4().hex[:8].upper()}"

        # Setup: create temp schema, staging table, and semantic view (DDL via
        # the native connector; the ADBC pool below is used only for queries).
        try:
            with (
                snowflake.connector.connect(  # type: ignore[attr-defined]
                    account=creds.account,
                    user=creds.user,
                    password=creds.password.get_secret_value(),
                    warehouse=creds.warehouse,
                    database=creds.database,
                    role=creds.role,
                ) as conn,
                conn.cursor() as cur,
            ):
                cur.execute(f"CREATE SCHEMA {schema_name}")  # type: ignore[attr-defined]
                cur.execute(f"USE SCHEMA {schema_name}")  # type: ignore[attr-defined]
                # Use quoted lowercase identifiers so the dialect's double-quoted
                # queries (e.g. FROM "sales_view") resolve correctly.
                cur.execute(  # type: ignore[attr-defined]
                    'CREATE TABLE "sales_data"'
                    ' ("revenue" NUMBER, "cost" NUMBER, "country" VARCHAR, "region" VARCHAR)'
                )
                cur.execute(  # type: ignore[attr-defined]
                    'INSERT INTO "sales_data" VALUES'
                    " (1000, 100, 'US', 'West'), (2000, 200, 'CA', 'East'),"
                    " (500, 50, 'US', 'East'), (1500, 150, 'MX', 'South'),"
                    " (800, 80, 'CA', 'West')"
                )
                cur.execute(  # type: ignore[attr-defined]
                    'CREATE SEMANTIC VIEW "sales_view"'
                    ' TABLES ("sales_data")'
                    " DIMENSIONS"
                    ' ("sales_data"."country" AS "country",'
                    ' "sales_data"."region" AS "region")'
                    " METRICS"
                    ' ("sales_data"."revenue" AS SUM("revenue"),'
                    ' "sales_data"."cost" AS SUM("cost"))'
                )
        except Exception as e:
            pytest.fail(f"Failed to create Snowflake integration test schema/objects: {e}")

        warnings.warn(f"[integration] Snowflake temp schema: {schema_name}", stacklevel=2)

        # Build a real ADBC pool pointed at the temp schema. Pass the password
        # as SecretStr (SnowflakeConfig.password is SecretStr) and the schema
        # via the ``schema`` alias (the model field is ``schema_``).
        config = SnowflakeConfig(
            account=creds.account,
            user=creds.user,
            password=creds.password,
            warehouse=creds.warehouse,
            database=creds.database,
            role=creds.role,
            schema=schema_name,  # type: ignore[call-arg]  # populated via field alias
        )
        pool = create_pool(config)
        semolina.register("test", pool, dialect="snowflake")
        try:
            yield pool
        finally:
            semolina.unregister("test")
            close_pool(pool)
            # Teardown: drop temp schema (CASCADE removes all objects within it).
            try:
                with (
                    snowflake.connector.connect(  # type: ignore[attr-defined]
                        account=creds.account,
                        user=creds.user,
                        password=creds.password.get_secret_value(),
                        warehouse=creds.warehouse,
                        database=creds.database,
                        role=creds.role,
                    ) as conn,
                    conn.cursor() as cur,
                ):
                    cur.execute(  # type: ignore[attr-defined]
                        f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"
                    )
            except Exception as e:
                print(f"Warning: Failed to drop Snowflake temp schema {schema_name}: {e}")
    else:
        pool = _ReplayPool(TEST_DATA, TEST_COLUMNS)
        semolina.register("test", pool, dialect="snowflake")
        try:
            yield pool
        finally:
            semolina.unregister("test")


@pytest.fixture
def databricks_engine(
    request: pytest.FixtureRequest,
) -> Generator[Any, None, None]:
    """
    Provide a Databricks-dialect pool for integration tests.

    Replay mode (default, incl. CI): a fake DBAPI pool (``_ReplayPool``)
    seeded with ``TEST_DATA``, registered with ``dialect="databricks"``. No
    credentials or warehouse needed.

    Record mode (``--warehouse-record`` + creds): a temp schema with a real
    ``sales_data`` table and ``sales_view`` metric view (YAML) is created via
    databricks-sql, then a real ADBC pool (adbc-poolhouse ``DatabricksConfig``)
    pointed at that schema is registered with ``dialect="databricks"``. Skips
    if credentials are unavailable.

    Yields the registered pool.
    """
    import semolina

    is_recording: bool = bool(request.config.getoption("--warehouse-record", default=False))

    pool: Any

    if is_recording:
        # NOTE: This branch is structurally correct but UNTESTED here — it
        # requires live Databricks credentials, which are not available in
        # this environment.
        import databricks.sql  # type: ignore[import-not-found]
        from adbc_poolhouse import DatabricksConfig, close_pool, create_pool

        from semolina.testing.credentials import CredentialError as _CredentialError
        from semolina.testing.credentials import DatabricksCredentials as _DatabricksCredentials

        try:
            creds = _DatabricksCredentials.load()
        except _CredentialError as e:
            pytest.skip(f"Databricks credentials not available for recording: {e}")

        schema_name = f"TEST_{uuid.uuid4().hex[:8].upper()}"
        catalog = creds.catalog

        # Setup: create temp schema, staging table, and metric view (DDL via
        # databricks-sql; the ADBC pool below is used only for queries).
        try:
            with (
                databricks.sql.connect(  # type: ignore[attr-defined]
                    server_hostname=creds.server_hostname,
                    http_path=creds.http_path,
                    access_token=creds.access_token.get_secret_value(),
                    catalog=catalog,
                ) as conn,
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

        # Build a real ADBC pool pointed at the temp schema. The credentials'
        # ``access_token`` (SecretStr) maps to DatabricksConfig.token (SecretStr);
        # the schema is passed via the ``schema`` alias (field is ``schema_``).
        config = DatabricksConfig(
            host=creds.server_hostname,
            http_path=creds.http_path,
            token=creds.access_token,
            catalog=catalog,
            schema=schema_name,  # type: ignore[call-arg]  # populated via field alias
        )
        pool = create_pool(config)
        semolina.register("test", pool, dialect="databricks")
        try:
            yield pool
        finally:
            semolina.unregister("test")
            close_pool(pool)
            # Teardown: drop temp schema (CASCADE removes all objects within it).
            try:
                with (
                    databricks.sql.connect(  # type: ignore[attr-defined]
                        server_hostname=creds.server_hostname,
                        http_path=creds.http_path,
                        access_token=creds.access_token.get_secret_value(),
                        catalog=catalog,
                    ) as conn,
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
        pool = _ReplayPool(TEST_DATA, TEST_COLUMNS)
        semolina.register("test", pool, dialect="databricks")
        try:
            yield pool
        finally:
            semolina.unregister("test")


@pytest.fixture(params=["snowflake_engine", "databricks_engine"])
def backend_engine(
    request: pytest.FixtureRequest,
) -> Generator[Any, None, None]:
    """
    Parametrized fixture that runs integration tests against both Snowflake and Databricks.

    pytest automatically creates [snowflake_engine] and [databricks_engine] variants
    for each test that uses this fixture. Snapshot entries in .ambr files are tagged
    with the parameter suffix so both variants are stored separately.

    Record (``--warehouse-record`` + creds): real ADBC pool against a live warehouse.
    Replay (default, CI): fake DBAPI pool (``_ReplayPool``), no credentials needed.

    Yields the registered pool.
    """
    yield request.getfixturevalue(request.param)
