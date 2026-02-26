# Phase 6: Databricks Backend - Research

**Researched:** 2026-02-15
**Domain:** Databricks SQL connector integration and metric view querying
**Confidence:** HIGH

## Summary

Phase 6 implements the second production backend for Cubano: DatabricksEngine. Following the pattern established in Phase 5 (SnowflakeEngine), this implementation leverages the existing architecture (Engine ABC + Dialect pattern) with DatabricksDialect already implemented and tested in Phase 3. The primary work involves connecting to Databricks SQL warehouses, executing SQL with MEASURE() syntax, and handling Unity Catalog three-part naming.

The databricks-sql-connector library (v4.2.5, February 2026) provides a mature, PEP 249-compliant API with comprehensive authentication options (OAuth M2M/U2M, personal access tokens), context manager support, and native parameterized query execution. MEASURE() syntax for metric views is validated and ready to use (requires Databricks Runtime 16.4+). GROUP BY ALL is supported (DBR 12.2 LTS+) for automatic dimension derivation, matching the Snowflake implementation pattern.

The architecture decision from Phase 5 (lazy driver imports via Query.using() storing engine names) enables the same pattern here: databricks-sql-connector only imported when DatabricksEngine is instantiated, preventing ImportError for users without Databricks credentials. Unity Catalog's three-part naming (catalog.schema.view) works transparently through the existing view parameter in SemanticView metaclass.

**Primary recommendation:** Implement DatabricksEngine as a near-identical twin to SnowflakeEngine, differing only in: (1) connector import (`databricks.sql` vs `snowflake.connector`), (2) connection parameter format (`server_hostname`/`http_path` vs `account`/`warehouse`), (3) dialect selection (DatabricksDialect vs SnowflakeDialect). Reuse all patterns from Phase 5: lazy import, context manager lifecycle, error translation, result mapping. Focus testing on Databricks-specific concerns: Unity Catalog naming, MEASURE() syntax, authentication methods.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| databricks-sql-connector | >=4.2.5 | Databricks SQL driver | Official Databricks connector with PEP 249 compliance, context manager support, OAuth authentication, PyArrow support |
| Python standard library | 3.11+ | TYPE_CHECKING, contextlib | Lazy imports and resource management (same as Phase 5) |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8.0.0 | Testing framework | Already in use; mock Databricks connections for unit tests |
| unittest.mock | stdlib | Connection mocking | Unit tests that don't require real Databricks workspace |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| databricks-sql-connector | databricks-connect | databricks-connect is for PySpark notebooks and DataFrame APIs; SQL connector is correct for raw SQL execution |
| databricks-sql-connector | ODBC/pyodbc | ODBC adds C dependencies and platform-specific setup; native Python connector preferred |
| OAuth authentication | Personal access tokens | OAuth M2M recommended for production; PAT simpler for development but less secure |
| Direct connector | databricks-sqlalchemy | SQLAlchemy extracted to separate package (v4.0+); Cubano needs low-level SQL control |

**Installation:**

Already configured in pyproject.toml:

```toml
[project.optional-dependencies]
databricks = [
    "databricks-sql-connector[pyarrow]>=4.2.5",
]
```

Install with: `uv pip install -e ".[databricks]"`

Note: `[pyarrow]` extra enables Arrow-based result fetching for performance optimization with large result sets.

## Architecture Patterns

### Recommended Project Structure

```
src/cubano/engines/
├── base.py              # Engine ABC (exists)
├── sql.py               # Dialect classes + SQLBuilder (exists)
├── mock.py              # MockEngine (exists)
├── snowflake.py         # SnowflakeEngine (Phase 5, exists)
└── databricks.py        # NEW: DatabricksEngine

tests/
├── conftest.py          # Shared fixtures
├── test_engines.py      # Engine ABC + MockEngine tests (exists)
├── test_snowflake_engine.py  # SnowflakeEngine tests (Phase 5, exists)
└── test_databricks_engine.py  # NEW: DatabricksEngine tests
```

### Pattern 1: Lazy Driver Import

**What:** Import databricks.sql only when DatabricksEngine is instantiated, not at module load time.

**When to use:** Always, for optional dependencies that should not break library import for users without credentials.

**Example:**

```python
# Source: Python TYPE_CHECKING pattern (PEP 563), same as Phase 5
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from databricks import sql
    from databricks.sql.client import Connection, Cursor

class DatabricksEngine(Engine):
    def __init__(self, **connection_params: Any) -> None:
        # Lazy import: only imported when DatabricksEngine() called
        try:
            from databricks import sql  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "databricks-sql-connector is required for DatabricksEngine. "
                "Install with: pip install cubano[databricks]"
            ) from e

        self._connection_params = connection_params
        self.dialect = DatabricksDialect()
```

### Pattern 2: Connection Parameters Dictionary

**What:** Accept connection parameters as **kwargs, store internally, resolve at execution time.

**When to use:** Engine initialization should not establish connection; defer connection until execute() called.

**Example:**

```python
# Source: https://docs.databricks.com/aws/en/dev-tools/python-sql-connector
# Databricks connection parameters differ from Snowflake
CONNECTION_PARAMETERS = {
    "server_hostname": "dbc-a1b2345c-d6e7.cloud.databricks.com",  # Required
    "http_path": "/sql/1.0/warehouses/abc123def456",              # Required
    "access_token": "<personal_access_token>",                    # Or use OAuth
    "catalog": "main",                                             # Optional: Unity Catalog default
    "schema": "analytics",                                         # Optional: schema default
}

engine = DatabricksEngine(**CONNECTION_PARAMETERS)
```

**Key differences from Snowflake:**
- `server_hostname` instead of `account`
- `http_path` instead of `warehouse` (references SQL warehouse ID)
- `access_token` instead of `password` (though OAuth preferred for production)
- `catalog` instead of `database` (Unity Catalog three-level namespace)

### Pattern 3: Context Manager for Connection Lifecycle

**What:** Use with statement to ensure connections are properly closed even on exception.

**When to use:** Every execute() call should use context manager for connection acquisition.

**Example:**

```python
# Source: https://docs.databricks.com/aws/en/dev-tools/python-sql-connector
def execute(self, query: Query) -> list[dict[str, Any]]:
    from databricks import sql

    with sql.connect(**self._connection_params) as conn:
        with conn.cursor() as cur:
            sql_text = self.to_sql(query)
            cur.execute(sql_text)
            return cur.fetchall()
```

**Note:** Same pattern as SnowflakeEngine; databricks.sql.connect() returns context manager.

### Pattern 4: Error Translation

**What:** Catch databricks.sql exceptions and translate to RuntimeError with context.

**When to use:** Always wrap execute() in try-except to provide helpful error messages.

**Example:**

```python
# Source: https://github.com/databricks/databricks-sql-python (exc module)
from databricks.sql.exc import Error, DatabaseError, OperationalError

def execute(self, query: Query) -> list[dict[str, Any]]:
    try:
        # ... execute logic
    except DatabaseError as e:
        # SQL syntax errors, invalid objects, semantic issues
        raise RuntimeError(f"Databricks query failed: {e}") from e
    except OperationalError as e:
        # Connection failures, authentication, permissions
        raise RuntimeError(f"Databricks operational error: {e}") from e
    except Error as e:
        # Generic DB API errors
        raise RuntimeError(f"Databricks error: {e}") from e
```

**Key differences from Snowflake:**
- databricks.sql.exc follows PEP 249 DB API exception hierarchy
- Less granular than Snowflake (no errno/sqlstate attributes documented)
- Catch DatabaseError (broad), OperationalError (connection), Error (fallback)

### Pattern 5: Result Row Mapping

**What:** Convert Databricks cursor results (tuples) to dicts using cursor.description for field names.

**When to use:** fetchall() returns tuples; convert to list[dict] for consistency with MockEngine.

**Example:**

```python
# Source: https://docs.databricks.com/aws/en/dev-tools/python-sql-connector
def execute(self, query: Query) -> list[dict[str, Any]]:
    with sql.connect(**self._connection_params) as conn:
        with conn.cursor() as cur:
            sql_text = self.to_sql(query)
            cur.execute(sql_text)

            # Get column names from cursor.description (PEP 249 standard)
            columns = [desc[0] for desc in cur.description]

            # Convert tuples to dicts
            rows = cur.fetchall()
            return [dict(zip(columns, row, strict=True)) for row in rows]
```

**Note:** Identical to SnowflakeEngine pattern; PEP 249 compliance guarantees cursor.description format.

### Pattern 6: Unity Catalog Three-Part Naming

**What:** Support catalog.schema.view naming in SemanticView's view parameter.

**When to use:** Always; Unity Catalog is the standard for Databricks (DBR 12.2 LTS+).

**Example:**

```python
# Source: https://docs.databricks.com/aws/en/data-governance/unity-catalog/
# Three-part name: catalog.schema.view
class Sales(SemanticView, view='main.analytics.sales_metrics'):
    revenue = Metric()
    country = Dimension()

# DatabricksEngine generates:
# SELECT MEASURE(`revenue`), `country`
# FROM `main`.`analytics`.`sales_metrics`
# GROUP BY ALL
```

**Note:** DatabricksDialect.quote_identifier() already handles three-part names (quotes each part separately). SQLBuilder splits view name on `.` and quotes each component.

### Anti-Patterns to Avoid

- **Embedding credentials in code:** Use environment variables, Databricks secrets, or OAuth. Never hardcode tokens.
- **Creating connections in __init__:** Connection creation is expensive and may fail; defer until execute() time.
- **Ignoring connection cleanup:** Always use context managers or explicit close() in finally blocks. Unclosed connections leak resources.
- **String formatting for SQL generation:** Use parameterized queries for WHERE clause values. Identifiers are already quoted by Dialect.quote_identifier().
- **Assuming case insensitivity:** Databricks stores unquoted identifiers as lowercase (opposite of Snowflake's UPPERCASE); always quote via Dialect.
- **Catching generic Exception:** Catch specific databricks.sql.exc types for actionable error messages.
- **Using jobs compute:** Databricks SQL connector only supports SQL warehouses and all-purpose clusters, not jobs compute.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SQL identifier quoting | Manual backtick escaping | DatabricksDialect.quote_identifier() | Already implemented in Phase 3; handles backtick-in-backtick escaping (``) |
| Connection pooling | Custom pool manager | databricks.sql.connect() per-request | Databricks connector handles connection efficiency; pooling adds complexity without proven benefit |
| MEASURE() metric wrapping | Template strings | DatabricksDialect.wrap_metric() | Already implemented; tested with MockEngine in Phase 3 |
| SQL generation | String concatenation | SQLBuilder(DatabricksDialect).build_select() | Phase 3 implementation covers all query features; reuse it |
| Authentication | Custom OAuth flow | databricks.sql auth parameters | Connector supports PAT, OAuth M2M, OAuth U2M out of box; let connector handle token refresh |
| Error messages | Generic exceptions | databricks.sql.exc hierarchy | PEP 249 compliant exceptions provide structured error information |

**Key insight:** DatabricksDialect already exists and is tested. DatabricksEngine's only new responsibility is connection management and result handling. Reuse everything else from Phase 3 and Phase 5 patterns.

## Common Pitfalls

### Pitfall 1: ImportError on Library Import

**What goes wrong:** Importing DatabricksEngine at module level fails for users without databricks-sql-connector installed.

**Why it happens:** Top-level import statements execute when module is loaded, before DatabricksEngine() is called.

**How to avoid:** Use TYPE_CHECKING guard for type hints, lazy import inside __init__ with helpful ImportError message.

**Warning signs:** Tests fail with "ModuleNotFoundError: No module named 'databricks'" when databricks extra not installed.

### Pitfall 2: Unclosed Connections Exhaust Resources

**What goes wrong:** Multiple non-closed connections can exhaust system resources and eventually crash the application.

**Why it happens:** Connection.close() not called due to exceptions or early returns in execute() method.

**How to avoid:** Always use with sql.connect() context manager; it guarantees cleanup.

**Warning signs:** Memory usage grows over time; "Too many connections" errors; active sessions accumulate in Databricks workspace.

### Pitfall 3: Missing http_path or Incorrect Format

**What goes wrong:** Connection fails with "Invalid http_path" or "Endpoint not found" errors.

**Why it happens:** http_path must reference SQL warehouse ID in format `/sql/1.0/warehouses/{warehouse_id}`, not cluster ID.

**How to avoid:** Document http_path format in docstring; include example. Validate format if possible.

**Warning signs:** OperationalError during connect() with "http_path" in error message.

### Pitfall 4: Case Sensitivity with Unquoted Identifiers

**What goes wrong:** Query fails with "Object does not exist" despite correct field names in metric view definition.

**Why it happens:** Databricks stores unquoted identifiers as lowercase (opposite of Snowflake); queries reference mixed case names.

**How to avoid:** DatabricksDialect.quote_identifier() already handles this by quoting all identifiers with backticks, preserving case exactly.

**Warning signs:** SQL works in Databricks SQL editor but fails through connector; mixed case field names.

### Pitfall 5: Metric View Querying Restrictions

**What goes wrong:** Query fails with "MEASURE function is only valid in queries against metric views" or "SELECT * not supported" errors.

**Why it happens:** MEASURE() only valid against Unity Catalog metric views; `SELECT *` explicitly disallowed by Databricks.

**How to avoid:** Document that DatabricksEngine requires Databricks metric views; ensure all fields are explicitly selected (Cubano already does this).

**Warning signs:** DatabaseError with "metric view" or "MEASURE" in message; queries work on normal views but fail on metric views.

### Pitfall 6: GROUP BY ALL Runtime Requirement

**What goes wrong:** Query fails with "GROUP BY ALL not supported" despite correct syntax.

**Why it happens:** GROUP BY ALL requires Databricks Runtime 12.2 LTS or above; older runtimes don't support it.

**How to avoid:** Document DBR 12.2 LTS+ requirement in DatabricksEngine docstring; verify runtime version if possible.

**Warning signs:** DatabaseError with "GROUP BY ALL" in message; queries work with explicit GROUP BY but fail with ALL.

### Pitfall 7: PyArrow Not Installed for Arrow Results

**What goes wrong:** fetchall_arrow() or fetchmany_arrow() methods fail with ImportError.

**Why it happens:** PyArrow is optional dependency in databricks-sql-connector v4.0+.

**How to avoid:** Install with `[pyarrow]` extra in pyproject.toml (already configured). Use standard fetchall() in DatabricksEngine, not Arrow methods.

**Warning signs:** ImportError mentioning "pyarrow" when using Arrow-based fetch methods.

## Code Examples

Verified patterns from official sources:

### Connecting to Databricks with Context Manager

```python
# Source: https://docs.databricks.com/aws/en/dev-tools/python-sql-connector
from databricks import sql

with sql.connect(
    server_hostname="dbc-a1b2345c-d6e7.cloud.databricks.com",
    http_path="/sql/1.0/warehouses/abc123def456",
    access_token="<personal_access_token>",
) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT MEASURE(revenue) FROM main.analytics.sales_metrics")
        results = cur.fetchall()
```

### Executing Query and Mapping Results to Dicts

```python
# Source: https://docs.databricks.com/aws/en/dev-tools/python-sql-connector (PEP 249)
with conn.cursor() as cur:
    cur.execute("SELECT MEASURE(revenue), country FROM sales_metrics GROUP BY ALL")

    # Get column names from cursor metadata (PEP 249 standard)
    columns = [desc[0] for desc in cur.description]

    # Map tuples to dicts
    rows = cur.fetchall()
    result_dicts = [dict(zip(columns, row)) for row in rows]
```

### Handling Databricks-Specific Exceptions

```python
# Source: https://github.com/databricks/databricks-sql-python (PEP 249 compliance)
from databricks import sql
from databricks.sql.exc import DatabaseError, OperationalError, Error

try:
    with sql.connect(**params) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)
            return cur.fetchall()
except DatabaseError as e:
    # SQL syntax error, invalid object reference, etc.
    raise RuntimeError(f"Databricks query failed: {e}") from e
except OperationalError as e:
    # Connection issues, permission errors, etc.
    raise RuntimeError(f"Databricks operational error: {e}") from e
except Error as e:
    # Generic DB API error (fallback)
    raise RuntimeError(f"Databricks error: {e}") from e
```

### Lazy Import Pattern for Optional Dependencies

```python
# Source: Python PEP 563 (TYPE_CHECKING) and typing best practices
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from databricks import sql

class DatabricksEngine(Engine):
    def __init__(self, **connection_params: Any) -> None:
        # Import deferred until instantiation
        try:
            from databricks import sql  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "databricks-sql-connector is required for DatabricksEngine. "
                "Install with: pip install cubano[databricks]"
            ) from e

        self._connection_params = connection_params
        self.dialect = DatabricksDialect()
```

### Querying Databricks Metric Views with MEASURE()

```python
# Source: https://docs.databricks.com/aws/en/metric-views/
# Direct metric view query (requires MEASURE() for metrics)
SELECT MEASURE(total_revenue_per_customer), extract(month from month) as month
FROM main.analytics.region_sales_metrics
WHERE extract(year FROM month) = 1995
GROUP BY ALL
ORDER BY ALL;

# Generated by SQLBuilder(DatabricksDialect).build_select(query):
SELECT MEASURE(`revenue`), `country`
FROM `main`.`analytics`.`sales_metrics`
GROUP BY ALL
```

### Unity Catalog Three-Part Naming

```python
# Source: https://docs.databricks.com/aws/en/data-governance/unity-catalog/
# Three-level namespace: catalog.schema.table
# Each component quoted separately by DatabricksDialect

# Model definition with three-part name
class Sales(SemanticView, view='main.analytics.sales_metrics'):
    revenue = Metric()
    country = Dimension()

# DatabricksDialect quotes each part:
# view='main.analytics.sales_metrics' -> `main`.`analytics`.`sales_metrics`
```

### Authentication Methods

```python
# Source: https://docs.databricks.com/aws/en/dev-tools/python-sql-connector

# Method 1: Personal Access Token (development)
conn = sql.connect(
    server_hostname="dbc-a1b2345c-d6e7.cloud.databricks.com",
    http_path="/sql/1.0/warehouses/abc123",
    access_token="<personal_access_token>"
)

# Method 2: OAuth M2M (recommended for production)
from databricks.sdk.core import oauth_service_principal

conn = sql.connect(
    server_hostname="dbc-a1b2345c-d6e7.cloud.databricks.com",
    http_path="/sql/1.0/warehouses/abc123",
    credentials_provider=oauth_service_principal(
        client_id="<service_principal_client_id>",
        client_secret="<service_principal_secret>"
    )
)

# Method 3: OAuth U2M (user machines only, browser-based)
conn = sql.connect(
    server_hostname="dbc-a1b2345c-d6e7.cloud.databricks.com",
    http_path="/sql/1.0/warehouses/abc123",
    auth_type="databricks-oauth"
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Basic username/password auth | OAuth M2M/U2M | v4.0.0 (2024), end-of-life July 2024 | Improved security; OAuth token refresh handled by connector |
| Inline parameter interpolation | Native parameterized queries | v3.0.0 (2023) | SQL injection prevention; server-side parameter binding for DBR 14.2+ |
| PyArrow bundled | PyArrow optional dependency | v4.0.0 (2024) | Smaller install footprint; users opt-in to Arrow performance |
| SQLAlchemy bundled | Separate databricks-sqlalchemy package | v4.0.0 (2024) | Cleaner separation of concerns; faster connector-only installs |
| Manual quote escaping | DatabricksDialect.quote_identifier() | Phase 3 (complete) | SQL injection prevention; case preservation for identifiers |
| Python 3.8 minimum | Python 3.9 minimum | v4.0.0+ (2024) | Cubano targets 3.11+ for typing and performance |

**Deprecated/outdated:**

- **Basic authentication (username/password):** Reached end-of-life July 10, 2024; use OAuth or personal access tokens
- **Inline parameter style (`use_inline_params=True`):** Use native parameterized queries (v3.0+) for security and performance
- **Jobs compute support:** Never supported; SQL connector only works with SQL warehouses and all-purpose clusters
- **SELECT * from metric views:** Explicitly disallowed; MEASURE() requires explicit column references (Cubano already does this)

## Open Questions

1. **Should DatabricksEngine support hybrid disposition for result fetching?**
   - What we know: v4.2.2 changed default `use_hybrid_disposition` to False; affects result delivery mechanism
   - What's unclear: Whether hybrid disposition provides performance benefits for typical Cubano use cases
   - Recommendation: Use connector defaults (False as of v4.2.2); add configuration parameter later if benchmarking shows benefit

2. **Should WHERE clause rendering be included in Phase 6?**
   - What we know: Query._filters stores Q objects; Q-to-SQL translation not implemented yet (deferred from Phase 5)
   - What's unclear: Whether metric view WHERE clauses have special requirements vs standard SQL
   - Recommendation: Phase 6 scope is MEASURE() + GROUP BY ALL only; defer WHERE clause to future phase (consistent with Phase 5)

3. **Should DatabricksEngine validate metric view existence before execution?**
   - What we know: Invalid view names raise DatabaseError during execute()
   - What's unclear: Whether pre-validation (SHOW VIEWS) improves UX vs adds overhead
   - Recommendation: Let execute() fail naturally with DatabaseError; translate to helpful RuntimeError message (consistent with Phase 5)

4. **Should DatabricksEngine support Arrow-based result fetching?**
   - What we know: fetchall_arrow() provides PyArrow Table results for performance with large datasets
   - What's unclear: Whether Arrow format is worth additional complexity vs standard dict-based results
   - Recommendation: Phase 6 uses standard fetchall() only; defer Arrow optimization to future phase if requested

5. **How should multi-statement transactions be handled?**
   - What we know: v4.2.0+ supports multi-statement transactions; v4.2.1 added `ignore_transactions` config
   - What's unclear: Whether Cubano queries (SELECT-only) need transaction control
   - Recommendation: Ignore transactions (read-only queries don't need ACID guarantees); consider adding transaction support in future phase if needed

## Sources

### Primary (HIGH confidence)

- [Databricks SQL Connector for Python](https://docs.databricks.com/aws/en/dev-tools/python-sql-connector) - Official connector guide
- [databricks-sql-connector PyPI](https://pypi.org/project/databricks-sql-connector/) - Package metadata, version requirements
- [databricks-sql-python GitHub](https://github.com/databricks/databricks-sql-python) - Source code, release notes, parameter documentation
- [Unity Catalog metric views](https://docs.databricks.com/aws/en/metric-views/) - Metric view overview, querying guide
- [MEASURE() function reference](https://docs.databricks.com/aws/en/sql/language-manual/functions/measure) - MEASURE() syntax, requirements, usage
- [GROUP BY ALL syntax](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-groupby) - GROUP BY clause documentation, ALL syntax
- [What is Unity Catalog?](https://docs.databricks.com/aws/en/data-governance/unity-catalog/) - Three-part naming, catalog hierarchy
- [databricks-sql-python Release Notes v4.2.5](https://github.com/databricks/databricks-sql-python/releases) - Breaking changes, authentication updates, feature additions

### Secondary (MEDIUM confidence)

- [Using the Python Connector for Databricks SQL](https://medium.com/@24chynoweth/using-the-python-connector-for-databricks-sql-fca24d432bed) - Community usage patterns
- [Databricks SQL Essentials - GROUP BY ALL](https://rueedlinger.ch/posts/2026/sql_group_by_all/) - GROUP BY ALL usage examples
- [Metric Views in Databricks: A Unified Approach](https://community.databricks.com/t5/community-articles/metric-views-in-databricks-a-unified-approach-to-business/td-p/139468) - Community explanation of metric views
- [Python Packaging Guide - pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) - Optional dependencies configuration

### Tertiary (LOW confidence)

- Community discussions on error handling, connection best practices (Stack Overflow, Databricks Community)
- Medium articles on Unity Catalog structure and naming conventions

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - Official Databricks connector documented extensively; already configured in project (v4.2.5)
- Architecture: HIGH - Lazy import, context managers, error translation verified in official docs; patterns match SnowflakeEngine (Phase 5) design
- Pitfalls: HIGH - Case sensitivity, unclosed connections, MEASURE() restrictions documented in official Databricks docs and verified community sources
- Code examples: HIGH - All examples sourced from official Databricks documentation or verified GitHub repositories

**Research date:** 2026-02-15

**Valid until:** 2026-03-15 (30 days) - Databricks SQL connector is stable; monthly releases add features but rarely break backward compatibility
