# Roadmap: Semolina

## Milestones

- ✅ **v0.1 MVP** — Phases 1-7 (shipped 2026-02-16)
- ✅ **v0.2 Tooling & Documentation** — Phases 8-24 (shipped 2026-02-26)
- 🚧 **v0.3 Arrow & Connection Layer** — Phases 25-29 (in progress)

See `.planning/milestones/v0.1-ROADMAP.md` for v0.1 details.
See `.planning/milestones/v0.2-ROADMAP.md` for v0.2 details.

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

### 🚧 v0.3 Arrow & Connection Layer (In Progress)

**Milestone Goal:** Replace the hand-rolled Engine ABC with adbc-poolhouse connection pools, evolve `.execute()` to return a `SemolinaCursor` with Arrow-native fetch methods, add TOML-based configuration, and provide query shorthand arguments.

**Phase Numbering:**
- Integer phases (25, 26, 27, 28): Planned milestone work
- Decimal phases (e.g. 25.1): Urgent insertions if needed

- [ ] **Phase 25: Pool Registry, Dialect Enum & MockPool** - Replace Engine registry with pool+dialect registry; MockPool enables testing without warehouse
- [ ] **Phase 26: SemolinaCursor & Row Convenience** - `.execute()` returns SemolinaCursor with Arrow fetch + Row convenience methods
- [ ] **Phase 27: TOML Configuration & Real Pools** - `.semolina.toml` config loading into adbc-poolhouse config classes; `pool_from_config()` helper
- [ ] **Phase 28: Query Shorthand** - `query(metrics=..., dimensions=...)` keyword args additive with builder methods
- [ ] **Phase 29: Documentation Update** - Update tutorials, how-to guides, and API reference for v0.3 API changes

## Phase Details

### Phase 25: Pool Registry, Dialect Enum & MockPool
**Goal**: Users can register connection pools with dialect tags and test queries without a warehouse using MockPool
**Depends on**: Nothing (first v0.3 phase; builds on v0.2 codebase)
**Requirements**: CONN-01, CONN-02, CONN-03, CONN-04
**Success Criteria** (what must be TRUE):
  1. User can call `register("default", pool, dialect="snowflake")` and the pool is stored with its dialect
  2. User can call `.using("name")` on a query and it resolves to the named pool at execute time
  3. Dialect enum (`Dialect.SNOWFLAKE`, `Dialect.DATABRICKS`, `Dialect.MOCK`) controls SQL generation (AGG vs MEASURE, placeholder style)
  4. User can create a `MockPool` with in-memory Arrow data, register it, and execute queries that return correct results without any warehouse connection
**Plans**: 2 plans

Plans:
- [ ] 25-01-PLAN.md — Dialect StrEnum, resolve_dialect(), registry rewrite for pool+dialect storage
- [ ] 25-02-PLAN.md — MockPool/MockConnection/MockCursor, wire _Query.execute() to pool registry

### Phase 26: SemolinaCursor & Row Convenience
**Goal**: `.execute()` returns a SemolinaCursor providing both Arrow-native fetch methods and Row convenience methods
**Depends on**: Phase 25 (MockPool needed for testing)
**Requirements**: CURS-01, CURS-02, CURS-03, CURS-04, CURS-05
**Success Criteria** (what must be TRUE):
  1. `.execute()` returns a `SemolinaCursor` that wraps the ADBC cursor (subclass or delegation)
  2. User can call `cursor.fetchall_rows()` and receive a `list[Row]` with all result rows
  3. User can call `cursor.fetchmany_rows(size)` and receive a `list[Row]` of at most `size` rows
  4. User can call `cursor.fetchone_row()` and receive `Row | None` for single-row access
  5. Row objects support both attribute access (`row.revenue`) and dict-style access (`row["revenue"]`)
**Plans**: TBD

Plans:
- [ ] 26-01: TBD
- [ ] 26-02: TBD

### Phase 27: TOML Configuration & Real Pools
**Goal**: Users can define connections in `.semolina.toml` and create pools from config without manual pool construction
**Depends on**: Phase 25 (pool registry must exist), Phase 26 (cursor must work for integration testing)
**Requirements**: CONF-01, CONF-02, CONF-03
**Success Criteria** (what must be TRUE):
  1. `.semolina.toml` connection sections contain a backend sub-section (`[connections.default.snowflake]` or `[connections.default.databricks]`) that determines which adbc-poolhouse config class to use
  2. TOML connection settings load into the correct adbc-poolhouse config class (SnowflakeConfig or DatabricksConfig) via pydantic-settings TomlSettingsSource
  3. User can call `pool_from_config(connection="conn1")` and receive a live adbc-poolhouse pool ready for `register()`, defaulting to `.semolina.toml` path
**Plans**: TBD

Plans:
- [ ] 27-01: TBD
- [ ] 27-02: TBD

### Phase 28: Query Shorthand
**Goal**: Users can pass metrics and dimensions directly to `query()` for concise one-liner queries
**Depends on**: Phase 26 (query execution path must be working)
**Requirements**: QAPI-01, QAPI-02
**Success Criteria** (what must be TRUE):
  1. User can write `Sales.query(metrics=[Sales.revenue], dimensions=[Sales.region])` and it behaves identically to `Sales.query().metrics(Sales.revenue).dimensions(Sales.region)`
  2. Builder methods (`.metrics()`, `.dimensions()`) are additive with args passed to `query()` -- calling `.metrics(Sales.cost)` after `query(metrics=[Sales.revenue])` selects both revenue and cost
**Plans**: TBD

Plans:
- [ ] 28-01: TBD

### Phase 29: Documentation Update
**Goal**: All user-facing documentation reflects the v0.3 API (pool registration, SemolinaCursor, TOML config, query shorthand)
**Depends on**: Phase 25, 26, 27, 28 (all API changes must be finalized)
**Requirements**: DOCS-01, DOCS-02, DOCS-03, DOCS-04
**Note**: MockPool is for internal tests; not documented beyond auto-generated API reference.
**Success Criteria** (what must be TRUE):
  1. Tutorials show pool registration and SemolinaCursor usage (not Engine-based API)
  2. How-to guides cover .semolina.toml connection config and pool_from_config()
  3. How-to guides cover Arrow fetch methods and Row convenience methods
  4. API reference auto-generates for SemolinaCursor, Dialect, pool_from_config, updated register()
**Plans**: TBD

Plans:
- [ ] 29-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 25 -> 26 -> 27 -> 28 -> 29

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-7 | v0.1 | 18/18 | Complete | 2026-02-16 |
| 8-24 | v0.2 | 66/66 | Complete | 2026-02-26 |
| 25. Pool Registry, Dialect & MockPool | v0.3 | 0/2 | Planned | - |
| 26. SemolinaCursor & Row | v0.3 | 0/TBD | Not started | - |
| 27. TOML Config & Real Pools | v0.3 | 0/TBD | Not started | - |
| 28. Query Shorthand | v0.3 | 0/TBD | Not started | - |
| 29. Documentation Update | v0.3 | 0/TBD | Not started | - |

---

*v0.3 roadmap created 2026-03-16 -- See .planning/STATE.md for current position*
