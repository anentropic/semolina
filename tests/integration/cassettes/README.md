# Integration test cassettes

These directories are **recorded ADBC interactions** (SQL + Arrow results) for the
warehouse integration tests in `tests/integration/test_queries.py`, captured by
[`pytest-adbc-replay`](https://anentropic.github.io/pytest-adbc-replay/).

By default (and in CI) the tests **replay** from these cassettes — no warehouse,
no credentials, no network. Each test+backend has its own cassette under
`<module>/<test>[<backend>]/<driver>/`.

## Recording / re-recording

Recording runs the tests against **real** Snowflake and Databricks warehouses,
so it needs credentials (`SNOWFLAKE_*` / `DATABRICKS_*` in the environment, a
`.env` file, or a Semolina config file — see `semolina.testing.credentials`).
The fixtures create a temporary schema with a `sales_data` table and a
`sales_view` semantic/metric view, run the queries, and capture the results.

```bash
# Record everything fresh (drops + recreates all cassettes):
uv run pytest --adbc-record=all tests/integration

# Record only what's missing (e.g. after adding a test):
uv run pytest --adbc-record=new_episodes tests/integration
```

Then commit the updated cassette files. Cassettes are matched by normalized SQL,
so they only need re-recording when the **generated SQL** changes (new/changed
query) or the **expected data** changes.

Do not edit cassette files by hand.
