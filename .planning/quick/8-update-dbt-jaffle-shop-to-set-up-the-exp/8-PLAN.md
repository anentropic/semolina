---
phase: quick-8
plan: 8
type: execute
wave: 1
depends_on: []
files_modified:
  - dbt-jaffle-shop/macros/create_snapshot_sales_view.sql
  - dbt-jaffle-shop/dbt_project.yml
autonomous: true
requirements: []

must_haves:
  truths:
    - "Running `dbt run` on Snowflake target creates snapshot_sales_view as a SEMANTIC VIEW queryable with AGG()"
    - "Running `dbt run` on Databricks target creates snapshot_sales_view as a METRIC VIEW queryable with MEASURE()"
    - "The view contains exactly the 5 SNAPSHOT_TEST_DATA rows (revenue, cost, country, region)"
    - "The macro uses target.type to branch between Snowflake and Databricks DDL"
  artifacts:
    - path: "dbt-jaffle-shop/macros/create_snapshot_sales_view.sql"
      provides: "dbt macro + on-run-end hook logic for both backends"
      contains: "{% macro create_snapshot_sales_view() %}"
    - path: "dbt-jaffle-shop/dbt_project.yml"
      provides: "on-run-end hook registering the macro"
      contains: "on-run-end"
  key_links:
    - from: "dbt_project.yml on-run-end"
      to: "macros/create_snapshot_sales_view.sql"
      via: "{{ create_snapshot_sales_view() }} hook call"
      pattern: "create_snapshot_sales_view"
    - from: "macro target.type branch"
      to: "Snowflake SEMANTIC VIEW / Databricks METRIC VIEW DDL"
      via: "run_query() with appropriate CREATE OR REPLACE SQL"
      pattern: "target\\.type"
---

<objective>
Add a dbt macro that creates `snapshot_sales_view` as the appropriate semantic/metric view
type for each warehouse backend, populated with the 5 SNAPSHOT_TEST_DATA rows.

Purpose: The cubano integration tests (tests/test_snapshot_queries.py) query
`snapshot_sales_view` against real warehouses during `--snapshot-update` recording.
The view must exist with the right structure before snapshot recording runs.

Output:
- `dbt-jaffle-shop/macros/create_snapshot_sales_view.sql` — macro + both DDL branches
- `dbt-jaffle-shop/dbt_project.yml` — on-run-end hook entry
</objective>

<execution_context>
@/Users/paul/.claude/get-shit-done/workflows/execute-plan.md
@/Users/paul/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@tests/conftest.py
@dbt-jaffle-shop/dbt_project.yml
@dbt-jaffle-shop/macros/cents_to_dollars.sql
@src/cubano/engines/sql.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create create_snapshot_sales_view macro</name>
  <files>dbt-jaffle-shop/macros/create_snapshot_sales_view.sql</files>
  <action>
    Create `dbt-jaffle-shop/macros/create_snapshot_sales_view.sql` with a single macro
    `create_snapshot_sales_view()` that branches on `target.type` and runs the
    appropriate DDL via `run_query()`.

    The inline data (5 rows) must match SNAPSHOT_TEST_DATA from tests/conftest.py exactly:
      (1000, 100, 'US', 'West')
      (2000, 200, 'CA', 'East')
      (500,  50,  'US', 'East')
      (1500, 150, 'MX', 'South')
      (800,  80,  'CA', 'West')

    **Snowflake branch (target.type == 'snowflake'):**

    Step 1 — create staging table from VALUES so the semantic view has a real table source:

    ```sql
    CREATE OR REPLACE TABLE snapshot_sales_data (
        revenue NUMBER, cost NUMBER, country VARCHAR, region VARCHAR
    ) AS
    SELECT column1 AS revenue, column2 AS cost, column3 AS country, column4 AS region
    FROM VALUES
        (1000, 100, 'US', 'West'),
        (2000, 200, 'CA', 'East'),
        (500,  50,  'US', 'East'),
        (1500, 150, 'MX', 'South'),
        (800,  80,  'CA', 'West')
    ```

    Step 2 — create semantic view on top of that table:

    ```sql
    CREATE OR REPLACE SEMANTIC VIEW snapshot_sales_view
        TABLES (snapshot_sales_data)
        DIMENSIONS (
            country = snapshot_sales_data.country,
            region  = snapshot_sales_data.region
        )
        METRICS (
            revenue = AGG(snapshot_sales_data.revenue),
            cost    = AGG(snapshot_sales_data.cost)
        )
    ```

    Both SQL strings are passed to `{{ run_query(...) }}` calls (use `{% do run_query(...) %}`
    with do-notation so the result is discarded).

    **Databricks branch (target.type == 'databricks'):**

    Step 1 — create staging table from VALUES:

    ```sql
    CREATE OR REPLACE TABLE snapshot_sales_data (
        revenue BIGINT, cost BIGINT, country STRING, region STRING
    ) AS
    SELECT column1 AS revenue, column2 AS cost, column3 AS country, column4 AS region
    FROM VALUES
        (1000, 100, 'US', 'West'),
        (2000, 200, 'CA', 'East'),
        (500,  50,  'US', 'East'),
        (1500, 150, 'MX', 'South'),
        (800,  80,  'CA', 'West')
    ```

    Step 2 — create metric view on top of that table:

    ```sql
    CREATE OR REPLACE METRIC VIEW snapshot_sales_view
    AS SELECT
        revenue,
        cost,
        country,
        region
    FROM snapshot_sales_data
    METRICS (
        revenue DOUBLE,
        cost    DOUBLE
    )
    DIMENSIONS (
        country,
        region
    )
    ```

    Note on Databricks METRIC VIEW syntax: Databricks Runtime 13.3 LTS+ supports
    `CREATE METRIC VIEW` DDL. The `METRICS` clause declares which columns are measures
    and `DIMENSIONS` declares grouping columns. Use the schema-qualified form if the
    connection has a default catalog/schema set (which it will from DatabricksEngine).

    **Fallback branch:** Use `{{ exceptions.raise_compiler_error(...) }}` for unknown
    target types so dbt fails loudly rather than silently doing nothing.

    Final macro structure:
    ```
    {% macro create_snapshot_sales_view() %}
      {% if target.type == 'snowflake' %}
        {% do run_query("CREATE OR REPLACE TABLE snapshot_sales_data ...") %}
        {% do run_query("CREATE OR REPLACE SEMANTIC VIEW snapshot_sales_view ...") %}
      {% elif target.type == 'databricks' %}
        {% do run_query("CREATE OR REPLACE TABLE snapshot_sales_data ...") %}
        {% do run_query("CREATE OR REPLACE METRIC VIEW snapshot_sales_view ...") %}
      {% else %}
        {{ exceptions.raise_compiler_error("create_snapshot_sales_view: unsupported target type: " ~ target.type) }}
      {% endif %}
    {% endmacro %}
    ```
  </action>
  <verify>
    `cat dbt-jaffle-shop/macros/create_snapshot_sales_view.sql` shows:
    - `{% macro create_snapshot_sales_view() %}` definition
    - `target.type == 'snowflake'` and `target.type == 'databricks'` branches
    - Both `CREATE OR REPLACE TABLE snapshot_sales_data` statements with VALUES
    - `CREATE OR REPLACE SEMANTIC VIEW snapshot_sales_view` (Snowflake)
    - `CREATE OR REPLACE METRIC VIEW snapshot_sales_view` (Databricks)
    - `{% do run_query(...) %}` calls (not `{{ run_query(...) }}`)
    - All 5 data rows present in both VALUE lists
  </verify>
  <done>
    Macro file exists with correct Jinja2 syntax, both DDL branches present,
    all 5 SNAPSHOT_TEST_DATA rows in the VALUES clause of each branch.
  </done>
</task>

<task type="auto">
  <name>Task 2: Register macro as on-run-end hook in dbt_project.yml</name>
  <files>dbt-jaffle-shop/dbt_project.yml</files>
  <action>
    Add an `on-run-end` hook to `dbt-jaffle-shop/dbt_project.yml` that calls the macro.

    Add at project root level (alongside `vars`, `seeds`, `models`):

    ```yaml
    on-run-end:
      - "{{ create_snapshot_sales_view() }}"
    ```

    This runs after all models finish, regardless of whether models succeeded or failed
    (on-run-end always runs). Since the macro is idempotent (CREATE OR REPLACE), running
    it multiple times is safe.

    The updated dbt_project.yml should look like (adding on-run-end after clean-targets):

    ```yaml
    config-version: 2

    name: "jaffle_shop"
    version: "3.0.0"
    require-dbt-version: ">=1.5.0"

    dbt-cloud:
      project-id: 275557

    profile: default

    model-paths: ["models"]
    analysis-paths: ["analyses"]
    test-paths: ["data-tests"]
    seed-paths: ["seeds"]
    macro-paths: ["macros"]
    snapshot-paths: ["snapshots"]

    target-path: "target"
    clean-targets:
      - "target"
      - "dbt_packages"

    on-run-end:
      - "{{ create_snapshot_sales_view() }}"

    vars:
      "dbt_date:time_zone": "America/Los_Angeles"

    seeds:
      jaffle_shop:
        +schema: raw
        jaffle-data:
          +enabled: "{{ var('load_source_data', false) }}"

    models:
      jaffle_shop:
        staging:
          +materialized: view
        marts:
          +materialized: table
    ```
  </action>
  <verify>
    `grep -A2 "on-run-end" dbt-jaffle-shop/dbt_project.yml` shows:
    ```
    on-run-end:
      - "{{ create_snapshot_sales_view() }}"
    ```
  </verify>
  <done>
    dbt_project.yml contains on-run-end hook calling create_snapshot_sales_view().
    `dbt parse` (if available) completes without errors on either target.
  </done>
</task>

</tasks>

<verification>
Manual check (no warehouse needed for syntax validation):

1. `cat dbt-jaffle-shop/macros/create_snapshot_sales_view.sql` — macro present, both branches, 5 rows each
2. `grep -n "on-run-end" dbt-jaffle-shop/dbt_project.yml` — hook present
3. Count data rows: each VALUES clause should have exactly 5 tuples
4. Check `{% do run_query(...) %}` syntax used (not `{{ run_query(...) }}` which would emit output)

When recording warehouse snapshots (`pytest --snapshot-update tests/test_snapshot_queries.py`):
- `dbt run --target snowflake` → snapshot_sales_view exists as SEMANTIC VIEW with 5 rows
- `dbt run --target databricks` → snapshot_sales_view exists as METRIC VIEW with 5 rows
- pytest snapshot tests pass with real engine results matching MockEngine replay
</verification>

<success_criteria>
- `dbt-jaffle-shop/macros/create_snapshot_sales_view.sql` exists and contains both warehouse DDL branches
- `dbt-jaffle-shop/dbt_project.yml` has `on-run-end` hook
- All 5 SNAPSHOT_TEST_DATA rows present in each VALUES clause
- Macro uses `{% do run_query(...) %}` (discards return value) for each DDL statement
- Databricks metric view and Snowflake semantic view use correct CREATE OR REPLACE syntax
- No changes to cubano Python source (pure dbt configuration change)
</success_criteria>

<output>
After completion, create `.planning/quick/8-update-dbt-jaffle-shop-to-set-up-the-exp/8-SUMMARY.md`
using the summary template.
</output>
