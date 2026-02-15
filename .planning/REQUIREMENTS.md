# Requirements: Cubano

**Defined:** 2026-02-14
**Core Value:** A single, Pythonic query API that works identically across Snowflake and Databricks semantic views, with typed models, IDE autocomplete, and backend-agnostic code.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Models

- [ ] **MOD-01**: Developer can define a semantic view model via metaclass: `class Sales(SemanticView, view='sales')`
- [ ] **MOD-02**: Developer can declare Metric fields on a model: `revenue = Metric()`
- [ ] **MOD-03**: Developer can declare Dimension fields on a model: `country = Dimension()`
- [ ] **MOD-04**: Developer can declare Fact fields on a model: `unit_price = Fact()`
- [ ] **MOD-05**: Developer can reference fields as Python attributes for type-safe queries: `Sales.revenue`

### Query Builder

- [ ] **QRY-01**: Developer can select metrics via `.metrics(Sales.revenue, Sales.cost)`
- [ ] **QRY-02**: Developer can select dimensions via `.dimensions(Sales.country, Sales.region)`
- [ ] **QRY-03**: Developer can select facts via `.dimensions(Sales.unit_price)` (facts behave like dimensions)
- [ ] **QRY-04**: Developer can filter results via `.filter(Q(country='US') | Q(country='CA'))`
- [ ] **QRY-05**: Developer can order results via `.order_by(Sales.revenue)`
- [ ] **QRY-06**: Developer can limit results via `.limit(100)`
- [ ] **QRY-07**: Query builder is immutable — each method returns a new query, original is unchanged
- [ ] **QRY-08**: Developer can compose Q-objects with `&` (AND), `|` (OR), `~` (NOT) operators

### SQL Generation

- [ ] **SQL-01**: Developer can inspect generated SQL via `.to_sql()` without executing
- [ ] **SQL-02**: Snowflake SQL wraps metrics in `AGG()`: `SELECT dim, AGG(metric) FROM view`
- [ ] **SQL-03**: Databricks SQL wraps metrics in `MEASURE()`: `SELECT dim, MEASURE(metric) FROM view`
- [ ] **SQL-04**: GROUP BY is implicit — derived from selected dimensions
- [ ] **SQL-05**: SQL identifiers are properly quoted to prevent injection

### Execution & Results

- [ ] **EXE-01**: Developer can execute query via `.fetch()` returning a list of Row objects
- [ ] **EXE-02**: Row objects support attribute access: `row.revenue`
- [ ] **EXE-03**: Row objects support dict-style access: `row['revenue']`

### Engine

- [ ] **ENG-01**: Engine ABC base class defines the interface for all backends
- [ ] **ENG-02**: MockEngine enables testing queries without a warehouse connection
- [ ] **ENG-03**: SnowflakeEngine connects to Snowflake and executes queries with AGG() syntax
- [ ] **ENG-04**: DatabricksEngine connects to Databricks and executes queries with MEASURE() syntax

### Registry

- [ ] **REG-01**: Developer can register engines by name: `cubano.register('default', engine)`
- [ ] **REG-02**: Engine resolution is lazy — resolved at `.fetch()` time, not at import time
- [ ] **REG-03**: Developer can select engine per-query via `.using('name')`

### Packaging

- [ ] **PKG-01**: Library installs as `pip install cubano` with zero required dependencies
- [ ] **PKG-02**: Snowflake driver installs via `pip install cubano[snowflake]`
- [ ] **PKG-03**: Databricks driver installs via `pip install cubano[databricks]`
- [ ] **PKG-04**: Public API is accessible via `import cubano`

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Query Features

- **ADV-01**: Window functions (OVER, PARTITION BY, ROW_NUMBER, RANK, LAG/LEAD)
- **ADV-02**: Time-based filter helpers (`.filter_last_n_days()`, `.filter_date_range()`)
- **ADV-03**: Filtered aggregates (`SUM(...) FILTER (WHERE ...)`)
- **ADV-04**: CTEs (WITH clause) for reusable subqueries

### Output Formats

- **OUT-01**: `.to_pandas()` returning a pandas DataFrame
- **OUT-02**: `.to_polars()` returning a Polars DataFrame

### Tooling

- **TOOL-01**: CLI codegen — auto-generate models from warehouse view introspection
- **TOOL-02**: Reverse codegen — models to semantic view YAML

### Integration

- **INT-01**: Django integration as separate `cubano-django` package
- **INT-02**: Async support (`fetch_async()`)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Write operations (INSERT/UPDATE/DELETE) | Semantic views are read-only |
| Relationship management (FK, M2M) | Views are pre-joined, no lazy loading needed |
| Schema migrations | Managed by dbt/SQL, not ORM |
| REST/GraphQL API generation | Cubano is a library, not a platform |
| Built-in caching layer | Warehouse/BI tool responsibility |
| Connection pooling | Backend driver concern |
| String-based field references | Field refs only for type safety |
| Multi-view join API | Complexity without clear value for v1 |
| Metric/dimension validation before execution | Defer to later |
| SEMANTIC_VIEW() clause syntax for Snowflake | Using standard SQL for cross-backend consistency |
| Time dimension convenience API (`.time()`) | Time dims are just dimensions |
| Web UI / admin interface | Library, not platform |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MOD-01 | Phase 1 | Pending |
| MOD-02 | Phase 1 | Pending |
| MOD-03 | Phase 1 | Pending |
| MOD-04 | Phase 1 | Pending |
| MOD-05 | Phase 1 | Pending |
| QRY-01 | Phase 2 | Pending |
| QRY-02 | Phase 2 | Pending |
| QRY-03 | Phase 2 | Pending |
| QRY-04 | Phase 2 | Pending |
| QRY-05 | Phase 2 | Pending |
| QRY-06 | Phase 2 | Pending |
| QRY-07 | Phase 2 | Pending |
| QRY-08 | Phase 2 | Pending |
| SQL-01 | Phase 3 | Pending |
| SQL-02 | Phase 3 | Pending |
| SQL-03 | Phase 3 | Pending |
| SQL-04 | Phase 3 | Pending |
| SQL-05 | Phase 3 | Pending |
| EXE-01 | Phase 4 | Pending |
| EXE-02 | Phase 4 | Pending |
| EXE-03 | Phase 4 | Pending |
| ENG-01 | Phase 3 | Pending |
| ENG-02 | Phase 3 | Pending |
| ENG-03 | Phase 5 | Pending |
| ENG-04 | Phase 6 | Pending |
| REG-01 | Phase 4 | Pending |
| REG-02 | Phase 4 | Pending |
| REG-03 | Phase 4 | Pending |
| PKG-01 | Phase 7 | Pending |
| PKG-02 | Phase 7 | Pending |
| PKG-03 | Phase 7 | Pending |
| PKG-04 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 32 total
- Mapped to phases: 32
- Unmapped: 0

---
*Requirements defined: 2026-02-14*
*Last updated: 2026-02-15 after roadmap creation*
