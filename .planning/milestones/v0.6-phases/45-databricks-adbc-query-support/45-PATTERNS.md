# Phase 45: Databricks ADBC Query Support - Pattern Map

**Mapped:** 2026-06-24
**Files analyzed:** 5 (2 in-repo modified, 2 in-repo new tests, 1 cross-repo)
**Analogs found:** 4 / 5 (the cross-repo poolhouse target has no in-repo analog — mirror its sibling)

Phase 45 is overwhelmingly MODIFY work, not greenfield. Two production seams change
(`src/semolina/engines/sql.py`, plus the cross-repo `adbc_poolhouse/_databricks_config.py`),
backed by new/extended unit tests and 7 recorded integration cassettes. Every analog below is a
real, existing file — the planner should copy the assertion style and escaping discipline verbatim.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/semolina/engines/sql.py` (MODIFY: add `supports_parameterized_queries` flag + `render_literal()` + literal post-pass) | service (SQL generator / dialect) | transform (query → `(sql, params)`) | itself — existing `Dialect` ABC + `placeholder`/`quote_identifier`/`render_inline` | exact (self-extend) |
| `tests/unit/test_sql.py` (MODIFY: add Databricks-literal + render_literal adversarial tests; extend Snowflake/DuckDB "still parameterized" regression) | test (unit) | request-response (assert on `(sql, params)` tuple) | `tests/unit/test_sql.py::TestBuildSelectWithParams` + `TestWhereClauseCompiler` | exact (same file) |
| `tests/integration/test_queries.py` + cassettes (RECORD: 7 `*_databricks_engine_` cassettes; model unchanged) | test (integration replay) | event-driven (cassette record/replay) | `test_filtered_by_dimension` + `*_snowflake_engine_` cassette tree | exact (same test, sibling backend) |
| `adbc_poolhouse/_databricks_config.py` (MODIFY, CROSS-REPO: append `?catalog=&schema=` to decomposed URI) | config (connection/DSN) | transform (config → ADBC kwargs) | `adbc_poolhouse/_snowflake_config.py::to_adbc_kwargs` (sets `adbc.snowflake.sql.schema`) | role-match (sibling, external repo) |
| poolhouse `tests/...test_databricks_config.py` (NEW, CROSS-REPO: assert URI carries params) | test (unit, external repo) | request-response (assert on URI string) | `tests/integration/test_queries.py` assertion style (in-repo proxy only) | partial (no in-repo poolhouse test visible) |

## Pattern Assignments

### `src/semolina/engines/sql.py` (service, transform)

**Analog:** itself — the existing `Dialect` ABC and `SQLBuilder`. The new code extends, not replaces.

**Where the capability flag goes** — the `Dialect` ABC (`src/semolina/engines/sql.py:40-72`) declares
class-level/property contracts. Add `supports_parameterized_queries: bool = True` here as a plain class
attribute (matches how `placeholder` is a per-dialect contract, not an `isinstance` check). Override
`= False` on `DatabricksDialect` (class body at `src/semolina/engines/sql.py:301-318`, alongside its
`placeholder` at `:320-323`).

**Escaping model to MIRROR** — `DatabricksDialect.quote_identifier` (`src/semolina/engines/sql.py:325-346`)
is the exact precedent for how `render_literal` must escape. Note it escapes the *quote char* by
doubling; `render_literal` differs (Spark string literals escape `\` then `'`), but the structure —
single audited escaping site, dialect-specific — is identical:
```python
# src/semolina/engines/sql.py:345-346  (DatabricksDialect.quote_identifier — IDENTIFIER escaping)
escaped = name.replace("`", "``")
return f"`{escaped}`"
```
Contrast Snowflake's `quote_identifier` (`:266-267`, doubles `"`). The new `render_literal` is the
STRING-LITERAL analog of these: Databricks doubles/backslash-escapes per Spark, standard SQL doubles `'`.

**Core compile pattern — DO NOT edit the 16 case arms** — `_compile_predicate`
(`src/semolina/engines/sql.py:519-679`) already routes every predicate through one compiler using
`ph = self.dialect.placeholder` (`:537`). The `In` arm emits N placeholders left-to-right
(`:596-603`), so param order matches placeholder order — this invariant is what makes a single
left-to-right substitution post-pass correct. Leave this method untouched.

**The single seam — `build_select_with_params`** (`src/semolina/engines/sql.py:694-730`). It assembles
`parts` + `all_params` and returns `"\n".join(parts), all_params` at `:730`. The literal-inlining
post-pass goes HERE, mirroring the research Pattern 1:
```python
# src/semolina/engines/sql.py:730  (current return — the seam)
return "\n".join(parts), all_params
# Phase 45 becomes (illustrative):
#   sql = "\n".join(parts)
#   if not self.dialect.supports_parameterized_queries:
#       return self._render_literal_sql(sql, all_params), []
#   return sql, all_params
```
NOTE: `DuckDBSQLBuilder` overrides `build_select_with_params` (`:966-1057`, return at `:1057`). DuckDB
keeps `supports_parameterized_queries = True`, so the post-pass is a no-op there — but if a shared
helper is added, prefer placing it on the base `SQLBuilder` so the DuckDB override can opt in trivially
or stay parameterized.

**UNSAFE — do NOT reuse for execution: `render_inline`** (`src/semolina/engines/sql.py:732-751`):
```python
# src/semolina/engines/sql.py:747-751  (render_inline — repr-based, DISPLAY ONLY)
result = sql_template
ph = self.dialect.placeholder
for param in params:
    result = result.replace(ph, repr(param), 1)   # repr() — NOT SQL-safe
return result
```
This is the correct *substitution discipline* (left-to-right, single-replace, `placeholder`-driven —
copy this loop shape) but `repr()` is Python repr: `repr(True)` → `True`, `repr(None)` → `None`, no Spark
escaping. The new `_render_literal_sql` must reuse this loop structure but call
`self.dialect.render_literal(param)` instead of `repr(param)`. `render_inline` itself stays for
`build_select` display (`:783-784`).

**Loud-failure for unsupported literal types:** per RESEARCH Open Question 2, `render_literal` should
handle str/int/float/bool/None (covers all current `.where()` lookups) and raise `NotImplementedError`
for unhandled types (e.g. date/Decimal), mirroring the catch-all `raise NotImplementedError` already in
`_compile_predicate` (`src/semolina/engines/sql.py:669-674`).

---

### `tests/unit/test_sql.py` (test, unit)

**Analog:** the same file. Three existing test classes are the templates to mirror.

**Assertion style for `(sql, params)` — `TestBuildSelectWithParams`** (`tests/unit/test_sql.py:765-811`).
This is the exact shape for the new "Databricks inlines literal + empty params" and the
"Snowflake/DuckDB STILL parameterized" regression (DBX-01 / DBX-01b):
```python
# tests/unit/test_sql.py:768-780  (TestBuildSelectWithParams.test_query_with_filters)
query = replace(
    _Query().metrics(Sales.revenue).dimensions(Sales.country),
    _filters=Exact("country", "US"),
)
builder = SQLBuilder(SnowflakeDialect())
sql, params = builder.build_select_with_params(query)
assert "WHERE" in sql
assert '"COUNTRY" = ?' in sql
assert params == ["US"]
assert "'US'" not in sql        # placeholder kept, literal NOT inlined
```
The Databricks counterpart asserts the inverse: `sql` contains `` `country` = 'US' `` and `params == []`.
The Snowflake/DuckDB regression test asserts these `?` + `["US"]` assertions still hold (no regression).

**Adversarial `render_literal` tests — `TestDialectEscaping`** (`tests/unit/test_sql.py:493-534`) is the
precedent for character-level escaping assertions (it currently covers identifier quoting). Mirror its
direct-call style for the new `render_literal` tests (DBX-01c — `O'Reilly`, `a\b`, NULL, bool, IN-list):
```python
# tests/unit/test_sql.py:527-534  (TestDatabricksDialect escaping precedent — backtick doubling)
dialect = DatabricksDialect()
result = dialect.quote_identifier("a`b`c")
assert result == "`a``b``c`"
# new render_literal tests follow this call/assert shape, e.g.:
#   assert DatabricksDialect().render_literal("O'Reilly") == "'O\\'Reilly'"
#   assert DatabricksDialect().render_literal("a\\b")     == "'a\\\\b'"
#   assert DatabricksDialect().render_literal(None)       == "NULL"
```

**`_compile_predicate` + IN-list precedent — `TestWhereClauseCompiler`** (`tests/unit/test_sql.py:554-762`).
The Databricks-placeholder tests at `:733-745` already prove backtick + `?` per-dialect; the new
literal-path tests for the `In` arm (DBX-01c IN-list) mirror `test_databricks_in_placeholder`
(`:740-745`) but assert inlined literals + `params == []`:
```python
# tests/unit/test_sql.py:740-745  (existing Databricks IN — the param-path precedent to invert)
builder = SQLBuilder(DatabricksDialect())
sql, params = builder._compile_predicate(In("country", ["US", "CA"]))
assert sql == "`country` IN (?, ?)"
assert params == ["US", "CA"]
```

**Imports/setup convention** (`tests/unit/test_sql.py:16-50`): tests import dialects from
`semolina.engines.sql`, `Sales` from the shared `models` module, predicates from `semolina.filters`,
and use `dataclasses.replace(..., _filters=...)` to inject a WHERE without the public `.where()` builder.
Class-per-feature with `setup_method` building `SQLBuilder(SnowflakeDialect())` (`:557-559`).

---

### `tests/integration/test_queries.py` + cassettes (test, integration replay)

**Analog:** `test_filtered_by_dimension` (`tests/integration/test_queries.py:170-186`) and the existing
`*_snowflake_engine_` cassette tree. This is the WHERE test that triggers the bind-param blocker.

**The shared model is unchanged** — `Sales(view="sales_view")` (`tests/integration/test_queries.py:49-60`),
`revenue`/`cost` Metrics, `country`/`region` Dimensions. RESEARCH anti-pattern: do NOT qualify or
per-backend the model; the DSN schema fix makes the unqualified name resolve on Databricks.

**The test that exercises the blocker** (`tests/integration/test_queries.py:170-186`):
```python
def test_filtered_by_dimension(backend_engine: Any) -> None:
    cursor = (
        Sales.query().using("test")
        .metrics(Sales.revenue, Sales.cost)
        .dimensions(Sales.country)
        .where(Sales.country == "US")
        .order_by(Sales.country)
        .execute()
    )
    ...
    assert rows == [(1500, 150, "US")]
```

**Parametrized backend fixture** — `backend_engine` (`tests/integration/conftest.py:357-371`) params over
`["snowflake_engine", "databricks_engine"]`; each test+backend gets its own cassette dir derived from the
node id. The `databricks_engine` fixture (`:239-354`) already has a record branch (`:263-338`, creates the
metric view via `CREATE OR REPLACE VIEW ... WITH METRICS LANGUAGE YAML`) and a replay branch (`:339-354`,
placeholder `DatabricksConfig`). Recording is therefore already wired — DBX-03 only needs the two upstream
fixes landed + live creds + Foundry driver.

**Cassette layout to replicate** — verified on disk for Snowflake:
```
tests/integration/cassettes/integration/test_queries/
  test_filtered_by_dimension_snowflake_engine_/
    adbc_driver_snowflake.dbapi/        <- driver-module subdir
      000_query.sql      000_params.json      000_result.arrow
```
The Snowflake `000_query.sql` (recorded, the **param-path** form — note the `?` and separate params):
```sql
SELECT
  AGG("REVENUE"),
  AGG("COST"),
  "COUNTRY"
FROM "SALES_VIEW"
WHERE
  "COUNTRY" = ?
GROUP BY ALL
ORDER BY
  "COUNTRY" ASC NULLS LAST
```
`000_params.json` == `["US"]`.

The 7 Databricks cassettes will record under `*_databricks_engine_/` with the driver subdir
`adbc_driver_manager.dbapi` (Databricks routes through the driver manager, per conftest docstring
`:246-249`). For `test_filtered_by_dimension` the recorded `000_query.sql` must show the **literal-inlined**
form (`` `country` = 'US' ``, `MEASURE(`revenue`)`, backtick lowercase names) and `000_params.json` == `[]`.
The other 6 tests have no WHERE, so their params are already `[]` and only the dialect/MEASURE/backtick
differences distinguish them from Snowflake.

**Recording command** (`tests/integration/test_queries.py:25`, conftest `:16-18`):
`pytest --adbc-record=once tests/integration` with `[connections.databricks]` configured. Mark DBX-03
`autonomous: false` — needs operator creds + warm SQL Warehouse + Foundry ADBC driver. RESEARCH Pitfall 3:
record only AFTER the poolhouse catalog/schema fix lands, or you record `TABLE_OR_VIEW_NOT_FOUND`.

---

### `adbc_poolhouse/_databricks_config.py` (config, transform) — CROSS-REPO

**External analog:** `adbc_poolhouse/_snowflake_config.py::to_adbc_kwargs`
(`.venv/.../adbc_poolhouse/_snowflake_config.py:144-246`), which sets the default schema on the connection:
```python
# _snowflake_config.py:195-198  (Snowflake sets schema on the connection — the precedent)
if self.database is not None:
    kwargs["adbc.snowflake.sql.db"] = self.database
if self.schema_ is not None:
    kwargs["adbc.snowflake.sql.schema"] = self.schema_
```
Databricks has no equivalent kwarg (driver gap), so the schema/catalog must ride the DSN instead.

**The fix site** — `DatabricksConfig.to_adbc_kwargs` decomposed branch
(`.venv/.../adbc_poolhouse/_databricks_config.py:88-113`):
```python
# _databricks_config.py:103-113  (current — drops catalog/schema)
if self.uri is not None:
    return {"uri": self.uri.get_secret_value()}          # URI mode: DO NOT mutate (anti-pattern)
assert self.host is not None
assert self.http_path is not None
assert self.token is not None
encoded_token = quote(self.token.get_secret_value(), safe="")
uri = f"databricks://token:{encoded_token}@{self.host}:443{self.http_path}"
return {"uri": uri}                                       # <-- append ?catalog=&schema= here
```
- `quote` is ALREADY imported (`_databricks_config.py:6`); add `urlencode` from `urllib.parse`
  (RESEARCH "Don't Hand-Roll": use `urlencode`, not manual `%`).
- `self.catalog` (`:64-65`) and `self.schema_` (`:67-69`) are the source fields. Emit no `?` when both
  are `None` (back-compat). DSN param names are exactly `catalog` and `schema` [VERIFIED docs].
- URI mode (`:103-104`) stays untouched — anti-pattern to mutate a user-supplied full DSN.

> **No in-repo file maps to this change.** It lives in the separate adbc-poolhouse repo. Per RESEARCH
> Runtime State Inventory, land it as its own poolhouse PR/release first, then bump
> `pyproject.toml adbc-poolhouse>=1.2.1`, then record. Treat as a prerequisite deliverable, not an
> in-repo edit.

**Poolhouse unit test (cross-repo, no in-repo analog)** — the assertion target (RESEARCH Code Examples):
```python
cfg = DatabricksConfig(host="h", http_path="/sql/1.0/warehouses/x",
                       token=SecretStr("t"), catalog="main", schema="myschema")
assert cfg.to_adbc_kwargs()["uri"] == \
    "databricks://token:t@h:443/sql/1.0/warehouses/x?catalog=main&schema=myschema"
# and: no '?' when catalog and schema are both None
```
Mirror the in-repo assertion discipline from `tests/unit/test_sql.py` (exact-equality on the produced
string) since no poolhouse test is visible in this repo's venv.

## Shared Patterns

### SQL-literal escaping (the single audited injection surface)
**Source:** `src/semolina/engines/sql.py:325-346` (`DatabricksDialect.quote_identifier`, the IDENTIFIER
escaping precedent) and `:266-267` (Snowflake).
**Apply to:** the new `Dialect.render_literal` (string-literal escaping) on the ABC + `DatabricksDialect`.
One method, one review surface (RESEARCH V5 / "Don't Hand-Roll"). Databricks: escape `\` → `\\` FIRST,
then `'` → `\'`; standard SQL default: `'` → `''`. Order matters (RESEARCH Pitfall 1).

### Left-to-right single-replace substitution discipline
**Source:** `src/semolina/engines/sql.py:747-751` (`render_inline` loop shape).
**Apply to:** the new `_render_literal_sql(sql_template, params)` — same loop, swap `repr(param)` for
`self.dialect.render_literal(param)`. Preserves the qmark-count == param-count invariant the `In` arm
relies on (`:596-603`).

### Capability-flag dispatch (no `isinstance` in the builder)
**Source:** the `placeholder` property contract pattern — declared abstract on `Dialect`
(`src/semolina/engines/sql.py:74-86`), overridden per dialect (`:241-244`, `:320-323`, `:394-397`).
**Apply to:** `supports_parameterized_queries` — a flag on the ABC, branched in `build_select_with_params`.
The builder must NOT import or `isinstance`-check `DatabricksDialect` (RESEARCH "Don't Hand-Roll").

### Engine-level SQL generation entry point
**Source:** `src/semolina/engines/base.py:171` — `sql, params = builder.build_select_with_params(query)`
then `cursor.execute(sql, params)`. The Databricks unit test
`tests/unit/test_databricks_engine.py:158-170` asserts `cursor.execute.assert_called_once_with(expected_sql,
expected_params)`. After the post-pass, the Databricks engine path will pass `params == []` here — an
engine-level assertion the planner may add mirroring `test_execute_runs_sql_over_pooled_cursor`.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| poolhouse `tests/...test_databricks_config.py` | test (unit) | request-response | Cross-repo; the adbc-poolhouse test suite is not present in this repo's venv. Use the in-repo exact-equality assertion style (`tests/unit/test_sql.py`) as the proxy and the RESEARCH Code-Examples URI string as the target. |

## Metadata

**Analog search scope:** `src/semolina/engines/`, `tests/unit/`, `tests/integration/` (+ cassette tree on
disk), `.venv/.../adbc_poolhouse/`.
**Files scanned:** `sql.py`, `base.py` (grep), `test_sql.py`, `test_databricks_engine.py`,
`test_queries.py`, `conftest.py`, `_databricks_config.py`, `_snowflake_config.py`, Snowflake filtered
cassette (`000_query.sql` / `000_params.json`).
**Pattern extraction date:** 2026-06-24
