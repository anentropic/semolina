# Roadmap: Semolina

## Milestones

- ✅ **v0.1 MVP** — Phases 1-7 (shipped 2026-02-16)
- ✅ **v0.2 Tooling & Documentation** — Phases 8-24 (shipped 2026-02-26)
- ✅ **v0.3 Arrow & Connection Layer** — Phases 25-32 (shipped 2026-04-18)
- ✅ **v0.4.0 DuckDB Backend & Arrow Output** — Phases 33-38 (shipped 2026-05-07)
- ✅ **v0.5 Streaming Arrow & Codegen Polish** — Phases 39-43 (shipped 2026-06-13)
- ✅ **v0.6 Engine Architecture** — Phases 44-45 (shipped 2026-06-25)
- 🚧 **v0.7 Async & Typed Results** — Phases 46-50 (in progress)

See `.planning/milestones/v0.1-ROADMAP.md` for v0.1 details.
See `.planning/milestones/v0.2-ROADMAP.md` for v0.2 details.
See `.planning/milestones/v0.3-ROADMAP.md` for v0.3 details.
See `.planning/milestones/v0.4.0-ROADMAP.md` for v0.4.0 details.
See `.planning/milestones/v0.5-ROADMAP.md` for v0.5 details.
See `.planning/milestones/v0.6-ROADMAP.md` for v0.6 details.

## Phases

<details>
<summary>✅ v0.1 MVP (Phases 1-7) — SHIPPED 2026-02-16</summary>

- [x] Phase 1: Model Foundation (1/1 plan) — completed 2026-02-15
- [x] Phase 2: Query Builder (3/3 plans) — completed 2026-02-15
- [x] Phase 3: SQL Generation & Mock Backend (5/5 plans) — completed 2026-02-15
- [x] Phase 4: Execution & Results (3/3 plans) — completed 2026-02-15
- [x] Phase 5: Snowflake Backend (2/2 plans) — completed 2026-02-15
- [x] Phase 6: Databricks Backend (2/2 plans) — completed 2026-02-16
- [x] Phase 7: Packaging (3/3 plans) — completed 2026-02-16

See `.planning/milestones/v0.1-ROADMAP.md` for phase details.

</details>

<details>
<summary>✅ v0.2 Tooling & Documentation (Phases 8-24) — SHIPPED 2026-02-26</summary>

- [x] Phase 8: Integration Testing (6/6 plans) — completed 2026-02-16
- [x] Phase 9: Codegen CLI (4/4 plans) — completed 2026-02-17
- [x] Phase 10: Documentation (4/4 plans) — completed 2026-02-17
- [x] Phase 10.1: Query Interface Refactor (9/8 plans) — completed 2026-02-19
- [x] Phase 11: CI & Example Updates (2/2 plans) — completed 2026-02-17
- [x] Phase 12: Warehouse Testing with Syrupy (4/4 plans) — completed 2026-02-19
- [x] Phase 13: Docs Accuracy & Verification (4/4 plans) — completed 2026-02-22
- [x] Phase 13.1: Filter Lookup & WHERE Compiler (5/5 plans) — completed 2026-02-22
- [x] Phase 14: Documentation Overhaul (5/5 plans) — completed 2026-02-22
- [x] Phase 15: Doc Accuracy & Tracking Cleanup (3/3 plans) — completed 2026-02-22
- [x] Phase 16: Doc Accuracy & Jaffle-Shop Fix (1/1 plan) — completed 2026-02-22
- [x] Phase 17: Nice Repr for Public API (1/1 plan) — completed 2026-02-23
- [x] Phase 18: Fix DDL Examples in Tutorial (1/1 plan) — completed 2026-02-23
- [x] Phase 19: Document Fact Field Type (1/1 plan) — completed 2026-02-24
- [x] Phase 20: Reverse Codegen (5/5 plans) — completed 2026-02-24
- [x] Phase 20.1: UAT Gap Fixes (5/5 plans) — completed 2026-02-25
- [x] Phase 21: Fix WHERE source= Bypass (1/1 plan) — completed 2026-02-25
- [x] Phase 22: Fix codegen.md Accuracy (1/1 plan) — completed 2026-02-25
- [x] Phase 23: API Export Cleanup (1/1 plan) — completed 2026-02-25
- [x] Phase 24: v0.2 Tech Debt Cleanup (4/4 plans) — completed 2026-02-26

See `.planning/milestones/v0.2-ROADMAP.md` for phase details.

</details>

<details>
<summary>✅ v0.3 Arrow & Connection Layer (Phases 25-32) — SHIPPED 2026-04-18</summary>

- [x] Phase 25: Pool Registry, Dialect Enum & MockPool (2/2 plans) — completed 2026-03-16
- [x] Phase 26: SemolinaCursor & Row Convenience (2/2 plans) — completed 2026-03-17
- [x] Phase 27: TOML Configuration & Real Pools (2/2 plans) — completed 2026-03-17
- [x] Phase 28: Query Shorthand (1/1 plan) — completed 2026-03-17
- [x] Phase 29: Documentation Update (3/3 plans) — completed 2026-03-17
- [x] Phase 30: Sphinx Shibuya Migration (4/4 plans) — completed 2026-04-09
- [x] Phase 31: Fix MockPool Doc Example (1/1 plan) — completed 2026-04-18
- [x] Phase 32: v0.3 Tech Debt Cleanup (1/1 plan) — completed 2026-04-18

See `.planning/milestones/v0.3-ROADMAP.md` for phase details.

</details>

<details>
<summary>✅ v0.4.0 DuckDB Backend & Arrow Output (Phases 33-38) — SHIPPED 2026-05-07</summary>

- [x] Phase 33: DuckDB Dialect + Packaging (2/2 plans) — completed 2026-04-19
- [x] Phase 34: Arrow Output (1/1 plan) — completed 2026-04-19
- [x] Phase 35: DuckDB Pool Wiring + MockPool Removal (3/3 plans) — completed 2026-04-20
- [x] Phase 36: DuckDB Codegen (2/2 plans) — completed 2026-04-26
- [x] Phase 37: Documentation (3/3 plans) — completed 2026-04-27
- [x] Phase 38: Packaging Fix + Test Cleanup (1/1 plan) — completed 2026-05-07

See `.planning/milestones/v0.4.0-ROADMAP.md` for phase details.

</details>

<details>
<summary>✅ v0.5 Streaming Arrow & Codegen Polish (Phases 39-43) — SHIPPED 2026-06-13</summary>

- [x] Phase 39: Streaming Arrow Output (2/2 plans) — completed 2026-05-14
- [x] Phase 40: Streaming How-To Guide (1/1 plan) — completed 2026-05-15
- [x] Phase 41: DuckDB File-Backed Codegen (3/3 plans) — completed 2026-06-09
- [x] Phase 42: Codegen Field-Type Inference (3/3 plans) — completed 2026-06-09
- [x] Phase 43: Cross-Phase UAT Audit (2/2 plans) — completed 2026-06-09

See `.planning/milestones/v0.5-ROADMAP.md` for phase details.

</details>

<details>
<summary>✅ v0.6 Engine Architecture (Phases 44-45) — SHIPPED 2026-06-25</summary>

- [x] Phase 44: Engine Owns the Pool (6/6 plans) — completed 2026-06-24
- [x] Phase 45: Databricks ADBC Query Support (3/3 plans) — completed 2026-06-25

`Engine` owns its ADBC pool + dialect (SQLAlchemy-style), serving both introspection
and execution; `create_engine(config | name)` + `register("name", engine)` replaced the
`(pool, dialect)` tuple registry; native connectors removed (ADBC-only); clean pre-1.0
break of the v0.5 connection API. Databricks query execution brought online over real
ADBC (literal-inlined WHERE, poolhouse DSN catalog/schema fix, first Databricks
cassettes), plus Databricks ADBC introspection implemented (Phase 44-04 fallback retired).

See `.planning/milestones/v0.6-ROADMAP.md` for phase details.

</details>

### 🚧 v0.7 Async & Typed Results (Phases 46-50) — IN PROGRESS

- [x] Phase 46: Async Query Surface (8 plans) — non-blocking `aexecute()` + async row streaming behind a `[async]` extra (completed 2026-08-11)
- [ ] Phase 47: Type Fidelity Probe & Decision Doc (4 plans) — empirical introspection-vs-probe comparison, then a committed type-mapping policy
- [ ] Phase 48: Type Map Implementation & Databricks Literals (plans TBD) — apply the policy across all three backends, add `--check`, widen `render_literal`
- [ ] Phase 49: `.into(DTO)` Typed Results (plans TBD) — Arrow → Pydantic v2 via arrowmodel, plus `fetch_df()`/`fetch_polars()`
- [ ] Phase 50: Codegen'd Typed DTOs (plans TBD) — generate DTO classes from a canonical query, typed by `adbc_execute_schema`

Milestone goal: give Semolina a non-blocking async query surface and an honest,
verified type story running from warehouse metadata through to Pydantic DTOs.

## Phase Details

### Phase 46: Async Query Surface

**Goal**: Users can run Semolina queries from an async web framework without blocking
the event loop, under either asyncio or Trio, with cancellation that actually reaches
the warehouse.
**Depends on**: Nothing in v0.7 — builds on the v0.6 Engine and adbc-poolhouse 1.6.2's
async stack (`create_async_pool` / `AsyncCursor` / `AsyncRecordBatchReader`)
**Requirements**: ASYNC-01, ASYNC-02, ASYNC-03, ASYNC-04, ASYNC-05, ASYNC-06, TOOL-01
**UI hint**: no — Semolina is a Python library with no frontend surface. The UI safety
gate token-sniffed `interface` out of the cited todo *filename* below and blocked
planning; this line is the documented authoritative override.
**Success Criteria** (what must be TRUE):

  1. User can `await engine.aexecute(query)` and `await Sales.query().metrics(...).aexecute()`
     from an async handler and get back the same result surface `.execute()` returns,
     while the event loop stays free to serve other requests (ASYNC-01, ASYNC-02)

  2. User can `async for row in result` and receive `Row` objects batch by batch —
     poolhouse fetches off-thread, Semolina maps — with no whole-table materialization
     (ASYNC-03)

  3. User cancelling an in-flight async query, whether by framework timeout or task
     cancellation, sees the warehouse query cancelled through `adbc_cancel` rather than
     left running (ASYNC-06)

  4. User installing `semolina[async]` gets the feature with `adbc-poolhouse[async]>=1.6.2`;
     a plain `pip install semolina` gains no new dependency, and an automated check (ruff
     `TID251`) fails the build if `asyncio` or `anyio` appears anywhere in the import graph
     of `src/semolina/` — a dynamic module lookup by string name is outside the rule's
     reach and is deliberately not defended against — with the async tests green under both
     asyncio and Trio (ASYNC-04, ASYNC-05).
     *(Floor amended from `>=1.5.0` on evidence, Phase 46 Plan 01: the `_resolve_tuning`
     helper that makes `create_async_pool` honour the config's own `pool_size` landed in
     adbc-poolhouse 1.6.0, so 1.5.x would silently build a five-connection pool for
     `DuckDBConfig(database=":memory:", pool_size=1)`.)*

  5. `.planning/config.json` carries `git.branching_strategy = "milestone"` again, the
     temporary `none` from v0.6 reverted (TOOL-01)
**Settled going in**: Posture A only — bare `async def` awaiting poolhouse primitives,
zero `asyncio.*` and no anyio import in Semolina. Posture B (fan-out/timeout sugar) is
out of scope. See `.planning/todos/pending/2026-02-23-async-query-interface-for-fastapi-and-async-frameworks.md`.
**Plans**: 8/8 plans executed

Plans:
**Wave 1**

- [x] 46-01-PLAN.md — poolhouse floor bump to 1.6.1, `[async]` extra, Trio dev dep, TID251 Posture A gate, requirement-floor amendments (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 46-02-PLAN.md — tracer: end-to-end async query and row streaming (`AsyncEngine`, `AsyncSemolinaCursor`, `create_async_engine`), then the full cursor surface and loop-freedom proof (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 46-03-PLAN.md — the D-16 cassette-replay spike: copied named cassettes replayed through the async path for Snowflake and Databricks (wave 3)
- [x] 46-04-PLAN.md — separate async engine registry, async-aware `reset()`, `_Query.aexecute()`, public exports (wave 3)
- [x] 46-05-PLAN.md — cancellation reaches the driver (real DuckDB), plus the structural asyncio-and-Trio matrix invariant (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 46-06-PLAN.md — async documentation across the web-API, streaming, connection-pools, and installation pages (wave 4)

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 46-07-PLAN.md — phase gate, then TOOL-01: restore `git.branching_strategy` to `milestone` as the final commit (wave 5)

**Gap closure** *(from 46-VERIFICATION.md gap #2; nothing in the phase gates it)*

- [x] 46-08-PLAN.md — the three unwritten cancellation sections: timeout and client disconnect in `web-api.rst`, mid-iteration cancellation in `streaming.rst`, then close WINDOWS.md entry 1 (wave 1)

### Phase 47: Type Fidelity Probe & Decision Doc

**Goal**: Settle, on evidence, how warehouse types map to Python — so every later typing
decision in this milestone rests on a measured answer rather than an assumption.
**Depends on**: Nothing — runs over existing Snowflake cassettes and the jaffle-shop
DuckDB database, so it can proceed alongside Phase 46
**Requirements**: TYPE-01, TYPE-02
**Success Criteria** (what must be TRUE):

  1. A maintainer can read a committed, per-backend comparison of introspection-time
     field types against query-time `adbc_execute_schema` result types for the same
     fields, produced by running against the existing Snowflake cassettes and the
     jaffle-shop DuckDB database (TYPE-01)

  2. The comparison names each concrete disagreement rather than a pass/fail summary —
     decimal precision widening under SUM, `AVG(int)` → double, COUNT → int64, and
     metric nullability on empty groups (TYPE-01)

  3. A committed decision doc states the Decimal policy for money columns, the
     metric-nullability stance, and which source of truth codegen uses (warehouse
     metadata vs `adbc_execute_schema` probe), each backed by the evidence that decided
     it (TYPE-02)

  4. The decision doc records, per driver, whether `adbc_execute_schema` is implemented
     or needs the zero-row fallback, so Phases 48 and 50 can build on a known answer
     instead of rediscovering it (TYPE-02)
**Gates**: Phase 48 (type-map implementation) and Phase 50 (codegen'd DTOs) both consume
this doc as their specification — neither can be planned honestly before it exists.
**Settled going in**: VARIANT maps to a `JsonValue` union, not `Any`. Untyped stays a
first-class fallback at every layer. Probes run at codegen and CI `--check` time, never
at runtime. See `.planning/todos/pending/2026-08-01-research-warehouse-type-fidelity-for-field-typing.md`.
**Plans**: 3/4 plans executed

Plans:
**Wave 1**

- [x] 47-01-PLAN.md — tracer: the whole evidence pipeline end to end on one DuckDB decimal metric — probe module, committed comparison artifact, `just type-fidelity`, canary and drift guards (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 47-02-PLAN.md — widen to every DuckDB field; the four named disagreements measured with their contrast cases, empty-group nullability, and the downstream Decimal consumers (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 47-03-PLAN.md — Snowflake and Databricks halves from copied cassettes, the driver-capability table from driver source, and the evidence-limitations section (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 47-04-PLAN.md — the normative decision doc, the user-facing explanation page, two follow-up todos, and the anti-circularity reviewer gate (wave 4)

### Phase 48: Type Map Implementation & Databricks Literals

**Goal**: Generated models carry the types the decision doc specifies, identically across
Snowflake, Databricks, and DuckDB, and Databricks filters accept the value types that
policy now makes reachable.
**Depends on**: Phase 47 (the decision doc is this phase's specification)
**Requirements**: TYPE-03, TYPE-04, TYPE-05, TYPE-06, TYPE-07, DBX-04
**Success Criteria** (what must be TRUE):

  1. User running codegen against an equivalent decimal-typed column on Snowflake,
     Databricks, and DuckDB gets the same Python annotation the decision doc specifies —
     the three backends no longer disagree about money (TYPE-03)

  2. User running codegen gets metric annotations whose nullability matches the decision
     doc's stance, visible in the emitted source (TYPE-04)

  3. User running codegen over DuckDB `DECIMAL`/`UUID`/`JSON`/`ENUM`/`TIMESTAMP_S|_MS|_NS`
     or Databricks `interval` gets a concrete Python type instead of a `TODO:`
     placeholder, and a VARIANT column yields a `JsonValue` union rather than `Any`
     (TYPE-05, TYPE-06)

  4. User can run a `--check` mode that reports whether a committed model's annotations
     still match the warehouse's current result schema, without fetching a single row
     (TYPE-07)

  5. User filtering a Databricks query on a `date`, `datetime`, or `Decimal` value gets
     rows back — `render_literal` inlines the value correctly instead of raising
     `NotImplementedError` (DBX-04)
**Note on DBX-04**: sequenced here because the Decimal policy from Phase 47 determines
what a `Decimal` filter value even means on Databricks; the `render_literal` widening
lands with the policy it serves.
**Plans**: TBD

### Phase 49: `.into(DTO)` Typed Results

**Goal**: Users can turn any query result — whole table, streaming batches, or async —
into Pydantic v2 DTOs, and hand results straight to pandas or polars.
**Depends on**: Phase 46 (the async cursor the `async for` DTO twin and the async
`fetch_df`/`fetch_polars` need)
**Requirements**: DTO-01, DTO-02, DTO-03, DTO-04, DTO-05, DTO-06, RESULT-01, RESULT-02
**Success Criteria** (what must be TRUE):

  1. User can call `.into(MyDTO)` on a result and get Pydantic v2 instances matched by
     column name — working the same against a fully typed, partially typed, or entirely
     untyped model, because conversion reads the Arrow result schema, not declared field
     types (DTO-01, DTO-04)

  2. User streaming a large result consumes DTOs per batch, from a sync iterator or an
     async one via `async for`, without materializing the whole table (DTO-02)

  3. User whose DTO does not match the result schema gets an error naming the offending
     field and both types, rather than a silently wrong-typed value (DTO-03)

  4. User can call `fetch_df()` for a `pandas.DataFrame` and `fetch_polars()` for a
     `polars.DataFrame` on both the sync and the async cursor; without the package
     installed the error names what to install instead of surfacing an internal
     `ImportError` traceback (RESULT-01, RESULT-02)

  5. User installing plain `semolina` gets neither pydantic nor the arrowmodel Rust
     extension — they arrive only with `semolina[arrowmodel]` — and the docs present
     `.into(DTO)` as the primary typed-result path with a worked BI-backend example
     covering both the whole-table and streaming forms (DTO-05, DTO-06)
**Settled going in**: DTOs derive from the query, not from the `SemanticView` model.
`.into(DTO)` needs no probe — the executed result already carries its Arrow schema.
arrowmodel level 2 (dynamic `create_model`) is out of scope. See
`.planning/todos/pending/2026-07-10-arrowmodel-result-serialization-integration.md`.
**Plans**: TBD

### Phase 50: Codegen'd Typed DTOs

**Goal**: Users can generate a DTO class from a canonical query and get real IDE types
and static checking on `.into(GeneratedDTO)` results.
**Depends on**: Phase 47 (typing policy), Phase 48 (type map + probe plumbing),
Phase 49 (the `.into(DTO)` surface the generated class is consumed by)
**Requirements**: DTO-07, DTO-08, DTO-09
**Success Criteria** (what must be TRUE):

  1. User can point codegen at a canonical query and get a typed DTO class whose
     annotations come from `adbc_execute_schema`, not from declared model field types
     (DTO-07)

  2. User gets IDE autocomplete and static type checking on `.into(GeneratedDTO)`
     results, and the generated file passes `basedpyright` strict with no ignores
     (DTO-08)

  3. User running DTO codegen against a driver that answers `NOT_IMPLEMENTED` for
     `adbc_execute_schema` still gets a generated class — codegen falls back to a
     zero-row execution and reports which path it used, instead of failing hard (DTO-09)
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-7 | v0.1 | 18/18 | Complete | 2026-02-16 |
| 8-24 | v0.2 | 66/66 | Complete | 2026-02-26 |
| 25-32 | v0.3 | 16/16 | Complete | 2026-04-18 |
| 33-38 | v0.4.0 | 12/12 | Complete | 2026-05-07 |
| 39-43 | v0.5 | 11/11 | Complete | 2026-06-13 |
| 44-45 | v0.6 | 9/9 | Complete | 2026-06-25 |
| 46. Async Query Surface | v0.7 | 8/8 | Complete    | 2026-08-11 |
| 47. Type Fidelity Probe & Decision Doc | v0.7 | 3/4 | In Progress|  |
| 48. Type Map Implementation & Databricks Literals | v0.7 | 0/? | Not started | - |
| 49. `.into(DTO)` Typed Results | v0.7 | 0/? | Not started | - |
| 50. Codegen'd Typed DTOs | v0.7 | 0/? | Not started | - |

---

*Roadmap updated 2026-08-01 — v0.7 (Async & Typed Results) roadmap created; Phases 46-50 mapped to all 26 v0.7 requirements*
