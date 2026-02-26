# How to test against real warehouses

Validate that queries produce correct results against real Snowflake and Databricks
warehouses using snapshot-based recording and replay.

## Understand the recording/replay pattern

Tests run against real warehouses once, locally, using `--snapshot-update`. The query
results are captured as snapshots and committed to the repository. In CI, tests replay
from committed snapshots using `MockEngine` -- zero warehouse cost, zero credentials
required.

## Use the `backend_engine` fixture

Cubano provides three engine fixtures in `tests/integration/conftest.py`:

- **`snowflake_engine`** -- connects to Snowflake when recording, MockEngine when replaying.
- **`databricks_engine`** -- connects to Databricks when recording, MockEngine when replaying.
- **`backend_engine`** -- a parametrized fixture that runs a single test function against both
  backends. Pytest creates `[snowflake_engine]` and `[databricks_engine]` variants for each test.

The `backend_engine` fixture is the primary entry point. Write one test function, get two
test IDs. No environment variable is needed to select a backend -- both run automatically.

## Add a snapshot test

### Step 1: Define your SemanticView model

Add your model to `tests/integration/test_queries.py` (or a new test file):

```python
from cubano import Dimension, Metric, SemanticView


class MyView(SemanticView, view="my_view"):
    revenue = Metric()
    category = Dimension()
```

### Step 2: Update `TEST_DATA`

In `tests/integration/conftest.py`, add (or update) the rows your view will expose in
`TEST_DATA`. The view name in `MockEngine.load()` must match the
`view=` parameter on your model.

!!! note
    If your view uses a different view name than the existing
    `snapshot_sales_view`, you will need to add a corresponding
    `engine.load("my_view", MY_TEST_DATA)` call in the engine fixtures.

### Step 3: Write the test function

Use `backend_engine` and `snapshot` fixtures:

```python
def test_my_query(backend_engine, snapshot):
    """Validates my query returns expected results."""
    result = (
        MyView.query()
        .using("test")
        .metrics(MyView.revenue)
        .order_by(MyView.revenue)
        .execute()
    )
    rows = [dict(row.items()) for row in result]
    assert rows == snapshot
```

### Step 4: Record the snapshot

Run with `--snapshot-update` to record against both warehouses:

```bash
uv run pytest tests/integration/test_queries.py --snapshot-update
```

If only Snowflake credentials are available, Databricks variants are skipped
(and vice versa). Re-record with the missing credentials when they become
available.

### Step 5: Verify the snapshot diff

```bash
git diff tests/integration/__snapshots__/
```

Review the captured data to confirm it matches your expectations.

### Step 6: Commit

```bash
git add tests/integration/__snapshots__/ && git commit -m "feat: add snapshot test for ..."
```

## Record snapshots

### How `--snapshot-update` works

When pytest runs with `--snapshot-update`, the engine fixtures detect recording mode:

- **`snowflake_engine`** uses `SnowflakeEngine` if `SNOWFLAKE_*` credentials are set
  in the environment. Otherwise, the test is skipped.
- **`databricks_engine`** uses `DatabricksEngine` if `DATABRICKS_*` credentials are set
  in the environment. Otherwise, the test is skipped.

No `CUBANO_SNAPSHOT_BACKEND` env var is needed. Both backends are always recorded in
one `pytest --snapshot-update` run -- each skips gracefully if its credentials are missing.

### Snowflake credentials

| Variable | Description |
|----------|-------------|
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier |
| `SNOWFLAKE_USER` | Username |
| `SNOWFLAKE_PASSWORD` | Password |
| `SNOWFLAKE_WAREHOUSE` | Warehouse name |
| `SNOWFLAKE_DATABASE` | Database name |

### Databricks credentials

| Variable | Description |
|----------|-------------|
| `DATABRICKS_SERVER_HOSTNAME` | Databricks workspace hostname |
| `DATABRICKS_HTTP_PATH` | SQL warehouse HTTP path |
| `DATABRICKS_ACCESS_TOKEN` | Personal access token |
| `DATABRICKS_CATALOG` | Unity Catalog name |
| `DATABRICKS_SCHEMA` | Schema name |

### Snapshot file contents

Each snapshot entry contains the `list[dict]` representation of query results.
Entries are tagged with `[snowflake_engine]` or `[databricks_engine]` suffixes
so both backend results are stored independently within the same file.

## Run in replay mode (CI)

In CI, no warehouse credentials are needed. Both `snowflake_engine` and
`databricks_engine` fixtures use `MockEngine` loaded with `TEST_DATA` from
`tests/integration/conftest.py`.

All snapshot test variants pass automatically as part of `pytest tests/`.

!!! tip
    Use `--snapshot-warn-unused` in CI to detect stale snapshots:

    ```bash
    pytest tests/ --snapshot-warn-unused
    ```

## Re-record after changes

Re-record when:

- SQL generation logic changes (query builder, SQL compiler)
- `TEST_DATA` changes (added rows, modified values)
- Warehouse schema changes (column renames, new columns)

```bash
uv run pytest tests/integration/test_queries.py --snapshot-update
```

Review before committing:

```bash
git diff tests/integration/__snapshots__/
```

!!! warning
    Any snapshot change in a PR should be reviewed intentionally. Unexpected
    changes may indicate a regression in SQL generation.

## Clean up stale snapshots

When a test is removed, its snapshot entries (both `[snowflake_engine]` and
`[databricks_engine]` variants) become stale.

**Detection:** CI prints a warning via `--snapshot-warn-unused`.

**Cleanup:** Run `pytest --snapshot-update` locally. Syrupy removes unused
entries automatically during the update pass.

**Manual alternative:** Delete the stale `# name: test_removed_test[...]`
blocks from the `.ambr` file directly.

## Write reliable snapshot tests

Follow these practices to keep snapshot tests stable:

- **Always use `.using("test")`** to select the engine registered by the fixture.
- **Always use `.order_by()`** -- warehouses do not guarantee row order without
  an explicit ORDER BY clause.
- **Always convert to `list[dict]`:**
  `rows = [dict(row.items()) for row in result]`
- **Use `.limit(N)` for large datasets** to keep `.ambr` files small
  (20 rows or fewer recommended).
- **Use integer values in `TEST_DATA`** to avoid `Decimal` precision drift
  across warehouse backends.
- **Keep `TEST_DATA` to 10 rows or fewer** per view.
- **Use synthetic, controlled data** -- not production data.
- **List `backend_engine` first** in the test function signature to ensure
  the engine is registered before queries execute.

## Understand the snapshot file format

Cubano uses syrupy's Amber format (`.ambr`) for snapshot storage. Snapshot
files live in `tests/integration/__snapshots__/` alongside the test modules.

Each entry in an `.ambr` file looks like this:

```text
# serializer version: 1
# name: test_single_metric[snowflake_engine]
  list([
    dict({
      'country': 'US',
      'revenue': 1000,
    }),
  ])
# ---
# name: test_single_metric[databricks_engine]
  list([
    dict({
      'country': 'US',
      'revenue': 1000,
    }),
  ])
# ---
```

The `# name:` line identifies the test function and its backend variant.
The `# ---` delimiter separates entries. The body is a Python-repr-style
serialization of the `list[dict]` data.

## Troubleshooting

**"AssertionError: snapshot missing"**

:   The snapshot file does not contain an entry for this test. Run
    `pytest --snapshot-update` locally and commit the updated `.ambr` file.

**"Snapshot mismatch" after a refactor**

:   Re-record with `--snapshot-update` and review the diff. If the change is
    expected (e.g., column order changed), commit the update. If unexpected,
    investigate the regression.

**"Test SKIPPED[snowflake_engine] in recording mode"**

:   The `SNOWFLAKE_*` environment variables are not set. Export them before
    running `--snapshot-update`:

    ```bash
    export SNOWFLAKE_ACCOUNT=...
    export SNOWFLAKE_USER=...
    export SNOWFLAKE_PASSWORD=...
    export SNOWFLAKE_WAREHOUSE=...
    export SNOWFLAKE_DATABASE=...
    ```

**"Test SKIPPED[databricks_engine] in recording mode"**

:   The `DATABRICKS_*` environment variables are not set. Export them before
    running `--snapshot-update`:

    ```bash
    export DATABRICKS_SERVER_HOSTNAME=...
    export DATABRICKS_HTTP_PATH=...
    export DATABRICKS_ACCESS_TOKEN=...
    export DATABRICKS_CATALOG=...
    export DATABRICKS_SCHEMA=...
    ```

**"Only one backend variant in `.ambr`"**

:   The other backend's credentials were missing during recording. Re-run
    `--snapshot-update` with the missing credentials set in your environment.

## See also

- [Backend overview](backends/overview.md) -- compare Snowflake and Databricks
- [Your first query](../tutorials/first-query.md) -- getting started with MockEngine
