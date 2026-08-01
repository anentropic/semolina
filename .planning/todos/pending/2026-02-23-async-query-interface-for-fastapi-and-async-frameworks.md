---
created: 2026-02-23T15:21:41.996Z
updated: 2026-06-25T00:00:00.000Z
title: Async query interface for FastAPI and async frameworks
area: api
resolves_phase: 46
files:
  - src/semolina/query.py
  - src/semolina/engines/
  - src/semolina/registry.py
---

## Problem

Semolina's `.execute()` is synchronous — it blocks the event loop when called
from an async route handler (FastAPI, Starlette, Litestar, Django async views).
Today users must wrap calls in `run_in_executor()` / `anyio.to_thread` themselves
or accept blocking their async app. This is a prerequisite for first-class async
web-framework integration.

## UNBLOCKED 2026-07-05 — adbc-poolhouse 1.5.0 shipped the async stack

The predicted "companion poolhouse task" is **DONE upstream**. poolhouse 1.5.0
ships async behind an optional `[async]` extra (`anyio>=4.13`) — the exact shape
this todo specified. Real API (verified against the 1.5.0 wheel):

    from adbc_poolhouse import create_async_pool, managed_async_pool, close_async_pool

    pool = create_async_pool(cfg, pool_size=5, max_overflow=3, timeout=30)  # -> AsyncPool
    async with await pool.connect() as conn:          # AsyncConnection (async ctx mgr)
        cur = conn.cursor()                            # AsyncCursor
        await cur.execute(sql, params)
        reader = await cur.fetch_record_batch()        # AsyncRecordBatchReader
        async for batch in reader:                     # streaming, async-iterable
            ...

- `AsyncPool.connect()/close()`, `managed_async_pool` (async-gen ctx mgr).
- `AsyncCursor`: `execute/executemany`, `fetch_arrow_table/fetch_record_batch/
  fetch_df/fetch_polars/fetchone/fetchmany/fetchall`, all `async`; `adbc_cancel`
  wired (`_async._cancel`); thread-offload in `_async._offload`.
- `AsyncRecordBatchReader`: async ctx mgr + `__aiter__`/`__anext__` → the
  **streaming batch fetch Posture A relied on** (poolhouse offloads, Semolina
  awaits + maps). Bonus: async introspection (`adbc_get_objects`,
  `adbc_get_table_schema`, ...) — lets Semolina codegen/introspection go async too.
- New `ConnectionBusyError` (guards concurrent misuse of one connection — the
  pool's per-op checkout is still the isolation boundary).
- Poolhouse is anyio-based, so Semolina's neutral `await`s stay Trio-compatible
  (verify `_offload` uses `anyio.to_thread`, not `asyncio`, before relying on it).

**Impact on this todo:** the hard/generic part is delivered. What remains is the
thin Semolina layer below (Posture A) + a version floor bump to
`adbc-poolhouse[async]>=1.5.0` (gated behind a Semolina `[async]` extra). This is
now **ready to plan as a milestone**, not blocked research.

Concrete Semolina layer (Posture A, no anyio import needed):

    class Engine:
        async def aexecute(self, query) -> SemolinaCursor:
            async with await self._pool.connect() as conn:
                cur = conn.cursor()
                await cur.execute(query.sql, query.params)
                reader = await cur.fetch_record_batch()
                return SemolinaCursor(reader, dialect=self._dialect)  # maps batches->Rows

## Feasibility (researched 2026-06-25)

**The Python ADBC stack is sync-only** — confirmed against
`adbc_driver_manager` 1.10.0: no coroutines, the DBAPI `Cursor` exposes only
synchronous `execute` / `fetch_*`. No async API exists or is on the roadmap.

**BUT meaningful async is achievable, not cosmetic**, because ADBC releases the
GIL during its blocking native calls. The Cython driver manager wraps every
native call in `with nogil:` (66 sites); the query path is explicit
(`_lib.pyx`):

    with nogil:
        status = AdbcStatementExecuteQuery(...)

Consequences of the GIL being dropped for the whole network round-trip:

1. **Event-loop non-blocking** — offloading `execute()`/`fetch()` to a thread
   (`anyio.to_thread.run_sync`) lets the async handler yield while the query
   runs. Justifies the feature on its own.
2. **Genuine parallelism** — N queries on N threads overlap their round-trips;
   `gather(q1, q2, q3)` total latency ≈ slowest, not the sum. The GIL release
   is what makes this real concurrency rather than a serialized façade. Same
   pattern psycopg/stdlib rely on.

Why it fits the v0.6 architecture:
- ADBC connections/statements are NOT safe to share across threads
  concurrently, but the **Engine-owns-the-pool** model already checks out one
  connection per operation — so async concurrency is naturally bounded by pool
  size (correct backpressure). We add an async checkout path, not a new model.
  See [[project_v06_engine_owns_pool]].
- ADBC exposes `adbc_cancel` (on the `Cursor`), so async timeouts/cancellation
  can actually cancel the in-flight query — makes the async surface more than a
  wrapper.

Honest caveats:
- Thread-pool concurrency, not native async I/O to the socket. Functionally
  equivalent for this workload; state it plainly, don't oversell.
- Use **anyio** (asyncio + Trio, first-class cancellation), not raw asyncio.
- Deeper, driver-dependent, OPTIONAL angles — do not commit up front:
  partitioned reads (`adbc_execute_partitions` / `adbc_read_partition`) for
  intra-query parallelism; free-threaded CPython 3.13+ to drop the thread pool.

## Where it belongs: mostly adbc-poolhouse, not Semolina (analysis 2026-06-25)

adbc-poolhouse is a generic, warehouse-agnostic ADBC pool lib (15 warehouse
configs) backed by **SQLAlchemy `QueuePool`** (`create_pool(...) ->
sqlalchemy.pool.QueuePool`, knobs `pool_size` / `max_overflow` / `timeout`).
Semolina is just one consumer. The generic async plumbing therefore belongs
DOWN in poolhouse, reusable by every consumer:

**poolhouse owns (generic):**
- Async checkout — swap `QueuePool` -> SQLAlchemy's `AsyncAdaptedQueuePool`
  (already shipped); async acquire that *awaits* on pool exhaustion instead of
  parking a thread.
- Thread-offload of `execute`/`fetch` (`anyio.to_thread` around the
  GIL-releasing ADBC call) — warehouse-agnostic.
- `adbc_cancel` on timeout/cancellation — operates on the conn poolhouse owns.

**Clinching argument — co-locate the concurrency envelope:** `pool_size +
max_overflow` IS the concurrency bound and the worker executor must be sized to
exactly that. Those numbers live in poolhouse. Offload-in-Semolina forces
Semolina to reach into poolhouse internals to size its pool → leaky
abstraction. Offload-in-poolhouse keeps capacity + executor together.

**Semolina keeps (thin ORM ergonomics):** `Query.aexecute()`, async result
iteration (`__aiter__`), `Engine.aexecute()` — all delegating to poolhouse
primitives.

Why poolhouse is well-positioned: it already depends on SQLAlchemy, so
`AsyncAdaptedQueuePool` + the greenlet bridge come for free — incremental, not a
greenfield async stack. Same author owns both repos → coordinated change.

Costs (real, not rubber-stamp): poolhouse is currently focused+sync, async
~doubles its surface/test matrix — gate behind an optional `[async]` extra so
the sync install stays lean and contains the anyio dep. `AsyncAdaptedQueuePool`
standalone (outside `create_async_engine`) needs care. Mechanism is threads
either way (ADBC has no async C API) — this is a *where-does-it-live* call, not
a perf one. See [[reference_adbc_gil_release_async]].

→ **Companion poolhouse task: DONE in adbc-poolhouse 1.5.0** (2026-07-05) —
`create_async_pool` + `AsyncPool.connect` + `AsyncCursor` + `AsyncRecordBatchReader`
+ `adbc_cancel`, behind the `[async]` extra. See the UNBLOCKED section at top.
Semolina's `aexecute()` is now a thin layer on top; ready to plan.

## anyio posture for Semolina's layer (decided 2026-06-25)

Agnosticism for *users* comes from poolhouse (anyio + sniffio loop detection)
plus **neutral awaits** — NOT from Semolina importing anyio. A plain `async def`
that only `await`s poolhouse coroutines is backend-neutral by construction
(runs identically under asyncio and Trio); cancellation propagates for free
into poolhouse's cancel scope → `adbc_cancel`. Users never import anyio; they
`await semolina.aexecute()` from their own framework. anyio stays an
implementation detail of the lower layers.

The thin pass-through needs NO anyio import:

    class Engine:
        async def aexecute(self, query) -> SemolinaCursor:
            async with self._pool.acquire() as conn:        # poolhouse async ctx
                raw = await conn.execute(query.sql, query.params)  # poolhouse offload
                return SemolinaCursor(raw, dialect=self._dialect) # sync map, fast

This requires poolhouse to own ALL `to_thread` offload — incl. a streaming async
record-batch fetch so Semolina's `__aiter__` just awaits the next batch and maps
it (poolhouse offloads, Semolina maps).

**THE HARD RULE: zero `asyncio.*` in Semolina library code.** Using
`asyncio.gather`/`asyncio.timeout`/`asyncio.TaskGroup` silently locks users into
asyncio and breaks Trio. Where Semolina owns concurrency (fan-out helpers,
timeout sugar, orchestration), use **anyio** (`create_task_group`, `fail_after`)
— never asyncio.

**Posture: start MINIMAL (Posture A), no anyio dep in Semolina.**
- A — Minimal (chosen first): only `aexecute()` + async iteration, all bare
  `async def` awaiting poolhouse. Users compose concurrency/timeouts with their
  own framework. Thinnest, agnostic by construction, zero new deps.
- B — Batteries (defer): if we add fan-out/timeout sugar Semolina orchestrates,
  THEN pull in anyio (trivial — already transitive via poolhouse; typed for
  basedpyright strict). Agnosticism guarantee holds either way.

Do not adopt anyio in Semolina reflexively to "match" poolhouse — adopt the
rule, keep pass-through neutral, add anyio only at the exact points Semolina
composes concurrency. See [[reference_adbc_gil_release_async]].

## Solution (options to explore at planning time)

- Surface: `await Sales.query().metrics(Sales.revenue).aexecute()` (async
  twin of `.execute()`), returning an awaitable that resolves to the same
  result type. Possibly an async `__aiter__` for streaming (compounds with the
  lazy/streaming-result todo).
- Engine layer: `async def aexecute()` on the Engine that does
  `anyio.to_thread.run_sync(self.execute, ...)` with the connection checked out
  inside the worker thread; wire structured cancellation to `adbc_cancel`.
- Decide anyio vs asyncio-only (lean anyio).
- Thread-pool sizing tied to the adbc-poolhouse pool size, not the default
  asyncio executor, so concurrency == available connections.

Related todos:
- FastAPI integration enhancements (serialization, lifecycle, DI)
- Lazy/streaming Result (async iteration via `__aiter__`)
