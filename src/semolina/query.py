"""
Immutable query builder for semantic views.

Provides fluent method chaining for constructing queries with metrics,
dimensions, filters, ordering, and limits. Each method returns a new
frozen Query instance, guaranteeing immutability.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from .fields import Dimension, Fact, Field, Metric, OrderTerm

if TYPE_CHECKING:
    from .cursor import SemolinaCursor
    from .filters import Predicate


@dataclass(frozen=True, repr=False)
class _Query:
    """
    Immutable query builder for semantic views.

    Each method returns a new _Query instance, preserving immutability.
    Build queries using fluent method chaining. Typically created via
    Model.query(), not directly via _Query().

    Use .where() for filtering with natural Python comparison operators:
        Users.country == 'US', Users.revenue > 1000, etc.

    Execution:
        .execute() returns SemolinaCursor (primary public API)

    Example:
        .. code-block:: pycon

            >>> query = (_Query()
            ...     .metrics(Sales.revenue, Sales.cost)
            ...     .dimensions(Sales.country)
            ...     .where(Sales.country == 'US')
            ...     .order_by(Sales.revenue)
            ...     .limit(100))
            >>> len(query._metrics)
            2

    Attributes:
        _metrics: Tuple of Metric fields for aggregation
        _dimensions: Tuple of Dimension/Fact fields for grouping
        _filters: Predicate tree with filter conditions (ANDed together)
        _order_by_fields: Tuple of Field objects for ordering
        _limit_value: Maximum number of rows to return
        _using: Pool name for lazy resolution (None = 'default')
        _model: Model class this query is bound to (set by Model.query())
    """

    _metrics: tuple[Metric[Any], ...] = field(default_factory=tuple)
    _dimensions: tuple[Dimension[Any] | Fact[Any], ...] = field(default_factory=tuple)
    _filters: Predicate | None = None
    _order_by_fields: tuple[Field[Any] | OrderTerm, ...] = field(default_factory=tuple)
    _limit_value: int | None = None
    _using: str | None = None
    _model: type | None = field(default=None, init=False, repr=False)

    def __repr__(self) -> str:
        """
        Return informative repr showing query state.

        Shows model name, selected metrics/dimensions, filters, ordering,
        limit, and pool binding.
        """
        model_name = self._model.__name__ if self._model else "unbound"
        parts: list[str] = [f"model={model_name}"]
        if self._metrics:
            names = [f.name for f in self._metrics]
            parts.append(f"metrics={names}")
        if self._dimensions:
            names = [f.name for f in self._dimensions]
            parts.append(f"dimensions={names}")
        if self._filters is not None:
            parts.append(f"where={self._filters!r}")
        if self._order_by_fields:
            order_parts: list[str] = []
            for f in self._order_by_fields:
                if isinstance(f, OrderTerm):
                    order_parts.append(repr(f))
                else:
                    order_parts.append(f.name or "?")
            parts.append(f"order_by=[{', '.join(order_parts)}]")
        if self._limit_value is not None:
            parts.append(f"limit={self._limit_value}")
        if self._using is not None:
            parts.append(f"using='{self._using}'")
        return f"<Query {' '.join(parts)}>"

    def _replace(self, **changes: Any) -> _Query:
        """
        Replace fields on a frozen dataclass, preserving _model.

        The _model field has init=False so dataclasses.replace() does not
        carry it forward. This helper propagates it to the new instance.
        """
        new = replace(self, **changes)
        if self._model is not None:
            object.__setattr__(new, "_model", self._model)
        return new

    def metrics(self, *fields: Any) -> _Query:
        """
        Select metrics for aggregation.

        Args:
            *fields: One or more Metric field references

        Returns:
            New _Query instance with metrics added

        Raises:
            TypeError: If any field is not a Metric
            ValueError: If no fields provided
            TypeError: If field is from a different model

        Example:
            .. code-block:: python

                >>> query = _Query().metrics(Sales.revenue, Sales.cost)
                >>> len(query._metrics)
                2
        """
        if not fields:
            raise ValueError("At least one metric must be provided")

        for f in fields:
            if not isinstance(f, Metric):
                raise TypeError(
                    f"metrics() requires Metric fields, got {type(f).__name__}. "
                    f"Did you mean .dimensions()?"
                )

            # Validate field ownership if model is set
            if self._model is not None and f.owner != self._model:
                model_name = self._model.__name__
                other_model = f.owner.__name__ if f.owner else "unknown"
                raise TypeError(
                    f"Cannot mix fields from different models in one query. "
                    f"Expected fields from {model_name}, "
                    f"got field '{f.name}' from {other_model}"
                )

        return self._replace(_metrics=self._metrics + fields)

    def dimensions(self, *fields: Any) -> _Query:
        """
        Select dimensions/facts for grouping.

        Accepts both Dimension fields (categorical attributes) and Fact fields
        (raw numeric values that can be used in calculations or grouping).

        Args:
            *fields: One or more Dimension or Fact field references

        Returns:
            New _Query instance with dimensions added

        Raises:
            TypeError: If any field is not a Dimension or Fact
            ValueError: If no fields provided
            TypeError: If field is from a different model

        Example:
            .. code-block:: python

                >>> query = _Query().dimensions(Sales.country, Sales.unit_price)
                >>> len(query._dimensions)
                2
        """
        if not fields:
            raise ValueError("At least one dimension must be provided")

        for f in fields:
            if not isinstance(f, Dimension | Fact):
                raise TypeError(
                    f"dimensions() requires Dimension or Fact fields, "
                    f"got {type(f).__name__}. "
                    f"Did you mean .metrics()?"
                )

            # Validate field ownership if model is set
            if self._model is not None and f.owner != self._model:
                model_name = self._model.__name__
                other_model = f.owner.__name__ if f.owner else "unknown"
                raise TypeError(
                    f"Cannot mix fields from different models in one query. "
                    f"Expected fields from {model_name}, "
                    f"got field '{f.name}' from {other_model}"
                )

        return self._replace(_dimensions=self._dimensions + fields)

    def where(self, *conditions: Predicate | None) -> _Query:
        """
        Add WHERE filter conditions to query.

        Accepts one or more Predicate objects (from field operators like
        ``Sales.country == 'US'``) or None values. Multiple conditions
        are ANDed together. None values are silently ignored, enabling
        the pattern ``query.where(pred if cond else None)``.

        Multiple ``.where()`` calls also AND together:
        ``query.where(a).where(b)`` is equivalent to ``query.where(a, b)``.

        Args:
            *conditions: Predicate objects or None (None values are no-ops)

        Returns:
            New _Query with conditions added (or same instance if all None/empty)

        Example:
            .. code-block:: python

                >>> query = _Query().where(Sales.country == 'US')
                >>> query._filters is not None
                True
        """
        # Filter out None values
        non_none = [c for c in conditions if c is not None]

        if not non_none:
            return self

        # Combine all non-None conditions with AND
        combined = non_none[0]
        for cond in non_none[1:]:
            combined = combined & cond

        # Combine with existing filters using AND
        new_filter = combined if self._filters is None else self._filters & combined
        return self._replace(_filters=new_filter)

    def order_by(self, *fields: Any) -> _Query:
        """
        Order results by fields.

        Accepts both bare Field instances (default ascending) and OrderTerm instances
        (created via field.asc() or field.desc()) for explicit direction and NULL handling.

        Args:
            *fields: One or more Field or OrderTerm objects for ordering

        Returns:
            New _Query instance with order_by fields added

        Raises:
            TypeError: If any field is not a Field or OrderTerm
            ValueError: If no fields provided

        Example:
            .. code-block:: python

                >>> query = _Query().metrics(Sales.revenue).order_by(Sales.revenue)
                >>> len(query._order_by_fields)
                1
        """
        if not fields:
            raise ValueError("At least one field must be provided")

        for f in fields:
            if not isinstance(f, Field | OrderTerm):
                raise TypeError(
                    f"order_by() requires Field or OrderTerm, got {type(f).__name__}. "
                    f"Use field.asc() or field.desc() for direction."
                )

        return self._replace(_order_by_fields=self._order_by_fields + fields)

    def limit(self, n: Any) -> _Query:
        """
        Limit results to n rows.

        Args:
            n: Maximum number of rows (must be positive)

        Returns:
            New _Query instance with limit set

        Raises:
            TypeError: If n is not an int
            ValueError: If n is not a positive integer

        Example:
            .. code-block:: python

                >>> query = _Query().limit(100)
                >>> query._limit_value
                100
        """
        if not isinstance(n, int):
            raise TypeError(f"limit() requires int, got {type(n).__name__}")

        if n <= 0:
            raise ValueError(f"limit() requires positive integer, got {n}")

        return self._replace(_limit_value=n)

    def using(self, pool_name: Any) -> _Query:
        """
        Select pool for this query by name.

        Pool is resolved lazily at .execute() time, not during query
        construction. This allows queries to be defined before pools
        are registered.

        Args:
            pool_name: Registered pool name (e.g., 'default', 'warehouse')

        Returns:
            New _Query instance with engine name set

        Raises:
            TypeError: If pool_name is not a string

        Example:
            .. code-block:: python

                >>> query = _Query().metrics(Sales.revenue).using('warehouse')
                >>> query._using
                'warehouse'
        """
        if not isinstance(pool_name, str):
            raise TypeError(
                f"using() requires pool name string, got {type(pool_name).__name__}. "
                f"Register pool first: semolina.register('name', pool, dialect='snowflake')"
            )
        return self._replace(_using=pool_name)

    def _validate_for_execution(self) -> None:
        """
        Validate query is ready for execution.

        Called by .execute() and .to_sql(), NOT during construction.
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

        Example:
            .. code-block:: python

                >>> sql = _Query().metrics(Sales.revenue).dimensions(Sales.country).to_sql()
                >>> "sales_view" in sql
                True
        """
        self._validate_for_execution()
        from semolina.engines.sql import MockDialect

        builder = MockDialect().create_builder()
        return builder.build_select(self)

    def execute(self) -> SemolinaCursor:
        """
        Execute query and return a cursor for result access.

        Tries the pool registry first (v0.3 path). If no pool is registered,
        falls back to the legacy engine registry (v0.2 backward compat).
        Pool-based execution uses standard DBAPI 2.0 cursor.execute(sql, params).

        Returns:
            SemolinaCursor wrapping the underlying DBAPI cursor. Use
            ``cursor.fetchall_rows()`` for Row objects or ``cursor.fetchall()``
            for raw tuples.

        Raises:
            ValueError: If query has no metrics or dimensions
            ValueError: If no pool or engine registered with the requested name
            Exception: If query execution fails (warehouse connection, SQL error, etc.)

        Example:
            .. code-block:: python

                cursor = (
                    Sales.query()
                    .metrics(Sales.revenue)
                    .dimensions(Sales.country)
                    .execute()
                )
                rows = cursor.fetchall_rows()
        """
        from .cursor import SemolinaCursor
        from .registry import get_engine, get_pool

        self._validate_for_execution()

        # Try pool registry first (v0.3 path)
        try:
            pool, dialect = get_pool(self._using)
        except ValueError:
            # Fall back to engine registry (v0.2 backward compat)
            engine = get_engine(self._using)
            raw_results = engine.execute(self)
            from .results import Row

            rows = [Row(data) for data in raw_results]
            adapter = _LegacyResultCursor(rows)
            return SemolinaCursor(adapter, _NoOpConn(), _NoOpPool())

        # Pool-based execution -- standard DBAPI 2.0 only
        builder = dialect.create_builder()
        sql, params = builder.build_select_with_params(self)

        conn = pool.connect()
        cur = conn.cursor()
        cur.execute(sql, params)

        return SemolinaCursor(cur, conn, pool)


class _LegacyResultCursor:
    """Minimal cursor adapter wrapping legacy engine results for SemolinaCursor."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self._pos = 0
        col_names = list(rows[0].keys()) if rows else []
        self.description: list[tuple[Any, ...]] | None = [
            (c, None, None, None, None, None, None) for c in col_names
        ] or None
        self.rowcount = len(rows)

    def fetchall(self) -> list[tuple[Any, ...]]:
        """Fetch all remaining rows as tuples."""
        result = [tuple(r[k] for k in r) for r in self._rows[self._pos :]]
        self._pos = len(self._rows)
        return result

    def fetchone(self) -> tuple[Any, ...] | None:
        """Fetch next row as tuple, or None if exhausted."""
        if self._pos >= len(self._rows):
            return None
        row = self._rows[self._pos]
        self._pos += 1
        return tuple(row[k] for k in row)

    def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        """Fetch up to size rows as tuples."""
        result = [tuple(r[k] for k in r) for r in self._rows[self._pos : self._pos + size]]
        self._pos += len(result)
        return result

    def close(self) -> None:
        """No-op close."""


class _NoOpConn:
    """No-op connection for legacy engine adapter."""

    def close(self) -> None:
        """No-op close."""


class _NoOpPool:
    """No-op pool for legacy engine adapter."""

    def close(self) -> None:
        """No-op close."""
