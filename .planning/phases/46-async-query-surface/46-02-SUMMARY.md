---
phase: 46
plan: "02"
subsystem: async-engine-and-cursor
tags: [async, engine, cursor, streaming, anyio, trio, duckdb, posture-a]
status: complete
requires:
  - "46-01: adbc-poolhouse>=1.6.1, the semolina[async] extra, trio in dev, the TID251 gate"
provides:
  - "semolina.engines.abase.AsyncEngine — sibling of Engine, owns exactly one poolhouse AsyncPool"
  - "semolina.acursor.AsyncSemolinaCursor — async row streaming with the mandatory ordered close"
  - "semolina.config.create_async_engine — sibling constructor, plain def, deferred poolhouse import"
  - "tests/conftest.py fixtures async_duckdb_engine and async_duckdb_file_engine"
  - "tests/unit/test_async_engine.py — ASYNC-01 coverage across asyncio and Trio"
  - "tests/unit/test_async_cursor.py — ASYNC-03 coverage across asyncio and Trio"
affects:
  - src/semolina/engines/abase.py
  - src/semolina/acursor.py
  - src/semolina/config.py
  - tests/conftest.py
  - tests/unit/test_async_engine.py
  - tests/unit/test_async_cursor.py
tech-stack:
  added: []
  patterns:
    - "Sibling async type per SQLAlchemy's shape: distinct constructor, distinct engine type, one pool each, mode fixed at construction"
    - "Ordered async teardown (reader, cursor, connection) with each step suppressed at Exception rather than BaseException"
    - "Module-local pytestmark + parametrized anyio_backend fixture for the asyncio/Trio matrix, never the repo-wide ini option"
    - "Non-vacuity probes: assert a test fails against a deliberately wrong implementation before trusting it"
key-files:
  created:
    - src/semolina/engines/abase.py
    - src/semolina/acursor.py
    - tests/unit/test_async_engine.py
    - tests/unit/test_async_cursor.py
  modified:
    - src/semolina/config.py
    - tests/conftest.py
decisions:
  - "Public surface settled: create_async_engine / AsyncEngine / AsyncSemolinaCursor, with aexecute returning an already-open cursor (async with await ...)"
  - "Fetch methods keep their sync names and are awaited; description and rowcount stay plain properties"
  - "fetch_arrow_table's async twin pulled forward now — it needs no reader, so it carries no close-ordering risk and gives the streaming tests an independent oracle"
  - "ConnectionBusyError propagates unwrapped and is documented; poolhouse's own message is already actionable"
  - "__del__ warns only and says plainly it is NOT parity with the sync cursor's connection-returning finalizer"
metrics:
  duration: "~2h"
  completed: 2026-08-01
  tasks: 3
  commits: 3
actuals:
  tokens: 14222
  tasks: 3
  commits: 3
---

# Phase 46 Plan 02: Async Engine & Cursor Summary

The async query path works end to end — `create_async_engine` → `await engine.aexecute(query)`
→ `async for row in cursor` yields `Row` objects against real DuckDB, under both asyncio and
Trio, with every pooled connection returned.

## What Was Built

**Task 1 — the tracer: one real path through every layer** (commit `91253f6`)

`src/semolina/engines/abase.py` — `AsyncEngine`, a sibling of `Engine` and not a proxy over
one. Concrete and backend-agnostic, because `introspect()` is the only method backends
specialise and async introspection is deferred. `aexecute` builds SQL with
`self.dialect.create_builder().build_select_with_params(query)` — the same builder the sync
path uses, so there is no second SQL path — then checks out a connection, calls
`conn.cursor()` with no await (poolhouse's accessor is synchronous), awaits `cur.execute`,
and guards the whole thing with `except BaseException: await conn.close(); raise`. That
handler never returns: under asyncio the cancellation arriving there is a `BaseException`,
and returning would swallow it. `dispose()` awaits `close_async_pool` with no fallback
branch — the sync `dispose`'s `_adbc_source` check keys on a marker that lives on the inner
sync pool, so for an `AsyncPool` it is false and the else arm would produce an un-awaited
coroutine that closes nothing.

`src/semolina/acursor.py` — `AsyncSemolinaCursor` with the four streaming state fields, the
`_column_names()` helper copied unchanged (poolhouse keeps `description` synchronous), and
the batch-buffer state machine mirroring `cursor.py:256-285` with exactly three
substitutions: `StopAsyncIteration`, `await reader.__anext__()`, and the `OSError`
normalisation arm dropped because poolhouse converts the driver's end-of-stream into its own
sentinel before it can cross the thread boundary.

`src/semolina/config.py` — `create_async_engine`, a plain `def` (pool construction does no
I/O). `create_async_pool` is imported inside the function body, and its `ImportError` is
re-raised as a static literal naming `semolina[async]` rather than poolhouse's own extra.
The pool is built from the config object, never a driver path. The DuckDB `semantic_views`
listener attaches to `pool._pool` — the inner sync pool — because `AsyncPool` is a plain
wrapper, not a SQLAlchemy event target.

`tests/conftest.py` — `async_duckdb_engine`. `tests/unit/test_async_engine.py` — the D-17
loop matrix wired from the start and the single tracer test.

**Task 2 — the full cursor result surface and its close ordering** (commit `6bc9f19`)

RED first: the test file landed before the implementation and ran 20 failed / 23 passed, the
23 being the streaming and close tests the tracer skeleton already satisfied. RED and GREEN
share one commit per the standing Phase 45 caveat — basedpyright strict rejects a test
referencing not-yet-existent attributes, and `--no-verify` is not an option.

`AsyncSemolinaCursor` gained `fetchall_rows` / `fetchone_row` / `fetchmany_rows`, the
raw-tuple `fetchall` / `fetchone` / `fetchmany`, `fetch_arrow_table`, `fetch_record_batch`,
`description` and `rowcount` as plain synchronous properties, `__repr__`, and a warn-only
`__del__`.

`tests/unit/test_async_cursor.py` — 43 tests. The close-ordering test drives a real DuckDB
cursor with a live, undrained reader, because a fake cannot prove poolhouse's reader-lifetime
guard is satisfied; fakes cover laziness, zero-row batches, re-iteration, and the
invalidated-connection path, which a real driver cannot produce on demand.

**Task 3 — loop freedom and concurrency** (commit `5de7aaa`)

`async_duckdb_file_engine`, built on the session-scoped `duckdb_file_backed_db` with
`pool_size` deliberately unset so the config's own file-backed default of 5 applies. Two
tests whose ids carry `concurrency`. The library diff for this task is empty: no semaphore,
no gather helper, no timeout wrapper. The concurrency envelope stays poolhouse's own per-pool
capacity limiter.

## The close ordering — the phase's highest risk, discharged

CONTEXT.md named connection lifetime as the highest-risk area and RESEARCH made it concrete:
poolhouse holds a reader-lifetime lock on the connection, draining does not clear it, and
both `AsyncCursor.close()` and `AsyncConnection.close()` take the foreign tier of that guard.
Closing either before the reader raises `ConnectionBusyError` from inside teardown.

`aclose()` runs reader → cursor → connection, sets `_closed` first so it is idempotent, and
suppresses `Exception` (not `BaseException`) at each step so a cancellation arriving during
teardown still propagates. Three tests hold it down, and the load-bearing one runs against a
real cursor:

- `test_close_order_is_reader_cursor_connection` asserts the log is exactly
  `["reader", "cursor", "conn"]`.
- `test_close_with_live_reader_returns_connection_to_pool` consumes one row from a **real**
  DuckDB cursor so the reader is live and undrained, calls `aclose()`, and asserts the inner
  pool's `checkedout()` goes 1 → 0 with no exception.
- `test_close_tolerates_invalidated_connection` drives the D-10 case a real driver will not
  produce on demand.

## Two prohibitions discharged by executed probes, not by assertion

The plan carries three kept prohibitions with `verification: test` and no `check_*`
descriptor. A test that would also pass against the prohibited implementation certifies
nothing, so two of them were probed against a deliberately wrong implementation.

**ASYNC-03, "MUST NOT materialize the full result set behind a streaming interface."** A
throwaway `MaterializingCursor` subclass whose `__anext__` drains the reader up front was run
through the same assertion sequence:

```
materializing impl: read_count after first row = 4
PROBE OK: the laziness assertion FAILS against a materializing impl
```

The real implementation shows `read_count == 1` after the first row with three batches
available, so `assert reader.read_count == 1` is a genuine discriminator.

**ASYNC-01, "MUST NOT present a blocking call as async."** A `BlockingAsyncEngine` whose
`aexecute` is an `async def` with the synchronous execute path as its body — no await
anywhere — was run through the loop-freedom test's exact task-group structure:

```
blocking impl: rows=2 spins=0
PROBE OK: the loop-freedom assertion FAILS against a blocking impl
```

It returns real rows and still scores zero, which is the point: the sibling task parks on a
`started` event until the query task is about to enter `aexecute`, so a coroutine body that
runs straight through offers no scheduling point and the counter never moves. Both throwaway
probes were deleted.

**ASYNC-01, "MUST NOT widen the warehouse connection budget."** Discharged structurally
rather than by probe: `git diff --stat -- src/semolina` for Task 3 is empty, and no
semaphore, second pool, or second limiter appears anywhere in the plan's library diff.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/unit/test_async_engine.py -x -q` | 6 passed (3 asyncio, 3 trio) |
| `uv run pytest tests/unit/test_async_cursor.py -x -q` | 43 passed |
| `uv run pytest tests/unit/test_async_engine.py -k concurrency -x -q` | 4 passed, 2 deselected |
| `uv run pytest tests/unit/test_async_cursor.py -k stream -q` | 11 passed |
| `uv run pytest tests/unit/test_async_cursor.py -k close -q` | 16 passed |
| `uv run pytest tests/unit -k async -x -q` | 54 passed |
| `uv run pytest -q` (full root suite) | 971 passed, 16 skipped |
| `uv run ruff check src/semolina` (TID251 gate) | All checks passed |
| `uv run basedpyright` (whole project, strict) | 0 errors, 0 warnings, 0 notes |
| `prek run --all-files` | all hooks Passed |
| `just docs-build` (Sphinx `-W`) | build succeeded; `acursor` + `engines/abase` in the API reference |
| Lazy-import probe (`semolina.acursor`, `semolina.engines.abase`) | `lazy ok` — anyio absent from `sys.modules` |
| Public surface shape probe | `surface ok` / `cursor surface ok` |
| `uv run pytest --collect-only src/semolina/acursor.py src/semolina/engines/abase.py` | 0 items — no async doctest prompt slipped in |
| `git diff --stat -- src/semolina` for Task 3 | empty |
| `# type: ignore` added | none; no new `[tool.basedpyright]` exemption either |

Suite went 924 → 967 → 971 across the three tasks (from 922 at the end of Plan 01).

## Deviations from Plan

None — plan executed exactly as written. No auto-fix rules fired; nothing in the plan turned
out to be wrong under execution.

Two things worth recording that changed no behaviour:

1. The pre-commit ruff pin (v0.9.6) is stricter about D403 than the 0.15.x dev dependency on
   docstrings opening with a lowercase identifier, and its autofix produced "Aexecute" and
   "Description". Both docstrings were reworded to read properly rather than accepting the
   mangled capitalisation. The same hook also reflowed four call sites in
   `test_async_cursor.py` that 0.15.x had left wrapped; that reflow is committed.
2. RESEARCH's read-from-source claims about poolhouse's async surface were re-verified
   against the **installed** 1.6.1 package rather than carried forward from the downloaded
   wheel: `create_async_pool` is not a coroutine and takes `pool_size: int | None = None`,
   `close_async_pool` is a coroutine, `AsyncConnection.cursor` is synchronous, all seven
   `AsyncCursor` fetch/close members are coroutines, `description`/`rowcount` are properties,
   and the reader exposes `schema` plus coroutine `__anext__`/`close`. Every claim held.

## Known Stubs

None. Every artifact this plan produced is complete and exercised by a test.

The one honest gap is a documented design limit rather than a stub: an async cursor closed by
neither `async with` nor `aclose()` leaks its pooled connection permanently. No `__del__`
rescue is possible because closing requires awaiting, so `__del__` warns and does nothing
else. This is stated in the method's own docstring, which says explicitly that it is not
parity with the sync cursor's finalizer.

## Threat Flags

None. No new network endpoint, auth path, file access pattern, or schema crosses a trust
boundary here. The plan's own `<threat_model>` rows are discharged as planned:

- **T-46-02** (DoS via leaked slots) — mitigated. Ordered close with narrow suppression, the
  `except BaseException` release-and-re-raise in `aexecute`, and `checkedout() == 0`
  assertions in three separate tests (after normal close, after close with a live reader,
  after two concurrent queries). Residual accepted and documented: the missing `__del__`
  rescue, above.
- **T-46-01** (concurrency bound) — transferred to poolhouse's per-pool limiter; Task 3's
  empty library diff is the evidence.
- **T-46-04** (shared connection across tasks) — transferred; `ConnectionBusyError`
  propagates unwrapped and the class docstring explains why rejecting beats serializing.
- **T-46-06** (`ImportError` disclosure) — mitigated; the message is a static literal that
  interpolates no config field, path, or credential.
- **T-46-08** (SQL generation) — accepted; `aexecute` calls the same
  `build_select_with_params` the sync path calls, so Phase 45's escaping and parameterization
  controls apply verbatim.

## Estimate vs Actual

The plan estimated 75000 tokens at `confidence: low`; the realized diff is 14222 on the same
chars/4 scale — roughly a fifth. The estimate priced this as the phase's risk centre, which
it was, but the risk turned out to be concentrated in *knowing* the close ordering rather
than in writing it. RESEARCH had already read it out of the wheel, so the ordering cost nine
lines. Read the miss as "research displaced implementation tokens", not as an easy phase.

## For Later Plans in This Phase

- The public surface is now fixed and Plans 03-06 can be written against it:
  `create_async_engine(config)`, `AsyncEngine.connect / aexecute / dispose`,
  `AsyncSemolinaCursor` with awaited fetches and synchronous `description` / `rowcount`, and
  `async with await engine.aexecute(q) as cur:` as the canonical call shape.
- Neither `create_async_engine` nor `AsyncSemolinaCursor` is exported from
  `semolina/__init__.py` yet — that export, alongside the async registry, belongs to Plan 04.
  `abase.py` and `acursor.py` are both free of module-level poolhouse async imports, so an
  eager export will be safe when it lands.
- The teardown asymmetry Plan 04 needs: `AsyncEngine.dispose()` is a coroutine, but
  `registry.reset()` is synchronous and autouse-invoked after every test. Tear async engines
  down inline with `close_pool(engine._pool._pool)` — that is what both new fixtures do, and
  it is literally the call `AsyncPool.close` offloads.
- `_sales_query()` is duplicated in both new test modules. If a third async test module needs
  it, promote it to `tests/conftest.py` rather than copying it again.
- The asyncio/Trio matrix costs nothing structural: `pytestmark = pytest.mark.anyio` plus a
  five-line module-local `anyio_backend` fixture. Keep it module-local — `testpaths` includes
  `src` under `--doctest-modules`, so the repo-wide ini option would have a blast radius
  nothing here needs.

## Self-Check: PASSED

- `src/semolina/engines/abase.py` — FOUND
- `src/semolina/acursor.py` — FOUND
- `src/semolina/config.py` (`create_async_engine`) — FOUND
- `tests/conftest.py` (`async_duckdb_engine`, `async_duckdb_file_engine`) — FOUND
- `tests/unit/test_async_engine.py` — FOUND
- `tests/unit/test_async_cursor.py` — FOUND
- Commit `91253f6` — FOUND
- Commit `6bc9f19` — FOUND
- Commit `5de7aaa` — FOUND
- Throwaway probe scripts — correctly ABSENT (both deleted after use)
