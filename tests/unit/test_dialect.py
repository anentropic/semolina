"""Tests for the Dialect StrEnum and resolve_dialect() function."""

import pytest

from semolina.dialect import Dialect, resolve_dialect
from semolina.engines.sql import (
    DatabricksDialect,
    DuckDBDialect,
    SnowflakeDialect,
)


class TestDialectEnum:
    """The dialect names a ``.semolina.toml`` ``type = "..."`` may carry."""

    def test_the_supported_dialects(self) -> None:
        """Exactly three dialects exist, spelled as a config file spells them."""
        assert {member.value for member in Dialect} == {"snowflake", "databricks", "duckdb"}

    @pytest.mark.parametrize("name", ["snowflake", "databricks", "duckdb"])
    def test_a_config_string_resolves_to_its_member(self, name: str) -> None:
        """The string from a config file is the member, and compares equal to it."""
        assert Dialect(name) == name

    def test_invalid_raises_value_error(self):
        """Dialect('invalid') raises ValueError."""
        with pytest.raises(ValueError):
            Dialect("invalid")


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
