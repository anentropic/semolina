---
gsd_state_version: 1.0
milestone: v0.7
milestone_name: Async & Typed Results
current_phase: 50
current_phase_name: Codegen'd Typed DTOs
status: executing
stopped_at: Completed 50-07-PLAN.md
last_updated: "2026-08-15T10:46:18.369Z"
last_activity: 2026-08-15
last_activity_desc: Phase 50 execution started
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 33
  completed_plans: 32
  percent: 80
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-13)

**Core value:** A single, Pythonic query API that works identically across Snowflake, Databricks, and DuckDB semantic views, with typed models, IDE autocomplete, and backend-agnostic code.
**Current focus:** Phase 50 — Codegen'd Typed DTOs

## Current Position

Phase: 50 (Codegen'd Typed DTOs) — EXECUTING
Plan: 8 of 8
Status: Ready to execute
Progress: [████████████████████] 18/18 plans ([██████████] 97%)
  Phase 48 closed 2026-08-13 at UAT with one accepted limitation: Databricks `interval`
  still annotates as `TODO:` because no fixture, cassette, or recording in the repo
  contains an interval column, so the annotation cannot be measured and a guess was
  rejected. TYPE-05 therefore stays open in REQUIREMENTS.md rather than being absorbed by
  phase closure; the override is in 48-VERIFICATION.md, the gap is WINDOWS.md entry 7, and
  closing it needs
  `.planning/todos/pending/2026-08-12-record-databricks-interval-column.md` — a live
  Databricks workspace, worth doing in one session with the two other Databricks
  recording todos.
Last activity: 2026-08-15 — Phase 50 execution started

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
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 46 P01 | 15min | 3 tasks | 5 files |
| Phase 46 P02 | ~2h | 3 tasks | 6 files |
| Phase 46 P03 | ~40m | 2 tasks | 14 files |
| Phase 46 P04 | ~50min | 2 tasks | 5 files |
| Phase 46 P06 | ~1h | 2 tasks | 4 files |
| Phase 46 P05 | 55 | 2 tasks | 2 files |
| Phase 46 P07 | 35min | 2 tasks | 0 src (gate) + 1 config files |
| Phase 46 P08 | 12min | 3 tasks | 5 files |
| Phase 47 P01 | 25min | 3 tasks | 6 files |
| Phase 47 P02 | 35min | 3 tasks | 4 files |
| Phase 47 P03 | 12min | 3 tasks | 11 files |
| Phase 47 P04 | ~40min | 3 tasks | 6 files |
| Phase 48 P01 | 16min | 3 tasks | 16 files |
| Phase 48 P02 | 9min | 2 tasks | 2 files |
| Phase 48 P03 | 22min | 4 tasks | 15 files |
| Phase 48 P04 | 38min | 4 tasks | 8 files |
| Phase 48 P05 | 19min | 3 tasks | 9 files |
| Phase 48 P06 | 13min | 3 tasks | 7 files |
| Phase 49 P01 | 12min | 3 tasks | 11 files |
| Phase 49 P03 | 13min | 2 tasks | 4 files |
| Phase 49 P02 | 21min | 3 tasks | 2 files |
| Phase 49 P04 | 25m | 2 tasks | 3 files |
| Phase 49 P05 | 18min | 2 tasks | 2 files |
| Phase 49 P06 | 12min | 3 tasks | 3 files |
| Phase 49 P07 | 25min | 3 tasks | 13 files |
| Phase 50 P01 | 13min | 2 tasks | 4 files |
| Phase 50 P02 | 32min | 2 tasks | 5 files |
| Phase 50 P03 | 13min | 2 tasks | 2 files |
| Phase 50 P04 | 21min | 2 tasks | 1 files |
| Phase 50 P05 | 10min | 2 tasks | 1 files |
| Phase 50 P06 | 20min | 3 tasks | 6 files |
| Phase 50 P07 | 8min | 2 tasks | 5 files |

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
- [Phase ?]: [Phase 46 Plan 01]: adbc-poolhouse floor bumped to >=1.6.1 on BOTH the base pin and the new [async] extra (not just the extra) so sync and async agree on pool_size resolution — _resolve_tuning landed in 1.6.0; RESEARCH Assumption A1 closed by an executed full-suite run (917 passed, zero test adjustments needed)
- [Phase ?]: [Phase 46 Plan 01]: TID251 Posture A gate armed over src/semolina (asyncio + anyio banned, tests/** exempt per D-14) and proven non-vacuous by an executed fail-first probe — a throwaway 'import asyncio' under src/semolina/ exits 1, the same imports under tests/ exit 0; residual dynamic-lookup evasion recorded, and ROADMAP SC4 reworded from a textual 'asyncio. reference' scan to the import-graph invariant TID251 actually enforces
- [Phase ?]: 46-02: async public surface fixed — create_async_engine / AsyncEngine / AsyncSemolinaCursor, with aexecute returning an already-open cursor (async with await ...)
- [Phase ?]: 46-02: async fetch methods keep their sync names and are awaited; description/rowcount stay plain properties (poolhouse keeps them synchronous)
- [Phase ?]: 46-02: async cursor teardown is strictly reader -> cursor -> connection, each step suppressed at Exception not BaseException so cancellation still propagates
- [Phase ?]: 46-02: no __del__ rescue on the async cursor — it warns only; an unclosed async cursor leaks a pool slot permanently, documented rather than claimed as parity
- [Phase ?]: 46-03: D-16 spike passed first run — copied cassettes replay through the async path for both dialects and both loop backends; RESEARCH Assumption A2 closed by execution
- [Phase ?]: 46-03: async cassette tests use the positional adbc_cassette marker, so one cassette serves both asyncio and trio; dialect comes from the requested engine fixture
- [Phase ?]: 46-04: async registry surface named register_async_engine / get_async_engine / unregister_async_engine (adjective-before-noun, matching create_async_engine) — a trailing _async verb suffix would read as 'this is a coroutine', the exact mode confusion D-05/D-06 exist to remove; all three are plain defs
- [Phase ?]: 46-04: two separate registry dicts with no fallback arm (D-05) — get_async_engine never reads _engines, and the empty-registry hint names register_async_engine + create_async_engine so a failed aexecute never sends a reader to the store that cannot serve it
- [Phase ?]: 46-04: registry.reset() stays a plain def and closes async engines inline via close_pool(engine._pool._pool) — the same call AsyncPool.close offloads — because it is autouse-invoked with no running loop; probed non-vacuous (both reset tests fail against a skipped-teardown impl)
- [Phase ?]: 46-04: _Query.aexecute validates before resolving and before any checkout, so an invalid query never consumes a pool slot; asserted on the inner pool's own checkedin/checkedout counters and probed against a checkout-first implementation
- [Phase ?]: 46-06: async docs omit cancellation/timeout/client-disconnect entirely — adbc-poolhouse 1.6.1 deadlocks on a cancelled in-flight query; fix is open PR #43 (1.6.2, unreleased) and the floor is still >=1.6.1
- [Phase ?]: 46-06: the no-finalizer async cursor leak is stated once under label howto-web-api-async-cursor-close in web-api.rst and cross-referenced elsewhere
- [Phase ?]: 46-06: docs lifecycle sections moved from close_pool(engine._pool) to engine.dispose(); DuckDB pool_size docs corrected (:memory: pins 1, file-backed defaults 5)
- [Phase ?]: The abort-reached-the-driver claim is asserted as elapsed time against a measured uncancelled duration — nothing weaker distinguishes a real abort from a client that merely stopped waiting
- [Phase ?]: DuckDB's semantic_views extension does not observe the interrupt flag inside its table function, so the ASYNC-06 reach claim runs over plain SQL through AsyncEngine.connect() while aexecute carries transparency and pool recovery
- [Phase ?]: The asyncio/Trio loop matrix is enforced structurally by an AST walk over the test tree, selecting modules by content rather than filename
- [Phase ?]: 46-07: the phase gate ran every plan's verification together — the loop-matrix invariant's first complete run (5 modules across waves 2-4), the cassette digest identical to Plan 03's, full suite 1029 passed, prek clean, docs -W clean, packaging smoke reproduced locally
- [Phase ?]: 46-07: TOOL-01 restored git.branching_strategy to milestone as the phase's FINAL commit, made with plain git rather than the GSD helper because the helper reads the value the same task changed — branch auto-switching is live again from that commit onward
- [Phase ?]: 46-07: the plan's packaging criterion named the 1.6.1 floor and fails verbatim; commit 00b0b31 moved both pins to 1.6.2, so the criterion's intent (base and async extra share one pinned floor, all includes async) was checked instead and the stale criterion recorded as a finding
- [Phase ?]: 46-08: the DuckDB caveat 46-VERIFICATION.md gap #2 requested was NOT written and the request is retired in place — it describes semantic_views below 0.12.0 and is false at the duckdb==1.5.5 floor; the timeout section states the version dependency positively with the old behaviour in the past tense
- [Phase ?]: 46-08: the client-disconnect section names Starlette 1.0.0 and the two functions read from installed source (routing.request_response awaits the handler with no disconnect watcher; requests.Request.is_disconnected polls inside a pre-cancelled scope) rather than asserting framework behaviour on the plan's say-so
- [Phase ?]: 46-08: the streaming section claims propagation and close ordering only — the elapsed-time evidence covers the executing statement, so no mid-batch-pull abort is claimed; the deadline story is told once under howto-web-api-timeouts and cross-referenced
- [Phase ?]: [Phase 47 Plan 01]: type-fidelity verdict vocabulary is two values (match/mismatch), not three — a 'TODO: ' annotation scores mismatch, resolving a contradiction between the plan's action text (which said mapping-gap) and its own must_haves (which required mismatch on that exact row). A TODO annotation renders as Any, so it names no Python type at all; that is the strongest disagreement, not a separate kind.
- [Phase ?]: [Phase 47 Plan 01]: the probe route is measured, not labelled — probe_schema returns ProbeResult(schema, route) and the artifact renders 'live (execute-schema)'; DuckDB answered adbc_execute_schema directly, so the zero-row fallback has still never fired in anger (RESEARCH A5 remains unrun).
- [Phase ?]: [Phase 47 Plan 01]: metadata raw type is re-measured by re-running introspect()'s own DESCRIBE SELECT * FROM semantic_view(...), never parsed back out of the 'TODO: ' prefix — the prefix only survives for types the map already misses, exactly the population the artifact must not special-case.
- [Phase ?]: [Phase 47 Plan 01]: only one of 47-VALIDATION.md's two Wave 0 checkboxes was ticked. The copied-Snowflake-cassette item stays open because this plan copied no cassette; ticking it would record unmeasured work in the phase whose premise is that claims must be measured.
- [Phase ?]: [Phase 47 Plan 01]: measurement matched RESEARCH.md on the first run with zero tuning — TODO: DECIMAL(38,2) / decimal128(38, 2) / decimal.Decimal. Every guard was proven non-vacuous by breaking its input and recording the red output before reverting.
- [Phase ?]: Phase 47 nullability is a policy call, not a measurement: the Arrow nullable flag reads True for all seven measured DuckDB fields including COUNT, so the empty-group observation (SUM/AVG/MIN/MAX -> None, COUNT -> 0) is the only evidence
- [Phase ?]: The type-fidelity artifact quotes measured DuckDB and semantic_views versions read from the running database rather than from pyproject.toml, so a version bump makes the artifact stale rather than silently wrong
- [Phase ?]: Capability and result-type claims live in two tables sharing no column: Driver capability is answered from driver source at a pinned version, Field type comparison from recordings; a replayed adbc_execute_schema is never presented as driver capability
- [Phase ?]: The artifact's Snowflake and Databricks numbers are read from the committed cassettes with pyarrow.ipc.open_file, not through the replay cursor; tests assert the two reads agree field for field
- [Phase ?]: Snowflake metadata cells are labelled derived-from-code (RESEARCH.md option b); the hand-fed mock in tests/unit/test_snowflake_engine.py is deliberately not used as evidence
- [Phase ?]: Databricks' measured result column is measure(revenue), not the MEASURE("revenue") the plan predicted; the measurement was recorded and the divergence flagged rather than the assertion adjusted
- [Phase ?]: [Phase 47 Plan 04]: Decimal policy is decimal.Decimal on all three backends and covers the whole Snowflake FIXED family INCLUDING scale 0 — the driver returns Decimal128 for every FIXED column while use_high_precision is enabled (its default, which adbc_poolhouse never changes), so a Snowflake NUMBER(38,0) column annotates as Decimal, not int
- [Phase ?]: [Phase 47 Plan 04]: the Decimal policy is ANNOTATION-ONLY and 47-DECISIONS.md states it as a prohibition — batch.to_pylist() feeding Row(...) at cursor.py:281 is the whole value path and carries no coercion, so Phase 48 touches type_map.py plus the renderer and must NOT touch cursor.py or results.py; this was the deciding factor at the review gate
- [Phase ?]: [Phase 47 Plan 04]: metric nullability is a uniform T-or-None stance with COUNT named as a documented over-approximation, chosen over expression sniffing because the aggregate expression is reachable on DuckDB and Databricks but not from Snowflake SHOW COLUMNS IN VIEW
- [Phase ?]: [Phase 47 Plan 04]: the query-time result schema is promoted to primary and warehouse introspection metadata demoted to a labelled fallback; where both exist and disagree the result schema wins and codegen records which route produced the annotation
- [Phase ?]: [Phase 47 Plan 04]: the Snowflake FIXED generalisation is labelled driver-source evidence rather than measurement (only one scale-0 column was measured), and a Snowflake COUNT annotating as Decimal is flagged as an unmeasured consequence for the follow-up cassette todo
- [Phase ?]: [Phase 47 Plan 04]: 47-DECISIONS.md is normative and docs/src/explanation/type-fidelity.rst is derived from it one-directionally — the page carries no .planning link, so the two cannot form a citation cycle
- [Phase ?]: Metric nullability is applied only in _build_model_context; type maps and all three engines stay nullability-free so IntrospectedField.data_type never carries | None
- [Phase ?]: _DATETIME_TYPES deleted rather than extended — imports now derive from resolved _FieldContext annotations by prefix containment, disarming the pitfall where | None silently drops import datetime
- [Phase ?]: duckdb_type_to_python refuses container types (names ending in ]) before stripping parenthesized parameters — the DECIMAL key exposed that DECIMAL(10,2)[] was annotating a list as a scalar decimal
- [Phase ?]: Phase 47's circularity canary re-pointed at a new region_list AS list(o.region) metric (raw type VARCHAR[]) with a positive twin for the decimal case; 47-DECISIONS.md left unedited and its superseded cell values recorded in 48-01-SUMMARY.md instead
- [Phase ?]: The scope fence defaults to Phase 48's starting commit, not origin/main — the v0.7 branch legitimately created acursor.py in Phase 46, so an origin/main default would be permanently red for an unrelated reason
- [Phase ?]: Regenerate 47-TYPE-FIDELITY.md with uv sync --all-groups --extra all, not --dev --extra all: the latter prunes the docs group and breaks just docs-build
- [Phase ?]: The str branch was folded into the same if/elif chain as date and datetime so each render_literal body evaluates its escaping expression exactly once
- [Phase ?]: _timestamp_literal_text is a module-level formatter (no escaping) shared by both dialects, so D-08's UTC normalisation cannot drift between them
- [Phase ?]: The re-pointed render_literal negative guards use a set, a type a user might plausibly pass by accident
- [Phase ?]: Phase 48's annotation contract is proved by executed measurement (isinstance against a value from the real driver path or a committed cassette), not by human review of a table — the planned checkpoint was rejected and replaced
- [Phase ?]: The Databricks day-time interval -> datetime.timedelta annotation was reverted as unmeasurable; TYPE-05 is evidence-limited on that half, tracked in WINDOWS.md 7 with a recording todo
- [Phase ?]: 48-04: the promoted probe's public surface was decided by grepping its consumers, not escalated — NOT_IMPLEMENTED_ERRORS has a live test asserting the fallback can fire, so hiding it would have made an existing test import a private name across a package boundary
- [Phase ?]: 48-04: there is exactly one import path to the probe — tests/type_fidelity_probe.py re-exports nothing and every consumer imports semolina.codegen.probe directly, so the shipped module is the thing under test
- [Phase ?]: 48-04: pyarrow is TYPE_CHECKING-only in probe.py against the plan's instruction — with 'from __future__ import annotations' a dataclass field annotation is never evaluated, and ruff TC002 rejected the module-scope import
- [Phase ?]: 48-04: arrow_type_to_python answers None for an interval, deliberately disagreeing with _DUCKDB_TYPE_MAP's known-wrong datetime.timedelta — two maps wrong in step would read as agreement
- [Phase ?]: 48-04: the Databricks ADBC driver still has no ExecuteSchema at the installed go/v0.1.2 (statement.go byte-identical at v0.1.3); the C shim's type assertion fails and returns ADBC_STATUS_NOT_IMPLEMENTED, so probe.py's zero-row fallback is load-bearing. The repo pins no ADBC Databricks driver at all — it arrives via a machine-local Foundry manifest
- [Phase ?]: semolina codegen --check ships as a flag on the existing codegen command with a required --model PATH, a per-field stderr table, and EXIT_ANNOTATION_DRIFT=5; every row names the route (execute-schema / zero-row / metadata) that produced it
- [Phase ?]: TYPE-07's 'fetches no rows' is scoped to the view's DATA: engine.introspect() fetches catalogue rows from DESCRIBE/SHOW and always has, so the guard permits those and refuses everything else
- [Phase ?]: Acceptance for the check mode is DuckDB-live end-to-end only. Snowflake is narrowed to the comparison core over the committed recording because no Snowflake introspection cassette exists; Databricks is claimed nowhere (D-09). Recorded as WINDOWS.md entry 9.
- [Phase ?]: 48-06: the falsified type-fidelity note was replaced with two body sections, not another admonition — what a generated annotation promises is the page's subject, not an aside
- [Phase ?]: 48-06: Databricks --check documented as 'unverified', claiming neither success nor failure; broken window 2 and its todo stay open (D-09)
- [Phase ?]: 48-06: TYPE-05 left Pending in REQUIREMENTS.md — partial by decision (Databricks interval unmapped, window 7); nyquist_compliant:true means every row has a green command, not that every requirement shipped
- [Phase ?]: 48-06: WINDOWS.md entries 2 and 3 hand-edited (gsd-tools windows has no description edit) from one string in one pass, then verified three ways per T-48-29
- [Phase ?]: [Phase 49 Plan 01]: arrowmodel floor is >=1.0.0 uncapped and its SUS legitimacy score is a confirmed false positive — PyPI author Anentropic <ego@anentropic.com> and repo anentropic/arrowmodel are this project's own maintainer; 1.0.0 is still the only release, re-checked at execution time
- [Phase ?]: [Phase 49 Plan 01]: PD-06 narrowed Phase 48's value-path scope fence from a path fence to a CONTENT fence for cursor.py/acursor.py (results.py stays path-fenced); the replacement AST fence was proven non-vacuous against a deliberate float() in __next__ and cannot skip, but the narrowing is a real reduction in guarantee and is the plan's only human_judgment deliverable
- [Phase ?]: [Phase 49 Plan 01]: typing.Any needs an explicit special case in the DTO pre-check because issubclass(x, Any) RAISES TypeError on 3.11 but quietly returns False on 3.14 — both are in the CI matrix, so falling through would crash on one and produce a false mismatch on the other
- [Phase ?]: [Phase 49 Plan 01]: validate=True catches exactly one thing the structural pre-check does not — a NULL in a non-optional field — which is D-09's accepted consequence (the Arrow nullable flag is uninformative); pinned by a test rather than left as an inference
- [Phase ?]: [Phase 49 Plan 01]: DTO-01/03/05 left Pending in REQUIREMENTS.md — each is partial (sync-only, eager-only, declaration-only) with the other halves owed by Plans 02/04/06; follows Phase 48's TYPE-05 precedent rather than ticking unmeasured work
- [Phase ?]: [Phase 49 Plan 01]: import semolina pulls pyarrow into sys.modules via adbc_poolhouse, which imports it opportunistically without declaring it — so Plan 04's packaging test must assert absence for arrowmodel/pandas/polars only, never pyarrow
- [Phase ?]: [Phase 49 Plan 03]: A3 closed by measurement — polars 1.43.2 maps decimal128(38,2) to a native Decimal(precision=38, scale=2) dtype holding decimal.Decimal, strictly better than pandas' object column; fetch_polars() therefore needs no precision caveat
- [Phase ?]: [Phase 49 Plan 03]: the generated closing prose in render_downstream_decimal was fixed alongside the table — editing the .md alone would have failed --check, since the A3-stays-open and pandas-is-undeclared sentences are emitted by the generator
- [Phase ?]: [Phase 49 Plan 03]: polars' unconditional DataFrame | Series return was narrowed with isinstance + get_column rather than Any or a type: ignore, and from_arrow was kept as the measured call because it is the call ADBC's fetch_polars() makes
- [Phase ?]: [Phase 49 Plan 03]: 47-DECISIONS.md corrected by addition only (14 insertions, 0 deletions) — two dated 2026-08-14 corrections beneath the originals per D-17, following the 46-VERIFICATION.md precedent
- [Phase ?]: 49-02: public streaming method name confirmed as iter_into at a one-way gate (D-04) — committed for cursor.py, Plan 06's async twin, Plan 07 docs and Phase 50 DTOs
- [Phase ?]: 49-02: iter_into is a plain method returning a generator from a private _iter_into_impl; proven non-vacuous by observing the fail-fast test go red against a bare-generator implementation
- [Phase ?]: 49-02: on Python 3.14 typing.Union IS types.UnionType (PEP 604 unification) — dto.py's two-branch union test is a tautology there and load-bearing on 3.11; do not simplify it
- [Phase ?]: 49-02: semolina.JsonValue's RecursionError reproduces only from a real imported module, never from a function-local class; its probe module must not live on disk under tests/ because --doctest-modules imports it at collection
- [Phase ?]: 49-04: base-install absence is asserted in CI for all four optional packages — a real clean venv measured False for every one, INCLUDING pyarrow, which supersedes 49-01's inference that pyarrow could not be asserted absent (that finding was about sys.modules in the dev venv, a different observation)
- [Phase ?]: 49-04: a module-scope AST import scan over src/semolina replaces the sys.modules coverage that adbc-driver-manager's opportunistic pyarrow/pandas/polars imports made vacuous; codegen/arrow_map.py is allowlisted and paired with a not-reached-by-the-package-root assertion
- [Phase ?]: 49-05: fetch_polars is guarded on polars ONLY (correcting D-15): ADBC hands polars the raw PyCapsule stream and never builds a pyarrow reader
- [Phase ?]: 49-05: fetch_df is guarded pyarrow-then-pandas, confirmed from ADBC source: fetch_df is self.reader.read_pandas() and the reader property calls _requires_pyarrow() first
- [Phase 49 Plan 06]: Async iter_into is a plain method returning an async iterator (neither coroutine nor async generator function) — proven by breaking it: 6 tests red across both backends
- [Phase 49 Plan 06]: The four async Arrow/dataframe guard sets are Plan 05's unchanged; poolhouse offloads ADBC's own implementations, and the guard must run before the await because poolhouse never pre-checks pandas/polars
- [Phase ?]: [Phase 49 Plan 07]: the [arrowmodel] extra now composes semolina[pyarrow] (orchestrator-directed, user-approved) — both DTO methods guard pyarrow BEFORE arrowmodel, so the extra named for DTO support raised SemolinaMissingDependencyError on the very call it advertised; extras are unreleased so nothing breaks
- [Phase ?]: [Phase 49 Plan 07]: the worked example uses the sibling how-to pages' Sales model (revenue + country) rather than jaffle-shop's Orders — the must_haves truth requires the cassette-verified AGG("REVENUE") string, and Sales.revenue/Sales.country are exactly the columns the committed Snowflake cassette carries, so every column name on the page is measured rather than derived
- [Phase ?]: [Phase 49 Plan 07]: the alias section is a measured three-warehouse table, not a Snowflake footnote — Snowflake AGG("REVENUE")/COUNTRY, Databricks measure(revenue)/country, DuckDB bare names; the dimension column diverges too, which the plan did not anticipate
- [Phase ?]: [Phase 49 Plan 07]: an unverified claim that arrowmodel releases the GIL during conversion was cut during the humanizer pass — nothing in this phase measured it
- [Phase ?]: [Phase 49 Plan 07]: todo-retirement convention is git mv pending/ -> completed/ plus an updated: frontmatter key and a leading ## Status section (2026-08-12 precedent); the parallel done/ directory is v0.2-era and unused
- [Phase ?]: [Phase 49 Plan 07]: the retired RESULT-01 todo records 'tests across all three backends' as only PARTLY met — no integration test calls fetch_df/fetch_polars; accepted because both are pure ADBC passthroughs with no Semolina-side branch by backend
- [Phase ?]: Metric result-column spelling lives on the dialect (Dialect.metric_result_column_name), distinct from wrap_metric's SELECT-clause spelling — appended as an extra candidate, never substituted
- [Phase ?]: ProbedQuery carries the query and the dialect alongside the schema, so a probed schema cannot be rendered against a dialect that did not build its SQL (T-50-06 stated in the type)
- [Phase ?]: A generated artifact's provenance header prints measured values (dialect, probe route) beside the caller's claimed backend label, and refuses the claim when the two are comparable and disagree
- [Phase ?]: DTO codegen's live tracer splits into a data_fetch_guard'ed generation half and an unguarded .into() round-trip half — the guard is what makes 'the probe fetches no rows' a measurement
- [Phase ?]: DTO alias cells are asserted through render_dtos with a synthetic pyarrow schema, so Snowflake and Databricks spellings are pinned offline
- [Phase ?]: Each generated DTO class docstring repeats its probe route, so provenance survives the class being copied out of the file
- [Phase ?]: Generated DTOs emit from __future__ import annotations unconditionally, since every metric annotation is a T | None union
- [Phase ?]: RESEARCH R-02's open config question resolved as option (b): both DTO-08 halves run under a dedicated stock-strict basedpyright config with no rule suppressions, not Semolina's seven-rule-disabled one
- [Phase ?]: The DTO-08 negative control trips reportUnknownVariableType, a rule pyproject.toml disables, so one control proves both that the harness can fail and whose configuration answered
- [Phase ?]: basedpyright's --project (which rules apply) and --pythonpath sys.executable (which environment resolves imports) are separate knobs, so a stricter-than-the-project claim costs no venv resolution
- [Phase 50]: DTO-09's fallback is proven as a branch, not as a backend: a live DuckDB cursor made to refuse ExecuteSchema, with Databricks explicitly unverified — pytest-adbc-replay serves adbc_execute_schema from the recorded result table regardless of driver capability, so a cassette-backed Databricks test would be green whatever the real driver does. WINDOWS.md entry 12; closed only by the pending live-workspace todo.
- [Phase 50]: The failing fallback is made to raise ProgrammingError, a class inside probe.NOT_IMPLEMENTED_ERRORS — Proves the catch is scoped to the primary adbc_execute_schema call rather than wrapped around the whole probe — a funnel one line wider fails this test.
- [Phase ?]: O-02 settled by the user: DTO codegen ships as a separate 'semolina codegen-dto' subcommand, not a --dto flag on codegen — the positional slot means one noun per command
- [Phase ?]: A generated DTO's backend_label is derived from the dialect that answered, never echoed from --backend, so --backend dotted.path.ClassName cannot trip the header's own truthfulness check
- [Phase ?]: No 'Generated by:' command line in generated DTOs: a faithful one would embed a local --database path, an unfaithful one is the false provenance the header check exists to prevent
- [Phase ?]: codegen-dto is a separate subcommand, so its docs are a separate page rather than a section of codegen.rst
- [Phase ?]: A duplicated table is verified by a script that parses all three copies, not by reading them side by side
- [Phase ?]: typed-results.rst keeps its hand-written alias route: a hand-authored DTO is still supported, so codegen is offered as a lead-in rather than a replacement

### Roadmap Evolution

- Phase 45 added: Databricks ADBC Query Support — fix the two query-execution blockers found during live Databricks cassette recording (2026-06-24): arrow-adbc Databricks driver has no bind params (breaks `.where()`) and no default catalog/schema (adbc-poolhouse drops them from the URI). Scope spans Semolina `DatabricksDialect` + adbc-poolhouse. See memory `project_databricks_adbc_query_blockers`.

### Pending Todos

20 pending todos — see `.planning/todos/pending/`. Mostly backlog carried forward at v0.5/v0.6 close (candidate seeds for the next milestone), plus three v0.7 recording todos that need one live Databricks session: `2026-08-12-record-databricks-interval-column.md` (blocks TYPE-05), `2026-08-12-verify-databricks-zero-row-fallback.md`, and `2026-08-12-record-snowflake-introspection-cassette.md`.

### Blockers/Concerns

- ~~**Phase 46 cannot close: ASYNC-06 is unproven**~~ **RESOLVED (2026-08-11).** The root cause was
  in `anentropic/duckdb-semantic-views`: `semantic_view()` executed its inner query on a **new
  `ClientContext`**, and DuckDB's interrupt flag is per-`ClientContext`, so the flag `adbc_cancel`
  set on the caller's context was never read. Fixed upstream in **0.12.0**, published to the
  community CDN for DuckDB core **1.5.5** on 2026-08-11; the `duckdb` pin moved `1.5.3` → `1.5.5`.
  Verified on one machine across both builds, interrupting at a tenth of the baseline: 0.10.3
  returned at 3.22s of a 3.97s baseline (ran to completion), 0.12.0 returns at 0.55s of 3.21s.
  ASYNC-06's elapsed-time claim is now asserted on Semolina's own generated SQL in
  `TestCancellationThroughAexecute` and is non-vacuous (the old build fails it at 0.81 of baseline
  where the new one passes at 0.17). All three gates green on the new pin; one unrelated fixture
  needed fixing, as 0.12.0 also began rejecting a metric/dimension name collision
  (`tests/unit/test_pool.py`).

- ~~**Phase 46 still owes its docs**~~ **RESOLVED (2026-08-11) by plan 46-08.** Three of the
  four sections `46-06-SUMMARY.md` listed are now written — `Time out a slow query` and
  `Handle a client disconnect` in `docs/src/how-to/web-api.rst`, `Cancel an async stream
  mid-iteration` in `docs/src/how-to/streaming.rst` — and the fourth (the `installation.rst`
  floor paragraph) was already done in 46-06. The omission spanned two files, not
  `web-api.rst` alone as `WINDOWS.md` entry 1 said. Every behavioural claim maps to a named
  test in `tests/unit/test_async_cancel.py`; the mapping table is in `46-08-SUMMARY.md`.
  `WINDOWS.md` entry 1 is `fixed` (closed via `gsd-tools windows fixed 1`, not by hand) and
  `open_count` is 0, so `/gsd-ship` is unblocked. Phase 46 is executed 8/8 with both
  verification gaps closed; a re-verification should return 6/6.

- ~~Databricks integration recording hangs~~ RESOLVED (2026-06-24): the "hang" was paused Free-Edition workloads resuming on first compute (~20min); `connect` is instant. Recording now proceeds, but revealed two arrow-adbc Databricks DRIVER blockers in query execution — no bind params (breaks `.where()`) and no default catalog/schema (poolhouse drops them) — moved to **Phase 45** (now complete: DBX-01/02/03 verified, 7 Databricks query cassettes recorded + green). The introspection spike has also been run — the ADBC Databricks driver turned out to be present on the dev machine — so introspect() is implemented and cassette-backed (2026-06-25). No open Databricks blockers. See memory `project_databricks_adbc_query_blockers`.
- TYPE-05 Databricks-interval half and the VARIANT->JsonValue row are unmeasured: no repo recording has an interval, decimal or VARIANT Databricks column. One Databricks recording session closes all three (WINDOWS.md 7, 8).
- ~~semolina[pandas] alone does not enable fetch_df()~~ RESOLVED (2026-08-14): the user confirmed it was the same question already answered for `[arrowmodel]`, so `[pandas]` now composes `semolina[pyarrow]`. Verified in a real clean venv — `pip install .[pandas]` yields pandas PRESENT / pyarrow PRESENT, and `pip install .[polars]` still yields polars PRESENT / pyarrow absent. The polars asymmetry is deliberate and now pinned by `test_packaging_polars_extra_deliberately_does_not_reach_pyarrow`, so a later "make the extras consistent" tidy-up cannot quietly add a dependency `fetch_polars()` does not need. `installation.rst` and `arrow-output.rst` updated to match.

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
| ~~future requirement~~ | ~~`render_literal` Date/Decimal support (Databricks `.where()` raises `NotImplementedError`)~~ | **Shipped** — v0.7 Phase 48 (DBX-04); both dialect bodies widened for `date`/`datetime`/`Decimal` |

The audit-open report at v0.6 close showed only the 17 pending backlog todos (no open debug/quick-task/code-review/security artifacts); acknowledged as future-milestone candidates, not gaps.

Earlier carried forward at v0.5 close (2026-06-13): the same backlog todos (then 16); 14 stale historical quick-tasks (v0.1/v0.2 era) were archived to `.planning/milestones/quick-tasks-archive/` then, not deferred.

## Session Continuity

Last session: 2026-08-15T10:46:10.549Z
Stopped at: Completed 50-07-PLAN.md
Resume file: None
Next: Phase 49 (`.into(DTO)` Typed Results) — `/gsd-discuss-phase 49` or `/gsd-plan-phase 49`. Phase 50 (codegen'd DTOs) inherits Phase 48's D-01/D-02 open thread: `--check` probes the result schema, but codegen *generation* still reads warehouse metadata, and DTO-07/DTO-09 owns promoting it.

## Operator Next Steps

- ✅ v0.6 (Engine Architecture) shipped 2026-06-25: archived to `.planning/milestones/v0.6-ROADMAP.md`; tagged `v0.6`; merged via PR #33.
- 🚧 v0.7 (Async & Typed Results) roadmapped 2026-08-01: Phases 46-50, 26/26 requirements mapped. Phases 46, 47, 48 complete (18 plans); next is Phase 49 (`.into(DTO)` Typed Results).
- **One live Databricks session would close three v0.7 gaps at once** — `2026-08-12-record-databricks-interval-column.md` (unblocks TYPE-05, the only requirement Phase 48 left open), `2026-08-12-verify-databricks-zero-row-fallback.md`, and the Databricks decimal column noted in `47-TYPE-FIDELITY.md`'s evidence limitations. All three need a SQL warehouse plus the Foundry ADBC Databricks shared library on the recording machine.
- Phase 47's decision doc (`47-DECISIONS.md`) remains the specification for Phase 50 as well as the now-complete Phase 48 — treat it as normative, and note Phase 48's D-01/D-02: codegen *generation* still reads warehouse metadata, and promoting it to the probe is Phase 50's DTO-07/DTO-09 work.
- `.planning/todos/pending/2026-07-10-arrowmodel-result-serialization-integration.md` is the research input for Phase 49; retire it as that phase closes.
