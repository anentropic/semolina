# Phase 2: Query Builder - Research

**Researched:** 2026-02-15
**Domain:** Immutable query builders, method chaining, Q-object filter composition
**Confidence:** HIGH

## Summary

Phase 2 requires implementing an immutable, type-safe query builder with method chaining (`.metrics()`, `.dimensions()`, `.filter()`, `.order_by()`, `.limit()`) and Q-object composition for complex filters. The standard approach combines frozen dataclasses with `dataclasses.replace()` for immutability, variadic methods (*args) for field collection, and tree-based Q-objects for boolean filter logic.

The research confirms that Django's Q-object pattern (tree structure with AND/OR/NOT connectors) and SQLAlchemy's generative select() pattern (each method returns a new instance) are the industry-standard approaches. Both prioritize immutability, composability, and type safety while maintaining intuitive fluent interfaces.

**Primary recommendation:** Use frozen dataclasses for Query with `dataclasses.replace()` for immutability, implement Q-objects as tree nodes with children and connectors, validate field types with `isinstance()` checks in variadic methods, and defer validation of empty queries to execution time (not construction time) for maximum composability.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.11+ | `dataclasses`, `typing` | Project requirement: zero dependencies |
| `dataclasses.replace()` | stdlib | Immutable updates on frozen dataclasses | Standard pattern for copy-with-changes in Python 3.7+ |
| `isinstance()` | builtin | Runtime field type validation | Only way to check descriptor types at runtime |
| Tree pattern | custom | Q-object boolean logic composition | Django Q-objects, widely adopted pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `dataclass(frozen=True)` | stdlib | Immutable Query object | Required for QRY-07 immutability guarantee |
| `typing.get_args()` | stdlib | Extract types from Union/Optional | For future type hint introspection if needed |
| `__slots__` | language feature | Memory optimization | Only if many Query instances created (unlikely) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `dataclasses.replace()` | Manual `copy.copy()` + attribute setting | Replace is faster, type-safe, and standard |
| Frozen dataclass | Mutable Query + `copy.deepcopy()` | Frozen prevents bugs, enforces immutability contract |
| Tree-based Q-objects | Lambda functions for filters | Tree structure enables inspection, optimization, and SQL generation |
| Variadic `*fields` | List argument `.metrics([Sales.revenue])` | Variadic is more Pythonic: `.metrics(A, B, C)` |

**Installation:**
```bash
# No external dependencies required
# Using Python 3.11+ stdlib only
```

## Architecture Patterns

### Recommended Project Structure
```
cubano/
├── models.py           # SemanticView base (Phase 1)
├── fields.py           # Field descriptors (Phase 1)
├── query.py            # Query class with method chaining
├── filters.py          # Q object implementation
└── __init__.py         # Public API exports
```

### Pattern 1: Frozen Dataclass with replace()
**What:** Query as immutable dataclass, methods use `dataclasses.replace()` to return new instances
**When to use:** Always - this is the foundation for immutable query building (QRY-07)

**Example:**
```python
# Source: https://docs.python.org/3/library/dataclasses.html
from dataclasses import dataclass, replace, field
from typing import Tuple

@dataclass(frozen=True)
class Query:
    """Immutable query builder for semantic views."""

    _metrics: Tuple[Metric, ...] = field(default_factory=tuple)
    _dimensions: Tuple[Dimension | Fact, ...] = field(default_factory=tuple)
    _filters: Q | None = None
    _order_by_fields: Tuple[Field, ...] = field(default_factory=tuple)
    _limit_value: int | None = None

    def metrics(self, *fields: Metric) -> 'Query':
        """Add metrics to query, returning new Query instance."""
        # Validate field types
        for f in fields:
            if not isinstance(f, Metric):
                raise TypeError(f"Expected Metric, got {type(f).__name__}")

        # Return new instance with added metrics
        return replace(self, _metrics=self._metrics + fields)

    def dimensions(self, *fields: Dimension | Fact) -> 'Query':
        """Add dimensions/facts to query, returning new Query instance."""
        for f in fields:
            if not isinstance(f, (Dimension, Fact)):
                raise TypeError(f"Expected Dimension or Fact, got {type(f).__name__}")

        return replace(self, _dimensions=self._dimensions + fields)

# Usage - each method returns a new instance
q1 = Query()
q2 = q1.metrics(Sales.revenue)  # q1 unchanged
q3 = q2.dimensions(Sales.country)  # q2 unchanged
assert q1._metrics == ()  # Original still empty
```

### Pattern 2: Q-Object Tree Structure
**What:** Q-objects as tree nodes with children and connectors (AND/OR), composable via `&`, `|`, `~` operators
**When to use:** For complex filter composition (QRY-04, QRY-08)

**Example:**
```python
# Source: https://github.com/django/django/blob/main/django/db/models/query_utils.py
from dataclasses import dataclass, field as dc_field
from typing import List, Tuple, Any

@dataclass
class Q:
    """Filter object for composing complex queries."""

    # Connector types
    AND = "AND"
    OR = "OR"

    # Tree structure
    children: List['Q | Tuple[str, Any]'] = dc_field(default_factory=list)
    connector: str = AND
    negated: bool = False

    def __init__(self, **kwargs):
        """Create Q object from keyword arguments."""
        # Children are (field, value) tuples
        self.children = [*sorted(kwargs.items())]
        self.connector = self.AND
        self.negated = False

    def _combine(self, other: 'Q', conn: str) -> 'Q':
        """Combine two Q objects with specified connector."""
        if not isinstance(other, Q):
            raise TypeError(f"Cannot combine Q with {type(other).__name__}")

        # Create new Q with both as children
        obj = Q()
        obj.connector = conn
        obj.children = [self, other]
        return obj

    def __or__(self, other: 'Q') -> 'Q':
        """Combine with OR: Q(a=1) | Q(b=2)"""
        return self._combine(other, self.OR)

    def __and__(self, other: 'Q') -> 'Q':
        """Combine with AND: Q(a=1) & Q(b=2)"""
        return self._combine(other, self.AND)

    def __invert__(self) -> 'Q':
        """Negate with NOT: ~Q(a=1)"""
        obj = Q()
        obj.children = [self]
        obj.negated = True
        return obj

# Usage
filter1 = Q(country='US') | Q(country='CA')  # OR
filter2 = Q(revenue__gt=1000) & Q(country='US')  # AND
filter3 = ~Q(country='US')  # NOT
complex_filter = (Q(country='US') | Q(country='CA')) & Q(revenue__gt=1000)
```

### Pattern 3: Variadic Methods for Field Collection
**What:** Methods accept `*fields` variadic args and validate types with `isinstance()`
**When to use:** For `.metrics()`, `.dimensions()`, `.order_by()` methods (QRY-01, QRY-02, QRY-03, QRY-05)

**Example:**
```python
# Validated at runtime since Field descriptors don't have static types
def metrics(self, *fields: Metric) -> 'Query':
    """Select metrics for aggregation.

    Args:
        *fields: One or more Metric field references

    Returns:
        New Query instance with metrics added

    Raises:
        TypeError: If any field is not a Metric
        ValueError: If no fields provided
    """
    if not fields:
        raise ValueError("At least one metric must be provided")

    # Runtime type validation (type hints alone don't enforce this)
    for f in fields:
        if not isinstance(f, Metric):
            raise TypeError(
                f"metrics() requires Metric fields, got {type(f).__name__}. "
                f"Did you mean to use .dimensions()?"
            )

    # Concatenate tuples (immutable)
    return replace(self, _metrics=self._metrics + fields)
```

### Pattern 4: Deferred Validation
**What:** Validate query completeness at execution time, not construction time
**When to use:** For empty query validation - allows composability during construction

**Example:**
```python
@dataclass(frozen=True)
class Query:
    # ... fields ...

    def _validate_for_execution(self) -> None:
        """Validate query is ready for execution.

        Called by .fetch() and .to_sql(), NOT during construction.
        Allows building queries incrementally without errors.
        """
        # Success criterion: cannot create empty queries at execution
        if not self._metrics and not self._dimensions:
            raise ValueError(
                "Query must select at least one metric or dimension. "
                "Use .metrics() or .dimensions() to add fields."
            )

    def to_sql(self) -> str:
        """Generate SQL for this query."""
        self._validate_for_execution()
        # ... SQL generation ...

    def fetch(self) -> List[Row]:
        """Execute query and return results."""
        self._validate_for_execution()
        # ... execution ...

# Usage - building empty queries is OK during construction
q = Query()  # OK - not executed yet
q = q.metrics(Sales.revenue)  # OK - adding fields
q.fetch()  # NOW validation happens
```

### Anti-Patterns to Avoid

- **Mutable Query with manual copying:** Breaks immutability guarantee (QRY-07), causes subtle bugs when queries are reused.
- **Validating at construction time:** `Query()` should be valid even when empty. Defer validation to `.fetch()` or `.to_sql()` for composability.
- **Using lists for field storage:** Lists are mutable and `replace()` won't create defensive copies. Use tuples (`Tuple[Field, ...]`).
- **Not validating field types:** Type hints on `*fields` are not enforced at runtime. Always `isinstance()` check in methods.
- **String-based filters in Q:** `Q('country=US')` is fragile. Use keyword args `Q(country='US')` to leverage Python syntax checking.
- **Forgetting to call `super().__init__(**kwargs)` in `__init_subclass__`:** If extending Query later, breaks cooperative inheritance.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Immutable copy-with-changes | Custom `_copy()` method with manual attribute copying | `dataclasses.replace()` | Handles all fields automatically, type-safe, standard since Python 3.7 |
| Field type checking | Custom type registry or string comparisons | `isinstance(field, Metric)` | Direct, fast, works with descriptor classes |
| Q-object operators | Lambda functions or string parsing | Tree structure with `__or__`, `__and__`, `__invert__` | Enables inspection, optimization, SQL generation |
| Validation messages | Generic "invalid query" errors | Specific errors with guidance: "Did you mean .dimensions()?" | Better DX, faster debugging |
| Filter composition | Nested lists `[['AND', filter1, filter2], ['OR', filter3]]` | Q-object tree with operators `(Q(a=1) & Q(b=2)) | Q(c=3)` | Pythonic, reads like logic, composable |

**Key insight:** Python 3.7+ provides all necessary primitives for immutable query builders through frozen dataclasses and `replace()`. Tree structures for boolean logic are proven patterns (Django Q, SQLAlchemy). Custom solutions add complexity without benefit.

## Common Pitfalls

### Pitfall 1: Forgetting Query Immutability in Tests
**What goes wrong:** Tests call `.metrics()` but don't capture the return value, then wonder why query is unchanged.

**Why it happens:** Developers familiar with mutable builder patterns (where methods modify `self`) forget that Cubano queries are immutable.

**How to avoid:**
```python
# BAD: Discards return value
query = Query()
query.metrics(Sales.revenue)  # Returns NEW query, but not captured!
query.fetch()  # Still empty query!

# GOOD: Capture returned query
query = Query()
query = query.metrics(Sales.revenue)
query = query.dimensions(Sales.country)
query.fetch()  # Has metrics and dimensions

# BETTER: Method chaining
query = (Query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .limit(100))
query.fetch()
```

**Warning signs:** Tests fail with "empty query" errors; intermediate query states seem to "disappear"; method calls have no effect.

### Pitfall 2: Passing Wrong Field Type to Method
**What goes wrong:** `.metrics(Sales.country)` where `country` is a Dimension raises `TypeError`.

**Why it happens:** Type hints on `*fields` are not enforced at runtime; easy to mix up field types.

**How to avoid:**
```python
def metrics(self, *fields: Metric) -> 'Query':
    """Select metrics - runtime validation required."""
    for f in fields:
        if not isinstance(f, Metric):
            # Helpful error message guides user to correct method
            raise TypeError(
                f"metrics() requires Metric fields, got {type(f).__name__} "
                f"'{getattr(f, 'name', '?')}'. "
                f"Did you mean to use .dimensions()?"
            )
    return replace(self, _metrics=self._metrics + fields)
```

**Warning signs:** `TypeError` with cryptic message; IDE autocomplete suggests field but runtime rejects it; confusion about Metric vs Dimension vs Fact.

### Pitfall 3: Q-Object Operator Precedence Confusion
**What goes wrong:** `Q(a=1) | Q(b=2) & Q(c=3)` doesn't group as expected due to Python operator precedence.

**Why it happens:** Python's `&` has higher precedence than `|`, so `a | b & c` groups as `a | (b & c)`, not `(a | b) & c`.

**How to avoid:**
```python
# BAD: Precedence surprise
Q(country='US') | Q(country='CA') & Q(revenue__gt=1000)
# Groups as: Q(country='US') | (Q(country='CA') & Q(revenue__gt=1000))

# GOOD: Explicit parentheses
(Q(country='US') | Q(country='CA')) & Q(revenue__gt=1000)

# Document this in Q-object docstring
class Q:
    """Filter object for boolean query composition.

    WARNING: Python operator precedence applies:
        & (AND) binds tighter than | (OR)
        Always use parentheses for clarity:
            (Q(a=1) | Q(b=2)) & Q(c=3)  ← GOOD
            Q(a=1) | Q(b=2) & Q(c=3)    ← CONFUSING
    """
```

**Warning signs:** Filters produce unexpected results; SQL WHERE clause has wrong parentheses; "simple" OR filter returns no results.

### Pitfall 4: Mutating Tuple Fields After Construction
**What goes wrong:** Even though Query is frozen, tuple concatenation doesn't validate at assignment time.

**Why it happens:** `replace()` doesn't re-validate field types; trusting that methods enforce types.

**How to avoid:**
```python
# This shouldn't be possible with frozen dataclass, but be defensive
@dataclass(frozen=True)
class Query:
    # Use Tuple (immutable), not List (mutable)
    _metrics: Tuple[Metric, ...] = field(default_factory=tuple)

    def metrics(self, *fields: Metric) -> 'Query':
        # Always validate before concatenating
        for f in fields:
            if not isinstance(f, Metric):
                raise TypeError(...)

        # Tuple concatenation creates NEW tuple
        return replace(self, _metrics=self._metrics + fields)

    # NEVER provide direct access to mutable internals
    # Use property with immutable return
    @property
    def selected_metrics(self) -> Tuple[Metric, ...]:
        """Public API for inspecting metrics."""
        return self._metrics  # Tuple is immutable, safe to return
```

**Warning signs:** Fields mysteriously change after query creation; tests fail sporadically; frozen dataclass errors don't trigger when they should.

### Pitfall 5: Negative or Zero Limit Values
**What goes wrong:** `.limit(0)` or `.limit(-10)` passes construction but causes errors at SQL generation or execution.

**Why it happens:** Limit validation not performed, or performed at wrong time.

**How to avoid:**
```python
def limit(self, n: int) -> 'Query':
    """Limit query results to n rows.

    Args:
        n: Maximum number of rows (must be positive)

    Raises:
        ValueError: If n is not a positive integer
    """
    if not isinstance(n, int):
        raise TypeError(f"limit() requires int, got {type(n).__name__}")

    if n <= 0:
        raise ValueError(
            f"limit() requires positive integer, got {n}. "
            f"Use a positive number to limit results."
        )

    return replace(self, _limit_value=n)

# Source: https://lewoudar.medium.com/fastapi-and-pagination-d27ad52983a
# Negative limits cause ORM to return None, leading to 500 errors
```

**Warning signs:** SQL errors with "LIMIT -10"; empty results when data exists; database driver errors about invalid limit values.

## Code Examples

Verified patterns from official sources and research:

### Complete Query Class Skeleton
```python
from dataclasses import dataclass, field, replace
from typing import Tuple, List

from .fields import Field, Metric, Dimension, Fact
from .filters import Q

@dataclass(frozen=True)
class Query:
    """Immutable query builder for semantic views.

    Each method returns a new Query instance, preserving immutability.

    Example:
        query = (Query()
            .metrics(Sales.revenue, Sales.cost)
            .dimensions(Sales.country)
            .filter(Q(country='US') | Q(country='CA'))
            .order_by(Sales.revenue)
            .limit(100))
    """

    # Private fields (use tuples for immutability)
    _metrics: Tuple[Metric, ...] = field(default_factory=tuple)
    _dimensions: Tuple[Dimension | Fact, ...] = field(default_factory=tuple)
    _filters: Q | None = None
    _order_by_fields: Tuple[Field, ...] = field(default_factory=tuple)
    _limit_value: int | None = None

    def metrics(self, *fields: Metric) -> 'Query':
        """Select metrics for aggregation (QRY-01)."""
        if not fields:
            raise ValueError("At least one metric must be provided")

        for f in fields:
            if not isinstance(f, Metric):
                raise TypeError(
                    f"metrics() requires Metric fields, got {type(f).__name__}. "
                    f"Did you mean to use .dimensions()?"
                )

        return replace(self, _metrics=self._metrics + fields)

    def dimensions(self, *fields: Dimension | Fact) -> 'Query':
        """Select dimensions/facts for grouping (QRY-02, QRY-03)."""
        if not fields:
            raise ValueError("At least one dimension must be provided")

        for f in fields:
            if not isinstance(f, (Dimension, Fact)):
                raise TypeError(
                    f"dimensions() requires Dimension or Fact fields, "
                    f"got {type(f).__name__}. "
                    f"Did you mean to use .metrics()?"
                )

        return replace(self, _dimensions=self._dimensions + fields)

    def filter(self, condition: Q) -> 'Query':
        """Add filter condition (QRY-04)."""
        if not isinstance(condition, Q):
            raise TypeError(f"filter() requires Q object, got {type(condition).__name__}")

        # Combine with existing filters using AND
        if self._filters is None:
            new_filters = condition
        else:
            new_filters = self._filters & condition

        return replace(self, _filters=new_filters)

    def order_by(self, *fields: Field) -> 'Query':
        """Order results by fields (QRY-05)."""
        if not fields:
            raise ValueError("At least one field must be provided")

        for f in fields:
            if not isinstance(f, Field):
                raise TypeError(f"order_by() requires Field, got {type(f).__name__}")

        return replace(self, _order_by_fields=self._order_by_fields + fields)

    def limit(self, n: int) -> 'Query':
        """Limit results to n rows (QRY-06)."""
        if not isinstance(n, int):
            raise TypeError(f"limit() requires int, got {type(n).__name__}")

        if n <= 0:
            raise ValueError(f"limit() requires positive integer, got {n}")

        return replace(self, _limit_value=n)

    def _validate_for_execution(self) -> None:
        """Validate query can be executed.

        Success criterion: cannot create empty queries at execution time.
        Validation deferred to execution to allow composability during construction.

        Raises:
            ValueError: If query has no metrics or dimensions
        """
        if not self._metrics and not self._dimensions:
            raise ValueError(
                "Query must select at least one metric or dimension. "
                "Use .metrics() or .dimensions() to add fields."
            )

    def to_sql(self) -> str:
        """Generate SQL for this query."""
        self._validate_for_execution()
        # Implementation in Phase 3
        raise NotImplementedError("SQL generation in Phase 3")

    def fetch(self) -> List:
        """Execute query and return results."""
        self._validate_for_execution()
        # Implementation in Phase 4
        raise NotImplementedError("Query execution in Phase 4")
```

### Complete Q-Object Implementation
```python
from dataclasses import dataclass, field as dc_field
from typing import List, Tuple, Any

@dataclass
class Q:
    """Filter object for boolean query composition.

    Q objects encapsulate filter conditions and can be composed using
    boolean operators: & (AND), | (OR), ~ (NOT).

    WARNING: Python operator precedence applies - & binds tighter than |.
    Always use parentheses for clarity:
        (Q(a=1) | Q(b=2)) & Q(c=3)  ← GOOD
        Q(a=1) | Q(b=2) & Q(c=3)    ← CONFUSING (groups as a | (b & c))

    Examples:
        # Simple condition
        Q(country='US')

        # OR condition
        Q(country='US') | Q(country='CA')

        # AND condition
        Q(country='US') & Q(revenue__gt=1000)

        # NOT condition
        ~Q(country='US')

        # Complex nested
        (Q(country='US') | Q(country='CA')) & ~Q(revenue__lt=100)
    """

    # Connector types (class constants)
    AND: str = "AND"
    OR: str = "OR"

    # Tree structure
    children: List['Q | Tuple[str, Any]'] = dc_field(default_factory=list)
    connector: str = AND
    negated: bool = False

    def __init__(self, **kwargs):
        """Create Q object from field=value keyword arguments.

        Args:
            **kwargs: Field conditions as keyword arguments
                     e.g., Q(country='US', revenue__gt=1000)
        """
        # Sort for consistent hashing/equality
        self.children = [*sorted(kwargs.items())]
        self.connector = self.AND
        self.negated = False

    def _combine(self, other: 'Q', conn: str) -> 'Q':
        """Combine two Q objects with specified connector.

        Args:
            other: Another Q object
            conn: Connector type (self.AND or self.OR)

        Returns:
            New Q object with both as children

        Raises:
            TypeError: If other is not a Q object
        """
        if not isinstance(other, Q):
            raise TypeError(
                f"Cannot combine Q with {type(other).__name__}. "
                f"Both operands must be Q objects."
            )

        # Create new Q object with both as children
        obj = Q.__new__(Q)
        obj.children = [self, other]
        obj.connector = conn
        obj.negated = False
        return obj

    def __or__(self, other: 'Q') -> 'Q':
        """Combine with OR: Q(a=1) | Q(b=2)"""
        return self._combine(other, self.OR)

    def __and__(self, other: 'Q') -> 'Q':
        """Combine with AND: Q(a=1) & Q(b=2)"""
        return self._combine(other, self.AND)

    def __invert__(self) -> 'Q':
        """Negate with NOT: ~Q(a=1)"""
        obj = Q.__new__(Q)
        obj.children = [self]
        obj.connector = self.AND  # Connector doesn't matter for single child
        obj.negated = True
        return obj

    def __repr__(self) -> str:
        """Readable representation for debugging."""
        if self.children and isinstance(self.children[0], tuple):
            # Leaf node with conditions
            conditions = ', '.join(f"{k}={v!r}" for k, v in self.children)
            prefix = "~" if self.negated else ""
            return f"{prefix}Q({conditions})"
        else:
            # Branch node with child Q objects
            op = " | " if self.connector == self.OR else " & "
            children_repr = op.join(repr(c) for c in self.children)
            prefix = "~" if self.negated else ""
            return f"{prefix}({children_repr})"
```

### Method Chaining Example
```python
# Demonstrates immutability (QRY-07) and chaining
from cubano import Query, Q
from myapp.models import Sales

# Build query incrementally (each step returns new instance)
base_query = Query()
with_metrics = base_query.metrics(Sales.revenue, Sales.cost)
with_dims = with_metrics.dimensions(Sales.country, Sales.region)
filtered = with_dims.filter(Q(country='US') | Q(country='CA'))
ordered = filtered.order_by(Sales.revenue)
final = ordered.limit(100)

# Verify immutability
assert base_query._metrics == ()  # Original unchanged
assert with_metrics._dimensions == ()  # Original unchanged

# Equivalent using method chaining
query = (Query()
    .metrics(Sales.revenue, Sales.cost)
    .dimensions(Sales.country, Sales.region)
    .filter(Q(country='US') | Q(country='CA'))
    .order_by(Sales.revenue)
    .limit(100))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Mutable builder with `.build()` | Immutable builder, each method returns new instance | Django 1.x → 2.x, SQLAlchemy 1.4 → 2.0 | Safer, composable, no accidental mutation |
| Manual `__copy__` or `copy.deepcopy()` | `dataclasses.replace()` | Python 3.7 (PEP 557) | Faster, type-safe, standard |
| String-based filters `filter('country=US')` | Q-objects `Q(country='US')` | Django 1.0+ | Type-safe, composable, inspectable |
| Validation at construction | Validation at execution | Modern query builders | Composability during construction, fail-fast at execution |
| Lists for field storage | Tuples for field storage | Best practice for immutable | Prevents accidental mutation |

**Deprecated/outdated:**
- **Mutable query builders:** Modern ORMs (Django 2+, SQLAlchemy 2.0) use immutable/generative patterns. Mutation causes subtle reuse bugs.
- **`.build()` terminal method:** Modern builders return ready-to-execute objects from methods. No separate "finalization" step.
- **String DSLs for filters:** `filter('country = "US"')` is error-prone. Q-objects leverage Python syntax for validation.

## Open Questions

1. **Should empty Query() raise error immediately?**
   - What we know: Success criterion says "cannot create empty queries" but doesn't specify when
   - What's unclear: Construction time vs execution time validation
   - Recommendation: Defer to execution (`.fetch()`, `.to_sql()`) for composability. Empty `Query()` is valid intermediate state.

2. **Should .filter() replace or combine with existing filters?**
   - What we know: Django's `.filter()` ANDs with existing filters
   - What's unclear: User expectation for Cubano's `.filter()`
   - Recommendation: Combine with AND (matches Django pattern). Multiple `.filter()` calls AND together. Use `Q(a) | Q(b)` for OR.

3. **Should order_by() support descending with `-` prefix or separate method?**
   - What we know: Django uses `.order_by('-revenue')`, SQLAlchemy uses `.desc()` method
   - What's unclear: Which is more Pythonic for field references
   - Recommendation: Defer to Phase 3 (SQL generation). Start with field-only, add `.desc()` wrapper if needed: `Sales.revenue.desc()`.

4. **Should Q-objects support lookup operators like `__gt`, `__gte`?**
   - What we know: Django uses `Q(revenue__gt=1000)` for "greater than"
   - What's unclear: Whether semantic views support WHERE clauses on metrics
   - Recommendation: Start with equality only `Q(country='US')`. Add lookup operators in Phase 3 if warehouse supports filtering metrics.

## Sources

### Primary (HIGH confidence)
- [Python dataclasses — Official Docs](https://docs.python.org/3/library/dataclasses.html) - `dataclasses.replace()` API and frozen dataclasses
- [Django Making Queries — Official Docs 6.0](https://docs.djangoproject.com/en/6.0/topics/db/queries/) - Q object composition with &, |, ~ operators
- [Django Q Object Source Code](https://github.com/django/django/blob/main/django/db/models/query_utils.py) - Tree structure implementation with children and connectors
- [SQLAlchemy Using SELECT Statements — Official Docs 2.1](https://docs.sqlalchemy.org/en/21/tutorial/data_select.html) - Generative select() pattern for immutable queries

### Secondary (MEDIUM confidence)
- [Python's dataclasses.replace() — Medium Article](https://elshad-karimov.medium.com/pythons-dataclasses-replace-a-hidden-gem-for-immutable-data-handling-e10a82f6260b) - Immutable data handling patterns
- [Modifying Immutable Objects with Chained Methods](https://www.andygibson.net/blog/article/modifying-immutable-objects-with-chained-methods/) - Builder pattern with immutability
- [FastAPI and Pagination — Medium](https://lewoudar.medium.com/fastapi-and-pagination-d27ad52983a) - Limit/offset validation best practices
- [How to Use the Builder Pattern in Python](https://www.freecodecamp.org/news/how-to-use-the-builder-pattern-in-python-a-practical-guide-for-devs/) - Method chaining and fluent interfaces

### Tertiary (LOW confidence - verify during implementation)
- [Python's Mutable vs Immutable Types — Real Python](https://realpython.com/python-mutable-vs-immutable-types/) - General immutability concepts
- [Django Q Objects — GeeksforGeeks](https://www.geeksforgeeks.org/python/how-to-perform-or-and-and-not-in-django-queryset-filtering/) - Q object examples
- [SQLAlchemy Generative Pattern — Narkive Discussion](https://sqlalchemy.narkive.com/Ucv4JCjF/generative-style-on-sql-api-layer) - Community discussion on generative design

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using Python 3.11+ stdlib only (dataclasses, isinstance), verified in official docs
- Architecture: HIGH - Patterns verified in Django Q source code, SQLAlchemy docs, and production ORMs
- Pitfalls: MEDIUM-HIGH - Immutability pitfalls documented in official sources; Q-object precedence from Python operator docs; limit validation from pagination best practices

**Research date:** 2026-02-15
**Valid until:** 2026-03-15 (30 days - stable domain, stdlib features and proven patterns unlikely to change)

**Key assumptions:**
- Python 3.11+ target (per project requirements)
- Zero external dependencies (per project requirements)
- Immutability via frozen dataclasses is strict requirement (QRY-07)
- Q-objects required for filter composition (QRY-04, QRY-08)
- Validation deferred to execution for composability
- Field type validation via isinstance() at runtime (type hints not enforced)
