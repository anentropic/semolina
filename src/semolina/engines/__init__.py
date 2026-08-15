"""
Backend engines for SQL generation and query execution.

Provides the abstract :class:`~semolina.engines.base.Engine` interface and dialect-specific SQL
generation (Dialect ABC with SnowflakeDialect, DatabricksDialect,
DuckDBDialect) for backend-agnostic query building.
"""

from .base import Engine
from .databricks import DatabricksEngine
from .duckdb import DuckDBEngine
from .snowflake import SnowflakeEngine
from .sql import DatabricksDialect, DuckDBDialect, SnowflakeDialect
from .sql import Dialect as DialectABC

__all__ = [
    "Engine",
    "DialectABC",
    "SnowflakeDialect",
    "DatabricksDialect",
    "DuckDBDialect",
    "SnowflakeEngine",
    "DatabricksEngine",
    "DuckDBEngine",
]
