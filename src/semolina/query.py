"""
Immutable query builder for semantic views.

Provides fluent method chaining for constructing queries with metrics,
dimensions, filters, ordering, and limits. Each method returns a new
frozen Query instance, guaranteeing immutability.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from .dialect import Dialect
from .fields import Dimension, Fact, Field, Metric, OrderTerm

if TYPE_CHECKING:
    from .acursor import AsyncSemolinaCursor
    from .cursor import SemolinaCursor
    from .filters import Predicate


def _term_key(term: Field[Any] | OrderTerm) -> object:
    """
    Return a hashable key identifying a selected field or order term.

    A bare :class:`Field` is keyed by identity, because ``Field.__eq__`` is the filter DSL's
    operator rather than a comparison. An :class:`OrderTerm` hashes itself correctly and is
    used as-is.

    Args:
        term: A Field or OrderTerm from one of the query's tuples.

    Returns:
        A key usable in a hash.
    """
    return term if isinstance(term, OrderTerm) else id(term)


def _same_terms(
    left: tuple[Field[Any] | OrderTerm, ...],
    right: tuple[Field[Any] | OrderTerm, ...],
) -> bool:
    """
    Compare two tuples of selected fields or order terms.

    Fields are compared with ``is`` rather than ``==``: tuple comparison falls through to
    ``Field.__eq__`` for any pair that is not already the same object, and that returns a
    truthy predicate, which would report every such tuple as equal.

    Args:
        left: One query's tuple.
        right: The other query's tuple.

    Returns:
        True when the tuples hold the same terms in the same order.
    """
    if len(left) != len(right):
        return False
    return all(
        a == b if isinstance(a, OrderTerm) and isinstance(b, OrderTerm) else a is b
        for a, b in zip(left, right, strict=True)
    )


@dataclass(frozen=True, repr=False, eq=False)
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

    def __eq__(self, other: object) -> bool:
        """
        Compare structurally, matching selected fields by identity.

        Declared ``eq=False`` on the dataclass and written out here for the reason
        :meth:`semolina.fields.OrderTerm.__eq__` gives: the generated version compared the
        field tuples with ``==``, which falls through to :meth:`Field.__eq__` for any pair
        that is not the same object, gets a truthy ``Exact`` predicate back, and calls two
        queries selecting different metrics equal.

        Filters are compared by value rather than identity: a ``Lookup`` holds the field
        *name* as a string, never a Field, so its dataclass equality is already correct.

        Args:
            other: Object to compare.

        Returns:
            True when both queries would build the same SQL against the same engine.
        """
        if not isinstance(other, _Query):
            return NotImplemented
        return (
            _same_terms(self._metrics, other._metrics)
            and _same_terms(self._dimensions, other._dimensions)
            and _same_terms(self._order_by_fields, other._order_by_fields)
            and self._filters == other._filters
            and self._limit_value == other._limit_value
            and self._using == other._using
            and self._model is other._model
        )

    def __hash__(self) -> int:
        """
        Hash the same parts :meth:`__eq__` compares, fields by identity.

        The dataclass was ``frozen=True`` and so hashable before; defining ``__eq__`` would
        otherwise set ``__hash__`` to None and silently make a query unusable as a dict key.

        Returns:
            The hash of this query.

        Raises:
            TypeError: If a filter holds an unhashable value, such as ``in_([[1]])``.
        """
        return hash(
            (
                tuple(_term_key(f) for f in self._metrics),
                tuple(_term_key(f) for f in self._dimensions),
                tuple(_term_key(f) for f in self._order_by_fields),
                self._filters,
                self._limit_value,
                self._using,
                id(self._model),
            )
        )

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
                f"using() requires engine name string, got {type(pool_name).__name__}. "
                f"Register an engine first: semolina.register('name', create_engine(config))"
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

    def to_sql(self, dialect: str | Dialect = Dialect.SNOWFLAKE) -> str:
        """
        Generate SQL for this query, for inspection and debugging.

        Renders SQL for the given dialect without connecting to a warehouse.
        Defaults to the Snowflake dialect (double quotes for identifiers,
        ``AGG()`` for metrics, identifiers folded to upper case). Pass a
        different ``dialect`` to preview another backend's SQL.

        Args:
            dialect: Dialect string or :class:`Dialect` enum value. Defaults
                to :attr:`Dialect.SNOWFLAKE`.

        Returns:
            SQL string for the selected dialect.

        Raises:
            ValueError: If query is not valid for execution

        Example:
            .. code-block:: python

                >>> sql = _Query().metrics(Sales.revenue).dimensions(Sales.country).to_sql()
                >>> "SALES_VIEW" in sql  # Snowflake folds identifiers to upper case
                True
        """
        self._validate_for_execution()
        from .dialect import resolve_dialect

        builder = resolve_dialect(dialect).create_builder()
        return builder.build_select(self)

    def execute(self) -> SemolinaCursor:
        """
        Execute query and return a cursor for result access.

        Looks up the registered Engine (see :func:`semolina.register`) and runs
        the query through its owned ADBC pool via ``Engine.execute``.

        Returns:
            SemolinaCursor wrapping the underlying DBAPI cursor. Use
            ``cursor.fetchall_rows()`` for Row objects or ``cursor.fetchall()``
            for raw tuples.

        Raises:
            ValueError: If query has no metrics or dimensions
            ValueError: If no engine is registered with the requested name
            Exception: If query execution fails (warehouse connection, SQL error, etc.)

        Example:
            .. code-block:: python

                with (
                    Sales.query()
                    .metrics(Sales.revenue)
                    .dimensions(Sales.country)
                    .execute()
                ) as cursor:
                    rows = cursor.fetchall_rows()
        """
        from .registry import get_engine

        self._validate_for_execution()

        engine = get_engine(self._using)
        return engine.execute(self)

    async def aexecute(self) -> AsyncSemolinaCursor:
        """
        Execute query on an async engine and return an open cursor.

        The async twin of :meth:`execute`. Looks up the registered AsyncEngine
        (see :func:`semolina.register_async_engine`) and runs the query through
        its owned async ADBC pool via ``AsyncEngine.aexecute``, awaiting rather
        than blocking the event loop.

        Because the synchronous and async registries are separate stores,
        :meth:`using` resolves against the async registry here and against the
        synchronous one in :meth:`execute`. The same name may therefore
        legitimately hold an engine of each kind, and neither lookup falls back
        to the other's store.

        The returned cursor is already open, so the call site reads
        ``async with await (...).aexecute() as cursor:``. Closing it is what
        returns the connection to the pool.

        Returns:
            AsyncSemolinaCursor wrapping the underlying async ADBC cursor. Use
            ``await cursor.fetchall_rows()`` for Row objects, ``async for row in
            cursor`` to stream them, or ``await cursor.fetchall()`` for raw
            tuples.

        Raises:
            ValueError: If query has no metrics or dimensions. Raised before any
                connection is checked out, so an invalid query never consumes a
                pool slot.
            ValueError: If no async engine is registered with the requested name
            Exception: If query execution fails (warehouse connection, SQL error, etc.)

        Example:
            .. code-block:: python

                async with await (
                    Sales.query()
                    .metrics(Sales.revenue)
                    .dimensions(Sales.country)
                    .aexecute()
                ) as cursor:
                    rows = await cursor.fetchall_rows()
        """
        from .registry import get_async_engine

        self._validate_for_execution()

        engine = get_async_engine(self._using)
        return await engine.aexecute(self)
