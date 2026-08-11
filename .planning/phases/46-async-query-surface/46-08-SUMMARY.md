---
phase: 46-async-query-surface
plan: "08"
subsystem: docs
tags: [async, cancellation, timeouts, fastapi, starlette, anyio, duckdb, streaming, rst, sphinx]

# Dependency graph
requires:
  - phase: 46-async-query-surface
    provides: "the async query surface (create_async_engine / aexecute / AsyncSemolinaCursor) plans 46-01..46-04 shipped, the four async how-to pages 46-06 wrote, and the executed cancellation evidence in tests/unit/test_async_cancel.py"
provides:
  - "docs/src/how-to/web-api.rst — 'Time out a slow query' (howto-web-api-timeouts)"
  - "docs/src/how-to/web-api.rst — 'Handle a client disconnect' (howto-web-api-client-disconnect)"
  - "docs/src/how-to/streaming.rst — 'Cancel an async stream mid-iteration' (howto-streaming-async-cancel)"
  - "WINDOWS.md entry 1 closed, so /gsd-ship is unblocked for v0.7"
  - "46-VERIFICATION.md body correction retiring the superseded DuckDB non-abort caveat"
affects: [v0.7 ship, phase-46 verification, async docs, future cancellation work]

actuals:
  tokens: 5238
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Every behavioural sentence in a doc section maps to a named test; the mapping is recorded in the SUMMARY"
    - "Framework behaviour is stated only after reading the installed source, and the version read is named in the prose"

key-files:
  created: []
  modified:
    - docs/src/how-to/web-api.rst
    - docs/src/how-to/streaming.rst
    - .planning/WINDOWS.md
    - .planning/phases/46-async-query-surface/46-VERIFICATION.md
    - .planning/phases/46-async-query-surface/deferred-items.md

key-decisions:
  - "46-08: the DuckDB version dependency is written positively (aborting a semantic_view() query needs semantic_views >=0.12.0, which duckdb==1.5.5 installs) with the old behaviour in the past tense — the caveat 46-VERIFICATION.md gap #2 asked for describes a build below the pinned floor and would have cost readers money"
  - "46-08: the client-disconnect section names Starlette 1.0.0 and the two functions read (routing.request_response, requests.Request.is_disconnected), because an unverified promise that a disconnect cancels a query leaves abandoned requests billing the warehouse"
  - "46-08: the streaming section claims propagation and close ordering only — no test measures an abort landing while the caller waits on the next batch, so the elapsed-time evidence is scoped to the executing statement and cross-referenced rather than extended"
  - "46-08: the deadline story is told once, under howto-web-api-timeouts, and referenced from streaming.rst; the no-finalizer cursor leak stays stated once under howto-web-api-async-cursor-close (46-06's canonical-statement rule)"

patterns-established:
  - "Claim-to-test mapping table: a doc plan that documents measured behaviour records one row per behavioural claim, its section, and the test that demonstrates it"

requirements-completed: [ASYNC-06, ASYNC-03]

coverage:
  - id: D1
    description: "'Time out a slow query' documents bounding an async query with a deadline: what exception surfaces, that adbc_cancel aborts the work inside the warehouse, and that the aborted connection is invalidated and replaced"
    requirement: ASYNC-06
    verification:
      - kind: unit
        ref: "tests/unit/test_async_cancel.py#TestCancellationThroughAexecute::test_deadline_over_a_semantic_view_query_is_transparent_and_recovers"
        status: pass
      - kind: unit
        ref: "tests/unit/test_async_cancel.py#TestCancellationReachesTheDriver::test_deadline_aborts_the_query_inside_the_driver"
        status: pass
      - kind: other
        ref: "just docs-build (sphinx-build -W)"
        status: pass
    human_judgment: false
  - id: D2
    description: "'Handle a client disconnect' states what Starlette 1.0.0 actually does with an abandoned request (nothing, verified from installed source) and how to turn a disconnect into a cancellation"
    requirement: ASYNC-06
    verification:
      - kind: unit
        ref: "tests/unit/test_async_cancel.py#TestDeterministicCancellation::test_cancel_during_execute_returns_the_slot"
        status: pass
      - kind: other
        ref: "read .venv/lib/python3.14/site-packages/starlette/routing.py::request_response and starlette/requests.py::Request.is_disconnected (Starlette 1.0.0); cross-checked against upstream main via context7"
        status: pass
    human_judgment: false
  - id: D3
    description: "'Cancel an async stream mid-iteration' states that a cancellation inside the async for body propagates out of the iteration and that the cursor's ordered close does not replace it with a teardown error"
    requirement: ASYNC-03
    verification:
      - kind: unit
        ref: "tests/unit/test_async_cancel.py#TestDeterministicCancellation::test_cancel_midstream_propagates_out_of_async_for"
        status: pass
      - kind: unit
        ref: "tests/unit/test_async_cancel.py#TestDeterministicCancellation::test_cancel_around_the_cursor_block_is_not_masked_by_teardown"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-08-11
status: complete
---

# Phase 46 Plan 08: Cancellation Docs Gap Closure Summary

**The three cancellation sections Phase 46 owed its readers — deadlines, client disconnects, and cancelling a stream mid-iteration — written against the tests that measure them, with broken window 1 closed so `/gsd-ship` is unblocked.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-08-11T22:34:09Z
- **Completed:** 2026-08-11T22:41:00Z (docs + gates), ledger and SUMMARY after
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- `docs/src/how-to/web-api.rst` gained `Time out a slow query` (`howto-web-api-timeouts`) and `Handle a client disconnect` (`howto-web-api-client-disconnect`), positioned between the `async with`-is-required warning and `Query a different engine per endpoint`.
- `docs/src/how-to/streaming.rst` gained `Cancel an async stream mid-iteration` (`howto-streaming-async-cancel`), between the `async for` warning and `Feed a downstream sink`.
- Every behavioural sentence in the three sections maps to a named test in `tests/unit/test_async_cancel.py` (table below). Nothing was written that the tests do not show.
- `.planning/WINDOWS.md` entry 1 is `fixed` via `gsd-tools windows fixed 1`; frontmatter now reads `open_count: 0`, `fixed_count: 1`.
- `46-VERIFICATION.md` carries a dated body correction (frontmatter byte-identical) recording that gap #2's second `missing` bullet — a caveat saying cancellation does not abort a DuckDB semantic-view query — is superseded and must not be written.

## Claim-to-test mapping

One row per behavioural claim in the three new sections. This is the evidence that no sentence outran the measurements.

| # | Claim as written | Section | Demonstrated by |
|---|------------------|---------|-----------------|
| C-1 | "The exception you catch is your framework's, not the driver's" — poolhouse re-raises the cancellation in place of ADBC's interrupt error and Semolina's frames pass it through | Time out a slow query | `TestCancellationThroughAexecute::test_deadline_over_a_semantic_view_query_is_transparent_and_recovers` — the `pytest.fail` arm fires if a driver error escapes instead, plus `isinstance(observed, cancelled_exc_class)` |
| C-2 | "A cancelled `aexecute()` raises rather than handing back a cursor" — no half-open cursor left over | Time out a slow query | `cursor is None` in the same test, and in `TestDeterministicCancellation::test_cancel_before_execute_completes_propagates_and_releases_slot` |
| C-3 | "The work stops in the warehouse, not only in your process" — `adbc_cancel` fires from inside a shield while the worker thread is in the driver; the cancelled aggregate returns in a small fraction of the uncancelled duration; a timed-out request stops accruing warehouse cost | Time out a slow query | `TestCancellationThroughAexecute::...` elapsed-time assertion (`elapsed < measured * ABORT_EVIDENCE_RATIO`) on Semolina's own generated `semantic_view()` SQL; control on plain SQL in `TestCancellationReachesTheDriver::test_deadline_aborts_the_query_inside_the_driver` |
| C-4 | "The connection whose query was aborted is invalidated… the pool opens a replacement, and its checkout count returns to zero" | Time out a slow query | The follow-up cheap query plus `checkedout() == 0` at the end of both long-query tests |
| C-5 | "Wrapping the whole `async with` block… is safe" — ordered close (reader, cursor, connection), each suppressing `Exception` not `BaseException`, so a `ConnectionBusyError` born in teardown cannot replace the cancellation | Time out a slow query | `TestDeterministicCancellation::test_cancel_around_the_cursor_block_is_not_masked_by_teardown` (asserts on the *type* of what escaped) |
| C-6 | DuckDB note: aborting a `semantic_view()` query needs `semantic_views` >= 0.12.0, which the pinned `duckdb==1.5.5` installs; builds below that floor evaluated the inner query on a separate client context where the interrupt flag was never read | Time out a slow query (note) | The measurement table in `tests/unit/test_async_cancel.py`'s module docstring (0.10.3: 3.22s of 3.97s; 0.12.0: 0.55s of 3.21s); `pyproject.toml` `duckdb==1.5.5`; commit `3e653d5` |
| C-7 | "In Starlette 1.0.0… `request_response()` awaits your handler directly. Nothing races it against a disconnect watcher." A disconnect cancels nothing by itself | Handle a client disconnect | Not a Semolina behaviour — read from the installed `starlette/routing.py::request_response` (Starlette 1.0.0, no `task_group`, no `http.disconnect`, no `cancel` anywhere in the module) and cross-checked against upstream `main` via context7 |
| C-8 | "`is_disconnected()` is awaited but never blocks: it reads the receive channel inside an already-cancelled scope" and does consume from that channel | Handle a client disconnect | Read from the installed `starlette/requests.py::Request.is_disconnected` (`with anyio.CancelScope() as cs: cs.cancel(); message = await self._receive()`) |
| C-9 | "Once the cancellation lands, everything in `howto-web-api-timeouts` applies" | Handle a client disconnect | Cross-reference to C-1..C-4; no new claim |
| C-10 | "When the cancellation arrives *after* the connection has been checked out, with the statement already in flight, the slot still comes back: checked-out returns to zero and checked-in goes up by one" | Handle a client disconnect | `TestDeterministicCancellation::test_cancel_during_execute_returns_the_slot` (`inner_pool.checkedout() == 0`, `inner_pool.checkedin() == 1`) |
| C-11 | "A cancellation raised inside the `async for` body propagates out of the iteration. The loop stops at the row it was handling… not converted into a `StopAsyncIteration`, and does not swallow it" | Cancel an async stream mid-iteration | `TestDeterministicCancellation::test_cancel_midstream_propagates_out_of_async_for` (`len(rows) == 1`, `isinstance(observed, cancelled_exc_class)`) |
| C-12 | "The ordered close still holds when the cancellation arrives during teardown" — reader, cursor, connection; `Exception` not `BaseException` | Cancel an async stream mid-iteration | `test_cancel_around_the_cursor_block_is_not_masked_by_teardown` |
| C-13 | "After a cancelled iteration the cursor is closed and the pool's checked-out count returns to zero, so cancelling a stream does not leak a slot" | Cancel an async stream mid-iteration | `test_cancel_midstream_propagates_out_of_async_for` (`cur._closed`, `checkedout() == 0`) |

**Claims deliberately not written**, each because no test measures it:

- That a cancellation landing while the caller waits on the *next batch* aborts that batch fetch in the driver. The elapsed-time evidence covers the executing statement (`aexecute` and `cursor.execute`) only, so the streaming section states propagation and close ordering and cross-references the deadline story rather than extending it.
- That a client disconnect cancels an in-flight query on its own. Read from the installed Starlette source, it does not.
- Any present-tense claim that a cancelled DuckDB `semantic_view()` query carries on computing. False at the pinned floor.
- Cancellation behaviour on Snowflake or Databricks. No live test exists for either in this phase.

## Task Commits

1. **Task 1: Time out a slow query — one section, end to end** — `a843670` (docs)
2. **Task 2: Client disconnect, and cancelling a stream mid-iteration** — `4a20877` (docs)
3. **Task 3: Run the gates, close broken window 1, correct the stale ledger text** — `be516f0` (docs)

## Files Created/Modified

- `docs/src/how-to/web-api.rst` — two new sections (`Time out a slow query`, `Handle a client disconnect`), plus the `See also` entry for `howto-streaming` reworded to mention cancelling mid-iteration
- `docs/src/how-to/streaming.rst` — one new section (`Cancel an async stream mid-iteration`), plus the `See also` entry for `howto-web-api` reworded to mention timeouts
- `.planning/WINDOWS.md` — entry 1 `open` → `fixed`, `open_count: 1` → `0`
- `.planning/phases/46-async-query-surface/46-VERIFICATION.md` — dated post-verification correction appended to the body; frontmatter untouched
- `.planning/phases/46-async-query-surface/deferred-items.md` — the 46-06 cancellation-docs entry closed, naming both files and the plan that landed them

## Gate results

All three run with the command sandbox disabled, as the plan's `<environment>` block requires.

| Gate | Result |
|------|--------|
| `prek run --all-files` | exit 0 (run twice: after Task 2's docs, and again after the `.planning` edits). `blacken-docs` passed both new snippets without reformatting. |
| `just docs-build` | exit 0 (`sphinx-build -W`), all three new labels and every new `:ref:` resolving |
| `just test` | exit 0 — 1051 passed, 16 skipped (unit + doctests), then 16 passed / 15 skipped in the jaffle-shop mock suite |

**Task 3's precondition held.** The venv carries `duckdb 1.5.5` matching `pyproject.toml`, and `semantic_views.duckdb_extension` is cached under `~/.duckdb/extensions/v1.5.5/`. The long-query cancellation tests **ran rather than skipped**: `tests/unit/test_async_cancel.py` is 12/12 green under both asyncio and Trio, with the uncancelled aggregate measured at `semantic_view()` 3.05s and plain SQL 3.26s (4,000,000 rows, digest depth 32) — clear of the 2.0s floor, so `_skip_unless_measurably_slow` did not fire.

## Decisions Made

- **The DuckDB caveat that 46-VERIFICATION.md gap #2 asked for was not written, and the request was retired in place.** The requested text ("as shipped they will pay the query's full cost regardless of client-side cancellation") describes the `semantic_views` extension below 0.12.0. Writing it at the pinned floor would have told readers to keep paying for queries they had cancelled, or to skip building a timeout they believed was cosmetic. The section states the version dependency positively instead, with the old behaviour in the past tense. The correction appended to `46-VERIFICATION.md` names commit `3e653d5` so the next reader can check rather than trust.
- **The client-disconnect section names its source.** Starlette 1.0.0's `request_response` awaits the handler with nothing racing it, which was read from `.venv/lib/python3.14/site-packages/starlette/routing.py` and confirmed against upstream `main`. Naming the version lets a reader on a different Starlette tell whether the advice still applies.
- **The streaming section defers the deadline story rather than retelling it.** `howto-web-api-timeouts` is the one place the abort-reaches-the-driver claim lives; `streaming.rst` cross-references it and scopes the reference to "the statement that is still executing". The no-finalizer cursor leak likewise stays stated once under `howto-web-api-async-cursor-close`.

## Deviations from Plan

None — plan executed exactly as written.

Two plan details worth recording as confirmed rather than changed: the `installation.rst` floor paragraph was already present from 46-06 and was left alone, as the plan's scope note instructed; and `blacken-docs` did not reformat either new snippet, so the anticipated accept-and-recommit loop was not needed.

## Issues Encountered

None. The three gates were green on first run.

## Known Stubs

None. No source code changed; no placeholder or unwired surface was introduced.

## Threat Flags

None. Documentation only — no new endpoint, auth path, file access pattern, or schema. The new snippets use the pages' existing placeholder convention and contain no host, account, or credential (T-46-08-01). Broken window 1 was closed only through `gsd-tools windows fixed 1`, after all three sections existed and `just docs-build` exited 0, so the ledger's own timestamps record the closure (T-46-08-02). The disconnect snippet was verified against the installed Starlette source and names the version it checked (T-46-08-03).

## Flagged assumptions carried forward

The plan's spec-less edge probe surfaced nine unresolved rows (E-01..E-09), none of which this plan closes, since it adds no behaviour. They remain `unresolved` and visible in `46-08-PLAN.md`; E-09's TOOL-01 is behaviourally complete (`.planning/config.json` carries `branching_strategy: "milestone"`) and this plan neither touched nor relied on it.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `WINDOWS.md` reports `open_count: 0`, so `/gsd-ship` is unblocked and the v0.7 milestone can proceed.
- Both of `46-VERIFICATION.md`'s gaps are now closed and the correction is recorded in that file's body, so a re-verification of Phase 46 should return 6/6 rather than 4/6. The frontmatter still says `gaps_found` / `4/6` by design — it is the 2026-08-03 record, not a live status.
- The one stale text that would have sent a future agent to write a false caveat (gap #2's second `missing` bullet) is now explicitly marked superseded in the same file.
- Phase 47 (Type Fidelity Probe & Decision Doc) is independent of 46 and remains the next phase.

## Self-Check: PASSED

All five modified files and this SUMMARY exist on disk; all three task commits (`a843670`, `4a20877`, `be516f0`) are present in `git log`.

---
*Phase: 46-async-query-surface*
*Completed: 2026-08-11*
