"""
Backend engines for SQL generation and query execution.

Provides abstract interface (Engine ABC) and dialect-specific SQL generation
(Dialect ABC with SnowflakeDialect, DatabricksDialect, MockDialect) for
backend-agnostic query building.
"""

from .base import Engine
from .sql import DatabricksDialect, Dialect, MockDialect, SnowflakeDialect

__all__ = [
    "Engine",
    "Dialect",
    "SnowflakeDialect",
    "DatabricksDialect",
    "MockDialect",
]
