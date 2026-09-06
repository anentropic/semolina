---
phase: 44-engine-owns-the-pool
plan: 05
subsystem: testing
tags: [pytest-adbc-replay, cassettes, snowflake, create_engine, register, integration]

# Dependency graph
requires:
  - phase: 44-engine-owns-the-pool
    provides: "Plan 02 create_engine + name→Engine register/get_engine; Plan 03 conftest migrated to create_engine + 2-arg register(engine) and record-mode native-kwargs helpers (commit 0a2591b)"
provides:
  - "VERIFIED cassette-stays-green gate: 7/7 recorded Snowflake query tests replay green through the create_engine + register(engine) fixtures (generated SQL byte-identical post-refactor)"
  - "Confirmation that cassette files are unmodified by replay (no re-record); replay path holds no live secrets"
  - "Confirmed the 7 Databricks integration failures are pre-existing CassetteMissError (cassettes never recorded — recording hangs), unchanged by this refactor"
affects: [44-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cassette-stays-green gate: run `pytest tests/integration -k snowflake` (replay mode default) as an explicit acceptance check after a connection-plumbing refactor; a CassetteMissError on Snowflake would mean SQL builder output drifted (regression), never a re-record trigger"
    - "Replay-integrity proof: checksum the cassette tree before/after the run to prove replay mode wrote nothing (no secret leak, no accidental re-record)"

key-files:
  created:
    - .planning/phases/44-engine-owns-the-pool/44-05-SUMMARY.md
  modified: []

key-decisions:
  - "Task 1 (fixture migration) was already landed by Plan 44-03 commit 0a2591b (deviation #3 there moved the record-mode native-kwargs helpers into the conftest while migrating to create_engine + 2-arg register); this plan adds no new source diff — it is the verification gate. No redundant re-commit of unchanged code."
  - "Databricks 7 failures are pre-existing CassetteMissError (directory-missing), not a SQL regression — the Databricks SQL builder emits correct MEASURE(`revenue`) SQL but there is nothing recorded to replay against (recording hangs, STATE blocker). Out of scope, confirmed not regressed."

patterns-established:
  - "A pure verification plan whose upstream code already landed produces a SUMMARY + state updates as its only artifacts; the gate result is the deliverable."

requirements-completed: []

# Metrics
duration: 8min
completed: 2026-06-24
---

# Phase 44 Plan 05: Integration Fixtures → Engine API + Cassette-Stays-Green Gate Summary

**Proved the cassette-stays-green gate: all 7 recorded Snowflake query cassettes replay green through the migrated `create_engine` + `register("test", engine)` fixtures, with cassette files byte-unchanged — confirming the engine-owns-the-pool refactor never touched the SQL builder output.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-06-24T08:10:34Z
- **Completed:** 2026-06-24T08:11:32Z
- **Tasks:** 2 (Task 1 code already landed in Plan 03; Task 2 is the gate)
- **Files modified:** 0 source (SUMMARY + state docs only)

## Accomplishments

- **Cassette gate GREEN (Task 2 — the load-bearing acceptance criterion):** `pytest tests/integration -k snowflake` → **7 passed, 0 failed** in replay mode (`adbc_record_mode = none`). This PROVES the generated Snowflake SQL is byte-identical after the engine-owns-the-pool refactor — pytest-adbc-replay matches on the SQL string the driver receives, so a green replay means only the connection plumbing moved (RESEARCH Pitfall 1 / A3 satisfied by an actual run, not assumed).
- **Replay integrity confirmed (no re-record, no secret leak):** the cassette tree (21 files: `*_query.sql` / `*_params.json` / `*_result.arrow` across 7 Snowflake tests) was checksummed before and after the run — **UNCHANGED**, and `git status` stayed clean. Replay wrote nothing; T-44-08 (secrets leaking into re-recorded cassettes) holds because no cassette was (re)written.
- **Fixtures already on the Engine API (Task 1, landed in Plan 03):** `tests/integration/conftest.py` builds engines via `create_engine(config)` (6 occurrences) and registers via 2-arg `register("test", engine)` (4 sites); zero 3-arg `register(pool, dialect=)`, zero `create_pool`, zero deleted `*_connect_kwargs` imports. Record-mode DDL is retained on the native connectors (`snowflake.connector` / `databricks.sql`, 9 references) via the local `_snowflake_native_kwargs` / `_databricks_native_kwargs` helpers (RESEARCH Open Q1). All Task 1 acceptance greps pass on the committed file.
- **Databricks failures confirmed pre-existing & not regressed:** `pytest tests/integration -k databricks` → 7 `CassetteMissError` (directory does not exist — cassettes never recorded; recording hangs, per the STATE blocker). The errors are *missing recordings*, not SQL drift — the Databricks builder emits correct ``SELECT MEASURE(`revenue`), `country` ... `` SQL. Identical to clean `main`; out of scope per the plan.
- **Full quality gates green:** `prek run --all-files` (ruff, ruff-format, basedpyright strict, no new `# type: ignore`) all PASS. `just test` / full `pytest` → **791 passed, 16 skipped** excluding Databricks; the only 7 failures across the entire suite are the documented pre-existing Databricks cassette misses.

## Task Commits

This plan introduced no new source code (Task 1's migration was completed by Plan 44-03 commit `0a2591b`), so there are no per-task code commits. The plan's deliverable is the verified gate result, recorded here and committed with the plan metadata.

1. **Task 1: Migrate integration fixtures to create_engine + register(engine), keep native DDL** — already landed in `0a2591b` (Plan 44-03 refactor); verified satisfied here via grep, no re-commit.
2. **Task 2: Run the cassette replay gate and confirm green** — verification only (7/7 Snowflake replay green); result recorded in this SUMMARY.

**Plan metadata:** committed with this SUMMARY + STATE.md + ROADMAP.md.

## Files Created/Modified

- `.planning/phases/44-engine-owns-the-pool/44-05-SUMMARY.md` — this gate-result record (created).
- No source files modified — the integration fixtures were already on the Engine API from Plan 03.

## Decisions Made

- **No redundant re-commit of already-migrated code:** the conftest migration (Task 1's intent) was completed in Plan 44-03 (`0a2591b`, deviation #3 there). The working tree is clean and every Task 1 acceptance grep passes against the committed file, so re-editing/re-committing it would be churn. This plan stands as the formal verification gate it was scoped to be.
- **Databricks misses left untouched:** confirmed they are `CassetteMissError` (no recording exists), not a SQL regression from the refactor, and therefore out of scope — matching the plan's explicit exclusion and the 44-03 deferred-items log.

## Deviations from Plan

None — plan executed exactly as written. Task 1's code was already in place from Plan 03 (an expected consequence of that plan's deviation #3, which front-ran the conftest migration while deleting the native helpers); this plan verified the acceptance criteria against the committed file and ran the Task 2 gate. No new code was required.

## Issues Encountered

None. The Snowflake gate passed first try; the Databricks `CassetteMissError`s were anticipated (pre-existing recording-hang blocker) and confirmed unchanged.

## Known Stubs

None.

## Threat Flags

None — this plan ran replay only (no re-record, verified by the before/after cassette checksum), introduces no new endpoint/auth/schema surface, and modifies no source files. T-44-08 (secret leak into cassettes) holds because no cassette was written; T-44-09 (inline native DDL kwargs) is dormant in replay mode (record-mode-only path, not exercised).

## User Setup Required

None - no external service configuration required. (Databricks live recording remains gated by the known recording-hang blocker, tracked in STATE — unchanged by this plan.)

## Next Phase Readiness

- The cassette-stays-green gate is formally PASSED: the engine-owns-the-pool redesign provably did not alter the generated Snowflake SQL. Plan 06 (docs migration to the `create_engine` / `register(engine)` surface) can proceed on a verified-stable runtime path.
- Blocker carried forward unchanged: Databricks integration recording hangs → Databricks cassettes absent and the Phase 44 Databricks ADBC-introspection spike still unvalidated. Not introduced or worsened by this plan.

---
*Phase: 44-engine-owns-the-pool*
*Completed: 2026-06-24*

## Self-Check: PASSED

- SUMMARY file present: `.planning/phases/44-engine-owns-the-pool/44-05-SUMMARY.md`
- Upstream migration commit present: `0a2591b` (Plan 03 — conftest on create_engine + 2-arg register)
- Gate result verified live: `pytest tests/integration -k snowflake` → 7 passed, 0 failed (replay mode)
- Cassette tree byte-unchanged across the run (before/after checksum identical); `git status` clean of cassette writes
- Quality gates green: `prek run --all-files` PASS; full suite 791 passed / 16 skipped excluding the 7 pre-existing Databricks cassette misses
