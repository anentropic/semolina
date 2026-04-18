"""
Backend engines for SQL generation and query execution.

Provides abstract interface (Engine ABC) and dialect-specific SQL generation
(Dialect ABC with SnowflakeDialect, DatabricksDialect, MockDialect) for
backend-agnostic query building. MockEngine provides testing without a real
warehouse connection.
"""

from .base import Engine
from .databricks import DatabricksEngine
from .mock import MockEngine
from .snowflake import SnowflakeEngine
from .sql import DatabricksDialect, MockDialect, SnowflakeDialect
from .sql import Dialect as DialectABC

__all__ = [
    "Engine",
    "DialectABC",
    "SnowflakeDialect",
    "DatabricksDialect",
    "MockDialect",
    "MockEngine",
    "SnowflakeEngine",
    "DatabricksEngine",
]
