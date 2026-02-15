"""
Immutable query builder for semantic views.

Provides fluent method chaining for constructing queries with metrics,
dimensions, filters, ordering, and limits. Each method returns a new
frozen Query instance, guaranteeing immutability.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from .fields import Dimension, Fact, Field, Metric, OrderTerm
from .filters import Q


@dataclass(frozen=True)
class Query:
    """
    Immutable query builder for semantic views.

    Each method returns a new Query instance, preserving immutability.
    Build queries using fluent method chaining.

    Example:
        query = (Query()
            .metrics(Sales.revenue, Sales.cost)
            .dimensions(Sales.country)
            .filter(Q(country='US') | Q(country='CA'))
            .order_by(Sales.revenue)
            .limit(100))

    Attributes:
        _metrics: Tuple of Metric fields for aggregation
        _dimensions: Tuple of Dimension/Fact fields for grouping
        _filters: Q object with filter conditions (ANDed together)
        _order_by_fields: Tuple of Field objects for ordering
        _limit_value: Maximum number of rows to return
        _using: Engine name for lazy resolution (None = 'default')
    """

    _metrics: tuple[Metric, ...] = field(default_factory=tuple)
    _dimensions: tuple[Dimension | Fact, ...] = field(default_factory=tuple)
    _filters: Q | None = None
    _order_by_fields: tuple[Field | OrderTerm, ...] = field(default_factory=tuple)
    _limit_value: int | None = None
    _using: str | None = None

    def metrics(self, *fields: Any) -> Query:
        """
        Select metrics for aggregation.

        Args:
            *fields: One or more Metric field references

        Returns:
            New Query instance with metrics added

        Raises:
            TypeError: If any field is not a Metric
            ValueError: If no fields provided

        Example:
            Query().metrics(Sales.revenue, Sales.cost)
        """
        if not fields:
            raise ValueError("At least one metric must be provided")

        for f in fields:
            if not isinstance(f, Metric):
                raise TypeError(
                    f"metrics() requires Metric fields, got {type(f).__name__}. "
                    f"Did you mean .dimensions()?"
                )

        return replace(self, _metrics=self._metrics + fields)

    def dimensions(self, *fields: Any) -> Query:
        """
        Select dimensions/facts for grouping.

        Accepts both Dimension fields (categorical attributes) and Fact fields
        (raw numeric values that can be used in calculations or grouping).

        Args:
            *fields: One or more Dimension or Fact field references

        Returns:
            New Query instance with dimensions added

        Raises:
            TypeError: If any field is not a Dimension or Fact
            ValueError: If no fields provided

        Example:
            Query().dimensions(Sales.country, Sales.unit_price)
        """
        if not fields:
            raise ValueError("At least one dimension must be provided")

        for f in fields:
            if not isinstance(f, (Dimension, Fact)):
                raise TypeError(
                    f"dimensions() requires Dimension or Fact fields, "
                    f"got {type(f).__name__}. "
                    f"Did you mean .metrics()?"
                )

        return replace(self, _dimensions=self._dimensions + fields)

    def filter(self, condition: Any) -> Query:
        """
        Add filter condition to query.

        Multiple .filter() calls are combined with AND.

        Args:
            condition: Q object with filter conditions

        Returns:
            New Query instance with filter added

        Raises:
            TypeError: If condition is not a Q object

        Example:
            Query().filter(Q(country='US') | Q(country='CA'))
        """
        if not isinstance(condition, Q):
            raise TypeError(f"filter() requires Q object, got {type(condition).__name__}")

        # Combine with existing filters using AND
        new_filters = condition if self._filters is None else self._filters & condition
        return replace(self, _filters=new_filters)

    def order_by(self, *fields: Any) -> Query:
        """
        Order results by fields.

        Accepts both bare Field instances (default ascending) and OrderTerm instances
        (created via field.asc() or field.desc()) for explicit direction and NULL handling.

        Args:
            *fields: One or more Field or OrderTerm objects for ordering

        Returns:
            New Query instance with order_by fields added

        Raises:
            TypeError: If any field is not a Field or OrderTerm
            ValueError: If no fields provided

        Example:
            Query().order_by(Sales.revenue)  # Bare field (ascending)
            Query().order_by(Sales.revenue.desc())  # Descending
            Query().order_by(Sales.revenue.desc(NullsOrdering.FIRST))  # With NULLS FIRST
            Query().order_by(Sales.revenue.desc(), Sales.country.asc())  # Mixed directions
        """
        if not fields:
            raise ValueError("At least one field must be provided")

        for f in fields:
            if not isinstance(f, (Field, OrderTerm)):
                raise TypeError(
                    f"order_by() requires Field or OrderTerm, got {type(f).__name__}. "
                    f"Use field.asc() or field.desc() for direction."
                )

        return replace(self, _order_by_fields=self._order_by_fields + fields)

    def limit(self, n: Any) -> Query:
        """
        Limit results to n rows.

        Args:
            n: Maximum number of rows (must be positive)

        Returns:
            New Query instance with limit set

        Raises:
            TypeError: If n is not an int
            ValueError: If n is not a positive integer

        Example:
            Query().limit(100)
        """
        if not isinstance(n, int):
            raise TypeError(f"limit() requires int, got {type(n).__name__}")

        if n <= 0:
            raise ValueError(f"limit() requires positive integer, got {n}")

        return replace(self, _limit_value=n)

    def using(self, engine_name: Any) -> Query:
        """
        Select engine for this query by name.

        Engine is resolved lazily at .fetch() time, not during query
        construction. This allows queries to be defined before engines
        are registered.

        Args:
            engine_name: Registered engine name (e.g., 'default', 'warehouse')

        Returns:
            New Query instance with engine name set

        Raises:
            TypeError: If engine_name is not a string

        Example:
            Query().metrics(Sales.revenue).using('warehouse')
        """
        if not isinstance(engine_name, str):
            raise TypeError(
                f"using() requires engine name string, got {type(engine_name).__name__}. "
                f"Register engine first: cubano.register('name', engine)"
            )
        return replace(self, _using=engine_name)

    def _validate_for_execution(self) -> None:
        """
        Validate query is ready for execution.

        Called by .fetch() and .to_sql(), NOT during construction.
        Allows building queries incrementally without errors.

        Raises:
            ValueError: If query has no metrics or dimensions
        """
        if not self._metrics and not self._dimensions:
            raise ValueError(
                "Query must select at least one metric or dimension. "
                "Use .metrics() or .dimensions() to add fields."
            )

    def to_sql(self) -> str:
        """
        Generate SQL for this query using MockDialect (Snowflake-like).

        Generates SQL using MockDialect (double quotes for identifiers, AGG()
        for metrics) for inspection and debugging. This is useful for
        understanding what SQL will be generated without specifying a backend.

        For backend-specific SQL generation, use Engine.to_sql(query) where
        Engine is bound to a specific backend (Snowflake, Databricks, etc.).

        Returns:
            SQL string (generated using MockDialect)

        Raises:
            ValueError: If query is not valid for execution
        """
        self._validate_for_execution()
        from cubano.engines.sql import MockDialect, SQLBuilder

        builder = SQLBuilder(MockDialect())
        return builder.build_select(self)

    def fetch(self) -> list[Any]:
        """
        Execute query and return results as Row objects.

        Resolves engine lazily from registry (using self._using or 'default'),
        executes query via engine.execute(), and wraps results in Row objects.

        Returns:
            List of Row objects with attribute and dict-style access

        Raises:
            ValueError: If query has no metrics or dimensions
            ValueError: If no engine registered with the requested name

        Example:
            results = Query().metrics(Sales.revenue).fetch()
            print(results[0].revenue)
        """
        from .registry import get_engine
        from .results import Row

        self._validate_for_execution()
        engine = get_engine(self._using)
        raw_results = engine.execute(self)
        return [Row(data) for data in raw_results]
