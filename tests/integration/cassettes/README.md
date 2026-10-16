# Integration test cassettes

These directories are **recorded ADBC interactions** (SQL + Arrow results) for the
warehouse integration tests in `tests/integration/test_queries.py`, captured by
[`pytest-adbc-replay`](https://s-layer.github.io/pytest-adbc-replay/).

By default (and in CI) the tests **replay** from these cassettes — no warehouse,
no credentials, no network. Each test+backend has its own cassette under
`<module>/<test>[<backend>]/<driver>/`.

## Recording / re-recording

Recording runs the tests against **real** Snowflake and Databricks warehouses,
so it needs connection config. The fixtures read the same source as the rest of
Semolina — the `[connections.snowflake]` / `[connections.databricks]` sections of
`.semolina.toml` (see `semolina.config.warehouse_config`), with `SNOWFLAKE_*` /
`DATABRICKS_*` environment variables filling any gaps. Both password and key-pair
auth are supported. The fixtures create a temporary schema with a `sales_data`
table and a `sales_view` semantic/metric view, run the queries, and capture the
results.

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

## Copied cassettes

Only `test_queries.py` and `test_introspect.py` record. The async, DTO and type-fidelity
tests replay cassettes **copied** byte for byte from `test_queries` recordings, so each of
those tests and its cassette ends in `_copied_cassette` or `_copied`: a pass there shows
that the SQL still matches a recording, not that anything ran live. Re-record the source
test, then copy its directory over the copy again. `tests/unit/test_cassette_provenance.py`
fails on a cassette outside the two recording modules whose name does not say `copied`.
