---
phase: 46
plan: "03"
subsystem: async-cassette-replay
tags: [async, testing, cassettes, replay, snowflake, databricks, trio, spike]
status: complete
requires:
  - "46-02: create_async_engine, AsyncEngine.aexecute, AsyncSemolinaCursor"
provides:
  - "tests/integration/conftest.py fixtures snowflake_async_engine and databricks_async_engine — replay-only"
  - "tests/integration/test_async_queries.py — four named-cassette replay tests across two dialects and two loop backends"
  - "Four copied named cassette trees under tests/integration/cassettes/async_*"
  - "Executed confirmation of RESEARCH Assumption A2 / D-15: replay intercepts the async path unmodified"
affects:
  - tests/integration/conftest.py
  - tests/integration/test_async_queries.py
  - tests/integration/cassettes/async_single_metric_snowflake
  - tests/integration/cassettes/async_single_metric_databricks
  - tests/integration/cassettes/async_streaming_iteration_snowflake
  - tests/integration/cassettes/async_streaming_iteration_databricks
tech-stack:
  added: []
  patterns:
    - "Positional adbc_cassette marker to pin a fixed cassette path, so one cassette serves both loop parametrizations"
    - "Replay-only fixtures: the replay half of a dual-mode fixture, with the recording branch deliberately absent"
    - "Cassette reuse by byte-for-byte copy rather than re-recording, gated by diff -r and a before/after tree digest"
    - "Non-vacuity probe: a deliberately wrong query must MISS before a match is trusted"
key-files:
  created:
    - tests/integration/test_async_queries.py
    - tests/integration/cassettes/async_single_metric_snowflake/
    - tests/integration/cassettes/async_single_metric_databricks/
    - tests/integration/cassettes/async_streaming_iteration_snowflake/
    - tests/integration/cassettes/async_streaming_iteration_databricks/
  modified:
    - tests/integration/conftest.py
decisions:
  - "D-16 spike passed on first run: the async path's SQL is byte-identical to the sync path's for both dialects, so the phase proceeds"
  - "Dialect is chosen by which engine fixture a test requests, not by a parametrized fixture — a named cassette is a fixed path, so the name must be a literal"
  - "_norm/_rows are copied into the async module rather than imported from test_queries.py, keeping the cross-test-module import surface at zero"
  - "Local Sales model duplicated per the plan, because the generated SQL must match the recording exactly"
metrics:
  duration: "~40m"
  completed: 2026-08-02
  tasks: 2
  commits: 2
actuals:
  tokens: 3942
  tasks: 2
  commits: 2
---

# Phase 46 Plan 03: Async Cassette Replay Spike Summary

Cassettes recorded through the sync path replay green through the async path for both
Snowflake and Databricks, under both asyncio and Trio, from one copied cassette each — and
the run wrote nothing.

## The spike's answer

D-15 said replay would intercept the async path unmodified; D-16 asked for that to be
executed rather than inferred. It is now executed. All eight replay tests passed on the
first run, with no adjustment to the plugin, the cassettes, the fixtures, or the
assertions.

Two claims came out of that single result:

- **The async path sends byte-identical SQL** (D-04's "no second SQL path"). The plugin
  matches on the SQL the driver received, so a match *is* that assertion — now
  machine-checked for both warehouse dialects rather than argued from a shared builder
  call.
- **Interception reaches inside poolhouse's offload worker thread.** The plugin patches
  `driver_mod.connect`, a process-global module attribute upstream of the entire async
  stack, and `_auto_patch_state["current_item"]` is guarded by a lock, so the patched
  connect fires correctly from the worker thread poolhouse offloads to.

## What Was Built

**Task 1 — replay-only fixtures and four copied cassettes** (commit `bb6f5c6`)

`tests/integration/conftest.py` gained `snowflake_async_engine` and
`databricks_async_engine`. Each is only the replay half of its sync sibling: no recording
branch, no native-connector DDL, no temp schema, no registry registration (the async
registry does not exist until Plan 04, and these tests call `engine.aexecute(query)`
directly). Each placeholder config repeats its sync sibling's replay-arm values field for
field — `account="replay"` … `schema="REPLAY"` for Snowflake, `host=
"replay.cloud.databricks.com"` … `schema="REPLAY"` for Databricks. That is load-bearing:
the cassettes were recorded against SQL generated under those values.

Teardown is the inline `close_pool(engine._pool._pool)` the Plan 02 fixtures established,
for the same reason — the fixture is synchronous and cannot await `dispose()`.

Both engines are built with `create_async_engine(config)`, from the config object. D-19's
trap is that `create_async_pool(driver_path=...)` would build the pool from a native shared
library, bypassing the Python dbapi module the plugin patches; such a test would miss
rather than match, and a miss looks like a real finding. The config path avoids it
structurally.

Four cassette directories were copied with `cp -R`, preserving the Databricks
`databricks/` differentiator segment that sits below the driver directory. Nothing was
edited, re-scrubbed, re-serialized, or regenerated, and no record mode was enabled at any
point.

**Task 2 — the four named-cassette replay tests** (commit `60050f9`)

`tests/integration/test_async_queries.py`. A module-local `Sales` whose view name and four
fields match `test_queries.py`'s exactly, the module-local loop matrix (`pytestmark =
pytest.mark.anyio` plus a parametrized `anyio_backend` fixture) Plan 02 established, local
copies of `_norm`/`_rows`, and four tests each carrying a **positional**
`@pytest.mark.adbc_cassette("<name>")`.

The positional form matters twice. It fixes the cassette path, so the `[asyncio]` and
`[trio]` variants share one cassette instead of deriving two node-id paths and each
demanding its own recording. And because the path is then a literal, the dialect cannot
come from a parametrized fixture — it comes from which engine fixture each test requests.

The two streaming tests build a `{country: revenue}` mapping from `async for row in cur:`
rather than asserting on value order or column names, for the reason the sync streaming
test's own comment gives: neither `Row.values()` order nor the backend-specific metric
column name (`AGG("REVENUE")` vs `MEASURE("revenue")`) is a Semolina contract.

## The match is not vacuous

Eight green tests against copied cassettes would look identical whether the SQL genuinely
matched or the plugin had silently passed through, so the discriminator was probed
directly. A throwaway test requested the same
`async_single_metric_snowflake` cassette with `Sales.cost` substituted for `Sales.revenue`:

```
CassetteMissError: Interaction 1 not found in cassette.
  Cassette path:  tests/integration/cassettes/async_single_metric_snowflake/adbc_driver_snowflake.dbapi
  Raw SQL:        'SELECT AGG("COST")\nFROM "SALES_VIEW"\nORDER BY AGG("COST") ASC'
  Normalised SQL: 'SELECT\n  AGG("COST")\nFROM "SALES_VIEW"\nORDER BY\n  AGG("COST") ASC NULLS LAST'
```

The miss is raised from `_cursor.py` on the async path, which confirms both that the SQL is
really being compared and that the comparison happens through the async stack. The
throwaway file was deleted.

## Nothing was recorded

The combined digest of the four copied cassette trees, taken before and after
`uv run pytest tests/integration -k async -q`:

```
before: d81ddfd054f68538a13e653eeec4d5028411d28e
after:  d81ddfd054f68538a13e653eeec4d5028411d28e
```

`git status --porcelain tests/integration/cassettes` is clean after the run, and each
copied tree is byte-identical to its source (`diff -r`, four pairs, no output). No new
credential material entered the repository: every file is a byte-for-byte copy of one
already committed and already scrubbed under the project's existing `adbc_scrub_keys`.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/integration -k async -q` | 8 passed, 15 deselected |
| `uv run pytest tests/integration/test_async_queries.py -q -k "asyncio and snowflake"` | 2 passed |
| `uv run pytest tests/integration/test_async_queries.py -q -k "trio and databricks"` | 2 passed |
| `uv run pytest tests/integration -q` (sync suite unregressed) | 23 passed |
| `uv run pytest -q` (full root suite) | 979 passed, 16 skipped (971 → 979) |
| `grep -c 'adbc_cassette("async_' tests/integration/test_async_queries.py` | 4 |
| `diff -r` source vs copy, all four pairs | no output, exit 0 |
| Cassette tree digest before vs after the run | identical |
| `git status --porcelain tests/integration/cassettes` | clean |
| `uv run ruff check tests/integration` | All checks passed |
| `uv run basedpyright` on both changed test files | 0 errors, 0 warnings, 0 notes |
| `prek run --all-files` | all hooks Passed |
| Non-vacuity probe (wrong metric) | `CassetteMissError` as required; probe deleted |
| Record mode enabled at any point | never — `adbc_record_mode = "none"` untouched, no `--adbc-record` flag used |

## Deviations from Plan

None — plan executed exactly as written. No auto-fix rules fired.

One addition beyond the plan's letter, in its spirit: the non-vacuity probe above. The plan
required capturing a mismatch only if a cassette *missed*; it passed, so the mismatch was
manufactured deliberately to prove the pass was a real discriminator. This follows Plan
02's precedent of probing an assertion against a deliberately wrong implementation before
trusting it.

## Known Stubs

None. Every artifact this plan produced is exercised by a passing test.

## Threat Flags

None. No new network endpoint, auth path, file access pattern, or schema crosses a trust
boundary. The plan's `<threat_model>` rows are discharged as planned:

- **T-46-05** (information disclosure via cassettes) — mitigated and machine-checked. The
  four trees are byte-identical to sources already recorded under the project's scrub keys
  (`diff -r`), and the tree digest is unchanged across the test run, so a silent write
  would have failed the gate. No file was edited, re-scrubbed, re-serialized, or
  re-recorded, and no record mode was enabled.
- **T-46-09** (placeholder replay credentials) — accepted as planned. The values are the
  literal non-secrets already committed in the sync fixtures; they authenticate to nothing,
  because the plugin intercepts `connect` before any network contact.
- **T-46-08** (SQL generation on the async path) — accepted, and now stronger than
  accepted: the cassette match makes D-04's "no second SQL path" control machine-checked
  across both warehouse dialects, and the probe shows the check has teeth.

## Estimate vs Actual

The plan estimated 40000 tokens at `confidence: low`; the realized diff is 3942 on the same
chars/4 scale — about a tenth. The estimate priced the risk that the spike would *fail* and
need diagnosis: a miss would have meant reading plugin internals, comparing generated SQL
byte by byte, and writing up a phase-stopping finding. It passed on the first run, so none
of that was spent. Read the miss as "the priced risk did not materialize", not as an
over-estimate of the work if it had.

## For Later Plans in This Phase

- **A2 is closed and D-16's gate is discharged.** Plan 06's cross-dialect documentation
  claims now rest on an executed result rather than an assumption.
- Warehouse-dialect async coverage exists and needs no credentials. If a later plan changes
  SQL generation on the async path, these four tests fail with a `CassetteMissError` naming
  both the expected and the received SQL — treat that as the signal it is.
- If a third async integration module appears, `_norm`/`_rows` are now duplicated twice
  (`test_queries.py` and `test_async_queries.py`); promote them to
  `tests/integration/conftest.py` rather than copying again.
- The async fixtures are deliberately **not** registered. When Plan 04 lands the async
  registry, these tests do not need to change — they call `aexecute` on the engine directly
  — but a registry-based variant could be added cheaply if the registry surface deserves
  integration coverage.
- Any future async cassette must use the positional marker form. The bare module-wide
  marker would derive one cassette path per loop backend and demand two recordings for one
  query.

## Self-Check: PASSED

- `tests/integration/conftest.py` (`snowflake_async_engine`, `databricks_async_engine`) — FOUND
- `tests/integration/test_async_queries.py` — FOUND
- `tests/integration/cassettes/async_single_metric_snowflake/adbc_driver_snowflake.dbapi/000_query.sql` — FOUND
- `tests/integration/cassettes/async_single_metric_databricks/adbc_driver_manager.dbapi/databricks/000_query.sql` — FOUND
- `tests/integration/cassettes/async_streaming_iteration_snowflake/adbc_driver_snowflake.dbapi/000_result.arrow` — FOUND
- `tests/integration/cassettes/async_streaming_iteration_databricks/adbc_driver_manager.dbapi/databricks/000_result.arrow` — FOUND
- Commit `bb6f5c6` — FOUND
- Commit `60050f9` — FOUND
- Throwaway probe file — correctly ABSENT (deleted after use)
