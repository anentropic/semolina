"""
Semolina - A Pythonic ORM for querying data warehouse semantic views.

Semolina provides typed model definitions and a fluent query API for
Snowflake and Databricks semantic views.
"""

from .config import pool_from_config
from .cursor import SemolinaCursor
from .dialect import Dialect
from .engines.base import SemolinaConnectionError, SemolinaViewNotFoundError
from .fields import Dimension, Fact, Metric, NullsOrdering, OrderTerm
from .filters import Predicate
from .models import SemanticView
from .pool import MockPool
from .registry import get_engine, get_pool, register, unregister
from .results import Row

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Dialect",
    "Dimension",
    "Fact",
    "Metric",
    "MockPool",
    "NullsOrdering",
    "OrderTerm",
    "Predicate",
    "Row",
    "SemolinaCursor",
    "SemolinaConnectionError",
    "SemolinaViewNotFoundError",
    "SemanticView",
    "get_engine",
    "get_pool",
    "pool_from_config",
    "register",
    "unregister",
]
