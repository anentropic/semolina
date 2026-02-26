# Phase 18: Fix invalid CREATE VIEW examples in first-query tutorial - Research

**Researched:** 2026-02-23
**Domain:** Snowflake CREATE SEMANTIC VIEW / Databricks CREATE METRIC VIEW DDL syntax
**Confidence:** HIGH

## Summary

The current `first-query.md` tutorial (lines 35-56) shows invented DDL syntax for both Snowflake and Databricks. The Snowflake example uses a bare `CREATE SEMANTIC VIEW` with `DIMENSIONS (country, region)` and `METRICS (revenue = AGG(revenue))` -- missing the mandatory `TABLES` clause and the required `table_alias.field_name AS expression` format for dimensions/metrics. The Databricks example uses `CREATE METRIC VIEW ... AS SELECT MEASURE(...) ...` -- but metric views are actually defined in YAML inside `CREATE VIEW ... WITH METRICS LANGUAGE YAML AS $$ ... $$`, not with SQL SELECT syntax.

Both official syntaxes have been verified against current Snowflake and Databricks documentation (Feb 2026). The fix is straightforward: replace the two SQL code blocks with valid DDL that a warehouse engineer would recognize. The surrounding prose ("this model maps to a view like:") will need minor adjustment to introduce the corrected examples naturally.

**Primary recommendation:** Replace the two DDL blocks with minimal but valid examples using official syntax. Keep them focused on the sales domain with `source_table` as placeholder. Snowflake needs `TABLES`, `DIMENSIONS`, and `METRICS` clauses with `table_alias.name AS expr` format. Databricks needs `CREATE VIEW ... WITH METRICS LANGUAGE YAML AS $$ ... $$` wrapping a YAML body with `source`, `dimensions`, and `measures`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Use valid DDL syntax from official Snowflake/Databricks docs, but keep illustrative (placeholder table names like `source_table` are fine)
- Match official syntax closely, even if the examples end up looking significantly different from current ones. Accuracy over familiarity.
- Show a realistic but focused subset of the DDL -- include clauses a user would actually need, skip rarely-used options
- If the Databricks DDL naturally distinguishes facts from dimensions, include a fact column to hint at the concept (the Sales model above doesn't use Fact, but a brief appearance is fine)

### Claude's Discretion
- Whether to include inline SQL comments mapping warehouse concepts to Cubano concepts, based on readability
- Source table design (column names, types) -- should feel natural for a sales domain
- Any adjustments to the surrounding prose ("this model maps to a view like:") based on what the corrected DDL looks like

### Deferred Ideas (OUT OF SCOPE)
- Better documentation for Cubano's `Fact` field type -- Databricks metric views explicitly define "facts" which behave functionally like dimensions (informative distinction). Snowflake users need explanation that they can label some dimensions as facts. Deserves its own how-to or section in models docs.
</user_constraints>

## Correct DDL Syntax

### Snowflake: CREATE SEMANTIC VIEW

**Source:** [Snowflake CREATE SEMANTIC VIEW reference](https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view)

The official syntax (verified from docs):

```sql
CREATE [ OR REPLACE ] SEMANTIC VIEW [ IF NOT EXISTS ] <name>
  TABLES ( logicalTable [ , ... ] )
  [ RELATIONSHIPS ( relationshipDef [ , ... ] ) ]
  [ FACTS ( factExpression [ , ... ] ) ]
  [ DIMENSIONS ( dimensionExpression [ , ... ] ) ]
  [ METRICS ( metricExpression [ , ... ] ) ]
  [ COMMENT = '<comment>' ]
;
```

Key syntax rules:
- **TABLES is mandatory.** Every semantic view must declare at least one logical table.
- **Clause order is fixed.** TABLES, then RELATIONSHIPS, then FACTS, then DIMENSIONS, then METRICS. Violating the order causes an error.
- **At least one DIMENSION or METRIC is required.**
- **All field expressions use `table_alias.field_name AS sql_expression` format.** Example: `sales.country AS country`, `sales.total_revenue AS SUM(revenue)`.
- **Metrics use aggregate functions directly** (SUM, COUNT, AVG, etc.). The `AGG()` function in SELECT queries is different from the definitions.
- **Logical table format:** `alias AS fully.qualified.table.name PRIMARY KEY (col)`.

**Minimal single-table example (from official docs pattern):**

```sql
CREATE OR REPLACE SEMANTIC VIEW sales
  TABLES (
    s AS source_table PRIMARY KEY (id)
  )
  DIMENSIONS (
    s.country AS country,
    s.region AS region
  )
  METRICS (
    s.total_revenue AS SUM(revenue),
    s.total_cost AS SUM(cost)
  )
;
```

**Confidence:** HIGH -- verified directly from [official syntax page](https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view) and [official example](https://docs.snowflake.com/en/user-guide/views-semantic/example).

### Databricks: CREATE VIEW ... WITH METRICS LANGUAGE YAML

**Source:** [Databricks CREATE VIEW reference](https://docs.databricks.com/en/sql/language-manual/sql-ref-syntax-ddl-create-view.html) and [YAML syntax reference](https://docs.databricks.com/aws/en/metric-views/data-modeling/syntax)

The official syntax (verified from docs):

```sql
CREATE [ OR REPLACE ] VIEW <name>
  WITH METRICS
  LANGUAGE YAML
  AS $$
    version: 1.1
    source: <table_name>
    dimensions:
      - name: <dimension_name>
        expr: <sql_expression>
    measures:
      - name: <measure_name>
        expr: <aggregate_sql_expression>
  $$;
```

Key syntax rules:
- **It is `CREATE VIEW`, not `CREATE METRIC VIEW`.** The `WITH METRICS` clause makes it a metric view.
- **`LANGUAGE YAML` is mandatory** when using `WITH METRICS`.
- **The body is YAML** inside `$$ ... $$` delimiters.
- **Top-level YAML keys:** `version` (defaults 1.1), `source` (required), `dimensions` (array), `measures` (array), `filter` (optional), `joins` (optional), `comment` (optional).
- **Each dimension has `name` and `expr`.**
- **Each measure has `name` and `expr`** (expr must contain an aggregate function like SUM, COUNT, etc.).
- **Databricks does NOT have a separate "facts" concept in metric view YAML.** Dimensions serve that role. Cubano's `Fact` type would map to a dimension in Databricks.

**Minimal example (from official docs pattern):**

```sql
CREATE OR REPLACE VIEW sales
  WITH METRICS
  LANGUAGE YAML
  AS $$
    version: 1.1
    source: source_table
    dimensions:
      - name: country
        expr: country
      - name: region
        expr: region
    measures:
      - name: total_revenue
        expr: SUM(revenue)
      - name: total_cost
        expr: SUM(cost)
  $$;
```

**Confidence:** HIGH -- verified directly from [official CREATE VIEW reference](https://docs.databricks.com/en/sql/language-manual/sql-ref-syntax-ddl-create-view.html) and [YAML syntax reference](https://docs.databricks.com/aws/en/metric-views/data-modeling/syntax).

## Current vs. Corrected: What's Wrong

### Snowflake (current, lines 37-44)

```sql
CREATE SEMANTIC VIEW sales
    DIMENSIONS (country, region)
    METRICS (
        revenue = AGG(revenue),
        cost = AGG(cost)
    );
```

**Problems:**
1. Missing `TABLES (...)` clause -- mandatory in real syntax.
2. Dimensions listed as bare names (`country, region`) -- must be `table_alias.name AS expression`.
3. Metrics use `name = AGG(name)` -- actual syntax is `table_alias.name AS SUM(column)` (AGG is a query-time function, not a definition-time function).
4. Missing `OR REPLACE` (optional but conventional).

### Databricks (current, lines 49-56)

```sql
CREATE METRIC VIEW sales AS
    SELECT
        MEASURE(revenue) AS revenue,
        MEASURE(cost) AS cost,
        country,
        region
    FROM source_table;
```

**Problems:**
1. `CREATE METRIC VIEW` is not the DDL command -- it is `CREATE VIEW ... WITH METRICS`.
2. The body is SQL SELECT syntax -- but metric views use YAML, not SQL.
3. `MEASURE()` is a query-time function used in SELECT queries against metric views, not in their definition.
4. Missing `LANGUAGE YAML` clause.
5. Missing `$$ ... $$` delimiters.

## Scope of Changes

### In-scope (first-query.md only)

The phase targets lines 33-56 of `docs/src/tutorials/first-query.md`. This is the section between "In your warehouse, this model maps to a view like:" and the "## 2. Register an engine" heading.

Changes needed:
1. Replace Snowflake DDL block (lines 37-44) with valid `CREATE SEMANTIC VIEW` using TABLES, DIMENSIONS, METRICS.
2. Replace Databricks DDL block (lines 49-56) with valid `CREATE VIEW ... WITH METRICS LANGUAGE YAML` using YAML body.
3. Possibly adjust the prose on line 33 ("this model maps to a view like:") -- since the Databricks example is now YAML-based, the lead-in should acknowledge that.

### Not in scope (other pages with DDL)

The codegen docs (`how-to/codegen.md`) and Snowflake backend docs (`how-to/backends/snowflake.md`) show codegen template output, which uses `TODO` comments by design (since codegen can't infer source tables). Those are intentionally different from "what the warehouse DDL looks like" and should not be changed in this phase.

The explanation page (`explanation/semantic-views.md`) references `CREATE SEMANTIC VIEW` and `CREATE METRIC VIEW` by name with links -- those are fine since "CREATE METRIC VIEW" is a commonly used shorthand even if the formal DDL is `CREATE VIEW ... WITH METRICS`.

## Architecture Patterns

### Pattern: Illustrative DDL in Tutorials

The DDL examples in the tutorial are not runnable code -- they illustrate what the warehouse equivalent looks like. The goal is recognition: a Snowflake user should see the DDL and think "yes, that's what my semantic view looks like." A Databricks user should see the YAML and recognize their metric view definition.

**The examples should:**
- Use the same field names as the Cubano model above (revenue, cost, country, region)
- Use `source_table` as a placeholder (user decision)
- Be syntactically valid per official docs
- Be minimal -- only include clauses needed for the sales model
- Skip rarely-used options (RELATIONSHIPS, FACTS, COMMENT, AI_SQL_GENERATION)

### Pattern: Tab-Aligned Content

MkDocs Material tabbed content requires exact indentation. The SQL/YAML blocks must be indented under the `=== "Snowflake"` and `=== "Databricks"` tabs.

## Common Pitfalls

### Pitfall 1: Confusing query-time syntax with definition-time syntax

**What goes wrong:** Using `AGG()` or `MEASURE()` in DDL examples. These are query-time functions used in `SELECT` statements against semantic/metric views, not in their definitions.
**How to avoid:** In Snowflake definitions, metrics use standard aggregates (`SUM`, `COUNT`, `AVG`). In Databricks YAML, measures use aggregate expressions in `expr`. `AGG()` and `MEASURE()` only appear in SELECT queries.

### Pitfall 2: Mixing Databricks SQL query syntax with DDL

**What goes wrong:** Writing `CREATE METRIC VIEW ... AS SELECT MEASURE(...) FROM ...` -- this conflates the DDL (YAML-based) with SELECT queries.
**How to avoid:** Databricks metric view DDL wraps YAML in `$$ ... $$`. The `MEASURE()` function is only used when querying an existing metric view.

### Pitfall 3: Snowflake clause order

**What goes wrong:** Putting DIMENSIONS before FACTS or METRICS before DIMENSIONS.
**Why it happens:** The clause order (TABLES, RELATIONSHIPS, FACTS, DIMENSIONS, METRICS) must be followed exactly.
**How to avoid:** Always follow the fixed order. For the tutorial, since we skip RELATIONSHIPS and FACTS, the order is TABLES, DIMENSIONS, METRICS.

### Pitfall 4: MkDocs indentation for tabbed content

**What goes wrong:** Code blocks under tab headers lose proper rendering.
**How to avoid:** Tab content blocks (`=== "..."`) require 4-space indentation for their content. Code fences inside tabs must also be indented.

## Code Examples

### Corrected Snowflake DDL (proposed)

```sql
CREATE OR REPLACE SEMANTIC VIEW sales
  TABLES (
    s AS source_table PRIMARY KEY (id)
  )
  DIMENSIONS (
    s.country AS country,
    s.region AS region
  )
  METRICS (
    s.total_revenue AS SUM(revenue),
    s.total_cost AS SUM(cost)
  )
;
```

Note: metric names in the semantic view (`total_revenue`, `total_cost`) don't need to match the Cubano model field names (`revenue`, `cost`) exactly -- Cubano maps by the model's `view="sales"` and field names. But for tutorial clarity, using identical names would reduce confusion.

**Alternative with matching names:**

```sql
CREATE OR REPLACE SEMANTIC VIEW sales
  TABLES (
    s AS source_table PRIMARY KEY (id)
  )
  DIMENSIONS (
    s.country AS country,
    s.region AS region
  )
  METRICS (
    s.revenue AS SUM(revenue),
    s.cost AS SUM(cost)
  )
;
```

### Corrected Databricks DDL (proposed)

```sql
CREATE OR REPLACE VIEW sales
  WITH METRICS
  LANGUAGE YAML
  AS $$
    version: 1.1
    source: source_table
    dimensions:
      - name: country
        expr: country
      - name: region
        expr: region
    measures:
      - name: revenue
        expr: SUM(revenue)
      - name: cost
        expr: SUM(cost)
  $$;
```

### Prose adjustment (proposed)

The current text says "this model maps to a view like:" -- this works for both tabs. No change needed unless the planner decides to differentiate (e.g., "In your warehouse, this model maps to a definition like:").

## Don't Hand-Roll

Not applicable -- this is a documentation-only change. No code, libraries, or tools needed.

## State of the Art

| Feature | Snowflake | Databricks |
|---------|-----------|------------|
| DDL command | `CREATE SEMANTIC VIEW` | `CREATE VIEW ... WITH METRICS` |
| Definition language | SQL clauses | YAML inside `$$ ... $$` |
| Metrics defined with | `table_alias.name AS SUM(col)` | `measures: [{name, expr: SUM(col)}]` |
| Dimensions defined with | `table_alias.name AS col` | `dimensions: [{name, expr: col}]` |
| Facts concept | Yes (FACTS clause, optional) | No (dimensions serve this role) |
| Source table | TABLES clause (mandatory) | `source:` YAML key (mandatory) |
| Relationships | RELATIONSHIPS clause (optional) | `joins:` YAML key (optional) |
| Available since | 2025 (Preview) | Databricks Runtime 16.4+ |

## Open Questions

1. **Metric naming alignment**
   - What we know: Snowflake semantic view metrics use `table_alias.metric_name AS AGG(source_col)`, so the metric name can differ from the source column name. The tutorial's Cubano model uses `revenue = Metric()` and `cost = Metric()`.
   - What's unclear: Should the Snowflake DDL use `s.revenue AS SUM(revenue)` (metric name matches source column) or `s.total_revenue AS SUM(revenue)` (more realistic, but doesn't match the Cubano field name)?
   - Recommendation: Use matching names (`s.revenue`, `s.cost`) for tutorial simplicity. The point is recognition, not a production-quality DDL tutorial.

2. **Fact column hint in Databricks**
   - What we know: User wants to "include a fact column to hint at the concept" if Databricks DDL naturally distinguishes facts from dimensions. Databricks metric views do NOT have a separate facts concept -- dimensions and facts are both dimensions.
   - What's unclear: How to "hint at the concept" when the DDL has no syntactic distinction.
   - Recommendation: Skip the fact hint in Databricks DDL since the YAML has no separate fact concept. This aligns with the deferred idea ("Better documentation for Cubano's Fact field type deserves its own how-to"). Alternatively, add a YAML comment like `# fact-like dimension` next to a column if included, but this seems forced.

## Sources

### Primary (HIGH confidence)
- [Snowflake CREATE SEMANTIC VIEW syntax](https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view) -- full BNF grammar, clause order, required/optional sections
- [Snowflake semantic view example](https://docs.snowflake.com/en/user-guide/views-semantic/example) -- complete working TPC-H example with all clauses
- [Databricks CREATE VIEW reference](https://docs.databricks.com/en/sql/language-manual/sql-ref-syntax-ddl-create-view.html) -- WITH METRICS, LANGUAGE YAML, complete example with YAML body
- [Databricks YAML syntax reference](https://docs.databricks.com/aws/en/metric-views/data-modeling/syntax) -- dimensions/measures structure, version field, source field

### Secondary (MEDIUM confidence)
- [Databricks metric views data modeling](https://docs.databricks.com/aws/en/metric-views/data-modeling/) -- conceptual overview of dimensions vs. measures

### Codebase (HIGH confidence)
- `docs/src/tutorials/first-query.md` -- the file to fix (lines 33-56)
- `src/cubano/codegen/templates/snowflake.sql.jinja2` -- existing codegen template (uses valid TABLES/DIMENSIONS/METRICS structure)
- `src/cubano/codegen/templates/databricks.yaml.jinja2` -- existing codegen template (uses YAML structure, not SQL SELECT)
- `src/cubano/fields.py` -- Fact class definition (lines 630-638), inherits from Field like Metric and Dimension

## Metadata

**Confidence breakdown:**
- DDL syntax accuracy: HIGH -- verified against official docs for both warehouses
- Scope of changes: HIGH -- single file, clearly defined section (lines 33-56)
- Pitfalls: HIGH -- all based on direct observation of current errors vs. official syntax

**Research date:** 2026-02-23
**Valid until:** 2026-06-23 (stable -- DDL syntax changes infrequently)
