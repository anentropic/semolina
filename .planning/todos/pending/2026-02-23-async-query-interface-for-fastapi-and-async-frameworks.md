---
created: 2026-02-23T15:21:41.996Z
updated: 2026-06-25T00:00:00.000Z
title: Async query interface for FastAPI and async frameworks
area: api
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

→ **Companion poolhouse task:** `create_async_pool` + async acquire +
offload-execute + cancel, behind `[async]` extra. Build there FIRST; Semolina's
`aexecute()` is a thin layer on top.

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
