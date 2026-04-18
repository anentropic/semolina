# Phase 26: SemolinaCursor & Row Convenience - Research

**Researched:** 2026-03-17
**Domain:** DBAPI 2.0 cursor delegation, Row convenience methods, production/mock separation
**Confidence:** HIGH

## Summary

Phase 26 introduces `SemolinaCursor` as the return type of `.execute()`, replacing the `Result` class entirely. SemolinaCursor wraps an underlying DBAPI 2.0 cursor via delegation (composition) and adds three Row convenience methods: `fetchall_rows()`, `fetchmany_rows(size)`, and `fetchone_row()`. The existing `Row` class from `results.py` is reused unchanged.

The most significant engineering challenge is removing the `isinstance(pool, MockPool)` check from `query.py` while keeping MockPool functional for testing. The user has decided that production code must only speak standard DBAPI 2.0 (`cursor.execute(sql, params)`), and any mock-specific behavior should use `unittest.mock.patch`. This means MockCursor needs a standard `execute(sql, params)` method, and the approach to predicate-filtered mock testing changes.

**Primary recommendation:** Create `src/semolina/cursor.py` with a SemolinaCursor that delegates to any DBAPI 2.0-compatible cursor and adds `fetchall_rows()`, `fetchmany_rows()`, `fetchone_row()` via `cursor.description` + tuple-to-Row conversion. Modify `query.py` execute() to remove the isinstance check and return SemolinaCursor. Update MockCursor with `execute(sql, params)` and `fetchmany()` methods. Use `unittest.mock.patch` in tests that need predicate-filtered mock execution.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- `execute()` returns `SemolinaCursor` -- not `Result`
- `Result` class is removed entirely -- no deprecation, no backward compat
- Clean break from v0.2 API
- **No isinstance(pool, MockPool) in production code** -- the check in `query.py:422` must be removed
- MockCursor must not appear in the normal runtime interface anywhere
- If tests need mock behavior, use `unittest.mock.patch`
- Production `execute()` only speaks standard DBAPI 2.0: `cursor.execute(sql, params)`
- `fetchall_rows()` returns `list[Row]`
- `fetchmany_rows(size)` returns `list[Row]`
- `fetchone_row()` returns `Row | None`
- Existing `Row` class (attribute + dict access) is reused from `results.py`

### Claude's Discretion
- Whether SemolinaCursor passes through native DBAPI methods (fetchall, fetchone, fetchmany) or only exposes the `_rows()` variants
- Whether `results.py` is kept (for `Row` only) or `Row` moves to `cursor.py`
- SemolinaCursor typing approach (Protocol for underlying cursor vs concrete types)
- How MockCursor adapts to standard `execute(sql, params)` interface (or whether tests patch instead)

### Deferred Ideas (OUT OF SCOPE)
- Arrow-native fetch methods (fetch_arrow_table, fetch_record_batch) -- Phase 27+
- Async cursor support -- future milestone
- Real ADBC cursor integration testing -- requires warehouse connection
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CURS-01 | `.execute()` returns a SemolinaCursor that wraps the ADBC cursor (subclass or delegation) | SemolinaCursor delegation pattern; query.py execute() modification; isinstance removal strategy |
| CURS-02 | User can call `cursor.fetchall_rows()` and receive `list[Row]` | Row conversion pattern via cursor.description + fetchall() tuples -> Row(dict(zip)) |
| CURS-03 | User can call `cursor.fetchmany_rows(size)` and receive `list[Row]` | fetchmany() DBAPI method + same Row conversion; MockCursor needs fetchmany() added |
| CURS-04 | User can call `cursor.fetchone_row()` and receive `Row | None` | fetchone() DBAPI method + single-Row conversion |
| CURS-05 | Row retains attribute access (`row.revenue`) and dict access (`row["revenue"]`) | Existing Row class unchanged; comprehensive test coverage already exists |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| semolina (internal) | current | SemolinaCursor, Row, query.py modifications | All changes are internal to the project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unittest.mock | stdlib | Patching MockCursor._execute_query in tests | Tests that need predicate-filtered mock execution |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Delegation (composition) | Subclassing ADBC cursor | MockCursor and ADBC cursors share no common base -- delegation is the only viable approach |
| unittest.mock.patch | Custom mock execute adaptor | More complex, user explicitly chose mock.patch |

**No new dependencies required.** Phase 26 uses only stdlib and existing semolina internals.

## Architecture Patterns

### Recommended Project Structure
```
src/semolina/
    cursor.py           # NEW: SemolinaCursor class
    query.py            # MODIFIED: execute() returns SemolinaCursor, isinstance removed
    results.py          # MODIFIED: Result class removed, Row stays
    pool.py             # MODIFIED: MockCursor gains execute(sql, params) + fetchmany()
    __init__.py         # MODIFIED: exports SemolinaCursor, removes Result
```

### Pattern 1: SemolinaCursor Delegation
**What:** SemolinaCursor wraps any DBAPI 2.0 cursor via composition, not inheritance. Stores `_cursor`, `_conn`, and `_pool` references. Adds Row convenience methods that convert DBAPI tuples to Row objects using cursor.description.
**When to use:** Always -- this is the single return type of `.execute()`.
**Example:**
```python
# Source: Semolina ARCHITECTURE.md + CONTEXT.md decisions
class SemolinaCursor:
    def __init__(
        self,
        cursor: Any,
        conn: Any,
        pool: Any,
    ) -> None:
        self._cursor = cursor
        self._conn = conn
        self._pool = pool

    def _column_names(self) -> list[str]:
        desc = self._cursor.description
        if desc is None:
            return []
        return [d[0] for d in desc]

    def fetchall_rows(self) -> list[Row]:
        columns = self._column_names()
        raw_rows = self._cursor.fetchall()
        return [Row(dict(zip(columns, row, strict=True))) for row in raw_rows]

    def fetchone_row(self) -> Row | None:
        raw = self._cursor.fetchone()
        if raw is None:
            return None
        columns = self._column_names()
        return Row(dict(zip(columns, raw, strict=True)))

    def fetchmany_rows(self, size: int = 1) -> list[Row]:
        columns = self._column_names()
        raw_rows = self._cursor.fetchmany(size)
        return [Row(dict(zip(columns, row, strict=True))) for row in raw_rows]
```

### Pattern 2: Clean Execute Path (no isinstance)
**What:** The production `query.py` execute() method always calls `cursor.execute(sql, params)` -- no MockPool special-casing. Connection lifecycle is managed by SemolinaCursor (context manager).
**When to use:** This replaces the current execute() implementation.
**Example:**
```python
# Source: CONTEXT.md locked decision
def execute(self) -> SemolinaCursor:
    from .cursor import SemolinaCursor
    from .engines.sql import SQLBuilder
    from .registry import get_pool

    self._validate_for_execution()
    pool, dialect = get_pool(self._using)
    sql, params = SQLBuilder(dialect).build_select_with_params(self)

    conn = pool.connect()
    cur = conn.cursor()
    cur.execute(sql, params)

    return SemolinaCursor(cur, conn, pool)
```

### Pattern 3: MockCursor Standard DBAPI Execute
**What:** MockCursor.execute(sql, params) is a no-op that returns all pre-loaded fixture data (no filtering). The _execute_query() method remains for direct-use testing but is never called by production code.
**When to use:** All MockPool-based testing via the production execute() path.
**Example:**
```python
# MockCursor update to support standard DBAPI 2.0
class MockCursor:
    def execute(self, sql: str, params: Any = None) -> None:
        """
        DBAPI 2.0 execute -- returns all loaded fixture data.

        For predicate-filtered testing, use _execute_query() directly
        or unittest.mock.patch on this method.
        """
        # Return all fixture data (no SQL parsing, no filtering)
        # Data was loaded via pool.load() into self._fixtures
        # Need to determine view_name from SQL or return all data
        ...
```

### Pattern 4: Test Patching for Predicate Filtering
**What:** Tests that need WHERE-filter behavior through the full execute() pipeline use unittest.mock.patch to replace cursor.execute with _execute_query.
**When to use:** Integration tests testing filter behavior via MockPool.
**Example:**
```python
from unittest.mock import patch

def test_filtered_mock_execution():
    pool = MockPool()
    pool.load("sales_view", [...])
    semolina.register("default", pool, dialect="mock")

    query = Sales.query().metrics(Sales.revenue).where(Sales.country == "US")

    # Patch to use _execute_query for predicate evaluation
    with patch.object(MockCursor, 'execute', MockCursor._execute_query_from_sql):
        cursor = query.execute()
        rows = cursor.fetchall_rows()
```

### Pattern 5: SemolinaCursor Context Manager
**What:** SemolinaCursor implements `__enter__`/`__exit__` for connection lifecycle management. close() releases cursor and connection back to pool.
**When to use:** Recommended usage pattern for all cursor consumers.
**Example:**
```python
with Sales.query().metrics(Sales.revenue).execute() as cursor:
    rows = cursor.fetchall_rows()
    # Connection released automatically on exit
```

### Anti-Patterns to Avoid
- **isinstance checks in production code:** The isinstance(pool, MockPool) check at query.py:422 is explicitly prohibited. All cursor dispatch goes through standard DBAPI 2.0.
- **SemolinaCursor holding _Query reference:** SemolinaCursor should only hold cursor + conn + pool. The query is consumed during execute() and not stored.
- **Moving Row into cursor.py:** Row is a general-purpose class used in tests independently. Keep it in results.py (or a dedicated module) where it can be imported without cursor dependencies.
- **Making SemolinaCursor iterable directly:** Users should call explicit fetch methods. Don't add `__iter__` that implicitly calls fetchall_rows() -- this hides whether data is consumed from the cursor.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tuple-to-Row conversion | Custom deserializer | `Row(dict(zip(columns, row, strict=True)))` | Pattern already exists in query.py:429, proven correct |
| Column name extraction | Custom description parser | `[d[0] for d in cursor.description]` | DBAPI 2.0 standard, first element is always column name |
| Mock patching framework | Custom mock infrastructure | `unittest.mock.patch` | stdlib, user explicitly chose this |

**Key insight:** SemolinaCursor is intentionally thin. It delegates everything to the underlying DBAPI 2.0 cursor and adds only the Row conversion sugar. Do not add query caching, result buffering, or other "smart" features -- those are future concerns.

## Common Pitfalls

### Pitfall 1: cursor.description is None Before Execute
**What goes wrong:** Calling fetchall_rows() on a cursor where execute() has not been called returns no column names, producing empty Row objects.
**Why it happens:** DBAPI 2.0 spec says description is None until a query has been executed.
**How to avoid:** In the production path, SemolinaCursor is always created AFTER cursor.execute(sql, params) runs. Document that SemolinaCursor is only constructed post-execution.
**Warning signs:** Tests creating SemolinaCursor without running execute() first.

### Pitfall 2: MockCursor.execute() Without View Name Resolution
**What goes wrong:** MockCursor.execute(sql, params) receives SQL strings but needs to know which view's fixture data to return. Without parsing SQL, it cannot determine the view name.
**Why it happens:** MockCursor was designed around _execute_query() which receives the _Query object for view name extraction.
**How to avoid:** Two approaches: (A) MockCursor.execute() returns ALL loaded fixture data from the first/only loaded view (simple), or (B) MockCursor parses the FROM clause minimally to extract the view name. Recommendation: approach (A) for simplicity, since most test setups load a single view.
**Warning signs:** Tests with multiple views loaded into MockPool failing to return data from the correct view.

### Pitfall 3: Existing Tests Asserting Result Return Type
**What goes wrong:** Many existing tests assert `isinstance(result, Result)` from execute(). Changing the return type to SemolinaCursor breaks all of these.
**Why it happens:** This is a deliberate breaking change. Result is being removed.
**How to avoid:** Systematically update all tests that call `.execute()` and expect `Result`. The test files affected are:
- `tests/unit/test_query.py` -- TestQueryFetch, TestExecuteMethod, TestModelCentricWorkflow, TestQueryFetchIntegration
- `tests/unit/test_pool.py` -- TestExecuteWithPool
**Warning signs:** Any test importing `Result` from semolina.

### Pitfall 4: Connection Leak if SemolinaCursor.close() Not Called
**What goes wrong:** If execute() returns SemolinaCursor but the caller doesn't call close() or use `with`, the connection leaks.
**Why it happens:** SemolinaCursor holds a connection reference that needs explicit release.
**How to avoid:** Document context manager pattern as the recommended usage. Consider adding `__del__` as a safety net (with warnings).
**Warning signs:** Tests that call execute() without closing the cursor.

### Pitfall 5: strict=True in zip() When Column Count Mismatches
**What goes wrong:** `dict(zip(columns, row, strict=True))` raises ValueError if the tuple length differs from the column count.
**Why it happens:** Corrupt cursor.description or partial row data.
**How to avoid:** This is actually desirable -- strict=True catches data corruption early. Keep it.
**Warning signs:** None -- this is correct behavior.

### Pitfall 6: Removing Result Breaks __init__.py Exports
**What goes wrong:** `Result` is currently exported from `semolina.__init__` and used in type annotations across the codebase.
**Why it happens:** Clean break requires updating all export points.
**How to avoid:** Remove Result from `__init__.py.__all__`, add SemolinaCursor. Update execute() return type annotation.
**Warning signs:** ImportError or AttributeError if Result is still referenced somewhere.

### Pitfall 7: MockCursor Missing fetchmany() Method
**What goes wrong:** SemolinaCursor.fetchmany_rows() delegates to cursor.fetchmany() but MockCursor does not implement fetchmany().
**Why it happens:** MockCursor was built for Phase 25 with minimal DBAPI coverage.
**How to avoid:** Add fetchmany(size) to MockCursor.
**Warning signs:** AttributeError when calling fetchmany_rows() with MockPool.

## Code Examples

### SemolinaCursor Complete Implementation
```python
# Source: derived from ARCHITECTURE.md + CONTEXT.md constraints
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .results import Row

if TYPE_CHECKING:
    pass


class SemolinaCursor:
    """
    DBAPI 2.0 cursor wrapper with Row convenience methods.

    Wraps any DBAPI 2.0-compatible cursor via delegation. Adds
    fetchall_rows(), fetchmany_rows(), and fetchone_row() methods
    that convert DBAPI tuples to Row objects.

    Context manager support releases cursor and connection on exit.
    """

    def __init__(
        self,
        cursor: Any,
        conn: Any,
        pool: Any,
    ) -> None:
        self._cursor = cursor
        self._conn = conn
        self._pool = pool

    def _column_names(self) -> list[str]:
        """Extract column names from cursor.description."""
        desc = self._cursor.description
        if desc is None:
            return []
        return [d[0] for d in desc]

    # -- Row convenience methods --

    def fetchall_rows(self) -> list[Row]:
        """Fetch all remaining rows as Row objects."""
        columns = self._column_names()
        raw_rows = self._cursor.fetchall()
        return [Row(dict(zip(columns, row, strict=True))) for row in raw_rows]

    def fetchone_row(self) -> Row | None:
        """Fetch next row as a Row, or None if exhausted."""
        raw = self._cursor.fetchone()
        if raw is None:
            return None
        columns = self._column_names()
        return Row(dict(zip(columns, raw, strict=True)))

    def fetchmany_rows(self, size: int = 1) -> list[Row]:
        """Fetch up to size rows as Row objects."""
        columns = self._column_names()
        raw_rows = self._cursor.fetchmany(size)
        return [Row(dict(zip(columns, row, strict=True))) for row in raw_rows]

    # -- DBAPI 2.0 passthrough properties --

    @property
    def description(self) -> list[tuple[Any, ...]] | None:
        """Cursor description passthrough."""
        return self._cursor.description

    @property
    def rowcount(self) -> int:
        """Row count passthrough."""
        return self._cursor.rowcount

    # -- Lifecycle --

    def close(self) -> None:
        """Close cursor and release connection."""
        self._cursor.close()
        self._conn.close()

    def __enter__(self) -> SemolinaCursor:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
```

### MockCursor Updates Required
```python
# MockCursor needs these additions for DBAPI 2.0 compliance:

def execute(self, sql: str, params: Any = None) -> None:
    """
    DBAPI 2.0 execute -- sets up all fixture data for retrieval.

    Does not parse SQL. Returns all loaded fixture rows.
    For predicate-filtered testing, use _execute_query() directly.
    """
    # Determine available fixture data
    if not self._fixtures:
        self._rows = []
        self._columns = []
        self._description = []
        return

    # Use first available view's data (single-view test pattern)
    view_name = next(iter(self._fixtures))
    rows = self._fixtures[view_name]
    if rows:
        self._columns = list(rows[0].keys())
        self._rows = [tuple(row.get(col) for col in self._columns) for row in rows]
        self._description = [
            (col, None, None, None, None, None, None) for col in self._columns
        ]
    else:
        self._rows = []
        self._columns = []
        self._description = []
    self._pos = 0

def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
    """Fetch up to size rows as tuples."""
    result = self._rows[self._pos : self._pos + size]
    self._pos += len(result)
    return result
```

### Updated query.py execute() Method
```python
def execute(self) -> SemolinaCursor:
    """Execute query and return SemolinaCursor."""
    from .cursor import SemolinaCursor
    from .engines.sql import SQLBuilder
    from .registry import get_engine, get_pool

    self._validate_for_execution()

    # Try pool registry first (v0.3 path)
    try:
        pool, dialect = get_pool(self._using)
    except ValueError:
        # Fall back to engine registry (v0.2 backward compat)
        engine = get_engine(self._using)
        raw_results = engine.execute(self)
        # Wrap legacy results in a minimal cursor-like interface
        # ... (backward compat handling)

    # Pool-based execution -- standard DBAPI 2.0 only
    builder = SQLBuilder(dialect)
    sql, params = builder.build_select_with_params(self)

    conn = pool.connect()
    cur = conn.cursor()
    cur.execute(sql, params)  # No isinstance check!

    return SemolinaCursor(cur, conn, pool)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `execute()` returns `Result` | `execute()` returns `SemolinaCursor` | Phase 26 (now) | Breaking change, all callers must update |
| `isinstance(pool, MockPool)` dispatch | Standard DBAPI 2.0 only | Phase 26 (now) | Cleaner production code, mock tests use patching |
| Result wrapping list[Row] | SemolinaCursor with lazy fetch | Phase 26 (now) | Enables future Arrow-native methods |

**Deprecated/outdated:**
- `Result` class: removed entirely, not deprecated
- `isinstance(pool, MockPool)` pattern: removed from production code

## Design Decisions (Claude's Discretion Recommendations)

### Decision 1: Pass Through Native DBAPI Methods
**Recommendation: YES, pass through fetchall/fetchone/fetchmany.**

SemolinaCursor should expose both the `_rows()` convenience variants AND the native DBAPI methods as passthrough. Rationale:
- Advanced users may want raw tuples for performance
- `description` and `rowcount` are already planned as passthroughs
- Consistency: if we expose description, we should expose the standard fetch methods too
- Minimal implementation cost (one-line delegation each)

### Decision 2: Keep Row in results.py
**Recommendation: Keep `Row` in `results.py`, remove only `Result`.**

Rationale:
- Row is tested extensively in `test_results.py`
- Moving Row to cursor.py creates an unwanted tight coupling
- results.py becomes a single-class module (Row), which is clean
- Import path `from semolina.results import Row` stays stable
- cursor.py imports Row from results -- simple, no circular deps

### Decision 3: SemolinaCursor Typing Approach
**Recommendation: Use `Any` for cursor/conn/pool types with docstring documentation.**

Rationale:
- ADBC cursors, MockCursor, and future cursor types share no common Protocol
- Creating a Protocol just for internal delegation adds complexity without value
- basedpyright strict mode is already configured with generous `reportUnknown*` suppression
- The internal `_cursor`, `_conn`, `_pool` attributes are private -- callers never access them
- Type safety comes from SemolinaCursor's public method signatures, not its internal wiring

### Decision 4: MockCursor DBAPI execute() Strategy
**Recommendation: Add `execute(sql, params)` to MockCursor that returns ALL fixture data from the loaded view(s).**

Detailed strategy:
1. MockCursor.execute(sql, params) extracts the view name from the SQL `FROM` clause using a simple regex or string search (not full SQL parsing)
2. Returns all rows from that view's fixture data (no predicate filtering)
3. The existing `_execute_query()` method stays for direct-use testing at the MockCursor level
4. Tests that need full WHERE-filter testing through `query.execute()` either:
   - Set up fixture data that is already the expected filtered result
   - Use `unittest.mock.patch` to intercept and call `_execute_query()`

Why extract view name from SQL: MockPool supports multiple views. Without view name extraction, `execute()` would not know which fixture data to return. A simple `FROM "viewname"` or `FROM viewname` regex is sufficient -- MockDialect uses double-quoted identifiers, so `FROM "sales_view"` is the pattern to match.

## Scope of Changes

### Files to Create
| File | Purpose |
|------|---------|
| `src/semolina/cursor.py` | SemolinaCursor class |
| `tests/unit/test_cursor.py` | SemolinaCursor unit tests |

### Files to Modify
| File | Changes |
|------|---------|
| `src/semolina/query.py` | execute() returns SemolinaCursor, remove isinstance check, remove Result import |
| `src/semolina/results.py` | Remove Result class, keep Row |
| `src/semolina/pool.py` | Add execute(sql, params) and fetchmany() to MockCursor |
| `src/semolina/__init__.py` | Export SemolinaCursor, remove Result export |
| `tests/unit/test_query.py` | Update all tests asserting Result to use SemolinaCursor |
| `tests/unit/test_pool.py` | Update TestExecuteWithPool tests |
| `tests/unit/test_results.py` | Remove TestResult* classes, keep TestRow* classes |
| `tests/conftest.py` | Potentially add MockPool fixture alongside MockEngine |

### Files NOT to Modify
| File | Why |
|------|-----|
| `src/semolina/registry.py` | Already correct -- stores (pool, dialect) tuples |
| `src/semolina/dialect.py` | Unchanged -- dialect resolution is independent |
| `src/semolina/engines/sql.py` | Unchanged -- SQL generation is independent |
| `src/semolina/fields.py` | Unchanged |
| `src/semolina/filters.py` | Unchanged |
| `src/semolina/models.py` | Unchanged (execute() return type change propagates through _Query) |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run --extra dev pytest tests/unit/test_cursor.py -x` |
| Full suite command | `uv run --extra dev pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CURS-01 | execute() returns SemolinaCursor wrapping cursor | unit + integration | `uv run --extra dev pytest tests/unit/test_cursor.py::TestSemolinaCursor -x` | Wave 0 |
| CURS-01 | execute() uses standard DBAPI (no isinstance) | unit | `uv run --extra dev pytest tests/unit/test_query.py::TestExecuteWithPool -x` | Needs update |
| CURS-02 | fetchall_rows() returns list[Row] | unit | `uv run --extra dev pytest tests/unit/test_cursor.py::TestFetchallRows -x` | Wave 0 |
| CURS-03 | fetchmany_rows(size) returns list[Row] | unit | `uv run --extra dev pytest tests/unit/test_cursor.py::TestFetchmanyRows -x` | Wave 0 |
| CURS-04 | fetchone_row() returns Row or None | unit | `uv run --extra dev pytest tests/unit/test_cursor.py::TestFetchoneRow -x` | Wave 0 |
| CURS-05 | Row attribute + dict access | unit | `uv run --extra dev pytest tests/unit/test_results.py::TestRowAttributeAccess -x` | Exists |

### Sampling Rate
- **Per task commit:** `uv run --extra dev pytest tests/unit/test_cursor.py tests/unit/test_query.py tests/unit/test_pool.py -x`
- **Per wave merge:** `uv run --extra dev pytest`
- **Phase gate:** Full suite green + `uv run basedpyright` + `uv run ruff check` before verify

### Wave 0 Gaps
- [ ] `tests/unit/test_cursor.py` -- new file, covers CURS-01 through CURS-04
- [ ] MockCursor needs `execute(sql, params)` and `fetchmany()` methods before SemolinaCursor tests work
- [ ] Existing test_query.py and test_pool.py tests must be updated for SemolinaCursor return type

## Open Questions

1. **Legacy Engine Fallback in execute()**
   - What we know: execute() currently falls back to the engine registry when no pool is registered
   - What's unclear: Should this backward compat path also return SemolinaCursor? Or should it be removed entirely?
   - Recommendation: Keep the fallback but have it return SemolinaCursor too. Create a minimal adapter that wraps engine.execute() results into a cursor-like object. Alternatively, if the user wants a clean break, remove the fallback entirely.

2. **MockCursor execute() View Name Resolution**
   - What we know: MockCursor.execute(sql, params) receives SQL strings, needs to know which view's data to return
   - What's unclear: Whether to parse FROM clause or use a simpler mechanism
   - Recommendation: Parse `FROM "viewname"` with a simple regex. The SQL is always generated by SQLBuilder which uses a consistent format. This is robust for test purposes.

3. **SemolinaCursor repr**
   - What we know: Result had a useful repr showing row count and columns
   - What's unclear: What should SemolinaCursor repr show?
   - Recommendation: Show cursor state (open/closed) and description if available. E.g., `<SemolinaCursor columns=['revenue', 'country'] open>`.

## Sources

### Primary (HIGH confidence)
- `src/semolina/query.py` -- current execute() implementation, the isinstance check to remove
- `src/semolina/pool.py` -- current MockCursor API, gaps identified (no execute, no fetchmany)
- `src/semolina/results.py` -- Row class to reuse, Result class to remove
- `.planning/research/ARCHITECTURE.md` -- SemolinaCursor design from v0.3 architecture research
- `.planning/phases/26-semolinacursor-row-convenience/26-CONTEXT.md` -- locked user decisions

### Secondary (MEDIUM confidence)
- PEP 249 (DBAPI 2.0 specification) -- defines cursor.description, fetchone, fetchmany, fetchall interface
- Existing test patterns in tests/unit/ -- established pytest patterns for this project

### Tertiary (LOW confidence)
- None -- all findings verified against existing codebase and user decisions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all internal changes
- Architecture: HIGH -- delegation pattern well-understood, existing code provides template
- Pitfalls: HIGH -- identified by code inspection of existing tests and implementations
- MockCursor strategy: MEDIUM -- the execute(sql, params) no-op + view name extraction needs validation during implementation

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (stable -- internal architecture, no external dependency concerns)
