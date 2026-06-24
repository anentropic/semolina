# Phase 45: Databricks ADBC Query Support - Research

**Researched:** 2026-06-24
**Domain:** SQL dialect generation (literal-inlining vs bind-params), ADBC Databricks driver capability gaps, cross-repo (adbc-poolhouse) DSN fix, pytest-adbc-replay cassette recording
**Confidence:** HIGH

## Summary

Phase 45 makes Databricks query execution work end-to-end over real ADBC and records the 7
Databricks `test_queries.py` cassettes (only Snowflake cassettes exist today). There is **no
CONTEXT.md** — the authoritative scope is the ROADMAP Phase 45 section plus the two
already-verified driver blockers carried forward in memory `project_databricks_adbc_query_blockers`.
Both blockers live in the **arrow-adbc Databricks (Foundry manifest) driver** — neither is a
Semolina SQL bug nor a Go-driver limitation. They are treated here as **ground truth, not
re-derived**.

The work is a focused, two-repo bug fix with a clean TDD path:
1. **Bind-param blocker** → add a `supports_parameterized_queries` capability flag to the
   `Dialect` ABC (default `True`; `False` only on `DatabricksDialect`) and a dialect
   `render_literal()` so the WHERE compiler inlines safe SQL literals for Databricks while
   Snowflake/DuckDB keep emitting `?` + params. This is unit-testable at the SQL-string level
   with **no live warehouse**.
2. **Catalog/schema blocker** → in adbc-poolhouse `DatabricksConfig.to_adbc_kwargs()`, append
   `?catalog=…&schema=…` (URL-encoded) to the decomposed `databricks://…` URI. The Go driver
   parses these DSN params (`catalog`, `schema`) — [VERIFIED: docs.databricks.com go-sql-driver].
   Unit-testable against the returned URI string with no warehouse.
3. **Live recording** of the 7 Databricks cassettes is the only step needing the operator's
   live credentials + a warm SQL Warehouse + the Foundry ADBC driver — gate it `autonomous: false`.

**Primary recommendation:** Implement **literal-inlining (Option a)** for the bind-param blocker —
the project ships query execution, so gating `.where()` as `NotImplementedError` (Option b) breaks
a first-class feature on one backend and is only a stopgap. Land the **adbc-poolhouse URI fix
first** (recording cannot resolve unqualified `sales_view` without it), then the dialect fix, then
record. Both code fixes are verifiable offline; only the cassette recording needs a human + creds.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| WHERE-value SQL emission (literal vs `?`) | Semolina `DatabricksDialect` + `SQLBuilder._compile_predicate` | — | Dialect owns backend SQL syntax differences; the builder already routes all predicates through one compiler |
| Capability flag (`supports_parameterized_queries`) | Semolina `Dialect` ABC | per-dialect override | Dialect is the single source of backend SQL truth (placeholder, quoting, folding all live there) |
| Default catalog/schema injection | adbc-poolhouse `DatabricksConfig` (connection layer) | — | This is a **connection/DSN** concern, not a SQL-generation concern; mirrors `SnowflakeConfig` setting `adbc.snowflake.sql.schema` |
| Cassette recording (live DDL + ADBC query capture) | `tests/integration/conftest.py` record-mode fixture | operator creds | Already built for both backends; only needs the two fixes upstream of it to land |
| MEASURE()/AGG() metric wrapping | Semolina `DatabricksDialect.wrap_metric` | — | Already implemented (`MEASURE(\`x\`)`); caveat only, not new work |

## Standard Stack

No new runtime dependencies. This phase edits existing code in two repos.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| adbc-poolhouse | >=1.2.0 (installed 1.2.0) | Owns the ADBC pool; `DatabricksConfig.to_adbc_kwargs()` is the cross-repo fix site | User's own library; already the sole connection layer [VERIFIED: pyproject.toml + installed METADATA] |
| pytest-adbc-replay | >=1.1.1 (per memory) | Records/replays cassettes; matches on `000_query.sql` + `000_params.json` | Already the integration-test harness; Snowflake 7/7 replay green [VERIFIED: cassette tree on disk] |
| databricks-sql-connector | >=4.2.5 (extra) | Record-mode DDL setup only (native connector creates the metric view) | Not on the runtime path; record-only glue [VERIFIED: pyproject.toml optional-deps] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Foundry Databricks ADBC driver | (Foundry-distributed, NOT PyPI) | The actual ADBC driver `databricks://` resolves to via `adbc_driver_manager` | Required only for live recording; absent from dev/CI venv [CITED: DatabricksConfig docstring + memory] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Literal-inlining `.where()` values (Option a) | Gate `.where()` as `NotImplementedError` on Databricks (Option b) | Option b is a pure stopgap — it ships a backend that can't filter, contradicting "works identically across Snowflake, Databricks, DuckDB" (PROJECT core value). Reconsider only if upstream lands ADBC binding soon. |
| DSN query-param injection in poolhouse | Pass catalog/schema as separate ADBC `db_kwargs` | The Databricks ADBC driver capability matrix lists specify-target-catalog/schema as unsupported (per established findings); the Go driver only honours the **DSN** params. DSN is the working route. |

**Installation:** None — no `npm/pip install`. Edits to installed `adbc_poolhouse` source are consumed
per "Cross-Repo Consumption" below.

## Package Legitimacy Audit

> No new packages are installed in this phase. All dependencies already present in `pyproject.toml`
> and the venv. Audit not applicable.

| Package | Registry | Verdict | Disposition |
|---------|----------|---------|-------------|
| (none added) | — | — | — |

**Packages removed due to SLOP:** none
**Packages flagged SUS:** none

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| (none) | No REQUIREMENTS.md; `phase_req_ids` is null. Scope = ROADMAP Phase 45 + memory blockers. | The two blocker fixes + recording below constitute the implicit requirements. The planner may mint local IDs (e.g. DBX-01 bind-param, DBX-02 catalog/schema, DBX-03 recording) for traceability. |

## Architecture Patterns

### System Architecture Diagram

```
                         Sales.query().where(country=="US").execute()
                                          |
                                          v
                          Engine.execute(query)            [src/semolina/engines/base.py]
                                          |
                                          v
              dialect.create_builder().build_select_with_params(query)
                                          |
                       +------------------+-------------------+
                       |                                      |
           supports_parameterized_queries == True   supports_parameterized_queries == False
              (Snowflake / DuckDB)                       (Databricks)  <-- NEW BRANCH
                       |                                      |
            "WHERE col = ?", params=["US"]        "WHERE col = 'US'", params=[]
                       |                                      |
                       +------------------+-------------------+
                                          v
                          conn.cursor().execute(sql, params)
                                          |
                                          v
              ADBC driver (snowflake.dbapi | adbc_driver_manager->Foundry databricks)
                                          |
                       connection DSN built by adbc-poolhouse:
            Snowflake: db_kwargs incl. adbc.snowflake.sql.schema
            Databricks: uri = databricks://token:..@host:443{http_path}?catalog=..&schema=..  <-- NEW
                                          |
                                          v
                                    Warehouse / recorded cassette
```

Data flow to trace: a `.where()` query enters `Engine.execute`, the builder branches on the dialect
capability flag (the **only** new control point in Semolina), and the connection layer (adbc-poolhouse)
supplies a DSN that now carries the default namespace so unqualified `FROM \`sales_view\`` resolves.

### Recommended Project Structure
No new files in Semolina. Touch-points:
```
src/semolina/engines/sql.py     # Dialect.supports_parameterized_queries flag + render_literal();
                                 #   SQLBuilder branch in build_select_with_params / _compile path
tests/unit/                      # NEW failing-first tests: assert Databricks SQL has inline literals
                                 #   + empty params; assert Snowflake/DuckDB still emit ? + params
tests/integration/test_queries.py  # unchanged model Sales(view="sales_view"); cassettes get recorded
tests/integration/cassettes/...    # 7 NEW databricks_engine cassettes (recorded, then committed)
```
Cross-repo (adbc-poolhouse, separate repo):
```
adbc_poolhouse/_databricks_config.py   # to_adbc_kwargs(): append ?catalog=&schema= to decomposed URI
tests/ (poolhouse)                      # NEW: assert URI contains the encoded params
```

### Pattern 1: Dialect capability flag + literal renderer (Option a)
**What:** Add a class-level (or property) `supports_parameterized_queries: bool` to the `Dialect`
ABC defaulting `True`; override `False` on `DatabricksDialect`. Add a `render_literal(value) -> str`
to the `Dialect` ABC (default standard-SQL: double single-quotes; subclasses override escaping).
The WHERE compiler keeps building `(sql, params)`; when `not supports_parameterized_queries`, the
builder substitutes literals for placeholders **at build time** so the driver receives `params=[]`.

**When to use:** Only Databricks (the one backend whose ADBC wrapper rejects binds).

**Where it branches in `sql.py`:**
- `_compile_predicate` already uses `ph = self.dialect.placeholder`. The cleanest seam is to keep
  `_compile_predicate` producing `(template_with_?, params)` unchanged, and add a **single
  post-pass** in `build_select_with_params`: if `not self.dialect.supports_parameterized_queries`,
  call a new `render_literal`-based substitution over the assembled `(sql, all_params)` and return
  `(inlined_sql, [])`. This avoids editing all 16 `case` arms.
- Note an existing `render_inline()` (line ~732) already substitutes `repr(param)` left-to-right —
  but **`repr()` is unsafe for SQL** (it is Python repr, used for display only; e.g. `repr("US")`
  → `'US'` happens to look right but `repr(True)` → `True`, `repr(None)` → `None`, and it does no
  Spark-specific escaping). Do **not** reuse `render_inline` for execution; add a sibling
  `render_literal_sql(sql_template, params)` that calls `self.dialect.render_literal(p)` per
  placeholder. Keep the qmark-count==param-count invariant; the `In` arm emits N placeholders, so
  left-to-right single-replace (as `render_inline` does) is the correct substitution order.

**Example (illustrative — verify against final `sql.py`):**
```python
# Source: pattern derived from src/semolina/engines/sql.py build_select_with_params (read 2026-06-24)
class Dialect(ABC):
    supports_parameterized_queries: bool = True

    def render_literal(self, value: Any) -> str:
        """Render a Python value as a safe SQL literal (standard SQL: '' escaping)."""
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return repr(value)            # numeric: no quoting
        s = str(value).replace("'", "''") # standard SQL: double the quote
        return f"'{s}'"

class DatabricksDialect(Dialect):
    supports_parameterized_queries = False

    def render_literal(self, value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return repr(value)
        # Spark SQL: backslash IS an escape char -> escape \ first, then '
        s = str(value).replace("\\", "\\\\").replace("'", "\\'")
        return f"'{s}'"
```

```python
# in SQLBuilder.build_select_with_params, before returning:
sql = "\n".join(parts)
if not self.dialect.supports_parameterized_queries:
    sql = self._render_literal_sql(sql, all_params)
    return sql, []
return sql, all_params
```

### Pattern 2: DSN namespace injection (adbc-poolhouse, cross-repo)
**What:** In `DatabricksConfig.to_adbc_kwargs()` decomposed mode, append the URL-encoded
`catalog`/`schema` query params to the built URI. URI mode (`self.uri` set) is left untouched —
the user supplied a full DSN, do not mutate it.

**Example:**
```python
# Source: adbc_poolhouse/_databricks_config.py to_adbc_kwargs (read 2026-06-24) + go-sql-driver DSN
from urllib.parse import quote, urlencode

# decomposed mode, after building the base uri:
uri = f"databricks://token:{encoded_token}@{self.host}:443{self.http_path}"
params: dict[str, str] = {}
if self.catalog is not None:
    params["catalog"] = self.catalog
if self.schema_ is not None:
    params["schema"] = self.schema_
if params:
    uri = f"{uri}?{urlencode(params, quote_via=quote)}"
return {"uri": uri}
```
- DSN param names are `catalog` and `schema` [VERIFIED: docs.databricks.com go-sql-driver — example
  DSN `...endpoints/...?catalog=hive_metastore&schema=example`].
- When `catalog`/`schema` are `None`, emit no query string (back-compat with current bare URI).
- URL-encode values (`urlencode`) so a schema/catalog with reserved chars is safe.

### Anti-Patterns to Avoid
- **Reusing `render_inline()` (repr-based) for execution SQL.** It is display-only; `repr` does not
  apply Spark escaping and renders `bool`/`None` as Python tokens. SQL-injection + correctness risk.
- **Escaping Databricks string literals by doubling the quote only.** Spark SQL treats `\` as an
  escape character, so `O'Connell` must become `'O\'Connell'` (or `''`-style is *also* accepted, but
  a stray backslash in user data must be doubled `\\` regardless). [VERIFIED: docs.databricks.com
  string-type — `\'` and `\\`]. Escape `\` **before** `'`.
- **Mutating the URI in URI-mode** of `DatabricksConfig`. Only the decomposed branch should append
  params; a user-supplied full `uri` is authoritative.
- **Changing the shared `Sales(view="sales_view")` model or qualifying it per-backend.** Once the DSN
  carries the default schema, the unqualified name resolves on Databricks exactly as it does on
  Snowflake (which sets schema on the connection). Keep the model unqualified and backend-agnostic.
- **Recording without the catalog/schema fix landed.** The view won't resolve; you'd record a
  `TABLE_OR_VIEW_NOT_FOUND` error, not a result.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| URL-encoding DSN params | Manual string concatenation with `%` escapes | `urllib.parse.urlencode` / `quote` | Already imported in poolhouse; handles reserved chars correctly |
| SQL literal escaping | Per-call inline `.replace()` scattered in compiler arms | One `dialect.render_literal()` | Single audited escaping site = single injection-surface to review |
| Cassette recording/replay harness | New recording code | existing `tests/integration/conftest.py` record-mode + pytest-adbc-replay | Already records Snowflake 7/7; Databricks fixture branch exists, just unexercised |
| Capability dispatch | `isinstance(dialect, DatabricksDialect)` checks in the builder | A `supports_parameterized_queries` flag on the ABC | Avoids the builder importing concrete dialects; matches existing flag-on-dialect style (`placeholder`, `normalize_identifier`) |

**Key insight:** Both fixes are tiny and live at exactly one seam each (one builder post-pass, one
`to_adbc_kwargs` branch). The risk is not complexity — it is correctness of SQL-literal escaping and
the ordering of the cross-repo landing.

## Runtime State Inventory

> This is a feature/bug-fix phase, not a rename. The closest analog is the **cross-repo dependency
> and the recorded cassettes** (stored test state). Inventory below.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | 7 Databricks cassettes do **not** exist yet (`tests/integration/cassettes/integration/test_queries/` has only `*_snowflake_engine_` dirs — verified on disk). | Record + commit 7 `*_databricks_engine_` cassette dirs (`000_query.sql` + `000_params.json` + `000_result.arrow`). |
| Live service config | Recording needs a live Databricks SQL Warehouse with a `sales_view` metric view (created by the record-mode fixture DDL) + the Foundry ADBC driver installed in the venv. | Operator step, `autonomous: false`. |
| Cross-repo dependency | `adbc-poolhouse` is a **separate repo**; installed at `.venv/.../adbc_poolhouse/_databricks_config.py` v1.2.0. `pyproject.toml` pins `adbc-poolhouse>=1.2.0`. | Decide consumption mechanism (see below) before recording — the Databricks `to_adbc_kwargs` must carry catalog/schema at record time. |
| Secrets/env vars | `DATABRICKS_HOST/HTTP_PATH/TOKEN` (or `[connections.databricks]` in `.semolina.toml`). Token stays a wrapped `SecretStr`; never printed. | None — read by `warehouse_config("databricks")`; recording fixture skips if absent. |
| Build artifacts | The dialect change is pure Python source in this repo (no compiled artifact). The poolhouse change requires the edited package to be importable at record/CI time. | If editing installed `adbc_poolhouse` in-place, ensure no `uv sync` clobbers it before recording; prefer a real version bump (below). |

**Cross-Repo Consumption (the key sequencing decision):**
The `DatabricksConfig.to_adbc_kwargs()` fix lives in adbc-poolhouse. Options for this repo to consume it:
1. **Release bump (cleanest):** cut adbc-poolhouse `1.2.1` (or `1.3.0`) with the fix, bump
   `pyproject.toml` `adbc-poolhouse>=1.2.1`, `uv sync`. CI replay then uses the fixed version.
   *But the fix must exist before recording*, so this requires the poolhouse release to land first.
2. **Local path / editable dep during development:** `uv pip install -e ../adbc-poolhouse` (or a
   `[tool.uv.sources]` path entry) so the working-tree fix is importable for recording, then pin the
   released version for CI. Recommend this for the **record** step, then switch to (1) for the commit.
3. **In-place edit of `.venv` source for recording only:** fastest, but ephemeral — `uv sync` wipes
   it and CI won't have it. Acceptable only as a throwaway to verify; not a shippable state.

**Recommendation:** Make the poolhouse fix + its test land in the adbc-poolhouse repo first (own
commit/PR/release), then bump the dependency here. The plan should treat the poolhouse change as a
**prerequisite deliverable** (own task, marked cross-repo) ahead of recording.

**Nothing found in category — none.** All five categories had concrete items.

## Common Pitfalls

### Pitfall 1: Backslash escaping in Databricks string literals
**What goes wrong:** A value like `a\b` or `O'Reilly\` renders to broken/injectable SQL if you only
double the single quote.
**Why it happens:** Spark SQL (unlike standard SQL / Snowflake) treats `\` as an escape character
inside string literals [VERIFIED: docs.databricks.com string-type].
**How to avoid:** In `DatabricksDialect.render_literal`, escape `\` → `\\` **first**, then `'` → `\'`
(or `''`). Order matters. Add a unit test with both characters in the value.
**Warning signs:** Generated SQL with an odd number of backslashes before a quote; parse errors.

### Pitfall 2: `In` lists and placeholder/param count drift
**What goes wrong:** The `In` arm emits `N` placeholders for `N` values; a naive substitution that
replaces all `?` at once, or miscounts, corrupts the SQL.
**Why it happens:** `render_inline` replaces one placeholder per param, left-to-right (`.replace(ph,
…, 1)`), which is correct **only** if param order matches placeholder order — which it does (params
are appended in compile order).
**How to avoid:** Reuse the same left-to-right single-replace discipline in `render_literal_sql`;
unit-test an `In([...])` filter on Databricks.
**Warning signs:** Leftover `?` in Databricks SQL, or a literal in the wrong column.

### Pitfall 3: Recording before the poolhouse fix lands
**What goes wrong:** `pytest --adbc-record=once -k databricks` records a `TABLE_OR_VIEW_NOT_FOUND`
error (no default schema) instead of a result.
**Why it happens:** `to_adbc_kwargs()` still drops catalog/schema; `FROM \`sales_view\`` is
unqualified.
**How to avoid:** Land/consume the poolhouse DSN fix **before** recording. Verify by asserting the
built URI contains `?catalog=…&schema=…` in a poolhouse unit test first.
**Warning signs:** Cassette `000_result.arrow` missing / fixture `pytest.fail` during DDL is fine but
the **query** errors.

### Pitfall 4: Identifier folding (lowercase) on Databricks
**What goes wrong:** A WHERE on a dimension or a view name resolves to the wrong case.
**Why it happens:** Databricks stores unquoted identifiers lowercase; `DatabricksDialect.normalize_identifier`
already lowercases, and `quote_table_name` folds+backticks. This is **already correct** — but the
record-mode fixture creates `sales_view`, `country`, etc. all lowercase, so it aligns.
**How to avoid:** No new work; just confirm the recorded `000_query.sql` shows backtick-quoted
lowercase names. (Caveat, not a task.)

### Pitfall 5: Metric views need MEASURE()
**What goes wrong:** Raw `SUM(col)` on a metric view → `METRIC_VIEW_MISSING_MEASURE_FUNCTION`.
**Why it happens:** Databricks metric views require `MEASURE()`/`AGG()` to read measures.
**How to avoid:** `DatabricksDialect.wrap_metric` already emits `MEASURE(\`x\`)` [VERIFIED: sql.py
line ~348]. No new work — caveat only. Confirm recorded SQL shows `MEASURE(...)`.

## Code Examples

### Generated SQL contrast (the unit-test assertion target)
```text
# Snowflake / DuckDB (params kept):
SELECT AGG("REVENUE"), AGG("COST"), "COUNTRY"
FROM "SALES_VIEW"
WHERE "COUNTRY" = ?
GROUP BY ALL
ORDER BY "COUNTRY" ASC NULLS LAST
# params == ["US"]
# (Source: tests/integration/cassettes/.../test_filtered_by_dimension_snowflake_engine_/000_query.sql)

# Databricks (literal inlined, params empty):
SELECT MEASURE(`revenue`), MEASURE(`cost`), `country`
FROM `sales_view`
WHERE `country` = 'US'
GROUP BY ALL
ORDER BY `country` ASC NULLS LAST
# params == []
```

### poolhouse URI assertion target
```python
cfg = DatabricksConfig(host="h", http_path="/sql/1.0/warehouses/x",
                       token=SecretStr("t"), catalog="main", schema="myschema")
kwargs = cfg.to_adbc_kwargs()
assert kwargs["uri"] == "databricks://token:t@h:443/sql/1.0/warehouses/x?catalog=main&schema=myschema"
# and: no '?' when catalog and schema are both None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| All dialects emit `?` + params (qmark) | Databricks inlines literals (`supports_parameterized_queries=False`) | Phase 45 | Databricks `.where()` works despite ADBC driver lacking binds |
| `DatabricksConfig.to_adbc_kwargs()` drops catalog/schema | Appends `?catalog=&schema=` to decomposed DSN | Phase 45 (adbc-poolhouse) | Unqualified view names resolve |
| Databricks query execution unverified | Recorded cassettes for all 7 tests | Phase 45 | CI replays Databricks alongside Snowflake |

**Deprecated/outdated:**
- The ADBC Databricks driver capability gap (no binds, no target catalog/schema) is an **upstream
  driver** limitation, not a permanent design choice. If/when the driver implements binds, the
  `supports_parameterized_queries` flag can flip back to `True` and the literal path retires. Keep the
  flag, not a hardcoded branch, so the reversal is one line.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The cleanest builder seam is a single post-pass over assembled `(sql, params)` rather than editing each `_compile_predicate` arm. | Pattern 1 | Low — if a per-arm approach is preferred, the flag+`render_literal` still apply; only the wiring location changes. |
| A2 | A real adbc-poolhouse release bump (vs editable path dep) is the shippable consumption mechanism. | Runtime State Inventory | Low — both work; choice affects CI plumbing only. Planner/operator decides. |
| A3 | The record-mode fixture's lowercase DDL + the DSN schema make the unqualified `Sales(view="sales_view")` resolve on Databricks without model changes. | Pitfalls 3/4 | Medium — confirmed by analogy to Snowflake (which sets schema on the connection and records unqualified SQL); only the live recording fully proves it. |
| A4 | Numeric Python values can be inlined via `repr()` safely (no quoting). | Pattern 1 | Low — standard for int/float; Decimal/date values in `.where()` would need explicit handling if they arise (current tests only filter on a string dimension). |

**Note:** The two driver blockers themselves (no binds, no catalog/schema) and the Go-driver DSN
param names are **VERIFIED ground truth** (memory + docs.databricks.com), not assumptions.

## Open Questions

1. **Cross-repo landing order / mechanism**
   - What we know: poolhouse fix must exist before recording; `pyproject.toml` pins `>=1.2.0`.
   - What's unclear: whether to cut a poolhouse release now or use an editable path dep during the
     record step.
   - Recommendation: land poolhouse fix+test as its own PR/release, bump the pin here, then record.
     Mark the poolhouse work as a distinct prerequisite task in the plan.

2. **Non-string `.where()` values on Databricks**
   - What we know: current integration tests only filter on `country` (a string).
   - What's unclear: whether `render_literal` needs Date/Decimal/datetime handling now.
   - Recommendation: implement string/number/bool/NULL/IN-list (covers all current lookups);
     leave a `# TODO` + raise a clear `NotImplementedError` for unsupported literal types so it
     fails loudly rather than mis-escaping.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| adbc-poolhouse | Both fixes (connection layer) | ✓ | 1.2.0 | — |
| pytest-adbc-replay | Cassette record/replay | ✓ (per memory >=1.1.1) | installed | — |
| Foundry Databricks ADBC driver | **Live recording only** | ✗ | — | None — recording cannot proceed without it |
| Live Databricks SQL Warehouse + creds | **Live recording only** | ✗ (operator-supplied) | — | None — fixture `pytest.skip` if creds absent |
| databricks-sql-connector | Record-mode DDL setup | ✓ (extra, >=4.2.5) | — | — |

**Missing dependencies with no fallback:**
- Foundry Databricks ADBC driver + live warehouse + creds → blocks **only** the recording task.
  The two code fixes and their unit tests need **none** of these (offline-verifiable).

**Missing dependencies with fallback:**
- None for the code fixes.

## Validation Architecture

> nyquist_validation: config.json has no `workflow.nyquist_validation` key → treated as **enabled**.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (+ pytest-adbc-replay plugin) |
| Config file | `pyproject.toml` (markers: `unit`, `adbc_cassette`; `adbc_auto_patch` for replay) |
| Quick run command | `just test` (or `uv run pytest tests/unit -x`) |
| Full suite command | `just test` (unit + jaffle-shop mock) |
| Quality gates | `prek run --all-files` (ruff + basedpyright strict), `just docs-build` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DBX-01 | Databricks `.where()` emits inline literal + empty params | unit | `uv run pytest tests/unit -k "databricks and where" -x` | ❌ Wave 0 |
| DBX-01b | Snowflake/DuckDB `.where()` STILL emit `?` + params (no regression) | unit | `uv run pytest tests/unit -k "where and (snowflake or duckdb)" -x` | ⚠️ likely exists; extend |
| DBX-01c | `render_literal` escapes `'`, `\`, NULL, bool, IN-list correctly for Databricks | unit | `uv run pytest tests/unit -k render_literal -x` | ❌ Wave 0 |
| DBX-02 | `DatabricksConfig.to_adbc_kwargs()` URI carries `?catalog=&schema=` (and none when both None) | unit (poolhouse repo) | `pytest -k to_adbc_kwargs` (in adbc-poolhouse) | ❌ Wave 0 (cross-repo) |
| DBX-03 | All 7 Databricks integration tests replay GREEN from recorded cassettes | integration (replay) | `uv run pytest tests/integration -k databricks` | ❌ cassettes don't exist — record first |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit -x` (SQL-generation assertions — fast, offline).
- **Per wave merge:** `just test` + `prek run --all-files`.
- **Phase gate:** `uv run pytest tests/integration` (all backends replay green, incl. the 7
  Databricks + 7 Snowflake) before `/gsd-verify-work`.

### Signals that prove each blocker is fixed
- **Bind-param fixed:** unit assertion that Databricks `build_select_with_params(query_with_where)`
  returns `("...WHERE `country` = 'US'...", [])` AND Snowflake returns `("...= ?...", ["US"])`.
- **Catalog/schema fixed:** unit assertion on the poolhouse URI string (no warehouse needed).
- **End-to-end:** `pytest tests/integration -k databricks` is 7/7 green on replay (the recorded
  `000_query.sql` shows inline-literal Databricks SQL + `MEASURE()` + backtick lowercase names;
  `000_params.json` is `[]` for the WHERE test).

### Wave 0 Gaps
- [ ] `tests/unit/...test_databricks_dialect_literals.py` — covers DBX-01, DBX-01c
- [ ] Extend existing dialect/SQL-builder unit tests — assert Snowflake/DuckDB unchanged (DBX-01b)
- [ ] adbc-poolhouse `tests/...test_databricks_config.py` — covers DBX-02 (cross-repo)
- [ ] No framework install needed — pytest + pytest-adbc-replay already present.

## Security Domain

> `security_enforcement` not present in config → treated as enabled. The relevant surface here is
> **SQL injection** via literal-inlining.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation / Output Encoding | **yes** | `Dialect.render_literal()` — the single audited SQL-literal escaping site. Escape `\` then `'` for Databricks; double `'` for standard SQL. |
| V6 Cryptography | no | — |
| V2 Authentication | no (token handled by poolhouse `SecretStr`; never logged) | — |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via inlined WHERE value | Tampering | Centralized `render_literal()` with backslash+quote escaping; unit tests with adversarial values (`O'Reilly`, `a\b`, `'; DROP`). This is the trade-off of leaving parameterization: injection surface moves from "none (bind)" to "one audited escaper" — must be tested adversarially. |
| Secret leak (token in DSN/logs) | Info Disclosure | Token stays `SecretStr`; URI is built only inside `to_adbc_kwargs`; do not log the URI. Recording fixture/spike already avoid printing the token. |

**Note:** Literal-inlining is a *necessary* concession to an upstream driver gap, not a design
preference. The `supports_parameterized_queries=False` path is the **only** place Semolina inlines
user values into SQL — every other backend stays parameterized. Flag adversarial-input tests as
mandatory for the WHERE-literal task.

## Sources

### Primary (HIGH confidence)
- `src/semolina/engines/sql.py`, `base.py`, `databricks.py`, `filters.py` — read 2026-06-24 (the
  exact branch points: `placeholder`, `_compile_predicate`, `build_select_with_params`,
  `render_inline`, `wrap_metric`, `quote_table_name`).
- `.venv/.../adbc_poolhouse/_databricks_config.py` + `_snowflake_config.py` — the `to_adbc_kwargs`
  contrast (Snowflake sets `adbc.snowflake.sql.schema`; Databricks drops catalog/schema).
- `tests/integration/conftest.py` + `test_queries.py` + on-disk cassette layout
  (`000_query.sql`/`000_params.json`/`000_result.arrow`; only `*_snowflake_engine_` dirs exist).
- docs.databricks.com go-sql-driver — DSN `catalog=` / `schema=` params [VERIFIED].
- docs.databricks.com SQL string-type — backslash + `\'` escaping [VERIFIED].
- memory `project_databricks_adbc_query_blockers` — the two driver blockers (ground truth).
- `.planning/STATE.md`, ROADMAP Phase 45, 44-CONTEXT.md — scope, precedent, recording-hang resolution.

### Secondary (MEDIUM confidence)
- Databricks ADBC driver capability matrix (no binds / no target catalog-schema) — cited via the
  established findings; the arrow-adbc docs page returned 404 this session, so relied on the
  pre-verified memory note rather than re-fetching.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; all read from installed source + pyproject.
- Architecture / fix design: HIGH — branch points read directly in `sql.py`; cassette match-surface
  confirmed on disk; DSN params verified against official docs.
- Pitfalls (escaping): HIGH — Databricks backslash escaping verified against official docs.
- Cross-repo consumption mechanism: MEDIUM — choice between release-bump vs editable path is a
  planner/operator decision.

**Research date:** 2026-06-24
**Valid until:** 2026-07-24 (stable; the only volatile element is the upstream ADBC Databricks driver
gaining bind-param support, which would let `supports_parameterized_queries` flip back to True).
