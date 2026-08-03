---
phase: 46-async-query-surface
plan: 05
subsystem: testing
tags: [anyio, trio, asyncio, adbc-poolhouse, duckdb, cancellation, ast, pytest]

# Dependency graph
requires:
  - phase: 46-async-query-surface (plan 02)
    provides: AsyncEngine.aexecute, AsyncSemolinaCursor, create_async_engine, the async DuckDB fixtures
  - phase: 46-async-query-surface (plan 01)
    provides: the trio dependency and the async extra
provides:
  - executed proof that a cancelled aexecute raises instead of returning a cursor, and returns its pool slot
  - executed proof that an abort fired by a framework deadline stops the query inside the DuckDB driver
  - executed proof that the pool recovers after an aborted query, with checkedout() back to 0
  - a structural build gate requiring every async test module to run under both asyncio and Trio
  - a measured, documented limit of the DuckDB semantic_views extension as a cancellation substrate
affects: [async, testing, ci, docs, warehouse-dialects]

actuals:
  tokens: 9800
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "measure-then-assert: a test that needs an expensive query measures one uncancelled run and derives its deadline from the measurement, instead of hardcoding a duration or racing a sleep"
    - "structural test invariants: enforce a cross-module testing convention by parsing the test tree with ast rather than by importing test modules"
    - "faulthandler watchdog: guard a block that can wedge inside a native call with a real-clock timer, since no event-loop timeout can reach a blocked worker thread"

key-files:
  created:
    - tests/unit/test_async_cancel.py
    - tests/unit/test_asyncio_trio_matrix.py
  modified: []

key-decisions:
  - "The abort-reached-the-driver claim is asserted as elapsed time against the measured uncancelled duration, deviating from the plan's no-elapsed-comparison criterion, because nothing else distinguishes a real abort from a client that merely stopped waiting"
  - "That claim runs over plain SQL through AsyncEngine.connect() rather than over aexecute, because DuckDB's semantic_views extension does not observe the interrupt flag inside its table function"
  - "The aexecute path keeps the transparency and pool-recovery claims and explicitly makes no early-abort claim, so no test certifies a property it cannot observe"
  - "The long-query family is guarded by a faulthandler watchdog rather than an anyio timeout, because the pre-1.6.2 upstream deadlock hung inside a native call where no loop-level timeout can reach"
  - "The loop-matrix checker selects modules by content (an ast walk for async test functions), never by filename, so async-free modules need no hand-maintained exclusion list"

patterns-established:
  - "Cancellation tests split by risk: a deterministic family with no timing at all carries the propagation and slot-release assertions, and a measured long-query family carries the reached-the-driver assertion"
  - "A test that cannot establish its claim on the available substrate says so in its docstring and hands the claim to a sibling test, rather than asserting something weaker under the same name"

requirements-completed: [ASYNC-05, ASYNC-06]

coverage:
  - id: D1
    description: "A cancelled aexecute propagates the cancellation, never returns a cursor, and leaves the pool's checkedout() at 0"
    requirement: ASYNC-06
    verification:
      - kind: unit
        ref: "tests/unit/test_async_cancel.py#TestDeterministicCancellation::test_cancel_before_execute_completes_propagates_and_releases_slot"
        status: pass
    human_judgment: false
  - id: D2
    description: "Cancelling mid-stream during `async for` propagates, and the cursor's teardown does not raise a second error over it"
    requirement: ASYNC-06
    verification:
      - kind: unit
        ref: "tests/unit/test_async_cancel.py#TestDeterministicCancellation::test_cancel_midstream_propagates_out_of_async_for"
        status: pass
      - kind: unit
        ref: "tests/unit/test_async_cancel.py#TestDeterministicCancellation::test_cancel_around_the_cursor_block_is_not_masked_by_teardown"
        status: pass
    human_judgment: false
  - id: D3
    description: "A deadline expiring during a measured-expensive query aborts the query inside the driver — the cancelled call returns in a fraction of the uncancelled duration — and surfaces the framework cancellation rather than the driver's interrupt error"
    requirement: ASYNC-06
    verification:
      - kind: unit
        ref: "tests/unit/test_async_cancel.py#TestCancellationReachesTheDriver::test_deadline_aborts_the_query_inside_the_driver"
        status: pass
    human_judgment: false
  - id: D4
    description: "After a cancelled query the pool recovers: a subsequent query on the same engine succeeds and checkedout() returns to 0"
    requirement: ASYNC-06
    verification:
      - kind: unit
        ref: "tests/unit/test_async_cancel.py#TestCancellationReachesTheDriver::test_deadline_aborts_the_query_inside_the_driver"
        status: pass
      - kind: unit
        ref: "tests/unit/test_async_cancel.py#TestCancellationThroughAexecute::test_deadline_over_a_semantic_view_query_is_transparent_and_recovers"
        status: pass
    human_judgment: false
  - id: D5
    description: "Semolina contributes zero lines of cancellation logic — the library diff for this plan is empty"
    requirement: ASYNC-06
    verification:
      - kind: other
        ref: "git diff --stat 638a800~1 HEAD -- src/semolina (empty output)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Every test module defining an async test carries the anyio marker and a module-local backend fixture over both asyncio and Trio, enforced structurally so a future module cannot silently cover one backend"
    requirement: ASYNC-05
    verification:
      - kind: unit
        ref: "tests/unit/test_asyncio_trio_matrix.py#TestLoopMatrixIsEnforcedStructurally::test_every_async_test_module_covers_asyncio_and_trio"
        status: pass
      - kind: unit
        ref: "tests/unit/test_asyncio_trio_matrix.py#TestLoopMatrixIsEnforcedStructurally::test_discovery_is_not_vacuous"
        status: pass
      - kind: other
        ref: "fail-first probe: a non-conforming tests/unit/test_async_ffprobe.py makes the checker exit non-zero; probe file removed"
        status: pass
    human_judgment: false
  - id: D7
    description: "DuckDB's semantic_views extension does not honour the interrupt flag inside its table function — a documented substrate limitation with consequences for how ASYNC-06 can be tested locally"
    verification: []
    human_judgment: true
    rationale: "This is a finding about a third-party extension, not a shipped behaviour. It needs a human to decide whether to file it upstream and whether it changes the phase's testing posture for other warehouses."

# Metrics
duration: 55min
completed: 2026-08-03
status: complete
---

# Phase 46 Plan 05: Cancellation Proof and the Loop-Matrix Gate Summary

**A measured proof that a framework deadline aborts the query inside the DuckDB driver and leaves a working pool, plus an AST-based build gate that stops any future async test module from silently covering only asyncio**

## Performance

- **Duration:** ~55 min across two sessions (Task 2 landed 2026-08-02, Task 1 on 2026-08-03 after an upstream fix unblocked it)
- **Started:** 2026-08-02T09:30:00+01:00
- **Completed:** 2026-08-03T19:06:00+01:00
- **Tasks:** 2
- **Files modified:** 2 created, 0 modified

## Accomplishments

- **Cancellation is proven to reach the driver, not merely to stop the client.** A deadline set at one tenth of a measured 3.1s aggregate returns in ~0.32s against a 3.1s uncancelled baseline, on both asyncio and Trio. That elapsed comparison is the whole point: a test asserting only "the caller saw a cancellation" greens identically whether the warehouse stopped or kept billing.
- **Every cancel path returns its pool slot, and the pool still serves the next caller.** `checkedout()` returns to 0 after an immediate cancel, after mid-stream cancellation, and after an aborted long query, and a fresh query on the same engine succeeds — the observable evidence that poolhouse invalidated and replaced the poisoned connection.
- **`aexecute` stays transparent.** A cancelled call raises rather than handing back a cursor, and what surfaces is the framework's cancellation class, not DuckDB's `INTERRUPT Error` — poolhouse swallows the driver error and re-raises the cancellation, and Semolina's `except BaseException` arm passes it through untouched.
- **A teardown error cannot mask a cancellation.** With the cancel scope wrapping the whole `async with`, `aclose()` runs while the cancellation propagates and a live Arrow reader still holds its lock — the one place a `ConnectionBusyError` would be born — and the exception that escapes is still the cancellation.
- **The two-backend matrix is now a build gate.** An `ast` walk finds every module defining an `async def test_*`, requires the anyio marker and a both-backends fixture on each, names the offender on failure, and refuses to pass on an empty walk. Proven fail-first against a deliberately non-conforming module.
- **Semolina wrote zero lines of cancellation logic.** `git diff --stat -- src/semolina` is empty across the whole plan.

## Task Commits

1. **Task 2: Enforce the asyncio/Trio matrix structurally (ASYNC-05)** — `638a800` (test)
2. **Task 1: Prove cancellation reaches the driver and the pool recovers (ASYNC-06)** — `a596859` (test)

Supporting, made by the orchestrator between the two tasks:

- **adbc-poolhouse floor raised to >=1.6.2** — `00b0b31` (chore)

_Tasks were executed out of order: Task 1 halted at a blocking checkpoint on the first attempt, so Task 2 landed first._

## Files Created/Modified

- `tests/unit/test_async_cancel.py` — the ASYNC-06 proof: three deterministic cancellation tests, a session-scoped fixture that provisions and *measures* an expensive DuckDB aggregate, and two long-query tests that split the reached-the-driver claim from the transparency claim
- `tests/unit/test_asyncio_trio_matrix.py` — the ASYNC-05 loop-matrix invariant, an AST walk over the whole test tree

## Decisions Made

**The abort claim is asserted on elapsed time, against the plan's explicit criterion.** The plan required that "the long-query tests assert on cancellation state and on pool recovery, and use the measured duration only to set the deadline and the skip condition". Measurement showed those assertions are satisfied by a query that ran to completion, so they cannot carry the claim. The plan's kept prohibition — never ship a cancellation test that greens while the query is still running — outranks the criterion's phrasing, and only an elapsed comparison can distinguish the two worlds. The margin is fivefold, not a race.

**The reached-the-driver test runs plain SQL through `AsyncEngine.connect()`, not `aexecute`.** DuckDB's `semantic_views` community extension does not observe the interrupt flag inside its table function (measured below), and `aexecute` on DuckDB always generates a `semantic_view()` call. The test still runs through Semolina's async surface — the engine's own pool, its `connect()`, poolhouse's offload — with only the SQL text differing.

**The `aexecute` long-query test keeps its name and drops the claim it cannot support.** It asserts transparency, no-cursor-returned, and pool recovery, and its docstring states outright that it makes no early-abort claim. Naming the absent assertion is what keeps it from being the prohibited shape.

**The long-query family is guarded by a `faulthandler` watchdog rather than an anyio timeout.** The upstream deadlock this plan waited on hung inside a native call with the loop thread wedged; an `anyio.fail_after` around the same block would hang with it. `faulthandler` times out on its own thread, so it still fires. Tripping it costs the rest of the session — chosen over wedging CI forever.

**Discovery in the matrix checker is by content, never by filename.** `test_async_packaging.py` and the checker itself read as async-adjacent by name while defining no async test. A name glob would flag them wrongly or need an exclusion list that rots.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The long-query test as originally specified certified a query that ran to completion**

- **Found during:** Task 1
- **Issue:** Written exactly as the plan specified — assert `cancelled_caught`, assert no cursor returned, assert the pool recovers — the long-query test passed on the first run and looked correct. Instrumenting it showed the cancelled `aexecute` call returned after **3.13s** against a 3.20s uncancelled baseline. The deadline had expired at 0.32s; the query ran the full duration anyway. The test was green while the work it claimed to have cancelled had gone to completion, which is precisely the shape the plan's kept prohibition forbids.
- **Root cause, established by four probes:** `adbc_cancel` fired against an in-flight plain-SQL aggregate aborts DuckDB at **0.324s** with `INTERRUPT Error: Interrupted!`. The identical aggregate wrapped in the `semantic_views` extension's `semantic_view()` table function runs the full **3.42s** and only then reports `INTERRUPT Error`. Pushing the expense down into an underlying SQL `VIEW` does not help either (3.58s), so the extension's inner query does not observe the outer interrupt flag. The driver's `adbc_cancel` is present and does register — the outcome changes from rows to `INTERRUPT` — but the table function does not poll for it. This is a limitation of the DuckDB community extension, not of Semolina or adbc-poolhouse, and the warehouses Semolina targets cancel server-side.
- **Fix:** Split the long-query family in two. `TestCancellationReachesTheDriver` runs the interruptible plain-SQL twin of the same aggregate through `AsyncEngine.connect()` and asserts the cancelled call returns within `ABORT_EVIDENCE_RATIO` (0.5) of the measured uncancelled duration — with the deadline at one tenth, a fivefold margin. `TestCancellationThroughAexecute` keeps the `aexecute` path for the transparency and pool-recovery claims and documents that it makes no early-abort claim. The measurement fixture now times both queries.
- **Files modified:** `tests/unit/test_async_cancel.py`
- **Verification:** The new assertion was proven non-vacuous by temporarily applying it to the `semantic_view()` path, where it fails with `PROBE: cancelled semantic_view query took 3.33s against an uncancelled 3.43s` on both backends. On the interruptible path it passes at ~0.32s against 3.11s. The probe edit was reverted; `git diff --stat tests/unit/test_async_cancel.py` was empty afterwards.
- **Committed in:** `a596859`

---

**Total deviations:** 1 auto-fixed (1 bug — a test that certified a property it did not observe)
**Impact on plan:** No scope creep and no library change. The deviation strengthens the plan's own kept prohibition rather than working around it; the acceptance criterion it contradicts was written on an assumption (RESEARCH Assumption A3) that measurement disproved.

## Issues Encountered

**The upstream deadlock that blocked this plan on its first attempt is fixed and confirmed.** Against adbc-poolhouse 1.6.1, `cancellable_offload`'s watcher fired `adbc_cancel()` and then immediately awaited `on_abort()` — closing the connection without waiting for the aborted worker thread to unwind — which deadlocked the DuckDB driver indefinitely. Fixed upstream in 1.6.2 (anentropic/adbc-poolhouse#43), floor raised in `00b0b31`. Every long-query test now completes, and the `faulthandler` watchdog is in place so a regression fails the suite in seconds instead of hanging CI.

**The `semantic_views` extension's non-interruptible table function is worth reporting upstream.** It is not a Semolina defect and it does not affect Snowflake or Databricks, but it means a local DuckDB deployment cannot honour a client deadline promptly for a semantic-view query. Filing it against the community extension is a reasonable follow-up.

**Measured numbers, recorded as the plan asked.** Cost rung: 4,000,000 rows, digest depth 32. Uncancelled `semantic_view()` aggregate: 3.07s. Uncancelled plain-SQL twin: 3.11s. Deadline used: one tenth of the measurement, ~0.31s. Cancelled call under that deadline: 0.317s (asyncio) and 0.315s (Trio). The cost ladder escalates to 8M/64 and 16M/128 for faster hardware, and skips with the measured number if the top rung cannot clear the 2.0s floor.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- ASYNC-05 and ASYNC-06 are both closed with executed gates rather than claims. The loop matrix is enforced structurally, so plan 07 and any later async work inherits it automatically — a new async test module that omits the backend fixture now fails the build with a message naming the file.
- Full suite green: 1029 passed, 16 skipped; `prek run --all-files` clean.
- The session cost of the expensive fixture is ~7s per xdist worker (build plus two measurements), paid once. Worth watching if the unit suite's runtime becomes a concern.
- One open item for a human: whether to file the `semantic_views` interrupt behaviour upstream (coverage item D7).

## Self-Check: PASSED

- `tests/unit/test_async_cancel.py` — present
- `tests/unit/test_asyncio_trio_matrix.py` — present
- `tests/unit/test_async_ffprobe.py` — absent, as the Task 2 fail-first probe requires
- Commits `638a800`, `00b0b31`, `a596859` — all present in history

---
*Phase: 46-async-query-surface*
*Completed: 2026-08-03*
