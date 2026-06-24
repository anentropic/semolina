---
gsd_state_version: 1.0
milestone: v0.6
milestone_name: Engine Architecture
status: executing
stopped_at: v0.5 milestone completed and archived (MILESTONES.md, ROADMAP collapsed, PROJECT evolved, RETROSPECTIVE appended, tag v0.5)
last_updated: "2026-06-24T08:07:00Z"
last_activity: 2026-06-24 -- Phase 44 Plan 04 completed (Databricks introspect NotImplementedError fallback + standalone spike; checkpoint deferred)
progress:
  total_phases: 7
  completed_phases: 5
  total_plans: 17
  completed_plans: 15
  percent: 88
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-13)

**Core value:** A single, Pythonic query API that works identically across Snowflake, Databricks, and DuckDB semantic views, with typed models, IDE autocomplete, and backend-agnostic code.
**Current focus:** Phase 44 — engine-owns-the-pool

## Current Position

Phase: 44 (engine-owns-the-pool) — EXECUTING
Plan: 5 of 6
Status: Plan 04 complete — Databricks introspect ships as a marked NotImplementedError fallback (Path B); standalone spike written for later live validation; checkpoint deferred
Last activity: 2026-06-24 -- Phase 44 Plan 04 completed

## Performance Metrics

**By Milestone:**

| Milestone | Phases | Plans | Shipped |
|-----------|--------|-------|---------|
| v0.1 MVP | 7 | 18 | 2026-02-16 |
| v0.2 Tooling & Docs | 20 | 66 | 2026-02-26 |
| v0.3 Arrow & Connection | 8 | 16 | 2026-04-18 |
| v0.4.0 DuckDB & Arrow | 6 | 12 | 2026-05-07 |
| v0.5 Streaming & Codegen | 5 | 11 | 2026-06-13 |

**Cumulative:** 46 phases shipped, 123 plans across 5 shipped milestones.
| Phase 44 P01 | 11min | 3 tasks | 7 files |
| Phase 44 P02 | 18min | 3 tasks | 13 files |
| Phase 44 P03 | 32min | 3 tasks | 10 files |
| Phase 44 P04 | 26min | 3 tasks | 5 files |

## Accumulated Context

### Decisions

(Full Key Decisions log lives in PROJECT.md.)

- [Phase ?]: Co-located Snowflake/Databricks codegen E2E tests in test_codegen_e2e.py sharing the existing .ambr snapshot file
- [Phase ?]: Snowflake sys.modules mock is a non-autouse named fixture so the credential-free DuckDB CLI test in the same module is unaffected
- [Phase 42]: `_field_class_for` uses a strict `_ROLE_TO_CLASS` dict and raises `ValueError` on unrecognized roles (`from None` to surface the role, not the dict miss) — schema drift fails loudly instead of mislabeling a column as Dimension
- [Phase 42]: Closed DKGEN-05; rewrote ROADMAP criterion 4 + REQUIREMENTS from 'Field() fallback preserved' to 'every column resolves to a concrete role; unrecognized role raises ValueError'; logged per-backend metadata-query paths (DuckDB DESCRIBE SEMANTIC VIEW, Snowflake SHOW COLUMNS IN VIEW, Databricks DESCRIBE TABLE EXTENDED AS JSON) in PROJECT.md
- [Phase 43]: Report named v0.5-MILESTONE-AUDIT.md at .planning/ root (not v0.5-UAT-AUDIT.md, not under milestones/) so milestone.complete glob archives it
- [Phase 43]: v0.5 milestone audit verdict: PASSED (6/6 reqs, 4/4 phases verified against shipped surface); STREAM-01/02 checkbox-vs-table drift classed as doc/traceability finding for Plan 02, not a functional gap
- [Phase ?]: [Phase 43]: Reconciled STREAM-01/02 by flipping the stale list checkboxes to [x] (table was the correct side) — list brought up to the Traceability table, table never downgraded
- [Phase ?]: [Phase 43]: Closed AUDIT-01 (list [x] + Traceability Complete) gated on .planning/v0.5-MILESTONE-AUDIT.md status: passed; flipped last after traceability fixes; ROADMAP SC1 amended to name v0.5-MILESTONE-AUDIT.md
- [Phase ?]: [Phase 44 Plan 01]: Rewrote unit suite + shared fixtures to the new create_engine / register(engine) / get_engine / ADBC-cursor contract, committed RED (Wave 0 bedrock for Plans 02-04)
- [Phase ?]: [Phase 44 Plan 01]: Used scoped, removable per-module pyright pragmas (not # type: ignore) to pass basedpyright strict on RED-first tests; Plan 02 removes each on GREEN
- [Phase ?]: Phase 44 Plan 02: create_engine(config|name) builds an Engine owning one ADBC pool + dialect-from-config; Engine base gained connect() + concrete ADBC execute(); registry collapsed to name→Engine register(name,engine)/get_engine (D1/D2/D4)
- [Phase ?]: Phase 44 Plan 02: subclass introspect() + cli/codegen _resolve_backend left on the native seam under removable scoped pyright pragmas; Plans 03/04 rewire onto the pool and remove the pragmas
- [Phase ?]: Phase 44 Plan 03: Snowflake+DuckDB introspect() run over the engine's ADBC pool (self.connect(); SHOW COLUMNS / two-pass DESCRIBE + parsers unchanged); errors caught as adbc_driver_manager.{ProgrammingError,OperationalError,Error}; Engine base now holds self._config so Snowflake reads database for view-name qualification (D3)
- [Phase ?]: Phase 44 Plan 03: codegen CLI _resolve_backend builds every backend via create_engine; native *_connect_kwargs deleted (record-mode DDL glue moved into integration conftest local helpers); public surface final = create_engine/register/get_engine, no pool_from_config/get_pool (D5). Snowflake cassettes replay 7/7 green. Databricks introspect deferred to Plan 04.
- [Phase 44 Plan 04]: Databricks ADBC introspection resolved via the documented FALLBACK (Path B) — the gated human-verify checkpoint was deferred (fallback shipped), NOT blocked: the Foundry adbc_driver_databricks is absent (find_spec→None) and the recording hangs, so a live spike cannot run here. DatabricksEngine now builds via create_engine (pool+dialect) and executes over the inherited ADBC path; introspect() raises NotImplementedError naming scripts/spike_databricks_adbc_introspect.py. The standalone spike (ADBC-vs-native DESCRIBE TABLE EXTENDED AS JSON, fail-fast on missing driver, never hangs) is written for the operator to run later before the real path is implemented (D3). Plan 02 native pragmas removed; no # type: ignore.

### Pending Todos

16 pending todos — see `.planning/todos/pending/`. Carried forward as backlog at v0.5 close (kept intentionally, not deferred gaps); candidate seeds for the next milestone.

### Blockers/Concerns

- Databricks integration recording hangs (likely SQL-warehouse cold-start in `databricks.sql.connect` or ADBC pool connect) — blocks Databricks cassettes AND the Phase 44 Databricks ADBC-introspection spike. Needs a Ctrl-C traceback to localize.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260623-t6a | Remove legacy dead code (credentials module removed; Engine.execute removal reverted → escalated to Phase 44) | 2026-06-23 | 9da2f4e | [260623-t6a-remove-legacy-dead-code-delete-unused-se](./quick/260623-t6a-remove-legacy-dead-code-delete-unused-se/) |

## Deferred Items

Acknowledged and carried forward at v0.5 milestone close (2026-06-13):

| Category | Item | Disposition |
|----------|------|-------------|
| backlog todos | 16 pending under `.planning/todos/pending/` | Kept — future-milestone candidates (CLI query, GraphQL, Cube.dev/dbt-SL backends, dataframe output, Django wrapper) |
| future requirement | STREAM-04 (user-controllable batch size) | Deferred to a later milestone |
| future requirement | DJANGO-01 (`django-semolina` helper package) | Deferred — separate repo |

14 stale historical quick-tasks (v0.1/v0.2 era) were archived to `.planning/milestones/quick-tasks-archive/` during this close, not deferred.

## Session Continuity

Last session: 2026-06-24T08:07:00Z
Stopped at: Completed 44-04-PLAN.md (Databricks introspect NotImplementedError fallback + standalone spike; checkpoint deferred — fallback shipped)
Resume file: None
Next: Execute 44-05 (Integration fixtures → Engine API + cassette-stays-green replay gate)

## Operator Next Steps

- Execute Phase 44 Plan 05 (Integration fixtures → Engine API + cassette-stays-green replay gate)
- DEFERRED (Plan 04 follow-up): live Databricks ADBC introspection is UNVALIDATED and ships as NotImplementedError. Install the Foundry Databricks ADBC driver + a running SQL Warehouse, then run `python scripts/spike_databricks_adbc_introspect.py <schema.metric_view>` to validate `DESCRIBE TABLE EXTENDED AS JSON` over ADBC before implementing the real introspect path. Same recording-hang blocker still gates the Databricks cassettes.
