---
phase: 46
plan: "04"
subsystem: async-registry-and-query-entry-point
tags: [async, registry, query-builder, exports, anyio, trio, posture-a]
status: complete
requires:
  - "46-01: adbc-poolhouse>=1.6.1, the semolina[async] extra, trio in dev, the TID251 gate"
  - "46-02: AsyncEngine, AsyncSemolinaCursor, create_async_engine, the async_duckdb_engine fixture"
provides:
  - "semolina.registry.register_async_engine / get_async_engine / unregister_async_engine — a second, separate store"
  - "semolina.registry.reset() — still synchronous, now tears async pools down inline"
  - "semolina.query._Query.aexecute — the async twin of execute against the async registry"
  - "five public exports from the package root: AsyncSemolinaCursor, create_async_engine, get_async_engine, register_async_engine, unregister_async_engine"
  - "tests/unit/test_async_query.py — ASYNC-02 coverage across asyncio and Trio"
  - "tests/unit/test_registry.py — async registry separation, miss-message, and reset coverage"
affects:
  - src/semolina/registry.py
  - src/semolina/query.py
  - src/semolina/__init__.py
  - tests/unit/test_registry.py
  - tests/unit/test_async_query.py
tech-stack:
  added: []
  patterns:
    - "Two separate registry dicts rather than one dict holding a union, so a wrong-kind resolution is impossible by construction rather than caught at runtime"
    - "Synchronous teardown of an async resource by reaching the inner sync pool — the same call the async path offloads, run where there is no loop"
    - "Deferred in-method registry import in the query builder, copied from the sync twin, to dodge the circular import"
    - "Non-vacuity probes: mutate the implementation to the wrong behaviour and confirm the assertion actually fails"
key-files:
  created:
    - tests/unit/test_async_query.py
  modified:
    - src/semolina/registry.py
    - src/semolina/query.py
    - src/semolina/__init__.py
    - tests/unit/test_registry.py
decisions:
  - "Registry verbs named register_async_engine / get_async_engine / unregister_async_engine — adjective before noun, matching create_async_engine; a trailing _async verb suffix would read as 'this is a coroutine', the exact mode confusion D-05 and D-06 exist to remove"
  - "The async miss message is its own text ('No async engine registered...') and its empty-registry hint names register_async_engine + create_async_engine, so a reader is never sent to the store that cannot serve aexecute"
  - "reset() clears both dicts unconditionally and closes the async side via close_pool on the inner sync pool, never AsyncPool.close()"
  - "The _sales_query() triplication flagged by 46-02's handoff was deferred rather than fixed — logged in deferred-items.md"
metrics:
  duration: "~50min"
  completed: 2026-08-02
  tasks: 2
  commits: 2
actuals:
  tokens: 8010
  tasks: 2
  commits: 2
---

# Phase 46 Plan 04: Async Registry & Query Entry Point Summary

`await Sales.query().metrics(...).dimensions(...).aexecute()` now works end to end under both
asyncio and Trio, resolving through a second registry that a synchronous engine can never leak
into, and the whole async surface is reachable from a plain `import semolina`.

## What Was Built

**Task 1 — the separate async registry and the reset that cannot await** (commit `022b15a`)

`src/semolina/registry.py` gained `_async_engines`, a second module-level dict reusing the
existing `_default_name`, plus `register_async_engine`, `get_async_engine`, and
`unregister_async_engine`. All three are plain `def`s. `get_async_engine` copies the sync
`get_engine` two-tier error shape — sorted, quoted available names when the store is non-empty;
a how-to-fix hint when it is empty — but its own text throughout, because a reader who lands on
"use `semolina.register(...)`" from a failed `aexecute` has been pointed at the store that
cannot serve them.

The lookup reads `_async_engines` only. There is no fallback arm to the sync store, and that
absence is the whole point of D-05: a union-in-one-dict design would let
`.using("reports").aexecute()` resolve a synchronous engine and then die on a missing attribute
somewhere inside execution, which reports the symptom rather than the registration mistake.

`reset()` stays a plain `def` — it is autouse-invoked from a synchronous fixture after every
test, where there is no running loop — and now has a second arm that closes each async engine
inline with `close_pool(engine._pool._pool)`. That is literally the call `AsyncPool.close()`
offloads to a worker thread, run directly where there is nothing to offload to. Calling the
async pool's own `close()` there would build an un-awaited coroutine and close nothing, leaking
a pool per test: the exact hazard RESEARCH Finding 3 flagged and 46-02's handoff repeated. The
`close_pool` import is deferred into the function body and guarded by `if _async_engines:`, so
the module still imports on a plain non-async install. Both dicts are cleared unconditionally,
so one bad engine cannot wedge later tests.

**Task 2 — `_Query.aexecute` and the public exports** (commit `c019b90`)

`_Query.aexecute` is a five-line transliteration of `execute()`: deferred
`from .registry import get_async_engine` inside the method body (the same circular-import dodge
the sync twin uses), `self._validate_for_execution()`, resolve, `return await
engine.aexecute(self)`. Validation runs before resolution and before any checkout, so an invalid
query never consumes a pool slot.

`src/semolina/__init__.py` eagerly exports the five async names. Eager is safe here only because
`acursor.py` and `abase.py` carry no module-level poolhouse async import and
`create_async_engine` defers its own — this task is precisely where that protection could have
been lost, so both the subprocess no-anyio probe and Plan 01's packaging test were re-run
against the new exports.

## Non-vacuity: two assertions probed against deliberately wrong implementations

Both of this plan's load-bearing claims are the kind a test can appear to cover while proving
nothing, so both were probed by mutating the implementation and confirming the assertion fails.

**"`reset()` actually tears the async pool down."** A test that only checks the dict is empty
would pass against a `reset()` that leaks every pool. With the async teardown call replaced by
`pass`:

```
FAILED test_reset_closes_inner_sync_pool_not_the_async_pool
FAILED test_reset_actually_tears_down_a_real_async_pool
E  +  where 1 = checkedin()
```

The real-pool test primes the inner pool with one checked-in connection and asserts it reaches
0, so it discriminates a real teardown from a cleared dict.

**"Validation happens before any checkout."** A test that only asserts `ValueError` would pass
against an implementation that checks a connection out first and returns it on the error path.
With `aexecute` reordered to resolve and check out before validating:

```
FAILED test_aexecute_invalid_query_raises_before_any_checkout[asyncio]
FAILED test_aexecute_invalid_query_raises_before_any_checkout[trio]
```

The assertion is `checkedin() == 0 and checkedout() == 0` — a pool that had served and reclaimed
a connection reports `checkedin() == 1`, so the counters distinguish "never touched" from
"borrowed and returned". Both mutations were reverted and the suite re-confirmed green.

## The wrong-kind lookup, closed at two levels

T-46-10 is discharged by construction plus two tests, one per level:

- `test_get_async_engine_never_falls_back_to_sync_store` — a name present only in `_engines`
  makes `get_async_engine` raise. It would fail against any fallback arm.
- `test_async_lookup_ignores_a_sync_only_registration` — the same claim from the call site, with
  a real registered sync engine and `aexecute` on the other end.
- `test_same_name_serves_both_paths` — the positive half. `"default"` holds both kinds at once;
  `execute()` returns a `SemolinaCursor` and `aexecute()` an `AsyncSemolinaCursor`, both with the
  right rows. This is the cost of the split and it is a feature: the same warehouse is often
  wanted from a synchronous script and an async request handler.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/unit/test_registry.py -q` | 30 passed (was 13) |
| `uv run pytest tests/unit/test_async_query.py -q` | 20 passed — 10 tests × asyncio/trio |
| `uv run pytest tests/unit -k async -q` | 90 passed |
| `uv run pytest tests/unit -k packaging -q` | 5 passed — the lazy-import contract survived |
| `uv run pytest -q` (full root suite) | 1016 passed, 16 skipped (was 979/16) |
| `uv run ruff check src/semolina` (TID251 gate) | All checks passed |
| `uv run basedpyright` (whole project, strict) | 0 errors, 0 warnings, 0 notes |
| `prek run --all-files` | all hooks Passed |
| `just docs-build` (Sphinx `-W`) | build succeeded |
| Registry surface probe (all four functions plain `def`, two distinct dicts) | `registry surface ok` |
| Empty-registry hint probe | `hint ok` — names `register_async_engine` |
| `aexecute` is a coroutine function | `aexecute ok` |
| Five exports resolve and are in `__all__` | `exports ok` |
| Subprocess `import semolina` → `"anyio" in sys.modules` | `still lazy` (False) |
| Reset teardown probed against a skipped-teardown impl | both tests FAIL as required |
| Validation-ordering probed against a checkout-first impl | both backends FAIL as required |
| `# type: ignore` added | none; no new `[tool.basedpyright]` exemption either |

## Deviations from Plan

None that changed behaviour. Two mechanical notes:

1. **[Rule 3 - Blocking] Two ruff findings in the new test module, fixed inline before commit.**
   `TC001` wanted `_Query` (used only in the `_sales_query()` return annotation) inside a
   `TYPE_CHECKING` block, and `D403` rejected a docstring opening with the lowercase identifier
   `aexecute`. The docstring was reworded to read properly rather than accepting ruff's
   "Aexecute" autofix — the same call 46-02 made on the same rule. No behaviour change; caught
   by `uv run ruff check` before the commit, not by the hook.
2. **RED and GREEN share one commit per task**, following the standing Phase 45 caveat:
   basedpyright strict rejects a test referencing not-yet-existent attributes and `--no-verify`
   is not an option. RED was demonstrated by execution in both tasks — Task 1 failed collection
   with `ImportError: cannot import name 'get_async_engine'`, Task 2 ran 20 failed / 0 passed
   across both backends — before any implementation was written.

## Out of Scope

`_sales_query()` is now defined identically in three test modules, and 46-02's handoff asked for
promotion to `tests/conftest.py` on the third copy. Not done: promotion means converting a
module-local helper into a fixture and threading it through ~16 call sites across two already
green modules that this plan does not declare in `files_modified`. That is churn against passing
tests with no behaviour change. Logged in
`.planning/phases/46-async-query-surface/deferred-items.md` for a later plan in this phase that
already touches those files.

## Known Stubs

None. Every artifact this plan produced is complete and exercised by a test.

## Threat Flags

None. No new network endpoint, auth path, file access pattern, or schema crosses a trust
boundary. The plan's own `<threat_model>` rows are discharged as planned:

- **T-46-10** (wrong-kind resolution by name) — mitigated. Two separate stores, no fallback arm,
  and three tests covering both the negative and positive halves (above).
- **T-46-02** (leaked pools via the autouse reset) — mitigated. `reset()` closes the inner sync
  pool inline, never the async pool's own coroutine `close()`, and the teardown assertion is on
  the pool's own counters, probed non-vacuous.
- **T-46-06** (miss-message disclosure) — accepted, unchanged from the sync message. Engine names
  are user-chosen labels; no config field, path, or connection string is interpolated.
- **T-46-11** (eager exports pulling anyio into a base install) — mitigated. The subprocess
  no-anyio check and Plan 01's packaging test both re-run green after the exports landed.

## Estimate vs Actual

Estimated 45000 tokens at `confidence: low`; realized 8010 on the same chars/4 scale — under a
fifth. The estimate priced naming as risky (an interface-contract section was written to settle
it) and priced the reset hazard as discovery work. Neither turned out to cost tokens: the naming
was argued once in the plan and implemented verbatim, and RESEARCH Finding 3 had already
identified the exact teardown call, so the async arm of `reset()` is four lines under a comment.
Read the miss the way 46-02's was read — upstream research displaced implementation tokens — not
as an easy plan. The two probe cycles were the only unbudgeted work, and they are the reason the
two riskiest assertions are known to discriminate.

## For Later Plans in This Phase

- The public async surface is now complete and importable from the package root:
  `semolina.create_async_engine`, `semolina.register_async_engine`,
  `semolina.get_async_engine`, `semolina.unregister_async_engine`,
  `semolina.AsyncSemolinaCursor`. Documentation plans can write `import semolina` call sites
  rather than submodule paths.
- `registry.reset()` now clears both stores, so an async test that registers an engine needs no
  manual unregister — the autouse `clean_registry` fixture handles it.
- Registering the `async_duckdb_engine` fixture's engine and letting `reset()` close it means
  `close_pool` runs twice on the same inner pool (once from reset, once from the fixture's own
  teardown). That is harmless — verified across 20 tests — but worth knowing before anyone
  "fixes" the apparent double close.
- `.using(name)` is per-registry. A doc page describing named engines must say that a name in
  the sync registry is invisible to `aexecute`, or readers will register once and wonder why the
  async path cannot find it.

## Self-Check: PASSED

- `src/semolina/registry.py` (`_async_engines`, three functions, async reset arm) — FOUND
- `src/semolina/query.py` (`_Query.aexecute`) — FOUND
- `src/semolina/__init__.py` (five exports) — FOUND
- `tests/unit/test_registry.py` (async registry + reset coverage) — FOUND
- `tests/unit/test_async_query.py` — FOUND
- `.planning/phases/46-async-query-surface/deferred-items.md` — FOUND
- Commit `022b15a` — FOUND
- Commit `c019b90` — FOUND
- Throwaway probe mutations — correctly ABSENT (both reverted from backups)
