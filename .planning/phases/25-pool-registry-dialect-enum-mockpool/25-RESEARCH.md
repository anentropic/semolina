# Phase 25: Pool Registry, Dialect Enum & MockPool - Research

**Researched:** 2026-03-16
**Domain:** Connection pool registry, dialect-tagged pools, mock testing infrastructure
**Confidence:** HIGH

## Summary

Phase 25 replaces Semolina's v0.2 Engine-based registry with a pool+dialect registry. The existing `registry.py` stores `Engine` instances by name; v0.3 stores `(pool, Dialect)` tuples where `pool` is an adbc-poolhouse pool (SQLAlchemy `QueuePool` wrapping ADBC connections) and `Dialect` is a new `StrEnum` that maps to existing SQL generation dialect classes (`SnowflakeDialect`, `DatabricksDialect`, `MockDialect`).

The core dependency is `adbc-poolhouse` (v1.2.0, PyPI, MIT license, by Anentropic). This is a real, published package that provides `create_pool(config)` returning a `sqlalchemy.pool.QueuePool`, with typed config classes (`SnowflakeConfig`, `DatabricksConfig`, etc.) and pool lifecycle helpers (`close_pool()`, `managed_pool()`). It wraps ADBC drivers with SQLAlchemy connection pooling.

For this phase, the key deliverables are: (1) a `Dialect` StrEnum with string-to-dialect-class resolution, (2) a modified `registry.py` that stores `(pool, Dialect)` tuples with a new `register(name, pool, *, dialect=)` signature, (3) a `MockPool` that implements the same connection interface as adbc-poolhouse pools but backed by in-memory fixture data, and (4) updated `_Query.execute()` wiring. The existing `Engine` ABC, `SnowflakeEngine`, `DatabricksEngine`, and `MockEngine` are NOT removed -- they are deprecated but kept importable for backward compatibility (especially `introspect()`).

**Primary recommendation:** Use `adbc-poolhouse` as the real pool backend. Build `MockPool` as a lightweight mock that satisfies the same connection interface (`pool.connect()` context manager returning a connection with `.cursor()`). Wire the new registry into `_Query.execute()` with backward-compatible handling.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONN-01 | User can register a pool with a dialect tag via `register("default", pool, dialect="snowflake")` | Registry stores `(pool, Dialect)` tuples; `dialect` param accepts string or Dialect enum; resolution via `_DIALECT_MAP` |
| CONN-02 | User can select a registered pool via `.using("name")` on queries | `_Query._using` already stores engine name; `execute()` calls `get_pool(self._using)` instead of `get_engine()` |
| CONN-03 | Dialect enum determines SQL generation (AGG vs MEASURE, placeholder style) | `Dialect` StrEnum maps to existing dialect classes; `SQLBuilder(dialect_instance)` generates backend-specific SQL |
| CONN-04 | User can test without a warehouse using MockPool with in-memory Arrow data | `MockPool` provides `connect()` returning `MockConnection` with `cursor()` returning `MockCursor`; reuses existing `_eval_predicate` for WHERE filtering |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| adbc-poolhouse | >=1.2.0 | Connection pool factory for ADBC drivers | Published PyPI package by same author; provides `create_pool(config)`, typed configs, SQLAlchemy QueuePool; will be Semolina's real pool backend in later phases |
| pyarrow | >=17.0.0 | Arrow in-memory data format | Required by ADBC drivers for `fetch_arrow_table()`; MockPool uses it for `fetch_arrow_table()` via lazy import |

Note: For Phase 25, `adbc-poolhouse` is NOT added as a dependency yet. Phase 25 only builds MockPool and the registry infrastructure. Real pool integration (with `adbc-poolhouse` as a dependency) happens in Phase 27. However, MockPool must conform to the same connection interface that adbc-poolhouse pools expose (`pool.connect()` context manager).

### What Exists (unchanged)

| Library | Purpose | Status |
|---------|---------|--------|
| `engines/sql.py` Dialect ABC | SnowflakeDialect, DatabricksDialect, MockDialect -- SQL generation | Unchanged. New Dialect enum maps to these classes |
| `engines/sql.py` SQLBuilder | Generates parameterized SQL from _Query | Unchanged |
| `engines/mock.py` MockEngine | Testing mock (v0.2) | Deprecated but kept importable |
| `engines/base.py` Engine ABC | Abstract engine (v0.2) | Deprecated but kept importable |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| adbc-poolhouse (later phases) | Hand-rolled pool with `collections.deque` | Avoids dependency but loses typed configs, QueuePool battle-testing, multi-driver support |
| StrEnum for Dialect | Plain strings | StrEnum gives IDE autocomplete, type safety, exhaustive matching; negligible cost |
| MockPool mimicking adbc-poolhouse interface | Separate MockEngine staying as-is | Must match real pool interface so SemolinaCursor works identically; existing MockEngine evaluates predicates differently |

## Architecture Patterns

### Recommended Project Structure Changes

```
src/semolina/
    dialect.py              # NEW: Dialect StrEnum + resolution helper
    pool.py                 # NEW: MockPool, MockConnection, MockCursor
    registry.py             # MODIFIED: stores (pool, Dialect) tuples
    query.py                # MODIFIED: execute() uses pool registry
    __init__.py             # MODIFIED: new exports
    engines/
        sql.py              # UNCHANGED: Dialect ABC + SQLBuilder
        mock.py             # UNCHANGED: MockEngine deprecated but kept
        base.py             # UNCHANGED: Engine ABC deprecated but kept
        snowflake.py        # UNCHANGED: SnowflakeEngine kept for introspect
        databricks.py       # UNCHANGED: DatabricksEngine kept for introspect
```

### Pattern 1: Dialect StrEnum with Resolution

**What:** `Dialect` is a `StrEnum` mapping string names to dialect class instances. A `_resolve_dialect()` helper converts string or enum to a concrete dialect class instance.

**When to use:** Whenever the user passes `dialect="snowflake"` or `dialect=Dialect.SNOWFLAKE`.

**Example:**
```python
# src/semolina/dialect.py
from enum import StrEnum
from semolina.engines.sql import (
    Dialect as DialectABC,
    DatabricksDialect,
    MockDialect,
    SnowflakeDialect,
)

class Dialect(StrEnum):
    SNOWFLAKE = "snowflake"
    DATABRICKS = "databricks"
    MOCK = "mock"

_DIALECT_MAP: dict[Dialect, type[DialectABC]] = {
    Dialect.SNOWFLAKE: SnowflakeDialect,
    Dialect.DATABRICKS: DatabricksDialect,
    Dialect.MOCK: MockDialect,
}

def resolve_dialect(dialect: str | Dialect) -> DialectABC:
    """Resolve a dialect string or enum to a Dialect class instance."""
    key = Dialect(dialect)  # validates string, passes enum through
    return _DIALECT_MAP[key]()
```

**Naming collision note:** The existing `engines/sql.py` already has an ABC named `Dialect`. The new `StrEnum` should also be named `Dialect` (it is the public-facing name). The ABC becomes an implementation detail accessed as `engines.sql.Dialect` when needed internally. In `__init__.py`, only the StrEnum `Dialect` is exported. This mirrors the v0.3 research architecture decision.

### Pattern 2: Pool Registry with Dialect Tag

**What:** Registry stores `(pool, DialectABC_instance)` tuples. `register()` accepts `dialect` as a required keyword argument.

**Example:**
```python
# src/semolina/registry.py (modified)
from typing import Any

from .dialect import Dialect, resolve_dialect
from .engines.sql import Dialect as DialectABC

_pools: dict[str, tuple[Any, DialectABC]] = {}
_default_name = "default"

# Backward compat: also store engines in separate dict
_engines: dict[str, Any] = {}

def register(
    name: str,
    pool_or_engine: Any,
    *,
    dialect: str | Dialect | None = None,
) -> None:
    if dialect is not None:
        # New v0.3 path: pool + dialect
        resolved = resolve_dialect(dialect)
        _pools[name] = (pool_or_engine, resolved)
    else:
        # Backward compat v0.2 path: engine (deprecated)
        import warnings
        warnings.warn(
            "register(name, engine) without dialect= is deprecated. "
            "Use register(name, pool, dialect='snowflake') instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        _engines[name] = pool_or_engine

def get_pool(name: str | None = None) -> tuple[Any, DialectABC]:
    lookup = name if name is not None else _default_name
    if lookup in _pools:
        return _pools[lookup]
    raise ValueError(...)

def get_engine(name: str | None = None) -> Any:
    """Backward compat: get engine by name."""
    lookup = name if name is not None else _default_name
    # Check pools first, then engines
    if lookup in _engines:
        return _engines[lookup]
    raise ValueError(...)
```

### Pattern 3: MockPool Matching adbc-poolhouse Interface

**What:** MockPool provides the same connection interface as adbc-poolhouse pools: `pool.connect()` as context manager returning a connection with `.cursor()`.

**Why:** SemolinaCursor (Phase 26) must work identically with MockPool and real adbc-poolhouse pools. If MockPool has a different interface, every consumer needs `isinstance` branching.

**adbc-poolhouse pool interface (from research):**
```python
# What adbc-poolhouse create_pool() returns:
pool = create_pool(config)  # sqlalchemy.pool.QueuePool

with pool.connect() as conn:    # context manager
    cursor = conn.cursor()       # standard DBAPI cursor
    cursor.execute(sql, params)  # standard execute
    rows = cursor.fetchall()     # standard DBAPI
    table = cursor.fetch_arrow_table()  # ADBC extension
```

**MockPool design:**
```python
class MockPool:
    """In-memory pool for testing without warehouse connections."""

    def __init__(self) -> None:
        self._fixtures: dict[str, list[dict[str, Any]]] = {}

    def load(self, view_name: str, data: list[dict[str, Any]]) -> None:
        """Load fixture data for a semantic view."""
        self._fixtures[view_name] = data

    def connect(self) -> MockConnection:
        """Return a mock connection (matches adbc-poolhouse pool.connect())."""
        return MockConnection(self._fixtures)

    def close(self) -> None:
        """No-op for mock."""
        pass

class MockConnection:
    """In-memory connection wrapping fixture data."""

    def __init__(self, fixtures: dict[str, list[dict[str, Any]]]) -> None:
        self._fixtures = fixtures

    def cursor(self) -> MockCursor:
        return MockCursor(self._fixtures)

    def close(self) -> None:
        pass

    def __enter__(self) -> MockConnection:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
```

### Pattern 4: Mock Execution via Query Object (Not SQL Parsing)

**What:** MockCursor receives the `_Query` object for predicate evaluation, not the SQL string. SQL generation still runs (for `.to_sql()` testing), but MockCursor evaluates predicates in-memory using the existing `_eval_predicate()`.

**Why:** Parsing SQL to extract filter predicates is fragile and complex. The `_Query` object already has the structured predicate tree.

**Implementation in `_Query.execute()`:**
```python
def execute(self) -> Result:  # Phase 25 keeps Result return type
    from .pool import MockPool
    from .registry import get_pool
    from .engines.sql import SQLBuilder
    from .results import Result, Row

    self._validate_for_execution()
    pool, dialect = get_pool(self._using)
    builder = SQLBuilder(dialect)
    sql, params = builder.build_select_with_params(self)

    conn = pool.connect()
    cur = conn.cursor()

    if isinstance(pool, MockPool):
        cur._execute_query(self)  # predicate evaluation
    else:
        cur.execute(sql, params)

    # Phase 25: still return Result for backward compat
    # Phase 26 will change this to return SemolinaCursor
    columns = [desc[0] for desc in cur.description] if cur.description else []
    raw_rows = cur.fetchall()
    rows = [Row(dict(zip(columns, row, strict=True))) for row in raw_rows]
    conn.close()
    return Result(rows)
```

**Key decision:** Phase 25 keeps the `Result` return type from `.execute()`. The SemolinaCursor return type change happens in Phase 26. This preserves backward compatibility for all existing tests during this phase.

### Anti-Patterns to Avoid

- **Pool knows about SQL:** Pool classes must NOT generate SQL or know about Dialect. Pool manages connections; SQLBuilder generates SQL.
- **Eager connection at pool construction:** MockPool.connect() is cheap, but real pools (later phases) must not connect in `__init__()`.
- **MockCursor parses SQL:** Never parse the SQL string to determine mock results. Pass the _Query object for predicate evaluation.
- **Breaking Result return type in Phase 25:** Keep `.execute()` returning `Result` to preserve all 674+ existing tests. SemolinaCursor comes in Phase 26.
- **Removing Engine classes:** Keep Engine ABC, SnowflakeEngine, DatabricksEngine, MockEngine all importable. Deprecate, do not delete.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Connection pooling | LIFO stack with threading.Lock | adbc-poolhouse (Phase 27) | Battle-tested QueuePool, typed configs, multi-driver support. Only ~50 lines to build, but why when the dependency exists? |
| Dialect string validation | Manual if/elif chain | `StrEnum` with `Dialect(value)` | Raises `ValueError` automatically for invalid strings |
| SQL generation per dialect | New SQL builder | Existing `SQLBuilder` + `SnowflakeDialect`/`DatabricksDialect` | Already built and tested in v0.2 |
| Predicate evaluation in mock | SQL parser for WHERE clauses | Existing `_eval_predicate()` from `engines/mock.py` | Already handles all 17 lookup types |

**Key insight:** Phase 25 is primarily a restructuring phase -- most of the actual logic (SQL generation, predicate evaluation, query building) already exists. The work is connecting existing pieces through a new registry interface.

## Common Pitfalls

### Pitfall 1: Dialect Name Collision

**What goes wrong:** The existing `engines/sql.py` exports an ABC named `Dialect`. The new `StrEnum` is also named `Dialect`. Importing both causes confusion.
**Why it happens:** Both concepts deserve the name "Dialect" -- the ABC defines the interface, the StrEnum provides user-facing selection.
**How to avoid:** The StrEnum lives in `dialect.py` and is the public-facing export from `semolina.__init__`. The ABC is accessed internally as `engines.sql.Dialect` or with an alias like `DialectABC`. In `engines/__init__.py`, update exports to NOT re-export the ABC `Dialect` (or rename its export).
**Warning signs:** `ImportError`, wrong type at runtime, basedpyright errors about incompatible types.

### Pitfall 2: Breaking Existing Tests

**What goes wrong:** Changing `registry.py` to store pools instead of engines breaks all tests that call `register("name", engine)` without `dialect=`.
**Why it happens:** Clean-break temptation. There are 674+ tests and many doctest examples.
**How to avoid:** Support both signatures: `register(name, engine)` (deprecated, stores in `_engines` dict) and `register(name, pool, dialect="snowflake")` (new, stores in `_pools` dict). `get_engine()` checks `_engines`. `get_pool()` checks `_pools`. Both `reset()` clears both dicts.
**Warning signs:** `TypeError` on existing `register()` calls. Doctest failures.

### Pitfall 3: MockPool Fidelity Gap

**What goes wrong:** MockPool cursor methods return data in a different format than real ADBC cursors. Tests pass with MockPool but fail with real connections.
**Why it happens:** MockCursor returns `list[dict]` while real DBAPI cursors return `list[tuple]`.
**How to avoid:** MockCursor.fetchall() must return `list[tuple]` (values only). Column names come from `cursor.description`. This matches DBAPI 2.0 spec. MockCursor.description must return proper 7-element tuples.
**Warning signs:** `dict` vs `tuple` type errors when switching from MockPool to real pool.

### Pitfall 4: Connection Lifecycle in Tests

**What goes wrong:** MockPool connections are not properly closed in test teardown. While MockPool connections are no-ops, setting a bad pattern leads to connection leaks when real pools arrive in Phase 27.
**Why it happens:** `registry.reset()` currently only clears `_engines` dict. It does not close pools.
**How to avoid:** Update `reset()` to also call `.close()` on any registered pools before clearing. MockPool.close() is a no-op, but real pools need cleanup.

### Pitfall 5: _Query.execute() isinstance Check

**What goes wrong:** Using `isinstance(pool, MockPool)` in `_Query.execute()` couples query execution to a specific mock type.
**Why it happens:** MockCursor needs the `_Query` object for predicate evaluation, while real cursors receive `(sql, params)`.
**How to avoid:** This is an acceptable tradeoff for Phase 25. The `isinstance` check is the ONLY place it appears. Alternative: add a `_supports_query_execution` attribute to pools and check that. But `isinstance` is simpler and MockPool is internal.

## Code Examples

### Dialect StrEnum Definition

```python
# src/semolina/dialect.py
from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engines.sql import Dialect as DialectABC


class Dialect(StrEnum):
    """
    Dialect enum for SQL generation backend selection.

    Determines how SQL is generated: identifier quoting style,
    metric wrapping function (AGG vs MEASURE), and placeholder format.
    """

    SNOWFLAKE = "snowflake"
    DATABRICKS = "databricks"
    MOCK = "mock"


def resolve_dialect(dialect: str | Dialect) -> DialectABC:
    """
    Resolve a dialect string or enum value to a Dialect class instance.

    Args:
        dialect: String name or Dialect enum value

    Returns:
        Concrete Dialect instance for SQL generation

    Raises:
        ValueError: If dialect string is not a valid Dialect member
    """
    from .engines.sql import DatabricksDialect, MockDialect, SnowflakeDialect
    from .engines.sql import Dialect as DialectABC

    _DIALECT_MAP: dict[Dialect, type[DialectABC]] = {
        Dialect.SNOWFLAKE: SnowflakeDialect,
        Dialect.DATABRICKS: DatabricksDialect,
        Dialect.MOCK: MockDialect,
    }
    key = Dialect(dialect)
    return _DIALECT_MAP[key]()
```

### Updated register() Signature

```python
# In src/semolina/registry.py
def register(
    name: str,
    pool_or_engine: Any,
    *,
    dialect: str | Dialect | None = None,
) -> None:
    """
    Register a pool (with dialect) or engine by name.

    New v0.3 form: register("default", pool, dialect="snowflake")
    Deprecated v0.2 form: register("default", engine)
    """
```

### MockPool with Fixture Loading

```python
# Usage in tests:
from semolina.pool import MockPool
from semolina import register, Dialect

pool = MockPool()
pool.load("sales_view", [
    {"revenue": 1000, "country": "US"},
    {"revenue": 500, "country": "CA"},
])
register("default", pool, dialect="mock")

result = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).execute()
assert len(result) == 2
```

### Full Query Flow (Phase 25)

```python
# 1. Create and register pool
pool = MockPool()
pool.load("sales_view", fixture_data)
semolina.register("default", pool, dialect=Dialect.MOCK)

# 2. Build query (unchanged from v0.2)
query = Sales.query().metrics(Sales.revenue).dimensions(Sales.country)

# 3. Execute (returns Result, same as v0.2)
result = query.execute()
for row in result:
    print(row.revenue, row.country)

# 4. Can also use named pools via .using()
semolina.register("test", pool, dialect="mock")
result = Sales.query().metrics(Sales.revenue).using("test").execute()
```

## State of the Art

| Old Approach (v0.2) | New Approach (v0.3 Phase 25) | Impact |
|----------------------|------------------------------|--------|
| `register("name", engine)` | `register("name", pool, dialect="snowflake")` | Dialect is explicit, not baked into engine class |
| Engine ABC with to_sql + execute | Pool provides connections; SQLBuilder generates SQL; separate concerns | Cleaner separation of connection management and SQL generation |
| MockEngine stores fixtures internally | MockPool stores fixtures, MockConnection/MockCursor provide DBAPI interface | Same mock cursor interface as real ADBC cursors |
| get_engine() returns Engine | get_pool() returns (pool, dialect_instance) | Pool + dialect are a pair; SQL generation needs both |
| Dialect only used internally by Engine | Dialect is user-facing StrEnum | Users choose dialect at registration time |

**Deprecated/outdated:**
- `Engine` ABC: Deprecated for query execution. Kept for `introspect()` CLI use.
- `MockEngine`: Deprecated. Use `MockPool` for v0.3 testing.
- `register(name, engine)` without dialect: Deprecated with warning.
- `get_engine()`: Kept for backward compat but new code uses `get_pool()`.

## Open Questions

1. **Should `register()` support Engine + auto-detected dialect?**
   - What we know: SnowflakeEngine has `self.dialect = SnowflakeDialect()`. We could detect the dialect from the engine.
   - What's unclear: Is auto-detection worth the complexity? Users can just add `dialect="snowflake"`.
   - Recommendation: No auto-detection. The deprecation path is: old engines emit DeprecationWarning, users migrate to pool+dialect form.

2. **Where does MockPool live? `pool.py` or `engines/mock.py`?**
   - What we know: MockEngine is in `engines/mock.py`. MockPool serves a similar role.
   - What's unclear: MockPool is conceptually different from engines. It is a pool, not an engine.
   - Recommendation: Put MockPool in `src/semolina/pool.py` alongside the Pool-related code. This keeps `engines/mock.py` as the deprecated-but-importable MockEngine location. Future SnowflakePool/DatabricksPool would also go in `pool.py` or a `pools/` subpackage.

3. **Should `_Query.execute()` change its return type in Phase 25?**
   - What we know: Phase 26 introduces SemolinaCursor as the return type.
   - Recommendation: NO. Phase 25 keeps `Result` return type. This preserves all existing tests without modification. Phase 26 handles the breaking change.

4. **pyarrow as a dependency for MockPool `fetch_arrow_table()`?**
   - What we know: pyarrow is not currently a dependency. ADBC drivers bring it transitively.
   - Recommendation: MockCursor.fetch_arrow_table() does a lazy `import pyarrow`. For Phase 25, MockPool only needs basic DBAPI methods (fetchall, fetchone, description). Arrow methods are tested in Phase 26 when SemolinaCursor is introduced.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/unit/ -x -q` |
| Full suite command | `uv run pytest` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONN-01 | register(name, pool, dialect="snowflake") stores pool+dialect | unit | `uv run pytest tests/unit/test_registry.py -x` | Exists (needs new tests added) |
| CONN-01 | Dialect StrEnum validates "snowflake", "databricks", "mock" | unit | `uv run pytest tests/unit/test_dialect.py -x` | Wave 0 |
| CONN-02 | .using("name") resolves named pool at execute time | unit | `uv run pytest tests/unit/test_query.py -x` | Exists (needs new tests added) |
| CONN-03 | Dialect enum controls SQL generation (AGG vs MEASURE) | unit | `uv run pytest tests/unit/test_sql.py -x` | Exists (verify dialect dispatch) |
| CONN-04 | MockPool with fixtures returns correct results | unit | `uv run pytest tests/unit/test_pool.py -x` | Wave 0 |
| CONN-04 | MockPool predicate evaluation matches MockEngine | unit | `uv run pytest tests/unit/test_pool.py -x` | Wave 0 |
| CONN-04 | Full query chain: register MockPool -> execute -> Result | unit | `uv run pytest tests/unit/test_pool.py -x` | Wave 0 |
| - | Backward compat: register(name, engine) still works | unit | `uv run pytest tests/unit/test_registry.py -x` | Exists (must still pass) |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/ -x -q`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_dialect.py` -- covers CONN-01, CONN-03 (Dialect StrEnum tests)
- [ ] `tests/unit/test_pool.py` -- covers CONN-04 (MockPool, MockConnection, MockCursor tests)
- [ ] Existing `tests/unit/test_registry.py` needs new tests for pool+dialect registration (CONN-01)
- [ ] Existing `tests/unit/test_query.py` needs new tests for pool-based execution path (CONN-02)

*(Framework install: not needed -- pytest already configured)*

## Sources

### Primary (HIGH confidence)

- [adbc-poolhouse on PyPI](https://pypi.org/project/adbc-poolhouse/) - v1.2.0, verified as published package; core deps: sqlalchemy>=2.0.0, adbc-driver-manager>=1.8.0, pydantic-settings>=2.0.0
- [adbc-poolhouse GitHub](https://github.com/anentropic/adbc-poolhouse) - full source, MIT license, by same author as Semolina
- [adbc-poolhouse docs](https://anentropic.github.io/adbc-poolhouse/) - `create_pool()`, `close_pool()`, `managed_pool()`, SnowflakeConfig, DatabricksConfig
- Existing Semolina v0.2 codebase - `registry.py`, `engines/sql.py`, `engines/mock.py`, `query.py`
- `.planning/research/ARCHITECTURE.md` - detailed v0.3 architecture design
- `.planning/research/STACK.md` - technology stack analysis
- `.planning/research/PITFALLS.md` - known pitfalls for v0.3 migration

### Secondary (MEDIUM confidence)

- `.planning/research/FEATURES.md` - SemolinaCursor design (relevant to Phase 26 but informs MockCursor interface)
- `.planning/research/SUMMARY.md` - executive summary of v0.3 research

### Notes on Prior Research Discrepancy

The `ARCHITECTURE.md` and `STACK.md` files contain a now-resolved discrepancy: they state "adbc-poolhouse does not exist as a published package." This was corrected in `SUMMARY.md` ("Correction: adbc-poolhouse is a published PyPI package, not project-internal"). This research confirms `adbc-poolhouse` v1.2.0 IS published on PyPI (verified 2026-03-16). The architecture research's Pool Protocol design and build-your-own-pool recommendations should be reconsidered in light of this -- adbc-poolhouse already provides the pool infrastructure.

However, the ARCHITECTURE.md's MockPool design, registry changes, and Dialect enum patterns remain valid and are the primary reference for Phase 25 implementation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - adbc-poolhouse verified on PyPI; existing Dialect classes verified in codebase
- Architecture: HIGH - follows established patterns from v0.3 research; registry modification is straightforward
- Pitfalls: HIGH - backward compatibility risks well-understood; mitigation strategy (dual dict) is proven pattern
- MockPool design: HIGH - reuses existing `_eval_predicate`; matches DBAPI 2.0 cursor interface

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (stable domain; main risk is adbc-poolhouse API changes)
