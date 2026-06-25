---
gsd_state_version: 1.0
milestone: v0.6
milestone_name: Engine Architecture
status: complete
stopped_at: v0.6 (Engine Architecture) milestone complete — archived to milestones/v0.6-ROADMAP.md, ROADMAP collapsed, PROJECT/RETROSPECTIVE updated, tagged v0.6
last_updated: "2026-06-25T00:00:00.000Z"
last_activity: 2026-06-25 -- v0.6 milestone archived, tagged, and shipped via PR #33
progress:
  total_phases: 2
  completed_phases: 2
  total_plans: 9
  completed_plans: 9
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-13)

**Core value:** A single, Pythonic query API that works identically across Snowflake, Databricks, and DuckDB semantic views, with typed models, IDE autocomplete, and backend-agnostic code.
**Current focus:** Between milestones — v0.6 shipped 2026-06-25. Run `/gsd-new-milestone` to define the next one.

## Current Position

Milestone: v0.6 (Engine Architecture) — COMPLETE & SHIPPED 2026-06-25 (Phases 44-45, 9 plans)
Status: Archived to milestones/v0.6-ROADMAP.md; ROADMAP collapsed to milestone grouping; PROJECT.md/RETROSPECTIVE.md/MILESTONES.md updated; tagged v0.6; shipped via PR #33 (CI green).
Last activity: 2026-06-25 -- v0.6 milestone archived, tagged, and shipped

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
| Phase 44 P05 | 8min | 2 tasks | 0 src (gate) |
| Phase 44 P06 | ~40min | 3 tasks | 12 files |
| Phase 45 P01 | ~25min | 2 tasks | 2 files |

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
- [Phase 45 Plan 01]: Databricks `.where()` bind-param blocker (DBX-01) fixed by literal-inlining behind a `Dialect.supports_parameterized_queries` flag (True default; False on DatabricksDialect only). A single audited `Dialect.render_literal` escaper (standard SQL doubles the quote; Spark escapes `\`→`\\` FIRST then `'`→`\'`) plus a `SQLBuilder._render_literal_sql` post-pass in `build_select_with_params` (and the DuckDB override) inline literals + return empty params for Databricks; Snowflake/DuckDB keep `?`+params (DBX-01b). Unsupported literal types raise NotImplementedError (no Date/Decimal yet). No `_compile_predicate` arm edited — the post-pass is the only new control point. Adversarial unit tests (`O'Reilly`, `a\b`, `'; DROP`, NULL, bool, IN-list) cover DBX-01c. TDD RED was demonstrated per task but RED+GREEN landed in one commit each because basedpyright strict rejects a test referencing not-yet-existent attributes and `--no-verify` was disallowed. No `# type: ignore` added. 7 Databricks integration failures (unrecorded cassettes, DBX-03) + 28 jaffle errors (stale `semolina.testing.credentials` import) are pre-existing/out-of-scope (deferred-items.md).
- [Phase 44 Plan 05]: Cassette-stays-green gate VERIFIED by an actual replay run — `pytest tests/integration -k snowflake` is 7/7 green via the create_engine + register("test", engine) fixtures, proving the engine-owns-the-pool refactor left the generated Snowflake SQL byte-identical (pytest-adbc-replay matches on the driver-received SQL). Cassette tree checksummed before/after = UNCHANGED (replay wrote nothing; no re-record, no secret leak). Task 1's fixture migration had already landed in Plan 03 commit 0a2591b (its deviation #3), so this plan added zero source diff — the gate result is the deliverable. The 7 Databricks failures are pre-existing CassetteMissError (recordings never made; recording-hang blocker), confirmed not regressed.
- [Phase 44-04 follow-up, 2026-06-25]: Databricks ADBC introspection IMPLEMENTED, retiring the NotImplementedError fallback. The "Foundry driver absent" premise was stale — the manifest ADBC Databricks driver is live on the dev machine (it recorded the Phase 45 query cassettes), so the spike ran: `DESCRIBE TABLE EXTENDED <view> AS JSON` over ADBC == native (byte-identical). `DatabricksEngine.introspect()` now parses that JSON (is_measure→metric, else→dimension; type.name→Python type via databricks_type_to_python; unmapped→TODO) mirroring SnowflakeEngine; ADBC ProgrammingError/OperationalError→SemolinaViewNotFoundError/SemolinaConnectionError. Recorded an introspect cassette (tests/integration/test_introspect.py, replays green in CI); replaced the NotImplementedError unit/e2e tests; removed scripts/spike_databricks_adbc_introspect.py and the stale docs note. Commit f94418d on gsd/v0.6-milestone.

### Roadmap Evolution

- Phase 45 added: Databricks ADBC Query Support — fix the two query-execution blockers found during live Databricks cassette recording (2026-06-24): arrow-adbc Databricks driver has no bind params (breaks `.where()`) and no default catalog/schema (adbc-poolhouse drops them from the URI). Scope spans Semolina `DatabricksDialect` + adbc-poolhouse. See memory `project_databricks_adbc_query_blockers`.

### Pending Todos

16 pending todos — see `.planning/todos/pending/`. Carried forward as backlog at v0.5 close (kept intentionally, not deferred gaps); candidate seeds for the next milestone.

### Blockers/Concerns

- ~~Databricks integration recording hangs~~ RESOLVED (2026-06-24): the "hang" was paused Free-Edition workloads resuming on first compute (~20min); `connect` is instant. Recording now proceeds, but revealed two arrow-adbc Databricks DRIVER blockers in query execution — no bind params (breaks `.where()`) and no default catalog/schema (poolhouse drops them) — moved to **Phase 45** (now complete: DBX-01/02/03 verified, 7 Databricks query cassettes recorded + green). The introspection spike has also been run — the ADBC Databricks driver turned out to be present on the dev machine — so introspect() is implemented and cassette-backed (2026-06-25). No open Databricks blockers. See memory `project_databricks_adbc_query_blockers`.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260623-t6a | Remove legacy dead code (credentials module removed; Engine.execute removal reverted → escalated to Phase 44) | 2026-06-23 | 9da2f4e | [260623-t6a-remove-legacy-dead-code-delete-unused-se](./quick/260623-t6a-remove-legacy-dead-code-delete-unused-se/) |

## Deferred Items

Acknowledged and carried forward at v0.6 milestone close (2026-06-25):

| Category | Item | Disposition |
|----------|------|-------------|
| backlog todos | 17 pending under `.planning/todos/pending/` | Kept — future-milestone candidates (CLI query, GraphQL, Cube.dev/dbt-SL backends, dataframe output, Django wrapper) |
| future requirement | STREAM-04 (user-controllable batch size) | Deferred to a later milestone |
| future requirement | DJANGO-01 (`django-semolina` helper package) | Deferred — separate repo |
| future requirement | `render_literal` Date/Decimal support (Databricks `.where()` raises `NotImplementedError`) | Deferred — widen when a real case needs it |

The audit-open report at v0.6 close showed only the 17 pending backlog todos (no open debug/quick-task/code-review/security artifacts); acknowledged as future-milestone candidates, not gaps.

Earlier carried forward at v0.5 close (2026-06-13): the same backlog todos (then 16); 14 stale historical quick-tasks (v0.1/v0.2 era) were archived to `.planning/milestones/quick-tasks-archive/` then, not deferred.

## Session Continuity

Last session: 2026-06-25
Stopped at: v0.6 (Engine Architecture) milestone complete — archived, ROADMAP collapsed, PROJECT/RETROSPECTIVE/MILESTONES updated, tagged v0.6, shipped via PR #33.
Resume file: None
Next: Between milestones. Run `/gsd-new-milestone` to define the next one (questioning → research → requirements → roadmap). 17 backlog todos under `.planning/todos/pending/` are candidate seeds.

## Operator Next Steps

- ✅ v0.6 (Engine Architecture) shipped 2026-06-25: Phase 44 (Engine owns the pool + docs migration) and Phase 45 (Databricks ADBC query support) complete; Phase 44-04 Databricks-introspect follow-up resolved. Archived to `.planning/milestones/v0.6-ROADMAP.md`; tagged `v0.6`; merged via PR #33.
- Start the next milestone with `/gsd-new-milestone` — it creates a fresh `REQUIREMENTS.md`. Candidate directions: CLI query interface, GraphQL, Cube.dev/dbt-SL backends, dataframe-agnostic output, `django-semolina` (17 pending todos).
