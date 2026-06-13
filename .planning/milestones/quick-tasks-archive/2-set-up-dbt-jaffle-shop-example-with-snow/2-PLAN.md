---
phase: quick-02
plan: 2
type: execute
wave: 1
depends_on: []
autonomous: true
files_modified:
  - dbt-jaffle-shop/dbt_project.yml
  - dbt-jaffle-shop/profiles.yml
  - dbt-jaffle-shop/seeds/raw_customers.csv
  - dbt-jaffle-shop/seeds/raw_orders.csv
  - dbt-jaffle-shop/seeds/raw_payments.csv
must_haves:
  truths:
    - "dbt Jaffle Shop project initialized from official template"
    - "Snowflake connection configured with credentials from scripts/connections.toml"
    - "Sample data loaded into Snowflake JAFFLE database"
    - "dbt models transform raw data into analytics-ready tables"
  artifacts:
    - path: "dbt-jaffle-shop/"
      provides: "dbt project directory with models and seeds"
      contains: "dbt_project.yml, models/, seeds/, profiles.yml"
    - path: "dbt-jaffle-shop/profiles.yml"
      provides: "Snowflake connection configuration"
      contains: "account, user, password, warehouse, database, schema, role"
    - path: "dbt-jaffle-shop/seeds/"
      provides: "Raw CSV data files"
      contains: "raw_customers.csv, raw_orders.csv, raw_payments.csv"
  key_links:
    - from: "dbt-jaffle-shop/profiles.yml"
      to: "scripts/connections.toml"
      via: "credential extraction"
      pattern: "SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD"
    - from: "dbt-jaffle-shop/"
      to: "Snowflake JAFFLE database"
      via: "dbt seed and run"
      pattern: "dbt seed && dbt run"
---

<objective>
Set up dbt Jaffle Shop example project with Snowflake backend.

Purpose: Establish a working dbt project connected to Snowflake that demonstrates data transformation workflows using the official Jaffle Shop example.

Output: Fully initialized dbt project in ./dbt-jaffle-shop/ with Snowflake profiles.yml configured and sample data loaded.
</objective>

<execution_context>
@/Users/paul/.claude/get-shit-done/workflows/execute-plan.md
@/Users/paul/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@scripts/connections.toml
</context>

<tasks>

<task type="auto">
  <name>Clone Jaffle Shop and initialize dbt project</name>
  <files>dbt-jaffle-shop/dbt_project.yml, dbt-jaffle-shop/models/, dbt-jaffle-shop/seeds/</files>
  <action>
1. Clone the official Jaffle Shop repository from https://github.com/dbt-labs/jaffle-shop into ./dbt-jaffle-shop/ directory
2. Navigate into dbt-jaffle-shop and install dbt-snowflake: `pip install dbt-snowflake`
3. Verify dbt installation: `dbt --version`
4. Do NOT run dbt seed or dbt run yet (those happen in next task)

Reference the Jaffle Shop README for project structure: the directory should contain models/, seeds/, dbt_project.yml, etc.
  </action>
  <verify>
Directory ./dbt-jaffle-shop/ exists with subdirectories: models/, seeds/, macros/, tests/
dbt_project.yml exists at dbt-jaffle-shop/dbt_project.yml
Three CSV files exist in dbt-jaffle-shop/seeds/: raw_customers.csv, raw_orders.csv, raw_payments.csv
dbt --version returns dbt version >= 1.7
  </verify>
  <done>
dbt Jaffle Shop cloned into ./dbt-jaffle-shop/ directory with all seeds and models, dbt-snowflake installed and verified
  </done>
</task>

<task type="auto">
  <name>Configure profiles.yml with Snowflake credentials from scripts/connections.toml</name>
  <files>dbt-jaffle-shop/profiles.yml</files>
  <action>
1. Read scripts/connections.toml to extract Snowflake credentials:
   - account: "NYXMXAI-YR37878"
   - user: "CUBANO_TEST"
   - password: "as78v8sa7na"
   - warehouse: "COMPUTE_WH"
   - database: "JAFFLE"
   - schema: "PUBLIC"
   - role: "TESTER"

2. Create dbt-jaffle-shop/profiles.yml with dbt-snowflake configuration:
   ```yaml
   jaffle_shop:
     outputs:
       dev:
         type: snowflake
         account: NYXMXAI-YR37878
         user: CUBANO_TEST
         password: as78v8sa7na
         role: TESTER
         database: JAFFLE
         schema: PUBLIC
         warehouse: COMPUTE_WH
         threads: 4
         client_session_keep_alive: False
     target: dev
   ```

3. Ensure file permissions are restricted: `chmod 600 profiles.yml` (sensitive credentials file)
4. Verify connection: `dbt debug` should show successful Snowflake connection
  </action>
  <verify>
File exists at dbt-jaffle-shop/profiles.yml
Contents include all required Snowflake fields: type, account, user, password, role, database, schema, warehouse
dbt debug runs without connection errors
Connection test shows "All checks passed!"
  </verify>
  <done>
profiles.yml configured with valid Snowflake credentials and dbt debug confirms successful connection to JAFFLE database
  </done>
</task>

<task type="auto">
  <name>Load seeds and run dbt models</name>
  <files>dbt-jaffle-shop/seeds/raw_customers.csv, dbt-jaffle-shop/seeds/raw_orders.csv, dbt-jaffle-shop/seeds/raw_payments.csv</files>
  <action>
1. From dbt-jaffle-shop/ directory, load seed data: `dbt seed`
   This uploads CSV files from seeds/ directory to Snowflake as RAW_CUSTOMERS, RAW_ORDERS, RAW_PAYMENTS tables

2. Run dbt models: `dbt run`
   This executes all models in models/ directory to create transformed tables:
   - customers (from raw data + payments)
   - orders (from raw data)
   - etc. (per Jaffle Shop model structure)

3. Run dbt tests (optional but recommended): `dbt test`
   Verifies data quality and model integrity

4. Generate documentation: `dbt docs generate` (optional, sets up for future browsing)

All commands should complete without errors. Monitor output for successful model creation in Snowflake.
  </action>
  <verify>
dbt seed output shows "Seed file resources loaded" with 3 CSV files processed
dbt run output shows all models created successfully (look for "Completed successfully" message)
Query Snowflake to confirm tables exist:
  - SELECT COUNT(*) FROM JAFFLE.PUBLIC.RAW_CUSTOMERS;
  - SELECT COUNT(*) FROM JAFFLE.PUBLIC.CUSTOMERS;
  - SELECT COUNT(*) FROM JAFFLE.PUBLIC.ORDERS;
All tables return row counts > 0
dbt test (if run) shows all tests passing
  </verify>
  <done>
Seeds loaded into Snowflake (RAW_CUSTOMERS, RAW_ORDERS, RAW_PAYMENTS) and all dbt models executed successfully with transformed tables created (CUSTOMERS, ORDERS, etc.)
  </done>
</task>

</tasks>

<verification>
1. Directory structure: Verify ./dbt-jaffle-shop/ contains models/, seeds/, dbt_project.yml
2. Configuration: Verify dbt-jaffle-shop/profiles.yml has all Snowflake credentials
3. Data loaded: Query Snowflake JAFFLE database to confirm RAW_* and transformed tables exist with data
4. Connection working: dbt debug shows successful Snowflake connection
5. Models built: dbt run completes without errors, all models created in JAFFLE.PUBLIC schema
</verification>

<success_criteria>
- [ ] dbt-jaffle-shop directory exists with full Jaffle Shop project files
- [ ] profiles.yml configured with Snowflake NYXMXAI-YR37878 account and JAFFLE database
- [ ] dbt debug shows successful connection ("All checks passed!")
- [ ] dbt seed loaded 3 CSV files into Snowflake as RAW_* tables
- [ ] dbt run executed all models successfully
- [ ] Snowflake tables exist: RAW_CUSTOMERS, RAW_ORDERS, RAW_PAYMENTS, CUSTOMERS, ORDERS (at minimum)
- [ ] All tables contain data (row counts > 0)
</success_criteria>

<output>
After completion, create `.planning/quick/2-set-up-dbt-jaffle-shop-example-with-snow/2-SUMMARY.md`
</output>
