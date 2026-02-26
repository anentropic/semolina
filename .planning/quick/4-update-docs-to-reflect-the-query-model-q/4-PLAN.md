---
phase: quick-4
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/guides/first-query.md
  - docs/guides/queries.md
  - docs/guides/filtering.md
  - docs/guides/ordering.md
  - docs/guides/models.md
  - docs/guides/backends/overview.md
  - docs/guides/backends/snowflake.md
  - docs/guides/backends/databricks.md
autonomous: true
requirements: [DOCS-QUERY-REFACTOR]

must_haves:
  truths:
    - "No doc file contains `Query()` as a standalone constructor call"
    - "No doc file contains `from cubano import ... Query ...` in user-facing imports"
    - "No doc file contains `.fetch()` as a method to execute queries"
    - "All query examples use `ModelName.query().method(...).execute()` pattern"
    - "All filter examples use `.where(Q(...))` as the documented public API"
    - "MockEngine prose describes `.execute()` not `.fetch()`"
  artifacts:
    - path: "docs/guides/first-query.md"
      provides: "Introductory guide with corrected Query API"
    - path: "docs/guides/queries.md"
      provides: "Query method reference with corrected API"
    - path: "docs/guides/filtering.md"
      provides: "Filter guide using .where() and Model.query()"
    - path: "docs/guides/ordering.md"
      provides: "Ordering guide using Model.query() and .execute()"
    - path: "docs/guides/models.md"
      provides: "Model guide with corrected query usage in descriptor example"
    - path: "docs/guides/backends/overview.md"
      provides: "Backend overview with corrected unified API example"
    - path: "docs/guides/backends/snowflake.md"
      provides: "Snowflake guide with corrected query example"
    - path: "docs/guides/backends/databricks.md"
      provides: "Databricks guide with corrected query example"
  key_links:
    - from: "docs/guides/first-query.md"
      to: "Model.query()"
      via: "Section 3 (Build a query) and complete example"
      pattern: "Sales\\.query\\(\\)"
    - from: "docs/guides/queries.md"
      to: ".execute()"
      via: "Section 7 (formerly .fetch())"
      pattern: "\\.execute\\(\\)"
    - from: "docs/guides/filtering.md"
      to: ".where()"
      via: "All filter call sites"
      pattern: "\\.where\\(Q\\("
---

<objective>
Update all documentation guides to reflect the Phase 10.1 Query API refactor.

Purpose: The guides were written during Phase 10 using the old procedural `Query()` constructor
and `.fetch()` execution method. Phase 10.1 removed both entirely. Readers following the docs
will get `NameError: name 'Query' is not defined` and `AttributeError: '_Query' has no attribute
'fetch'` errors. This plan corrects every occurrence across all 8 affected guide files.

Output: 8 updated Markdown files where all code examples use `Model.query().execute()` and
prose accurately describes the current public API.
</objective>

<execution_context>
@/Users/paul/.claude/get-shit-done/workflows/execute-plan.md
@/Users/paul/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Update first-query.md, queries.md, and models.md</name>
  <files>
    docs/guides/first-query.md
    docs/guides/queries.md
    docs/guides/models.md
  </files>
  <action>
Apply these precise substitutions to each file:

**docs/guides/first-query.md**

1. Line 48 — prose referencing `.fetch()` in MockEngine note:
   Change: `When your code calls `.fetch()`, the engine returns the matching rows.`
   To:     `When your code calls `.execute()`, the engine returns the matching rows.`

2. Section 3 heading + code block (lines 61-68):
   Change heading: `## 3. Build a query`
   Keep heading as-is (content is the issue).
   Change: `from cubano import Query` → remove this import line entirely
   Change: `query = Query().metrics(Sales.revenue).dimensions(Sales.country)`
   To:     `query = Sales.query().metrics(Sales.revenue).dimensions(Sales.country)`
   Also update preceding prose: `Use `Query` with method chaining...`
   To: `Use `Model.query()` with method chaining...`

3. Section 4 heading + code block (lines 72-78):
   Change heading: `## 4. Execute with `.fetch()``
   To:             `## 4. Execute with `.execute()``
   Change: `results = query.fetch()`
   To:     `results = query.execute()`

5. Complete example block (lines 93-118):
   Change: `from cubano import SemanticView, Metric, Dimension, register, Query`
   To:     `from cubano import SemanticView, Metric, Dimension, register`
   Change: `results = Query().metrics(Sales.revenue).dimensions(Sales.country).fetch()`
   To:     `results = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).execute()`
   Change comment: `# 3. Build and execute query`  (keep as-is, it's still accurate)

**docs/guides/queries.md**

The intro paragraph references `Query` class — update:
   Change: `Cubano's `Query` class gives you a fluent, immutable API...`
   To:     `Cubano's query API gives you a fluent, immutable API...`

Section "The 8 query methods" — update all `Query()` constructor calls to `ModelName.query()`:

1. Section 1 `.metrics()`:
   Change: `from cubano import Query` → remove
   Change: `query = Query().metrics(Sales.revenue)` → `query = Sales.query().metrics(Sales.revenue)`
   Change: `query = Query().metrics(Sales.revenue, Sales.cost)` → `query = Sales.query().metrics(Sales.revenue, Sales.cost)`
   Change: `Query().metrics(Sales.country)  # TypeError:...` → `Sales.query().metrics(Sales.country)  # TypeError:...`

2. Section 2 `.dimensions()`:
   Change: `query = Query().metrics(Sales.revenue).dimensions(Sales.country)` → `query = Sales.query().metrics(Sales.revenue).dimensions(Sales.country)`
   Change: `query = Query().metrics(Sales.revenue).dimensions(Sales.country, Sales.region)` → `query = Sales.query().metrics(Sales.revenue).dimensions(Sales.country, Sales.region)`

3. Section 3 `.filter()`:
   Rename section heading: `### 3. `.filter(condition)`` → `### 3. `.where(condition)``
   Change: `from cubano import Q` (keep, needed)
   Change: `query = Query().metrics(Sales.revenue).filter(Q(country="US"))` → `query = Sales.query().metrics(Sales.revenue).where(Q(country="US"))`
   Change the multi-line example similarly, replacing `Query()` with `Sales.query()` and `.filter(` with `.where(`
   Update prose: `Add a filter condition using a `Q` object. Multiple `.filter()` calls are **ANDed** together:`
   To:            `Add a filter condition using a `Q` object. Multiple `.where()` calls are **ANDed** together:`
   Update cross-ref: `See [Filtering with Q](filtering.md) for the full lookup reference...` (keep as-is)

4. Section 4 `.order_by()`:
   Change all `Query()` → `Sales.query()`

5. Section 5 `.limit(n)`:
   Change: `query = Query().metrics(Sales.revenue).dimensions(Sales.country).limit(10)` → `query = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).limit(10)`

6. Section 6 `.using(name)`:
   Change: `query = Query().metrics(Sales.revenue).using("warehouse")` → `query = Sales.query().metrics(Sales.revenue).using("warehouse")`
   Update prose about engine resolution: `at `.fetch()` time` → `at `.execute()` time`

7. Section 7 rename: `### 7. `.fetch()`` → `### 7. `.execute()``
   Change: `results = Query().metrics(Sales.revenue).dimensions(Sales.country).fetch()` → `results = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).execute()`
   Update prose: ``.fetch()` validates the query...` → ``.execute()` validates the query...`

8. Section 8 `.to_sql()`:
   Change: `sql = Query().metrics(Sales.revenue).dimensions(Sales.country).to_sql()` → `sql = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).to_sql()`
   In the tip block: `query = (Query()` → `query = (Sales.query()`
   In the tip block: `.filter(Q(country="US"))` → `.where(Q(country="US"))`

"Immutable chaining" section:
   Change: `base = Query().metrics(Sales.revenue).dimensions(Sales.country)` → `base = Sales.query().metrics(Sales.revenue).dimensions(Sales.country)`
   Change: `us_only = base.filter(Q(country="US"))` → `us_only = base.where(Q(country="US"))`
   Change: `us_top_10 = base.filter(Q(country="US")).limit(10)` → `us_top_10 = base.where(Q(country="US")).limit(10)`

"Building queries incrementally" section:
   Change: `def add_revenue_filter(query: Query, threshold: int) -> Query:` → `def add_revenue_filter(query, threshold: int):`
   Change inside function: `return query.filter(Q(revenue__gt=threshold))` → `return query.where(Q(revenue__gt=threshold))`
   Change: `base = Query().metrics(Sales.revenue).dimensions(Sales.country)` → `base = Sales.query().metrics(Sales.revenue).dimensions(Sales.country)`
   Change: `results = filtered.fetch()` → `results = filtered.execute()`

**docs/guides/models.md**

In the "How field descriptors work" section:
   Change: `from cubano import Query` → remove
   Change: `query = Query().metrics(Orders.total_revenue, Orders.order_count)` → `query = Orders.query().metrics(Orders.total_revenue, Orders.order_count)`
  </action>
  <verify>
    grep -n "Query()" /Users/paul/Documents/Dev/Personal/cubano/docs/guides/first-query.md | wc -l
    grep -n "Query()" /Users/paul/Documents/Dev/Personal/cubano/docs/guides/queries.md | wc -l
    grep -n "Query()" /Users/paul/Documents/Dev/Personal/cubano/docs/guides/models.md | wc -l
    # All should return 0
  </verify>
  <done>
    - `first-query.md`: no `Query()` calls, no `from cubano import ... Query`, no `.fetch()`, `.execute()` used, `Sales.query()` used
    - `queries.md`: no `Query()` calls, section 3 renamed to `.where()`, section 7 renamed to `.execute()`, all examples use `Sales.query()`
    - `models.md`: descriptor example uses `Orders.query()` with no `Query` import
  </done>
</task>

<task type="auto">
  <name>Task 2: Update filtering.md, ordering.md, and all backend guides</name>
  <files>
    docs/guides/filtering.md
    docs/guides/ordering.md
    docs/guides/backends/overview.md
    docs/guides/backends/snowflake.md
    docs/guides/backends/databricks.md
  </files>
  <action>
**docs/guides/filtering.md**

Replace all `Query()` with `Sales.query()` and `.filter(` with `.where(` and `.fetch()` with `.execute()`:

1. "Basic equality" section:
   Change: `from cubano import Query`  → remove this import line
   Change: `results = Query().metrics(Sales.revenue).filter(Q(country="US")).fetch()`
   To:     `results = Sales.query().metrics(Sales.revenue).where(Q(country="US")).execute()`

2. "Lookup expressions" section (3 examples):
   Change: `query = Query().metrics(Sales.revenue).filter(Q(revenue__gt=1000))`
   To:     `query = Sales.query().metrics(Sales.revenue).where(Q(revenue__gt=1000))`
   (same pattern for the other two examples in this section)

3. "OR composition":
   Change: `results = Query().metrics(Sales.revenue).filter(q).fetch()`
   To:     `results = Sales.query().metrics(Sales.revenue).where(q).execute()`

4. "AND composition":
   Change: `results = Query().metrics(Sales.revenue).filter(q).fetch()`
   To:     `results = Sales.query().metrics(Sales.revenue).where(q).execute()`
   Change multi-line `.filter()` chained example:
   ```python
   results = (Query()
       .metrics(Sales.revenue)
       .filter(Q(country="US"))
       .filter(Q(revenue__gt=500))
       .fetch())
   ```
   To:
   ```python
   results = (Sales.query()
       .metrics(Sales.revenue)
       .where(Q(country="US"))
       .where(Q(revenue__gt=500))
       .execute())
   ```
   Update prose: `Multiple `.filter()` calls are also ANDed together:`
   To:            `Multiple `.where()` calls are also ANDed together:`

5. "NOT negation":
   Change: `results = Query().metrics(Sales.revenue).filter(q).fetch()`
   To:     `results = Sales.query().metrics(Sales.revenue).where(q).execute()`

6. "Complex nesting":
   Change: `results = Query().metrics(Sales.revenue).filter(q).fetch()`
   To:     `results = Sales.query().metrics(Sales.revenue).where(q).execute()`

7. "Multiple `.filter()` calls" section:
   Rename heading: `## Multiple `.filter()` calls` → `## Multiple `.where()` calls`
   Change: `query = Query().metrics(Sales.revenue).dimensions(Sales.country)`
   To:     `query = Sales.query().metrics(Sales.revenue).dimensions(Sales.country)`
   Change: `query = query.filter(Q(region=region_filter))`
   To:     `query = query.where(Q(region=region_filter))`
   Change: `query = query.filter(Q(revenue__gte=min_revenue))`
   To:     `query = query.where(Q(revenue__gte=min_revenue))`
   Change: `results = query.fetch()`
   To:     `results = query.execute()`
   Update prose: `Each `.filter()` call ANDs with the accumulated filter.`
   To:            `Each `.where()` call ANDs with the accumulated filter.`

**docs/guides/ordering.md**

Replace all `Query()` with `Sales.query()` and `.fetch()` with `.execute()`:

1. "Default ascending order": `Query().metrics(Sales.revenue)` → `Sales.query().metrics(Sales.revenue)`, and remove the `from cubano import Query` line.

2. "Explicit ascending": same replacement.

3. "Descending order": same.

4. "NULL handling":
   Change: `from cubano import NullsOrdering, Query`
   To:     `from cubano import NullsOrdering`
   Change both `Query()` constructor calls to `Sales.query()`

5. "Multiple sort fields":
   Change: `query = (Query()` → `query = (Sales.query()`

6. "Ordering and limiting together":
   Change: `query = (Query()` → `query = (Sales.query()`
   Change: `results = query.fetch()` → `results = query.execute()`

7. "OrderTerm objects":
   Change: `query = (Query()` → `query = (Sales.query()`

**docs/guides/backends/overview.md**

1. Import block in "The unified API" section:
   Change: `from cubano import register, Query` → `from cubano import register`

2. Query example at the end of "The unified API" section:
   Change: `results = Query().metrics(Sales.revenue).dimensions(Sales.country).fetch()`
   To:     `results = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).execute()`

3. "Local testing without a warehouse" prose:
   Change: `It accepts fixture data and returns it on `.fetch()``
   To:     `It accepts fixture data and returns it on `.execute()``

**docs/guides/backends/snowflake.md**

1. "Running a query" section:
   Change: `from cubano import Query, SemanticView, Metric, Dimension`
   To:     `from cubano import SemanticView, Metric, Dimension`
   Change: `results = Query().metrics(Sales.revenue).dimensions(Sales.country).fetch()`
   To:     `results = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).execute()`

2. "Backend-specific SQL" note block:
   Change: `sql = engine.to_sql(Query().metrics(Sales.revenue).dimensions(Sales.country))`
   To:     `sql = engine.to_sql(Sales.query().metrics(Sales.revenue).dimensions(Sales.country))`

**docs/guides/backends/databricks.md**

1. "Running a query" section:
   Change: `from cubano import Query`  → remove
   Change: `results = Query().metrics(Sales.revenue).dimensions(Sales.country).fetch()`
   To:     `results = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).execute()`

2. "Backend-specific SQL" note block:
   Change: `sql = engine.to_sql(Query().metrics(Sales.revenue).dimensions(Sales.country))`
   To:     `sql = engine.to_sql(Sales.query().metrics(Sales.revenue).dimensions(Sales.country))`
  </action>
  <verify>
    grep -rn "Query()\|\.fetch()\|from cubano import.*Query" \
      /Users/paul/Documents/Dev/Personal/cubano/docs/guides/filtering.md \
      /Users/paul/Documents/Dev/Personal/cubano/docs/guides/ordering.md \
      /Users/paul/Documents/Dev/Personal/cubano/docs/guides/backends/overview.md \
      /Users/paul/Documents/Dev/Personal/cubano/docs/guides/backends/snowflake.md \
      /Users/paul/Documents/Dev/Personal/cubano/docs/guides/backends/databricks.md
    # Should return no matches
  </verify>
  <done>
    - `filtering.md`: no `Query()`, no `.filter(` in code examples, `.where()` used throughout, `.execute()` used
    - `ordering.md`: no `Query()`, no `.fetch()`, `Sales.query()` used, `from cubano import NullsOrdering` (no Query)
    - `backends/overview.md`: no `Query()` import or constructor, `.execute()` used, MockEngine prose updated
    - `backends/snowflake.md`: no `Query()` import or constructor, `.execute()` used in both code blocks
    - `backends/databricks.md`: no `Query()` import or constructor, `.execute()` used in both code blocks
  </done>
</task>

<task type="auto">
  <name>Task 3: Verify docs build clean with no stale API references</name>
  <files></files>
  <action>
Run a final grep across all docs to confirm zero remaining references to the old API:

```bash
grep -rn "Query()\|\.fetch()\|from cubano import.*Query" /path/to/docs/guides/
```

Then verify the MkDocs build succeeds (catches broken Markdown / bad syntax introduced by edits):

```bash
uv run --group docs mkdocs build --strict
```

If the build fails, inspect the error and fix the offending file. Common issues:
- Unbalanced backtick fences after substitution
- Accidental deletion of a heading or code block delimiter

Do NOT run the full test suite — these are Markdown files, not Python source.
  </action>
  <verify>
    grep -rn "Query()" /Users/paul/Documents/Dev/Personal/cubano/docs/guides/ | wc -l
    # Should be 0
    grep -rn "\.fetch()" /Users/paul/Documents/Dev/Personal/cubano/docs/guides/ | wc -l
    # Should be 0
    grep -rn "\.filter(" /Users/paul/Documents/Dev/Personal/cubano/docs/guides/ | wc -l
    # Should be 0 — all filter calls should use .where()
    uv run --group docs mkdocs build --strict 2>&1 | tail -5
    # Should end with "INFO    -  Documentation built in ..."
  </verify>
  <done>
    - Zero occurrences of `Query()` as a standalone constructor across all guide files
    - Zero occurrences of `.fetch()` as a query execution method
    - `mkdocs build --strict` exits 0 with no warnings
  </done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Grep for old API patterns — all should return 0:
   ```
   grep -rn "Query()" docs/guides/
   grep -rn "\.fetch()" docs/guides/
   grep -rn "from cubano import.*Query" docs/guides/
   ```

2. Grep for new API patterns — should have matches:
   ```
   grep -rn "\.query()" docs/guides/         # Should appear in all 8 files
   grep -rn "\.execute()" docs/guides/        # Should appear in most files
   grep -rn "\.where(Q(" docs/guides/         # Should appear in filtering.md, queries.md
   ```

3. MkDocs builds without errors:
   `uv run --group docs mkdocs build --strict`
</verification>

<success_criteria>
- All 8 guide files updated: `first-query.md`, `queries.md`, `filtering.md`, `ordering.md`, `models.md`, `backends/overview.md`, `backends/snowflake.md`, `backends/databricks.md`
- Zero `Query()` constructor calls in any guide
- Zero `from cubano import ... Query ...` in user-facing imports
- Zero `.fetch()` method calls in any guide
- All filter examples use `.where(Q(...))` as the public API
- MockEngine prose updated to reference `.execute()`
- `mkdocs build --strict` exits 0
</success_criteria>

<output>
After completion, create `.planning/quick/4-update-docs-to-reflect-the-query-model-q/4-SUMMARY.md`
</output>
