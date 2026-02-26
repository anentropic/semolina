# Feature Landscape: Cubano v0.2 Codegen & Integration Testing

**Domain:** Data warehouse semantic view code generation and integration testing
**Researched:** 2026-02-17
**Research Mode:** Ecosystem (Codegen Tools, Testing Patterns)
**Overall Confidence:** MEDIUM (WebSearch-based; partially verified with official docs)

## Executive Summary

v0.2 faces five distinct feature categories: Python metadata extraction (HIGH confidence, Cubano handles this via `SemanticViewMeta`), multi-backend SQL generation (HIGH, Snowflake AGG/Databricks MEASURE documented), schema validation (MEDIUM, patterns known but require Snowflake/Databricks introspection APIs), integration testing (MEDIUM, pytest patterns established but warehouse connectivity required), and documentation auto-generation (HIGH, standard tools available).

The ecosystem strongly favors **template-based codegen** (Jinja2) over AST/reflection approaches due to maintainability, **pytest fixtures** for test database setup, and **pdoc/Sphinx** for documentation. Common pitfalls center on SQL dialect drift (mixing Snowflake/Databricks syntax), circular relationship validation, and schema staleness in generated code.

For v0.2 MVP: prioritize template-based SQL generation + mock-based integration tests. Defer real warehouse connectivity and schema validation to v0.3.

---

## Table Stakes

Features users expect. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Confidence | Notes |
|---------|--------------|-----------|------------|-------|
| **Parse Python SemanticView models** | Core value prop: extract metadata from existing Cubano models | Low | HIGH | Already built in `SemanticViewMeta`; v0.2 just needs to traverse `_fields` and `_view_name` |
| **Generate CREATE SEMANTIC VIEW SQL** | v0.2 scope: Snowflake AGG + Databricks MEASURE syntax | Medium | MEDIUM | Both platforms documented; requires handling FACTS/DIMENSIONS/METRICS clause ordering |
| **Generate multiple SQL dialects** | Single codebase → Snowflake + Databricks; avoid rewrite | High | MEDIUM | Existing `Dialect` architecture supports this; must handle quote chars and metric functions |
| **Validate generated SQL compiles** | Catch syntax errors, missing fields before deploying | Medium | MEDIUM | Can validate locally (AST parse) or via warehouse introspection (deferred to v0.3) |
| **Execute integration tests** | Verify generated views work in actual warehouse | High | MEDIUM | Requires pytest + warehouse connection; patterns known but needs fixture setup |
| **Document generated code** | Auto-generate API reference from docstrings | Low | HIGH | pdoc/Sphinx handle this; Cubano models use docstrings in Field classes |

---

## Differentiators

Features that set product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Confidence | Notes |
|---------|-------------------|-----------|------------|-------|
| **Validate against live warehouse schema** | Catch drift between generated view and actual table structure | High | MEDIUM | Snowflake Python Connector + `sqlalchemy.MetaData()` can introspect; caching critical (expensive calls) |
| **Generate CREATE TABLE from models** | Extend beyond semantic views to table DDL | High | LOW | Beyond v0.2 scope; different DDL patterns for each backend |
| **Type-safe query generation** | Generate Python query DSL from semantic view definitions | Medium | LOW | Possible extension; not in current v0.2 roadmap |
| **CI/CD publishing pipeline** | Auto-publish generated views to warehouse on PR/commit | High | MEDIUM | GitHub Actions pattern known; requires credentials in CI environment |
| **Query result validation** | Assert query returns expected rows, types, aggregations | Medium | MEDIUM | pytest pattern: load fixtures, run query, assert results match expected |

---

## Anti-Features

Features to explicitly NOT build (or defer significantly).

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Full ORM code generation** | Cubano is lightweight by design; ORM models bloat scope | Use existing Pydantic/SQLAlchemy tools if full ORM needed |
| **LLM-based SQL generation** | High error rates (join logic, aggregations, syntax); can't validate without warehouse | Use template-based generation with human-written templates instead |
| **Automatic relationship inference** | Snowflake/Databricks require explicit relationships; no magic | Require users to define relationships in Python models or YAML config |
| **Schema versioning system** | Deferred; complex for v0.2 | Simple approach: track git history of generated views for now |
| **Real-time query execution** | Out of scope; integration tests are offline | Use pytest fixtures with mock data or lightweight test warehouse |

---

## Feature Dependencies

```
Parse Python Models (Table stakes)
  └─ SemanticView metadata extraction (already built)

Generate SQL (Table stakes)
  ├─ Snowflake dialect (table stakes)
  ├─ Databricks dialect (table stakes)
  └─ Validate SQL syntax (table stakes)

Integration Tests (Table stakes)
  ├─ Parse models + Generate SQL (dependencies)
  ├─ pytest fixtures (test data setup)
  └─ Engine.execute() (already built)

Schema Validation (Differentiator)
  └─ Generate SQL + Warehouse introspection (requires Schema extraction)

CI/CD Pipeline (Differentiator)
  ├─ Generate SQL (dependency)
  └─ GitHub Actions workflow (separate tool)
```

---

## MVP Recommendation

### Phase 1: Python → SQL (Core Codegen)

**Rationale:** Unblock v0.2 MVP release; all other features depend on this.

| Feature | Why Include |
|---------|-------------|
| Parse SemanticView models | Already works; small extraction layer |
| Generate Snowflake CREATE SEMANTIC VIEW | Primary backend; AGG syntax established |
| Generate Databricks metric view YAML | Secondary backend; simpler than SQL |
| Validate SQL syntax (local parsing) | Catch gross errors before submitting to warehouse |

**Not Included:** Schema introspection, real warehouse validation, CI/CD pipeline, type-safe query gen

### Phase 2: Integration Testing (Optional for v0.2, Critical for v0.3)

| Feature | Why Include |
|---------|-------------|
| pytest fixtures + MockEngine | Existing infrastructure; fast tests |
| Mock-based integration tests | Test codegen without warehouse connectivity |
| Result validation patterns | Document how to test generated views locally |

**Not Included:** Real warehouse connection tests (deferred to v0.3)

### Phase 3: Documentation (Nice-to-have for v0.2, Standard for v0.3)

| Feature | Why Include |
|---------|-------------|
| Auto-generate API reference | pdoc/Sphinx handles this; low effort |
| Document generated SQL examples | Human examples + tool guidance |

**Defer:** Automated publishing to docs site (v0.3+)

---

## Implementation Patterns

### 1. Metadata Extraction (Already Built)

**Pattern:** Descriptor protocol + `SemanticViewMeta` metaclass

Cubano's existing architecture:
- `SemanticViewMeta.__init_subclass__()` collects Field descriptors into `_fields`
- `_view_name` stored as ClassVar
- `_fields` frozen as `MappingProxyType` (immutable)

**v0.2 codegen task:** Walk `_fields` dict, extract Field type (Metric/Dimension/Fact) and name.

```python
# Existing Cubano code (no changes needed)
class Sales(SemanticView, view='sales'):
    revenue = Metric()
    country = Dimension()

# v0.2 codegen extracts:
Sales._view_name  # 'sales'
Sales._fields     # {'revenue': Metric(), 'country': Dimension()}
```

**Confidence:** HIGH (verified in `/Users/paul/Documents/Dev/Personal/cubano/src/cubano/models.py`)

---

### 2. Template-Based SQL Generation (Industry Standard)

**Pattern:** Jinja2 templates + Python data classes

**Why Jinja2:**
- Feature-rich, well-maintained (Python community standard)
- Supports conditionals, loops, filters, macros (needed for multi-backend support)
- Separates SQL logic from Python code (maintainability)
- LangChain, FastAPI, Trusted Firmware-M use this pattern

**Structure:**

```python
# Extract metadata into data class
@dataclass
class Field:
    name: str
    field_type: str  # 'Metric' | 'Dimension' | 'Fact'
    comment: str = ""

@dataclass
class SemanticViewModel:
    view_name: str
    table_name: str
    fields: list[Field]
    relationships: list[Relationship] = field(default_factory=list)

# Load template, render
from jinja2 import Environment
env = Environment(loader=FileSystemLoader('templates/'))
template = env.get_template('snowflake_semantic_view.sql.jinja2')
sql = template.render(model=view_model)
```

**Templates needed for v0.2:**

| Template | Backend | Output |
|----------|---------|--------|
| `snowflake_semantic_view.sql.jinja2` | Snowflake | CREATE SEMANTIC VIEW with FACTS/DIMENSIONS/METRICS clauses |
| `databricks_metric_view.yaml.jinja2` | Databricks | Metric view YAML definition |

**Confidence:** MEDIUM (WebSearch confirms pattern; requires hands-on implementation)

---

### 3. SQL Dialect Abstraction (Already Designed)

**Pattern:** Strategy pattern via `Dialect` base class

**Existing in Cubano:**
- `Dialect` ABC with `quote_identifier()` and `wrap_metric()`
- `SnowflakeDialect`: double quotes, AGG()
- `DatabricksDialect`: backticks, MEASURE()
- `MockDialect`: Snowflake-compatible

**v0.2 uses existing Dialect classes:**

```python
class CodeGenerator:
    def __init__(self, dialect: Dialect):
        self.dialect = dialect

    def generate_select(self, fields: list[Field]) -> str:
        metrics = [f for f in fields if isinstance(f, Metric)]
        wrapped = [self.dialect.wrap_metric(m.name) for m in metrics]
        return f"SELECT {', '.join(wrapped)}"
```

**Confidence:** HIGH (verified in `/Users/paul/Documents/Dev/Personal/cubano/src/cubano/engines/sql.py`)

---

### 4. Integration Testing with pytest (Industry Standard)

**Pattern:** Fixtures + parametrization + DatabaseFixture

**Existing in Cubano:**
- `conftest.py` with `sales_model`, `sales_fixtures`, `sales_engine` fixtures
- MockEngine for testing without warehouse

**v0.2 extends with:**

```python
# conftest.py additions

@pytest.fixture(scope='session')
def snowflake_engine():
    """Real Snowflake connection (optional for integration tests)."""
    # Lazy import; skip if credentials missing
    try:
        return SnowflakeEngine(
            account=os.getenv('SNOWFLAKE_ACCOUNT'),
            user=os.getenv('SNOWFLAKE_USER'),
            ...
        )
    except ImportError:
        pytest.skip("Snowflake credentials not available")

@pytest.mark.integration
def test_generated_view_in_snowflake(snowflake_engine):
    """Test that codegen-generated view executes correctly."""
    # 1. Parse model
    # 2. Generate SQL
    # 3. Execute against real Snowflake
    # 4. Assert results match expected
    pass
```

**Key pytest libraries for v0.2:**

| Library | Purpose | Confidence |
|---------|---------|------------|
| pytest | Test framework | HIGH |
| pytest-cov | Coverage reporting | HIGH |
| conftest.py fixtures | Test data + connections | HIGH |
| pytest-mark | Skip integration tests by default | MEDIUM |

**Confidence:** HIGH (verified in Cubano's existing test suite)

---

### 5. Documentation Auto-Generation (Industry Standard)

**Pattern:** pdoc or Sphinx + docstring extraction

**For v0.2:**
- pdoc is simpler; requires no config
- Auto-detects Google/NumPy docstring formats
- Generates HTML from Python docstrings

**Cubano's docstring style** (from MEMORY.md):
```python
"""
Summary line on second line after opening quotes.

Extended description if needed.

Args:
    param1: Description

Returns:
    Description of return value
"""
```

**v0.2 approach:**
```bash
# Generate API docs from source
pdoc --html --output-dir docs/ src/cubano/

# OR integrate with MkDocs
mkdocs build
```

**Confidence:** HIGH (pdoc documented; simple to integrate)

---

## Common Pitfalls & Mitigations

### Pitfall 1: SQL Dialect Drift
**Problem:** Mix Snowflake syntax (double quotes, AGG) with Databricks syntax (backticks, MEASURE).
**Why it happens:** Template logic unclear about which backend; human copy-paste errors.
**Prevention:**
- Use Dialect pattern consistently (already designed in Cubano)
- Keep templates separate per backend
- Lint generated SQL post-generation

**v0.2 Flag:** HIGH priority (affects both major backends)

---

### Pitfall 2: Circular Relationship Validation
**Problem:** Snowflake allows transitive relationships but prohibits cycles. v0.2 codegen must detect cycles before submitting to warehouse.
**Why it happens:** Complex relationship graphs; users define A→B, B→C, C→A without realizing.
**Prevention:**
- Build relationship graph at codegen time
- Run cycle detection algorithm (DFS-based)
- Emit clear error: "Circular relationship: A→B→C→A"

**v0.2 Flag:** MEDIUM priority (affects users with complex schemas; Snowflake validation catches it, but early error better)

---

### Pitfall 3: Schema Staleness
**Problem:** Generated views assume specific base table schema; if tables change (columns dropped/renamed), generated view breaks.
**Why it happens:** No schema validation; generated code is static.
**Prevention (v0.2):** Document that users must re-run codegen after table schema changes
**Prevention (v0.3):** Integrate Snowflake `sqlalchemy.MetaData()` introspection with caching

**v0.2 Flag:** LOW priority (defer to v0.3; document manual re-generation)

---

### Pitfall 4: Field Type Mismatch
**Problem:** Codegen assumes all Metric fields use SUM aggregation; user expects AVG.
**Why it happens:** Cubano Field classes don't encode aggregation function; codegen must infer or allow configuration.
**Prevention:**
- Allow optional `aggregation` parameter in Metric class: `revenue = Metric(aggregation='SUM')`
- Default to SUM if not specified
- Document in API reference

**v0.2 Flag:** MEDIUM priority (MVP can default to SUM; enhancement for v0.2.1)

---

### Pitfall 5: Missing Field Documentation
**Problem:** Generated views lack comments explaining dimensions/metrics.
**Why it happens:** Cubano Fields don't capture docstrings; templates can't emit meaningful comments.
**Prevention:**
- Add optional `comment` parameter to Field: `revenue = Metric(comment="Total revenue in USD")`
- Include in template: `PUBLIC ... COMMENT = 'Total revenue in USD'`

**v0.2 Flag:** MEDIUM priority (nice-to-have; defer if time-constrained)

---

## Feature Complexity Assessment

| Feature | Estimated Effort | Risk | MVP Criticality |
|---------|------------------|------|-----------------|
| Parse SemanticView models | 2-4 hours | LOW | CRITICAL |
| Generate Snowflake SQL | 6-8 hours | MEDIUM | CRITICAL |
| Generate Databricks YAML | 4-6 hours | MEDIUM | CRITICAL |
| Validate SQL syntax (local) | 4-6 hours | MEDIUM | HIGH |
| Mock-based integration tests | 4-6 hours | LOW | HIGH |
| Real warehouse integration tests | 8-12 hours | HIGH | DEFER v0.3 |
| Schema validation (introspection) | 8-12 hours | HIGH | DEFER v0.3 |
| Auto-generate docs | 2-3 hours | LOW | NICE-TO-HAVE |
| CI/CD publishing pipeline | 6-8 hours | MEDIUM | DEFER v0.3 |

---

## Architecture Alignment with Cubano

### Existing Cubano Infrastructure That v0.2 Leverages

| Component | Location | Used For | v0.2 Changes |
|-----------|----------|----------|--------------|
| `SemanticViewMeta` | `models.py` | Metadata collection | No changes; codegen reads `_fields` |
| `Dialect` ABC | `engines/sql.py` | Multi-backend support | Extend for codegen (wrap_metric already works) |
| `SQLBuilder` | `engines/sql.py` | SQL generation | Already generates SELECT; codegen uses similar pattern for CREATE VIEW |
| `MockEngine` | `engines/mock.py` | Testing | Already supports test fixtures; v0.2 adds integration test templates |
| `registry` | `registry.py` | Engine lookup | No changes needed |
| `Query` DSL | `query.py` | Query construction | No changes; codegen outputs SQL, not Query objects |

### New Components Required for v0.2

| Component | Purpose | Location |
|-----------|---------|----------|
| `CodeGenerator` class | Main API for codegen | `src/cubano/codegen/__init__.py` |
| `SemanticViewCodegen` | Snowflake codegen | `src/cubano/codegen/snowflake.py` |
| `DatabricksCodegen` | Databricks codegen | `src/cubano/codegen/databricks.py` |
| `FieldValidator` | Local SQL syntax validation | `src/cubano/codegen/validator.py` |
| Jinja2 templates | SQL/YAML templates | `src/cubano/codegen/templates/` |
| Integration test helpers | Pytest fixtures for codegen tests | `tests/test_codegen.py` |

---

## Sources

- [Snowflake CREATE SEMANTIC VIEW Documentation](https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view)
- [Snowflake Semantic View Validation Rules](https://docs.snowflake.com/en/user-guide/views-semantic/validation-rules)
- [Snowflake Overview of Semantic Views](https://docs.snowflake.com/en/user-guide/views-semantic/overview)
- [Databricks Semantic Metadata in Metric Views](https://docs.databricks.com/aws/en/metric-views/data-modeling/semantic-metadata)
- [Code Generation With Jinja2 - Trusted Firmware-M](https://trustedfirmware-m.readthedocs.io/en/latest/design_docs/software/tfm_code_generation_with_jinja2.html)
- [C++ Code Generation using Python and Jinja2](https://markvtechblog.wordpress.com/2024/04/28/code-generation-in-python-with-jinja2/)
- [pdoc – Auto-generate API Documentation](https://pdoc.dev/)
- [How To Test Database Transactions With Pytest And SQLModel](https://pytest-with-eric.com/database-testing/pytest-sql-database-testing/)
- [pytest-databases · PyPI](https://pypi.org/project/pytest-databases/)
- [Streamlining Snowflake SQL Validation via CICD using Python](https://medium.com/@zainafzal003/streamlining-snowflake-sql-validation-via-cicd-using-python-and-snowsql-b7d494105506)
- [Fixing Snowflake Performance Issues with Introspection Caching](https://tech.quantco.com/blog/snowflake-testsuite-performance)
- [SQL Code Generation Common Pitfalls - 2026](https://research.aimultiple.com/text-to-sql/)
