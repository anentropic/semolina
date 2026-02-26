---
phase: quick-9
plan: 9
type: execute
wave: 1
depends_on: []
files_modified:
  - dbt-jaffle-shop/macros/create_snapshot_sales_view.sql
  - dbt-jaffle-shop/dbt_project.yml
  - tests/conftest.py
autonomous: true
requirements: [QUICK-9]

must_haves:
  truths:
    - "dbt-jaffle-shop has no on-run-end hook and no create_snapshot_sales_view macro"
    - "snowflake_engine fixture creates snapshot_sales_data table and snapshot_sales_view in recording mode before yielding"
    - "databricks_engine fixture creates snapshot_sales_data table and snapshot_sales_view in recording mode before yielding"
    - "Both fixtures drop the view and table in teardown after yielding"
    - "Replay mode (MockEngine path) is unchanged"
  artifacts:
    - path: "dbt-jaffle-shop/macros/create_snapshot_sales_view.sql"
      provides: "File does not exist (deleted)"
    - path: "dbt-jaffle-shop/dbt_project.yml"
      provides: "dbt project config without on-run-end section"
      contains: "on-run-end absent"
    - path: "tests/conftest.py"
      provides: "snowflake_engine and databricks_engine fixtures with warehouse setup/teardown in recording mode"
      exports: ["snowflake_engine", "databricks_engine"]
  key_links:
    - from: "tests/conftest.py snowflake_engine"
      to: "snowflake.connector.connect"
      via: "engine._connection_params"
      pattern: "snowflake\\.connector\\.connect\\(\\*\\*engine\\._connection_params\\)"
    - from: "tests/conftest.py databricks_engine"
      to: "databricks.sql.connect"
      via: "engine._connection_params"
      pattern: "databricks\\.sql\\.connect\\(\\*\\*engine\\._connection_params\\)"
---

<objective>
Revert the dbt-based approach for snapshot_sales_view setup (quick-8) and replace it with
pytest session-scoped fixture logic that creates and tears down the warehouse objects directly
from within the snowflake_engine and databricks_engine fixtures.

Purpose: The dbt macro approach couples test infrastructure to dbt run execution order.
Pytest fixtures keep test setup self-contained and are the correct home for test
data lifecycle management.

Output: Deleted dbt macro, clean dbt_project.yml, updated conftest.py fixtures that
create/drop snapshot_sales_data + snapshot_sales_view in recording mode.
</objective>

<execution_context>
@/Users/paul/.claude/get-shit-done/workflows/execute-plan.md
@/Users/paul/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@tests/conftest.py
@src/cubano/engines/snowflake.py
@src/cubano/engines/databricks.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Revert dbt-jaffle-shop snapshot view changes</name>
  <files>dbt-jaffle-shop/macros/create_snapshot_sales_view.sql
dbt-jaffle-shop/dbt_project.yml</files>
  <action>
    Delete `dbt-jaffle-shop/macros/create_snapshot_sales_view.sql` entirely — this file should
    not exist after this task.

    Edit `dbt-jaffle-shop/dbt_project.yml` to remove the `on-run-end` block that was added by
    quick-8. The on-run-end section to remove is:

    ```yaml
    on-run-end:
      - "{{ create_snapshot_sales_view() }}"
    ```

    The restored dbt_project.yml should have no `on-run-end` key at all. Verify the file matches
    the pre-quick-8 state: config-version, name, version, require-dbt-version, dbt-cloud, profile,
    all path settings, clean-targets, vars, seeds, models — with no on-run-end section.
  </action>
  <verify>
    `ls dbt-jaffle-shop/macros/` shows only `cents_to_dollars.sql` and `generate_schema_name.sql`
    (create_snapshot_sales_view.sql absent).
    `grep -c "on-run-end" dbt-jaffle-shop/dbt_project.yml` returns 0.
  </verify>
  <done>
    create_snapshot_sales_view.sql deleted. dbt_project.yml contains no on-run-end hook.
    `ls dbt-jaffle-shop/macros/` confirms only the two original macros remain.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add warehouse setup/teardown to snowflake_engine and databricks_engine fixtures</name>
  <files>tests/conftest.py</files>
  <action>
    Modify `snowflake_engine` and `databricks_engine` in `tests/conftest.py` to create the
    staging table and semantic/metric view in recording mode before yielding the engine, then
    drop them in teardown after yielding. Replay mode (MockEngine path) is unchanged.

    The SNAPSHOT_TEST_DATA constant already exists in conftest.py and must NOT be duplicated.

    **For snowflake_engine**, add a helper after the engine is created in the `is_recording` branch.
    Open a new snowflake.connector connection using `engine._connection_params`, execute the two
    DDL statements, then close it. On teardown (after yield), open another connection and execute
    the two DROP statements.

    Snowflake setup DDL (execute as two separate cursor.execute calls):
    ```sql
    CREATE OR REPLACE TABLE snapshot_sales_data (
        revenue NUMBER, cost NUMBER, country VARCHAR, region VARCHAR
    ) AS SELECT column1, column2, column3, column4 FROM VALUES
        (1000, 100, 'US', 'West'), (2000, 200, 'CA', 'East'),
        (500, 50, 'US', 'East'), (1500, 150, 'MX', 'South'), (800, 80, 'CA', 'West')
    ```
    ```sql
    CREATE OR REPLACE SEMANTIC VIEW snapshot_sales_view
        TABLES (snapshot_sales_data)
        DIMENSIONS (country = snapshot_sales_data.country, region = snapshot_sales_data.region)
        METRICS (revenue = AGG(snapshot_sales_data.revenue), cost = AGG(snapshot_sales_data.cost))
    ```

    Snowflake teardown DDL (execute as two separate cursor.execute calls, in teardown block):
    ```sql
    DROP VIEW IF EXISTS snapshot_sales_view
    ```
    ```sql
    DROP TABLE IF EXISTS snapshot_sales_data
    ```

    Use snowflake.connector.connect(**engine._connection_params) for both setup and teardown.
    Wrap each block in try/finally: setup failure should call pytest.fail() with the exception
    message; teardown failure should print a warning (matching the pattern already used in
    `snowflake_connection` fixture) without re-raising.

    Both setup and teardown connections should use context managers (`with snowflake.connector.connect(...) as conn, conn.cursor() as cur:`).

    **For databricks_engine**, same structure. Open a databricks.sql.connect connection using
    `engine._connection_params`. The `catalog` key is already present in `_connection_params`
    (set when the engine was created with `catalog=creds.catalog`), so the connection will
    automatically land in the right catalog context.

    Databricks setup DDL (execute as two separate cursor.execute calls):
    ```sql
    CREATE OR REPLACE TABLE snapshot_sales_data (
        revenue BIGINT, cost BIGINT, country STRING, region STRING
    ) AS SELECT column1, column2, column3, column4 FROM VALUES
        (1000, 100, 'US', 'West'), (2000, 200, 'CA', 'East'),
        (500, 50, 'US', 'East'), (1500, 150, 'MX', 'South'), (800, 80, 'CA', 'West')
    ```
    ```sql
    CREATE OR REPLACE METRIC VIEW snapshot_sales_view
    AS SELECT revenue, cost, country, region FROM snapshot_sales_data
    METRICS (revenue DOUBLE, cost DOUBLE)
    DIMENSIONS (country, region)
    ```

    Databricks teardown DDL (execute as two separate cursor.execute calls):
    ```sql
    DROP VIEW IF EXISTS snapshot_sales_view
    ```
    ```sql
    DROP TABLE IF EXISTS snapshot_sales_data
    ```

    Use `databricks.sql.connect(**engine._connection_params)` with context managers
    (`with databricks.sql.connect(...) as conn, conn.cursor() as cur:`). Wrap setup in
    try/finally with pytest.fail() on error; teardown wraps in try/except Exception with print
    warning, no re-raise.

    The `cubano.register("test", engine)` / `cubano.unregister("test")` calls already present
    in each fixture remain unchanged and in their current positions.

    Preserve all existing type annotations. The `is_recording` guard wrapping setup means no
    additional TYPE_CHECKING imports are needed beyond what already exists.

    Run `uv run ruff check tests/conftest.py` and `uv run basedpyright tests/conftest.py`
    after editing to confirm no lint/type errors introduced.
  </action>
  <verify>
    `uv run ruff check tests/conftest.py` — 0 errors.
    `uv run basedpyright tests/conftest.py` — 0 errors.
    `uv run --extra dev pytest tests/ -x -q` — all tests pass (replay mode uses MockEngine,
    setup/teardown code only runs in recording mode so no credentials needed).
    Grep confirms setup DDL present: `grep -c "snapshot_sales_data" tests/conftest.py` >= 4.
    Grep confirms teardown present: `grep -c "DROP VIEW IF EXISTS" tests/conftest.py` >= 2.
  </verify>
  <done>
    snowflake_engine and databricks_engine fixtures each contain warehouse setup (CREATE TABLE +
    CREATE VIEW) before yield and teardown (DROP VIEW + DROP TABLE) after yield, guarded by
    is_recording. All tests pass. Lint and typecheck clean.
  </done>
</task>

</tasks>

<verification>
- `ls dbt-jaffle-shop/macros/` shows only cents_to_dollars.sql and generate_schema_name.sql
- `grep "on-run-end" dbt-jaffle-shop/dbt_project.yml` returns no output
- `grep "snapshot_sales_data" tests/conftest.py` shows CREATE TABLE and DROP TABLE DDL
- `grep "snapshot_sales_view" tests/conftest.py` shows CREATE VIEW and DROP VIEW DDL
- `uv run --extra dev pytest tests/ -x -q` passes (replay mode, no credentials)
- `uv run basedpyright` — 0 errors
- `uv run ruff check` — 0 errors
</verification>

<success_criteria>
The dbt macro and on-run-end hook are fully removed. The pytest fixtures are self-contained:
in recording mode (`--snapshot-update`) they create snapshot_sales_data and snapshot_sales_view
before the test runs, and drop them afterward. Replay mode is unaffected. All quality gates pass.
</success_criteria>

<output>
After completion, create `.planning/quick/9-revert-dbt-jaffle-shop-snapshot-view-cha/9-SUMMARY.md`
</output>
