"""
The Snowflake recording fixture's query-pool config, checked without a warehouse.

The record fixture creates its temp schema over the native connector, then queries it over
an ADBC pool. The Snowflake ADBC driver ignores ``schema`` unless ``database`` is also set,
so a pool given only the schema stays in the user's default namespace and every query
fails with ``Object 'SALES_VIEW' does not exist`` (measured in 53-04 against a
``[connections.snowflake]`` with no ``database`` key). The fixture therefore pins the
database the native session resolved.

These tests assert on ``to_adbc_kwargs()``, what the driver actually receives, rather than
on the config object: the failure was a missing driver option, not a wrong attribute.
"""

from __future__ import annotations

import pytest
from _recording import snowflake_query_config
from adbc_poolhouse import SnowflakeConfig
from pydantic import SecretStr


def _config_without_database() -> SnowflakeConfig:
    return SnowflakeConfig(
        account="acct",
        user="user",
        password=SecretStr("pass"),
        warehouse="wh",
        role="role",
    )


def test_the_session_database_reaches_the_driver_with_the_schema() -> None:
    """A config with no database still sends the driver both db and schema."""
    config = snowflake_query_config(
        _config_without_database(), schema_name="TEST_ABC", session_database="DEMO"
    )

    kwargs = config.to_adbc_kwargs()
    assert kwargs["adbc.snowflake.sql.db"] == "DEMO"
    assert kwargs["adbc.snowflake.sql.schema"] == "TEST_ABC"


def test_a_session_without_a_database_is_refused() -> None:
    """With no database to pin, the schema would be ignored, so setup fails loudly instead."""
    with pytest.raises(ValueError, match=r"no current database"):
        snowflake_query_config(
            _config_without_database(), schema_name="TEST_ABC", session_database=None
        )
