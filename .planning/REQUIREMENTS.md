# Requirements: Semolina

**Defined:** 2026-03-16
**Core Value:** A single, Pythonic query API that works identically across Snowflake and Databricks semantic views, with typed models, IDE autocomplete, and backend-agnostic code.

## v0.3 Requirements

Requirements for Arrow & Connection Layer milestone. Each maps to roadmap phases.

### Connection Layer

- [ ] **CONN-01**: User can register a pool with a dialect tag via `register("default", pool, dialect="snowflake")`
- [ ] **CONN-02**: User can select a registered pool via `.using("name")` on queries
- [ ] **CONN-03**: Dialect enum determines SQL generation (AGG vs MEASURE, placeholder style)
- [ ] **CONN-04**: User can test without a warehouse using MockPool with in-memory Arrow data

### Cursor & Results

- [ ] **CURS-01**: `.execute()` returns a SemolinaCursor that subclasses the ADBC cursor
- [ ] **CURS-02**: SemolinaCursor adds `fetchall_rows()` returning `list[Row]`
- [ ] **CURS-03**: SemolinaCursor adds `fetchmany_rows(size)` returning `list[Row]`
- [ ] **CURS-04**: SemolinaCursor adds `fetchone_row()` returning `Row | None`
- [ ] **CURS-05**: Row retains attribute access (`row.revenue`) and dict access (`row["revenue"]`)

### Configuration

- [ ] **CONF-01**: `.semolina.toml` connection sections have a backend sub-section (snowflake/databricks) determining config class
- [ ] **CONF-02**: `.semolina.toml` sections load into adbc-poolhouse config classes via TomlSettingsSource
- [ ] **CONF-03**: User can create a pool via `pool_from_config(connection="conn1")` with default `.semolina.toml` path

### Query API

- [ ] **QAPI-01**: `query(metrics=[...], dimensions=[...])` shorthand accepted as keyword args
- [ ] **QAPI-02**: Builder methods (`.metrics()`, `.dimensions()`) are additive with args passed to `query()`

### Documentation

- [ ] **DOCS-01**: Tutorials updated for pool registration and SemolinaCursor API
- [ ] **DOCS-02**: How-to guides updated for .semolina.toml connection config and pool_from_config()
- [ ] **DOCS-03**: How-to guides updated for Arrow fetch methods and Row convenience methods
- [ ] **DOCS-04**: API reference generated for new public API (SemolinaCursor, Dialect, pool_from_config, register with dialect)

## Future Requirements

Deferred to post-v0.3. Tracked but not in current roadmap.

### Integrations

- **INTG-01**: FastAPI integration with pydantic-compatible results
- **INTG-02**: Django integration (`semolina-django`) — ORM-style queryset wrapper
- **INTG-03**: GraphQL interface

### Extended Backends

- **BACK-01**: cube.dev backend
- **BACK-02**: dbt Semantic Layer backend

### Advanced Query

- **ADVQ-01**: Async query execution (`async def execute()`)
- **ADVQ-02**: CLI query interface (`semolina query <model> --metrics ...`)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-view join API | Complex feature, requires extensive design work |
| Window functions (ROW_NUMBER, LAG, etc.) | SQL complexity beyond semantic view scope |
| HAVING clause for metric filtering | Evaluate after core query API stabilizes |
| SEMANTIC_VIEW() clause syntax for Snowflake | Using standard SQL instead |
| dbt manifest → Semolina model codegen | Focus is warehouse-direct introspection |
| Connection pooling logic in Semolina | adbc-poolhouse handles this |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONN-01 | Phase 25 | Pending |
| CONN-02 | Phase 25 | Pending |
| CONN-03 | Phase 25 | Pending |
| CONN-04 | Phase 25 | Pending |
| CURS-01 | Phase 26 | Pending |
| CURS-02 | Phase 26 | Pending |
| CURS-03 | Phase 26 | Pending |
| CURS-04 | Phase 26 | Pending |
| CURS-05 | Phase 26 | Pending |
| CONF-01 | Phase 27 | Pending |
| CONF-02 | Phase 27 | Pending |
| CONF-03 | Phase 27 | Pending |
| QAPI-01 | Phase 28 | Pending |
| QAPI-02 | Phase 28 | Pending |
| DOCS-01 | Phase 29 | Pending |
| DOCS-02 | Phase 29 | Pending |
| DOCS-03 | Phase 29 | Pending |
| DOCS-04 | Phase 29 | Pending |

**Coverage:**
- v0.3 requirements: 18 total
- Mapped to phases: 18
- Unmapped: 0

---
*Requirements defined: 2026-03-16*
*Last updated: 2026-03-16 after adding DOCS requirements and Phase 29*
