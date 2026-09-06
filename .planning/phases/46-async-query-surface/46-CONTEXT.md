# Phase 46: Async Query Surface - Context

**Gathered:** 2026-08-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can run Semolina queries from an async web framework without blocking the event
loop, under either asyncio or Trio, with cancellation that actually reaches the
warehouse. Covers ASYNC-01..06 plus TOOL-01.

Fixed by ROADMAP.md. Posture A only — bare `async def` awaiting adbc-poolhouse
primitives, zero `asyncio.*` and no anyio import in `src/semolina/`. Posture B
(fan-out/timeout sugar Semolina orchestrates) is out of scope, as is async
introspection/codegen and async `fetch_df`/`fetch_polars`/`.into(DTO)` — those belong
to Phase 49 and the deferred ASYNC-F2.

</domain>

<decisions>
## Implementation Decisions

### Engine architecture

- **D-01:** `create_async_engine()` is a **separate constructor** returning a distinct
  `AsyncEngine` type owning exactly one poolhouse `AsyncPool`. This mirrors
  SQLAlchemy, which was checked against the official docs: `create_async_engine()` is a
  distinct function returning `AsyncEngine`, and `AsyncAdaptedQueuePool` "is used by
  default when using `AsyncEngine` engines that were generated from
  `create_async_engine()`". One pool per engine, mode fixed at construction.
- **D-02:** `AsyncEngine` is a **sibling** of `Engine`, not a proxy wrapping one.
  SQLAlchemy's `AsyncEngine`-wraps-`.sync_engine` arrangement works only because its
  async is real async I/O bridged by greenlet over a shared pool. Semolina's async is
  thread-offload and poolhouse's `AsyncPool` is a genuinely separate object from the
  sync `QueuePool`, so there is nothing to proxy. Rejected explicitly.
- **D-03:** One `Engine` holding two pools was **rejected** — no precedent in
  SQLAlchemy, doubles the warehouse connection budget, and breaks the v0.6
  "an Engine owns exactly one pool" invariant.
- **D-04:** `AsyncEngine` shares the dialect and SQL builder with `Engine` unchanged.
  `build_select_with_params()` output is identical for both paths; only connection
  checkout differs (~12 lines). Do not duplicate SQL generation.

### Registry

- **D-05:** **Separate registries** for sync and async engines, chosen for cleaner
  typing over a single registry holding a union of engine kinds. This avoids
  `.using("default").aexecute()` failing at runtime because the registered engine was
  the sync kind. Planner decides the exact public surface (e.g. an async-specific
  `register`/`get_engine` pair vs. a namespaced variant).

### Cursor

- **D-06:** **Separate cursor types** — an async cursor distinct from `SemolinaCursor`,
  consistent with the engine split. Avoids a single class where calling a wrong-mode
  method silently returns a coroutine.
- **D-07:** The async cursor mirrors the existing batch-buffer state machine in
  `cursor.py:238-285` (`_batch_rows` / `_batch_pos` / `_stream_exhausted`), awaiting
  `AsyncRecordBatchReader.__anext__` instead of calling `reader.read_next_batch()`.
  Buffering logic is duplicated rather than shared — a sync and async iterator cannot
  cleanly share a body.

### Connection lifetime (highest-risk area)

- **D-08:** The async path uses **manual checkout with an explicit guard**, matching the
  sync `Engine.execute()` discipline at `engines/base.py:173-186` — check out, keep the
  connection alive past the call, hand it to the cursor, close it in the cursor's close,
  and catch `BaseException` to return the slot on the error path.
- **D-09:** Do **not** follow the `async with await pool.connect() as conn: ... return
  cursor` sketch in the source todo. It returns the connection to the pool while the
  reader is still live, which contradicts the existing `fetch_record_batch` constraint
  that "the cursor must outlive the reader" (arrow-adbc #1893, noted at
  `cursor.py:179-180`).
- **D-10:** The cursor close path must tolerate an **already-invalidated connection**.
  On cancellation poolhouse passes `on_abort=self._owner.invalidate` for poison
  recovery, so the connection may be dead before Semolina closes it. The sync path never
  faced this.

### Dependencies and packaging

- **D-11:** A `semolina[async]` extra pins `adbc-poolhouse[async]>=1.5.0`. A plain
  `pip install semolina` gains no new dependency. The base pin is currently
  `adbc-poolhouse>=1.3.1` (pyproject.toml:11) and **1.3.1 is what is installed** —
  verified, it has no async surface at all. The floor bump is real work, and nothing
  else in this phase can be written or tested until it lands. Sequence it first.
- **D-12:** The async engine must construct its pool via the **config / `dbapi_module`
  path**, not `create_async_pool(driver_path=...)`. The native-shared-library form
  bypasses the Python dbapi module entirely, which would defeat cassette interception
  (see D-15).

### Enforcing Posture A (ASYNC-05)

- **D-13:** Enforce via ruff's `flake8-tidy-imports` banned-API (`TID251`) scoped to
  `src/semolina/`, banning `asyncio` and `anyio` imports, rather than a bespoke grep
  script. Ruff already runs in the quality gate; `TID` is not currently in
  `[tool.ruff.lint] select` (`E,F,W,I,UP,B,SIM,TCH,D`), so this adds a rule.
- **D-14:** The ban scopes to `src/semolina/` **only**. Tests may import anyio freely —
  the Trio half of the test matrix requires it.

### Testing

- **D-15:** Cassette replay through the async path is **viable unmodified** —
  established by reading the poolhouse 1.5.0 source (see Canonical References). This was
  a user-set gate: if replay could not intercept `AsyncCursor`, work stops and
  pytest-adbc-replay gets updated first. It can, so the phase proceeds.
- **D-16:** **Task 1 is a spike** proving one existing cassette replays end-to-end
  through the async path. D-15 is a structural inference from source reading, not an
  executed test — poolhouse 1.5.0 is not installed in the project venv. Nothing else
  should be built on the assumption until the spike confirms it.
- **D-17:** The async test matrix runs under **both asyncio and Trio** via the anyio
  pytest plugin.

### Sequencing

- **D-18:** **TOOL-01 lands last**, as the phase's final commit. Flipping
  `git.branching_strategy` back to `"milestone"` re-arms the GSD commit helper's branch
  auto-switching — the exact behaviour that stranded commits during Phase 44 and caused
  it to be set to `"none"`. Doing it early would migrate this phase's own task commits
  mid-flight.

### Claude's Discretion

- Exact public naming and shape of the async registry surface (D-05).
- Exact name of the async cursor type (D-06).
- Whether `aexecute()` returns an awaited-open cursor (`async with await
  engine.aexecute(q) as cur:`) or an async context manager (`async with
  engine.aexecute(q) as cur:`). ASYNC-01's wording ("`await engine.aexecute(query)`")
  leans to the former; planner may choose on ergonomics.
- Whether an async `fetch_arrow_table()` twin is pulled forward. Not required by
  ASYNC-01..06, but Phase 49 needs it and it sits ~3 lines from the streaming work.
- How `ConnectionBusyError` is surfaced (D-20 below) — message and whether it is
  wrapped in a Semolina exception type.

</decisions>

<specifics>
## Specific Ideas

**SQLAlchemy as the shape reference, not the mechanism.** The user asked directly what
SQLAlchemy does, and its answer settled D-01/D-02/D-03. Take the *structure* (separate
constructor, distinct type, one pool each, mode fixed at construction) but not the
*implementation* (greenlet bridge over an async DBAPI), which does not transfer to
thread-offloaded ADBC.

One axis where Semolina is cleaner than SQLAlchemy: the same ADBC driver serves both
modes, so the sync/async choice is purely which constructor was called, rather than
being smuggled into a connection URL (`postgresql+asyncpg` vs `postgresql+psycopg2`).

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase source of truth
- `.planning/ROADMAP.md` § "Phase 46: Async Query Surface" — goal, the five success
  criteria, the settled-going-in note
- `.planning/REQUIREMENTS.md` § "Async Query Surface" + "Tooling" — ASYNC-01..06, TOOL-01
- `.planning/todos/pending/2026-02-23-async-query-interface-for-fastapi-and-async-frameworks.md`
  — the deep research behind this phase: the UNBLOCKED section listing poolhouse 1.5.0's
  verified API, the ADBC GIL-release feasibility analysis, the where-it-belongs argument,
  and the Posture A/B decision. **Note its `Engine.aexecute` code sketch is superseded by
  D-09.**

### Verified findings on adbc-poolhouse 1.5.0

Established by reading the 1.5.0 wheel source directly (the project venv still has
1.3.1). Re-verify against the installed package once the floor bump lands.

- `_async/_pool.py` — `AsyncPool.connect()` is `await offload(self._pool.connect,
  limiter=self._limiter)`: it offloads the blocking sync SQLAlchemy `QueuePool.connect()`
  to a worker thread. `AsyncPool` is built from the same `_create_pool_impl` as the sync
  pool.
- `_async/_connection.py:287` — `AsyncConnection.cursor()` is "a plain synchronous
  accessor (NOT `async`)" returning an `AsyncCursor` bound to a fresh dbapi cursor.
- `_async/_cursor.py:204+` — `AsyncCursor.execute()` offloads `self._cursor.execute` to a
  thread. Every async method bottoms out in a sync DBAPI call.
- `_async/_reader.py:73,124` — `AsyncRecordBatchReader` wraps anything satisfying a
  `_SyncReader` protocol (`schema` / `read_next_batch` / `close`) **by composition**,
  "rather than subclassing it, so nothing about the concrete Arrow class leaks".
- `_async/_cancel.py:17` — "the literal `anyio.to_thread.run_sync` chokepoint stays in
  `_offload.py`". **This confirms the Trio-compatibility precondition the source todo
  flagged as unverified.**
- `_async/_cursor.py` — cancellation passes `on_abort=self._owner.invalidate` for poison
  recovery (drives D-10).
- `_async/_connection.py:293` — `AsyncConnection` guards an `_in_use` flag; two cursors on
  one connection raises `ConnectionBusyError` (drives D-20).

### Why cassette replay still works (basis for D-15)
- `pytest_adbc_replay/plugin.py:334` — the plugin monkeypatches `driver_mod.connect` for
  each driver named in the `adbc_auto_patch` ini. That patch point is **upstream of the
  entire async stack**, so it fires inside the offload worker thread.
- `pytest_adbc_replay/_cursor.py:105` — `ReplayCursor` is entirely sync (the package
  contains no `async def`, no `await`, no `Async*` class at version 1.1.1). Its
  `fetch_record_batch()` returns a real `pa.RecordBatchReader`, which satisfies
  poolhouse's `_SyncReader` protocol.

### SQLAlchemy precedent (basis for D-01/D-02/D-03)
- https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html — `create_async_engine()`
  as a distinct constructor returning `AsyncEngine`; `.sync_engine` exists but is a
  proxied implementation detail for event registration; `run_sync()` bridges sync-shaped
  calls
- https://docs.sqlalchemy.org/en/20/core/pooling.html — `AsyncAdaptedQueuePool` "is used
  by default when using `AsyncEngine` engines that were generated from
  `create_async_engine()`"

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `engines/sql.py` dialects + `build_select_with_params()` — used unchanged by both
  paths; the async engine adds no SQL-generation code
- `cursor.py:238-285` `__next__` batch-buffer state machine — the template the async
  iterator mirrors (D-07)
- `engines/base.py:173-186` `execute()` checkout-plus-`BaseException`-guard — the
  template for async connection lifetime (D-08)
- `config.py:178` `create_engine()` — the structural model for `create_async_engine()`:
  config-or-name resolution, dialect derivation from config type, DuckDB
  `semantic_views` connect listener wiring
- `query.py:386` `_Query.execute()` → `get_engine(self._using)` → `engine.execute(self)` —
  `aexecute()` is a near-copy against the async registry

### Established Patterns
- **Posture A / neutral awaits.** A plain `async def` that only awaits poolhouse
  coroutines is loop-agnostic by construction. Users never import anyio; agnosticism
  comes from poolhouse plus neutral awaits, not from Semolina adopting anyio.
- **No `# type: ignore`.** Project rule (CLAUDE.md). The poolhouse surface is untyped and
  already carried as `Any` with that noted as deliberate (`engines/base.py:69-86`); the
  async surface will land the same way. Any basedpyright-strict friction must be solved,
  not suppressed — pyproject-level exemptions are the last resort.
- **TDD, failing test first** for anything bug-shaped (CLAUDE.md). Note the Phase 45
  precedent: basedpyright strict rejects a test referencing not-yet-existent attributes,
  so RED and GREEN may have to land in one commit per task.
- **Docstring style** — D213, opening/closing `"""` on own lines, `.. code-block:: python`
  in `Example:` sections (not markdown fences).

### Integration Points
- `pyproject.toml` `[project.optional-dependencies]` — new `async` extra alongside
  `snowflake`/`databricks`/`duckdb`/`codegen-lint`; decide whether `all` includes it
- `pyproject.toml` `[tool.ruff.lint]` — add `TID` to `select` plus a
  `flake8-tidy-imports.banned-api` block (D-13)
- `[dependency-groups] dev` — anyio/Trio pytest support for the D-17 matrix
- `src/semolina/__init__.py` — public export of `create_async_engine` and the async
  registry surface
- `.planning/config.json:13` — `"branching_strategy": "none"` → `"milestone"` (TOOL-01,
  sequenced last per D-18)

### Known Failure Modes To Surface Well
- **D-19:** `create_async_pool(driver_path=...)` silently bypasses cassette interception
  — guard against it (D-12).
- **D-20:** `ConnectionBusyError` from two cursors on one `AsyncConnection` is a new
  failure mode with no sync analogue; give it an actionable message.

### Coverage Caveats
- Databricks' ADBC driver is Foundry-distributed, not on PyPI (`pyproject.toml`
  `[databricks]` comment), so live async verification against Databricks is not possible
  here — cassette replay is the only path.
- DuckDB in-memory pools are the fastest unit-test substrate and need no cassettes.

</code_context>

<deferred>
## Deferred Ideas

- **Posture B concurrency sugar** — fan-out/timeout helpers Semolina orchestrates, which
  would require taking an anyio dependency. Tracked as ASYNC-F1 in REQUIREMENTS.md.
- **Async introspection / codegen** using poolhouse's async `adbc_get_objects` /
  `adbc_get_table_schema`. Tracked as ASYNC-F2.
- **Async `fetch_df()` / `fetch_polars()`** — RESULT-01, Phase 49.
- **Async `.into(DTO)` per-batch conversion** — DTO-02, Phase 49, which hard-depends on
  the cursor this phase delivers.
- **Partitioned reads** (`adbc_execute_partitions`) for intra-query parallelism —
  driver-dependent, listed Out of Scope in REQUIREMENTS.md.
- **FastAPI integration package** (lifespan helper, `Depends()` engine provider, response
  serialization) — gated on this surface existing; its own milestone. See
  `.planning/todos/pending/2026-02-18-fastapi-integration-enhancements.md`.

</deferred>

---

*Phase: 46-async-query-surface*
*Context gathered: 2026-08-01*
