# Phase 3: SQL Generation & Mock Backend - Research

**Researched:** 2026-02-15
**Domain:** SQL generation, engine abstraction, mock testing
**Confidence:** HIGH

## Summary

Phase 3 adds SQL generation and MockEngine to enable testing without warehouse connections. The research reveals a clear path: use composable string building (not AST) for SQL generation with dialect-specific quoting, implement Engine ABC for backend abstraction, and leverage GROUP BY ALL for automatic dimension derivation.

**Key findings:**
- Snowflake uses double quotes for identifiers, Databricks uses backticks (with ANSI mode for double quotes)
- Both support GROUP BY ALL to auto-derive grouping from non-aggregated SELECT columns
- AGG(metric) for Snowflake, MEASURE(metric) for Databricks - both wrap metrics identically
- Composable string building (a la SQLAlchemy) is simpler than AST for this use case
- MockEngine should validate query structure and return configurable test data

**Primary recommendation:** Build SQL generator as composable string builder with dialect classes. Use Engine ABC with to_sql(query) abstract method. MockEngine validates structure and returns fixtures.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| abc | stdlib | Engine base class | Python standard for interface definition |
| dataclasses | stdlib | Frozen SQL components | Immutability, zero dependencies |
| pytest | dev dep | Testing MockEngine | Already in use for Phases 1-2 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing | stdlib | Type hints for SQL components | All modules need Protocol, ABC typing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| String builder | sqlglot AST | AST adds parsing/transpilation complexity for limited benefit |
| String builder | SQLAlchemy Core | Heavy dependency (800+ KB) for simple SQL generation |
| Custom quoting | Third-party lib | No zero-dependency option for identifier quoting |

**Installation:**
Zero new dependencies - all stdlib for Phase 3.

## Architecture Patterns

### Recommended Project Structure
```
src/cubano/
├── engines/
│   ├── __init__.py         # Engine ABC, MockEngine, exports
│   ├── base.py             # Engine ABC base class
│   ├── mock.py             # MockEngine implementation
│   └── sql.py              # SQL generation helpers (Dialect, quote_identifier)
├── fields.py               # Existing - no changes needed
├── filters.py              # Existing - no changes needed
├── models.py               # Existing - no changes needed
└── query.py                # Update to_sql() and fetch() stubs
```

### Pattern 1: Composable SQL Builder
**What:** Generate SQL by composing immutable string fragments, not building an AST

**When to use:** When SQL structure is known and simple (SELECT...FROM...WHERE...GROUP BY...ORDER BY...LIMIT)

**Why not AST:** AST requires parsing/traversal overhead. SQLAlchemy, PyPika, and other successful query builders use composable objects that render to strings, not AST.

**Example:**
```python
# Composable approach (recommended)
class SQLBuilder:
    def __init__(self, dialect: Dialect):
        self.dialect = dialect

    def build_select(self, query: Query) -> str:
        parts = []
        parts.append(self._select_clause(query))
        parts.append(self._from_clause(query))
        if query._filters:
            parts.append(self._where_clause(query))
        if query._dimensions:
            parts.append("GROUP BY ALL")
        if query._order_by_fields:
            parts.append(self._order_by_clause(query))
        if query._limit_value:
            parts.append(f"LIMIT {query._limit_value}")
        return "\n".join(parts)
```

### Pattern 2: Engine ABC with Dialect Injection
**What:** Abstract base class defining engine interface, with dialect-specific SQL generation

**When to use:** When multiple backends need different SQL syntax but same interface

**Example:**
```python
from abc import ABC, abstractmethod

class Engine(ABC):
    """
    Abstract base class for query execution backends.

    Subclasses implement dialect-specific SQL generation and execution.
    """

    @abstractmethod
    def to_sql(self, query: Query) -> str:
        """
        Generate SQL for query using backend-specific dialect.

        Args:
            query: Query to convert to SQL

        Returns:
            SQL string
        """
        pass

    @abstractmethod
    def execute(self, query: Query) -> list[Row]:
        """
        Execute query and return results.

        Args:
            query: Query to execute

        Returns:
            List of Row objects
        """
        pass


class MockEngine(Engine):
    """
    Mock engine for testing without warehouse connection.

    Validates query structure and returns configurable test data.
    """

    def __init__(self, fixtures: dict[str, list[dict]] | None = None):
        self.fixtures = fixtures or {}
        self.dialect = MockDialect()

    def to_sql(self, query: Query) -> str:
        # Validate then generate mock SQL
        query._validate_for_execution()
        builder = SQLBuilder(self.dialect)
        return builder.build_select(query)

    def execute(self, query: Query) -> list[Row]:
        # Return fixture data or empty list
        sql = self.to_sql(query)  # Validates structure
        # Extract view name from query, return fixtures[view_name]
        ...
```

### Pattern 3: Dialect Classes for Backend-Specific Syntax
**What:** Encapsulate quoting, wrapping, and dialect quirks in Dialect classes

**When to use:** When backends have different identifier quoting or metric wrapping

**Example:**
```python
class Dialect(ABC):
    """Base dialect for SQL generation."""

    @abstractmethod
    def quote_identifier(self, name: str) -> str:
        """Quote identifier (table, column) for this dialect."""
        pass

    @abstractmethod
    def wrap_metric(self, field_name: str) -> str:
        """Wrap metric field for aggregation."""
        pass


class SnowflakeDialect(Dialect):
    def quote_identifier(self, name: str) -> str:
        # Snowflake uses double quotes, escape internal " as ""
        escaped = name.replace('"', '""')
        return f'"{escaped}"'

    def wrap_metric(self, field_name: str) -> str:
        return f"AGG({self.quote_identifier(field_name)})"


class DatabricksDialect(Dialect):
    def quote_identifier(self, name: str) -> str:
        # Databricks uses backticks, escape internal ` as ``
        escaped = name.replace('`', '``')
        return f'`{escaped}`'

    def wrap_metric(self, field_name: str) -> str:
        return f"MEASURE({self.quote_identifier(field_name)})"


class MockDialect(Dialect):
    def quote_identifier(self, name: str) -> str:
        # Use double quotes like Snowflake for consistency
        escaped = name.replace('"', '""')
        return f'"{escaped}"'

    def wrap_metric(self, field_name: str) -> str:
        # Mock uses AGG() like Snowflake
        return f"AGG({self.quote_identifier(field_name)})"
```

### Pattern 4: GROUP BY ALL Auto-Derivation
**What:** Both Snowflake and Databricks support GROUP BY ALL to automatically group by non-aggregated columns

**When to use:** When dimensions are explicit in SELECT but you want database to derive grouping

**Example:**
```python
# Instead of manually tracking dimensions for GROUP BY:
# SELECT dim1, dim2, AGG(metric) FROM view GROUP BY dim1, dim2

# Use GROUP BY ALL:
# SELECT dim1, dim2, AGG(metric) FROM view GROUP BY ALL

def build_select(self, query: Query) -> str:
    # ...
    if query._dimensions:
        # Both Snowflake and Databricks support GROUP BY ALL
        # Automatically groups by all non-aggregate SELECT expressions
        parts.append("GROUP BY ALL")
    return "\n".join(parts)
```

**Constraint:** Databricks requires Runtime 12.2 LTS+ for GROUP BY ALL. Snowflake has no version constraint.

### Anti-Patterns to Avoid

- **String concatenation for SQL:** Use composable builders with proper quoting, not f-strings or % formatting
- **Manual GROUP BY tracking:** Use GROUP BY ALL instead of manually listing dimension fields
- **Mixing quoting styles:** Each dialect has one correct quoting mechanism - don't mix double quotes and backticks
- **AGG/MEASURE confusion:** AGG is Snowflake-only, MEASURE is Databricks-only - enforce via Dialect class
- **Validating queries during construction:** Defer validation to .to_sql()/.fetch() time (already decided in Phase 2)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SQL parsing | Custom SQL parser | (Not needed) | Only generating SQL, not parsing it |
| AST traversal | Query AST walker | Composable string builder | Simpler, fewer edge cases for known query structure |
| Identifier escaping | Regex-based escape | Dialect.quote_identifier() | Dialect-specific rules (", ``, quotes in names) |
| Connection pooling | Custom pool manager | (Defer to Phase 5/6) | Backend driver concern, not Phase 3 |
| Result set parsing | Custom Row parser | (Defer to Phase 4) | Phase 4's responsibility |

**Key insight:** SQL generation for a known query structure (SELECT...FROM...WHERE...GROUP BY...ORDER BY...LIMIT) is straightforward with composable builders. Avoid over-engineering with AST or full query parsers.

## Common Pitfalls

### Pitfall 1: Incorrect Identifier Quoting
**What goes wrong:** Using single quotes for identifiers, or wrong quote char for dialect

**Why it happens:** SQL confusion - single quotes are for strings, double quotes/backticks for identifiers

**How to avoid:**
- Snowflake: Double quotes ("), escape internal " as ""
- Databricks: Backticks (`), escape internal ` as ``
- Never use single quotes (') for identifiers
- Always use Dialect.quote_identifier() method, never manual quoting

**Warning signs:** `SELECT 'column' FROM table` instead of `SELECT "column" FROM table`

### Pitfall 2: Case Sensitivity in Snowflake
**What goes wrong:** Unquoted identifiers stored as UPPERCASE, quoted identifiers case-sensitive

**Why it happens:** Snowflake normalizes unquoted identifiers to uppercase

**How to avoid:** Always quote identifiers to preserve case exactly as defined in Field.name

**Warning signs:** `SELECT revenue FROM sales` becomes `SELECT REVENUE FROM SALES` internally

### Pitfall 3: Wrong Metric Wrapper for Dialect
**What goes wrong:** Using AGG() in Databricks or MEASURE() in Snowflake

**Why it happens:** Copying examples from wrong dialect

**How to avoid:** Enforce via Dialect.wrap_metric() - only one implementation per dialect

**Warning signs:** SQL syntax errors when executing against real backend

### Pitfall 4: Manual GROUP BY Instead of GROUP BY ALL
**What goes wrong:** Building "GROUP BY dim1, dim2, dim3" manually when dimensions change

**Why it happens:** Traditional SQL thinking, unaware of GROUP BY ALL

**How to avoid:** Always use GROUP BY ALL when dimensions exist - database derives grouping

**Warning signs:** Fragile code that breaks when dimension list changes

### Pitfall 5: Validating Empty Queries During Construction
**What goes wrong:** Raising errors in .metrics()/.dimensions() if query still empty

**Why it happens:** Wanting to fail fast

**How to avoid:** Deferred validation pattern (Phase 2 decision) - only validate in .to_sql()/.fetch()

**Warning signs:** Users can't incrementally build queries without errors

### Pitfall 6: Not Escaping Quotes Inside Identifiers
**What goes wrong:** Identifier named `my"field` generates invalid SQL `"my"field"`

**Why it happens:** Forgetting that quotes can appear inside names

**How to avoid:** Always escape: `my"field` → `"my""field"` (Snowflake) or `` my`field `` → `` `my``field` `` (Databricks)

**Warning signs:** SQL injection vulnerabilities, syntax errors on quoted identifiers

## Code Examples

Verified patterns from official sources:

### Snowflake GROUP BY ALL
```sql
-- Source: https://docs.snowflake.com/en/sql-reference/constructs/group-by
-- Automatically groups by all non-aggregate SELECT expressions
SELECT state, city, SUM(retail_price * quantity) AS gross_revenue
FROM sales
GROUP BY ALL;
-- Equivalent to: GROUP BY state, city
```

### Databricks MEASURE Function
```sql
-- Source: https://docs.databricks.com/aws/en/sql/language-manual/functions/measure
-- MEASURE inherits aggregation from metric view definition
SELECT extract(month from month) as month,
       status,
       measure(total_revenue_per_customer)::bigint AS total_revenue_per_customer
FROM region_sales_metrics
WHERE extract(year FROM month) = 1995
GROUP BY ALL
ORDER BY ALL;
```

### Snowflake AGG Function
```sql
-- Source: https://docs.snowflake.com/en/user-guide/views-semantic/querying
-- AGG evaluates metric defined in semantic view
SELECT customer_market_segment,
       AGG(order_average_value)
FROM tpch_analysis
GROUP BY customer_market_segment
ORDER BY customer_market_segment;
```

### psycopg2 SQL Identifier Composition
```python
# Source: https://www.psycopg.org/docs/sql.html
from psycopg2 import sql

# Safe identifier quoting with format()
query = sql.SQL("SELECT {field} FROM {table} WHERE {pkey} = %s").format(
    field=sql.Identifier('my_name'),
    table=sql.Identifier('some_table'),
    pkey=sql.Identifier('id')
)
# Produces: SELECT "my_name" FROM "some_table" WHERE "id" = %s

# Qualified names (schema.table)
sql.Identifier("schema", "table")  # → "schema"."table"

# Multiple fields with join
sql.SQL(',').join([
    sql.Identifier('field1'),
    sql.Identifier('field2')
])  # → "field1","field2"
```

### SQLAlchemy Dialect Pattern
```python
# Source: SQLAlchemy documentation architecture
# Note: This is architectural pattern, not direct code usage

# Dialect classes handle backend-specific SQL generation
class Dialect:
    def quote_identifier(self, name: str) -> str:
        """Quote identifier for this SQL dialect."""
        raise NotImplementedError

class PostgreSQLDialect(Dialect):
    def quote_identifier(self, name: str) -> str:
        escaped = name.replace('"', '""')
        return f'"{escaped}"'

# Each engine uses its dialect
engine = create_engine('postgresql://...')
# engine.dialect is PostgreSQLDialect instance
```

### PyPika Fluent Query Builder Pattern
```python
# Source: https://pypika.readthedocs.io/en/latest/
# Demonstrates immutable fluent API pattern (similar to Cubano Query)

from pypika import Query, Table

customers = Table('customers')

# Method chaining returns new instances (immutable)
q = Query.from_(customers).select(
    customers.id, customers.fname, customers.lname
).where(
    customers.age > 18
).orderby(
    customers.lname
).limit(10)

# Converts to SQL string
str(q)
# → "SELECT id, fname, lname FROM customers WHERE age > 18 ORDER BY lname LIMIT 10"
```

### MockEngine Fixture Pattern
```python
# Pattern from pytest best practices
# Source: Synthesis of pytest-mock and fixture patterns

import pytest
from cubano.engines import MockEngine
from cubano.models import SemanticView
from cubano.fields import Metric, Dimension

class Sales(SemanticView, view='sales'):
    revenue = Metric()
    country = Dimension()

@pytest.fixture
def mock_engine():
    """Fixture providing MockEngine with test data."""
    fixtures = {
        'sales': [
            {'country': 'US', 'revenue': 1000},
            {'country': 'CA', 'revenue': 500},
        ]
    }
    return MockEngine(fixtures=fixtures)

def test_query_with_mock(mock_engine):
    query = Query().metrics(Sales.revenue).dimensions(Sales.country)

    # to_sql() validates structure without executing
    sql = mock_engine.to_sql(query)
    assert 'AGG("revenue")' in sql
    assert 'GROUP BY ALL' in sql

    # execute() returns fixture data
    results = mock_engine.execute(query)
    assert len(results) == 2
    assert results[0]['country'] == 'US'
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual GROUP BY listing | GROUP BY ALL | Snowflake: standard, Databricks: Runtime 12.2+ (2023) | Simpler SQL, auto-derivation from SELECT |
| String concatenation SQL | Composable builders | ~2015 (SQLAlchemy popularized) | Type-safe, prevents injection |
| Single dialect per library | Dialect abstraction | ~2010s (SQLAlchemy dialects) | One codebase, multiple backends |
| AST-based generation | Composable rendering | Ongoing | AST for transpiling, composables for generation |
| Mock with full DB | Mock engine with fixtures | ~2015 (pytest fixtures) | Fast tests, no external dependencies |

**Deprecated/outdated:**
- f-string or % formatting for SQL: Use composable builders with parameterization
- Manual quote escaping: Use Dialect.quote_identifier()
- Per-backend codebases: Use dialect pattern for shared query builder
- Testing against real DB in unit tests: Use MockEngine for fast, isolated tests

## Open Questions

1. **Should MockEngine support filter execution on fixtures?**
   - What we know: MockEngine needs to return test data for .execute()
   - What's unclear: Does it need to actually filter/aggregate fixtures, or just return raw data?
   - Recommendation: Start simple - return raw fixture data without filtering. Filtering logic validation happens in integration tests against real backends (Phase 5/6).

2. **How should ORDER BY interact with OrderTerm.nulls?**
   - What we know: OrderTerm has NullsOrdering enum (FIRST, LAST, DEFAULT)
   - What's unclear: Do both Snowflake and Databricks support NULLS FIRST/LAST?
   - Recommendation: Research during implementation. If both support it, generate "ORDER BY field DESC NULLS FIRST". If not, Dialect.build_order_by() can omit NULLS clause for backends that don't support it.

3. **Should to_sql() be on Query or Engine?**
   - What we know: Different engines need different SQL (AGG vs MEASURE)
   - What's unclear: Query.to_sql() currently exists (Phase 2 stub) but engine-agnostic SQL doesn't exist
   - Recommendation: Move to_sql() to Engine. Query.to_sql() becomes NotImplementedError with helpful message: "Use engine.to_sql(query) - SQL generation is dialect-specific". Phase 4 adds engine registry, Query.to_sql() can delegate to registered engine.

## Sources

### Primary (HIGH confidence)
- [Snowflake Semantic Views Querying](https://docs.snowflake.com/en/user-guide/views-semantic/querying) - AGG() syntax, GROUP BY behavior
- [Snowflake AGG Function](https://docs.snowflake.com/en/sql-reference/functions/agg) - AGG() definition
- [Snowflake GROUP BY ALL](https://docs.snowflake.com/en/sql-reference/constructs/group-by) - Automatic dimension derivation
- [Snowflake Identifier Requirements](https://docs.snowflake.com/en/sql-reference/identifiers-syntax) - Double quote quoting, case sensitivity
- [Databricks Metric Views](https://docs.databricks.com/aws/en/metric-views/) - MEASURE() syntax overview
- [Databricks MEASURE Function](https://docs.databricks.com/aws/en/sql/language-manual/functions/measure) - MEASURE() definition
- [Databricks GROUP BY ALL](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-groupby) - Runtime 12.2+ requirement
- [Databricks Identifiers](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-identifiers) - Backtick quoting
- [psycopg2 SQL Composition](https://www.psycopg.org/docs/sql.html) - sql.Identifier() pattern
- [Python abc Module](https://docs.python.org/3/library/abc.html) - ABC, abstractmethod

### Secondary (MEDIUM confidence)
- [SQLAlchemy Dialects](https://docs.sqlalchemy.org/en/21/dialects/) - Dialect system architecture (verified from official docs)
- [PyPika Documentation](https://pypika.readthedocs.io/en/latest/) - Fluent API pattern (verified from official docs)
- [Real Python: Preventing SQL Injection](https://realpython.com/prevent-python-sql-injection/) - Parameterized queries best practices
- [SQLite Identifier Quoting](https://sqlite.org/quirks.html) - Double quote escaping pattern
- [Pytest Fixtures Guide 2026](https://devtoolbox.dedyn.io/blog/pytest-fixtures-complete-guide) - Fixture pattern for MockEngine

### Tertiary (LOW confidence)
- [Medium: Snowflake Semantic Views Testing Jan 2026](https://medium.com/@masato.takada/comprehensive-testing-of-snowflakes-new-sql-syntax-for-semantic-views-db4dccb7f7) - Recent AGG() examples
- WebSearch: Python query builder patterns - General patterns, not Cubano-specific
- WebSearch: Mock database testing - General testing strategies

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Zero new dependencies, all stdlib
- Architecture: HIGH - Verified from SQLAlchemy, psycopg2, PyPika official docs
- Snowflake SQL: HIGH - Direct from official Snowflake documentation
- Databricks SQL: HIGH - Direct from official Databricks documentation
- Pitfalls: MEDIUM-HIGH - Synthesized from multiple authoritative sources

**Research date:** 2026-02-15
**Valid until:** ~2026-03-15 (30 days - both Snowflake/Databricks semantic views are stable features, dialects unlikely to change)
