"""
MockEngine for testing queries without a real warehouse connection.

MockEngine validates query structure and returns configurable fixture data,
enabling developers to test SQL generation and query logic locally without
connecting to Snowflake, Databricks, or other warehouses.
"""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING, Any, cast

from semolina.filters import (
    And,
    Between,
    EndsWith,
    Exact,
    Gt,
    Gte,
    IEndsWith,
    IExact,
    ILike,
    In,
    IsNull,
    IStartsWith,
    Like,
    Lookup,
    Lt,
    Lte,
    Not,
    NotEqual,
    Or,
    Predicate,
    StartsWith,
)

from .base import Engine
from .sql import MockDialect, SQLBuilder

if TYPE_CHECKING:
    from semolina.codegen.introspector import IntrospectedView


def _sql_like(text: str, pattern: str) -> bool:
    """
    Evaluate a SQL LIKE pattern against text using Python fnmatch semantics.

    Translates SQL wildcard characters to fnmatch patterns:
    - ``%`` in SQL maps to ``*`` in fnmatch (any sequence of characters)
    - ``_`` in SQL maps to ``?`` in fnmatch (any single character)

    Args:
        text: The string value from the fixture row.
        pattern: A SQL LIKE pattern (e.g. ``'%foo%'``, ``'bar%'``).

    Returns:
        True if text matches the pattern, False otherwise.
    """
    fnmatch_pattern = pattern.replace("%", "*").replace("_", "?")
    return fnmatch.fnmatchcase(text, fnmatch_pattern)


def _eval_predicate(node: Predicate, row: dict[str, Any]) -> bool:
    """
    Evaluate a Predicate tree against a single fixture row.

    Uses structural pattern matching to mirror the logic of
    ``SQLBuilder._compile_predicate``. Key resolution follows the same
    convention: use ``node.source`` verbatim when set, otherwise fall back
    to ``node.field_name`` (MockDialect is identity — no case folding).

    Args:
        node: A Predicate tree node (leaf Lookup, or composite And/Or/Not).
        row: A dict representing a single fixture row.

    Returns:
        True if the row satisfies the predicate, False otherwise.

    Raises:
        NotImplementedError: For unknown Lookup subclasses.
        TypeError: For non-Predicate input.
    """
    match node:
        # -- Composite nodes -------------------------------------------
        case And(left=left, right=right):
            return _eval_predicate(left, row) and _eval_predicate(right, row)

        case Or(left=left, right=right):
            return _eval_predicate(left, row) or _eval_predicate(right, row)

        case Not(inner=inner):
            return not _eval_predicate(inner, row)

        # -- Leaf lookups (specific before generic) --------------------
        # Key resolution: source verbatim when set, otherwise field_name
        # (MockDialect.normalize_identifier is identity, so field_name is used as-is)
        case Exact(field_name=f, value=v):
            key = node.source if node.source is not None else f
            return row.get(key) == v

        case NotEqual(field_name=f, value=v):
            key = node.source if node.source is not None else f
            return row.get(key) != v

        case Gt(field_name=f, value=v):
            key = node.source if node.source is not None else f
            val = row.get(key)
            return val is not None and val > v  # type: ignore[operator]

        case Gte(field_name=f, value=v):
            key = node.source if node.source is not None else f
            val = row.get(key)
            return val is not None and val >= v  # type: ignore[operator]

        case Lt(field_name=f, value=v):
            key = node.source if node.source is not None else f
            val = row.get(key)
            return val is not None and val < v  # type: ignore[operator]

        case Lte(field_name=f, value=v):
            key = node.source if node.source is not None else f
            val = row.get(key)
            return val is not None and val <= v  # type: ignore[operator]

        case In(field_name=f, value=v):
            if not v:
                return False
            key = node.source if node.source is not None else f
            return row.get(key) in v

        case Between(field_name=f, value=v):
            lo, hi = v
            key = node.source if node.source is not None else f
            val = row.get(key)
            return val is not None and lo <= val <= hi  # type: ignore[operator]

        case IsNull(field_name=f, value=v):
            key = node.source if node.source is not None else f
            if v:
                return row.get(key) is None
            return row.get(key) is not None

        case StartsWith(field_name=f, value=v):
            key = node.source if node.source is not None else f
            return str(row.get(key, "")).startswith(str(v))

        case IStartsWith(field_name=f, value=v):
            key = node.source if node.source is not None else f
            return str(row.get(key, "")).lower().startswith(str(v).lower())

        case EndsWith(field_name=f, value=v):
            key = node.source if node.source is not None else f
            return str(row.get(key, "")).endswith(str(v))

        case IEndsWith(field_name=f, value=v):
            key = node.source if node.source is not None else f
            return str(row.get(key, "")).lower().endswith(str(v).lower())

        case Like(field_name=f, value=v):
            key = node.source if node.source is not None else f
            return _sql_like(str(row.get(key, "")), v)

        case ILike(field_name=f, value=v):
            key = node.source if node.source is not None else f
            return _sql_like(str(row.get(key, "")).lower(), v.lower())

        case IExact(field_name=f, value=v):
            key = node.source if node.source is not None else f
            return str(row.get(key, "")).lower() == str(v).lower()

        # -- Catch-all: unknown Lookup subclass or non-Predicate -------
        case _:
            cls_name = type(cast("object", node)).__name__
            if isinstance(node, Lookup):
                msg = (
                    f"Unsupported lookup type: {cls_name}. Add a case for it in _eval_predicate()."
                )
                raise NotImplementedError(msg)
            msg = (
                f"Expected Predicate, got {cls_name}. "
                f"Use Lookup subclasses or And/Or/Not composites."
            )
            raise TypeError(msg)


class MockEngine(Engine):
    """
    Mock backend engine for testing queries without a real warehouse connection.

    MockEngine validates query structure and generates SQL for testing purposes.
    SQL generation uses MockDialect (Snowflake-compatible syntax) for consistency.
    For test data injection, use pytest fixtures rather than passing data to the
    constructor.

    MockEngine evaluates WHERE predicates in-memory via ``_eval_predicate``,
    so ``.where()`` filters are correctly reflected in ``execute()`` results.

    Attributes:
        dialect: MockDialect instance for SQL generation

    Example:
        .. code-block:: python

            from semolina import SemanticView, Metric, Dimension
            from semolina.engines import MockEngine


            # In conftest.py
            @pytest.fixture
            def sales_fixtures():
                return {
                    "sales_view": [
                        {"revenue": 1000, "country": "US"},
                        {"revenue": 500, "country": "CA"},
                    ]
                }


            @pytest.fixture
            def engine(sales_fixtures):
                return MockEngine()


            # In test file
            def test_query(engine):
                query = (
                    Sales.query()
                    .metrics(Sales.revenue)
                    .dimensions(Sales.country)
                )
                sql = engine.to_sql(query)
                # SELECT AGG("revenue"), "country"
                # FROM "sales_view"
                # GROUP BY ALL
    """

    def __init__(self) -> None:
        """
        Initialize MockEngine with MockDialect for SQL generation.

        For testing with data, use pytest fixtures to inject test data
        rather than passing it to the constructor.
        """
        self.dialect = MockDialect()
        self._fixtures: dict[str, list[dict[str, Any]]] = {}

    def load(self, view_name: str, data: list[dict[str, Any]]) -> None:
        """
        Load fixture data for a semantic view.

        Args:
            view_name: View name matching SemanticView's view parameter
            data: List of row dicts with field names as keys

        Example:
            .. code-block:: python

                engine = MockEngine()
                engine.load(
                    "sales_view",
                    [
                        {"revenue": 1000, "country": "US"},
                        {"revenue": 500, "country": "CA"},
                    ],
                )
        """
        self._fixtures[view_name] = data

    def to_sql(self, query: Any) -> str:
        """
        Generate SQL for a query using MockDialect.

        Validates that the query has at least one metric or dimension,
        then uses SQLBuilder to generate SQL with Snowflake-compatible
        syntax (double quotes, AGG() wrapping).

        Args:
            query: Query object to convert to SQL

        Returns:
            SQL string formatted for MockEngine

        Raises:
            ValueError: If query is invalid (missing metrics and dimensions)

        Example:
            .. code-block:: python

                sql = engine.to_sql(query)
                # SELECT AGG("revenue"), "country"
                # FROM "sales_view"
                # GROUP BY ALL
        """
        query._validate_for_execution()
        builder = SQLBuilder(self.dialect)
        return builder.build_select(query)

    def execute(self, query: Any) -> list[dict[str, Any]]:
        """
        Execute a query against loaded fixture data.

        Validates query, extracts view name from query fields, and returns
        fixture data for that view filtered by any WHERE predicates. Returns
        an empty list if no fixtures are loaded for the view.

        WHERE predicates applied via ``.where()`` are evaluated in-memory
        using ``_eval_predicate``, so only rows matching the filter are
        returned.

        Args:
            query: Query object to execute

        Returns:
            List of row dicts from loaded fixtures matching query predicates

        Raises:
            ValueError: If query is invalid (missing metrics and dimensions)

        Example:
            .. code-block:: python

                engine = MockEngine()
                engine.load(
                    "sales_view", [{"revenue": 1000, "country": "US"}]
                )
                results = engine.execute(query)
        """
        query._validate_for_execution()

        # Extract view name from query fields
        view_name: str | None = None
        if query._metrics:
            owner = query._metrics[0].owner
            if owner is not None:
                view_name = owner._view_name
        elif query._dimensions:
            owner = query._dimensions[0].owner
            if owner is not None:
                view_name = owner._view_name

        if view_name is None:
            return []

        rows = self._fixtures.get(view_name, [])
        if query._filters is not None:
            rows = [r for r in rows if _eval_predicate(query._filters, r)]
        return rows

    def introspect(self, view_name: str) -> IntrospectedView:
        """
        Raise NotImplementedError — MockEngine does not support introspection.

        MockEngine is designed for testing query construction and SQL generation
        without a real warehouse. Introspection requires a live warehouse
        connection; use SnowflakeEngine or DatabricksEngine for reverse codegen.

        Args:
            view_name: Ignored.

        Raises:
            NotImplementedError: Always. MockEngine does not support introspection.

        Example:
            .. code-block:: python

                engine = MockEngine()
                engine.introspect("sales_view")
                # NotImplementedError: MockEngine does not support introspection
        """
        raise NotImplementedError("MockEngine does not support introspection")
