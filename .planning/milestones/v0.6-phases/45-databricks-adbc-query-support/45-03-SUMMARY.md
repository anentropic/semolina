---
phase: 45-databricks-adbc-query-support
plan: 03
subsystem: testing
tags: [databricks, adbc, pytest-adbc-replay, cassettes, integration, metric-view]

requires:
  - phase: 45-databricks-adbc-query-support
    provides: "Plan 01 Databricks literal-inlining (.where() emits inline literals + empty params); Plan 02 poolhouse DSN catalog/schema so unqualified views resolve"
provides:
  - "7 recorded Databricks integration cassettes — pytest tests/integration -k databricks now replays 7/7 green in CI with no live warehouse"
  - "End-to-end proof of DBX-01 + DBX-02 over real ADBC (inlined WHERE literal + resolvable unqualified view)"
affects: [ci, databricks-query-execution]

tech-stack:
  added: []
  patterns: ["Databricks cassettes live under adbc_driver_manager.dbapi/databricks/ (the manifest driver), parallel to Snowflake's adbc_driver_snowflake.dbapi/"]

key-files:
  created:
    - "tests/integration/cassettes/integration/test_queries/*_databricks_engine_/ (7 dirs)"
  modified: []

key-decisions:
  - "Recorded SQL uses ANSI double-quoted identifiers (\"country\"), not backticks — this is DatabricksDialect's actual output and the live warehouse accepted it (recording returned correct results). The plan's backtick expectation was a planner assumption; substance (inlined literal + empty params + resolved view) is what DBX-01/02 require and all are present."

patterns-established:
  - "Databricks integration replay: per-backend cassette under .../<test>_databricks_engine_/adbc_driver_manager.dbapi/databricks/ with 000_query.sql / 000_params.json / 000_result.arrow"

requirements-completed: [DBX-03]

duration: ~15m
completed: 2026-06-24
---

# Phase 45 Plan 03: Databricks cassette recording (DBX-03) Summary

**Recorded and committed the 7 Databricks integration cassettes; `pytest tests/integration` now replays 14/14 green (7 Databricks + 7 Snowflake) with no live warehouse, proving the DBX-01 literal-inlining and DBX-02 catalog/schema fixes end-to-end.**

## Performance
- **Duration:** ~15 min (operator recording + verify/commit)
- **Completed:** 2026-06-24
- **Tasks:** 2 (1 human-action checkpoint + verify/commit)
- **Files added:** 7 cassette directories (21 files)

## Accomplishments
- **Task 0 (human-action):** Operator recorded against a live Databricks warehouse via `uv run pytest --adbc-record=once tests/integration -k databricks`. The `databricks_engine` fixture created the temp schema + `sales_view` metric view, recorded, and dropped it on teardown.
- **Task 1 (verify + commit):**
  - 7 `*_databricks_engine_/adbc_driver_manager.dbapi/databricks/` cassette dirs present, each with `000_query.sql` + `000_params.json` + `000_result.arrow`.
  - **WHERE cassette proves both fixes:** `test_filtered_by_dimension` `000_query.sql` is `... WHERE "country" = 'US' ...` (literal **inlined**, no `?`) over `FROM "sales_view"` (unqualified, **resolved** via the DSN catalog/schema), with `MEASURE(...)` wrapping; `000_params.json` == `[]`.
  - Offline replay: `pytest tests/integration -k "databricks or snowflake"` → **14/14 green**. Snowflake unchanged (no regression from the dialect change).
  - Token-leak guard: no `dapi`/`token`/`Bearer`/`access_token` strings in any Databricks cassette.

## Task Commits
1. **Task 0 — record (operator):** no repo commit (produces untracked cassettes)
2. **Task 1 — verify + commit cassettes:** see the `test(45-03)` cassette commit below

## Files Created/Modified
- `tests/integration/cassettes/integration/test_queries/*_databricks_engine_/` — 7 recorded cassette dirs (single_metric, multiple_metrics, metric_with_dimension, multiple_metrics_with_dimension, dimension_only, filtered_by_dimension, streaming_iteration)

## Decisions Made
- **ANSI double-quote identifiers in recorded SQL** (not backticks): this is `DatabricksDialect`'s real output and the live warehouse accepted it (correct results recorded). The plan's backtick expectation was an assumption; the DBX-01/02 substance is fully present. Flagged as a follow-up doc note (the `DatabricksEngine` docstring says "backtick-quoted identifiers" — stale vs. actual double-quote behavior; not a functional issue).

## Deviations from Plan
- Task 1 was run by the orchestrator inline (verify + replay + commit) rather than a spawned executor, continuing the checkpoint. All acceptance criteria met: 7 cassette dirs, inlined WHERE literal + empty params, 14/14 replay green, Snowflake no-regression, no token leak.

## Issues Encountered
- Cassette path has an extra `databricks/` leaf under `adbc_driver_manager.dbapi/` (the manifest driver's DB name) vs Snowflake's `adbc_driver_snowflake.dbapi/` — expected, just a path-shape difference.

## Next Phase Readiness
- DBX-03 complete: Databricks query execution is validated end-to-end and CI has a permanent credential-free replay.
- Phase 45 plans all complete (3/3). Pre-existing, unrelated: ~28 jaffle-shop collection errors (`ModuleNotFoundError: semolina.testing.credentials`, stale conftest import) break `just test` — out of scope for this phase; recommend a separate quick fix.

---
*Phase: 45-databricks-adbc-query-support*
*Completed: 2026-06-24*
