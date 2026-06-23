"""
Semolina - A Pythonic ORM for querying data warehouse semantic views.

Semolina provides typed model definitions and a fluent query API for
Snowflake and Databricks semantic views.
"""

from .config import create_engine
from .cursor import SemolinaCursor
from .dialect import Dialect
from .engines.base import SemolinaConnectionError, SemolinaViewNotFoundError
from .fields import Dimension, Fact, Metric, NullsOrdering, OrderTerm
from .filters import Predicate
from .models import SemanticView
from .registry import get_engine, register, unregister
from .results import Row

__version__ = __import__("importlib.metadata").metadata.version("semolina")

__all__ = [
    "__version__",
    "Dialect",
    "Dimension",
    "Fact",
    "Metric",
    "NullsOrdering",
    "OrderTerm",
    "Predicate",
    "Row",
    "SemolinaCursor",
    "SemolinaConnectionError",
    "SemolinaViewNotFoundError",
    "SemanticView",
    "create_engine",
    "get_engine",
    "register",
    "unregister",
]
