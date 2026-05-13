"""
Fixtures for warehouse integration tests.

Provides engine instances for Snowflake and Databricks, with credential loading,
temp schema setup/teardown, and syrupy snapshot configuration.
"""

from __future__ import annotations

import uuid
import warnings
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from syrupy.assertion import SnapshotAssertion

    from semolina.engines.databricks import DatabricksEngine
    from semolina.engines.snowflake import SnowflakeEngine

from semolina.engines.mock import MockEngine
from semolina.testing.credentials import (
    CredentialError,
    DatabricksCredentials,
    SnowflakeCredentials,
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

# Synthetic dataset loaded into the warehouse view during --snapshot-update recording.
# Must match the rows inserted into the temp table in snowflake_engine / databricks_engine.
# Integer values avoid Decimal precision drift across warehouse backends.
TEST_DATA: list[dict[str, Any]] = [
    {"revenue": 1000, "cost": 100, "country": "US", "region": "West"},
    {"revenue": 2000, "cost": 200, "country": "CA", "region": "East"},
    {"revenue": 500, "cost": 50, "country": "US", "region": "East"},
    {"revenue": 1500, "cost": 150, "country": "MX", "region": "South"},
    {"revenue": 800, "cost": 80, "country": "CA", "region": "West"},
]


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
) -> Generator[MockEngine | SnowflakeEngine, None, None]:
    """
    Provide a Snowflake engine for integration tests.

    Replay mode (default, CI): MockEngine loaded with TEST_DATA.
    Record mode (--snapshot-update): SnowflakeEngine, requires SNOWFLAKE_* env vars.
    Creates a temp schema with sales_data table and sales_view before yielding,
    drops the schema in teardown. Skips if credentials are unavailable in record mode.
    """
    import semolina

    is_recording: bool = bool(request.config.getoption("--snapshot-update", default=False))

    engine: MockEngine | SnowflakeEngine

    if is_recording:
        import snowflake.connector  # type: ignore[import-not-found]

        from semolina.engines.snowflake import SnowflakeEngine as _SnowflakeEngine
        from semolina.testing.credentials import CredentialError as _CredentialError
        from semolina.testing.credentials import SnowflakeCredentials as _SnowflakeCredentials

        try:
            creds = _SnowflakeCredentials.load()
        except _CredentialError as e:
            pytest.skip(f"Snowflake credentials not available for recording: {e}")

        schema_name = f"TEST_{uuid.uuid4().hex[:8].upper()}"

        engine = _SnowflakeEngine(
            account=creds.account,
            user=creds.user,
            password=creds.password.get_secret_value(),
            warehouse=creds.warehouse,
            database=creds.database,
            role=creds.role,
            schema=schema_name,
        )

        # Setup: create temp schema, staging table, and semantic view
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
                # Use quoted lowercase identifiers so the engine's double-quoted
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
    else:
        schema_name = ""
        engine = MockEngine()
        engine.load("sales_view", TEST_DATA)

    semolina.register("test", engine)
    yield engine
    semolina.unregister("test")

    # Teardown: drop temp schema (CASCADE removes all objects within it)
    if is_recording:
        import snowflake.connector  # type: ignore[import-not-found]

        try:
            with (
                snowflake.connector.connect(**engine._connection_params) as conn,  # type: ignore[attr-defined]
                conn.cursor() as cur,
            ):
                cur.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")  # type: ignore[attr-defined]
        except Exception as e:
            print(f"Warning: Failed to drop Snowflake temp schema {schema_name}: {e}")


@pytest.fixture
def databricks_engine(
    request: pytest.FixtureRequest,
) -> Generator[MockEngine | DatabricksEngine, None, None]:
    """
    Provide a Databricks engine for integration tests.

    Replay mode (default, CI): MockEngine loaded with TEST_DATA.
    Record mode (--snapshot-update): DatabricksEngine, requires DATABRICKS_* env vars.
    Creates a temp schema with sales_data table and sales_view before yielding,
    drops the schema in teardown. Skips if credentials are unavailable in record mode.
    """
    import semolina

    is_recording: bool = bool(request.config.getoption("--snapshot-update", default=False))

    engine: MockEngine | DatabricksEngine

    if is_recording:
        import databricks.sql  # type: ignore[import-not-found]

        from semolina.engines.databricks import DatabricksEngine as _DatabricksEngine
        from semolina.testing.credentials import CredentialError as _CredentialError
        from semolina.testing.credentials import DatabricksCredentials as _DatabricksCredentials

        try:
            creds = _DatabricksCredentials.load()
        except _CredentialError as e:
            pytest.skip(f"Databricks credentials not available for recording: {e}")

        schema_name = f"TEST_{uuid.uuid4().hex[:8].upper()}"
        catalog = creds.catalog

        engine = _DatabricksEngine(
            server_hostname=creds.server_hostname,
            http_path=creds.http_path,
            access_token=creds.access_token.get_secret_value(),
            catalog=catalog,
            schema=schema_name,
        )

        # Setup: create temp schema, staging table, and metric view
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
    else:
        schema_name = ""
        catalog = ""
        engine = MockEngine()
        engine.load("sales_view", TEST_DATA)

    semolina.register("test", engine)
    yield engine
    semolina.unregister("test")

    # Teardown: drop temp schema (CASCADE removes all objects within it)
    if is_recording:
        import databricks.sql  # type: ignore[import-not-found]

        try:
            with (
                databricks.sql.connect(**engine._connection_params) as conn,  # type: ignore[attr-defined]
                conn.cursor() as cur,  # type: ignore[attr-defined]
            ):
                cur.execute(  # type: ignore[attr-defined]
                    f"DROP SCHEMA IF EXISTS {catalog}.{schema_name} CASCADE"
                )
        except Exception as e:
            print(f"Warning: Failed to drop Databricks temp schema {catalog}.{schema_name}: {e}")


@pytest.fixture(params=["snowflake_engine", "databricks_engine"])
def backend_engine(
    request: pytest.FixtureRequest,
) -> Generator[MockEngine | SnowflakeEngine | DatabricksEngine, None, None]:
    """
    Parametrized fixture that runs integration tests against both Snowflake and Databricks.

    pytest automatically creates [snowflake_engine] and [databricks_engine] variants
    for each test that uses this fixture. Snapshot entries in .ambr files are tagged
    with the parameter suffix so both variants are stored separately.

    Recording (--snapshot-update): real engine used if credentials available.
    Replay (default, CI): MockEngine used, no credentials needed.
    """
    yield request.getfixturevalue(request.param)
