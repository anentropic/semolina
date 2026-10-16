"""
Semolina - A Pythonic ORM for querying data warehouse semantic views.

Semolina provides typed model definitions and a fluent query API for
Snowflake and Databricks semantic views.
"""

from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any

from .acursor import AsyncSemolinaCursor
from .cursor import SemolinaCursor
from .dialect import Dialect
from .engines.abase import AsyncEngine
from .engines.base import Engine
from .exceptions import (
    SemolinaConnectionError,
    SemolinaEngineNotRegisteredError,
    SemolinaError,
    SemolinaMissingDependencyError,
    SemolinaResultConsumedError,
    SemolinaSchemaMismatchError,
    SemolinaViewNotFoundError,
)
from .fields import Dimension, Fact, Field, Metric, NullsOrdering, OrderTerm
from .filters import And, Lookup, Not, Or, Predicate
from .models import SemanticView
from .query import Query
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

if TYPE_CHECKING:
    from .config import create_async_engine, create_engine

try:
    __version__ = version("semolina")
except PackageNotFoundError:
    # Editable/source checkout without installed package metadata.
    __version__ = "0.0.0+unknown"

__all__ = [
    "__version__",
    "And",
    "AsyncEngine",
    "AsyncSemolinaCursor",
    "create_async_engine",
    "create_engine",
    "Dialect",
    "Dimension",
    "Engine",
    "Fact",
    "Field",
    "get_async_engine",
    "get_engine",
    "JsonValue",
    "Lookup",
    "Metric",
    "Not",
    "NullsOrdering",
    "Or",
    "OrderTerm",
    "Predicate",
    "Query",
    "register",
    "register_async_engine",
    "Row",
    "SemanticView",
    "SemolinaConnectionError",
    "SemolinaCursor",
    "SemolinaEngineNotRegisteredError",
    "SemolinaError",
    "SemolinaMissingDependencyError",
    "SemolinaResultConsumedError",
    "SemolinaSchemaMismatchError",
    "SemolinaViewNotFoundError",
    "unregister",
    "unregister_async_engine",
]


_LAZY = {"create_engine", "create_async_engine"}
"""
Names resolved from :mod:`semolina.config` on first use rather than at ``import semolina``.

``semolina.config`` imports adbc-poolhouse's pool factories, and with them pydantic-settings
and SQLAlchemy. A module that only defines models and builds queries never needs those, so
``import semolina`` does not pay for them.
"""


def __getattr__(name: str) -> Any:
    """
    Resolve the engine factories lazily (PEP 562).

    Args:
        name: The attribute being looked up on the package.

    Returns:
        The factory from :mod:`semolina.config`.

    Raises:
        AttributeError: For any other name, as a missing module attribute would.
    """
    if name in _LAZY:
        from . import config

        return getattr(config, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
