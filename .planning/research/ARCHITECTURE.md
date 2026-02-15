# Architecture Research: Python ORM/Query Builder Patterns

**Dimension**: Architecture
**Milestone**: Greenfield - How are Python ORM / query builder libraries typically structured?
**Date**: 2026-02-14

## Executive Summary

Python ORM and query builder libraries follow established architectural patterns that separate concerns into distinct layers: model definition, query construction, SQL generation, execution, and result mapping. Analysis of SQLAlchemy, Django ORM, and ibis reveals common components that cubano should adopt:

**Key Components**:
1. **Model Layer**: Metaclass-based declarative models with field descriptors
2. **Query Builder**: Immutable chain pattern with lazy evaluation
3. **SQL Generator**: Backend-specific compiler/visitor pattern
4. **Engine/Backend**: Abstract connection and execution layer
5. **Registry**: Global state management for engine lookup
6. **Result Mapper**: Dynamic row objects or dataclass generation

**Recommended Build Order for Cubano**:
1. Field descriptors and metaclass foundation
2. Basic query object with immutable chain
3. Mock backend for testing
4. SQL generator with visitor pattern
5. Engine ABC and registry
6. Result Row class
7. Real backends (Snowflake, Databricks)

---

## 1. Model Definition Layer

### Pattern Analysis

**SQLAlchemy (Declarative)**:
- Uses `DeclarativeMeta` metaclass to process class definitions
- Field descriptors (`Column`, `relationship`) are introspected at class creation time
- Creates a `Table` metadata object and binds columns to it
- Stores metadata in `__table__`, `__mapper__` class attributes
- Descriptor pattern for field access (reads/writes to instance state)

**Django ORM**:
- `ModelBase` metaclass processes `Field` instances
- Separates field definition from database columns via `db_column` parameter
- Stores `_meta` Options object with field registry
- Field descriptors handle both Python value access and SQL generation
- Uses `__init_subclass__` hook for inheritance

**ibis**:
- No metaclass - functional API with explicit schema definition
- Table expressions created via `ibis.table(name, schema)`
- Schema is immutable after creation
- Column references are expression nodes, not descriptors

**Recommended for Cubano**:

```python
# Metaclass pattern with explicit view name argument
class SemanticViewMeta(type):
    def __new__(mcs, name, bases, namespace, **kwargs):
        # Extract view='sales' from class definition
        view_name = kwargs.get('view')

        # Collect field descriptors
        fields = {}
        for key, value in namespace.items():
            if isinstance(value, (Metric, Dimension, Fact)):
                value._set_name(key)  # Store field name
                fields[key] = value

        # Store metadata
        cls = super().__new__(mcs, name, bases, namespace)
        cls._meta = ViewMeta(
            view_name=view_name,
            fields=fields,
            metrics={k: v for k, v in fields.items() if isinstance(v, Metric)},
            dimensions={k: v for k, v in fields.items() if isinstance(v, Dimension)},
            facts={k: v for k, v in fields.items() if isinstance(v, Fact)},
        )
        return cls

class SemanticView(metaclass=SemanticViewMeta):
    @classmethod
    def query(cls, using: str | None = None) -> Query:
        return Query(view_meta=cls._meta, using=using)
```

**Why This Works**:
- Metaclass with `**kwargs` enables clean syntax: `class Sales(SemanticView, view='sales')`
- Field descriptors are introspected once at class creation (no runtime overhead)
- `_meta` object encapsulates all view metadata (mirrors Django pattern)
- Fields remain class attributes for type-safe references: `Sales.revenue`

---

## 2. Field Descriptors

### Pattern Analysis

**SQLAlchemy**:
- `Column` objects are descriptors implementing `__get__` and `__set__`
- On class access: returns the Column itself (for query building)
- On instance access: reads from instance's `__dict__` state
- Hybrid behavior: `User.name` vs `user_instance.name`

**Django**:
- `Field` base class with descriptor protocol
- Class access returns the Field (for queryset filters)
- Instance access reads from `instance.__dict__[field.attname]`
- Uses `contribute_to_class()` hook for metaclass integration

**Recommended for Cubano**:

```python
class FieldDescriptor:
    """Base class for Metric, Dimension, Fact"""

    def __init__(self, column_name: str | None = None):
        self.column_name = column_name  # Override default name
        self.attname: str | None = None  # Set by metaclass

    def _set_name(self, name: str) -> None:
        """Called by metaclass during class construction"""
        self.attname = name
        if self.column_name is None:
            self.column_name = name

    def __get__(self, instance, owner):
        # Always return self for query building
        # Cubano models are not instantiated (class-only API)
        return self

    def __repr__(self):
        return f"{self.__class__.__name__}({self.attname!r})"

class Metric(FieldDescriptor):
    """Aggregated measure - wrapped in AGG() or MEASURE()"""
    pass

class Dimension(FieldDescriptor):
    """Groupable attribute"""
    pass

class Fact(FieldDescriptor):
    """Non-aggregated value (treated as dimension in queries)"""
    pass
```

**Why No Instance Access**:
- Cubano models represent views, not row objects
- Query API is class-based: `Sales.query().metrics(Sales.revenue)`
- Results are separate `Row` objects, not model instances
- Simpler than Django/SQLAlchemy dual-mode descriptors

---

## 3. Query Builder (Immutable Chain)

### Pattern Analysis

**SQLAlchemy Core**:
- `Select` object is immutable
- Each method (`where()`, `order_by()`) calls `_generate()` to create a shallow copy
- Uses `ClauseElement` base class with visitor pattern for SQL generation
- Lazy evaluation - SQL is generated only when executed

**Django QuerySet**:
- `QuerySet` is immutable via `_clone()` pattern
- Methods return new QuerySet with updated `._query` state
- Uses `Query` object to accumulate filters, annotations, etc.
- Lazy evaluation - hits database only on iteration or `.get()`, `.count()`, etc.

**ibis**:
- Expression tree is immutable
- Each operation creates new expression nodes
- `Table.filter()`, `.select()`, etc. return new Table expressions
- Backend-specific compilation happens at `.execute()` time

**Recommended for Cubano**:

```python
from dataclasses import dataclass, replace
from typing import Sequence

@dataclass(frozen=True)  # Immutability via frozen dataclass
class Query:
    view_meta: ViewMeta
    _metrics: tuple[Metric, ...] = ()
    _dimensions: tuple[Dimension | Fact, ...] = ()
    _filters: tuple[Q, ...] = ()
    _order_by: tuple[tuple[FieldDescriptor, bool], ...] = ()  # (field, is_desc)
    _limit: int | None = None
    _using: str | None = None

    def metrics(self, *fields: Metric) -> Query:
        """Add metrics to selection (immutable)"""
        return replace(self, _metrics=self._metrics + fields)

    def dimensions(self, *fields: Dimension | Fact) -> Query:
        """Add dimensions/facts to selection (immutable)"""
        return replace(self, _dimensions=self._dimensions + fields)

    def filter(self, *args: Q, **kwargs) -> Query:
        """Add filters (immutable)"""
        filters = self._filters
        if args:
            filters = filters + args
        if kwargs:
            filters = filters + (Q(**kwargs),)
        return replace(self, _filters=filters)

    def order_by(self, *fields: FieldDescriptor) -> Query:
        """Add ordering (immutable)"""
        ordering = []
        for field in fields:
            if isinstance(field, str) and field.startswith('-'):
                # Handle '-revenue' syntax
                raise TypeError("Use field.desc() instead of '-fieldname'")
            is_desc = getattr(field, '_desc', False)
            ordering.append((field, is_desc))
        return replace(self, _order_by=self._order_by + tuple(ordering))

    def limit(self, n: int) -> Query:
        """Set result limit (immutable)"""
        return replace(self, _limit=n)

    def using(self, engine_name: str) -> Query:
        """Select engine for execution (immutable)"""
        return replace(self, _using=engine_name)

    def fetch(self) -> list[Row]:
        """Execute query and return results"""
        from .registry import get_engine
        engine = get_engine(self._using)
        sql = self.to_sql(engine.dialect)
        raw_results = engine.execute(sql)
        return [Row(data) for data in raw_results]

    def to_sql(self, dialect: str | None = None) -> str:
        """Generate SQL without executing"""
        from .compiler import compile_query
        return compile_query(self, dialect=dialect or 'generic')
```

**Key Patterns**:
- `frozen=True` dataclass enforces immutability at runtime
- `replace()` creates shallow copies efficiently
- All query state is stored in private `_fields` attributes
- Lazy evaluation: SQL generation deferred until `fetch()` or `to_sql()`
- Engine resolution happens at execution time, not query construction

---

## 4. Filter Composition (Q Objects)

### Pattern Analysis

**Django Q Objects**:
- Tree structure with AND/OR/NOT nodes
- Overloads `&`, `|`, `~` operators
- Serializable to SQL via recursive visitor
- Supports nested logic: `Q(a=1) & (Q(b=2) | Q(b=3))`

**SQLAlchemy**:
- Uses `and_()`, `or_()`, `not_()` functions
- Column comparisons return `BinaryExpression` objects
- Natural operator overloading: `User.name == 'alice'` returns expression
- Composable via `&`, `|`, `~` on expressions

**Recommended for Cubano**:

```python
from dataclasses import dataclass
from typing import Any
from enum import Enum

class QOp(Enum):
    AND = 'AND'
    OR = 'OR'
    NOT = 'NOT'

@dataclass
class Q:
    """Filter expression tree"""
    children: tuple['Q', ...] = ()
    op: QOp = QOp.AND
    filters: dict[str, Any] = None  # Leaf node: field=value pairs

    def __init__(self, *args: 'Q', **kwargs):
        if args and kwargs:
            raise ValueError("Cannot mix Q objects and keyword filters")

        if args:
            # Combining Q objects: Q(q1, q2) => AND
            self.children = args
            self.op = QOp.AND
            self.filters = None
        else:
            # Leaf node: Q(country='US', year=2024)
            self.children = ()
            self.op = QOp.AND
            self.filters = kwargs

    def __and__(self, other: 'Q') -> 'Q':
        """Q1 & Q2"""
        q = Q()
        q.children = (self, other)
        q.op = QOp.AND
        q.filters = None
        return q

    def __or__(self, other: 'Q') -> 'Q':
        """Q1 | Q2"""
        q = Q()
        q.children = (self, other)
        q.op = QOp.OR
        q.filters = None
        return q

    def __invert__(self) -> 'Q':
        """~Q1"""
        q = Q()
        q.children = (self,)
        q.op = QOp.NOT
        q.filters = None
        return q
```

**Usage**:
```python
# Simple filter
query.filter(Q(country='US'))

# Complex composition
query.filter(
    Q(country='US') | Q(country='CA'),
    Q(year=2024),  # Multiple args are AND'd together
)

# Nested logic
query.filter(
    (Q(country='US') & Q(state='CA')) | Q(country='CA')
)
```

---

## 5. SQL Generation (Compiler/Visitor Pattern)

### Pattern Analysis

**SQLAlchemy**:
- Visitor pattern over `ClauseElement` tree
- Dialect-specific compilers subclass `SQLCompiler`
- Recursive traversal: `self.process(element, **kwargs)`
- Compile-time context (aliasing, subquery nesting, etc.)

**Django**:
- `SQLCompiler` class per backend (PostgreSQL, MySQL, etc.)
- `as_sql()` method on each expression/lookup/query node
- Returns `(sql, params)` tuple for parameterized queries
- Vendor-specific SQL built via subclass overrides

**ibis**:
- Backend registry maps to compiler classes
- Expression tree compiled via visitor pattern
- Each backend provides dialect-specific SQL generation
- Clear separation: expressions (frontend) vs compilation (backend)

**Recommended for Cubano**:

```python
# compiler.py
from typing import Protocol

class SQLDialect(Protocol):
    """Backend-specific SQL generation rules"""
    def compile_metric(self, field: Metric) -> str: ...
    def compile_filter(self, q: Q) -> tuple[str, dict]: ...

class SnowflakeDialect:
    def compile_metric(self, field: Metric) -> str:
        return f"AGG({field.column_name})"

    def compile_filter(self, q: Q) -> tuple[str, dict]:
        # Returns (sql, params) for parameterized queries
        if q.filters:
            conditions = [f"{k} = :{k}" for k in q.filters.keys()]
            return (" AND ".join(conditions), q.filters)

        if q.op == QOp.AND:
            parts = [self.compile_filter(child) for child in q.children]
            sql = " AND ".join(f"({p[0]})" for p in parts)
            params = {k: v for part in parts for k, v in part[1].items()}
            return (sql, params)

        # Similar for OR, NOT...

class DatabricksDialect:
    def compile_metric(self, field: Metric) -> str:
        return f"MEASURE({field.column_name})"

    # ... same pattern

def compile_query(query: Query, dialect: str = 'snowflake') -> str:
    """Generate SQL from Query object"""
    dialect_obj = _get_dialect(dialect)

    # Build SELECT clause
    select_fields = []
    for dim in query._dimensions:
        select_fields.append(dim.column_name)
    for metric in query._metrics:
        select_fields.append(dialect_obj.compile_metric(metric))

    sql = f"SELECT {', '.join(select_fields)}"
    sql += f" FROM {query.view_meta.view_name}"

    # Build WHERE clause
    if query._filters:
        combined = Q(*query._filters)  # AND all filters
        where_sql, params = dialect_obj.compile_filter(combined)
        sql += f" WHERE {where_sql}"
        # Note: would need to substitute params for non-parameterized execution

    # Build GROUP BY
    if query._dimensions:
        group_by = ", ".join(d.column_name for d in query._dimensions)
        sql += f" GROUP BY {group_by}"

    # Build ORDER BY
    if query._order_by:
        order_terms = []
        for field, is_desc in query._order_by:
            term = field.column_name
            if is_desc:
                term += " DESC"
            order_terms.append(term)
        sql += f" ORDER BY {', '.join(order_terms)}"

    # Build LIMIT
    if query._limit:
        sql += f" LIMIT {query._limit}"

    return sql
```

**Key Patterns**:
- Dialect object encapsulates backend-specific SQL syntax
- Query compilation is pure function (no mutation)
- Visitor pattern for recursive filter tree traversal
- Parameterized queries for safety (though warehouses may not support)

---

## 6. Engine Abstraction

### Pattern Analysis

**SQLAlchemy**:
- `Engine` owns connection pool
- `Connection` represents single DB connection
- `Dialect` handles backend-specific SQL and type conversion
- Clear separation: Engine (pooling) vs Dialect (SQL generation)

**Django**:
- `DatabaseWrapper` per backend (PostgreSQL, MySQL, etc.)
- Lazy connection creation (opens on first query)
- Settings-driven configuration (no explicit Engine object)
- Connection pooling delegated to backend driver

**ibis**:
- `Backend` abstract class with `compile()` and `execute()` methods
- Backends are stateless compilers (connection is separate concern)
- Clear API: `backend.compile(expr)` and `backend.execute(expr)`

**Recommended for Cubano**:

```python
# engine.py
from abc import ABC, abstractmethod
from typing import Any

class Engine(ABC):
    """Abstract base class for backend execution engines"""

    dialect: str  # 'snowflake', 'databricks', 'mock'

    @abstractmethod
    def execute(self, sql: str) -> list[dict[str, Any]]:
        """Execute SQL and return raw results as list of dicts"""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close connections and clean up resources"""
        pass

class MockEngine(Engine):
    """In-memory backend for testing"""

    dialect = 'mock'

    def __init__(self):
        self._data: dict[str, list[dict]] = {}

    def seed(self, view_name: str, rows: list[dict]) -> None:
        """Populate mock data for a view"""
        self._data[view_name] = rows

    def execute(self, sql: str) -> list[dict[str, Any]]:
        """Parse SQL and return mock results"""
        # Simplified: real implementation would parse SQL
        # For testing, could use DuckDB or SQLite in-memory
        return self._data.get('sales', [])

    def close(self) -> None:
        pass

class SnowflakeEngine(Engine):
    """Snowflake backend"""

    dialect = 'snowflake'

    def __init__(self, account: str, user: str, password: str, **kwargs):
        # Lazy import to avoid required dependency
        import snowflake.connector
        self._conn = snowflake.connector.connect(
            account=account,
            user=user,
            password=password,
            **kwargs
        )

    def execute(self, sql: str) -> list[dict[str, Any]]:
        cursor = self._conn.cursor()
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def close(self) -> None:
        self._conn.close()

class DatabricksEngine(Engine):
    """Databricks SQL backend"""

    dialect = 'databricks'

    def __init__(self, server_hostname: str, http_path: str, access_token: str):
        from databricks import sql
        self._conn = sql.connect(
            server_hostname=server_hostname,
            http_path=http_path,
            access_token=access_token,
        )

    def execute(self, sql: str) -> list[dict[str, Any]]:
        cursor = self._conn.cursor()
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def close(self) -> None:
        self._conn.close()
```

**Key Design Decisions**:
- Engine ABC defines minimal interface: `execute()` and `close()`
- Dialect is an attribute, not a separate object (simpler)
- Connection management is internal to Engine (not exposed)
- Lazy imports for backend drivers (zero required dependencies)
- MockEngine for testing without warehouse connection

---

## 7. Registry Pattern

### Pattern Analysis

**SQLAlchemy**:
- No global registry for engines (explicit passing)
- Declarative base has global registry for mapped classes
- Scoped session factory for thread-local session management

**Django**:
- `settings.DATABASES` dict defines connections
- `django.db.connections` is a thread-local connection handler
- Lazy connection creation on first query
- `using()` method on QuerySet to select database

**Recommended for Cubano**:

```python
# registry.py
_engines: dict[str, Engine] = {}
_default: str = 'default'

def register(engine: Engine, name: str = 'default', *, set_default: bool = False) -> None:
    """Register an engine by name"""
    _engines[name] = engine
    if set_default or name == 'default':
        global _default
        _default = name

def get_engine(name: str | None = None) -> Engine:
    """Get engine by name (None returns default)"""
    if name is None:
        name = _default

    if name not in _engines:
        raise ValueError(f"No engine registered with name {name!r}")

    return _engines[name]

def unregister(name: str) -> None:
    """Remove engine from registry"""
    if name in _engines:
        del _engines[name]

def reset() -> None:
    """Clear all registered engines (for testing)"""
    global _engines, _default
    _engines = {}
    _default = 'default'
```

**Usage**:
```python
# Application setup
import cubano
from cubano import SnowflakeEngine, DatabricksEngine

cubano.register(
    SnowflakeEngine(account='xyz', user='...', password='...'),
    name='default'
)

cubano.register(
    DatabricksEngine(server_hostname='...', http_path='...', access_token='...'),
    name='databricks'
)

# Query usage - implicit default
results = Sales.query().metrics(Sales.revenue).fetch()

# Explicit engine selection
results = Sales.query().using('databricks').metrics(Sales.revenue).fetch()
```

**Why This Pattern**:
- Simple flat dict (no nesting needed for single-framework use)
- Lazy resolution: queries can be defined before registry is populated
- Thread-safe if engines are thread-safe (warehouse drivers handle this)
- Explicit registration at app startup (Django-like but framework-agnostic)

---

## 8. Result Mapping

### Pattern Analysis

**SQLAlchemy**:
- Result rows are `Row` objects (tuple-like with named access)
- Supports both positional (`row[0]`) and attribute (`row.name`) access
- ORM mode maps to model instances via mapper
- Core mode returns lightweight Row objects

**Django**:
- QuerySet returns model instances by default
- `.values()` returns dicts
- `.values_list()` returns tuples
- Model instances have full ORM behavior (save, delete, etc.)

**ibis**:
- Returns backend-native results (DataFrame, Arrow table, etc.)
- No custom Row class
- Relies on existing data structures

**Recommended for Cubano**:

```python
# results.py
from typing import Any

class Row:
    """Dynamic result row with attribute and dict-style access"""

    def __init__(self, data: dict[str, Any]):
        # Store in __dict__ for attribute access
        object.__setattr__(self, '_data', data)

    def __getattr__(self, name: str) -> Any:
        """Attribute access: row.revenue"""
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(f"Row has no field {name!r}")

    def __getitem__(self, key: str) -> Any:
        """Dict-style access: row['revenue']"""
        return self._data[key]

    def __setattr__(self, name: str, value: Any) -> None:
        """Prevent mutation after creation"""
        if name != '_data':
            raise AttributeError("Row objects are immutable")
        object.__setattr__(self, name, value)

    def __repr__(self) -> str:
        fields = ", ".join(f"{k}={v!r}" for k, v in self._data.items())
        return f"Row({fields})"

    def __iter__(self):
        """Iteration over values"""
        return iter(self._data.values())

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def to_dict(self) -> dict[str, Any]:
        """Convert to plain dict"""
        return self._data.copy()
```

**Why Custom Row Class**:
- Result shape is dynamic (depends on selected fields)
- Can't use static dataclass or Pydantic model (field names unknown at definition time)
- Provides both attribute access (ergonomic) and dict access (compatibility)
- Immutable to prevent accidental mutation
- Lightweight (thin wrapper over dict)

**Future Enhancement**:
- Could generate typed dataclass at runtime based on selected fields
- Would enable type checking: `reveal_type(row.revenue)` → `float`
- But adds complexity - defer to later milestone

---

## 9. Component Dependencies and Build Order

### Dependency Graph

```
┌─────────────────┐
│ Field Descriptors│
│ (Metric, Dim, Fact)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Metaclass     │
│ (SemanticViewMeta)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐         ┌──────────────┐
│  Query Builder  │◄────────┤  Q Objects   │
│   (Query)       │         └──────────────┘
└────────┬────────┘
         │
         ├────────────────────┬─────────────────┐
         ▼                    ▼                 ▼
┌─────────────────┐  ┌──────────────┐  ┌──────────────┐
│  SQL Compiler   │  │   Registry   │  │  Row Class   │
└────────┬────────┘  └──────┬───────┘  └──────────────┘
         │                  │
         ▼                  ▼
┌─────────────────────────────────┐
│       Engine ABC                │
│  (execute, close, dialect)      │
└──────────────┬──────────────────┘
               │
               ├──────────────┬─────────────────┐
               ▼              ▼                 ▼
      ┌────────────┐  ┌────────────┐  ┌────────────┐
      │ MockEngine │  │ Snowflake  │  │ Databricks │
      └────────────┘  └────────────┘  └────────────┘
```

### Build Order (Recommended)

**Phase 1: Foundation (No External Dependencies)**
1. **Field Descriptors** (`fields.py`)
   - Implement `FieldDescriptor`, `Metric`, `Dimension`, `Fact`
   - Add `_set_name()` hook for metaclass integration
   - Test: field creation and naming

2. **Metaclass** (`metaclass.py`)
   - Implement `SemanticViewMeta` with `**kwargs` support
   - Create `ViewMeta` dataclass for metadata storage
   - Test: class definition with `view='name'` syntax

3. **Q Objects** (`filters.py`)
   - Implement `Q` class with tree structure
   - Overload `&`, `|`, `~` operators
   - Test: filter composition logic

**Phase 2: Query Building**
4. **Query Builder** (`query.py`)
   - Implement immutable `Query` dataclass
   - Add `.metrics()`, `.dimensions()`, `.filter()`, etc.
   - Test: query chain immutability and state accumulation

**Phase 3: Execution Layer**
5. **Engine ABC** (`engine.py`)
   - Define `Engine` abstract base class
   - Implement `MockEngine` with in-memory data
   - Test: basic execute() contract

6. **Registry** (`registry.py`)
   - Implement global engine registry
   - Add `register()`, `get_engine()` functions
   - Test: registration and lazy resolution

**Phase 4: SQL Generation**
7. **SQL Compiler** (`compiler.py`)
   - Implement dialect classes (Snowflake, Databricks, Mock)
   - Build `compile_query()` function
   - Test: SQL generation for each dialect against mock data

**Phase 5: Results**
8. **Row Class** (`results.py`)
   - Implement dynamic `Row` with dual access modes
   - Test: attribute access, dict access, immutability

**Phase 6: Integration**
9. **Wire Query → Compiler → Engine → Results**
   - Implement `Query.fetch()` and `Query.to_sql()`
   - Test: end-to-end query execution against MockEngine

**Phase 7: Real Backends (Optional Dependencies)**
10. **SnowflakeEngine** (`backends/snowflake.py`)
    - Implement with lazy import of `snowflake.connector`
    - Test: against real Snowflake instance or VCR recorded responses

11. **DatabricksEngine** (`backends/databricks.py`)
    - Implement with lazy import of `databricks.sql`
    - Test: against real Databricks or mocked responses

**Why This Order**:
- Bottom-up: build foundation before higher layers
- MockEngine enables testing entire stack without external dependencies
- Real backends are last (require warehouse access)
- Each phase is independently testable

---

## 10. Data Flow

### Query Construction Flow

```
User Code                    Cubano Internals
─────────                    ─────────────────

Sales.query()
    │
    └──> Query.__init__(view_meta=Sales._meta)
             │
             └──> Returns Query(view_meta=..., _metrics=(), ...)

.metrics(Sales.revenue)
    │
    └──> Query.metrics(Sales.revenue)
             │
             └──> replace(self, _metrics=self._metrics + (Sales.revenue,))
                      │
                      └──> Returns new Query object

.dimensions(Sales.country)
    │
    └──> Query.dimensions(Sales.country)
             │
             └──> replace(self, _dimensions=self._dimensions + (Sales.country,))
                      │
                      └──> Returns new Query object

.filter(Q(year=2024))
    │
    └──> Query.filter(Q(year=2024))
             │
             └──> replace(self, _filters=self._filters + (Q(year=2024),))
                      │
                      └──> Returns new Query object
```

### Query Execution Flow

```
.fetch()
    │
    ├──> get_engine(self._using)
    │        │
    │        └──> registry._engines[name]  (lazy resolution)
    │                 │
    │                 └──> Returns Engine instance
    │
    ├──> self.to_sql(engine.dialect)
    │        │
    │        └──> compile_query(self, dialect='snowflake')
    │                 │
    │                 ├──> dialect.compile_metric(field) for each metric
    │                 ├──> dialect.compile_filter(q) for each filter
    │                 └──> Returns SQL string
    │
    ├──> engine.execute(sql)
    │        │
    │        └──> Backend-specific execution
    │                 │
    │                 └──> Returns list[dict[str, Any]]
    │
    └──> [Row(data) for data in raw_results]
             │
             └──> Returns list[Row]
```

### Component Communication

**Model Layer → Query Builder**:
- Model metaclass creates `ViewMeta` object
- `Sales.query()` passes `ViewMeta` to Query constructor
- Field descriptors (Sales.revenue) passed to `.metrics()`, etc.

**Query Builder → SQL Compiler**:
- Query object passed to `compile_query()`
- Compiler reads `._metrics`, `._dimensions`, `._filters`, etc.
- Returns SQL string

**Query Builder → Registry → Engine**:
- Query calls `get_engine(self._using)` at fetch time
- Registry returns Engine instance
- Query calls `engine.execute(sql)`

**Engine → Results**:
- Engine returns `list[dict[str, Any]]` (raw rows)
- Query wraps each dict in `Row` object
- Returns `list[Row]` to user

---

## 11. Cross-Cutting Concerns

### Error Handling

**Where Errors Occur**:
1. Model definition time (metaclass):
   - Missing `view='name'` argument
   - Duplicate field names
   - Invalid field types

2. Query construction time:
   - Wrong field type (metric in dimensions, etc.)
   - Invalid filter syntax

3. SQL compilation time:
   - Unsupported operations for dialect
   - Invalid field references

4. Execution time:
   - Connection failures
   - SQL syntax errors (warehouse rejection)
   - No engine registered

**Recommended Strategy**:
```python
# Custom exceptions
class CubanoError(Exception):
    """Base exception for all cubano errors"""

class ConfigurationError(CubanoError):
    """Engine registration or configuration issues"""

class QueryError(CubanoError):
    """Invalid query construction"""

class ExecutionError(CubanoError):
    """Query execution failures"""

# Usage in code
def get_engine(name: str | None = None) -> Engine:
    if name is None:
        name = _default
    if name not in _engines:
        raise ConfigurationError(
            f"No engine registered with name {name!r}. "
            f"Available engines: {list(_engines.keys())}"
        )
    return _engines[name]
```

### Type Safety

**Type Hints**:
- All public APIs fully typed
- Field descriptors have generic type parameters (future):
  ```python
  class Metric(FieldDescriptor, Generic[T]):
      pass

  class Sales(SemanticView, view='sales'):
      revenue: Metric[float] = Metric()
  ```
- Query builder methods return `Query` (enables chaining)
- Row class typed as `Row` (no generic, dynamic fields)

**Runtime Validation**:
- Metaclass validates field types at class creation
- Query builder validates field ownership (field belongs to view)
- Compiler validates operation support per dialect

### Testing Strategy

**Levels**:
1. **Unit tests**: Each component in isolation
   - Field descriptors, metaclass, Q objects, Row class
   - Mock external dependencies

2. **Integration tests**: Component interactions
   - Query construction → SQL generation
   - Engine → Result mapping
   - Use MockEngine exclusively

3. **Backend tests**: Real warehouse integration
   - Optional (require credentials)
   - Use VCR or similar for recorded responses
   - Mark as slow/integration

**Test Organization**:
```
tests/
├── unit/
│   ├── test_fields.py
│   ├── test_metaclass.py
│   ├── test_query.py
│   ├── test_filters.py
│   ├── test_compiler.py
│   ├── test_registry.py
│   └── test_results.py
├── integration/
│   ├── test_query_execution.py
│   └── test_sql_generation.py
└── backends/
    ├── test_snowflake.py  (marked slow)
    └── test_databricks.py (marked slow)
```

---

## 12. Alternative Architectures Considered

### 1. Decorator-Based Models (Rejected)

```python
@semantic_view('sales')
class Sales:
    revenue = Metric()
```

**Pros**: Familiar pattern
**Cons**: Less clean than metaclass with kwargs; decorator can't intercept class creation early enough for field introspection

### 2. Separate Engine + Dialect (Rejected)

```python
engine = Engine(dialect=SnowflakeDialect(), connection=...)
```

**Pros**: Mirrors SQLAlchemy pattern
**Cons**: More complex; dialect is backend-specific anyway (no mix-and-match)

**Decision**: Dialect is an attribute of Engine, not a separate object

### 3. Mutable Query Builder (Rejected)

```python
query = Sales.query()
query.metrics(Sales.revenue)  # mutates query
```

**Pros**: Slightly more performant (no copying)
**Cons**: Surprising behavior (Django learned this lesson); hard to debug; not thread-safe

**Decision**: Immutable via frozen dataclass

### 4. String-Based Field References (Rejected)

```python
query.metrics('revenue')
```

**Pros**: Shorter syntax
**Cons**: No type safety, no IDE autocomplete, runtime errors

**Decision**: Field references only (`Sales.revenue`)

### 5. Parameterized Queries (Deferred)

```python
sql, params = query.to_sql()
engine.execute(sql, params)
```

**Pros**: SQL injection prevention
**Cons**: Not all warehouse backends support parameterized queries; adds complexity

**Decision**: Inline values in SQL for now; revisit in later milestone

---

## 13. Open Questions and Future Work

### Open Questions

1. **Async Support**:
   - Should `Query` have both `.fetch()` and `.fetch_async()`?
   - Or separate `AsyncQuery` class?
   - Decision: Defer to later milestone (validate sync API first)

2. **DataFrame Support**:
   - `.fetch_df()` returning Pandas/Polars?
   - Which library? User-configurable?
   - Decision: Defer to later milestone

3. **Type Hints for Row**:
   - Can we generate TypedDict at runtime based on selected fields?
   - Would enable `reveal_type(row.revenue)` → `float`
   - Decision: Explore in later milestone

4. **Connection Pooling**:
   - Should Engine manage pools or delegate to driver?
   - Decision: Delegate to driver (Snowflake connector handles this)

5. **Multi-View Joins**:
   - How to express joins between semantic views?
   - Is this even supported by Snowflake/Databricks?
   - Decision: Out of scope for initial milestone

### Future Enhancements

1. **Query Introspection**:
   - `.explain()` to show query plan
   - `.count()` for fast row counting
   - `.exists()` for boolean checks

2. **Result Formats**:
   - `.fetch_df()` for DataFrames
   - `.fetch_arrow()` for Arrow tables
   - Streaming results for large datasets

3. **Advanced Filters**:
   - Comparison operators: `Sales.revenue > 1000`
   - IN queries: `Sales.country.in_(['US', 'CA'])`
   - Range queries: `Sales.date.between(start, end)`

4. **Aggregation Control**:
   - Explicit aggregation functions: `Sales.revenue.sum()`, `.avg()`
   - Currently assumes view-defined aggregation

5. **Caching Layer**:
   - Query result caching
   - Semantic view metadata caching

---

## Quality Gate Checklist

- [x] Components clearly defined with boundaries
  - Model Layer, Query Builder, SQL Compiler, Engine, Registry, Results
- [x] Data flow direction explicit
  - Model → Query → Compiler → Engine → Results
- [x] Build order implications noted
  - Phase 1-7 with dependencies mapped
- [x] Patterns justified with examples from existing ORMs
  - SQLAlchemy, Django, ibis patterns analyzed
- [x] Alternative architectures considered
  - Decorator vs metaclass, mutable vs immutable, etc.
- [x] Open questions documented
  - Async, DataFrames, type hints, etc.

---

## References

**SQLAlchemy**:
- Declarative metaclass pattern
- Immutable Select objects
- Dialect and compiler separation
- Connection pooling via Engine

**Django ORM**:
- ModelBase metaclass with field introspection
- Immutable QuerySet via `_clone()`
- Q objects for filter composition
- Database router pattern for multi-DB

**ibis**:
- Expression tree with immutable operations
- Backend abstraction via compiler pattern
- Clean separation: frontend (expressions) vs backend (SQL generation)

**Key Takeaway**:
All mature ORMs separate concerns into distinct layers. Cubano should follow this proven pattern:
- **Definition**: Metaclass + field descriptors
- **Construction**: Immutable query builder
- **Compilation**: Dialect-specific SQL generation
- **Execution**: Abstract engine with concrete backends
- **Results**: Lightweight dynamic row objects

This architecture enables testing each component in isolation while maintaining clear contracts between layers.
