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


class TestOneThingIsCalledDialect:
    """
    The SQL-generation base class is ``SQLDialect``; ``Dialect`` is only the enum.

    The old names keep working for one release, with a ``DeprecationWarning``.
    """

    @pytest.mark.parametrize("concrete", [SnowflakeDialect, DatabricksDialect, DuckDBDialect])
    def test_every_concrete_dialect_is_an_sql_dialect(self, concrete: type) -> None:
        """Each backend's dialect derives from ``SQLDialect``."""
        from semolina.engines.sql import SQLDialect

        assert issubclass(concrete, SQLDialect)

    def test_engines_package_exports_sql_dialect(self) -> None:
        """``SQLDialect`` is importable from ``semolina.engines``."""
        import semolina.engines
        from semolina.engines.sql import SQLDialect

        assert "SQLDialect" in semolina.engines.__all__
        assert semolina.engines.SQLDialect is SQLDialect

    @pytest.mark.parametrize(
        ("module_name", "old_name"),
        [("semolina.engines.sql", "Dialect"), ("semolina.engines", "DialectABC")],
    )
    def test_the_old_name_warns_and_is_sql_dialect(self, module_name: str, old_name: str) -> None:
        """``engines.sql.Dialect`` and ``engines.DialectABC`` still work, and say so."""
        import importlib

        from semolina.engines.sql import SQLDialect

        module = importlib.import_module(module_name)
        with pytest.warns(DeprecationWarning, match="SQLDialect"):
            old = getattr(module, old_name)
        assert old is SQLDialect

    def test_the_old_names_are_not_advertised(self) -> None:
        """Neither old name is in an ``__all__``, so a star import does not bring it back."""
        import semolina.engines
        import semolina.engines.sql

        assert "Dialect" not in semolina.engines.sql.__all__
        assert "DialectABC" not in semolina.engines.__all__
