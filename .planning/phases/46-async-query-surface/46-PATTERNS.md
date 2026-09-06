# Phase 46: Async Query Surface - Pattern Map

**Mapped:** 2026-08-01
**Files analyzed:** 16 (7 source/config, 7 test, 4 docs — some overlap)
**Analogs found:** 15 / 16

Every new file in this phase is an **async sibling of an existing sync file**. That is the
single most important fact for the planner: there is almost no greenfield here. Each new
module has a named in-repo template, and the diff between template and target is small and
enumerable. Where a pattern is a *deliberate divergence* from the analog (async `dispose`,
no `__del__` rescue, ordered close), that is called out explicitly under the file.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/semolina/engines/abase.py` (NEW) | engine / service | request-response + streaming | `src/semolina/engines/base.py` (`Engine`, esp. `connect`/`execute`/`dispose`) | exact (sibling) |
| `src/semolina/acursor.py` (NEW) | cursor / adapter | streaming (batch pull) | `src/semolina/cursor.py` (`SemolinaCursor`) | exact (sibling) |
| `src/semolina/config.py` (MOD: `create_async_engine`) | factory / config | construction | `config.py:178-238` `create_engine()` | exact |
| `src/semolina/registry.py` (MOD: async registry) | registry / store | CRUD (in-memory map) | `registry.py:16-111` (`_engines`, `register`, `get_engine`, `unregister`, `reset`) | exact |
| `src/semolina/query.py` (MOD: `_Query.aexecute`) | query DSL method | request-response | `query.py:386-419` `_Query.execute()` | exact |
| `src/semolina/__init__.py` (MOD: exports) | package init | config | `__init__.py:10-44` existing import + `__all__` block | exact |
| `pyproject.toml` (MOD: `[async]` extra, `all`, dev `trio`, base pin, `TID`) | config | config | `pyproject.toml:27-51`, `57-69`, `108-117` | exact |
| `tests/unit/test_async_engine.py` (NEW) | test | request-response | `tests/unit/test_duckdb_engine.py` + `duckdb_pool` fixture | role-match |
| `tests/unit/test_async_cursor.py` (NEW) | test | streaming | `tests/unit/test_cursor.py` (`_CountingReader`, `TestStreamingIteration`) | exact |
| `tests/unit/test_async_query.py` (NEW) | test | request-response | `tests/unit/test_query.py` | role-match |
| `tests/unit/test_async_cancel.py` (NEW) | test | event-driven (cancellation) | — | **no analog** |
| `tests/conftest.py` (MOD: async fixtures) | test fixture | config | `tests/conftest.py:112-138` `duckdb_pool`, `141-179` `duckdb_file_backed_db`, `43-49` `clean_registry` | exact |
| `tests/integration/conftest.py` (MOD: async engine fixtures) | test fixture | config | `tests/integration/conftest.py:123-238` `snowflake_engine`, `239-356` `databricks_engine`, `357-371` `backend_engine` | exact |
| `tests/integration/test_queries.py` (MOD or NEW async module) | test | request-response (cassette) | `tests/integration/test_queries.py:46` `pytestmark = pytest.mark.adbc_cassette` | exact |
| `.github/workflows/ci.yml` (MOD: smoke assertion) | CI config | config | `ci.yml:149-172` `packaging-smoke` job | exact |
| `docs/src/how-to/{web-api,streaming}.rst` (MOD) | docs | — | existing `.. code-block:: python` sections in the same files | exact |
| `.planning/config.json` (MOD: TOOL-01) | config | config | single-key edit | n/a |

## Pattern Assignments

### `src/semolina/engines/abase.py` — `AsyncEngine` (NEW)

**Analog:** `src/semolina/engines/base.py`

**Module docstring + import pattern** (`base.py:1-19`) — note `from __future__ import
annotations`, the `TYPE_CHECKING` block for all Semolina types, and that
`adbc_poolhouse` is **never** imported at module level:

```python
"""
Abstract base class for backend engines.
...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from semolina.codegen.introspector import IntrospectedView
    from semolina.cursor import SemolinaCursor
    from semolina.engines.sql import Dialect
    from semolina.query import _Query
```

Divergences for `abase.py`: drop `ABC`/`abstractmethod` (per RESEARCH A4 — `introspect`
is the only abstract method and async introspection is deferred, so `AsyncEngine` is
concrete); `TYPE_CHECKING` imports become `AsyncSemolinaCursor` from `..acursor`.

**Constructor pattern — `Any`-typed pool with the documented rationale** (`base.py:69-86`).
Copy this verbatim in spirit; it is the standing answer to "no `# type: ignore`" for the
untyped poolhouse surface (RESEARCH Finding 5):

```python
    def __init__(self, *, pool: Any, dialect: Dialect, config: Any = None) -> None:
        """
        Store the owned ADBC pool, its derived dialect, and the source config.

        Args:
            pool: The adbc-poolhouse connection pool this engine owns. Typed as
                ``Any`` because the poolhouse/SQLAlchemy pool surface is untyped.
            ...
        """
        self._pool = pool
        self.dialect = dialect
        self._config = config
```

**Core pattern — checkout + `BaseException` guard** (`base.py:167-186`). This is *the*
template D-08 names. Copy the structure and the comment's reasoning:

```python
        from semolina.cursor import SemolinaCursor

        builder = self.dialect.create_builder()
        sql, params = builder.build_select_with_params(query)

        conn = self.connect()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
        except BaseException:
            # Return the checked-out connection to the pool before propagating.
            # Otherwise (cursor()/execute() failures, or cancellation) the slot
            # is leaked, since checkin normally happens only via
            # SemolinaCursor.close() on the success path. Mirrors
            # SemolinaCursor.close()'s ``self._conn.close()``.
            conn.close()
            raise

        return SemolinaCursor(cur, conn, self._pool)
```

Async substitutions (RESEARCH Code Examples §1): `conn = await self._pool.connect()`;
`cur = conn.cursor()` stays **sync, no await**; `await cur.execute(sql, params)`;
`await conn.close()` in the guard; deferred local import becomes
`from ..acursor import AsyncSemolinaCursor`. The `except BaseException: ... raise`
shape must be preserved exactly — never `return` from it (Pitfall 2).

**`connect()` docstring pattern — the two-consumption-modes contract** (`base.py:88-114`).
The async twin needs the same explicit contract, because D-08/D-09 make the
"long-lived handle" mode mandatory rather than optional:

```python
    def connect(self) -> Any:
        """
        Check an ADBC connection out of the owned pool.
        ...
        - **Long-lived handle:** keep the bare return value alive past this call
          and return it to the pool with an explicit ``conn.close()``. Used by
          :meth:`execute`, which hands the live connection to a
          ... that closes it on ``SemolinaCursor.close()``.
        ...
        """
        return self._pool.connect()
```

**`dispose()` — the analog must NOT be copied as-is** (`base.py:116-136`):

```python
        pool = self._pool
        if hasattr(pool, "_adbc_source"):
            from adbc_poolhouse import close_pool

            close_pool(pool)
        else:
            pool.close()
```

Two things carry over — the **deferred function-body import** of poolhouse (this is the
Pitfall 3 precedent the whole phase relies on) and the docstring's "single sanctioned
teardown path" framing. The branch logic does not: `_adbc_source` lives on the inner sync
pool, so the `hasattr` check is `False` for an `AsyncPool` and would fall through to a
bare `pool.close()` returning an un-awaited coroutine (RESEARCH Finding 3). Use
`async def dispose()` → `await close_async_pool(self._pool)`.

---

### `src/semolina/acursor.py` — `AsyncSemolinaCursor` (NEW)

**Analog:** `src/semolina/cursor.py`

**State initialisation** (`cursor.py:31-53`) — the four streaming state fields the async
iterator mirrors per D-07:

```python
        self._cursor = cursor
        self._conn = conn
        self._pool = pool
        self._closed = False
        # Streaming iteration state (lazily initialised on first __next__).
        self._reader: pyarrow.RecordBatchReader | None = None
        self._batch_rows: list[dict[str, Any]] = []
        self._batch_pos = 0
        self._stream_exhausted = False
```

Async note: the `_reader` annotation cannot be `pyarrow.RecordBatchReader` — poolhouse's
`AsyncRecordBatchReader` is not a public importable name (Finding 5), so type it `Any`
with the `base.py:74-75` rationale comment.

**Column-name + Row mapping — unchanged, reuse verbatim** (`cursor.py:55-65`, `69-78`).
`description` stays a synchronous property on `AsyncCursor` (Finding 10), so this needs no
async variant beyond the fetch call itself:

```python
    def _column_names(self) -> list[str]:
        desc = self._cursor.description
        if desc is None:
            return []
        return [d[0] for d in desc]

    def fetchall_rows(self) -> list[Row]:
        columns = self._column_names()
        raw_rows: list[tuple[Any, ...]] = self._cursor.fetchall()
        return [Row(dict(zip(columns, row, strict=True))) for row in raw_rows]
```

Async form: `async def fetchall_rows` with `raw_rows = await self._cursor.fetchall()`.
Keep the name (Open Question 1 recommendation: same names, awaited).

**Core pattern — the batch-buffer state machine** (`cursor.py:256-285`, the exact range
D-07 points at):

```python
        if self._stream_exhausted and self._batch_pos >= len(self._batch_rows):
            raise StopIteration
        if self._reader is None:
            try:
                self._reader = self._cursor.fetch_record_batch()
            except (StopIteration, OSError) as exc:
                self._stream_exhausted = True
                raise StopIteration from exc
        reader = self._reader
        assert reader is not None  # narrowing for the type checker
        while self._batch_pos >= len(self._batch_rows):
            try:
                batch = reader.read_next_batch()
            except StopIteration:
                self._stream_exhausted = True
                raise
            except OSError as exc:
                # ADBC drivers may surface drained-reader access as OSError
                # rather than StopIteration; normalise to iteration termination.
                self._stream_exhausted = True
                raise StopIteration from exc
            if batch.num_rows == 0:
                continue
            self._batch_rows = batch.to_pylist()
            self._batch_pos = 0
        row = Row(self._batch_rows[self._batch_pos])
        self._batch_pos += 1
        return row
```

Three substitutions only (RESEARCH Code Examples §2): `StopIteration` →
`StopAsyncIteration`; `reader.read_next_batch()` → `await reader.__anext__()`; the
`OSError` normalisation **drops** because poolhouse converts end-of-stream itself via its
`_EXHAUSTED` sentinel. `__iter__`/`__next__` → `__aiter__`/`__anext__`.

**Iteration docstring pattern** (`cursor.py:223-255`) — the single-pass / does-NOT-
auto-close / zero-row-batches-skipped contract is stated in the analog's docstrings and
should be restated for the async twin.

**Lifecycle — the analog is the thing that must change most** (`cursor.py:289-321`):

```python
    def close(self) -> None:
        """Close cursor and release connection."""
        self._cursor.close()
        self._conn.close()
        self._closed = True

    def __del__(self) -> None:
        """
        Best-effort finalizer that returns a leaked connection to the pool.
        ...
        """
        if getattr(self, "_closed", True):
            return
        conn = getattr(self, "_conn", None)
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()
        self._closed = True

    def __enter__(self) -> SemolinaCursor:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
```

Divergences the planner must schedule as explicit work, not incidental edits:

1. **Close order is mandatory** `reader → cursor → connection` (Pitfall 1). The sync
   `close()` has no reader step at all; skipping it in async raises `ConnectionBusyError`.
2. Each step wrapped in `contextlib.suppress(Exception)` — narrower than `BaseException`
   on purpose so a cancellation during teardown still propagates (Pitfall 2). The
   `contextlib` import already exists at `cursor.py:11`.
3. **No `__del__` rescue.** The sync safety net cannot be replicated (Pitfall 7). A
   warn-only `__del__` mirroring poolhouse's reader finalizer is the most that is allowed;
   the docstring must not claim parity.
4. `__enter__`/`__exit__` → `__aenter__`/`__aexit__`; `close()` → `async def aclose()`.

**`__repr__` pattern** (`cursor.py:323-334`) — copy the closed/open two-branch shape.

---

### `src/semolina/config.py` — `create_async_engine()` (MODIFY)

**Analog:** `config.py:178-238` `create_engine()`

**Config-or-name resolution + pool + DuckDB listener + return** (`config.py:223-238`):

```python
    if isinstance(config, str):
        wh_config, dialect = _read_connection(config, config_path)
    else:
        wh_config = _expand_private_key_path(config)
        dialect = _dialect_for_config_type(config)

    pool = create_pool(wh_config)

    if dialect is Dialect.DUCKDB:
        from sqlalchemy import event

        event.listen(pool, "connect", _load_semantic_views)

    dialect_instance = resolve_dialect(dialect)
    engine_cls = _engine_cls_for_dialect(dialect)
    return engine_cls(pool=pool, dialect=dialect_instance, config=wh_config)
```

Three substitutions: `create_pool` → `create_async_pool` **imported inside the function
body** with a re-labelled `ImportError` naming `semolina[async]` (Pitfall 3, RESEARCH Code
Examples §4); `event.listen(pool, ...)` → `event.listen(pool._pool, ...)` because
`AsyncPool` is not a SQLAlchemy event target (Finding 4 — add the explanatory comment;
`reportPrivateUsage = false` at `pyproject.toml:84` makes this clean); no
`_engine_cls_for_dialect` call — `AsyncEngine` is concrete (A4). Stays a plain `def`
(Pattern 1: `create_async_pool` does no I/O).

**Docstring pattern** (`config.py:183-222`): the "single public construction entry point
(the SQLAlchemy `create_engine` parallel)" framing, full `Args`/`Returns`/`Raises`, and an
`Example:` using `.. code-block:: python`. For the async example use `.. code-block::
python` and **never** `pycon`/`>>>` (Pitfall 5 — `--doctest-modules` runs over `src`).

---

### `src/semolina/registry.py` — async registry (MODIFY)

**Analog:** the whole of `registry.py` — module dict, three public functions, `reset()`.

**Module state** (`registry.py:13-17`):

```python
if TYPE_CHECKING:
    from .engines.base import Engine

_engines: dict[str, Engine] = {}
_default_name: Final[str] = "default"
```

Async twin: a second `_async_engines: dict[str, AsyncEngine]` reusing `_default_name`
(D-05: separate registries, one dict each).

**`register` duplicate guard** (`registry.py:47-49`):

```python
    if name in _engines:
        raise ValueError(f"Engine '{name}' is already registered")
    _engines[name] = engine
```

**`get_engine` two-tier error message** (`registry.py:70-82`) — copy this shape, including
the sorted available-names list and the "how to fix it" second message. The async variant
should name the async register function in that hint:

```python
    lookup = name if name is not None else _default_name
    if lookup in _engines:
        return _engines[lookup]
    available = list(_engines.keys())
    if available:
        available_str = ", ".join(f"'{k}'" for k in sorted(available))
        raise ValueError(
            f"No engine registered with name '{lookup}'. Available engines: {available_str}"
        )
    raise ValueError(
        f"No engine registered with name '{lookup}'. "
        "Use semolina.register(name, create_engine(config)) to register an engine."
    )
```

**`reset()` — analog structure, divergent teardown call** (`registry.py:103-110`):

```python
    for engine in _engines.values():
        # Test-only teardown: pool close can surface driver/OS shutdown errors
        # (OSError) or poolhouse teardown failures (RuntimeError); swallow only
        # those so a flaky close does not break test isolation, while genuine
        # programming errors (e.g. AttributeError) still propagate.
        with contextlib.suppress(OSError, RuntimeError):
            engine.dispose()
    _engines.clear()
```

`reset()` **stays synchronous** — it is autouse-invoked from `tests/conftest.py:43-49` and
cannot `await` (Finding 3). Tear async engines down inline with
`close_pool(engine._pool._pool)`, reusing the same `contextlib.suppress(OSError,
RuntimeError)` guard.

---

### `src/semolina/query.py` — `_Query.aexecute()` (MODIFY)

**Analog:** `query.py:386-419` — a 4-line body plus a full docstring.

```python
        from .registry import get_engine

        self._validate_for_execution()

        engine = get_engine(self._using)
        return engine.execute(self)
```

Async form (RESEARCH Code Examples §3) swaps `get_engine` → the async lookup and adds two
`await`s. Note the deferred `from .registry import ...` inside the method — copy that,
it avoids the circular import. Docstring: mirror `query.py:387-413` including the
`Raises:` list and the multi-line `with (... ) as cursor:` example, converted to
`async with`.

---

### `src/semolina/__init__.py` — exports (MODIFY)

**Analog:** `__init__.py:10-18` and the `__all__` block at `26-44`.

```python
from .config import create_engine
from .cursor import SemolinaCursor
...
from .registry import get_engine, register, unregister

__all__ = [
    "__version__",
    ...
    "create_engine",
    "get_engine",
    "register",
    "unregister",
]
```

Constraint the analog does not show: these are **eager** module-level imports.
`create_async_engine` and `AsyncSemolinaCursor` must not transitively import
`adbc_poolhouse`'s async surface at `import semolina` time (Pitfall 3). Since the deferred
import lives inside `create_async_engine`'s body, a plain eager import of the *function*
is safe — but `acursor.py`/`abase.py` must themselves be free of module-level poolhouse
async imports for that to hold. `__all__` is alphabetised-by-convention; keep it so.

---

### `pyproject.toml` (MODIFY)

**Analog:** `[project.optional-dependencies]` at `27-51`, `[dependency-groups] dev` at
`58-69`, `[tool.ruff.lint]` at `108-117`.

**Extra pattern with an explanatory comment** (`pyproject.toml:45-51`):

```toml
codegen-lint = [
    # Optional: lets `semolina codegen` emit ruff-formatted, import-sorted source.
    "ruff>=0.15.1",
]
all = [
    "semolina[snowflake,databricks,duckdb]",
]
```

Edits: base pin `adbc-poolhouse>=1.3.1` → `>=1.6.1` (line 11, Finding 1); new
`async = ["adbc-poolhouse[async]>=1.6.1"]`; `all` gains `async` (Pitfall 4); dev gains
`trio>=0.33.0` (Finding 6 — `all` alone leaves Trio missing).

**Ruff select list** (`108-109`) — add `TID`, then the banned-api block and per-file
ignores exactly as verified in RESEARCH Code Examples §5 (config confirmed working on both
ruff 0.15.x and the `.pre-commit-config.yaml` v0.9.6 pin):

```toml
select = ["E", "F", "W", "I", "UP", "B", "SIM", "TCH", "D", "TID"]
```

---

### `tests/unit/test_async_cursor.py` (NEW)

**Analog:** `tests/unit/test_cursor.py`

**Module docstring → requirement-ID map** (`test_cursor.py:11-23`) — this file lists the
requirement each test class covers; the async twin should do the same for ASYNC-03:

```python
- STREAM-02: __iter__/__next__ yield Row objects lazily from RecordBatchReader
...
- TestStreamingIteration: __iter__/__next__ semantics over RecordBatchReader (STREAM-02)
```

**Duck-typed fake reader with a laziness counter** (`test_cursor.py:104-146`) — the
directly reusable pattern for asserting batches are pulled one at a time:

```python
class _CountingReader:
    """
    Duck-typed fake of ``pyarrow.RecordBatchReader`` for streaming tests.

    Counts calls to ``read_next_batch`` so tests can assert laziness. We
    duck-type instead of subclassing because pyarrow forbids subclassing
    ``RecordBatchReader``...
    """

    def __init__(self, schema: Any, batches: Any) -> None:
        self.schema = schema
        self.batches = iter(batches)
        self.read_count = 0
        self.closed = False

    def read_next_batch(self) -> Any:
        self.read_count += 1
        return next(self.batches)
```

Async twin: `_CountingAsyncReader` with `async def __anext__` raising
`StopAsyncIteration`, `async def close`, and the same `read_count`. Also copy the
`FIXTURE_DATA` list-of-dicts constant at `test_cursor.py:97-101`.

**Loop matrix pattern** — no in-repo analog; use RESEARCH Code Examples §6 verbatim
(module-local `pytestmark = pytest.mark.anyio` + a local
`@pytest.fixture(params=["asyncio", "trio"]) def anyio_backend`). Do **not** use the
repo-wide `anyio_mode = "auto"` ini option — `testpaths` includes `src`.

---

### `tests/conftest.py` — async fixtures (MODIFY)

**Analog:** `duckdb_pool` at `112-138`, `duckdb_file_backed_db` at `141-179`,
`clean_registry` at `43-49`.

**Engine fixture pattern — importorskip, deferred imports, connect listener, register,
yield, teardown** (`conftest.py:125-138`):

```python
    pytest.importorskip("adbc_driver_duckdb")
    from adbc_poolhouse import DuckDBConfig, close_pool
    from sqlalchemy import event

    import semolina
    from semolina.config import create_engine

    engine = create_engine(DuckDBConfig(database=":memory:", pool_size=1))
    event.listen(engine._pool, "connect", _setup_sales_data)

    semolina.register("default", engine)
    yield engine._pool
    semolina.unregister("default")
    close_pool(engine._pool)
```

Note `event.listen(engine._pool, ...)` — the in-repo precedent for the private-attribute
reach that Finding 4 needs in `create_async_engine`.

For the concurrency fixture, build on **`duckdb_file_backed_db`** (session-scoped,
`tmp_path_factory`, provisions `sales_data` + `sales_view`) rather than `duckdb_pool`:
in-memory DuckDB pins `pool_size=1` and raising it is a `ConfigurationError`, so it cannot
demonstrate a free event loop (Finding 7).

**Scoped pyright pragma pattern for RED-first tests** (`conftest.py:6-10`) — the sanctioned
alternative to `# type: ignore` when a fixture references not-yet-existent API, and the
precedent for the Phase 45 RED+GREEN-in-one-commit caveat:

```python
# RED-first (Phase 44 Wave 0): create_engine and the 2-arg register() land in
# Plan 02. Until then basedpyright strict cannot see them in the duckdb_pool
# fixture, so scope-disable the rules the not-yet-built API triggers. Plan 02
# REMOVES this pragma when the fixtures go GREEN (not a `# type: ignore`).
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false
```

---

### `tests/integration/conftest.py` + async cassette tests (MODIFY)

**Analog:** `snowflake_engine` at `123-238`, `databricks_engine` at `239-356`,
`backend_engine` at `357-371`; `tests/integration/test_queries.py:46`.

**Record/replay dual-mode fixture skeleton** (`conftest.py:141-160`, with the docstring at
`127-140` explaining both modes):

```python
    from adbc_poolhouse import SnowflakeConfig, close_pool

    import semolina
    from semolina.config import create_engine

    if _is_recording(request):
        ...
```

The async fixtures need only the **replay half** — placeholder credentials, no recording
branch — because cassettes are copied, not recorded (RESEARCH Code Examples §7,
Finding 9). Keep the `_is_recording(request)` helper untouched.

**Module-wide cassette marker** (`test_queries.py:46`):

```python
pytestmark = pytest.mark.adbc_cassette
```

Async tests need the **named** form, `@pytest.mark.adbc_cassette("<name>")`, so the
`[asyncio]` and `[trio]` parametrizations do not derive two node-id cassette paths.

---

### `.github/workflows/ci.yml` — packaging smoke (MODIFY)

**Analog:** `ci.yml:149-172`

```yaml
  packaging-smoke:
    name: Smoke test [duckdb] extras install
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: Checkout
        uses: actions/checkout@v7
      - name: Set up uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - name: Install [duckdb] extra in clean venv
        run: |
          uv venv /tmp/smoke-venv
          uv pip install --python /tmp/smoke-venv/bin/python ".[duckdb]"
      - name: Import smoke test
        run: |
          /tmp/smoke-venv/bin/python -c "from semolina.engines.duckdb import DuckDBEngine; print('OK')"
```

Add a step in the same shape asserting a *base* install pulls no anyio (ASYNC-04):
`uv pip install --python /tmp/smoke-venv/bin/python "."` then
`python -c "import semolina, importlib.util; assert importlib.util.find_spec('anyio') is None"`.
Note the four test jobs at `ci.yml:34,55,76,107` all use `--extra all`, which is why `all`
must gain `async`.

---

## Shared Patterns

### Deferred poolhouse import (Pitfall 3 — applies to every new async module)

**Source:** `src/semolina/engines/base.py:130-136`
**Apply to:** `config.py` (`create_async_engine`), `abase.py` (`dispose`), anywhere
`create_async_pool` / `close_async_pool` is named

```python
        pool = self._pool
        if hasattr(pool, "_adbc_source"):
            from adbc_poolhouse import close_pool

            close_pool(pool)
```

The import is inside the function body, not at module scope. For the async surface, wrap
it in `try/except ImportError` and re-raise naming `semolina[async]` — poolhouse's own
message says `pip install adbc-poolhouse[async]`, which points users at the wrong package.

### Release-and-re-raise, never swallow (Pitfall 2 — applies to every async error path)

**Source:** `src/semolina/engines/base.py:177-184`
**Apply to:** `AsyncEngine.aexecute`, `AsyncSemolinaCursor.aclose`

```python
        except BaseException:
            # Return the checked-out connection to the pool before propagating.
            ...
            conn.close()
            raise
```

`BaseException` (not `Exception`) because `asyncio.CancelledError` is a `BaseException`.
Never `return` from such a block. In teardown paths use
`contextlib.suppress(Exception)` — deliberately narrower — so cancellation still
propagates.

### `Any` for untyped poolhouse surfaces, with the rationale in the docstring

**Source:** `src/semolina/engines/base.py:70-82`
**Apply to:** every `AsyncPool` / `AsyncConnection` / `AsyncCursor` /
`AsyncRecordBatchReader` annotation

```python
            pool: The adbc-poolhouse connection pool this engine owns. Typed as
                ``Any`` because the poolhouse/SQLAlchemy pool surface is untyped.
```

This is how the phase satisfies basedpyright strict with zero `# type: ignore` and zero
new pyproject exemptions (Finding 5). `Async*` classes are not in poolhouse's `__all__`;
do not import them from `adbc_poolhouse._async.*` to obtain a name.

### `contextlib.suppress` teardown guard

**Source:** `src/semolina/registry.py:104-109` (typed suppress) and
`src/semolina/cursor.py:311-312` (broad suppress in a finalizer)
**Apply to:** `AsyncSemolinaCursor.aclose`, async `registry.reset()` branch

```python
        with contextlib.suppress(OSError, RuntimeError):
            engine.dispose()
```

The narrow tuple is the preferred form where the failure modes are known; the async close
path uses `Exception` because poolhouse can raise `PoolhouseError` subclasses.

### Docstring conventions

**Source:** `src/semolina/cursor.py:139-163` (`fetch_arrow_table`)
**Apply to:** every new public method

```python
    def fetch_arrow_table(self) -> pyarrow.Table:
        """
        Fetch all remaining rows as a PyArrow Table (ADBC passthrough).
        ...
        Returns:
            ``pyarrow.Table`` with the query results.

        Raises:
            AttributeError: If the underlying cursor does not support
                ``fetch_arrow_table()`` (e.g. a non-ADBC cursor).

        Example:
            .. code-block:: python

                cursor = Sales.query().metrics(Sales.revenue).execute()
                table = cursor.fetch_arrow_table()
        """
```

Opening/closing `"""` on their own lines (D213), Google sections, and `.. code-block::
python` in `Example:`. Async examples must **never** use `.. code-block:: pycon` or `>>>`
— `results.py:15-19` shows the repo has genuinely executed doctests and `--doctest-modules`
runs over `src`, so `>>> await ...` would fail collection (Pitfall 5).

### `See Also:` cross-reference block

**Source:** `src/semolina/engines/base.py:61-66`
**Apply to:** `AsyncEngine`, `AsyncSemolinaCursor`, `create_async_engine`

```python
    See Also:
        - semolina.config.create_engine: Builds an Engine from a config or name
        - semolina.engines.sql.Dialect: Backend-specific SQL generation rules
```

Each async type should point at its sync sibling and vice versa — that pairing is the
main discoverability affordance of the two-surface design.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/unit/test_async_cancel.py` | test | event-driven (cancellation) | No cancellation test exists anywhere in the repo — nothing sync is cancellable. Use RESEARCH Finding 8 as the sole guide: real DuckDB (not cassettes — `ReplayCursor.adbc_cancel()` is a no-op), a deterministic long-running query rather than a sleep-based race (A3), and assert on cancellation/timeout rather than `ProgrammingError` (poolhouse swallows the driver interrupt and re-raises the framework cancellation) |

Partial-analog note: the anyio `asyncio`/`trio` parametrized-backend fixture also has no
in-repo precedent — no test currently uses the anyio plugin. RESEARCH Code Examples §6
(sourced from anyio's own `docs/testing.md`) is the pattern to copy.

## Metadata

**Analog search scope:** `src/semolina/`, `src/semolina/engines/`, `tests/unit/`,
`tests/integration/`, `pyproject.toml`, `.github/workflows/ci.yml`, `docs/src/how-to/`
**Files scanned:** 14 read (7 source, 4 test, 2 config, 1 workflow); directory listings
for `tests/unit`, `tests/integration`, `docs/src/how-to`
**Pattern extraction date:** 2026-08-01
