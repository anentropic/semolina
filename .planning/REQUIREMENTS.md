# Requirements: Semolina v0.5

**Defined:** 2026-05-14
**Core Value:** A single, Pythonic query API that works identically across Snowflake, Databricks, and DuckDB semantic views, with typed models, IDE autocomplete, and backend-agnostic code.

## v0.5 Requirements

Requirements for the v0.5 release. Each maps to a roadmap phase. Phase numbering continues from v0.4.0 (last phase: 38), so v0.5 phases start at 39.

### Streaming Arrow Output

Closes `STREAM-01`/`STREAM-02` from the v0.4.0 Future Requirements list. Both methods mirror the `adbc_driver_manager` cursor interface — Semolina passes through to the underlying ADBC cursor, so backend differences are absorbed by ADBC.

- [x] **STREAM-01**: User can call `cursor.fetch_record_batch()` on `SemolinaCursor` to receive a `pyarrow.RecordBatchReader`, mirroring the same-named method on `adbc_driver_manager` cursors (passthrough to ADBC)
- [x] **STREAM-02**: User can iterate `for row in cursor:` on `SemolinaCursor` to receive `Row` objects via lazy nested iteration over the underlying `RecordBatchReader`, without full materialisation
- [x] **STREAM-03**: How-to guide under `docs/src/how-to/` covers streaming usage, when to stream vs. `fetch_arrow_table()`, and any backend-specific behaviour observed during implementation

### Codegen Enhancements

Closes `DKGEN-04` and `DKGEN-03` (renumbered to `DKGEN-05`) from the v0.4.0 Future Requirements list.

- [x] **DKGEN-04**: `semolina codegen --backend duckdb --database <path>` accepts filesystem paths (relative, `~`-expansion, absolute), opens read-only, runs `INSTALL/LOAD semantic_views` on the native codegen connection, and is verified against a fixture `.db` generated at test-collection time by a committed pytest fixture (`tests/conftest.py::duckdb_file_backed_db`)
- [x] **DKGEN-05**: `semolina codegen` emits `Metric`/`Dimension`/`Fact` field types inferred from semantic view metadata across all three backends. Every column resolves to a concrete role; an unrecognized role string raises `ValueError` rather than defaulting to `Dimension`. DuckDB sources role info from `DESCRIBE SEMANTIC VIEW`; Snowflake reads `kind` from `SHOW COLUMNS IN VIEW`; Databricks reads `is_measure` from `DESCRIBE TABLE EXTENDED ... AS JSON` (metric vs dimension; Databricks has no native Fact type)

### Cross-Phase Audit

Closes the v0.4.0 retrospective gap noting that `/gsd-audit-uat` was skipped — de facto integration verified by 924 tests and the doc build, but no structured cross-phase audit was run.

- [ ] **AUDIT-01**: `/gsd-audit-uat` runs across all v0.5 phases and produces a structured audit report committed under `.planning/`

## Future Requirements

Deferred to a later milestone.

### Streaming / Chunking

- **STREAM-04**: User-controllable batch size / chunk size for `fetch_record_batch()` (currently relies on ADBC defaults)

### Django Integration

- **DJANGO-01**: `django-semolina` helper package — settings-based pool registration, `AppConfig.ready()` hook, codegen management command. Scoped in `_notes/django-semolina-v0.1.md`. Will live in a separate repo, not this milestone.

## Out of Scope

Explicitly excluded from v0.5. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Async `SemolinaCursor` / ASGI hooks | Architectural change, not coupled to streaming output; evaluate independently |
| Streaming via a non-ADBC path (driver-direct) | The whole point of using ADBC is that streaming normalises across backends; revisit only if ADBC behaviour is unworkable |
| `cursor.to_pandas_chunks()` / `.to_polars_chunks()` helpers | Users can compose `pa.Table.from_batches(...)` over `fetch_record_batch()`; avoid surface creep until there's clear demand |
| MotherDuck (`md:`) URIs in codegen | Out of scope for this milestone — open a follow-up requirement if it surfaces |
| Attach-database codegen (`ATTACH 'other.db' AS x`) | Single-file scope for `DKGEN-04`; attach support is a separate feature |
| New extension points in Semolina for `django-semolina` | django-semolina v0.1 (as scoped in `_notes/`) needs nothing beyond existing public API |
| Recovery of phases 33–35 planning artifacts | Lost from git in commit `2933df2` during v0.4.0; the milestone audit is the authoritative record |

## Traceability

Which phases cover which requirements. Updated during roadmap creation, then again as phases land.

| Requirement | Phase | Status |
|-------------|-------|--------|
| STREAM-01 | Phase 39 | Complete |
| STREAM-02 | Phase 39 | Complete |
| STREAM-03 | Phase 40 | Complete |
| DKGEN-04 | Phase 41 | Complete |
| DKGEN-05 | Phase 42 | Complete |
| AUDIT-01 | Phase 43 | Pending |

**Coverage:**
- v0.5 requirements: 6 total
- Mapped to phases: 6
- Unmapped: 0

---
*Requirements defined: 2026-05-14*
*Last updated: 2026-06-09 — DKGEN-05 marked Complete at Phase 42 close; wording aligned with the rewritten ROADMAP criterion 4 (every column resolves to a concrete role; unrecognized role raises, no Field() fallback)*
*Last updated: 2026-06-09 — Phase 43 Plan 02 reconciled the STREAM-01/STREAM-02 list checkboxes (were stale `- [ ]`) to `- [x]` so the requirements list agrees with the Traceability table (both already `Complete` for Phase 39); the v0.5 milestone audit (`.planning/v0.5-MILESTONE-AUDIT.md`, status: passed) classed this as a doc/traceability finding, not a functional gap*
