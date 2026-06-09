# Roadmap: Semolina

## Milestones

- ✅ **v0.1 MVP** — Phases 1-7 (shipped 2026-02-16)
- ✅ **v0.2 Tooling & Documentation** — Phases 8-24 (shipped 2026-02-26)
- ✅ **v0.3 Arrow & Connection Layer** — Phases 25-32 (shipped 2026-04-18)
- ✅ **v0.4.0 DuckDB Backend & Arrow Output** — Phases 33-38 (shipped 2026-05-07)
- 🚧 **v0.5 Streaming Arrow & Codegen Polish** — Phases 39-43 (in progress)

See `.planning/milestones/v0.1-ROADMAP.md` for v0.1 details.
See `.planning/milestones/v0.2-ROADMAP.md` for v0.2 details.
See `.planning/milestones/v0.3-ROADMAP.md` for v0.3 details.
See `.planning/milestones/v0.4.0-ROADMAP.md` for v0.4.0 details.

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

### v0.5 Streaming Arrow & Codegen Polish (Phases 39-43)

- [x] **Phase 39: Streaming Arrow Output** — `fetch_record_batch()` + lazy `__iter__` on `SemolinaCursor` (completed 2026-05-14)
- [x] **Phase 40: Streaming How-To Guide** — Document streaming usage and when to choose it (completed 2026-05-15)
- [x] **Phase 41: DuckDB File-Backed Codegen** — Codegen against `.db` filesystem paths (completed 2026-06-09)
- [x] **Phase 42: Codegen Field-Type Inference** — `Metric`/`Dimension`/`Fact` inference across all three backends (completed 2026-06-09)
- [ ] **Phase 43: Cross-Phase UAT Audit** — `/gsd-audit-uat` structured report for v0.5

## Phase Details

### Phase 39: Streaming Arrow Output
**Goal**: Users can stream Arrow record batches and iterate rows lazily without full materialisation.
**Depends on**: Phase 38 (v0.4.0 `fetch_arrow_table()` and SemolinaCursor surface)
**Requirements**: STREAM-01, STREAM-02
**Success Criteria** (what must be TRUE):
  1. User calls `cursor.fetch_record_batch()` on a `SemolinaCursor` and receives a `pyarrow.RecordBatchReader` that streams batches from the underlying ADBC cursor without buffering the full result.
  2. User writes `for row in cursor:` and receives `Row` objects one at a time, with batches consumed lazily from the `RecordBatchReader` (verifiable via memory profile or batch-pull instrumentation in tests).
  3. Cursor iteration and `fetch_record_batch()` work across all three backends (Snowflake, Databricks, DuckDB) via ADBC passthrough — no backend-specific code paths in Semolina.
  4. Requirement names in REQUIREMENTS.md match the shipped API surface (lesson from v0.4.0 `to_arrow()` → `fetch_arrow_table()` echo); requirement text and shipped method names are reconciled at phase close.
  5. REQUIREMENTS.md Traceability table is updated when this phase lands (not deferred to milestone archive).
**Plans**: 2 plans
- [ ] 39-01-PLAN.md — Implement `fetch_record_batch` + lazy `__iter__`/`__next__` on `SemolinaCursor`; fix `fetch_arrow_table` typing; add unit tests with laziness + edge cases (Wave 1)
- [ ] 39-02-PLAN.md — Cross-backend integration smoke (gated by `--snapshot-update`) + REQUIREMENTS.md traceability close-out (Wave 2)

### Phase 40: Streaming How-To Guide
**Goal**: Users find clear guidance on streaming vs. materialised Arrow output in the docs.
**Depends on**: Phase 39
**Requirements**: STREAM-03
**Success Criteria** (what must be TRUE):
  1. A new how-to page under `docs/src/how-to/` covers `fetch_record_batch()` and `for row in cursor:` with runnable example snippets.
  2. The page articulates when to stream vs. when `fetch_arrow_table()` is preferable (memory, latency, downstream consumer pattern), with at least one explicit decision rule.
  3. Any backend-specific behaviour observed during Phase 39 implementation (batch sizes, end-of-stream semantics) is documented under a "Backend notes" section.
  4. Page passes the semolina-docs-author skill workflow (Diataxis how-to classification + humanizer pass) and the Sphinx `-W` build succeeds.
  5. REQUIREMENTS.md Traceability for STREAM-03 is updated on close.
**Plans**: 1 plan
- [x] 40-01-PLAN.md — Create streaming how-to page + toctree wiring + reverse See-also link from arrow-output + Sphinx -W build gate + humanizer pass + STREAM-03 traceability close (Wave 1)
**UI hint**: no

### Phase 41: DuckDB File-Backed Codegen
**Goal**: Users can run `semolina codegen` against a DuckDB `.db` file on disk.
**Depends on**: Phase 38 (v0.4.0 in-memory DuckDB codegen via Phase 36)
**Requirements**: DKGEN-04
**Success Criteria** (what must be TRUE):
  1. `semolina codegen --backend duckdb --database <path>` accepts relative paths, absolute paths, and `~`-expansion, opens the database read-only, and generates the same model classes as the in-memory equivalent.
  2. The codegen connection runs `INSTALL semantic_views FROM community; LOAD semantic_views` on the native (non-ADBC) DuckDB connection used for introspection.
  3. A fixture `.db` file is committed under `tests/` and exercised by a test asserting end-to-end codegen output against that fixture.
  4. CI verifies the `[duckdb]` extra still installs cleanly (packaging smoke test — lesson from v0.4.0 Phase 38).
  5. REQUIREMENTS.md Traceability for DKGEN-04 is updated on close; the existing DuckDB codegen how-to is amended (not a new doc page).
**Plans**: 3 plans
- [x] 41-01-PLAN.md — Wave 0 test infrastructure: fixture + test stubs + loosen existing SQL-sequence assertion (Wave 0)
- [x] 41-02-PLAN.md — Implementation: `_normalize_database_path` helper + INSTALL hook + packaging-smoke CI job (Wave 1)
- [x] 41-03-PLAN.md — E2E snapshot capture + how-to amendment + REQUIREMENTS.md DKGEN-04 close (Wave 2)

### Phase 42: Codegen Field-Type Inference
**Goal**: Codegen emits the correct `Metric`/`Dimension`/`Fact` field type for every column across all three backends.
**Depends on**: Phase 41 (DuckDB codegen surface stabilised)
**Requirements**: DKGEN-05
**Success Criteria** (what must be TRUE):
  1. DuckDB codegen reads role info from `DESCRIBE SEMANTIC VIEW` and emits `Metric()`, `Dimension()`, or `Fact()` per column (no `Field()` placeholders for known roles).
  2. Snowflake codegen emits the correct field type using a Snowflake-native metadata source (specific query path determined during phase planning) — verified against a snapshot fixture in the test suite.
  3. Databricks codegen emits the correct field type using a Databricks-native metadata source — verified against a snapshot fixture in the test suite.
  4. Every column resolves to a concrete role (`Metric`/`Dimension`/`Fact`) across all three backends; an unrecognized role string raises `ValueError` (fails loudly) rather than silently defaulting to `Dimension`; behaviour is documented in the codegen how-to.
  5. REQUIREMENTS.md Traceability for DKGEN-05 is updated on close, with the metadata-query implementation path recorded in PROJECT.md Key Decisions.
**Plans**: 3 plans
- [x] 42-01-PLAN.md — Wave 0 failing tests: strict-raise RED unit test + offline Snowflake & Databricks codegen snapshot tests (Wave 0)
- [x] 42-02-PLAN.md — Make `_field_class_for` strict (raise on unrecognized role); DuckDB snapshot stays byte-identical (Wave 1)
- [x] 42-03-PLAN.md — Amend codegen how-to + rewrite criterion 4/DKGEN-05 + close DKGEN-05 + log decisions in PROJECT.md (Wave 2)

### Phase 43: Cross-Phase UAT Audit
**Goal**: A structured cross-phase audit confirms v0.5 ships as designed and closes the v0.4.0 retrospective gap.
**Depends on**: Phases 39, 40, 41, 42
**Requirements**: AUDIT-01
**Success Criteria** (what must be TRUE):
  1. `/gsd-audit-uat` runs across Phases 39–42 and produces an audit report committed under `.planning/milestones/v0.5-UAT-AUDIT.md` (or equivalent path).
  2. The audit verifies each v0.5 success criterion is observably true against the shipped surface (not just "tests pass").
  3. Any gaps surfaced by the audit are either closed via follow-up plans within Phase 43 or explicitly deferred to v0.6 with a note in REQUIREMENTS.md Future Requirements.
  4. The audit confirms REQUIREMENTS.md Traceability is fully populated and requirement text matches shipped API names (lessons baked in from v0.4.0).
  5. Final audit verdict is `PASSED` before milestone archival.
**Plans**: 2 plans
- [ ] 43-01-PLAN.md — Run audit-uat baseline + SC-by-SC verification of Phases 39-42 against the shipped surface; write `.planning/v0.5-MILESTONE-AUDIT.md` with a passed/gaps verdict (Wave 1)
- [ ] 43-02-PLAN.md — Reconcile STREAM-01/02 checkbox-vs-table defect + fix ROADMAP SC1 wording; close AUDIT-01 gated on the PASSED verdict (Wave 2)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-7 | v0.1 | 18/18 | Complete | 2026-02-16 |
| 8-24 | v0.2 | 66/66 | Complete | 2026-02-26 |
| 25-32 | v0.3 | 16/16 | Complete | 2026-04-18 |
| 33-38 | v0.4.0 | 12/12 | Complete | 2026-05-07 |
| 39 | v0.5 | 2/2 | Complete    | 2026-05-14 |
| 40 | v0.5 | 1/1 | Complete    | 2026-05-15 |
| 41 | v0.5 | 3/3 | Complete    | 2026-06-09 |
| 42 | v0.5 | 3/3 | Complete    | 2026-06-09 |
| 43 | v0.5 | 0/2 | Planned     | - |

---

*Roadmap updated 2026-06-09 — Phase 43 planned (2 plans across 2 waves)*
