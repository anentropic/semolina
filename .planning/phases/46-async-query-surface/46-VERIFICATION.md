---
phase: 46-async-query-surface
verified: 2026-08-03T00:00:00Z
status: gaps_found
score: 4/6 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "Cancelling an in-flight async query against Semolina's own generated SQL (a semantic_view query) causes the underlying warehouse query to stop running, not merely the client to stop waiting (ASYNC-06 / Success Criterion 3)"
    status: failed
    reason: >
      The phase's own test suite measures the opposite for the only backend it can measure
      live. tests/unit/test_async_cancel.py::TestCancellationThroughAexecute::
      test_deadline_over_a_semantic_view_query_is_transparent_and_recovers deliberately
      contains no elapsed-time assertion, with a docstring stating why: "on this path the
      work does not stop early and pretending otherwise would be the exact false
      certification the sibling class exists to prevent." The sibling class
      (TestCancellationReachesTheDriver) proves the abort-lands-early claim only on hand-written
      plain SQL, bypassing Semolina's query builder entirely, and measures the DuckDB
      semantic_views extension running to full completion (3.4s) after a cancel fired at
      0.3s, versus 0.32s for the same aggregate in plain SQL. That is the literal
      "abandonment" scenario the requirement says to rule out, reproduced for the real
      `Sales.query()...aexecute()` code path on the one backend actually exercised live.
      Cassette replay cannot substitute evidence here (`ReplayCursor.adbc_cancel()` is a
      documented no-op), and no live Snowflake or Databricks test exists in this phase
      (Databricks' ADBC driver is not on PyPI; Snowflake would need live credentials), so
      there is zero executed evidence that `adbc_cancel` actually halts warehouse work on
      any backend when reached through Semolina's own generated SQL — only that poolhouse's
      mechanism fires and the client-side call stays transparent and returns its pool slot.
    artifacts:
      - path: "tests/unit/test_async_cancel.py"
        issue: "TestCancellationThroughAexecute proves transparency + pool recovery only; it explicitly disclaims the abort-lands-early claim for the real aexecute/semantic_view path"
      - path: "docs/src/how-to/web-api.rst"
        issue: "No cancellation/timeout/client-disconnect section exists, so this limitation is not disclosed to the users the phase goal names"
    missing:
      - "Either demonstrate (on a real interruptible DuckDB build, or by another technique) that a Semolina-generated query is actually interrupted mid-flight, or scope ASYNC-06's wording down to what is proven (the client stays transparent and the pool recovers) and say plainly that the warehouse-side abort is unverified/known-absent for DuckDB semantic views"
      - "A documented caveat for users querying DuckDB semantic views under a cancelling framework, since as shipped they will pay the query's full cost regardless of client-side cancellation"
  - truth: "Async cancellation, timeout, and client-disconnect behaviour — including the DuckDB semantic_view limitation just measured — is documented for the users the phase goal targets"
    status: failed
    reason: >
      docs/src/how-to/web-api.rst (the page this phase's own plan targets for exactly this
      scenario) has no cancellation, timeout, or client-disconnect section at all — confirmed
      by grep. WINDOWS.md ledger entry 1 records this omission and is still `open`; its
      recorded cause ("pending adbc-poolhouse 1.6.2") is stale, since 1.6.2 shipped mid-phase
      (commit 00b0b31) and Plan 05 went on to measure the cancellation behaviour those
      sections would describe. deferred-items.md's own Phase 46-07 entry says as much: "The
      blocker is gone; the sections are simply still unwritten. ... It needs a follow-up doc
      plan before `/gsd-ship`." WINDOWS.md's own header states `/gsd-ship` blocks while
      `open_count > 0`, so this phase currently cannot proceed through the project's own ship
      gate.
    artifacts:
      - path: "docs/src/how-to/web-api.rst"
        issue: "Zero mentions of cancel/timeout/abandon; grep confirms no matching section"
      - path: ".planning/WINDOWS.md"
        issue: "Entry 1 open, with a stale blocking-cause rationale"
    missing:
      - "The four async cancellation/timeout/client-disconnect doc sections named in 46-06-SUMMARY.md's 'Deliberately omitted' note, updated to include the DuckDB non-early-abort caveat this verification surfaced"
      - "Closing WINDOWS.md entry 1 once the docs land"
human_verification: []
---

# Phase 46: Async Query Surface Verification Report

**Phase Goal:** Users can run Semolina queries from an async web framework without blocking
the event loop, under either asyncio or Trio, with cancellation that actually reaches the
warehouse.
**Verified:** 2026-08-03
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can `await engine.aexecute(query)` and `await Sales.query()...aexecute()`, getting the same result surface as `.execute()`, loop stays free (ASYNC-01, ASYNC-02) | VERIFIED | `src/semolina/engines/abase.py:135` `aexecute()`; `src/semolina/query.py:422` `_Query.aexecute()` delegates to `get_async_engine()`; both exported from `src/semolina/__init__.py`. `tests/unit/test_async_engine.py`, `tests/unit/test_async_query.py` pass (111/111 across cursor+engine+query+registry). Loop-freedom proven by `5de7aaa` ("prove the loop stays free and two queries run concurrently") |
| 2 | `async for row in result` streams `Row` objects batch by batch, off-thread fetch, no whole-table materialization (ASYNC-03) | VERIFIED | `src/semolina/acursor.py:295-350` `__anext__` mirrors the sync batch-buffer state machine (D-07), awaits `reader.__anext__()`. `tests/unit/test_async_cursor.py` streaming tests (`test_stream_yields_rows_from_multiple_batches`, `test_stream_pulls_one_batch_at_a_time`, etc.) pass |
| 3 | Cancelling an in-flight async query causes the warehouse query to be cancelled via `adbc_cancel`, not merely abandoned (ASYNC-06) | **FAILED** | See gap #1. The phase's own measurement shows the opposite for the real `aexecute`/`semantic_view()` path on the only backend tested live: the query runs to full completion (3.4s) regardless of client-side cancellation. Only hand-written plain SQL (not what Semolina generates) is proven to abort early |
| 4 | `semolina[async]` extra pins `adbc-poolhouse[async]>=1.6.2`; plain install gains no new dependency; automated TID251 check enforces zero `asyncio`/`anyio` in `src/semolina/`; tests green under asyncio and Trio (ASYNC-04, ASYNC-05) | VERIFIED | `pyproject.toml:64` async extra pin; `pyproject.toml:11` base pin matches; `pyproject.toml:129,143-150` TID251 wired and scoped; `ruff check src/semolina/` passes clean; `grep -rn "asyncio\|anyio\|import_module"` over `src/semolina/` finds only comments/docstrings, no live imports; `tests/unit/test_async_packaging.py` (5/5) and `tests/unit/test_asyncio_trio_matrix.py` (3/3) pass. Reworded roadmap SC4 (TID251 + disclosed dynamic-import gap) is a faithful, more precise restatement of ASYNC-05's intent, not a lowered bar |
| 5 | `.planning/config.json` carries `git.branching_strategy = "milestone"` (TOOL-01) | VERIFIED | `.planning/config.json:13` reads `"branching_strategy": "milestone"`, landed in commit `9035a0d` as the phase's declared final commit (D-18) |
| 6 | Async cancellation/timeout/client-disconnect behaviour is documented for users (implicit in the user-facing goal, and explicit as WINDOWS.md ledger entry 1) | **FAILED** | See gap #2. `docs/src/how-to/web-api.rst` has no such section; WINDOWS.md entry 1 is open with a stale rationale |

**Score:** 4/6 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/semolina/engines/abase.py` | `AsyncEngine` — sibling engine, `connect()`/`aexecute()`/`dispose()` | ✓ VERIFIED | Concrete class, one pool, `BaseException` checkout guard at :180-191, deterministically tested (`test_cancel_during_execute_returns_the_slot`, `test_failed_execute_returns_the_slot`) |
| `src/semolina/acursor.py` | `AsyncSemolinaCursor` — sibling cursor, batch streaming, teardown ordering | ✓ VERIFIED | CR-01 (reader-leak) and WR-02 (OSError-on-drained-stream) from code review are fixed in current code (`fetch_record_batch()` now records `self._reader`; `__anext__` catches `OSError`); tests added and pass |
| `src/semolina/registry.py` | Separate `_async_engines` store, `register_async_engine`/`get_async_engine`/`unregister_async_engine`, async-aware `reset()` | ✓ VERIFIED | Two independent dicts, no cross-fallback; `reset()` works but is not exception-atomic despite its docstring (WR-04, unfixed — test-only impact) |
| `src/semolina/config.py` | `create_async_engine()` — config/dbapi_module path, DuckDB listener wiring | ✓ VERIFIED | Builds via `create_async_pool(wh_config)`, not `driver_path=`; deferred `anyio`-pulling import; DuckDB `semantic_views` listener attached via the (undocumented, private) `pool._pool` (WR-05, unfixed) |
| `src/semolina/query.py` | `_Query.aexecute()` — async twin of `.execute()` | ✓ VERIFIED | `query.py:422`, validates then resolves via `get_async_engine()` |
| `pyproject.toml` | `[async]` extra, TID251 gate, dev-group Trio | ✓ VERIFIED | All three present and correctly scoped (barring IN-01's documentation-vs-config mismatch on ban scope, informational only) |
| `docs/src/how-to/web-api.rst` (+ streaming/connection-pools/installation) | Async endpoints, streaming, lifecycle, packaging documented | ⚠️ PARTIAL | Everything except cancellation/timeout/client-disconnect is documented; that specific, now-measured behaviour is documented nowhere (see gap #2) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `query.py::_Query.aexecute` | `registry.py::get_async_engine` | direct call | ✓ WIRED | |
| `engines/abase.py::AsyncEngine.aexecute` | `acursor.py::AsyncSemolinaCursor` | constructs and returns | ✓ WIRED | |
| `__init__.py` | `config.py`, `registry.py`, `acursor.py` | public re-export | ✓ WIRED | `create_async_engine`, `register_async_engine`, `get_async_engine`, `unregister_async_engine`, `AsyncSemolinaCursor` all exported |
| `pyproject.toml` TID251 | `src/semolina/**` | ruff lint gate | ✓ WIRED | Verified by direct `ruff check` run; catches `import asyncio`, `from anyio import to_thread`, etc. per 46-REVIEW.md's probe and this verification's own confirmation that no live import exists |
| poolhouse `cancellable_offload`/`adbc_cancel` | actual warehouse query cancellation | mechanism only | ⚠️ NOT PROVEN for real Semolina SQL | The mechanism is real and structurally verified by source-reading (D-13/canonical refs) and by a plain-SQL DuckDB measurement, but the link from "Semolina generates SQL and a user cancels" to "the warehouse stops working" is disproven for the one path measured (see gap #1) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full unit + integration suite green | `uv run pytest -q` | 1043 passed, 16 skipped | ✓ PASS |
| Async unit modules green in isolation | `uv run pytest tests/unit/test_async_*.py tests/unit/test_registry.py -q` | all pass (111 + 8 + 8 across runs) | ✓ PASS |
| Cassette-replay async integration | `uv run pytest tests/integration/test_async_queries.py -q` | 8 passed | ✓ PASS |
| Posture A ruff gate | `uv run ruff check src/semolina/` | All checks passed | ✓ PASS |
| No live `asyncio`/`anyio`/`import_module` in library code | `grep -rn "asyncio\|anyio\|import_module" src/semolina/` | only comments/docstrings | ✓ PASS |
| `import semolina` does not pull `anyio` | `tests/unit/test_async_packaging.py::test_packaging_importing_semolina_does_not_import_anyio` | passes | ✓ PASS |
| Full quality gates | `prek run --all-files`, `just docs-build` | clean / build succeeded | ✓ PASS |
| Cancellation actually halts a Semolina-generated (semantic_view) query | inspected `test_deadline_over_a_semantic_view_query_is_transparent_and_recovers` | test explicitly asserts no such thing, by design | ✗ FAIL (see gap #1) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ASYNC-01 | 46-02, 46-03, 46-06 | `await engine.aexecute(query)` without blocking the loop | ✓ SATISFIED | Truth 1 |
| ASYNC-02 | 46-04, 46-06 | `await Sales.query()...aexecute()` | ✓ SATISFIED | Truth 1 |
| ASYNC-03 | 46-02, 46-03, 46-06 | `async for row in result`, batch streaming | ✓ SATISFIED | Truth 2 |
| ASYNC-04 | 46-01, 46-06 | `semolina[async]` extra, `adbc-poolhouse[async]>=1.6.2`, no new base dep | ✓ SATISFIED | Truth 4 |
| ASYNC-05 | 46-01, 46-05 | Zero `asyncio.*`/anyio in library code, verified by automated check | ✓ SATISFIED | Truth 4 |
| ASYNC-06 | 46-05 | Cancellation reaches the warehouse via `adbc_cancel`, not merely abandoned | ✗ BLOCKED | Truth 3 / gap #1 |
| TOOL-01 | 46-07 | `git.branching_strategy` restored to `"milestone"` | ✓ SATISFIED | Truth 5 |

No orphaned requirements: all seven IDs from REQUIREMENTS.md's Phase 46 section are claimed by at least one plan's `requirements:` frontmatter.

### Anti-Patterns Found (from 46-REVIEW.md, cross-checked against current code)

| File | Issue | Severity | Status | Impact |
|------|-------|----------|--------|--------|
| `acursor.py:249-251` | `fetch_record_batch()` leaked the pooled connection (CR-01) | was Critical | **FIXED** (`caa0884`) — verified in current code, reader now recorded | none remaining |
| `acursor.py:295-324` | `__anext__` raised uncaught `OSError` on a post-drain re-fetch (WR-02) | was Warning | **FIXED** (`1dbec69`) — verified, `OSError` now caught and normalised | none remaining |
| `engines/abase.py:180-191` | `aexecute`'s `BaseException` check-in arm untested; the one test claiming to cover it was vacuous (WR-03) | was Warning | **FIXED** (`d75bf1b`, `a00ee23`) — `test_failed_execute_returns_the_slot` and `test_cancel_during_execute_returns_the_slot` now drive the handler deterministically | none remaining |
| `acursor.py:380-383` | `aclose()` suppresses `Exception` on connection close with no observability if check-in itself fails (WR-01) | Warning | **UNFIXED** | Silent permanent pool-slot leak on a genuine teardown failure, with no log/warning; compounds the reliability concern already raised by gap #1's cancellation caveats |
| `registry.py:214-251` | `reset()` docstring claims exception-atomicity the code (narrow `except (OSError, RuntimeError)`, no `finally`) does not provide (WR-04) | Warning | **UNFIXED** | Test-isolation risk only (`reset()` is test-only); a non-OSError/RuntimeError teardown failure can cascade "already registered" errors across the rest of a test session |
| `config.py:324`, `registry.py:250` | Library code reaches into adbc-poolhouse's private `_pool` attribute, pinned with no upper bound (WR-05) | Warning | **UNFIXED** | A future poolhouse minor release renaming/removing `_pool` breaks DuckDB async engine construction and wedges `reset()` at runtime with no guard |
| `pyproject.toml`, `justfile` | Async tests hard-fail (not skip) without the `[async]` extra; `just test` runs plain `uv run pytest` (WR-06) | Warning | **UNFIXED** | Not observed in this repo's current venv (anyio is installed here), but the documented `just test` gate would go red rather than "green with skips" on a freshly-synced plain install |
| `test_async_cancel.py` | Session-scoped `heavy_database` fixture + `faulthandler.dump_traceback_later(exit=True)` can hard-kill the pytest process under xdist contention (WR-07) | Warning | **UNFIXED** (judgement call, not confirmed to trip) | CI-flakiness risk, not a functional defect |
| `pyproject.toml:147-150` | TID251 ban is repo-wide except `tests/**`, not scoped to `src/semolina/` as documented (IN-01) | Info | **UNFIXED** | Contributor-facing config/comment mismatch only |
| `test_async_cursor.py` | Dead fixture data, duplicated/weak assertions (IN-02) | Info | **UNFIXED** | Test-quality only |
| `acursor.py:80` | `self._pool` stored, never read (IN-03) | Info | **UNFIXED** | Dead state, no functional effect |
| `config.py:293-304` | `create_async_engine`'s `except ImportError` can mislabel an unrelated import failure (IN-04) | Info | **UNFIXED** | Misleading error message only |
| `engines/abase.py:158` | Documented `ValueError` for an invalid query is actually an `AssertionError` (IN-05) | Info | **UNFIXED**, pre-existing (also true of sync `Engine.execute`) | Docstring accuracy only |

### Deviations Assessed

1. **ROADMAP SC4 reworded (TID251 + disclosed dynamic-import gap).** Judged faithful, not a lowered bar: it trades a vaguer "no `asyncio.` reference" grep-style claim for a precise description of what the shipped mechanism (ruff TID251) actually enforces, and names the one honest gap (`importlib.import_module("asyncio")`) rather than hiding it. Verified directly: `ruff check src/semolina/` passes, and 46-REVIEW.md independently probed the rule catches `import asyncio`, `from anyio import to_thread`, etc.

2. **ASYNC-06 split across two test classes, one using elapsed-time.** This is the deviation that matters most, and it does not hold up as delivering the requirement as worded. See gap #1 above — the split was the right way to discover and honestly report the limitation, but the underlying claim ("not merely abandoned") is false for the real code path on the one backend measured, and unverified on the others.

3. **poolhouse floor 1.6.1 → 1.6.2 mid-phase.** Legitimate, well-evidenced amendment (a real deadlock bug, fixed upstream, REQUIREMENTS.md and ROADMAP.md both updated to match, `pyproject.toml` confirms `>=1.6.2` everywhere it should). No concern.

4. **13 code review findings, 3 fixed / 10 not.** CR-01, WR-02, WR-03 (the three most severe) are fixed and verified in current code with new passing tests. The seven unfixed warnings and five info items are real but none independently rises to a phase-blocking severity on its own; WR-01 and WR-05 are the two worth a maintainer's attention soonest, since both touch the same "silent failure under cancellation/teardown" theme as gap #1.

### Gaps Summary

Two related gaps block this phase, both centered on ASYNC-06 and the phase's core promise that
cancellation "actually reaches the warehouse":

1. **The mechanism is real; the outcome it's supposed to guarantee is not proven, and where it
   was measured, it was disproven.** For the real `Sales.query()...aexecute()` path against a
   DuckDB semantic view — the primary backend this phase tests live — cancelling an in-flight
   query does not stop the warehouse from doing the work; it only stops the client from
   waiting. The phase's own test suite says so, deliberately and honestly, but the roadmap
   success criterion and REQUIREMENTS.md ASYNC-06 both still assert the stronger claim without
   qualification.

2. **The gap in (1) is not documented for users.** The how-to page this phase's own plan
   targeted for exactly this audience (`web-api.rst`) has no cancellation/timeout/client-
   disconnect section at all. WINDOWS.md's open ledger entry for this was recorded against a
   blocker (adbc-poolhouse 1.6.2) that has since shipped; the docs were never written once it
   did, and the project's own ship gate is configured to block while that ledger entry stays
   open.

Everything else — the async engine/cursor/registry/query surface, the streaming iterator, the
packaging contract, the Posture A lint gate, and TOOL-01 — is real, wired, tested, and passing
under both asyncio and Trio. The phase delivers a working, non-blocking async query surface.
What it does not yet deliver is the cancellation guarantee as worded, or an honest accounting of
that gap to the people who will hit it.

---

_Verified: 2026-08-03_
_Verifier: Claude (gsd-verifier)_

---

## Post-verification correction — 2026-08-11

Both gaps recorded above are now closed. The frontmatter is left as the 2026-08-03 verifier
wrote it; this section is the correction, and one of the `missing` bullets above is now a
trap rather than an instruction.

**Gap #1 is closed.** The root cause was upstream in `anentropic/duckdb-semantic-views`:
`semantic_view()` evaluated its inner query on a fresh `ClientContext`, and DuckDB's
interrupt flag is per-`ClientContext`, so the flag `adbc_cancel` set on the caller's context
was never read. Fixed in **0.12.0**, published to the community CDN for DuckDB core
**1.5.5**. Commit **`3e653d5`** moved the `pyproject.toml` pin `1.5.3` → `1.5.5` and added
the elapsed-time assertion to
`TestCancellationThroughAexecute::test_deadline_over_a_semantic_view_query_is_transparent_and_recovers`,
so ASYNC-06's central claim is now asserted on Semolina's own generated `semantic_view()`
SQL rather than only on a hand-written plain-SQL twin. The assertion is non-vacuous: across
the two builds, at a deadline of one tenth of the baseline, 0.10.3 returned at 3.22s of a
3.97s baseline where 0.12.0 returns at 0.55s of 3.21s — 0.81 of baseline against 0.17, so
the old build fails the assertion the new one passes. Re-measured during plan 46-08 on the
pinned build: 12/12 tests in `tests/unit/test_async_cancel.py` pass under both asyncio and
Trio, with the uncancelled aggregate measured at `semantic_view()` 3.05s and plain SQL 3.26s
(4,000,000 rows, digest depth 32), well clear of the 2.0s floor, so nothing skipped.

**Gap #2 is closed** by plan 46-08, which wrote the three sections the phase owed:
`Time out a slow query` (`howto-web-api-timeouts`) and `Handle a client disconnect`
(`howto-web-api-client-disconnect`) in `docs/src/how-to/web-api.rst`, and
`Cancel an async stream mid-iteration` (`howto-streaming-async-cancel`) in
`docs/src/how-to/streaming.rst`. The scope was wider than gap #2 described: the omission
spanned two files, not `web-api.rst` alone.

**Gap #2's second `missing` bullet is superseded and must not be acted on.** It asks for
"a documented caveat for users querying DuckDB semantic views under a cancelling framework,
since as shipped they will pay the query's full cost regardless of client-side
cancellation." That described the `semantic_views` extension below 0.12.0. It is false at
the pinned floor, and writing it would ship a statement that costs a reader money: they
would either keep paying for queries they had cancelled or decline to build a timeout they
believed was cosmetic. The `Time out a slow query` section states the version dependency
positively instead — aborting a `semantic_view()` query needs the extension at 0.12.0 or
newer, which is what `duckdb==1.5.5` installs — and describes the old behaviour in the past
tense, about builds below the floor.

`.planning/WINDOWS.md` entry 1 was marked `fixed` after the three sections landed and all
three gates ran green, via `gsd-tools windows fixed 1` rather than a hand edit.

_Corrected: 2026-08-11 (plan 46-08)_
