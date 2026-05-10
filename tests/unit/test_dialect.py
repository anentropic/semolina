"""Tests for the Dialect StrEnum and resolve_dialect() function."""

import pytest

from semolina.dialect import Dialect, resolve_dialect
from semolina.engines.sql import (
    DatabricksDialect,
    DuckDBDialect,
    SnowflakeDialect,
)


class TestDialectEnum:
    """Tests for the Dialect StrEnum."""

    def test_snowflake_from_string(self):
        """Dialect('snowflake') returns Dialect.SNOWFLAKE."""
        assert Dialect("snowflake") is Dialect.SNOWFLAKE

    def test_databricks_from_string(self):
        """Dialect('databricks') returns Dialect.DATABRICKS."""
        assert Dialect("databricks") is Dialect.DATABRICKS

    def test_invalid_raises_value_error(self):
        """Dialect('invalid') raises ValueError."""
        with pytest.raises(ValueError):
            Dialect("invalid")

    def test_snowflake_string_equality(self):
        """Dialect.SNOWFLAKE == 'snowflake' (StrEnum string equality)."""
        assert Dialect.SNOWFLAKE == "snowflake"

    def test_snowflake_value(self):
        """Dialect.SNOWFLAKE.value == 'snowflake'."""
        assert Dialect.SNOWFLAKE.value == "snowflake"

    def test_databricks_value(self):
        """Dialect.DATABRICKS.value == 'databricks'."""
        assert Dialect.DATABRICKS.value == "databricks"

    def test_duckdb_from_string(self):
        """Dialect('duckdb') returns Dialect.DUCKDB."""
        assert Dialect("duckdb") is Dialect.DUCKDB

    def test_duckdb_value(self):
        """Dialect.DUCKDB.value == 'duckdb'."""
        assert Dialect.DUCKDB.value == "duckdb"

    def test_duckdb_string_equality(self):
        """Dialect.DUCKDB == 'duckdb' (StrEnum string equality)."""
        assert Dialect.DUCKDB == "duckdb"

    def test_members_iterable(self):
        """All three Dialect members are iterable."""
        members = list(Dialect)
        assert len(members) == 3
        assert Dialect.SNOWFLAKE in members
        assert Dialect.DATABRICKS in members
        assert Dialect.DUCKDB in members


class TestResolveDialect:
    """Tests for the resolve_dialect() function."""

    def test_resolve_snowflake_string(self):
        """resolve_dialect('snowflake') returns SnowflakeDialect instance."""
        result = resolve_dialect("snowflake")
        assert isinstance(result, SnowflakeDialect)

    def test_resolve_databricks_enum(self):
        """resolve_dialect(Dialect.DATABRICKS) returns DatabricksDialect instance."""
        result = resolve_dialect(Dialect.DATABRICKS)
        assert isinstance(result, DatabricksDialect)

    def test_resolve_snowflake_enum(self):
        """resolve_dialect(Dialect.SNOWFLAKE) returns SnowflakeDialect instance."""
        result = resolve_dialect(Dialect.SNOWFLAKE)
        assert isinstance(result, SnowflakeDialect)

    def test_resolve_databricks_string(self):
        """resolve_dialect('databricks') returns DatabricksDialect instance."""
        result = resolve_dialect("databricks")
        assert isinstance(result, DatabricksDialect)

    def test_resolve_duckdb_string(self):
        """resolve_dialect('duckdb') returns DuckDBDialect instance."""
        result = resolve_dialect("duckdb")
        assert isinstance(result, DuckDBDialect)

    def test_resolve_duckdb_enum(self):
        """resolve_dialect(Dialect.DUCKDB) returns DuckDBDialect instance."""
        result = resolve_dialect(Dialect.DUCKDB)
        assert isinstance(result, DuckDBDialect)

    def test_resolve_invalid_raises_value_error(self):
        """resolve_dialect('invalid') raises ValueError."""
        with pytest.raises(ValueError):
            resolve_dialect("invalid")

    def test_resolve_returns_new_instance_each_time(self):
        """Each call to resolve_dialect returns a fresh instance."""
        d1 = resolve_dialect("snowflake")
        d2 = resolve_dialect("snowflake")
        assert d1 is not d2
