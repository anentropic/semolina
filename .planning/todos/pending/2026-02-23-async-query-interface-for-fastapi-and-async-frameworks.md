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
