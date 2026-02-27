"""
Semolina - A Pythonic ORM for querying data warehouse semantic views.

Semolina provides typed model definitions and a fluent query API for
Snowflake and Databricks semantic views.
"""

from .engines.base import SemolinaConnectionError, SemolinaViewNotFoundError
from .fields import Dimension, Fact, Metric, NullsOrdering, OrderTerm
from .filters import Predicate
from .models import SemanticView
from .registry import get_engine, register, unregister
from .results import Result, Row

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "SemanticView",
    "Metric",
    "Dimension",
    "Fact",
    "Predicate",
    "OrderTerm",
    "NullsOrdering",
    "register",
    "get_engine",
    "unregister",
    "Row",
    "Result",
    "SemolinaViewNotFoundError",
    "SemolinaConnectionError",
]
