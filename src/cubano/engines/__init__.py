"""
Backend engines for SQL generation and query execution.

Provides abstract interface (Engine ABC) and dialect-specific SQL generation
(Dialect ABC with SnowflakeDialect, DatabricksDialect, MockDialect) for
backend-agnostic query building. MockEngine provides testing without a real
warehouse connection.
"""

from .base import Engine
from .mock import MockEngine
from .snowflake import SnowflakeEngine
from .sql import DatabricksDialect, Dialect, MockDialect, SnowflakeDialect

__all__ = [
    "Engine",
    "Dialect",
    "SnowflakeDialect",
    "DatabricksDialect",
    "MockDialect",
    "MockEngine",
    "SnowflakeEngine",
]
