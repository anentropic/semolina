"""
Dialect enum for SQL generation backend selection.

Maps string dialect names to concrete Dialect ABC implementations from
engines.sql. The StrEnum provides the public-facing name; the ABC in
engines.sql is the internal interface for SQL generation.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engines.sql import Dialect as DialectABC


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
    MOCK = "mock"


def resolve_dialect(dialect: str | Dialect) -> DialectABC:
    """
    Resolve a dialect string or enum value to a concrete Dialect ABC instance.

    Args:
        dialect: String name or Dialect enum value.

    Returns:
        Concrete Dialect instance for SQL generation.

    Raises:
        ValueError: If dialect string is not a valid Dialect member.

    Example:
        .. code-block:: python

            from semolina.dialect import resolve_dialect

            sf = resolve_dialect("snowflake")
            # sf is a SnowflakeDialect instance
    """
    from .engines.sql import DatabricksDialect, MockDialect, SnowflakeDialect

    _DIALECT_MAP: dict[Dialect, type[DialectABC]] = {
        Dialect.SNOWFLAKE: SnowflakeDialect,
        Dialect.DATABRICKS: DatabricksDialect,
        Dialect.MOCK: MockDialect,
    }
    key = Dialect(dialect)
    return _DIALECT_MAP[key]()
