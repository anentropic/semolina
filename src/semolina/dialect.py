"""
Dialect enum for SQL generation backend selection.

Maps string dialect names to the concrete :class:`~semolina.engines.sql.SQLDialect`
implementations in ``engines.sql``. The StrEnum is the public-facing name; ``SQLDialect`` is
the interface that generates the SQL.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engines.sql import SQLDialect

__all__ = [
    "Dialect",
    "resolve_dialect",
]


class Dialect(StrEnum):
    """
    Dialect enum for SQL generation backend selection.

    Determines how SQL is generated: identifier quoting style,
    metric wrapping function (AGG vs MEASURE), and placeholder format.

    Example:
        .. code-block:: python

            from semolina.dialect import Dialect

            d = Dialect("snowflake")
            assert d is Dialect.SNOWFLAKE
            assert d == "snowflake"
    """

    SNOWFLAKE = "snowflake"
    DATABRICKS = "databricks"
    DUCKDB = "duckdb"


def resolve_dialect(dialect: str | Dialect) -> SQLDialect:
    """
    Resolve a dialect string or enum value to a concrete SQLDialect instance.

    Args:
        dialect: String name or Dialect enum value.

    Returns:
        Concrete SQLDialect instance for SQL generation.

    Raises:
        ValueError: If dialect string is not a valid Dialect member.

    Example:
        .. code-block:: python

            from semolina.dialect import resolve_dialect

            sf = resolve_dialect("snowflake")
            # sf is a SnowflakeDialect instance
    """
    from .engines.sql import DatabricksDialect, DuckDBDialect, SnowflakeDialect

    _DIALECT_MAP: dict[Dialect, type[SQLDialect]] = {
        Dialect.SNOWFLAKE: SnowflakeDialect,
        Dialect.DATABRICKS: DatabricksDialect,
        Dialect.DUCKDB: DuckDBDialect,
    }
    key = Dialect(dialect)
    return _DIALECT_MAP[key]()
