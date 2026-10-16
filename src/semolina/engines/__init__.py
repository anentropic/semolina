"""
Backend engines for SQL generation and query execution.

Provides the abstract :class:`~semolina.engines.base.Engine` interface and dialect-specific SQL
generation (the SQLDialect ABC with SnowflakeDialect, DatabricksDialect,
DuckDBDialect) for backend-agnostic query building.
"""

import warnings
from typing import Any

from semolina.exceptions import (
    SemolinaConnectionError,
    SemolinaIntrospectionError,
    SemolinaViewNotFoundError,
)

from .abase import AsyncEngine
from .base import Engine
from .databricks import DatabricksEngine
from .duckdb import DuckDBEngine
from .snowflake import SnowflakeEngine
from .sql import DatabricksDialect, DuckDBDialect, SnowflakeDialect, SQLDialect

__all__ = [
    "AsyncEngine",
    "Engine",
    "SemolinaConnectionError",
    "SemolinaIntrospectionError",
    "SemolinaViewNotFoundError",
    "SQLDialect",
    "SnowflakeDialect",
    "DatabricksDialect",
    "DuckDBDialect",
    "SnowflakeEngine",
    "DatabricksEngine",
    "DuckDBEngine",
]


def __getattr__(name: str) -> Any:
    """
    Resolve ``DialectABC``, the export :class:`SQLDialect` had before 0.7.0, with a warning.

    Args:
        name: The attribute being looked up on the package.

    Returns:
        :class:`~semolina.engines.sql.SQLDialect` for ``DialectABC``.

    Raises:
        AttributeError: For any other name, as a missing module attribute would.
    """
    if name == "DialectABC":
        warnings.warn(
            "semolina.engines.DialectABC is renamed SQLDialect; the old name will be removed "
            "in the next release.",
            DeprecationWarning,
            stacklevel=2,
        )
        return SQLDialect
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
