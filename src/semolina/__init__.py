"""
Semolina - A Pythonic ORM for querying data warehouse semantic views.

Semolina provides typed model definitions and a fluent query API for
Snowflake and Databricks semantic views.
"""

from importlib.metadata import PackageNotFoundError, version

from .acursor import AsyncSemolinaCursor
from .config import create_async_engine, create_engine
from .cursor import SemolinaCursor
from .dialect import Dialect
from .engines.base import SemolinaConnectionError, SemolinaViewNotFoundError
from .fields import Dimension, Fact, Metric, NullsOrdering, OrderTerm
from .filters import Predicate
from .models import SemanticView
from .registry import (
    get_async_engine,
    get_engine,
    register,
    register_async_engine,
    unregister,
    unregister_async_engine,
)
from .results import Row
from .types import JsonValue

try:
    __version__ = version("semolina")
except PackageNotFoundError:
    # Editable/source checkout without installed package metadata.
    __version__ = "0.0.0+unknown"

__all__ = [
    "__version__",
    "AsyncSemolinaCursor",
    "Dialect",
    "Dimension",
    "Fact",
    "JsonValue",
    "Metric",
    "NullsOrdering",
    "OrderTerm",
    "Predicate",
    "Row",
    "SemolinaCursor",
    "SemolinaConnectionError",
    "SemolinaViewNotFoundError",
    "SemanticView",
    "create_async_engine",
    "create_engine",
    "get_async_engine",
    "get_engine",
    "register",
    "register_async_engine",
    "unregister",
    "unregister_async_engine",
]
