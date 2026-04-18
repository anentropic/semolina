# Phase 32: v0.3 Tech Debt Cleanup - Research

**Researched:** 2026-04-18
**Domain:** Code cleanup / deprecated API migration (Python internals)
**Confidence:** HIGH

## Summary

Phase 32 addresses four specific tech debt items flagged by the v0.3 milestone audit. All changes are within the semolina codebase -- no new libraries, no external dependencies, no architecture changes. The scope is:

1. **`src/semolina/conftest.py`:** Convert doctest fixture from deprecated `register("default", engine)` to `register("default", pool, dialect="mock")` using `MockPool` instead of `MockEngine`.
2. **`src/semolina/query.py`:** Rename `using()` parameter from `engine_name` to `pool_name`, update all docstrings/comments that say "engine" to say "pool".
3. **`tests/unit/test_query.py`:** Convert ~21 `register()` calls from deprecated MockEngine path to MockPool + `dialect="mock"` path.
4. **All tests must pass after changes.**

The critical insight from this research is that **none of the existing test assertions depend on MockEngine's predicate-filtering behavior**. Every test either (a) does not use `.where()` at all, (b) uses `.where()` but does not call `.execute()`, or (c) uses `.where()` with `.execute()` but the filter conditions match all fixture rows. This means the MockEngine-to-MockPool conversion is straightforward with no assertion changes needed for filter behavior.

**Primary recommendation:** Convert all three files in a single plan. The changes are mechanical and self-contained. The only coordination point is that `using()` error message changes must be synchronized with test assertion updates.

## Project Constraints (from CLAUDE.md)

- **Typecheck:** `uv run basedpyright` (strict mode)
- **Lint:** `uv run ruff check`
- **Format:** `uv run ruff format --check`
- **Tests:** `uv run pytest` (runs both unit tests and doctests via `--doctest-modules`)
- **Docs build:** `uv run sphinx-build -W docs/src docs/_build`
- **Line length:** 100 chars
- **Docstrings:** Google style, opening/closing `"""` on own lines for multi-line, D213 enforced
- **Docstring examples:** Use `.. code-block:: python` RST directives, not markdown fences
- **Avoid `# type: ignore`**
- **Bug fixes:** Failing test first, then fix (not applicable here -- this is refactoring, not bug fixing)

## Architecture Patterns

### Change Map

All changes are localized to three files. No public API signatures change (the `using()` method's external behavior is identical -- only the internal parameter name and docstring wording change).

```
src/semolina/conftest.py       # MockEngine -> MockPool + dialect="mock"
src/semolina/query.py          # engine_name -> pool_name, docstring updates
tests/unit/test_query.py       # ~21 register() calls: MockEngine -> MockPool
```

### Pattern: MockEngine to MockPool Conversion

Both `MockEngine` and `MockPool` have identical `load()` APIs:

```python
# MockEngine (deprecated)
engine = MockEngine()
engine.load("sales_view", [{"revenue": 1000, "country": "US"}])
register("default", engine)

# MockPool (current)
pool = MockPool()
pool.load("sales_view", [{"revenue": 1000, "country": "US"}])
register("default", pool, dialect="mock")
```

[VERIFIED: codebase grep -- MockEngine.load() at engines/mock.py:248, MockPool.load() at pool.py:31, both accept (view_name: str, data: list[dict[str, Any]])]

The `load()` method signature is identical, so every conversion is a mechanical replacement:
1. Change `MockEngine()` to `MockPool()`
2. Change `register("name", engine)` to `register("name", pool, dialect="mock")`
3. Update variable names from `engine` to `pool` (optional but improves clarity)
4. Update imports: `from semolina.engines.mock import MockEngine` to `from semolina.pool import MockPool` (or `from semolina import MockPool`)

### Pattern: Execution Path Difference

When using MockEngine via the deprecated path:
1. `get_pool()` raises ValueError (no pool registered)
2. Falls back to `get_engine()` -- succeeds
3. `MockEngine.execute(query)` applies predicate filtering via `_eval_predicate`
4. Wraps results in `_LegacyResultCursor` -> `SemolinaCursor`

When using MockPool via the pool path:
1. `get_pool()` succeeds -- returns (pool, dialect)
2. `SQLBuilder.build_select_with_params(query)` generates SQL + params
3. `MockCursor.execute(sql, params)` extracts view name from SQL, returns ALL fixture rows (no predicate filtering)
4. Wraps in `SemolinaCursor`

**Key difference:** MockPool does NOT filter rows by WHERE predicates. MockEngine does.

[VERIFIED: codebase -- pool.py MockCursor.execute() line 116-147 does not filter; engines/mock.py MockEngine.execute() line 299-348 does filter via _eval_predicate]

### Risk Assessment: Filter Behavior

Exhaustive analysis of all 21 `register()` sites in `test_query.py` confirms **zero tests will break** due to the filter behavior difference:

| Test Class | Tests with register() | Uses .where() + .execute()? | Assertion at risk? |
|------------|----------------------|----------------------------|-------------------|
| TestQueryFetch | 9 tests | No | No |
| TestQueryFetchIntegration | 3 tests | No | No |
| TestQueryStubs | 1 test (error path) | No | No |
| TestExecuteMethod | 5 tests | No | No |
| TestModelCentricWorkflow | 1 test | Yes, but all 3 rows match filter | No (asserts `len==3`) |

[VERIFIED: codebase -- read every test that calls register() and execute(), traced filter conditions against fixture data]

### Anti-Patterns to Avoid

- **Updating error messages without updating matching test assertions:** The `using()` TypeError message at query.py:331 says "engine name string". Two tests (lines 501, 503) assert `match="requires engine name string"`. These MUST be updated together.
- **Forgetting the import change:** Tests import `MockEngine` from `semolina.engines.mock`. The new import should be `MockPool` from `semolina.pool` (or `from semolina import MockPool`).
- **Leaving stale docstring references:** The `_Query` class docstring at line 53 says "Engine name for lazy resolution". The `__repr__` docstring at line 71 says "engine binding". Both need updating.

## Don't Hand-Roll

Not applicable -- this phase involves only mechanical code changes with no library decisions.

## Common Pitfalls

### Pitfall 1: Doctest Format Error in query.py

**What goes wrong:** The `_Query` class docstring has a formatting issue: the `Attributes:` section at line 47 lacks a blank line after the code example block, causing a doctest parse error.
**Why it happens:** The original docstring has `Attributes:` immediately after the code block with inconsistent indentation.
**How to avoid:** When updating the docstring (to change "Engine name" to "Pool name" on line 53), also add a blank line between the code example and the `Attributes:` section.
**Warning signs:** `uv run pytest --doctest-modules src/semolina/` fails with `ValueError: inconsistent leading whitespace`.
[VERIFIED: ran `uv run pytest --doctest-modules src/semolina/` and observed the error]

### Pitfall 2: Error Message / Test Assertion Mismatch

**What goes wrong:** Renaming the `engine_name` parameter in `using()` naturally leads to updating the error message from "requires engine name string" to "requires pool name string". But two test assertions at lines 501 and 503 match on the old message.
**Why it happens:** The parameter rename and error message update happen in `query.py` but the test assertions are in `test_query.py`.
**How to avoid:** Update `query.py` error messages and `test_query.py` assertions in the same task.
**Warning signs:** `pytest tests/unit/test_query.py::TestQueryUsing::test_using_with_non_string_raises` fails.

### Pitfall 3: conftest.py Docstring Still References MockEngine

**What goes wrong:** The `src/semolina/conftest.py` module docstring (line 4) says "Injects a pre-configured MockEngine" and the `doctest_setup` function docstring (lines 39-40) says "Registers a MockEngine as 'default'". After converting to MockPool, these become inaccurate.
**Why it happens:** Docstrings are easy to overlook during mechanical code changes.
**How to avoid:** Update all docstrings and comments in conftest.py that reference MockEngine/engine to MockPool/pool.

### Pitfall 4: Tests That Assert on Error Messages from get_engine()

**What goes wrong:** Tests at lines 478, 599, and 610 assert `match="No engine registered"`. One might think these need updating too, but they should NOT be changed.
**Why it happens:** These tests exercise the path where NO pool AND no engine is registered. `execute()` tries `get_pool()` first (fails), then falls back to `get_engine()` (also fails). The error from `get_engine()` is what the test catches. This fallback path is intentional v0.2 backward compatibility.
**How to avoid:** Understand that these tests are testing the "nothing registered at all" error path, which still goes through `get_engine()` as the final fallback. Leave these assertions unchanged.

### Pitfall 5: Variable Name Consistency

**What goes wrong:** Converting `engine = MockEngine()` to `pool = MockPool()` but leaving some references as `engine` in the same test method.
**Why it happens:** Mechanical find-and-replace that misses some instances.
**How to avoid:** For each test method, rename ALL local variables: `engine` -> `pool`, `engine1` -> `pool1`, `engine2` -> `pool2`, etc. Also update docstrings/comments within test methods.

## Code Examples

### conftest.py Conversion Pattern

```python
# BEFORE (deprecated)
from semolina.engines.mock import MockEngine

engine = MockEngine()
engine.load("sales_view", [...])
register("default", engine)

# AFTER (current)
from semolina.pool import MockPool

pool = MockPool()
pool.load("sales_view", [...])
register("default", pool, dialect="mock")
```

[VERIFIED: MockPool API at pool.py, register() with dialect= at registry.py:56-60]

### query.py using() Rename Pattern

```python
# BEFORE
def using(self, engine_name: Any) -> _Query:
    """
    Select engine for this query by name.

    Engine is resolved lazily at .execute() time...

    Args:
        engine_name: Registered engine name (e.g., 'default', 'warehouse')
    ...
    """
    if not isinstance(engine_name, str):
        raise TypeError(
            f"using() requires engine name string, got {type(engine_name).__name__}. "
            f"Register engine first: semolina.register('name', engine)"
        )
    return self._replace(_using=engine_name)

# AFTER
def using(self, pool_name: Any) -> _Query:
    """
    Select pool for this query by name.

    Pool is resolved lazily at .execute() time...

    Args:
        pool_name: Registered pool name (e.g., 'default', 'warehouse')
    ...
    """
    if not isinstance(pool_name, str):
        raise TypeError(
            f"using() requires pool name string, got {type(pool_name).__name__}. "
            f"Register pool first: semolina.register('name', pool, dialect='snowflake')"
        )
    return self._replace(_using=pool_name)
```

### test_query.py Conversion Pattern

```python
# BEFORE
def test_fetch_returns_semolina_cursor(self):
    import semolina
    engine = MockEngine()
    engine.load("sales_view", [{"revenue": 1000, "country": "US"}])
    semolina.register("default", engine)
    cursor = _Query().metrics(Sales.revenue).execute()
    ...

# AFTER
def test_fetch_returns_semolina_cursor(self):
    import semolina
    pool = MockPool()
    pool.load("sales_view", [{"revenue": 1000, "country": "US"}])
    semolina.register("default", pool, dialect="mock")
    cursor = _Query().metrics(Sales.revenue).execute()
    ...
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via uv) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/unit/test_query.py -x -q` |
| Full suite command | `uv run pytest` |

### Phase Requirements -> Test Map

Phase 32 has no formal requirement IDs (tech debt). The success criteria map as follows:

| Criterion | Behavior | Test Type | Automated Command | File Exists? |
|-----------|----------|-----------|-------------------|-------------|
| SC-1 | conftest.py uses register() with dialect= | smoke | `uv run pytest --doctest-modules src/semolina/ -x -q` | Existing doctests |
| SC-2 | query.py using() says "pool" not "engine" | unit | `uv run pytest tests/unit/test_query.py::TestQueryUsing -x -q` | Existing |
| SC-3 | test_query.py uses MockPool + dialect="mock" | unit | `uv run pytest tests/unit/test_query.py -x -q` | Existing |
| SC-4 | All existing tests pass | full suite | `uv run pytest` | Existing |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_query.py -x -q`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green + zero DeprecationWarnings in test_query.py output

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. No new test files needed.

## Specific Change Inventory

### File 1: `src/semolina/conftest.py` (7 changes)

| Line(s) | Current | Target |
|---------|---------|--------|
| 4 | "Injects a pre-configured MockEngine" | "Injects a pre-configured MockPool" |
| 16 | `from semolina.engines.mock import MockEngine` | `from semolina.pool import MockPool` |
| 39-40 | "Registers a MockEngine as 'default'" | "Registers a MockPool as 'default'" |
| 45 | "mock_engine: MockEngine with sample rows loaded" | "mock_pool: MockPool with sample rows loaded" |
| 57 | `engine = MockEngine()` | `pool = MockPool()` |
| 58-65 | `engine.load(...)` | `pool.load(...)` |
| 67 | `register("default", engine)` | `register("default", pool, dialect="mock")` |
| 71 | `doctest_namespace["mock_engine"] = engine` | `doctest_namespace["mock_pool"] = pool` |

**Doctest impact:** The `mock_engine` namespace variable becomes `mock_pool`. Any doctests that reference `mock_engine` in source files will break. Let me check:

[VERIFIED: grep for "mock_engine" in src/semolina/ -- only conftest.py line 71 sets it, and no source doctest references it. Safe to rename.]

### File 2: `src/semolina/query.py` (12 changes)

| Line(s) | Current | Target |
|---------|---------|--------|
| 47 | Missing blank line before `Attributes:` | Add blank line (fixes doctest parse error) |
| 53 | "Engine name for lazy resolution" | "Pool name for lazy resolution" |
| 71 | "engine binding" | "pool binding" |
| 305 | `def using(self, engine_name: Any)` | `def using(self, pool_name: Any)` |
| 307 | "Select engine for this query by name." | "Select pool for this query by name." |
| 309 | "Engine is resolved lazily" | "Pool is resolved lazily" |
| 310 | "engines are registered" | "pools are registered" |
| 314 | "engine_name: Registered engine name" | "pool_name: Registered pool name" |
| 320 | "TypeError: If engine_name is not a string" | "TypeError: If pool_name is not a string" |
| 329 | `if not isinstance(engine_name, str):` | `if not isinstance(pool_name, str):` |
| 330-332 | Error message with "engine" | Error message with "pool" |
| 334 | `return self._replace(_using=engine_name)` | `return self._replace(_using=pool_name)` |

### File 3: `tests/unit/test_query.py` (~50+ changes)

**Import change:** Replace `from semolina.engines.mock import MockEngine` with `from semolina.pool import MockPool`

**21 register() call sites** across these test classes:
- `TestQueryFetch` (9 calls): lines 529, 546, 560, 574, 588, 607, 618, 629, 646
- `TestQueryFetchIntegration` (5 calls): lines 673, 699, 703, 725, 729
- `TestExecuteMethod` (6 calls): lines 937, 955, 976, 996, 1009, 1020
- `TestModelCentricWorkflow` (1 call): line 1074

**Error message assertion updates:**
- Line 501: `match="requires engine name string"` -> `match="requires pool name string"`
- Line 503: `match="requires engine name string"` -> `match="requires pool name string"`

**Docstring/comment updates:** All test class and method docstrings that say "engine" (where they mean the registered backend).

**Error path tests that should NOT change:**
- Lines 478, 599: `match="No engine registered"` -- keep as-is (tests the fallback to `get_engine()`)
- Line 610: `match="No engine registered with name 'other'"` -- keep as-is

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | No doctest in src/ references `mock_engine` namespace variable | Change Inventory | Doctests would fail if any file uses `mock_engine` in examples |

All other claims were verified by reading the codebase directly. No external dependencies or version assumptions.

## Open Questions

None. All changes are fully understood from the codebase analysis.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `register(name, engine)` (no dialect) | `register(name, pool, dialect="snowflake")` | Phase 25 (v0.3) | Emits DeprecationWarning, uses legacy engine path |
| `MockEngine` for testing | `MockPool` for testing | Phase 25 (v0.3) | MockPool is DBAPI 2.0 compatible, no predicate filtering |
| `_Query.using(engine_name)` | `_Query.using(pool_name)` | This phase | Parameter name and docstring terminology |

## Sources

### Primary (HIGH confidence)
- Codebase direct inspection of all three target files
- `registry.py` -- register() API with dialect= parameter
- `pool.py` -- MockPool class and MockCursor.execute() behavior
- `engines/mock.py` -- MockEngine class and _eval_predicate filtering
- `query.py` -- using() method and execute() flow
- Full read of all 127 tests in test_query.py

### Verification
- Ran `uv run pytest tests/unit/test_query.py -x -q` -- 127 passed, 21 DeprecationWarnings [VERIFIED]
- Ran `uv run pytest --doctest-modules src/semolina/` -- confirmed doctest parse error in query.py [VERIFIED]
- Grep audit of all `register()`, `MockEngine`, `engine_name` references across target files [VERIFIED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, pure internal refactoring
- Architecture: HIGH -- execution path differences fully traced and verified
- Pitfalls: HIGH -- all risk areas identified with specific line numbers and test evidence

**Research date:** 2026-04-18
**Valid until:** No expiry (internal codebase analysis, not version-dependent)
