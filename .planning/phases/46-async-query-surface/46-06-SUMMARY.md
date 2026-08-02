---
phase: 46
plan: "06"
subsystem: async-documentation
tags: [docs, async, diataxis, how-to, tutorial, fastapi, streaming, connection-pools]
status: complete
requires:
  - "46-01: the semolina[async] extra pinning adbc-poolhouse[async]>=1.6.1"
  - "46-02: create_async_engine, AsyncEngine.aexecute/dispose, AsyncSemolinaCursor"
  - "46-04: register_async_engine / get_async_engine / unregister_async_engine, _Query.aexecute"
provides:
  - "docs/src/how-to/web-api.rst — async engine lifecycle, async def endpoints, the required async with, ConnectionBusyError"
  - "docs/src/how-to/streaming.rst — async for row in cursor, where the work happens, the awaited fetch_arrow_table"
  - "docs/src/how-to/connection-pools.rst — async construction, awaited dispose, the separate async registry, the pool as concurrency bound"
  - "docs/src/tutorials/installation.rst — the semolina[async] extra and a runnable async verification step"
  - "label howto-web-api-async-cursor-close — the canonical statement of the no-finalizer leak, cross-referenced from streaming.rst"
affects:
  - docs/src/how-to/web-api.rst
  - docs/src/how-to/streaming.rst
  - docs/src/how-to/connection-pools.rst
  - docs/src/tutorials/installation.rst
tech-stack:
  added: []
  patterns:
    - "Async sections extend the section that already answers the question, rather than being collected into an async annex — a reader looking up 'how do I dispose an engine' finds both answers in one place"
    - "The sync form is retained everywhere and explicitly described as still correct, so a reader with working sync handlers is not told to rewrite them"
    - "Doc claims verified by execution against the installed floor rather than carried forward from the plan's prose"
key-files:
  created: []
  modified:
    - docs/src/how-to/web-api.rst
    - docs/src/how-to/streaming.rst
    - docs/src/how-to/connection-pools.rst
    - docs/src/tutorials/installation.rst
decisions:
  - "The no-finalizer leak is stated once in full, as a labelled warning subsection in web-api.rst, and cross-referenced from streaming.rst rather than explained twice — one canonical statement cannot drift out of sync with itself"
  - "Cancellation, timeouts, and client-disconnect handling are documented nowhere, because adbc-poolhouse 1.6.1 (the pinned floor) deadlocks on a cancelled in-flight query; omission chosen over a promise that is false against the floor"
  - "Private-path xrefs (semolina.query._Query.aexecute) replaced with plain literals — the private name should not appear in user-facing docs, and autoapi does not document it"
  - "Lifecycle sections switched from close_pool(engine._pool) to engine.dispose(), the sanctioned teardown path since v0.6, rather than documenting the async path alongside a sync example that reaches into a private attribute"
metrics:
  duration: "~1h"
  completed: 2026-08-02
  tasks: 2
  commits: 2
actuals:
  tokens: 7022
  tasks: 2
  commits: 2
---

# Phase 46 Plan 06: Async Documentation Summary

The async surface is now discoverable from four pages a reader already visits, its one
sharp edge is stated plainly instead of softened, and the topic that is not yet true
against the pinned floor is documented nowhere at all.

## What Was Built

**Task 1 — the two how-to pages that show a cursor** (commit `a74f3ff`)

`docs/src/how-to/web-api.rst` gained an async counterpart in every section that had a
synchronous answer: a `create_async_engine` / `register_async_engine` lifespan handler
with `await engine.dispose()` at shutdown, a new "Serve a query from an async endpoint"
section, the `ConnectionBusyError` paragraph in "Handle errors", a labelled
`async with` subsection under "Use the cursor as a context manager", and a note that
`.using()` resolves against the async registry.

The synchronous handler stayed, with a sentence saying why: FastAPI runs a plain `def`
handler in a threadpool, so a blocking `.execute()` does not stall the loop, and an
application whose sync handlers work has no reason to be rewritten. The async form is
for handlers that are `async def` anyway, or a framework with no threadpool fallback.

The "two differences and no others" paragraph is deliberate framing. A reader comparing
the two endpoints should be able to see that the call is awaited and the fetch methods
are awaited, and that `Row`, `description`, and `rowcount` are unchanged — rather than
inferring that async is a different API.

`docs/src/how-to/streaming.rst` gained an async iteration section positioned directly
after the sync one, in parallel structure, plus the awaited `fetch_arrow_table` in the
"when to stream" section. The paragraph the phase actually exists for is the one about
where the work happens: adbc-poolhouse pulls each batch on a worker thread so the loop
is free while the warehouse computes it, and Semolina maps that batch to `Row` objects
on the loop thread, bounded by one batch rather than the whole result. That is the
reader's real question and it now has an honest answer, including the part that is not
offloaded.

**Task 2 — packaging and the engine lifecycle page** (commit `0ecb365`)

`docs/src/tutorials/installation.rst` gained "Optional: async support", shaped after the
existing `codegen-lint` section: the install command, the composable
`semolina[snowflake,async]` form, the statement that a plain install picks up no part of
it, and that `all` includes `async`. The `>=1.6.1` floor is named with its reason —
before 1.6.0 `create_async_pool` ignored the config's `pool_size` and always built five,
so a `DuckDBConfig(database=":memory:", pool_size=1)` would have got five isolated
in-memory databases.

"Verify the installation" gained a step that actually discriminates:
`python -c "from adbc_poolhouse import create_async_pool; print('async support ready')"`.
`import semolina` succeeds with or without the extra because the async stack is resolved
lazily, so the obvious check would have told the reader nothing.

`docs/src/how-to/connection-pools.rst` was extended section by section rather than given
an async annex: `create_async_engine` beside `create_engine`, the sizing section covering
both pool kinds, `await engine.dispose()` in both lifecycle sections with the
construction asymmetry explained, an "Async engines live in a separate registry"
subsection, async `.using()` resolution, and the concurrency-bound paragraph.

## The leak, stated once and stated plainly

The plan's kept prohibition forbids presenting `async with` as a style preference. The
full statement lives in one place, `web-api.rst` under the label
`howto-web-api-async-cursor-close`, as a `.. warning::` titled
"``async with`` is required, not recommended". It says that `SemolinaCursor` has a
finalizer that returns a forgotten connection to the pool, that `AsyncSemolinaCursor`
cannot have one because closing requires awaiting and a finalizer cannot await, that a
cursor closed by neither `async with` nor `await cursor.aclose()` holds its pooled
connection for the life of the process, that nothing reclaims it later, and that the
`ResourceWarning` reports the leak without repairing it.

`streaming.rst` carries a shorter warning naming the same requirement and the same
reason, cross-referencing that label rather than re-explaining. Neither page anywhere
describes the two cursors as behaving alike on the forgotten path; the paragraph about
`with` being "deterministic and immediate" was left attached to the sync cursor where it
is true, and the async warning immediately follows it so the contrast is visible.

## Deliberately omitted, pending adbc-poolhouse 1.6.2

**Cancellation, timeouts, and client-disconnect handling are documented nowhere on these
four pages.** This is the topic a reader building a FastAPI backend would most naturally
expect in the async web-API how-to, and its absence is a decision rather than an
oversight.

ASYNC-06 (cancellation reaching the warehouse) is not proven and its test has not
landed. A deadlock in adbc-poolhouse 1.6.1 was found during this phase: cancelling an
in-flight query wedges the worker thread permanently, hanging the awaiting task forever
and leaking both a thread and a connection. The upstream fix is an open PR
(anentropic/adbc-poolhouse#43, version 1.6.2) and is not released; this project's floor
is still `>=1.6.1`.

Writing "cancel a slow query with a timeout" or "queries stop when the client
disconnects" would therefore have documented a hang as a feature. Omission was chosen
over a hedged claim, because a hedged claim still puts the pattern in front of a reader
who will copy the code and skim the caveat.

**What a follow-up should add once 1.6.2 ships and the floor moves:**

1. `web-api.rst` — a timeout section: cancelling an `aexecute()` in a cancellation scope,
   what reaches the warehouse (`adbc_cancel`), and what the connection's state is
   afterwards (poolhouse invalidates a connection whose query it aborted).
2. `web-api.rst` — client disconnect: what happens to an in-flight query when the
   request is abandoned, and whether the pool slot comes back.
3. `streaming.rst` — cancelling mid-iteration, and whether the ordered close still holds
   when the cancellation arrives during teardown (`aclose()` suppresses `Exception`, not
   `BaseException`, specifically so it does).
4. `installation.rst` — the floor bump to `>=1.6.2` and its reason, replacing the
   current 1.6.1 paragraph.

Nothing currently written contradicts any of this; the four pages are additive with
respect to the missing topic.

## Claims verified against the shipped floor, and two corrections

The plan required the pool-sizing section be read against shipped behaviour rather than
trusted. Every claim was checked by executing against the installed adbc-poolhouse 1.6.1.

| Claim as written | Verdict |
|---|---|
| Config classes carry `pool_size`, `max_overflow`, `timeout`, `recycle` | True |
| `timeout` default 30, `recycle` default 3600 | True |
| Config-supplied sizing is honoured (the section's whole premise) | True at this floor; `create_async_pool`'s signature defaults every tuning arg to `None` and derives from the config |
| "The defaults are 5 and 3" | **Corrected** |
| "DuckDB defaults to `pool_size=1`" | **Corrected** |
| `pool_size > 1` with `:memory:` raises `ValidationError` | True — pydantic `ValidationError`, confirmed by construction |

**Correction 1.** "The defaults are 5 and 3, so up to 8 concurrent connections" became
"For Snowflake and Databricks the defaults are 5 and 3, so up to 8 concurrent
connections." `DuckDBConfig` does not default to 5, so the unqualified sentence was
false for one of the three supported backends.

**Correction 2.** "DuckDB defaults to ``pool_size=1``" became a note distinguishing the
two cases: an in-memory database pins `pool_size` to 1, while a file-backed path
defaults to 5 and can be raised. Verified directly —
`DuckDBConfig(database=":memory:").pool_size` is 1 and
`DuckDBConfig(database="x.db").pool_size` is 5. The old sentence would have led a reader
with a file-backed DuckDB to believe their async pool was serialized behind one
connection when it was not.

The concurrency-bound claim was verified too rather than asserted: poolhouse's
`_async/_pool.py` builds `anyio.CapacityLimiter(pool_size + max_overflow)`, one per pool,
which is what the new paragraph states.

## Deviations from Plan

**1. [Rule 1 - Bug] Lifecycle sections switched from `close_pool(engine._pool)` to
`engine.dispose()`.**

- **Found during:** Task 2, while adding `await engine.dispose()` to the two lifecycle
  sections.
- **Issue:** Both sections told the reader to call `close_pool(engine._pool)`, reaching
  into a private attribute, and a `.. warning::` instructed them to do so. Since v0.6
  `Engine.dispose()` is the sanctioned teardown path, and its own docstring says so.
  Documenting `await engine.dispose()` for async while leaving the sync example on
  `close_pool(engine._pool)` would have implied the two paths differ in shape when they
  differ only by the `await`.
- **Fix:** Both lifecycle sections and the shutdown-loop example now call
  `engine.dispose()`; the warning was rewritten to say why disposing beats reaching into
  `_pool`, including the async-specific hazard that the pool's own `close()` is a
  coroutine which silently closes nothing if not awaited.
- **Files modified:** `docs/src/how-to/connection-pools.rst`
- **Commit:** `0ecb365`

**2. [Rule 1 - Bug] Stale version in the installation tutorial's verification output.**

- **Found during:** Task 2, extending "Verify the installation".
- **Issue:** The expected output block showed `0.4.0`; `pyproject.toml` is at `0.6.0`, so
  a reader following the tutorial would see a mismatch on the first command they ran.
- **Fix:** Updated to `0.6.0`, verified by executing the command.
- **Files modified:** `docs/src/tutorials/installation.rst`
- **Commit:** `0ecb365`

**3. Two private-path cross-references replaced with plain literals.**

`:py:meth:`~semolina.query._Query.aexecute`` was written into both Task 1 pages and then
removed. autoapi does not document `_Query` (private), so the reference resolved to
nothing, and a private module path should not appear in user-facing prose regardless.
Both became plain ``aexecute()`` literals. No behaviour change; caught by checking the
built `objects.inv` rather than by the build, since Sphinx is not in nitpicky mode here.

**4. `blacken-docs` reformatted two snippets in `connection-pools.rst` on commit.**

The hook wraps at a narrower width than the source line length. Its rewrite was accepted,
except that it left a trailing comment awkwardly split across a wrapped call; that
comment was moved onto its own line before re-committing. No content change.

## Out of Scope

`docs/src/how-to/warehouse-testing.rst` still calls `close_pool(engine._pool)` at lines
36 and 83, now inconsistent with the lifecycle guidance on `connection-pools.rst`. That
page is not in this plan's `files_modified` and its example is not wrong, only dated.
Logged in `.planning/phases/46-async-query-surface/deferred-items.md`.

## Known Stubs

None. Every section this plan added is complete prose against shipped behaviour.

The one deliberate absence is the cancellation topic documented above, which is a
recorded omission rather than a stub: no placeholder, no "coming soon", and nothing on
these pages implies the topic is covered.

## Threat Flags

None. No new network endpoint, auth path, file access pattern, or schema crosses a trust
boundary. The plan's `<threat_model>` rows are discharged:

- **T-46-13** (documented cursor lifecycle) — mitigated. The leak is stated in full on
  `web-api.rst` under a label and restated with a cross-reference on `streaming.rst`.
  Neither page claims parity with the sync cursor's forgotten-path rescue; the kept
  prohibition holds.
- **T-46-04** (documented concurrency patterns) — mitigated. The `ConnectionBusyError`
  paragraph in "Handle errors" names the remedy (a separate `aexecute()` call per task)
  and says explicitly not to reach for a lock, with the reason.
- **T-46-01** (documented concurrency tuning) — mitigated. The pools how-to states that
  the pool's capacity limiter, sized to `pool_size + max_overflow`, is the only bound and
  that a user-supplied semaphore stacks a second limit below what was configured.
- **T-46-14** (credentials in examples) — accepted, unchanged. Every new snippet uses the
  pages' existing placeholder convention (`password="..."`, `xy12345.us-east-1`) or reads
  from a named TOML section.

## Verification

| Check | Result |
|-------|--------|
| `just docs-build` (Sphinx `-W`) after Task 1 | build succeeded |
| `just docs-build` (Sphinx `-W`) after Task 2 | build succeeded |
| `grep -c 'aexecute' docs/src/how-to/web-api.rst` (≥2) | 8 |
| `grep -c 'create_async_engine' docs/src/how-to/web-api.rst` (≥1) | 4 |
| `grep -c 'register_async_engine' docs/src/how-to/web-api.rst` (≥1) | 6 |
| `grep -c 'async for' docs/src/how-to/streaming.rst` (≥1) | 4 |
| `grep -c 'aexecute' docs/src/how-to/streaming.rst` (≥1) | 3 |
| `grep -c 'def get_sales' docs/src/how-to/web-api.rst` (≥1, sync form retained) | 8 |
| `grep -c 'for row in cursor' docs/src/how-to/streaming.rst` (≥1, sync form retained) | 8 |
| `grep -c 'semolina\[async\]' docs/src/tutorials/installation.rst` (≥1) | 2 |
| `grep -c '1\.6\.1' docs/src/tutorials/installation.rst` (≥1) | 1 |
| `grep -c 'create_async_engine' docs/src/how-to/connection-pools.rst` (≥1) | 10 |
| `grep -c 'get_async_engine' docs/src/how-to/connection-pools.rst` (≥1) | 6 |
| `grep -c 'register_async_engine' docs/src/how-to/connection-pools.rst` (≥1) | 13 |
| `grep -c 'dispose' docs/src/how-to/connection-pools.rst` (≥2) | 11 |
| `grep -c 'code-block:: pycon'` across all four pages | 0 on every page |
| `find docs/_build -name '*acursor*'` | `reference/api/semolina/acursor` + module page |
| `find docs/_build -name '*abase*'` | `reference/api/semolina/engines/abase` + module page |
| Task 1 identifier probe (`create_async_engine`, `register_async_engine`, `get_async_engine`, `AsyncSemolinaCursor` off `semolina`) | `doc identifiers ok` |
| Task 2 identifier probe (registry trio, `create_async_engine`, `AsyncEngine.dispose`) | `doc identifiers ok` |
| Async verification command from the tutorial, executed | `async support ready` |
| `python -c "import semolina; print(semolina.__version__)"` matches the documented output | `0.6.0` |
| Pool sizing defaults, executed against installed 1.6.1 | Snowflake/Databricks 5/3, DuckDB `:memory:` 1, DuckDB file 5 |
| `DuckDBConfig(database=":memory:", pool_size=3)` | raises `ValidationError` as documented |
| `prek` hooks on both commits | Passed (`blacken-docs` rewrote once, see Deviations) |

## Estimate vs Actual

Estimated 40000 tokens at `confidence: low`; realized 7022 on the same chars/4 scale over
the four-file diff. The estimate priced the prose as the work. It was not: 46-02 and
46-04 had already written the honest version of every hard sentence into docstrings and
summaries — the leak, the close ordering, the busy-connection rationale, the
construction/teardown asymmetry — so drafting was largely transposition into the pages'
existing voice. The unbudgeted work was verification: executing every sizing claim
against the installed floor, which is what produced the two corrections, and checking the
built `objects.inv` for dangling references. Read the miss the way 46-02's and 46-04's
were read: upstream work displaced this plan's tokens, not that documentation is cheap.

## For the Rest of the Phase

- The canonical statement of the async cursor leak is the label
  `howto-web-api-async-cursor-close` in `web-api.rst`. Any later page that shows an async
  cursor should cross-reference it rather than restate it.
- Short-form cross-references like `:py:class:`~semolina.AsyncSemolinaCursor`` do not
  resolve in `objects.inv` — autoapi documents `semolina.acursor.AsyncSemolinaCursor`.
  This matches the existing site-wide convention (`~semolina.SemolinaCursor` and
  `~semolina.Row` are equally unresolved), produces no warning, and was kept for
  consistency. A site-wide fix is a separate piece of work.
- The cancellation follow-up above is the phase's outstanding documentation debt. It is
  gated on adbc-poolhouse 1.6.2 shipping and the floor moving, not on anything in this
  repository.

## Self-Check: PASSED

- `docs/src/how-to/web-api.rst` — FOUND
- `docs/src/how-to/streaming.rst` — FOUND
- `docs/src/how-to/connection-pools.rst` — FOUND
- `docs/src/tutorials/installation.rst` — FOUND
- Commit `a74f3ff` — FOUND
- Commit `0ecb365` — FOUND
