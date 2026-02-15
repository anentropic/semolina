# Roadmap: Cubano

## Overview

Cubano builds from foundation to production: starting with typed models and immutable query construction, adding SQL generation with a mock backend for testing, wiring execution with results and registry, then implementing production backends (Snowflake and Databricks), and finally packaging for distribution. Each phase delivers a complete, verifiable capability that enables the next.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Model Foundation** - Typed models with metaclass and field descriptors
- [x] **Phase 2: Query Builder** - Fluent, immutable query construction with Q-objects
- [ ] **Phase 3: SQL Generation & Mock Backend** - SQL compilation with MockEngine for testing
- [ ] **Phase 4: Execution & Results** - Query execution, Row objects, and engine registry
- [ ] **Phase 5: Snowflake Backend** - First production backend with AGG() syntax
- [ ] **Phase 6: Databricks Backend** - Second backend with MEASURE() syntax
- [ ] **Phase 7: Packaging** - Distribution-ready library with extras

## Phase Details

### Phase 1: Model Foundation
**Goal**: Developers can define typed semantic view models with field references
**Depends on**: Nothing (first phase)
**Requirements**: MOD-01, MOD-02, MOD-03, MOD-04, MOD-05
**Success Criteria** (what must be TRUE):
  1. Developer can define a model using `class Sales(SemanticView, view='sales')`
  2. Developer can declare Metric, Dimension, and Fact fields with class-level syntax
  3. Developer can reference fields as Python attributes: `Sales.revenue`
  4. Field names are validated against SQL injection patterns and reserved keywords
  5. Model metadata is frozen after class creation (immutable)
**Plans**: 1 plan

Plans:
- [x] 01-01-PLAN.md — Field descriptors, SemanticView base class, tests, and package metadata

### Phase 2: Query Builder
**Goal**: Developers can construct immutable, type-safe queries with filters
**Depends on**: Phase 1
**Requirements**: QRY-01, QRY-02, QRY-03, QRY-04, QRY-05, QRY-06, QRY-07, QRY-08
**Success Criteria** (what must be TRUE):
  1. Developer can select metrics via `.metrics(Sales.revenue, Sales.cost)`
  2. Developer can select dimensions and facts via `.dimensions(Sales.country, Sales.unit_price)`
  3. Developer can chain query methods: `.metrics(...).dimensions(...).filter(...).order_by(...).limit(...)`
  4. Developer can compose filters with Q-objects: `Q(country='US') | Q(country='CA')`
  5. Query objects are immutable — each method returns a new instance
  6. Developer cannot create empty queries (validation requires at least one metric or dimension)
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md — Q-object filter composition (TDD)
- [x] 02-02-PLAN.md — Immutable Query builder with method chaining (TDD)

### Phase 3: SQL Generation & Mock Backend
**Goal**: Queries compile to SQL and execute against mock backend for testing
**Depends on**: Phase 2
**Requirements**: SQL-01, SQL-02, SQL-03, SQL-04, SQL-05, ENG-01, ENG-02
**Success Criteria** (what must be TRUE):
  1. Developer can inspect generated SQL via `.to_sql()` without executing
  2. SQL generation wraps metrics in `AGG()` for Snowflake dialect
  3. SQL generation wraps metrics in `MEASURE()` for Databricks dialect
  4. GROUP BY clause is automatically derived from selected dimensions
  5. All SQL identifiers are properly quoted to prevent injection
  6. Developer can execute queries against MockEngine without warehouse connection
  7. MockEngine validates query structure and returns test data
**Plans**: TBD

Plans:
- [ ] TBD (planned during phase planning)

### Phase 4: Execution & Results
**Goal**: Queries execute and return Row objects with attribute and dict access
**Depends on**: Phase 3
**Requirements**: EXE-01, EXE-02, EXE-03, REG-01, REG-02, REG-03
**Success Criteria** (what must be TRUE):
  1. Developer can execute query via `.fetch()` returning list of Row objects
  2. Row objects support attribute access: `row.revenue`
  3. Row objects support dict-style access: `row['revenue']`
  4. Developer can register engines by name: `cubano.register('default', engine)`
  5. Engine resolution is lazy — resolved at `.fetch()` time
  6. Developer can select engine per-query via `.using('warehouse_name')`
**Plans**: TBD

Plans:
- [ ] TBD (planned during phase planning)

### Phase 5: Snowflake Backend
**Goal**: Library connects to Snowflake and executes queries with AGG() syntax
**Depends on**: Phase 4
**Requirements**: ENG-03 (plus Snowflake-specific validation of SQL-02, SQL-04, SQL-05)
**Success Criteria** (what must be TRUE):
  1. SnowflakeEngine connects to Snowflake warehouse with connection parameters
  2. SnowflakeEngine generates SQL with `AGG(metric)` wrapper for metrics
  3. Developer can execute queries against Snowflake Semantic Views
  4. Snowflake driver imports lazily (only when SnowflakeEngine is instantiated)
  5. Connection management follows Snowflake connector best practices
**Plans**: TBD

Plans:
- [ ] TBD (planned during phase planning)

### Phase 6: Databricks Backend
**Goal**: Library connects to Databricks and executes queries with MEASURE() syntax
**Depends on**: Phase 5
**Requirements**: ENG-04 (plus Databricks-specific validation of SQL-03, SQL-04, SQL-05)
**Success Criteria** (what must be TRUE):
  1. DatabricksEngine connects to Databricks workspace with connection parameters
  2. DatabricksEngine generates SQL with `MEASURE(metric)` wrapper for metrics
  3. Developer can execute queries against Databricks Metric Views
  4. DatabricksEngine supports Unity Catalog three-part names (`catalog.schema.view`)
  5. Databricks driver imports lazily (only when DatabricksEngine is instantiated)
**Plans**: TBD

Plans:
- [ ] TBD (planned during phase planning)

### Phase 7: Packaging
**Goal**: Library is installable via pip with zero required dependencies and optional backend extras
**Depends on**: Phase 6
**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04
**Success Criteria** (what must be TRUE):
  1. Developer can install core library via `pip install cubano` with zero dependencies
  2. Developer can install Snowflake support via `pip install cubano[snowflake]`
  3. Developer can install Databricks support via `pip install cubano[databricks]`
  4. Public API is accessible via `import cubano` (models, query, engines, registry)
  5. Package includes `py.typed` marker for type checking support
**Plans**: TBD

Plans:
- [ ] TBD (planned during phase planning)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Model Foundation | 1/1 | ✓ Complete | 2026-02-15 |
| 2. Query Builder | 2/2 | ✓ Complete | 2026-02-15 |
| 3. SQL Generation & Mock Backend | 0/? | Not started | - |
| 4. Execution & Results | 0/? | Not started | - |
| 5. Snowflake Backend | 0/? | Not started | - |
| 6. Databricks Backend | 0/? | Not started | - |
| 7. Packaging | 0/? | Not started | - |
