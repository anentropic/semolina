# Phase 4: Execution & Results - Research

**Researched:** 2026-02-15
**Domain:** Query execution, result handling, Row objects, engine registry
**Confidence:** HIGH

## Summary

Phase 4 implements query execution and result handling, bridging the gap between SQL generation (Phase 3) and real backend integration (Phases 5-6). The phase centers on three components: (1) Row class for result object access, (2) Query.fetch() orchestration, and (3) engine registry for lazy resolution.

Research shows this follows established ORM patterns from SQLAlchemy, Django, and ibis. The Row class requires careful design to avoid attribute conflicts with dict methods. The registry pattern must handle lazy resolution correctly to avoid stale state. Query.fetch() acts as orchestrator, coordinating registry lookup, SQL generation, engine execution, and result mapping.

**Primary recommendation:** Build Row class first (simplest, no dependencies), then registry (tested in isolation), then Query.fetch() integration (coordinates all pieces). Use MockEngine exclusively for testing - real backends come in Phases 5-6.

## Standard Stack

### Core Components (Zero Dependencies)

All Phase 4 components use Python standard library only:

| Component | Purpose | Standard Library |
|-----------|---------|------------------|
| **Row class** | Dynamic result object with attribute and dict access | `object.__setattr__`, `__getattr__`, type checking |
| **Engine registry** | Global engine storage and lazy resolution | `dict`, module-level state |
| **Query.fetch()** | Orchestrate lookup → SQL → execute → map | Existing Query, Engine ABC |

### Testing Tools

| Library | Version | Purpose | Already Available |
|---------|---------|---------|-------------------|
| **pytest** | Latest | Unit and integration tests | Yes - 81 tests passing |
| **pytest fixtures** | Built-in | MockEngine and test data injection | Yes - conftest.py exists |

### No New Dependencies

Phase 4 requires **zero new dependencies**. All components use:
- Python standard library (dataclasses, typing, collections.abc)
- Existing codebase (Query, Engine ABC, MockEngine)
- Existing testing infrastructure (pytest, fixtures)

## Architecture Patterns

### Pattern 1: Row Class with Dynamic Attribute Access

**What:** Lightweight wrapper over dict providing both attribute access (`row.revenue`) and dict-style access (`row['revenue']`).

**When to use:** Query results have dynamic field names (depend on selected metrics/dimensions), so static dataclass/TypedDict won't work.

**Key Design Decisions:**
1. **Store data in `_data` dict, use `__getattr__` for field access**
   - Avoids conflicts with Python object methods
   - Clean separation: internal (`_data`) vs. external (field names)

2. **Immutable after creation**
   - Prevent accidental mutation: `row.revenue = 999` raises error
   - Use `object.__setattr__` to set `_data` once in `__init__`

3. **Dict protocol methods explicitly defined**
   - Implement `.keys()`, `.values()`, `.items()`, `.__getitem__()` explicitly
   - Delegate to `_data` dict
   - Prevents shadowing if field named 'keys' or 'values'

4. **Reserved name validation in Field class (already done)**
   - Field.__set_name__ rejects fields named 'keys', 'values', 'items', 'get', 'pop', 'update', 'clear'
   - Row class can safely assume no conflicts

**Example:**
```python
class Row:
    """Dynamic result row with attribute and dict-style access."""

    def __init__(self, data: dict[str, Any]):
        # Use object.__setattr__ to bypass our own __setattr__
        object.__setattr__(self, '_data', data)

    def __getattr__(self, name: str) -> Any:
        """Attribute access: row.revenue"""
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(
                f"Row has no field {name!r}. "
                f"Available fields: {list(self._data.keys())}"
            )

    def __getitem__(self, key: str) -> Any:
        """Dict-style access: row['revenue']"""
        return self._data[key]

    def __setattr__(self, name: str, value: Any) -> None:
        """Prevent mutation after creation."""
        raise AttributeError(
            f"Row objects are immutable. Cannot set {name!r}."
        )

    def __repr__(self) -> str:
        fields = ", ".join(f"{k}={v!r}" for k, v in self._data.items())
        return f"Row({fields})"

    # Dict protocol
    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()
```

**Sources:**
- SQLAlchemy Row class: tuple-like with named access
- Django model instances: attribute access for fields
- ibis: returns native formats (DataFrame, Arrow)
- Architecture research (ARCHITECTURE.md): Row class pattern

**Complexity:** LOW (1-2 days implementation + tests)

### Pattern 2: Engine Registry with Lazy Resolution

**What:** Module-level dict mapping engine names to Engine instances, with lazy lookup at `.fetch()` time.

**When to use:** Query objects created before engines are registered, or queries need to specify backend per-query via `.using('warehouse_name')`.

**Key Design Decisions:**
1. **Flat dict registry (not nested)**
   - Simple: `_engines: dict[str, Engine] = {}`
   - No need for hierarchical namespacing in single-framework library

2. **Lazy resolution at .fetch() time, not query construction**
   - `Query.using('snowflake')` stores name string, not Engine instance
   - `Query.fetch()` calls `registry.get_engine(name)` when executing
   - Allows queries to be defined before registry populated

3. **Default engine named 'default'**
   - `register(engine, name='default')` or `register(engine, name='warehouse', set_default=True)`
   - `Query.fetch()` with no `.using()` resolves to default engine

4. **Thread-safe dict (Python 3.11+ GIL semantics)**
   - Python dict operations are atomic in CPython
   - Registration happens at app startup (single-threaded)
   - Reads during query execution are thread-safe

5. **Reset for testing only**
   - `registry.reset()` clears all engines
   - Not exposed in public API (internal testing helper)
   - Tests use fixture: `yield; registry.reset()`

**Example:**
```python
# registry.py
from typing import Any

_engines: dict[str, Any] = {}  # Use Any to avoid circular import with Engine
_default: str = 'default'


def register(name: str, engine: Any) -> None:
    """
    Register an engine by name.

    Args:
        name: Engine identifier (e.g., 'default', 'warehouse', 'databricks')
        engine: Engine instance (MockEngine, SnowflakeEngine, etc.)

    Raises:
        ValueError: If engine name already registered
    """
    if name in _engines:
        raise ValueError(
            f"Engine {name!r} already registered. "
            f"Use unregister({name!r}) first to replace."
        )
    _engines[name] = engine


def get_engine(name: str | None = None) -> Any:
    """
    Get engine by name (None returns default).

    Args:
        name: Engine identifier, or None for default engine

    Returns:
        Engine instance

    Raises:
        ValueError: If no engine registered with name
    """
    engine_name = name if name is not None else _default

    if engine_name not in _engines:
        available = list(_engines.keys()) if _engines else ["none"]
        raise ValueError(
            f"No engine registered with name {engine_name!r}. "
            f"Available engines: {available}. "
            f"Use cubano.register({engine_name!r}, engine) to register."
        )

    return _engines[engine_name]


def unregister(name: str) -> None:
    """Remove engine from registry."""
    if name in _engines:
        del _engines[name]


def reset() -> None:
    """Clear all registered engines (for testing only)."""
    global _engines, _default
    _engines = {}
    _default = 'default'
```

**Usage:**
```python
# Application setup
import cubano
from cubano.engines import MockEngine

cubano.register('default', MockEngine())

# Query with default engine
results = Query().metrics(Sales.revenue).fetch()

# Query with explicit engine
results = Query().metrics(Sales.revenue).using('warehouse').fetch()
```

**Sources:**
- Django DATABASES registry: settings-driven, thread-local
- SQLAlchemy: no global registry (engines passed explicitly)
- Cubano requirements: REG-01, REG-02, REG-03
- Architecture research (ARCHITECTURE.md): Registry pattern section

**Complexity:** LOW (1-2 days implementation + tests)

### Pattern 3: Query.fetch() Orchestration

**What:** Coordinate registry lookup, SQL generation (already exists), engine execution, and result mapping.

**When to use:** User calls `.fetch()` to execute query and return Row objects.

**Flow:**
```
Query.fetch()
    ├─> 1. Validate query has metrics or dimensions
    ├─> 2. Lookup engine: registry.get_engine(self._using)
    ├─> 3. Generate SQL: engine.to_sql(self)
    ├─> 4. Execute: raw_results = engine.execute(self)
    └─> 5. Map results: [Row(data) for data in raw_results]
```

**Key Design Decisions:**
1. **Validate before execution**
   - Call `self._validate_for_execution()` (already exists)
   - Ensures at least one metric or dimension selected

2. **Engine resolves SQL generation**
   - Call `engine.to_sql(self)` not `self.to_sql()`
   - Engine's dialect determines SQL syntax (AGG vs MEASURE)
   - Query.to_sql() (Phase 3) uses MockDialect for convenience only

3. **Engine.execute() returns list[dict]**
   - Engine ABC already specifies this contract
   - Each dict has field names as keys, values as results
   - Phase 4 wraps dicts in Row objects

4. **Row wrapping is Query responsibility, not Engine**
   - Engine returns raw dicts (backend-agnostic)
   - Query.fetch() maps to Row objects
   - Later phases can add `.fetch_raw()` for raw dicts, `.fetch_df()` for pandas

**Example:**
```python
# query.py (modifications to existing Query class)
def fetch(self) -> list[Row]:
    """
    Execute query and return results as Row objects.

    Returns:
        List of Row objects with attribute and dict-style access

    Raises:
        ValueError: If query is not valid for execution
        ValueError: If no engine registered (from registry.get_engine)
        RuntimeError: If engine execution fails
    """
    from .registry import get_engine
    from .results import Row

    # Validate query
    self._validate_for_execution()

    # Lookup engine
    engine = get_engine(self._using)

    # Execute (engine generates SQL and runs it)
    raw_results = engine.execute(self)

    # Map to Row objects
    return [Row(data) for data in raw_results]
```

**Sources:**
- SQLAlchemy: `session.execute(select(...))` → `Result` → `Row` objects
- Django: `QuerySet.__iter__()` → model instances
- ibis: `expr.execute()` → backend-specific format
- Cubano requirements: EXE-01 (execute via .fetch() returning Row objects)

**Complexity:** LOW (1 day implementation, integration with existing components)

### Anti-Patterns to Avoid

**Anti-pattern 1: Row class shadowing dict methods**
- **Problem:** If field named 'keys', `row.keys()` returns field value instead of dict keys
- **Solution:** Field.__set_name__ already rejects reserved names
- **Status:** Already prevented in Phase 1

**Anti-pattern 2: Registry mutation after initialization**
- **Problem:** Tests register engines, forget to clean up, next test fails
- **Solution:** pytest fixture with cleanup: `yield; registry.reset()`
- **Status:** Must implement in Phase 4 testing

**Anti-pattern 3: Stale engine references in Query**
- **Problem:** Store Engine instance in Query, engine becomes stale after registry change
- **Solution:** Store engine name (string), resolve at .fetch() time
- **Status:** Already designed correctly (REG-02: lazy resolution)

**Anti-pattern 4: Empty query generating invalid SQL**
- **Problem:** `Query().fetch()` with no metrics/dimensions generates `SELECT FROM view`
- **Solution:** `_validate_for_execution()` already checks this
- **Status:** Already implemented in Phase 3

## Don't Hand-Roll

Phase 4 has minimal "don't hand-roll" concerns because components are simple and use standard patterns.

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Result serialization** | Custom JSON encoder for Row | Standard `dataclasses.asdict` pattern | Rows are dict-like, no special encoding needed |
| **Connection pooling** | Custom pool manager | Delegate to backend drivers | Snowflake/Databricks connectors handle this |
| **Type-safe Row class** | Runtime TypedDict generation | Keep Row dynamic | Phase 4 scope; defer typed rows to v2 |

**Key insight:** Phase 4 is about integration, not reinvention. Use simple wrappers over standard Python patterns (dict, descriptor protocol, module state).

## Common Pitfalls

### Pitfall 1: Row Attribute Conflicts with Dict Methods

**What goes wrong:** Field named 'keys', 'values', or 'items' shadows Row's dict protocol methods.

**Why it happens:** `__getattr__` returns field value for any name, including method names.

**How to avoid:**
- Field.__set_name__ already validates against reserved names
- Test: attempt to create field named 'keys', verify error raised
- Row class assumes no conflicts (safe because Field validation)

**Warning signs:**
- `row.keys()` returns a value instead of dict keys
- TypeError when iterating: `'str' object is not callable`

**Status:** Already prevented by Field class validation (Phase 1).

### Pitfall 2: Registry Stale State in Tests

**What goes wrong:** Test A registers engine 'default', test B expects clean registry, fails with "engine already registered."

**Why it happens:** Global module state persists across tests without cleanup.

**How to avoid:**
- pytest fixture with cleanup: `@pytest.fixture def reset_registry(): yield; registry.reset()`
- Use `autouse=True` to reset after every test
- Never call `registry.reset()` in application code (test-only)

**Warning signs:**
- Tests pass in isolation, fail when run together
- "Engine 'default' already registered" errors in tests
- Test order dependency

**Status:** Must implement in Phase 4 test suite.

### Pitfall 3: Immutable Query Shallow Copy (Already Fixed)

**What goes wrong:** Query._filters is a list, `replace()` shares reference between copies.

**Status:** Already fixed in Phase 2 - all Query internal state uses tuples, not lists. No action needed in Phase 4.

### Pitfall 4: Engine.execute() Contract Mismatch

**What goes wrong:** Engine returns different result format than `list[dict[str, Any]]`.

**Why it happens:** Backend integration bug - raw driver results not normalized.

**How to avoid:**
- Engine ABC docstring already specifies `list[dict]` contract
- MockEngine returns correct format (validates contract)
- Integration tests verify result shape

**Warning signs:**
- TypeError in Row.__init__: expected dict, got tuple/list
- KeyError when accessing fields: `row['revenue']` fails

**Status:** Prevented by Engine ABC contract. Phase 5-6 must follow it.

### Pitfall 5: Query.fetch() with No Engine Registered

**What goes wrong:** User calls `.fetch()` before registering any engines.

**Why it happens:** Registry is empty at import time, user forgets to register.

**How to avoid:**
- `registry.get_engine()` raises clear error with available engines
- Error message suggests: "Use cubano.register('default', engine)"
- Document registration as required setup step

**Warning signs:**
- ValueError: "No engine registered with name 'default'"
- User confusion: "I thought MockEngine was built-in"

**Status:** registry.get_engine() already designed with clear error (see Pattern 2 example).

## Code Examples

### Example 1: Row Class Usage

```python
# Execution
results = Query().metrics(Sales.revenue).dimensions(Sales.country).fetch()

# Attribute access
for row in results:
    print(f"{row.country}: ${row.revenue}")

# Dict-style access
for row in results:
    print(f"{row['country']}: ${row['revenue']}")

# Dict protocol
first_row = results[0]
print(first_row.keys())    # dict_keys(['revenue', 'country'])
print(first_row.values())  # dict_values([1000, 'US'])
print(first_row.items())   # dict_items([('revenue', 1000), ('country', 'US')])

# Immutability
try:
    results[0].revenue = 999
except AttributeError as e:
    print(e)  # "Row objects are immutable. Cannot set 'revenue'."
```

### Example 2: Engine Registry

```python
# Setup (application startup)
import cubano
from cubano.engines import MockEngine

cubano.register('default', MockEngine())
cubano.register('warehouse', MockEngine())  # Different backend

# Query with default engine
results = Query().metrics(Sales.revenue).fetch()

# Query with explicit engine
results = Query().metrics(Sales.revenue).using('warehouse').fetch()

# Error handling
try:
    results = Query().metrics(Sales.revenue).using('nonexistent').fetch()
except ValueError as e:
    print(e)  # "No engine registered with name 'nonexistent'..."
```

### Example 3: Query.fetch() Flow

```python
# User code
query = (Query()
    .metrics(Sales.revenue, Sales.cost)
    .dimensions(Sales.country)
    .filter(Q(year=2024))
    .order_by(Sales.revenue.desc())
    .limit(10)
)

results = query.fetch()

# Internal flow:
# 1. query._validate_for_execution() - ensures metrics/dimensions selected
# 2. engine = registry.get_engine(None) - resolves 'default'
# 3. raw_results = engine.execute(query) - engine calls to_sql(), executes, returns list[dict]
# 4. Row objects = [Row(data) for data in raw_results]
# 5. Return to user

# Result
assert isinstance(results, list)
assert isinstance(results[0], Row)
assert results[0].country == 'US'
assert results[0]['revenue'] == 1000
```

## State of the Art

| Pattern | Old Approach | Current Approach | Impact |
|---------|-------------|------------------|--------|
| **Result objects** | Tuples or raw dicts | Row class with dual access | Better ergonomics, IDE support |
| **Registry** | Import-time resolution | Lazy resolution at .fetch() | Allows query definition before setup |
| **Execution** | Manual SQL → execute → map | Integrated .fetch() | Simpler API, one call |

**Deprecated/outdated:**
- Raw tuple results: SQLAlchemy 1.x used tuples, 2.x uses Row objects
- String-based field access: Django `.values('field')` vs. typed field refs
- Synchronous-only: Future async support in v2+

## Open Questions

### Question 1: Type-Safe Row Objects

**What we know:** Row class is dynamic (fields determined at runtime). Python typing can't express "Row with fields X, Y, Z" without codegen.

**What's unclear:** Should we generate TypedDict at runtime for better IDE support?

**Recommendation:** Defer to later phase. Dynamic Row is simpler and meets requirements. Typed rows require complex runtime type generation.

### Question 2: Result Format Extensions

**What we know:** Requirements specify Row objects. Future: `.fetch_df()` for pandas, `.fetch_raw()` for dicts.

**What's unclear:** Should these be in Query class or separate result formatters?

**Recommendation:** Phase 4 implements Row objects only. Add `.fetch_df()` in later phase as convenience (delegates to Row.items()).

### Question 3: Streaming Results

**What we know:** `.fetch()` returns full list. Large result sets consume memory.

**What's unclear:** Should Phase 4 include `.stream()` returning iterator?

**Recommendation:** Defer to later phase. Most semantic view queries are aggregated (small results). Streaming requires backend-specific cursor handling.

### Question 4: Error Handling in Execution

**What we know:** Engine.execute() can raise RuntimeError for backend failures.

**What's unclear:** Should Query.fetch() wrap backend errors in custom exception?

**Recommendation:** Let backend exceptions bubble up for now. Custom error wrapping in later phase after real backend integration (Phases 5-6).

## Sources

### Primary (HIGH confidence)

**Codebase:**
- `/Users/paul/Documents/Dev/Personal/cubano/src/cubano/engines/base.py` - Engine ABC with execute() signature
- `/Users/paul/Documents/Dev/Personal/cubano/src/cubano/query.py` - Query class with _validate_for_execution()
- `/Users/paul/Documents/Dev/Personal/cubano/src/cubano/fields.py` - Field.__set_name__ reserved name validation

**Planning docs:**
- `.planning/research/ARCHITECTURE.md` - Row class pattern, registry pattern, component flow
- `.planning/research/PITFALLS.md` - Row attribute conflicts, registry stale state, immutable query
- `.planning/phases/03-sql-generation-mock-backend/03-05-SUMMARY.md` - Phase 3 MockEngine API (no fixtures parameter)

**Requirements:**
- EXE-01: Execute query via .fetch() returning list of Row objects
- EXE-02: Row objects support attribute access: `row.revenue`
- EXE-03: Row objects support dict-style access: `row['revenue']`
- REG-01: Register engines by name: `cubano.register('default', engine)`
- REG-02: Lazy resolution at .fetch() time
- REG-03: Select engine per-query: `.using('warehouse_name')`

### Secondary (MEDIUM confidence)

**ORM patterns (training knowledge):**
- SQLAlchemy Row class: attribute and positional access
- Django QuerySet: lazy evaluation, model instance results
- ibis expression execution: backend-specific result formats

**Python patterns:**
- Dynamic attribute access via `__getattr__`
- Module-level state for registries
- Immutability via `object.__setattr__` override

## Metadata

**Confidence breakdown:**
- Row class pattern: HIGH - well-established Python descriptor protocol, codebase Field validation already in place
- Registry pattern: HIGH - simple dict, lazy resolution is standard ORM pattern
- Query.fetch() integration: HIGH - orchestrates existing components (Engine.execute already defined)

**Research date:** 2026-02-15
**Valid until:** 90 days (stable patterns, unlikely to change)

**Phase dependencies:**
- Depends on: Phase 3 complete (MockEngine, Engine ABC, Query._validate_for_execution)
- Enables: Phase 5 (Snowflake backend), Phase 6 (Databricks backend)

**Implementation complexity:**
- Row class: 1-2 days (simple wrapper, comprehensive tests)
- Registry: 1-2 days (dict + helpers, test fixtures)
- Query.fetch(): 1 day (integration, delegates to existing components)
- Total: 3-5 days implementation + testing
