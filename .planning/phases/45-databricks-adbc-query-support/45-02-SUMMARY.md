---
phase: 45-databricks-adbc-query-support
plan: 02
subsystem: infra
tags: [adbc, databricks, adbc-poolhouse, dsn, catalog, schema, dependency-pin]

requires:
  - phase: 44-engine-owns-the-pool
    provides: Engine owns the adbc-poolhouse pool + dialect; create_engine builds the Databricks pool from DatabricksConfig
provides:
  - "Databricks ADBC connections now carry a default catalog/schema via the DSN, so unqualified view names resolve"
  - "adbc-poolhouse pin bumped to the release (1.3.1) carrying the to_adbc_kwargs catalog/schema fix"
affects: [45-03-recording, databricks-query-execution]

tech-stack:
  added: []
  patterns: ["Databricks default namespace via DSN query params (catalog=/schema=), parallel to SnowflakeConfig's adbc.snowflake.sql.schema"]

key-files:
  created: []
  modified: ["pyproject.toml"]

key-decisions:
  - "Consumption mechanism = release-bump (operator decision at Task 0): cut adbc-poolhouse 1.3.1, then bump the pin here. Cleanest; CI replay uses a real published version."
  - "The to_adbc_kwargs() DSN fix itself lives in the separate adbc-poolhouse repo (released as 1.3.1), not in this repo."

patterns-established:
  - "Default catalog/schema for the arrow-adbc Databricks driver is supplied as URL-encoded ?catalog=&schema= DSN params (the Go driver parses them); the ADBC layer has no target-catalog/schema kwarg."

requirements-completed: [DBX-02]

duration: ~15m
completed: 2026-06-24
---

# Phase 45 Plan 02: Databricks default catalog/schema (DBX-02) Summary

**adbc-poolhouse `DatabricksConfig.to_adbc_kwargs()` now appends URL-encoded `?catalog=&schema=` to the decomposed Databricks DSN (released as 1.3.1); this repo consumes it via a pin bump, so unqualified `FROM \`sales_view\`` resolves on Databricks.**

## Performance

- **Duration:** ~15 min (cross-repo release + consumption)
- **Completed:** 2026-06-24
- **Tasks:** 3 (1 decision checkpoint + cross-repo fix + consumption)
- **Files modified (this repo):** 1 (`pyproject.toml`)

## Accomplishments
- **Task 0 (decision):** Operator chose **release-bump** — cut an adbc-poolhouse release, then bump the pin here. (Cleanest; reproducible CI replay against a published version.)
- **Task 1 (cross-repo fix):** `DatabricksConfig.to_adbc_kwargs()` decomposed branch now builds a `params` dict (`catalog`/`schema` when set) and appends `?` + URL-encoded query string; URI mode untouched; no query string when both are `None`. Landed and **released as adbc-poolhouse 1.3.1** in the separate repo (with its own `to_adbc_kwargs` unit tests).
- **Task 2 (consumption):** Bumped this repo's pin `adbc-poolhouse>=1.2.0` → `>=1.3.1` and `uv sync`'d. Verified from this repo's venv that the built DSN ends with `?catalog=main&schema=myschema` and that a no-catalog/no-schema config emits a bare URI (no `?`). Token stays a `SecretStr` — never logged.

## Task Commits
1. **Task 0 — decision (release-bump):** recorded in `.planning/STATE.md` / this summary (no code commit)
2. **Task 1 — poolhouse `to_adbc_kwargs` fix:** cross-repo, released as **adbc-poolhouse 1.3.1** (commit in the adbc-poolhouse repo, not this one)
3. **Task 2 — consume the fix:** `fd36596` (deps(45): bump adbc-poolhouse to >=1.3.1 — DBX-02 catalog/schema fix consumed)

Supporting: `4bf4b662` (docs(45): adbc-poolhouse bug report for DBX-02) — the issue filed against the cross-repo fix.

## Files Created/Modified
- `pyproject.toml` — `adbc-poolhouse>=1.2.0` → `>=1.3.1` (consumes the DSN catalog/schema fix)
- `uv.lock` — re-locked to adbc-poolhouse 1.3.1

## Decisions Made
- Consumption mechanism = **release-bump** (operator decision; RESEARCH-recommended default).
- The fix is a connection-layer concern (adbc-poolhouse), not a Semolina SQL-generation change — mirrors how `SnowflakeConfig` sets `adbc.snowflake.sql.schema`.

## Deviations from Plan
None as to outcome. Process note: Tasks 0–2 were carried out **interactively with the operator** (decision made live, poolhouse release cut by the operator, pin bump applied and verified) rather than by a spawned executor. All acceptance criteria — DSN carries `?catalog=&schema=`, bare URI when both None, URI mode unmutated, token never logged, pin bumped + venv synced + verified — were met. This SUMMARY is orchestrator-authored to record the already-committed, already-verified work.

## Issues Encountered
None. The verification command from the plan (`to_adbc_kwargs()['uri']` ends `?catalog=main&schema=myschema`) printed OK against the installed 1.3.1.

## User Setup Required
None remaining for this plan — the operator already cut and published adbc-poolhouse 1.3.1.

## Next Phase Readiness
- DBX-02 unblocked: Databricks ADBC connections now default to the configured catalog/schema, so the shared unqualified `Sales(view="sales_view")` model resolves.
- Plan 45-03 (cassette recording) can now resolve the view — pending Plan 45-01 (the `.where()` literal-inlining) and a live warehouse.

---
*Phase: 45-databricks-adbc-query-support*
*Completed: 2026-06-24*
