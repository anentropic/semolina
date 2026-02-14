# Features Research: Python ORM/Query Builder/Semantic Layer Libraries

**Research Date:** 2026-02-14
**Researcher:** Claude (Sonnet 4.5)
**Context:** Feature comparison for Cubano - Python ORM for data warehouse semantic views

## Executive Summary

This research analyzes features across 7 major Python libraries spanning ORMs (SQLAlchemy, Django), query builders (PyPika), dataframe/analytical query engines (ibis), and semantic layers (dbt metrics, Cube.dev). The goal is to identify table stakes features, differentiators, and anti-features for a Python ORM targeting data warehouse semantic views (Snowflake, Databricks).

**Key Findings:**
- **Table Stakes:** Type safety, fluent API, SQL generation without execution, basic aggregations, filtering, joins
- **Differentiators for Semantic Layer:** Metric definitions/reuse, dimension hierarchies, time intelligence, multi-backend abstraction, immutability
- **Anti-Features:** Complex relationship management, migrations, write operations, admin UIs

---

## Libraries Analyzed

### 1. SQLAlchemy (ORM + Core)
**Category:** General-purpose ORM/SQL toolkit
**Version:** 2.x
**Target:** OLTP databases (PostgreSQL, MySQL, SQLite, etc.)

### 2. Django ORM
**Category:** Framework-integrated ORM
**Target:** OLTP databases, tightly coupled to Django

### 3. PyPika
**Category:** Pure query builder
**Target:** SQL generation without execution

### 4. ibis
**Category:** Dataframe/analytical query engine
**Target:** 20+ backends including data warehouses, pandas, Spark

### 5. dbt Metrics (now dbt Semantic Layer)
**Category:** Metrics/semantic layer
**Target:** Data warehouses via dbt

### 6. Cube.dev
**Category:** Semantic layer platform
**Target:** Data warehouses + REST API + caching

### 7. Other Semantic Layer Tools
- MetricFlow (dbt's engine)
- Transform
- Lightdash
- Malloy

---

## Feature Matrix

### Core Query Building

| Feature | SQLAlchemy | Django | PyPika | ibis | dbt | Cube.dev | Complexity | Category |
|---------|------------|--------|--------|------|-----|----------|------------|----------|
| **SELECT/projection** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Low | Table Stakes |
| **WHERE/filtering** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Low | Table Stakes |
| **ORDER BY** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Low | Table Stakes |
| **LIMIT/OFFSET** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Low | Table Stakes |
| **GROUP BY** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Low | Table Stakes |
| **HAVING** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Medium | Table Stakes |
| **JOIN (explicit)** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Medium | Table Stakes |
| **JOIN (auto via FK)** | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | High | Differentiator |
| **Subqueries** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Medium | Table Stakes |
| **CTEs (WITH)** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Medium | Table Stakes |
| **Window functions** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | High | Differentiator |
| **UNION/INTERSECT** | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | Medium | Table Stakes |

**Analysis:**
- All libraries support basic CRUD-style queries
- Window functions are advanced but expected in analytical contexts
- Auto-joins via relationships are powerful but complex to implement

---

### Type Safety & Developer Experience

| Feature | SQLAlchemy | Django | PyPika | ibis | dbt | Cube.dev | Complexity | Category |
|---------|------------|--------|--------|------|-----|----------|------------|----------|
| **Typed models/schemas** | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | Medium | Table Stakes |
| **Type hints (Python)** | Partial | ✗ | ✗ | ✓✓ | ✗ | Partial | Medium | Differentiator |
| **Field reference (not strings)** | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ | Low | Differentiator |
| **IDE autocomplete** | Good | Good | Poor | Excellent | N/A | Poor | Medium | Differentiator |
| **Compile-time validation** | Partial | ✗ | ✗ | ✓ | ✗ | ✗ | High | Differentiator |
| **Immutable query objects** | ✗ | ✗ | ✗ | ✓ | N/A | N/A | Low | Differentiator |
| **Fluent/chainable API** | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | Low | Table Stakes |
| **Q-objects/complex filters** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Medium | Table Stakes |

**Analysis:**
- **ibis leads in type safety** with full type hints, immutability, excellent IDE support
- **Cubano's field refs (no strings) is a differentiator** - Django uses strings extensively
- **Immutability prevents bugs** in query construction
- String-based APIs (Django's `"field__lookup"`) are error-prone

---

### Aggregations & Metrics

| Feature | SQLAlchemy | Django | PyPika | ibis | dbt | Cube.dev | Complexity | Category |
|---------|------------|--------|--------|------|-----|----------|------------|----------|
| **Basic aggregates (SUM, AVG, COUNT)** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Low | Table Stakes |
| **Named/reusable metrics** | ✗ | ✗ | ✗ | ✗ | ✓✓ | ✓✓ | High | Differentiator |
| **Metric dependencies** | ✗ | ✗ | ✗ | ✗ | ✓✓ | ✓✓ | High | Differentiator |
| **Calculated/derived metrics** | Manual | Manual | Manual | ✓ | ✓✓ | ✓✓ | Medium | Differentiator |
| **Metric metadata (desc, format)** | ✗ | ✗ | ✗ | ✗ | ✓ | ✓✓ | Low | Differentiator |
| **Aggregate over windows** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | High | Table Stakes |
| **DISTINCT aggregates** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Low | Table Stakes |
| **Filtered aggregates (FILTER WHERE)** | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | Medium | Differentiator |
| **Ratio/percent metrics** | Manual | Manual | Manual | ✓ | ✓✓ | ✓✓ | Medium | Differentiator |

**Analysis:**
- **dbt & Cube.dev excel at metric reusability** - this is their core value prop
- Traditional ORMs require manual aggregation composition
- **Named metrics with metadata is a key semantic layer feature**
- Snowflake/Databricks semantic views provide built-in metrics - Cubano should expose these cleanly

---

### Dimensions & Attributes

| Feature | SQLAlchemy | Django | PyPika | ibis | dbt | Cube.dev | Complexity | Category |
|---------|------------|--------|--------|------|-----|----------|------------|----------|
| **Dimension selection** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Low | Table Stakes |
| **Dimension hierarchies** | ✗ | ✗ | ✗ | ✗ | ✓ | ✓✓ | High | Differentiator |
| **Dimension metadata** | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | Low | Differentiator |
| **Fact vs dimension distinction** | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | Medium | Differentiator |
| **Automatic dimension joins** | Via FK | Via FK | ✗ | ✗ | ✓ | ✓ | High | Differentiator |
| **Dimension role-playing** | Manual | Manual | Manual | Manual | ✓ | ✓ | High | Differentiator |

**Analysis:**
- **Dimension hierarchies** (e.g., Date → Month → Quarter → Year) are critical for OLAP
- **Fact vs dimension** is a semantic layer concept, not in traditional ORMs
- Cubano treats facts as dimensions in queries - this is pragmatic for data warehouse views

---

### Time Intelligence

| Feature | SQLAlchemy | Django | PyPika | ibis | dbt | Cube.dev | Complexity | Category |
|---------|------------|--------|--------|------|-----|----------|------------|----------|
| **Date/time filtering** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Low | Table Stakes |
| **Date arithmetic** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Medium | Table Stakes |
| **Date part extraction** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Low | Table Stakes |
| **Date truncation/bucketing** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Low | Table Stakes |
| **Relative dates (last 7 days)** | Manual | Manual | Manual | ✓ | ✓ | ✓✓ | Medium | Differentiator |
| **Period over period (YoY, MoM)** | Manual | Manual | Manual | Manual | ✓ | ✓✓ | High | Differentiator |
| **Time grain specification** | Manual | Manual | Manual | ✓ | ✓ | ✓✓ | Medium | Differentiator |
| **Fiscal calendar support** | Manual | Manual | Manual | Manual | ✗ | ✓ | High | Nice-to-have |

**Analysis:**
- **Time intelligence is a killer feature for analytics**
- Traditional ORMs make you write SQL manually for period-over-period
- Cube.dev has extensive time intelligence (rolling windows, etc.)
- **Relative dates are high-value, low-complexity** - good early target

---

### Backend Abstraction

| Feature | SQLAlchemy | Django | PyPika | ibis | dbt | Cube.dev | Complexity | Category |
|---------|------------|--------|--------|------|-----|----------|------------|----------|
| **Multi-backend support** | ✓✓ | ✓ | ✓ | ✓✓ | ✓✓ | ✓✓ | High | Differentiator |
| **Dialect-aware SQL gen** | ✓✓ | ✓ | Partial | ✓✓ | ✓✓ | ✓✓ | High | Table Stakes |
| **Custom dialect/compiler** | ✓✓ | Limited | ✓ | ✓ | ✓ | ✓ | Very High | Differentiator |
| **Backend-specific types** | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | Medium | Table Stakes |
| **Driver abstraction** | ✓✓ | ✓ | N/A | ✓✓ | ✓ | ✓ | High | Table Stakes |
| **Connection pooling** | ✓ | ✓ | N/A | ✓ | N/A | ✓ | Medium | Nice-to-have |

**Analysis:**
- **SQLAlchemy's dialect system is industry-leading**
- **ibis supports 20+ backends** - excellent abstraction
- For Cubano: **Snowflake + Databricks is sufficient initially**, but extensibility is key
- **Driver as extras (like Cubano has)** is modern, reduces bloat

---

### SQL Generation & Execution

| Feature | SQLAlchemy | Django | PyPika | ibis | dbt | Cube.dev | Complexity | Category |
|---------|------------|--------|--------|------|-----|----------|------------|----------|
| **Generate SQL without execution** | ✓✓ | ✓ | ✓✓ | ✓ | ✓ | ✓ | Low | Table Stakes |
| **Preview/explain SQL** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Low | Table Stakes |
| **Parameter binding (safe)** | ✓✓ | ✓✓ | ✓ | ✓ | ✓ | ✓ | Medium | Table Stakes |
| **Raw SQL escape hatch** | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | Low | Table Stakes |
| **Query compilation caching** | ✓ | ✓ | ✗ | ✓ | ✓ | ✓✓ | Medium | Nice-to-have |
| **Lazy evaluation** | ✓ | ✓ | N/A | ✓ | N/A | N/A | Medium | Table Stakes |
| **Result pagination** | ✓ | ✓ | N/A | ✓ | ✗ | ✗ | Low | Table Stakes |
| **Streaming results** | ✓ | ✓ | N/A | ✓ | ✗ | ✗ | Medium | Nice-to-have |

**Analysis:**
- **`.to_sql()` is critical** for debugging and integration
- **Lazy evaluation** prevents accidental large fetches
- Cubano's separation of `.to_sql()` and `.fetch()` is good design
- **Parameter binding prevents SQL injection** - must-have

---

### Result Handling

| Feature | SQLAlchemy | Django | PyPika | ibis | dbt | Cube.dev | Complexity | Category |
|---------|------------|--------|--------|------|-----|----------|------------|----------|
| **Row objects (not tuples)** | ✓ | ✓ | N/A | ✓ | N/A | ✓ | Low | Table Stakes |
| **Attribute access (row.field)** | ✓ | ✓ | N/A | ✓ | N/A | ✓ | Low | Table Stakes |
| **Dict conversion** | ✓ | ✓ | N/A | ✓ | N/A | ✓ | Low | Table Stakes |
| **Pandas DataFrame output** | Via pandas | Via pandas | N/A | ✓✓ | ✗ | ✓ | Medium | Differentiator |
| **Arrow/Polars output** | ✗ | ✗ | N/A | ✓✓ | ✗ | ✗ | Medium | Differentiator |
| **JSON serialization** | Manual | ✓ | N/A | ✓ | N/A | ✓✓ | Low | Table Stakes |
| **Iterator/lazy fetch** | ✓ | ✓ | N/A | ✓ | N/A | ✗ | Medium | Nice-to-have |
| **Type preservation** | ✓ | ✓ | N/A | ✓ | N/A | ✓ | Medium | Table Stakes |

**Analysis:**
- **Row objects with attribute access is standard**
- **Pandas/Arrow output is valuable for data science workflows**
- ibis excels here - can output to many formats
- Cubano's custom Row objects are good - consider `.to_pandas()` later

---

### Relationship Management

| Feature | SQLAlchemy | Django | PyPika | ibis | dbt | Cube.dev | Complexity | Category |
|---------|------------|--------|--------|------|-----|----------|------------|----------|
| **One-to-many relationships** | ✓✓ | ✓✓ | ✗ | ✗ | ✓ | ✓ | High | Anti-feature |
| **Many-to-many relationships** | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | Very High | Anti-feature |
| **Lazy loading relationships** | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | High | Anti-feature |
| **Eager loading (select_related)** | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | High | Anti-feature |
| **Relationship traversal in queries** | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | High | Anti-feature |

**Analysis:**
- **For OLTP ORMs, relationships are critical**
- **For semantic views, relationships are anti-patterns** - views pre-join data
- Snowflake/Databricks semantic views are denormalized
- **Cubano correctly avoids complex relationship management**

---

### Schema Definition & Introspection

| Feature | SQLAlchemy | Django | PyPika | ibis | dbt | Cube.dev | Complexity | Category |
|---------|------------|--------|--------|------|-----|----------|------------|----------|
| **Declarative models** | ✓✓ | ✓✓ | ✗ | ✓ | ✓ | ✓ | Medium | Table Stakes |
| **Reflection/introspection** | ✓✓ | ✓ | ✗ | ✓ | ✗ | ✗ | High | Differentiator |
| **Schema migrations** | Via Alembic | ✓✓ | ✗ | ✗ | ✗ | ✗ | Very High | Anti-feature |
| **Column constraints** | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | Medium | Anti-feature |
| **Indexes** | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | Medium | Anti-feature |
| **Validation** | Via ext | ✓ | ✗ | ✗ | ✓ | ✓ | Medium | Nice-to-have |
| **Type coercion** | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | Medium | Table Stakes |

**Analysis:**
- **Schema introspection is valuable** for dynamic model generation from existing views
- **Migrations are OLTP concerns** - data warehouses use dbt/SQL migrations
- **Cubano's metaclass approach is similar to Django/SQLAlchemy**
- Consider auto-generating models from `SHOW VIEWS` metadata

---

### Write Operations

| Feature | SQLAlchemy | Django | PyPika | ibis | dbt | Cube.dev | Complexity | Category |
|---------|------------|--------|--------|------|-----|----------|------------|----------|
| **INSERT** | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | Medium | Anti-feature |
| **UPDATE** | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | Medium | Anti-feature |
| **DELETE** | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | Medium | Anti-feature |
| **Bulk operations** | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | Medium | Anti-feature |
| **Transactions** | ✓ | ✓ | N/A | ✓ | ✗ | ✗ | High | Anti-feature |
| **Savepoints** | ✓ | ✓ | N/A | ✗ | ✗ | ✗ | High | Anti-feature |

**Analysis:**
- **Semantic views are read-only** by nature
- **No write operations needed** - this simplifies Cubano significantly
- dbt/Cube.dev also read-only
- **Anti-feature: Focus on reads prevents scope creep**

---

### Advanced Features

| Feature | SQLAlchemy | Django | PyPika | ibis | dbt | Cube.dev | Complexity | Category |
|---------|------------|--------|--------|------|-----|----------|------------|----------|
| **Custom SQL functions** | ✓✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Medium | Table Stakes |
| **UDFs (user-defined functions)** | ✓ | ✗ | ✗ | ✓ | ✓ | ✗ | High | Nice-to-have |
| **Materialized views** | ✓ | ✗ | ✗ | ✗ | ✓✓ | ✓ | High | Anti-feature |
| **Incremental models** | ✗ | ✗ | ✗ | ✗ | ✓✓ | ✗ | Very High | Anti-feature |
| **Caching/memoization** | Via ext | ✗ | ✗ | ✓ | ✗ | ✓✓ | High | Nice-to-have |
| **Query optimization hints** | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ | High | Nice-to-have |
| **Pivot/unpivot** | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | High | Differentiator |
| **Array/JSON operations** | ✓ | ✓ | Partial | ✓✓ | ✓ | ✓ | High | Differentiator |

**Analysis:**
- **Custom SQL functions** needed for warehouse-specific functions (AGG(), MEASURE())
- **Materialized views** are warehouse/dbt concern, not ORM
- **Caching** is valuable but complex - consider later
- **Pivot is common in BI** - medium priority

---

### API/Integration Features

| Feature | SQLAlchemy | Django | PyPika | ibis | dbt | Cube.dev | Complexity | Category |
|---------|------------|--------|--------|------|-----|----------|------------|----------|
| **REST API generation** | ✗ | Via DRF | ✗ | ✗ | ✗ | ✓✓ | High | Anti-feature |
| **GraphQL API** | Via ext | Via ext | ✗ | ✗ | ✗ | ✓ | High | Anti-feature |
| **CLI tool** | ✗ | ✓ | ✗ | ✗ | ✓✓ | ✓ | Medium | Anti-feature |
| **Web UI/admin** | ✗ | ✓✓ | ✗ | ✗ | ✗ | ✓✓ | Very High | Anti-feature |
| **Jupyter integration** | ✓ | ✗ | ✗ | ✓✓ | ✗ | ✗ | Low | Differentiator |
| **Async support** | ✓ | ✓ | ✗ | Partial | ✗ | ✓ | High | Nice-to-have |

**Analysis:**
- **Cube.dev is a platform** (API + caching + UI) - different scope
- **Cubano is a library** - no UI/API generation
- **Jupyter integration is valuable** for data science
- **Async support** useful for web apps - consider for v2+

---

### Developer Tooling

| Feature | SQLAlchemy | Django | PyPika | ibis | dbt | Cube.dev | Complexity | Category |
|---------|------------|--------|--------|------|-----|----------|------------|----------|
| **Type stubs (py.typed)** | ✓ | Partial | ✗ | ✓✓ | ✗ | ✗ | Low | Table Stakes |
| **Comprehensive docs** | ✓✓ | ✓✓ | ✓ | ✓✓ | ✓✓ | ✓✓ | N/A | Table Stakes |
| **Migration guides** | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | N/A | Nice-to-have |
| **Testing utilities** | ✓ | ✓✓ | ✗ | ✓ | ✓ | ✗ | Medium | Nice-to-have |
| **Query debugging/logging** | ✓✓ | ✓ | ✗ | ✓ | ✓ | ✓ | Low | Table Stakes |
| **Performance profiling** | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | Medium | Nice-to-have |
| **Examples/recipes** | ✓✓ | ✓✓ | ✓ | ✓ | ✓✓ | ✓ | N/A | Table Stakes |

**Analysis:**
- **Type stubs are critical for modern Python**
- **Good docs are non-negotiable**
- **Query logging** helps debugging - low-hanging fruit

---

## Feature Categories for Cubano

### Table Stakes (Must Have)

These features are expected in any query builder/ORM. Users will leave if these are missing.

#### Core Query Operations (Low Complexity)
- ✅ SELECT specific columns/dimensions
- ✅ WHERE filtering with Q-objects
- ✅ ORDER BY
- ✅ LIMIT/OFFSET
- ✅ Basic aggregates (SUM, AVG, COUNT, MIN, MAX)
- ✅ GROUP BY (implicit from dimension selection)
- Field reference (not strings) - **already implemented**
- Fluent chainable API - **already implemented**

#### SQL Generation (Low-Medium Complexity)
- ✅ `.to_sql()` - generate SQL without execution
- ✅ `.fetch()` - execute and return results
- Parameter binding for safety
- SQL comment injection (for query tracking)
- Pretty-print SQL option

#### Type Safety (Low-Medium Complexity)
- ✅ Typed model classes via metaclass
- ✅ Immutable query objects
- Full type hints for IDE support
- `py.typed` marker file
- Runtime type validation (optional)

#### Backend Support (Medium Complexity)
- ✅ Snowflake dialect (AGG() syntax)
- ✅ Databricks dialect (MEASURE() syntax)
- Dialect-specific SQL generation
- Backend-specific type mappings

#### Result Handling (Low Complexity)
- ✅ Custom Row objects
- Attribute access (`row.field`)
- Dict conversion (`.to_dict()`, `.to_dicts()`)
- JSON serialization
- Type preservation from database

#### Documentation & DX (Low Complexity)
- Comprehensive API docs
- Quickstart guide
- Examples for common patterns
- Clear error messages
- Query debugging/logging

**Dependencies:**
- Type hints depend on model metaclass
- SQL generation depends on dialect system
- Result handling depends on fetch implementation

---

### Differentiators (Competitive Advantage)

These features set Cubano apart from generic ORMs and compete with semantic layer tools.

#### Semantic View Specific (Medium-High Complexity)
- **Metrics vs dimensions distinction** (Medium)
  - `.metrics()` and `.dimensions()` separate APIs
  - Type system enforces correct usage
  - Already partially implemented ✓

- **Warehouse-specific syntax support** (High)
  - Snowflake `AGG(field)` function calls
  - Databricks `MEASURE(field)` function calls
  - Already planned ✓

- **Fact-as-dimension queries** (Low)
  - Facts (additive fields) usable in dimension context
  - Already supported ✓

#### Developer Experience (Low-Medium Complexity)
- **Immutable queries** (Low)
  - Query methods return new instances
  - Prevents accidental mutations
  - Already implemented ✓

- **Field references only** (Low)
  - No string-based field access
  - Compile-time safety
  - Already implemented ✓

- **Zero required dependencies** (Low)
  - Core lib is dependency-free
  - Drivers as extras
  - Already implemented ✓

- **Excellent type hints** (Medium)
  - Full generic typing
  - IDE autocomplete for fields
  - MyPy/Pyright support

#### Advanced Querying (Medium-High Complexity)
- **Window functions** (High)
  - `OVER (PARTITION BY ... ORDER BY ...)`
  - Row number, rank, lag/lead
  - Critical for analytics

- **CTEs (WITH clause)** (Medium)
  - Reusable subqueries
  - Better readability than nested queries

- **Filtered aggregates** (Medium)
  - `SUM(...) FILTER (WHERE ...)`
  - Snowflake/Databricks support this

- **Time-based filtering helpers** (Medium)
  - `.filter_last_n_days(7)`
  - `.filter_current_month()`
  - Common analytics patterns

#### Multi-Format Output (Medium Complexity)
- **Pandas DataFrame output** (Medium)
  - `.to_pandas()` method
  - Depends on pandas extra
  - High value for data science users

- **Polars DataFrame output** (Medium)
  - `.to_polars()` method
  - Modern alternative to pandas
  - Growing popularity

#### Introspection & Codegen (High Complexity)
- **Auto-generate models from views** (High)
  - Inspect `SHOW VIEWS` metadata
  - Generate Python model code
  - Similar to `sqlacodegen`
  - Massive time-saver

**Dependencies:**
- Window functions need dialect-specific syntax
- Time helpers depend on Q-objects
- DataFrame output depends on result handling
- Codegen depends on introspection + model metaclass

**Priority Ranking:**
1. Excellent type hints (high impact, medium effort)
2. Time-based filtering (high impact, medium effort)
3. Filtered aggregates (medium impact, medium effort)
4. CTEs (medium impact, medium effort)
5. Window functions (high impact, high effort)
6. Pandas output (high impact, medium effort)
7. Codegen (very high impact, very high effort - v2+)

---

### Nice-to-Have (Future Enhancements)

Features that add value but aren't critical for initial adoption.

#### Query Features (Medium-High Complexity)
- **HAVING clause** (Low)
  - Filter on aggregates
  - Less common in semantic views

- **UNION/INTERSECT/EXCEPT** (Medium)
  - Set operations
  - Occasional use cases

- **Pivot/unpivot** (High)
  - Common in BI
  - Complex SQL generation
  - Consider for v2+

#### Performance (Medium-High Complexity)
- **Query compilation caching** (Medium)
  - Cache SQL generation results
  - Useful for repeated queries

- **Connection pooling** (Medium)
  - Reuse database connections
  - Depends on driver implementation

- **Streaming results** (High)
  - Iterator over large result sets
  - Memory-efficient
  - Warehouse-dependent

#### Integration (Low-Medium Complexity)
- **Async support** (High)
  - Asyncio-compatible API
  - Useful for web frameworks
  - Major undertaking

- **Jupyter magic commands** (Low)
  - `%%cubano_query` cell magic
  - Nice DX for notebooks

- **Query explain/profiling** (Medium)
  - Show query plan
  - Performance analysis

#### Developer Tools (Low-Medium Complexity)
- **Testing utilities** (Medium)
  - Mock query builder
  - Fixtures for common scenarios

- **Migration guides** (Low)
  - From raw SQL
  - From other ORMs

- **Performance benchmarks** (Medium)
  - vs raw SQL
  - vs other libraries

**Priority for v1.0:** Focus on table stakes + top differentiators. Nice-to-haves for v1.1+.

---

### Anti-Features (Deliberately Excluded)

Features common in other ORMs but inappropriate for Cubano's semantic view focus.

#### OLTP-Specific Features
- **Write operations** (INSERT/UPDATE/DELETE)
  - Semantic views are read-only
  - Would require different architecture

- **Transactions & savepoints**
  - Not applicable to read-only queries

- **Schema migrations**
  - Views are managed by dbt/SQL migrations
  - Not ORM responsibility

- **Relationship management** (One-to-many, M2M)
  - Semantic views pre-join data
  - No lazy loading needed
  - Adds massive complexity

- **Column constraints & indexes**
  - Defined at view creation time
  - Not ORM concern

#### Platform Features
- **REST API generation**
  - Cubano is a library, not a platform
  - Users build their own APIs

- **GraphQL API**
  - Same reasoning as REST

- **Web UI/admin interface**
  - Not a platform
  - Users can build with Streamlit/etc.

- **Built-in caching layer**
  - Warehouse/BI tool responsibility
  - Adds operational complexity

#### Scope Creep
- **Materialized view management**
  - dbt's job

- **Incremental model building**
  - dbt's job

- **Data validation rules**
  - Should be in dbt models

- **Business logic in ORM**
  - Keep ORM thin, logic in application

**Rationale:** These features would:
1. Increase maintenance burden significantly
2. Compete with purpose-built tools (dbt, Cube.dev)
3. Violate single-responsibility principle
4. Add complexity without value for target use case

---

## Implementation Complexity Analysis

### Low Complexity (1-2 weeks)
- Query logging
- Time-based filter helpers
- `py.typed` marker + type stub improvements
- SQL pretty-printing
- Dict/JSON result serialization
- HAVING clause

### Medium Complexity (2-4 weeks)
- CTEs (WITH clause)
- Filtered aggregates
- Pandas/Polars output
- Query compilation caching
- UNION/INTERSECT
- Custom SQL function registry
- Connection pooling

### High Complexity (1-3 months)
- Window functions
- Full async support
- Auto-codegen from views
- Pivot/unpivot
- Streaming results
- Comprehensive testing framework

### Very High Complexity (3+ months)
- Complete multi-backend abstraction (beyond Snowflake/Databricks)
- Advanced time intelligence (period-over-period, etc.)
- Query optimization engine
- Platform features (API generation, caching, UI)

---

## Feature Dependencies Map

```
Core Model System (✓ implemented)
├── Type Hints Enhancement (Medium)
├── Query Logging (Low)
└── Introspection/Codegen (High)

Query Builder (✓ implemented)
├── CTEs (Medium) → enables reusable subqueries
├── Window Functions (High) → depends on dialect
├── Filtered Aggregates (Medium)
├── Time Helpers (Medium) → depends on Q-objects ✓
└── HAVING (Low)

Result Handling (✓ implemented)
├── Pandas Output (Medium) → depends on extras
├── Polars Output (Medium) → depends on extras
└── Streaming (High) → depends on driver capabilities

Backend/Dialect (✓ implemented)
├── Snowflake AGG() (✓ planned)
├── Databricks MEASURE() (✓ planned)
└── Additional backends (High) → future

Developer Experience
├── Type Stubs (Low)
├── Docs (Low)
├── Examples (Low)
└── Testing Utils (Medium)

Future/Optional
├── Async Support (High) → major refactor
├── Pivot/Unpivot (High)
└── Query Caching (Medium)
```

---

## Competitive Positioning

### vs SQLAlchemy
**Cubano advantages:**
- Purpose-built for data warehouses, not OLTP
- Simpler API (no relationship management)
- Immutable queries
- Zero dependencies
- First-class semantic view support

**SQLAlchemy advantages:**
- Mature ecosystem
- Supports write operations
- More databases
- Battle-tested

**Positioning:** "SQLAlchemy for data warehouses - simpler, typed, read-only"

---

### vs Django ORM
**Cubano advantages:**
- Framework-independent
- Type-safe (no string field names)
- Data warehouse optimized
- Immutable queries

**Django advantages:**
- Integrated with Django ecosystem
- Admin UI
- Migrations
- Write operations

**Positioning:** "Django-like API for data warehouse analytics, without the framework"

---

### vs ibis
**Cubano advantages:**
- Simpler API for semantic views specifically
- Direct SQL generation (no intermediate IR)
- Snowflake/Databricks semantic view native support

**ibis advantages:**
- 20+ backends
- Dataframe-like API
- Mature ecosystem
- More advanced operations

**Positioning:** "Specialized for semantic views, simpler than ibis for this use case"

---

### vs PyPika
**Cubano advantages:**
- Semantic view abstractions (metrics/dimensions)
- Type-safe models
- Execution capability (not just generation)
- Immutable queries

**PyPika advantages:**
- Pure query builder
- No opinions
- Lightweight

**Positioning:** "PyPika + typed models + semantic view support"

---

### vs dbt Semantic Layer / Cube.dev
**Cubano advantages:**
- Python-native (no config files)
- Programmatic query building
- Library not platform
- No additional infrastructure

**dbt/Cube.dev advantages:**
- Central metric definitions
- Caching layer
- Multi-user/governance
- REST APIs
- BI tool integration

**Positioning:** "Programmatic access to semantic views, not a platform replacement. Complementary to dbt."

---

## Recommendations for Cubano v1.0

### Must Build (Table Stakes)
1. ✅ Core query API (.metrics, .dimensions, .filter, .order_by, .limit)
2. ✅ Q-objects for complex filters
3. ✅ Immutable query objects
4. ✅ Field references (no strings)
5. ✅ .to_sql() and .fetch()
6. ✅ Snowflake + Databricks backends
7. **Enhance type hints** (Medium effort, high value)
8. **Query logging** (Low effort, high value)
9. **SQL pretty-printing** (Low effort, medium value)
10. **Comprehensive documentation** (Medium effort, critical)

### Should Build (Key Differentiators)
1. **Time-based filter helpers** (Medium effort, high value)
   - `.filter_last_n_days(n)`
   - `.filter_date_range(start, end)`
   - `.filter_current_month()`

2. **Filtered aggregates** (Medium effort, medium value)
   - Backend-specific FILTER WHERE syntax

3. **CTEs** (Medium effort, medium value)
   - Improves query readability

4. **Pandas output** (Medium effort, high value for target users)
   - `.to_pandas()` method

### Consider for v1.1+
1. **Window functions** (High effort, high value)
2. **Auto-codegen** (Very high effort, very high value)
3. **Polars output** (Medium effort, medium value)
4. **Async support** (Very high effort, medium value)
5. **Query caching** (Medium effort, medium value)

### Explicitly Don't Build
1. Write operations (INSERT/UPDATE/DELETE)
2. Relationship management
3. Schema migrations
4. REST/GraphQL APIs
5. Web UIs
6. Materialized view management
7. Built-in caching platform

---

## Conclusion

Cubano occupies a unique position: **purpose-built Python ORM for data warehouse semantic views**, combining:
- The type safety and DX of modern Python (like ibis)
- The simplicity of query builders (like PyPika)
- The semantic abstractions of dbt/Cube.dev
- The read-only focus appropriate for analytical workloads

**Key differentiators:**
1. Immutable, type-safe queries
2. First-class Snowflake/Databricks semantic view support
3. Zero dependencies, drivers as extras
4. Fluent API with field references (no strings)
5. Simple mental model (no complex relationships)

**Success criteria:**
- Match ibis on type safety/DX
- Beat Django ORM on warehouse-specific features
- Simpler than SQLAlchemy for read-only analytics
- Complement dbt (not compete)

**Next steps:**
1. Complete type hints across codebase
2. Add time-based filter helpers
3. Implement filtered aggregates
4. Build comprehensive docs + examples
5. Release v1.0 with core features + 2-3 differentiators
6. Gather feedback, iterate on v1.1 with window functions + codegen
