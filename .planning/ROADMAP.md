# Roadmap: Semolina

## Milestones

- ✅ **v0.1 MVP** — Phases 1-7 (shipped 2026-02-16)
- ✅ **v0.2 Tooling & Documentation** — Phases 8-24 (shipped 2026-02-26)
- ✅ **v0.3 Arrow & Connection Layer** — Phases 25-32 (shipped 2026-04-18)
- ✅ **v0.4.0 DuckDB Backend & Arrow Output** — Phases 33-38 (shipped 2026-05-07)
- ✅ **v0.5 Streaming Arrow & Codegen Polish** — Phases 39-43 (shipped 2026-06-13)
- ✅ **v0.6 Engine Architecture** — Phases 44-45 (shipped 2026-06-25)
- 🚧 **v0.7 Async & Typed Results** — Phases 46-57 (in progress)

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

### 🚧 v0.7 Async & Typed Results (Phases 46-57) — IN PROGRESS

- [x] Phase 46: Async Query Surface (8 plans) — non-blocking `aexecute()` + async row streaming behind a `[async]` extra (completed 2026-08-11)
- [x] Phase 47: Type Fidelity Probe & Decision Doc (4 plans) — empirical introspection-vs-probe comparison, then a committed type-mapping policy (completed 2026-08-12)
- [x] Phase 48: Type Map Implementation & Databricks Literals (6 plans) — apply the policy across all three backends, add `--check`, widen `render_literal` (completed 2026-08-13; TYPE-05's Databricks `interval` half open by accepted limitation)
- [ ] Phase 49: `.into(DTO)` Typed Results (plans TBD) — Arrow → Pydantic v2 via arrowmodel, plus `fetch_df()`/`fetch_polars()`
- [ ] Phase 50: Codegen'd Typed DTOs (8 plans) — generate DTO classes from a canonical query, typed by `adbc_execute_schema`
- [ ] Phase 51: Ship Safely — Release & CI Gates (4 plans) — release gating, PR trigger, docs in CI, `just test` parity
- [ ] Phase 52: Core Object Semantics (6 plans) — `Row`, equality, inheritance, `in_()`, cursor parity, DTO exactness
- [ ] Phase 53: Portable Result Column Names (5 plans) — alias every selected column to its Python field name on all backends
- [ ] Phase 54: Filter Semantics (5 plans) — `None`, LIKE escaping, `to_sql()` literals, metric-in-WHERE, introspect quoting
- [ ] Phase 55: Codegen Hardening (4 plans) — validity gate, credential redaction, exit-code parity, output plumbing
- [ ] Phase 56: Public Surface & Packaging (6 plans) — typed builder, public `Query`, `SemolinaError`, `SQLDialect`, `[cli]` extra, wheel contents
- [ ] Phase 57: Release v0.7.0 (5 plans) — test-suite structure, changelog page, release notes, the tag

Milestone goal: give Semolina a non-blocking async query surface and an honest,
verified type story running from warehouse metadata through to Pydantic DTOs.

Extended 2026-09-07: Phases 46-50 delivered that goal and the milestone was verified
complete on 2026-08-16. A pre-release codebase review
(`.planning/research/2026-09-06-CODEBASE-REVIEW.md`) then reproduced defects across the
query builder, the result objects, codegen and the release pipeline. Phases 51-57 close
them inside v0.7, so the first tagged release carries none of them. There is no v0.8.

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
**Plans**: 4/4 plans executed

Plans:
**Wave 1**

- [x] 47-01-PLAN.md — tracer: the whole evidence pipeline end to end on one DuckDB decimal metric — probe module, committed comparison artifact, `just type-fidelity`, canary and drift guards (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 47-02-PLAN.md — widen to every DuckDB field; the four named disagreements measured with their contrast cases, empty-group nullability, and the downstream Decimal consumers (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 47-03-PLAN.md — Snowflake and Databricks halves from copied cassettes, the driver-capability table from driver source, and the evidence-limitations section (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 47-04-PLAN.md — the normative decision doc, the user-facing explanation page, two follow-up todos, and the anti-circularity reviewer gate (wave 4)

### Phase 48: Type Map Implementation & Databricks Literals

**Goal**: Generated models carry the types the decision doc specifies, identically across
Snowflake, Databricks, and DuckDB, and Databricks filters accept the value types that
policy now makes reachable.
**Depends on**: Phase 47 (the decision doc is this phase's specification)
**Requirements**: TYPE-03, TYPE-04, TYPE-05, TYPE-06, TYPE-07, DBX-04
**Success Criteria** (what must be TRUE):

  1. User running codegen against a decimal-typed column gets an annotation naming what that
     backend's own driver returns — `decimal.Decimal` on Snowflake and DuckDB, `str` on
     Databricks — so no generated model claims a type its driver never produces (TYPE-03)
     — **reworded 2026-08-16.** Originally "gets the same Python annotation the decision doc
     specifies — the three backends no longer disagree about money", which a live Databricks
     probe falsified: its ADBC driver hands every decimal over as an Arrow string. The rule
     47-DECISIONS Decision 1 states never changed; uniformity was evidence that it held while
     all three drivers behaved alike, not the thing being promised. The criterion now states
     the promise directly. See the 2026-08-16 correction in `47-DECISIONS.md`.

  2. User running codegen gets metric annotations whose nullability matches the decision
     doc's stance, visible in the emitted source (TYPE-04)

  3. User running codegen over DuckDB `DECIMAL`/`UUID`/`JSON`/`ENUM`/`TIMESTAMP_S|_MS|_NS`
     or Databricks `interval` gets a concrete Python type instead of a `TODO:`
     placeholder, and a VARIANT column yields a `JsonValue` union rather than `Any`
     (TYPE-05, TYPE-06)
     — **met except for Databricks `interval`**, accepted at UAT (2026-08-13) as a
     documented limitation: no fixture, cassette, or recording in this repo contains an
     interval column, so the annotation cannot be measured and a guess was rejected. The
     override is recorded in `48-VERIFICATION.md`; TYPE-05 stays open in REQUIREMENTS.md
     and closing it needs
     `.planning/todos/pending/2026-08-12-record-databricks-interval-column.md`.

  4. User can run a `--check` mode that reports whether a committed model's annotations
     still match the warehouse's current result schema, without fetching a single row
     (TYPE-07)

  5. User filtering a Databricks query on a `date`, `datetime`, or `Decimal` value gets
     rows back — `render_literal` inlines the value correctly instead of raising
     `NotImplementedError` (DBX-04)
**Note on DBX-04**: sequenced here because the Decimal policy from Phase 47 determines
what a `Decimal` filter value even means on Databricks; the `render_literal` widening
lands with the policy it serves.
**Plans**: 6/6 plans executed

Plans:
**Wave 1**

- [x] 48-01-PLAN.md — Tracer: one DuckDB DECIMAL metric end to end, metric nullability, generalised import emission, raw-type comments, Phase 47 canary/artifact fallout, scope-fence gate (wave 1)
- [x] 48-02-PLAN.md — DBX-04: widen both `render_literal` bodies for `date`/`datetime`/`Decimal`, RED then GREEN (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 48-03-PLAN.md — Complete the type map: Snowflake `FIXED` and Databricks `decimal` to `decimal.Decimal`, DuckDB gaps + `HUGEINT`, Databricks `interval`, `semolina.JsonValue` for VARIANT (wave 2)
- [x] 48-04-PLAN.md — Promote `probe_schema` into `src/semolina/codegen/probe.py` and add `arrow_type_to_python`; re-read the Databricks driver's `ExecuteSchema` answer (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 48-05-PLAN.md — `semolina codegen --check`: AST model reader, per-field comparison against the probed result schema, `EXIT_ANNOTATION_DRIFT` (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 48-06-PLAN.md — Docs (`type-fidelity.rst` note rewrite, `codegen.rst` `--check` section and VARIANT correction) plus the phase gate (wave 4)

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

  5. User installing plain `semolina` gets neither arrowmodel nor its Rust extension —
     they arrive only with `semolina[arrowmodel]` — and the docs present
     `.into(DTO)` as the primary typed-result path with a worked BI-backend example
     covering both the whole-table and streaming forms (DTO-05, DTO-06)
**Settled going in**: DTOs derive from the query, not from the `SemanticView` model.
`.into(DTO)` needs no probe — the executed result already carries its Arrow schema.
arrowmodel level 2 (dynamic `create_model`) is out of scope. See
`.planning/todos/pending/2026-07-10-arrowmodel-result-serialization-integration.md`.
**Plans**: 7/7 plans executed

Plans:

- [x] 49-01-PLAN.md — Wave 1: four published extras + regenerated lock, then the tracer —
      one live DuckDB DECIMAL metric through the guard, the pre-check and `.into()`, and the
      same column declared `float` refused

- [x] 49-02-PLAN.md — Wave 2: sync `iter_into` checking at the call and producing lazily,
      plus the pre-check's full rule set on both sides of the confidence boundary

- [x] 49-03-PLAN.md — Wave 2: measure polars' Decimal behaviour for real (closing Phase 47's
      assumption A3) and correct `47-DECISIONS.md` in place, without rewriting it

- [x] 49-04-PLAN.md — Wave 2: the extras contract in the suite, and a clean-venv CI proof
      that a default install pulls no arrowmodel

- [x] 49-05-PLAN.md — Wave 3: sync `fetch_df` / `fetch_polars`, and a guard on each of the
      four Arrow/dataframe methods for exactly what it imports

- [x] 49-06-PLAN.md — Wave 3: the async twins, with `iter_into` provably neither a coroutine
      nor an async generator function, under both asyncio and Trio

- [x] 49-07-PLAN.md — Wave 4: the typed-results how-to with a worked BI-backend example, and
      the three existing pages pointed at the new methods

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
**Settled going in**: the generator derives every annotation through
`codegen/arrow_map.py::arrow_type_to_python` — it must not re-derive Arrow→Python types.
**A generated DTO must never annotate a decimal column `float`.** Phase 49 measured why:
against a `float` field, `validate=False` leaves a `Decimal` in a field declared `float`
(type is a lie), and `validate=True` coerces through IEEE-754 and silently loses precision
(measured: `12345678901234567890.99` → `1.2345678901234567e+19`, 890.99 gone). Phase 49's
pre-check refuses that DTO at `.into()`, which is the correct outcome for a hand-authored
mistake — but a *generated* DTO that produced it would make Semolina emit a class its own
result surface then rejects. `arrow_type_to_python` already maps every decimal (128/256, any
precision, scale 0 included) to `decimal.Decimal`, checked before `is_integer`/`is_floating`
so it cannot fall through, and `tests/unit/codegen/test_arrow_map.py` pins that. Phase 50
needs the end-to-end guard the unit test cannot give: a test that generates a DTO from a real
decimal-bearing schema and asserts the emitted annotation, then round-trips it through
`.into()` without raising.
**Plans**: 8/8 plans executed

Plans:
**Wave 1**

- [x] 50-01-PLAN.md — fix the Databricks metric result-column name, failing test first

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 50-02-PLAN.md — tracer: dotted path → projection strip → probe → render → `.into()` round trip

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 50-03-PLAN.md — per-backend aliases, unmapped types, derived imports, several DTOs per file
- [x] 50-04-PLAN.md — DTO-08: basedpyright strict with no suppressions, and `.into()`'s return type
- [x] 50-05-PLAN.md — DTO-09: forced `ExecuteSchema` refusal, route agreement, fatal probe failure

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 50-06-PLAN.md — the CLI surface, its exit codes, and the O-02 decision checkpoint

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 50-07-PLAN.md — the DTO codegen how-to page and the three surface-driven doc updates

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 50-08-PLAN.md — requirement statuses, broken windows, the routed R-04 decision, all gates

---

*Phases 51-57 below were added 2026-09-07 from the pre-release codebase review. Finding
numbers (A-, CI-, C-) refer to `.planning/research/2026-09-06-CODEBASE-REVIEW.md`.*

**Release context.** `0.6.0` is published on PyPI (2026-06-25) and no git tag exists — it
was published outside `release.yml`, which has therefore never run. Everything added in
Phases 46-50 is unreleased, so fixes to `.into()`, `codegen-dto`, `--check`, the async
cursor and `fetch_df`/`fetch_polars` need no deprecation path. Seven requirements marked
**[0.6-visible]** in REQUIREMENTS.md touch published surface: five are bug fixes, API-04
keeps the old name as an alias, and API-06 is the only one that can break a working
install. All seven earn a changelog entry in Phase 57.

**Working rule for every fix:** failing test first, then the fix, in separate commits
(CLAUDE.md).

### Phase 51: Ship Safely — Release & CI Gates

**Goal**: a tag cannot publish an untested or mis-versioned package, and a PR cannot merge
with a broken docs build or a silently weaker local test run. This lands first so every
later phase is protected by it.
**Depends on**: nothing.
**Requirements**: REL-01..08
**Success Criteria** (what must be TRUE):

  1. A `vX.Y.Z` tag with `X.Y.Z != semolina.__version__` fails release before `uv build`,
     naming both values (REL-01)
  2. `publish` runs only after CI is green on the tagged commit (REL-02)
  3. CI has a `pull_request` trigger; the coverage comment runs on PRs; `fail_under` is set
     just below today's 96% and the XML is uploaded (REL-03)
  4. `sphinx-build -W` runs in `ci.yml` on every push and PR (REL-04)
  5. `just test` and CI produce the same skip count; `MAINTAINER.md` says what to install
     (REL-05)
  6. The scope-fence resolves-here test skips with a message on a shallow clone outside CI
     (REL-06)
  7. Pre-commit ruff equals the locked ruff (REL-07); the matrix covers 3.11-3.14 or
     documents the gap; `.python-version` names a released interpreter (REL-08)

**Settled going in**: `release.yml` has never executed. Treat its first run as unproven —
Phase 57 tags a release candidate before `v0.7.0` if the gates cannot be exercised any
other way.

**Plans**: 0/4 plans executed

Plans:
**Wave 1** *(independent)*

- [ ] 51-01-PLAN.md — release gating: tag/version assertion, `needs` on CI, drop the needless `uv sync --dev` before `uv build`
- [ ] 51-02-PLAN.md — `pull_request` trigger, coverage `fail_under` + artifact, docs build job in `ci.yml`
- [ ] 51-03-PLAN.md — `just test` parity with CI, `MAINTAINER.md`, pre-commit ruff alignment, matrix and `.python-version`
- [ ] 51-04-PLAN.md — scope-fence shallow-clone guard (test-first: run the test under a `--depth 1` clone in a tmp dir and assert Skipped)

### Phase 52: Core Object Semantics

**Goal**: the objects a user holds — `Row`, fields, queries, cursors — behave like ordinary
Python objects and fail loudly on misuse.
**Depends on**: Phase 51.
**Requirements**: CORE-01..12
**Success Criteria** (what must be TRUE):

  1. `copy`, `deepcopy` and `pickle` round-trip a `Row`; `Row` is hashable, has `.get()`,
     and is a registered `Mapping` (CORE-01); method-name collisions are reachable via item
     access and documented (CORE-02)
  2. `Sales.cost in [Sales.revenue]` is `False`; `OrderTerm`s and queries for different
     fields are unequal; the tautological `test_query.py` assertions now fail on the wrong
     field (CORE-03)
  3. Model inheritance works or refuses clearly, per D1 (CORE-04)
  4. `in_("US")` raises `TypeError`; a generator works; placeholders always equal params
     (CORE-05); `Engine.execute(Query())` raises `ValueError` (CORE-06)
  5. Sync `close()` returns the connection even when `cursor.close()` raises and never masks
     the body's exception (CORE-07); iterate-then-fetch raises a named error on both cursors
     and the `acursor.py` docstring is corrected (CORE-08); every sync row method is
     pyarrow-guarded like the async twin (CORE-09)
  6. Duplicate selection raises in the builder and duplicate column names raise in `Row`
     (CORE-10); `timestamp` into `date` is refused by the fast-path check (CORE-11); dead
     `pool` arg gone and sync reader bookkeeping matches async (CORE-12)

**Settled going in**: `OrderTerm` and the query dataclass get `eq=False` plus an explicit
`__eq__` comparing field *identity*. `Field.__eq__` must keep returning a predicate — that
is the filter DSL, not a defect.

**Plans**: 0/6 plans executed

Plans:
**Wave 1** *(independent)*

- [ ] 52-01-PLAN.md — `Row`: pickle/copy, hash, `get`, `Mapping` registration, duplicate-column raise
- [ ] 52-02-PLAN.md — equality: `OrderTerm` and the query dataclass; rewrite the tautological tests
- [ ] 52-03-PLAN.md — `in_()` validation; `Engine.execute` validation; builder dedupe
- [ ] 52-04-PLAN.md — cursor parity: sync `close()` safety, mixed-consumption error, pyarrow guards on the row path, reader bookkeeping, docstring correction, `snowflake`/`databricks` extras decision
- [ ] 52-05-PLAN.md — DTO date/datetime exactness

**Wave 2** *(blocked on D1)*

- [ ] 52-06-PLAN.md — model inheritance (or the clear refusal), with `how-to/models.rst`

### Phase 53: Portable Result Column Names

**Goal**: `row.revenue` and a DTO field named `revenue` work identically on all three
backends. The largest usability finding in the review.
**Depends on**: Phase 52 — dedupe and duplicate-column handling must exist first, because
aliasing makes a duplicate name a hard error.
**Requirements**: ALIAS-01..05
**Success Criteria** (what must be TRUE):

  1. The same query yields keys `revenue` and `country` on all three backends, proven by
     re-recorded Snowflake/Databricks cassettes and live DuckDB (ALIAS-01)
  2. A plain-named DTO converts everywhere with no alias (ALIAS-02); `codegen-dto` output is
     backend-independent except for driver-type differences (ALIAS-03)
  3. README and the two how-to pages run unchanged on Snowflake; the column-key warning is
     gone (ALIAS-04)
  4. DuckDB no longer widens the projection silently (ALIAS-05)

**Design (recommended, confirmed at 53-01)**: the builder emits `AS "<python_field_name>"`
for every selected metric and dimension on Snowflake and Databricks; on DuckDB it wraps the
table function (`SELECT "revenue" AS "revenue", … FROM semantic_view(...)`) so a
`source=`-mapped field also returns under its Python name. One site:
`SQLBuilder._build_select_list`. `Dialect.metric_result_column_name` is retired from the
query path and kept only where introspection still needs the warehouse's own spelling.

**Settled going in**: no compatibility shim. `.into()` and `codegen-dto` are unreleased, so
no published DTO carries an `AGG("REVENUE")` alias. The `Row`-key change on Snowflake and
Databricks is `0.6.0`-visible and is a changelog entry, not a shim — `row.revenue` raises
there today, so the keys being fixed are ones no working code depends on.

**Plans**: 0/5 plans executed

Plans:
**Wave 1**

- [ ] 53-01-PLAN.md — design checkpoint (D2): aliasing strategy and DuckDB wrapping written to DECISIONS.md — **blocking human review**

**Wave 2** *(blocked on Wave 1)*

- [ ] 53-02-PLAN.md — builder: alias emission per dialect, test-first against `to_sql()` snapshots
- [ ] 53-03-PLAN.md — cursor/DTO consumption of the new keys; DuckDB wrapping and projection

**Wave 3** *(blocked on Wave 2)*

- [ ] 53-04-PLAN.md — re-record Snowflake and Databricks cassettes (credentialed, local); record a metric-in-WHERE and a Snowflake introspection in the same session (feeds 54-03 and 57-02)
- [ ] 53-05-PLAN.md — `codegen-dto` drops backend aliases; README, tutorials and how-to pages updated

### Phase 54: Filter Semantics and SQL Edge Cases

**Goal**: every predicate the DSL can express compiles to SQL that means what the Python
reads as, or raises.
**Depends on**: 53-04 for the metric-in-WHERE recording (54-03 only).
**Requirements**: FILT-01..08
**Success Criteria** (what must be TRUE):

  1. `== None` → `IS NULL`, `!= None` → `IS NOT NULL`, `between(x, None)` raises, per D3
     (FILT-01)
  2. Prefix/suffix/iexact lookups escape wildcards with an `ESCAPE` clause per dialect;
     `like`/`ilike` pass through and say so; Databricks backslash is tested (FILT-02)
  3. `to_sql()` renders valid SQL for apostrophes, dates, decimals and `None` (FILT-03)
  4. Metric-in-WHERE is `HAVING` or rejected, per D4, and the tutorial is true (FILT-04)
  5. `introspect()` quotes names on all engines and DuckDB honours the schema prefix
     (FILT-05); dotted pre-quoted segments raise and pre-quoted segments are escaped
     (FILT-06); `?` in identifiers works on Databricks (FILT-07); error mapping is complete
     (FILT-08)

**Plans**: 0/5 plans executed

Plans:
**Wave 1** *(independent)*

- [ ] 54-01-PLAN.md — `None` handling (D3) and `between` validation
- [ ] 54-02-PLAN.md — LIKE escaping with `ESCAPE` per dialect; docstring truth
- [ ] 54-04-PLAN.md — `to_sql()` through `render_literal`; narrow the how-to warning
- [ ] 54-05-PLAN.md — introspect quoting and error mapping; pre-quoted segments; `?` in identifiers

**Wave 2** *(blocked on 53-04)*

- [ ] 54-03-PLAN.md — metric-in-WHERE (D4): `HAVING` or reject; DuckDB projection resolved the same way; tutorial updated

### Phase 55: Codegen Hardening

**Goal**: `semolina codegen` cannot emit a file that does not parse, cannot print a secret,
and behaves like `codegen-dto` on errors and output.
**Depends on**: nothing — runs alongside Phases 52-54.
**Requirements**: GEN-01..10
**Success Criteria** (what must be TRUE):

  1. Invalid identifiers, case collisions and leading-digit view names exit non-zero naming
     the offender, and rendered source is `ast.parse`d before emission on both commands
     (GEN-01); a ruff failure is loud (GEN-02)
  2. A config `ValidationError` never prints `input_value`; a test asserts the password is
     absent from stderr (GEN-03)
  3. Both commands share one exception-to-exit table covering missing extras, unmapped ADBC
     errors and dotted-backend constructor failures (GEN-04)
  4. `> models.py` and `--output` are byte-identical and pass `ruff format --check`
     (GEN-05); `codegen` has atomic `--output` and `--check` drops the `--model` workaround
     (GEN-06); output is cwd-independent (GEN-07)
  5. `~` expands before joining and env overrides are announced (GEN-08); `--check` handles
     untyped `Metric()` and reports probe fallback via exit code (GEN-09); dead
     `cli/utils.py` code is gone (GEN-10)

**Settled going in**: the DTO path already has the guards the model path lacks
(`is_valid_class_name`, `_check_dto_field_name`, duplicate detection). Reuse them rather
than writing a second implementation.

**Plans**: 0/4 plans executed

Plans:
**Wave 1** *(independent)*

- [ ] 55-01-PLAN.md — validity gate: name validation in `_build_model_context`, `ast.parse` before emit, loud ruff failure — test-first with a mocked engine returning `CLASS` and `"ORDER DATE"`
- [ ] 55-02-PLAN.md — credential redaction; shared exception-to-exit table
- [ ] 55-03-PLAN.md — output plumbing: `nl=False`, `--output`, atomic write, cwd-independent formatting

**Wave 2** *(blocked on Wave 1)*

- [ ] 55-04-PLAN.md — config paths and precedence; `--check` fixes; dead code removal; `how-to/codegen.rst` for `--output`

### Phase 56: Public Surface & Packaging

**Goal**: the types, names and dependencies a user sees match a strongly typed library for
backend services. Last chance to make these changes cheaply — after `v0.7.0` they cost a
deprecation cycle.
**Depends on**: Phase 53 (the aliasing decision settles what `Query` and the cursor return).
**Requirements**: API-01..10 (API-11 lands in Phase 57)
**Success Criteria** (what must be TRUE):

  1. Builder methods are typed and a pyright negative-test file proves misuse is reported
     (API-01)
  2. `Query`, `Field`, `Engine`, `AsyncEngine` and the predicate composites are exported;
     every public module has `__all__` (API-02)
  3. `SemolinaError` exists and every Semolina error derives from it, per D5 (API-03)
  4. One thing is called `Dialect`, with the old name aliased for a release; `to_sql()`
     defaults to the registered engine's dialect when `.using()` names one, per D7
     (API-04); sync/async naming has a stated rule (API-05)
  5. `[cli]` extra per D6; a base install imports no typer/rich/jinja2 and the console
     script prints the hint (API-06); `import semolina` no longer imports `config` eagerly
     (API-07); `conftest.py` and `testing/` are out of the wheel with a smoke assertion
     (API-08)
  6. Dead type-ignores removed and `reportUnnecessaryTypeIgnoreComment` on (API-09);
     registry locked with a concurrency test (API-10)

**Plans**: 0/6 plans executed

Plans:
**Wave 1**

- [ ] 56-01-PLAN.md — decision checkpoint (D5, D6, D7): `SemolinaError`, `[cli]` extra, `Dialect` rename — **blocking human review**, because D6 breaks a working `0.6.0` CLI install

**Wave 2** *(blocked on Wave 1; plans independent of each other)*

- [ ] 56-02-PLAN.md — builder typing + pyright negative tests; `Query` rename and exports; `__all__`
- [ ] 56-03-PLAN.md — exception hierarchy; `get_engine` error type; `web-api.rst`
- [ ] 56-04-PLAN.md — packaging: `[cli]` extra, lazy `config` import, wheel contents, smoke steps
- [ ] 56-05-PLAN.md — `SQLDialect` rename and `to_sql()` default; registry lock; type-ignore cleanup; naming rule
- [ ] 56-06-PLAN.md — full-surface sweep: every doc page and example against the renamed, re-typed, re-keyed API

### Phase 57: Release v0.7.0

**Goal**: the suite proves what it claims, the changelog tells a `0.6.0` user what changed,
and v0.7.0 ships through the gates Phase 51 built.
**Depends on**: Phases 51-56; 53-04 for the cassettes.
**Requirements**: TEST-01..06, API-11
**Success Criteria** (what must be TRUE):

  1. The `test_engines.py` abstract-method tests fail if a method stops being abstract and
     the `to_sql` test is gone (TEST-01); Snowflake introspection has a cassette and copied
     cassettes are marked or removed (TEST-02)
  2. The type-fidelity artifact lives under `tests/`, a pin bump cannot fail the byte
     comparison, and the duckdb-bump PR triggers CI (TEST-03)
  3. Timing tests run outside `-n auto` or carry reasoned margins, and the extension install
     retries once (TEST-04); `semolina-jaffle-shop/` is type-checked (TEST-05); root markers
     are used or removed (TEST-06)
  4. The docs site has the `/changelog/` page `pyproject.toml` already advertises, and the
     0.7.0 notes list every **[0.6-visible]** change (API-11)
  5. `v0.7.0` is tagged, CI is green on that commit, the release workflow runs for the first
     time in the project's history, and `pip install semolina==0.7.0` serves the wheel

**Plans**: 0/5 plans executed

Plans:
**Wave 1** *(independent)*

- [ ] 57-01-PLAN.md — vacuous tests fixed; marker cleanup; jaffle-shop typecheck job
- [ ] 57-02-PLAN.md — type-fidelity artifact relocation; bump-PR CI trigger; cassette marking
- [ ] 57-03-PLAN.md — timing-test isolation and install retry

**Wave 2** *(blocked on Wave 1)*

- [ ] 57-04-PLAN.md — changelog page on the docs site; 0.7.0 release notes covering the six `0.6.0`-visible changes
- [ ] 57-05-PLAN.md — version bump to `0.7.0`, tag, and the first real run of `release.yml`


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
| 47. Type Fidelity Probe & Decision Doc | v0.7 | 4/4 | Complete    | 2026-08-12 |
| 48. Type Map Implementation & Databricks Literals | v0.7 | 6/6 | Complete    | 2026-08-13 |
| 49. `.into(DTO)` Typed Results | v0.7 | 7/7 | Complete    | 2026-08-14 |
| 50. Codegen'd Typed DTOs | v0.7 | 8/8 | Complete    | 2026-08-16 |
| 51. Ship Safely — Release & CI Gates | v0.7 | 0/4 | Not started | |
| 52. Core Object Semantics | v0.7 | 0/6 | Not started | |
| 53. Portable Result Column Names | v0.7 | 0/5 | Not started | |
| 54. Filter Semantics | v0.7 | 0/5 | Not started | |
| 55. Codegen Hardening | v0.7 | 0/4 | Not started | |
| 56. Public Surface & Packaging | v0.7 | 0/6 | Not started | |
| 57. Release v0.7.0 | v0.7 | 0/5 | Not started | |

---

*Roadmap updated 2026-09-07 — v0.7 extended with a pre-release hardening pass; Phases 51-57 mapped to 60 new requirements, for 86 across Phases 46-57. Phases 49 and 50 corrected to Complete, matching STATE.md.*
