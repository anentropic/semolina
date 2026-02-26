# Phase 5: Snowflake Backend - Research

**Researched:** 2026-02-15
**Domain:** Snowflake Python connector integration and semantic view querying
**Confidence:** HIGH

## Summary

Phase 5 implements the first production backend for Cubano: SnowflakeEngine. The research confirms that the existing architecture (Engine ABC + Dialect pattern) is well-suited for this implementation. The core insight is that MockDialect already uses Snowflake syntax, meaning SQL generation is complete and battle-tested. The primary work is connecting to Snowflake, executing SQL, and handling results.

The snowflake-connector-python library (v4.3.0+) provides a mature, well-documented API with comprehensive authentication options, context manager support, and built-in security features. AGG() syntax for semantic views is validated and ready to use. The architecture decision to make Query.using() store engine names (not instances) enables lazy driver imports, preventing ImportError for users without Snowflake credentials installed.

**Primary recommendation:** Implement SnowflakeEngine as a thin wrapper around snowflake.connector with lazy import, context manager-based connection lifecycle, and comprehensive error translation. Reuse SnowflakeDialect and SQLBuilder from Phase 3. Focus testing on connection management, error handling, and result mapping rather than SQL generation (already covered by MockEngine tests).

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| snowflake-connector-python | >=4.3.0 | Snowflake database driver | Official Snowflake connector with PEP 249 compliance, context manager support, comprehensive auth methods |
| Python standard library | 3.11+ | TYPE_CHECKING, contextlib | Lazy imports and resource management |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8.0.0 | Testing framework | Already in use; mock Snowflake connections for unit tests |
| unittest.mock | stdlib | Connection mocking | Unit tests that don't require real Snowflake warehouse |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| snowflake-connector-python | snowflake-sqlalchemy | SQLAlchemy adds abstraction layer, complicates debugging, heavier dependency footprint |
| Direct connector | Snowpark Python | Snowpark is higher-level API for data processing; Cubano needs low-level SQL execution control |
| unittest.mock | fakesnow | fakesnow (local DB simulation) useful for integration tests but adds dependency; mock is sufficient for unit tests |
| Manual recording | snowflake-vcrpy | VCR.py approach records HTTP interactions for replay; useful for reducing network calls in CI but adds complexity |

**Installation:**

Already configured in pyproject.toml:

```toml
[project.optional-dependencies]
snowflake = [
    "snowflake-connector-python>=4.3.0",
]
```

Install with: `uv pip install -e ".[snowflake]"`

## Architecture Patterns

### Recommended Project Structure

```
src/cubano/engines/
├── base.py              # Engine ABC (exists)
├── sql.py               # Dialect classes + SQLBuilder (exists)
├── mock.py              # MockEngine (exists)
└── snowflake.py         # NEW: SnowflakeEngine

tests/
├── conftest.py          # Shared fixtures
├── test_engines.py      # Engine ABC + MockEngine tests (exists)
└── test_snowflake_engine.py  # NEW: SnowflakeEngine tests
```

### Pattern 1: Lazy Driver Import

**What:** Import snowflake.connector only when SnowflakeEngine is instantiated, not at module load time.

**When to use:** Always, for optional dependencies that should not break library import for users without credentials.

**Example:**

```python
# Source: Python TYPE_CHECKING pattern (PEP 563)
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import snowflake.connector
    from snowflake.connector.connection import SnowflakeConnection

class SnowflakeEngine(Engine):
    def __init__(self, **connection_params: Any) -> None:
        # Lazy import: only imported when SnowflakeEngine() called
        try:
            import snowflake.connector
        except ImportError as e:
            raise ImportError(
                "snowflake-connector-python is required for SnowflakeEngine. "
                "Install with: pip install cubano[snowflake]"
            ) from e

        self._connection_params = connection_params
        self.dialect = SnowflakeDialect()
```

### Pattern 2: Connection Parameters Dictionary

**What:** Accept connection parameters as **kwargs, store internally, resolve at execution time.

**When to use:** Engine initialization should not establish connection; defer connection until execute() called.

**Example:**

```python
# Source: https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-connect
CONNECTION_PARAMETERS = {
    "account": "<account_identifier>",
    "user": "<username>",
    "password": "<password>",
    "warehouse": "<warehouse_name>",  # Optional
    "database": "<database_name>",    # Optional
    "schema": "<schema_name>",        # Optional
}

engine = SnowflakeEngine(**CONNECTION_PARAMETERS)
```

### Pattern 3: Context Manager for Connection Lifecycle

**What:** Use with statement to ensure connections are properly closed even on exception.

**When to use:** Every execute() call should use context manager for connection acquisition.

**Example:**

```python
# Source: https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-example
def execute(self, query: Query) -> list[Any]:
    import snowflake.connector

    with snowflake.connector.connect(**self._connection_params) as conn:
        with conn.cursor() as cur:
            sql = self.to_sql(query)
            cur.execute(sql)
            return cur.fetchall()
```

### Pattern 4: Error Translation

**What:** Catch snowflake.connector.errors exceptions and translate to RuntimeError with context.

**When to use:** Always wrap execute() in try-except to provide helpful error messages.

**Example:**

```python
# Source: https://github.com/snowflakedb/snowflake-connector-python/blob/main/src/snowflake/connector/errors.py
from snowflake.connector.errors import DatabaseError, ProgrammingError

def execute(self, query: Query) -> list[Any]:
    try:
        # ... execute logic
    except ProgrammingError as e:
        raise RuntimeError(
            f"Snowflake query failed: {e.msg} (Error {e.errno}, SQL State {e.sqlstate})"
        ) from e
    except DatabaseError as e:
        raise RuntimeError(f"Snowflake database error: {e.msg}") from e
```

### Pattern 5: Result Row Mapping

**What:** Convert Snowflake cursor results (tuples) to dicts using cursor.description for field names.

**When to use:** fetchall() returns tuples; convert to list[dict] for consistency with MockEngine.

**Example:**

```python
# Source: https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-api
def execute(self, query: Query) -> list[dict[str, Any]]:
    with snowflake.connector.connect(**self._connection_params) as conn:
        with conn.cursor() as cur:
            sql = self.to_sql(query)
            cur.execute(sql)

            # Get column names from cursor.description
            columns = [desc[0] for desc in cur.description]

            # Convert tuples to dicts
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows]
```

### Anti-Patterns to Avoid

- **Embedding credentials in code:** Use environment variables, config files, or secrets manager. Never hardcode account/password.
- **Creating connections in __init__:** Connection creation is expensive and may fail; defer until execute() time.
- **Ignoring connection cleanup:** Always use context managers or explicit close() in finally blocks. Unclosed connections leak resources.
- **String formatting for SQL generation:** Use parameterized queries for WHERE clause values. Identifiers are already quoted by Dialect.quote_identifier().
- **Assuming DataFrame compatibility:** Column names are case-sensitive in Snowflake; quote_identifier() already handles this.
- **Catching generic Exception:** Catch specific snowflake.connector.errors types for actionable error messages.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SQL identifier quoting | Manual quote escaping | SnowflakeDialect.quote_identifier() | Already implemented in Phase 3; handles quote-in-quote escaping (") |
| Connection pooling | Custom pool manager | snowflake.connector.connect() per-request | Snowflake connector handles connection efficiency internally; premature optimization |
| AGG() metric wrapping | Template strings | SnowflakeDialect.wrap_metric() | Already implemented; tested with MockEngine |
| SQL generation | String concatenation | SQLBuilder(SnowflakeDialect).build_select() | Phase 3 implementation covers all query features; reuse it |
| Authentication | Custom auth flow | snowflake.connector auth parameters | Connector supports username/password, MFA, key-pair, OAuth, WIF out of box |
| Error messages | Generic exceptions | snowflake.connector.errors hierarchy | PEP 249 compliant exceptions provide errno, sqlstate, msg for debugging |

**Key insight:** MockEngine already uses SnowflakeDialect for SQL generation. SnowflakeEngine's only new responsibility is connection management and result handling. Reuse everything else from Phase 3.

## Common Pitfalls

### Pitfall 1: ImportError on Library Import

**What goes wrong:** Importing SnowflakeEngine at module level fails for users without snowflake-connector-python installed.

**Why it happens:** Top-level import statements execute when module is loaded, before SnowflakeEngine() is called.

**How to avoid:** Use TYPE_CHECKING guard for type hints, lazy import inside __init__ with helpful ImportError message.

**Warning signs:** Tests fail with "ModuleNotFoundError: No module named 'snowflake'" when snowflake extra not installed.

### Pitfall 2: Unclosed Connections Exhaust Resources

**What goes wrong:** Multiple non-closed connections can exhaust system resources and eventually crash the application.

**Why it happens:** Connection.close() not called due to exceptions or early returns in execute() method.

**How to avoid:** Always use with snowflake.connector.connect() context manager; it guarantees cleanup.

**Warning signs:** Memory usage grows over time; "Too many connections" errors; sessions accumulate in Snowflake warehouse.

### Pitfall 3: Missing Region in Account Parameter

**What goes wrong:** Connection fails with "Account not found" error despite correct account identifier.

**Why it happens:** Snowflake account parameter requires region suffix (e.g., "xy12345.us-east-1") not just account name.

**How to avoid:** Document account parameter format in docstring; include example with region.

**Warning signs:** ProgrammingError during connect() with misleading "incorrect username or password" message.

### Pitfall 4: Case Sensitivity Surprises with Identifiers

**What goes wrong:** Query fails with "Object does not exist" despite correct field names in view definition.

**Why it happens:** Snowflake stores unquoted identifiers as UPPERCASE; queries reference lowercase names.

**How to avoid:** SnowflakeDialect.quote_identifier() already handles this by quoting all identifiers with double quotes, preserving case exactly.

**Warning signs:** SQL works in Snowflake UI but fails through connector; mixed case field names.

### Pitfall 5: Semantic View Querying Restrictions

**What goes wrong:** Query fails with "Invalid AGG() usage" or "Dimension not compatible with metric" errors.

**Why it happens:** AGG() only valid against semantic views; dimensions must have equal/lower granularity than metrics.

**How to avoid:** Document that SnowflakeEngine requires Snowflake semantic views; validate view exists before execution.

**Warning signs:** ProgrammingError with "semantic view" in message; queries work on normal views but fail on semantic views.

### Pitfall 6: WHERE Clause SQL Injection Risk

**What goes wrong:** User-provided filter values enable SQL injection attacks if string-formatted into WHERE clauses.

**Why it happens:** Identifiers (field names) are quoted by Dialect; VALUES need parameterization.

**How to avoid:** Phase 5 scope is limited to AGG() and GROUP BY ALL; WHERE clause rendering (from Q objects) is deferred to future phase. When implemented, use cursor.execute() with qmark or pyformat parameter binding.

**Warning signs:** Generated SQL contains unescaped user input in WHERE clause.

## Code Examples

Verified patterns from official sources:

### Connecting to Snowflake with Context Manager

```python
# Source: https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-connect
import snowflake.connector

with snowflake.connector.connect(
    user="<username>",
    password="<password>",
    account="<account_identifier>",
    warehouse="<warehouse_name>",
    database="<database_name>",
    schema="<schema_name>",
) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT AGG(revenue) FROM sales_semantic_view")
        results = cur.fetchall()
```

### Executing Query and Mapping Results to Dicts

```python
# Source: https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-api
with conn.cursor() as cur:
    cur.execute("SELECT AGG(revenue), country FROM sales_view GROUP BY ALL")

    # Get column names from cursor metadata
    columns = [desc[0] for desc in cur.description]

    # Map tuples to dicts
    rows = cur.fetchall()
    result_dicts = [dict(zip(columns, row)) for row in rows]
```

### Handling Snowflake-Specific Exceptions

```python
# Source: https://github.com/snowflakedb/snowflake-connector-python/blob/main/src/snowflake/connector/errors.py
from snowflake.connector.errors import DatabaseError, ProgrammingError

try:
    with snowflake.connector.connect(**params) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
except ProgrammingError as e:
    # SQL syntax error, invalid object reference, etc.
    raise RuntimeError(
        f"Query failed: {e.msg} (Error {e.errno}, SQL State {e.sqlstate})"
    ) from e
except DatabaseError as e:
    # Connection issues, permission errors, etc.
    raise RuntimeError(f"Database error: {e.msg}") from e
```

### Lazy Import Pattern for Optional Dependencies

```python
# Source: Python PEP 563 (TYPE_CHECKING) and typing best practices
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import snowflake.connector

class SnowflakeEngine(Engine):
    def __init__(self, **connection_params: Any) -> None:
        # Import deferred until instantiation
        try:
            import snowflake.connector
        except ImportError as e:
            raise ImportError(
                "snowflake-connector-python is required for SnowflakeEngine. "
                "Install with: pip install cubano[snowflake]"
            ) from e

        self._connection_params = connection_params
        self.dialect = SnowflakeDialect()
```

### Querying Snowflake Semantic Views with AGG()

```python
# Source: https://docs.snowflake.com/en/user-guide/views-semantic/querying
# Direct semantic view query (requires AGG() for metrics)
SELECT AGG(order_average_value), customer_country
FROM tpch_analysis
GROUP BY ALL;

# Generated by SQLBuilder(SnowflakeDialect).build_select(query):
SELECT AGG("revenue"), "country"
FROM "sales_view"
GROUP BY ALL
```

### Authentication Methods

```python
# Source: https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-connect

# Method 1: Username/Password (default)
conn = snowflake.connector.connect(
    user="myuser",
    password="mypassword",
    account="xy12345.us-east-1"
)

# Method 2: Key-Pair Authentication (recommended for production)
conn = snowflake.connector.connect(
    user="myuser",
    account="xy12345.us-east-1",
    authenticator="SNOWFLAKE_JWT",
    private_key_file="~/.ssh/snowflake_private_key.pem",
    private_key_file_pwd="my_passphrase"
)

# Method 3: connections.toml (user config file)
# ~/.config/snowflake/connections.toml (Linux/macOS)
# Then: conn = snowflake.connector.connect(connection_name="myconnection")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| DataFrame.to_sql() | write_pandas() | v2.0.0+ (2022) | 20% faster bulk loads for 10GB+ datasets; optimized chunking and compression |
| Separate AGG functions | AGG() wrapper | Semantic views GA (2024) | Unified metric aggregation syntax; MIN/MAX/ANY_VALUE equivalent to AGG() |
| Manual quote escaping | SnowflakeDialect.quote_identifier() | Phase 3 (complete) | SQL injection prevention via proper escaping; case preservation |
| Python 3.8 support | Python 3.11+ required | v4.0.0 (2024) | Cubano targets 3.11+ for performance and typing improvements |
| Global connection pool | Per-request context managers | Recommended pattern | Simpler lifecycle; connection reuse handled by Snowflake internally |

**Deprecated/outdated:**

- **Embedding private keys as strings:** Security risk; use private_key_file parameter instead (added v2.2.0, 2020)
- **SQLAlchemy for simple queries:** Adds complexity without benefit for Cubano's use case; direct connector preferred
- **qmark binding for IN operator:** Not supported; use pyformat/format for WHERE ... IN clauses (limitation documented)
- **ocsp_fail_open=False (strict):** Changed to True by default in v1.8.0+ for better availability vs strict security tradeoff

## Open Questions

1. **Should SnowflakeEngine support connection pooling in __init__?**
   - What we know: snowflake-connector-python supports connection pooling via PooledSnowflakeConnection
   - What's unclear: Whether per-request connections are sufficient performance for typical Cubano use cases
   - Recommendation: Start with per-request connections (simpler); add pooling in Phase 6+ if benchmarking shows performance issue

2. **Should WHERE clause rendering be included in Phase 5?**
   - What we know: Query._filters stores Q objects; Q-to-SQL translation not implemented yet
   - What's unclear: Whether semantic view WHERE clauses have special requirements vs standard SQL
   - Recommendation: Phase 5 scope is AGG() + GROUP BY ALL only; defer WHERE clause to Phase 6 (Filters). MockEngine already uses placeholder "WHERE 1=1"

3. **Should SnowflakeEngine validate semantic view existence before execution?**
   - What we know: Invalid view names raise ProgrammingError during execute()
   - What's unclear: Whether pre-validation (SHOW VIEWS) improves UX vs adds overhead
   - Recommendation: Let execute() fail naturally with ProgrammingError; translate to helpful RuntimeError message

4. **How should async queries (execute_async) be handled?**
   - What we know: snowflake-connector-python supports execute_async() for long-running queries
   - What's unclear: Whether Cubano API should expose async execution or always use synchronous execute()
   - Recommendation: Phase 5 uses synchronous execute() only; defer async support to future phase if requested

5. **Should SnowflakeEngine support Snowpark API instead of connector?**
   - What we know: Snowpark provides higher-level DataFrame API over connector
   - What's unclear: Whether Snowpark adds value for Cubano's SQL-centric use case
   - Recommendation: Use snowflake-connector-python directly; Snowpark is overkill for executing raw SQL queries

## Sources

### Primary (HIGH confidence)

- [Snowflake Python Connector Documentation](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector) - Official connector guide
- [Connecting to Snowflake with Python Connector](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-connect) - Connection parameters, authentication methods
- [Python Connector API Reference](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-api) - Cursor methods, result handling, type mappings
- [Querying Semantic Views](https://docs.snowflake.com/en/user-guide/views-semantic/querying) - AGG() function usage, GROUP BY ALL requirements
- [AGG Function Reference](https://docs.snowflake.com/en/sql-reference/functions/agg) - Metric aggregation in semantic views
- [Identifier Syntax Rules](https://docs.snowflake.com/en/sql-reference/identifiers-syntax) - Quoting rules, case sensitivity, escaping
- [Snowflake Python Connector Release Notes 2025](https://docs.snowflake.com/en/release-notes/clients-drivers/python-connector-2025) - Version 4.x features and changes
- [snowflake-connector-python GitHub](https://github.com/snowflakedb/snowflake-connector-python) - Error handling, source code reference

### Secondary (MEDIUM confidence)

- [Common Mistakes to Avoid with Snowflake Connector for Python](https://www.aimpointdigital.com/blog/common-mistakes-to-avoid-when-using-the-snowflake-connector-for-python) - Verified best practices from Snowflake consulting firm
- [Using pandas DataFrames with Python Connector](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-pandas) - write_pandas() performance characteristics
- [PEP 810 – Explicit lazy imports](https://peps.python.org/pep-0810/) - Python lazy import patterns
- [Writing Tests for Snowpark Python](https://docs.snowflake.com/en/developer-guide/snowpark/python/testing-python-snowpark) - Testing strategy for Snowflake integrations
- [Python Packaging Guide - pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) - Optional dependencies configuration

### Tertiary (LOW confidence)

- [fakesnow GitHub](https://github.com/tekumara/fakesnow) - Local Snowflake mocking library (alternative to unittest.mock)
- [snowflake-vcrpy Medium Article](https://medium.com/snowflake/snowflake-vcrpy-faster-python-tests-for-snowflake-c7711d3aabe6) - HTTP recording for faster tests (advanced pattern)
- Community discussions on connection pooling, error handling (Stack Overflow, Snowflake Community)

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - Official Snowflake connector documented extensively; already installed in project (v4.3.0)
- Architecture: HIGH - Lazy import, context managers, error translation verified in official docs; patterns match Cubano's Engine ABC design
- Pitfalls: HIGH - Case sensitivity, unclosed connections, AGG() restrictions documented in official Snowflake docs and verified community sources
- Code examples: HIGH - All examples sourced from official Snowflake documentation or verified GitHub repositories

**Research date:** 2026-02-15

**Valid until:** 2026-03-15 (30 days) - Snowflake connector is stable; monthly releases add features but rarely break backward compatibility
