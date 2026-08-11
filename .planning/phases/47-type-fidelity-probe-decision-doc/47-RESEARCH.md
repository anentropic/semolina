# Phase 47: Type Fidelity Probe & Decision Doc - Research

**Researched:** 2026-08-12
**Domain:** Warehouse type inference, ADBC result schemas, Arrow → Python type mapping
**Confidence:** HIGH

## Summary

This is a measurement phase, and almost everything it needs to measure is already measurable
offline in this repo today. Three findings reshape how the phase should be planned.

First, the headline disagreement is already proven by evidence sitting in git. The recorded
Snowflake cassettes carry `AGG("REVENUE")` as `decimal128(38, 0)`, while
`SnowflakeEngine.introspect()` maps the same field's `FIXED`/`scale=0` metadata to `int`.
Semolina's row path calls `RecordBatch.to_pylist()`, which turns `decimal128` into
`decimal.Decimal`. So a generated `Metric[int]` annotation already describes a value that
arrives as a `Decimal`. No new recording is required to state that.

Second, `adbc_execute_schema` is not a uniform capability, and its per-driver answer is
knowable from source rather than guesswork. The Snowflake Go driver implements
`ExecuteSchema` via `gosnowflake.WithDescribeOnly` — but explicitly refuses it when bind
parameters are present, which is exactly the shape Semolina's `.where()` produces on
Snowflake. The Databricks driver does not implement it at all and inherits driverbase's
`StatusNotImplemented`. DuckDB implements it, verified by running it in this session.

Third, `pytest-adbc-replay` 1.1.1 serves `adbc_execute_schema` in replay by reading the
schema off the recorded result table. That makes an offline Snowflake probe possible, but it
also makes it *epistemically different* from the other two: the replayed schema proves what
Snowflake's result types are, and proves nothing about whether the driver implements
`ExecuteSchema`. Keeping those two claims apart is the honesty problem at the heart of this
phase.

**Primary recommendation:** Build the comparison as a *generated* artifact — a `just` recipe
driving a script that introspects and probes the same fields on each backend and writes a
committed markdown table — with the DuckDB rows measured live in-process, the Snowflake rows
replayed from copied cassettes, and the Databricks rows split into a real metadata half
(existing cassette) and an explicitly evidence-limited probe half. Write the decision doc
by hand into `docs/src/explanation/type-fidelity.rst` with a thin `.planning/` pointer.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Read warehouse metadata types | Engine (`src/semolina/engines/*.py` `introspect()`) | — | Each dialect owns its own metadata statement; this is where `IntrospectedField.data_type` is born |
| Map SQL type name → Python annotation | Codegen (`src/semolina/codegen/type_map.py`) | — | Pure function layer, no I/O; the only place the policy will land in Phase 48 |
| Read query-time result schema | ADBC driver (`Cursor.adbc_execute_schema` / `fetch_record_batch().schema`) | Test harness (replay) | The warehouse resolves the aggregate's type; Semolina must not guess it |
| Arrow → Python value conversion | pyarrow (`RecordBatch.to_pylist()` in `cursor.py:281`) | — | Determines the *actual* runtime type a user sees; not a Semolina decision |
| Comparison artifact generation | Test/tooling tier (script + `just` recipe) | — | Must be re-runnable so it can be re-verified rather than trusted |
| Decision doc | Docs tier (`docs/src/explanation/`) | `.planning/` pointer | Phases 48 and 50 consume it as spec; users benefit from the same explanation |

**Note:** nothing in this phase touches the runtime query path. Probes are a codegen/CI
concern (locked in the originating todo, "Probe mechanics + timing").

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TYPE-01 | Empirical comparison, per backend, of introspection-time field types against query-time `adbc_execute_schema` result types, run over existing Snowflake cassettes and jaffle-shop DuckDB | §"What introspection produces today", §"Running the probe without live warehouses", §"The four named disagreements" — all three backends have a concrete, reproducible measurement path; Databricks probe half is evidence-limited and the limitation is characterised |
| TYPE-02 | Committed type-mapping decision doc covering Decimal policy, metric-nullability stance, and which source of truth codegen uses | §"Decimal policy inputs", §"Metric nullability", §"`adbc_execute_schema` per driver", §"Artifact placement" |

## Settled Context (substitute for CONTEXT.md)

No `/gsd-discuss-phase` was run for this phase. The following are locked and must not be
re-litigated. Source: `.planning/ROADMAP.md` Phase 47 "Settled going in" and
`.planning/todos/pending/2026-08-01-research-warehouse-type-fidelity-for-field-typing.md`.

### Locked decisions

- VARIANT maps to a `JsonValue` union, not `Any` (recursive
  `str | int | float | bool | None | list | dict`). DTO side uses `pydantic.JsonValue`;
  model side needs a `semolina.JsonValue` alias because semolina core has no pydantic
  dependency.
- Untyped stays a first-class fallback at every layer. `Metric()` ≡ `Metric[Any]()` is
  documented shorthand; the renderer's `TODO: <raw type>` path stays.
- Probes run at codegen time and CI `--check` time. **Never at runtime.**
- `.into(DTO)` needs no probe — the executed result already carries its Arrow schema.
- Layers degrade independently: untyped model fields still build queries; conversion works
  by name against Arrow data.
- Untypeable-case taxonomy (four categories) is settled; category 1 (map gaps) is what the
  Decimal policy plus map additions must fix.

### Claude's discretion (this phase must decide, with evidence)

- Decimal policy for money columns.
- Metric-nullability stance.
- Which source of truth codegen uses (warehouse metadata vs probe).
- Whether filter `value:` typing is worth wiring (research question 4 in the todo; the
  ROADMAP success criteria do not require an answer, so treat as optional-but-welcome).
- Artifact form and location.

### Out of scope

- Implementing the type map (Phase 48).
- `.into(DTO)` (Phase 49) and codegen'd DTOs (Phase 50).
- `render_literal` widening for Databricks (Phase 48, DBX-04).
- arrowmodel level-2 dynamic `create_model`.

## Project Constraints (from CLAUDE.md)

| Directive | Effect on this phase |
|-----------|----------------------|
| `prek run --all-files` before committing (ruff lint+format, basedpyright strict, shellcheck) | Any probe script under `tests/` or `src/` must pass basedpyright strict |
| Avoid `# type: ignore`; pyproject-level exemptions only as last resort | The probe script must be honestly typed; `pyarrow` types are available |
| `just test` = `uv run pytest` + `pushd semolina-jaffle-shop; uv run pytest` | A probe placed in `tests/` runs in the main suite; a probe in `semolina-jaffle-shop/tests/` runs in the second |
| `just docs-build` = `sphinx-build -W` (strict) | Anything added to `docs/src/` must build warning-free and be added to the `explanation/index.rst` toctree |
| Line length 100; docstrings with `"""` on own lines; D213 | Applies to the probe script |
| Docstring `Example:` uses `.. code-block:: python`, never fenced backticks | Applies to any new public function |
| **Mandatory skill for new docs pages / major rewrites:** `@.claude/skills/semolina-docs-author/SKILL.md` | If the decision doc lands in `docs/src/explanation/`, that plan's `<execution_context>` MUST include this line |
| Bug fixes: failing test first, then fix | Not applicable — this phase adds no behaviour changes |
| Docs are Diataxis-classified | A "why we chose Decimal" doc is **Explanation**, not How-to |

## Standard Stack

No new packages. Everything the phase needs is already installed and pinned.

### Core

| Library | Version (verified) | Purpose | Why standard |
|---------|--------------------|---------|--------------|
| `pyarrow` | 24.0.0 | Reads result schemas and converts to Python values | Already the Arrow surface throughout `cursor.py` |
| `adbc-driver-manager` | 1.10.0 | Provides `Cursor.adbc_execute_schema` | The ADBC 1.1 `ExecuteSchema` entry point |
| `adbc-driver-snowflake` | 1.10.0 | Snowflake ADBC driver | Pinned via `semolina[snowflake]` → `adbc-poolhouse[snowflake]` |
| `duckdb` | 1.5.5 (pinned exact) | DuckDB engine + `semantic_views` community extension | `pyproject.toml` pins `duckdb==1.5.5` because the community extension is version-locked |
| `adbc-poolhouse` | 1.6.2 | Owns the pool; builds `db_kwargs` per backend | v0.6 Engine architecture |
| `pytest-adbc-replay` | 1.1.1 | Cassette record/replay, incl. `adbc_execute_schema` | Already the warehouse-test mechanism |

*(Versions read from `uv pip list` in this session's `.venv`; `duckdb==1.5.5` pin read from
`pyproject.toml` `[project.optional-dependencies] duckdb`.)*

### Alternatives considered

| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| Generated comparison table | Hand-written markdown | Cheaper to write, impossible to re-verify. Phases 48/50 consume this as spec; a stale hand-typed table is a wrong spec. Rejected. |
| Probe script under `tests/` | Standalone `scripts/` file | `tests/` gets basedpyright + CI for free and `just test` keeps it honest. `scripts/` would drift. |
| `adbc_execute_schema` for the Snowflake evidence | Read the recorded `.arrow` schema directly with `pyarrow.ipc` | Direct read is simpler but skips the API under test. Use `adbc_execute_schema` via replay (proven below) so the probe code is the same code Phase 48's `--check` will use. |

## Package Legitimacy Audit

**This phase installs no external packages.** Every dependency it uses is already declared in
`pyproject.toml` and present in the lockfile. No `npm view` / `pip index versions` gate is
required for Phase 47.

One forward-looking note, out of scope here but relevant to Phase 49:

| Package | Registry | Age | Downloads | Source repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `arrowmodel` | PyPI | first and only release 2026-07-07 | not checked | `github.com/anentropic/arrowmodel` ("Fast instantiation of Pydantic instances from Arrow data via Rust") | OK — first-party | Not used in Phase 47 |

Provenance: PyPI JSON API reports `author_email` = `Anentropic <ego@anentropic.com>`, and
`gh api repos/anentropic/arrowmodel` returns a public repo with a matching description. It is
the maintainer's own package, not a lookalike. Single release, `1.0.0`, no `project_urls` —
Phase 49 should add the repo URL to its metadata rather than treat the sparse listing as a
red flag. [VERIFIED: pypi.org/pypi/arrowmodel/json + GitHub API, this session]

## What introspection produces today

The probe has to call these exact symbols. All read this session.

| Backend | Metadata statement | Module:lines | Type mapper | Result |
|---------|-------------------|--------------|-------------|--------|
| Snowflake | `SHOW COLUMNS IN VIEW {db}.{schema}.{view}` | `src/semolina/engines/snowflake.py:165` | `snowflake_json_type_to_python` (`codegen/type_map.py:47`) | `IntrospectedField.data_type: str \| None` |
| Databricks | `DESCRIBE TABLE EXTENDED {view} AS JSON` | `src/semolina/engines/databricks.py:167` (`cur.execute`) | `databricks_type_to_python` (`codegen/type_map.py:97`) | same |
| DuckDB | `DESCRIBE SEMANTIC VIEW {view}` **then** `DESCRIBE SELECT * FROM semantic_view(...)` | `src/semolina/engines/duckdb.py:180` and `:215`/`:225` | `duckdb_type_to_python` (`codegen/type_map.py:163`) | same |

`IntrospectedField.data_type` is a **Python annotation string, not a SQL type** — this is the
single most important shape fact for the probe. From
`src/semolina/codegen/introspector.py:39-43`, quoted verbatim:

```python
    name: str
    field_type: Literal["metric", "dimension", "fact"]
    data_type: str | None
    description: str = ""
    source_name: str | None = None
```

And the docstring at `introspector.py:28-30`, verbatim:

> `data_type: Python annotation string (e.g., 'int', 'str', 'datetime.date'), or None if the SQL type has no clean Python equivalent (triggers a TODO comment in the generated output).`

So a comparison of "introspected type vs probed type" is comparing an *annotation string*
against an *Arrow DataType*. The probe must normalise both sides — see
§"Validation Architecture" for why that normalisation is the phase's main circularity risk.

Where the raw SQL type survives: when the mapper returns `None`, the engine writes
`f"TODO: {raw}"` into `data_type` (`snowflake.py:178`, `databricks.py:~200`,
`duckdb.py:239`). That is the only place the raw warehouse type name reaches the artifact, so
the probe should capture the raw type separately rather than parsing it back out of the
`TODO:` string.

### The three current maps, verbatim

From `src/semolina/codegen/type_map.py:15-25` (Snowflake), keys uppercase:

```python
_SNOWFLAKE_TYPE_MAP: dict[str, str] = {
    "TEXT": "str", "REAL": "float", "BOOLEAN": "bool", "DATE": "datetime.date",
    "TIMESTAMP_LTZ": "datetime.datetime", "TIMESTAMP_NTZ": "datetime.datetime",
    "TIMESTAMP_TZ": "datetime.datetime", "TIME": "datetime.time", "BINARY": "bytes",
}
```

plus, `type_map.py:90-92` verbatim:

```python
    if type_name == "FIXED":
        scale = type_json.get("scale", 0)
        return "int" if scale == 0 else "float"
```

From `type_map.py:29-44` (Databricks), note `"decimal": "float"` — quoted verbatim:

```python
_DATABRICKS_TYPE_MAP: dict[str, str] = {
    "string": "str", "bigint": "int", "int": "int", "smallint": "int",
    "tinyint": "int", "long": "int", "double": "float", "float": "float",
    "decimal": "float", "boolean": "bool", "date": "datetime.date",
    "timestamp": "datetime.datetime", "timestamp_ntz": "datetime.datetime",
    "binary": "bytes",
}
```

From `type_map.py:139-160` (DuckDB) — note there is **no `DECIMAL` key**, so DuckDB decimals
fall through to `None` → `TODO:`:

```python
_DUCKDB_TYPE_MAP: dict[str, str] = {
    "VARCHAR": "str", "INTEGER": "int", "BIGINT": "int", "SMALLINT": "int",
    "TINYINT": "int", "HUGEINT": "int", "UBIGINT": "int", "UINTEGER": "int",
    "USMALLINT": "int", "UTINYINT": "int", "DOUBLE": "float", "FLOAT": "float",
    "BOOLEAN": "bool", "DATE": "datetime.date", "TIMESTAMP": "datetime.datetime",
    "TIMESTAMP WITH TIME ZONE": "datetime.datetime", "TIME": "datetime.time",
    "TIME WITH TIME ZONE": "datetime.time", "BLOB": "bytes",
    "INTERVAL": "datetime.timedelta",
}
```

`duckdb_type_to_python` strips parenthesised parameters before lookup
(`type_map.py:198`, verbatim): `base = type_name.split("(")[0].strip().upper()` — so
`DECIMAL(38,2)` becomes `DECIMAL`, misses the map, and returns `None`.

### Two structural facts the planner needs

1. **Nullability is discarded on Databricks, and it is available.** The recorded
   `DESCRIBE TABLE EXTENDED ... AS JSON` payload contains `"nullable": true` per column
   (see the payload quoted below), but `databricks.py`'s parse loop reads only `name`,
   `type`, `is_measure`, and `comment`. Snowflake's `SHOW COLUMNS` parse
   (`snowflake.py:171-203`) also ignores the `null?` column. So "introspection doesn't
   capture nullable" (todo research question 3) is a *code* fact, not a warehouse
   limitation, on at least Databricks. [VERIFIED: src/semolina/engines/databricks.py
   parse loop + recorded cassette payload, this session]

2. **DuckDB already probes.** `DuckDBEngine.introspect` runs
   `DESCRIBE SELECT * FROM semantic_view(...)` because `DESCRIBE SEMANTIC VIEW` reports an
   empty `DATA_TYPE` for every field. Verified live this session — every DIMENSION/METRIC row
   returns `('...', 'DATA_TYPE', '')`. So DuckDB's "introspection" column in the comparison
   table is *already* a query-shaped probe, and its introspected-vs-probed row will trivially
   agree on type while still disagreeing on *mapping* (`DECIMAL(38,2)` → `TODO:`). Say this
   in the artifact or the DuckDB row looks like a false pass.

## `adbc_execute_schema` per driver

This section answers Success Criterion 4 directly.

| Driver | Version checked | `ExecuteSchema` implemented? | Evidence | Fallback needed |
|--------|-----------------|------------------------------|----------|-----------------|
| Snowflake (`adbc_driver_snowflake`) | Go tag `go/v1.10.0` = PyPI `adbc-driver-snowflake` 1.10.0 (installed); also confirmed on `main`, currently `go/v1.12.0` | **Yes**, with a hard exception for bound parameters | `adbc-drivers/snowflake` `go/statement.go:638` (v1.10.0) / `:1014` (main) | Only when the query has bind params |
| Databricks (via `adbc_driver_manager` + Foundry shared lib) | Foundry repo `adbc-drivers/databricks`, latest tag `go/v0.1.3` | **No** — not implemented; inherits driverbase default | `go/statement.go` embeds `driverbase.StatementImplBase` (line 38) and defines no `ExecuteSchema`; `driverbase-go` `driverbase/statement.go:127-129` returns `StatusNotImplemented` | **Yes** — zero-row fallback required |
| DuckDB (libduckdb via `duckdb_adbc_init`, driven by `adbc_driver_manager.dbapi`) | duckdb 1.5.5 | **Yes** — verified by execution | Ran `cur.adbc_execute_schema(q)` on a live in-memory DuckDB semantic view this session; returned the full schema | No |

### Snowflake — implemented, but refuses bind parameters

`adbc-drivers/snowflake` `go/statement.go`, quoted verbatim from tag `go/v1.10.0`
(line numbers from `main`, where the same code sits at 1014-1052):

```go
// ExecuteSchema gets the schema of the result set of a query without executing it.
func (st *statement) ExecuteSchema(ctx context.Context) (schema *arrow.Schema, err error) {
	...
	if st.streamBind != nil || st.bound != nil {
		err = adbc.Error{
			Msg:  "executing schema with bound params not yet implemented",
			Code: adbc.StatusNotImplemented,
		}
		return nil, err
	}

	var loader gosnowflake.ArrowStreamLoader
	loader, err = st.cnxn.cn.QueryArrowStream(gosnowflake.WithDescribeOnly(ctx), st.query)
```

Two consequences the decision doc must record:

- The Snowflake probe is genuinely cheap: `WithDescribeOnly` is Snowflake's describe-only
  query mode, so it is a metadata round trip and not a warehouse-compute execution.
  [VERIFIED: adbc-drivers/snowflake go/statement.go, this session]
- **A Snowflake query carrying bind parameters cannot be probed.** Semolina's Snowflake path
  keeps `?` placeholders (Snowflake and DuckDB keep `?` + params; only Databricks inlines —
  see `.planning/STATE.md:108`). The recorded cassette
  `test_filtered_by_dimension_snowflake_engine_/000_query.sql` is literally
  `... WHERE "COUNTRY" = ? ...`. So any `--check` or codegen probe over a *filtered* canonical
  query will hit `StatusNotImplemented` on Snowflake. This is a Phase 48/50 design
  constraint discovered here, and it belongs in the decision doc.

### Databricks — not implemented

`adbc-drivers/databricks` `go/statement.go` line 38 is `driverbase.StatementImplBase`, and
grepping the file for `ExecuteSchema` returns nothing. The inherited default, quoted verbatim
from `adbc-drivers/driverbase-go` `driverbase/statement.go:127-129`:

```go
func (st *StatementImplBase) ExecuteSchema(context.Context) (*arrow.Schema, error) {
	return nil, st.ErrorHelper.Errorf(adbc.StatusNotImplemented, "execute schema")
}
```

So Databricks needs the zero-row fallback. Note the ADBC Foundry docs do not publish a
feature matrix — `adbc-drivers.org` has no status page, and
`arrow.apache.org/adbc/current/driver/status.html` now returns only a JS redirect stub, so
the driver source is the authoritative reference. [VERIFIED: adbc-drivers/databricks +
driverbase-go source via GitHub API, this session] [CITED: adbc-drivers.org — no matrix page]

### The zero-row fallback

Two shapes, both zero rows:

- `SELECT * FROM (<query>) WHERE 1=0`
- appending `LIMIT 0`

Verified on DuckDB this session that the `WHERE 1=0` wrapper returns a schema byte-identical
to both `adbc_execute_schema` and a real execution. Read the schema from
`cursor.fetch_record_batch().schema` (Semolina already exposes this at `cursor.py:165`).

Caveat for the decision doc: the fallback *compiles and runs* on the warehouse. On Databricks
that is a real query submission — latency and (on a serverless warehouse) a billable
wake-up — where Snowflake's describe-only is not. That asymmetry is a genuine argument for
the doc's "which source of truth" answer.

Unverified: whether the Databricks metric-view planner accepts a `WHERE 1=0` wrapper around
`SELECT MEASURE(...) FROM view GROUP BY ALL` without complaint. Nobody has run it; there is
no Databricks credential in this session. Plan it as a `checkpoint:human-verify` item or mark
the Databricks probe row evidence-limited.

## Running the probe without live warehouses

### The jaffle-shop DuckDB database

There is no `.duckdb` file in the repo. "The jaffle-shop DuckDB database" is built
**in-memory on every physical connection** by SQLAlchemy `connect` listeners. Two candidate
sources, and the phase should probably use both:

**A. `tests/conftest.py` `duckdb_pool` — the cross-backend anchor.** Its `sales_data` DDL
(`tests/conftest.py:101-108`, verbatim):

```sql
CREATE TABLE IF NOT EXISTS sales_data (
    id INTEGER, revenue INTEGER, cost INTEGER,
    country VARCHAR, region VARCHAR, unit_price INTEGER
)
```

and its view (`tests/conftest.py:118-131`) declares `s.revenue AS SUM(s.revenue)`,
`s.cost AS SUM(s.cost)`, dimensions `country`/`region`/`unit_price`.

This mirrors the Snowflake fixture (`tests/integration/conftest.py:184-202`:
`sales_data (revenue NUMBER, cost NUMBER, country VARCHAR, region VARCHAR)` and
`METRICS (sales_data.revenue AS SUM(revenue), sales_data.cost AS SUM(cost))`) and the
Databricks fixture (`:293-317`: `revenue BIGINT, cost BIGINT` and YAML measures
`SUM(revenue)`/`SUM(cost)`). **All three backends have a `sales_view` with the same field
names and the same aggregate expressions.** That is the comparison table's spine: one row per
`(backend, field)` where the field means the same thing everywhere.

**B. `semolina-jaffle-shop/tests/conftest.py` — the decimal evidence.** Its `orders` table
uses `order_total DECIMAL(10, 2)`, `tax_paid DECIMAL(10, 2)`, `order_cost DECIMAL(10, 2)`
with `SUM(...)` metrics, and `customers` uses `DECIMAL(12, 2)`. This is where money actually
lives in this repo, and the only place decimal widening is demonstrable end to end. The
Snowflake fixture's `NUMBER` is already `NUMBER(38,0)`, so it cannot show widening.

Watch out: `semolina-jaffle-shop` is a **separate uv project with its own pytest run**
(`just test` does `pushd semolina-jaffle-shop; uv run pytest`). A probe living there does not
see the root project's fixtures, and vice versa.

### Snowflake — cassettes CAN serve `adbc_execute_schema`, with a copy step

`pytest-adbc-replay` 1.1.1 implements `ReplayCursor.adbc_execute_schema`
(`_cursor.py:364`). Its docstring, verbatim:

> `Replay: derive the schema from the matching recorded result table. PEEK the front of the replay queue first — this does NOT consume the queue or disturb _pending / _fetch_offset, so a schema-before-execute() call leaves the recorded rows intact for a later execute() (D-02 LOCKED).`

**Proven this session.** A temporary test was added, the cassette directory
`integration/test_queries/test_metric_with_dimension_snowflake_engine_/adbc_driver_snowflake.dbapi`
was copied to the new test's node-id path, and the call returned:

```
AGG("REVENUE") | decimal128(38, 0) | nullable=True |
    md={b'logicalType': b'FIXED', b'precision': b'38', b'scale': b'0', ...}
COUNTRY        | string            | nullable=True
```

Three mechanics the plan must get right, all learned the hard way in this session:

1. **Cassette paths are derived from the pytest node id**, so a new probe test cannot read an
   existing test's cassette. The directory must be *copied*. This is not a hack — it is the
   documented in-repo precedent: `tests/integration/conftest.py:20-24` states the async
   fixtures' "cassettes were copied from the sync tests' recordings rather than recorded
   again", and Phase 46 Plan 03 was exactly this spike.
2. **Params are part of the cassette key.** `_make_key` is
   `(canonical_sql, params_to_cache_key(params, registry))` (`_cursor.py:186-188`). The
   recorded `000_params.json` is `[]`, not `null` — calling
   `adbc_execute_schema(SQL)` misses; `adbc_execute_schema(SQL, [])` hits.
3. **SQL is matched after sqlglot normalisation**, so the probe must issue SQL that
   normalises to the recorded form. Safest path: build it with Semolina's own SQL builder
   from the same model + query the recorded test used, rather than pasting a literal.

**The epistemic caveat, and it is the whole point of Success Criterion 4:** in replay, the
"probe" reads a schema Snowflake produced *for an `execute()`*, replayed from disk. It is
real Snowflake evidence about result types. It is **zero** evidence that
`AdbcStatementExecuteSchema` works against a live Snowflake. Those are two different claims
and the artifact must label them differently. The `ExecuteSchema` claim is answered from
driver source (above), not from the cassette.

### Databricks — metadata half only

There is exactly one Databricks introspection cassette:
`integration/test_introspect/test_databricks_introspect_metric_view/...`. Its recorded
payload contains, verbatim:

```json
{ "name": "revenue", "type": { "name": "bigint" }, "nullable": true, "is_measure": true }
```

and the source table is `revenue BIGINT, cost BIGINT` with measure `SUM(revenue)`. The query
cassettes give the query-time half: `measure(revenue)` → `int64`, field metadata
`Spark:DataType:SqlName: 'BIGINT'`. So Databricks' *metadata vs result* comparison is fully
supported by existing cassettes for the `sales_view` fields — what is **not** supported is
any claim about `adbc_execute_schema` itself, and any decimal case (the fixture has no
decimal column).

### There is no Snowflake introspection cassette

`tests/integration/test_introspect.py` is Databricks-only, and says so at lines 11-13,
verbatim:

> `Databricks-only: Snowflake and DuckDB introspection use different metadata statements (SHOW COLUMNS IN VIEW / DESCRIBE SEMANTIC VIEW) and are covered by their own engine unit tests.`

Snowflake's introspection is covered only by a **mock** in
`tests/unit/test_snowflake_engine.py`, whose `_show_columns_cursor` feeds hand-written rows
like `("revenue", "METRIC", json.dumps({"type": "FIXED", "scale": 0}), "")` and asserts
`revenue.data_type == "int"` (line 129).

This is the phase's evidence gap, and the plan must choose one of three postures:

| Option | Cost | Honesty |
|--------|------|---------|
| **(a)** Record a real Snowflake introspection cassette (`pytest --adbc-record=new_episodes`, live creds) | One live session; maintainer has recorded before | Best — closes the gap fully |
| **(b)** Mark Snowflake's introspection column *derived*: real cassette on the query side, code-path derivation on the metadata side | Zero | Acceptable if labelled; the derivation is deterministic and the code is quoted |
| **(c)** Present the mock's output as evidence | Zero | **Unacceptable.** This is exactly the circularity the phase exists to avoid — the mock asserts the answer the type map already produces |

Recommendation: plan for (b) as the guaranteed floor, with (a) as a `checkpoint:human-verify`
task the maintainer can run if creds are handy. Never (c).

### Do not mark the DuckDB probe `@pytest.mark.adbc_cassette`

`pyproject.toml` sets `adbc_auto_patch = ["adbc_driver_snowflake.dbapi",
"adbc_driver_manager.dbapi"]`, and **DuckDB also routes through
`adbc_driver_manager.dbapi`** (poolhouse `_duckdb_config.py:84` gives entrypoint
`duckdb_adbc_init` and `:88` resolves `adbc_driver_duckdb.driver_path()`). The plugin wraps
connections only for tests carrying the marker
(`tests/integration/conftest.py:12-13`), so an unmarked DuckDB probe runs live in-process.
Marking it would silently divert it into cassette replay. Note also that
`adbc_dialect` maps `adbc_driver_manager.dbapi` to the `databricks` sqlglot dialect, so a
marked DuckDB test would additionally normalise its SQL as Databricks.

## The four named disagreements

All four measured live on DuckDB 1.5.5 + `semantic_views` this session, cross-checked against
official warehouse docs. Each has a minimal reproducing query, ready to become an acceptance
criterion.

### 1. Decimal precision widening under SUM

**Smallest query** (over the `semolina-jaffle-shop` `orders` view, `order_total DECIMAL(10,2)`):

```sql
SELECT * FROM semantic_view('orders', metrics := ['order_total'])
```

**Observed (DuckDB 1.5.5):** `order_total: decimal128(38, 2)` — source `DECIMAL(10,2)`,
result precision 38. `to_pylist()` yields `Decimal('30.75')`.
Contrast: `MAX(order_total)` → `decimal128(10, 2)` — **no** widening, only accumulating
aggregates widen. [VERIFIED: live DuckDB run, this session]

**Current Semolina output for that field:** `data_type='TODO: DECIMAL(38,2)'` → renderer emits
`Metric[Any]` + a TODO comment (`python_renderer.py:111-114`).

**Documented behaviour elsewhere:**
- Databricks: `sum(DECIMAL(p, s))` → `DECIMAL(p + min(10, 31-p), s)`; integral → `BIGINT`.
  [CITED: docs.databricks.com/aws/en/sql/language-manual/functions/sum]
- Snowflake: the SUM docs say only *"Numeric values are summed into an equivalent or larger
  data type"* — no precision/scale rule is published.
  [CITED: docs.snowflake.com/en/sql-reference/functions/sum] The recorded cassette shows
  `NUMBER` (i.e. `NUMBER(38,0)`) summing to `decimal128(38, 0)`, which is consistent but
  cannot demonstrate widening because the input is already at max precision. **If a
  re-recording happens, add a `NUMBER(10,2)` column to the Snowflake fixture** — that single
  change makes Snowflake widening measurable.

**Cross-backend disagreement, the money headline:** for an equivalent decimal column, the three
type maps disagree three ways — Snowflake `FIXED` scale>0 → `float`, Databricks `decimal` →
`float`, DuckDB `DECIMAL` → `None`/`TODO:`. Meanwhile all three produce `decimal128` on the
wire, so `to_pylist()` returns `Decimal` in every case. Every existing mapping is wrong.

### 2. `AVG(int)` → double

**Smallest query:**

```sql
SELECT * FROM semantic_view('orders', metrics := ['avg_order_count'])
-- where the metric is AVG(o.order_count), order_count INTEGER
```

**Observed:** `avg_order_count: double`, Python `float`. Also `AVG(DECIMAL(10,2))` → `double`
on DuckDB. [VERIFIED: live DuckDB run, this session]

**Documented:** Databricks `avg()` returns `DECIMAL(p + 4, s + 4)` for `DECIMAL(p,s)` and
*"In all other cases the result is a DOUBLE"*.
[CITED: docs.databricks.com/aws/en/sql/language-manual/functions/avg] Note this makes
Databricks and DuckDB **disagree** on `AVG(decimal)`: Databricks widens to decimal, DuckDB
collapses to double. Worth a row of its own. Snowflake's AVG page does not document a return
type at all; the arithmetic-operators page has no aggregate section either.
[CITED: docs.snowflake.com/en/sql-reference/functions/avg — return type undocumented]
Snowflake's `AVG` result type is **unverified** and should be marked so.

### 3. `COUNT` → int64

**Smallest query:**

```sql
SELECT * FROM semantic_view('orders', metrics := ['n_orders'])  -- COUNT(o.id)
```

**Observed:** `n_orders: int64`, Python `int`, **and never NULL** — see next item.
[VERIFIED: live DuckDB run, this session]

**Bonus finding worth a row:** `MIN(order_count)` over an `INTEGER` column returns `int32`,
not `int64`. So "integer metric" is not one type; the probe must record the exact Arrow type.

**Bonus finding #2, DuckDB-specific and easy to get wrong:** plain
`SELECT SUM(n) FROM t` where `n INTEGER` gives `HUGEINT`, which pyarrow renders as
`decimal128(38, 0)` → Python `Decimal`. Through the `semantic_views` extension the same
`SUM(o.n)` comes back as `int64` → `int`. The extension casts down. Both measured this
session. The comparison must therefore probe *through `semantic_view(...)`*, not with a
hand-written `SELECT SUM(...)`, or it will report a type users never see.

### 4. Metric nullability on empty groups

**Smallest query** (the canonical case — an aggregate over an empty input set):

```sql
SELECT SUM(amt) s, COUNT(amt) c, AVG(n) a, MIN(n) m FROM t WHERE false
```

**Observed:** one row, `{'s': None, 'c': 0, 'a': None, 'm': None}`. Schema
`s: decimal128(38,2) | c: int64 | a: double | m: int32`.
[VERIFIED: live DuckDB run, this session]

**Second shape — a group that exists but whose metric inputs are all NULL:**

```sql
-- region 'CA' has one row with amt IS NULL
SELECT * FROM semantic_view('sv', metrics := ['total','cnt','avg_cnt','mx'],
                                  dimensions := ['region'])
```

**Observed:** `{'region': 'CA', 'total': None, 'cnt': 0, 'avg_cnt': None, 'mx': None}`.
[VERIFIED: live DuckDB run, this session]

**Three conclusions the decision doc must state:**

- **Metric nullability is not uniform.** `SUM`/`AVG`/`MIN`/`MAX` are NULL-able; `COUNT` is
  not — it returns `0`. A blanket `T | None` for all metrics would be wrong for COUNT, and a
  blanket `T` would be wrong for the rest.
- **A `GROUP BY` that matches nothing yields zero rows, not NULL rows.** The NULL only
  appears when a group exists with no non-NULL inputs, or when the aggregate is ungrouped.
  The success criterion's phrase "metric nullability on empty groups" therefore needs
  precise wording in the artifact, or reviewers will look for the wrong thing.
- **The Arrow `nullable` flag is useless as evidence.** Every field in every cassette and
  every live probe this session came back `nullable=True`, including `COUNT`. Nullability
  must be decided by policy from the aggregate's semantics, not read off the probe. This is
  a genuine limit on "probe as source of truth" and belongs in the decision doc.

  Corroborating detail: the one field observed as `NOT NULL` anywhere is Databricks'
  `json_metadata` column in the `DESCRIBE ... AS JSON` cassette — a metadata string, not a
  metric.

## Decimal policy inputs

### What actually happens today

`SemolinaCursor` builds rows with `batch.to_pylist()` (`src/semolina/cursor.py:281`). pyarrow
converts `decimal128` → `decimal.Decimal` unconditionally. Confirmed live: a DuckDB
`SUM(DECIMAL(10,2))` metric arrives as `Decimal('30.75')`; the Snowflake cassette's
`decimal128(38,0)` would arrive as `Decimal('5800')`. Meanwhile the generated annotation says
`float` (Snowflake scale>0, Databricks decimal) or `int` (Snowflake scale=0) or `Any`
(DuckDB). **The current annotations are already wrong at runtime**; choosing `Decimal` is not
a change of behaviour, it is a correction of the annotation.

### The three options

| Option | What breaks | What works |
|--------|-------------|-----------|
| `decimal.Decimal` | JSON serialisation needs a custom encoder (pydantic v2 handles it; `json.dumps` does not); arithmetic with `float` raises `TypeError`; `float(d)` needed at chart boundaries | Exact round trip; matches what pyarrow already returns; pydantic v2 has native `Decimal` support; matches the audience's money semantics |
| `float` | Silently lossy for money — the exact failure mode a revenue-querying audience must not hit; the annotation would also be a *lie* about the runtime type, since `to_pylist()` still returns `Decimal` | Convenient arithmetic |
| `str` | Every consumer must parse; ordering/comparison break | Lossless transport |

`float` has an additional problem specific to this stack: it does not describe reality unless
Semolina *also* forces the Snowflake driver's `use_high_precision` off. The Snowflake driver
option, verbatim from `adbc-drivers/snowflake` `go/driver.go:74-80`:

```go
	// OptionUseHighPrecision controls the data type used for NUMBER columns
	// using a FIXED size data type. By default, this is enabled and NUMBER
	// columns will be returned as Decimal128 types using the indicated
	// precision and scale of the type. If disabled, then fixed-point data
	// with a scale of 0 will be returned as Int64 columns, and a non-zero
	// scale will return a Float64 column.
	OptionUseHighPrecision = "adbc.snowflake.sql.client_option.use_high_precision"
```

That `int64`/`float64` split is *exactly* the current `snowflake_json_type_to_python` rule.
So the existing map is a faithful copy of the driver's **non-default** behaviour. And
`adbc_poolhouse._snowflake_config` never sets the option, so the default (Decimal128) is what
Semolina actually gets — which the cassettes confirm.

**This is the decisive evidence for the Decimal policy**, and the decision doc should say so
explicitly: the map is not merely imprecise, it encodes a driver configuration Semolina does
not use.

The doc should also name the alternative it is rejecting: Semolina *could* pass
`use_high_precision=disabled` and make `float` true. Against that — it is lossy for money by
construction, it is a per-driver knob with no Databricks or DuckDB equivalent (so the three
backends would diverge again, which is the exact thing TYPE-03 exists to end), and
`adbc-poolhouse`'s `SnowflakeConfig` exposes no pass-through for arbitrary `db_kwargs`, so
setting it would need an upstream change.

### Downstream Decimal behaviour to check while writing the doc

| Consumer | Behaviour | Status |
|----------|-----------|--------|
| `to_pylist()` (Semolina rows) | `decimal128` → `decimal.Decimal` | [VERIFIED: live run] |
| pydantic v2 | Native `Decimal` field support | [ASSUMED] — confirm before Phase 49 relies on it |
| `pyarrow.Table.to_pandas()` | decimal → `object` dtype holding `Decimal` (not float64) | [ASSUMED] — matters for Phase 49's `fetch_df()`; measure it, it is one line |
| polars | Decimal support has historically been feature-gated | [ASSUMED] — matters for `fetch_polars()`; out of scope here but flag it |
| arrowmodel | Rust Arrow → pydantic path; decimal handling unknown | [ASSUMED] — Phase 49's problem |

Three of five rows are assumptions. The probe script can convert them to measurements at
near-zero cost by adding a `to_pandas()` dtype column for one decimal field. Recommend doing
so — it costs one line and pre-empts a Phase 49 surprise.

## Architecture Patterns

### Probe data flow

```
                    ┌───────────────────────────────────────────┐
                    │  probe driver (one row per backend/field)  │
                    └──────────────┬────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
      ┌───────────────┐    ┌───────────────┐    ┌───────────────┐
      │   DuckDB      │    │  Snowflake    │    │  Databricks   │
      │  (live, in-   │    │  (cassette    │    │  (cassette    │
      │   process)    │    │   replay)     │    │   replay)     │
      └───────┬───────┘    └───────┬───────┘    └───────┬───────┘
              │                    │                    │
      ┌───────┴───────┐    ┌───────┴───────┐    ┌───────┴───────┐
      │ A) introspect │    │ A) introspect │    │ A) introspect │
      │    live       │    │    DERIVED    │    │    cassette   │
      │               │    │    (no        │    │    (DESCRIBE  │
      │               │    │     cassette) │    │     AS JSON)  │
      ├───────────────┤    ├───────────────┤    ├───────────────┤
      │ B) probe:     │    │ B) probe:     │    │ B) probe:     │
      │    adbc_      │    │    replayed   │    │    replayed   │
      │    execute_   │    │    result     │    │    result     │
      │    schema     │    │    schema     │    │    schema     │
      ├───────────────┤    ├───────────────┤    ├───────────────┤
      │ C) values:    │    │ C) values:    │    │ C) values:    │
      │    to_pylist  │    │    to_pylist  │    │    to_pylist  │
      └───────┬───────┘    └───────┬───────┘    └───────┬───────┘
              │                    │                    │
              └────────────────────┼────────────────────┘
                                   ▼
                   ┌───────────────────────────────┐
                   │  normalise + diff A vs B vs C │
                   │  (record raw forms, not just  │
                   │   the verdict)                │
                   └───────────────┬───────────────┘
                                   ▼
                   ┌───────────────────────────────┐
                   │  committed comparison table   │
                   │  + evidence-limitation notes  │
                   └───────────────┬───────────────┘
                                   ▼
                   ┌───────────────────────────────┐
                   │  hand-written decision doc    │
                   │  (Decimal / nullability /     │
                   │   source of truth / per-      │
                   │   driver ExecuteSchema)       │
                   └───────────────────────────────┘
```

Column C (actual Python value type from `to_pylist()`) is not in the ROADMAP's success
criteria, but it is the column that makes the artifact persuasive — it shows the *user-visible*
consequence rather than an Arrow type a reader must translate. Recommend including it.

### Component responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| Probe driver | `tests/type_fidelity/probe.py` (proposed) | Orchestrates A/B/C per backend, emits rows |
| Snowflake cassette copies | `tests/integration/cassettes/<probe-node-id>/...` | Makes the Snowflake half replayable |
| Table writer | same script, `--write` mode | Renders the committed markdown |
| Drift guard | pytest test | Fails if regenerating changes the committed table |
| Decision doc | `docs/src/explanation/type-fidelity.rst` | Human judgement, cites the table |

### Anti-patterns to avoid

- **Comparing `data_type` strings to Arrow type strings without recording both raw forms.**
  A row that says "MISMATCH" and nothing else is useless to Phase 48. Record the raw
  warehouse type, the mapped annotation, the Arrow type, and the Python value type.
- **Using the unit-test mocks as evidence.** `tests/unit/test_snowflake_engine.py` hand-feeds
  `{"type": "FIXED", "scale": 0}` and asserts `"int"`. Restating that in the artifact is
  circular.
- **Probing with hand-written `SELECT SUM(...)` instead of through `semantic_view(...)`.**
  Measured this session: DuckDB gives `HUGEINT`/`decimal128(38,0)` for the former and `int64`
  for the latter. Only the latter is what users get.
- **Letting the comparison table be a pass/fail summary.** Success Criterion 2 explicitly
  requires each concrete disagreement to be named.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---------|-------------|-------------|-----|
| Getting a query's result schema | A SQL-type-string parser over `DESCRIBE` output | `cursor.adbc_execute_schema(sql, params)`, falling back to `cursor.fetch_record_batch().schema` | The driver already resolves it; a parser would reimplement warehouse type inference |
| Replaying warehouse traffic | A bespoke fixture recorder | `pytest-adbc-replay` cassettes (already configured in `pyproject.toml`) | Already the project mechanism; it even handles `adbc_execute_schema` |
| Arrow type → Python type | A lookup table written by hand | `pyarrow`'s own `to_pylist()`, observed | The point of the phase is to observe, not to assert |
| Normalising SQL for cassette matching | String munging | Semolina's `SQLBuilder` producing the same statement the recorded test produced | Cassette keys are sqlglot-normalised; hand-written SQL drifts |
| Rendering the markdown table | A template engine | f-strings / `str.join` | 10 columns; jinja2 is already a dep but adds indirection for no gain |

**Key insight:** every "clever" shortcut in this phase converts a measurement into an
assertion, which is precisely the failure mode the phase was created to prevent.

## Common Pitfalls

### Pitfall 1: Circular evidence

**What goes wrong:** the probe reads a type through a code path that already applies
Semolina's type map, so the comparison confirms the map against itself.
**Why it happens:** `IntrospectedField.data_type` is *already mapped*; the raw warehouse type
survives only inside the `TODO: ` prefix. It is tempting to compare mapped-to-mapped.
**How to avoid:** capture the raw metadata type from the engine's own statement output
(re-run `SHOW COLUMNS` / `DESCRIBE` and keep the raw column), and capture the Arrow type
straight from the schema. Compare raw-vs-raw and mapped-vs-actual as separate columns.
**Warning signs:** a comparison table where every DuckDB row says "match"; a column whose
values are all drawn from `_*_TYPE_MAP`'s value set.

### Pitfall 2: Treating replay as proof of driver capability

**What goes wrong:** the artifact claims Snowflake supports `adbc_execute_schema` because the
replayed call succeeded.
**Why it happens:** `ReplayCursor.adbc_execute_schema` succeeds regardless of what the real
driver does.
**How to avoid:** answer the capability question from driver source (done above) and label the
replayed value as "result schema, recorded" rather than "ExecuteSchema, verified".
**Warning signs:** a single table column trying to carry both claims.

### Pitfall 3: Cassette key misses

**What goes wrong:** the probe raises `CassetteMissError` and the plan concludes cassettes
cannot serve schemas.
**Why it happens:** three separate causes — node-id-derived path, `None` vs `[]` params, SQL
that does not sqlglot-normalise to the recorded form.
**How to avoid:** copy the cassette dir to the probe's node-id path, pass `[]`, and build SQL
through `SQLBuilder`. All three verified this session.
**Warning signs:** `Cassette directory does not exist` (path) vs `Interaction N not found`
(key mismatch — params or SQL).

### Pitfall 4: The DuckDB probe silently replaying

**What goes wrong:** the DuckDB probe returns Databricks-shaped results or misses cassettes.
**Why it happens:** `adbc_auto_patch` includes `adbc_driver_manager.dbapi`, which DuckDB also
uses, and `adbc_dialect` maps that module to the `databricks` sqlglot dialect.
**How to avoid:** do not put `@pytest.mark.adbc_cassette` on the DuckDB probe.
**Warning signs:** DuckDB SQL appearing in a `CassetteMissError`.

### Pitfall 5: Fixture rebuild on every physical connection

**What goes wrong:** data inserted mid-test vanishes, or the semantic view is missing.
**Why it happens:** poolhouse's DuckDB pool clones independent in-memory instances per
physical connection; `tests/conftest.py:96-97` documents this. Observed this session — an
`INSERT` issued after the fixture set-up did not appear in a subsequent grouped result.
**How to avoid:** put all probe data in the `connect` listener, or use `pool_size=1` and a
single connection, or use a file-backed database.
**Warning signs:** a group you inserted is absent from the result.

### Pitfall 6: Snowflake bind parameters break the probe

**What goes wrong:** `--check` on a filtered query returns `NOT_IMPLEMENTED` on Snowflake.
**Why it happens:** documented refusal in the driver (quoted above); Semolina keeps `?`
placeholders on Snowflake.
**How to avoid:** probe the *unfiltered* canonical query shape, or inline literals for the
probe only. Record the constraint in the decision doc so Phase 48 designs `--check` around it.
**Warning signs:** probes passing on unfiltered queries and failing on `.where()` ones.

## Code Examples

### Reading a probe schema (works on all three backends)

```python
# Source: adbc_driver_manager/dbapi.py:1127 (installed 1.10.0), verified live this session
def probe_schema(cursor: Any, sql: str, params: list[object]) -> pyarrow.Schema:
    """
    Return a query's result schema without fetching rows.

    Prefers ADBC ExecuteSchema; falls back to a zero-row execution for drivers
    that answer NOT_IMPLEMENTED (Databricks) or that reject bound parameters
    (Snowflake).
    """
    from adbc_driver_manager import NotSupportedError

    try:
        return cursor.adbc_execute_schema(sql, params)
    except NotSupportedError:
        cursor.execute(f"SELECT * FROM ({sql}) WHERE 1=0", params)
        reader = cursor.fetch_record_batch()
        try:
            return reader.schema
        finally:
            reader.close()
```

Unverified detail: the exact exception class the driver manager raises for
`StatusNotImplemented` — `NotSupportedError` is the DBAPI-mapped candidate, but this was not
exercised against a NOT_IMPLEMENTED driver in this session (DuckDB and the replay cursor both
succeeded). The plan should have its first task confirm the class rather than assume it; a
`ProgrammingError`/`OperationalError` catch-all with a message check is the safe fallback.

### Copying a cassette so a probe test can replay it

```python
# Source: precedent documented at tests/integration/conftest.py:20-24
# (Phase 46's async fixtures replay cassettes copied from the sync tests).
# Verified working in this session.
SRC = (
    "tests/integration/cassettes/integration/test_queries/"
    "test_metric_with_dimension_snowflake_engine_/adbc_driver_snowflake.dbapi"
)
DST = (
    "tests/integration/cassettes/integration/test_type_fidelity/"
    "test_snowflake_probe/adbc_driver_snowflake.dbapi"
)
# shutil.copytree(SRC, DST, dirs_exist_ok=True)  -- committed, not generated at runtime

# then, inside the test:
schema = cursor.adbc_execute_schema(sql, [])  # note: [] not None -- params are part of the key
```

### Reading a cassette's recorded schema directly (for the derivation path)

```python
# Verified this session. Cassettes are Arrow IPC *file* format, not stream --
# pa.ipc.open_stream() raises ArrowInvalid on them.
import pyarrow as pa

with pa.ipc.open_file("<cassette>/000_result.arrow") as reader:
    schema = reader.schema
```

## Artifact placement

### Recommendation

| Artifact | Location | Form | Rationale |
|----------|----------|------|-----------|
| Comparison table | `.planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md` | **Generated**, committed | It is evidence with a date, not user documentation. Regenerable so a reviewer can re-run it; committed so Phase 48 can read it without a warehouse. |
| Probe script | `tests/type_fidelity/probe.py` | Python, basedpyright-strict | Under `tests/` so `just test` and `prek` police it |
| Regeneration entry point | `just type-fidelity` recipe | one line | Discoverable; the repo already uses `just` for `test`/`docs-build` |
| Drift guard | `tests/type_fidelity/test_probe.py` | pytest | Fails when regenerating would change the committed table |
| Decision doc | `docs/src/explanation/type-fidelity.rst` | Hand-written Diataxis **Explanation** | Phases 48/50 need it durable; users need to know why their money column is a `Decimal` |
| Pointer | `.planning/phases/47-.../47-DECISIONS.md` | 10 lines + link | Keeps `.planning/` self-contained without duplicating content that will drift |

### Why both locations rather than one

`.planning/` alone: Phase 48 can read it, but a user who finds `Metric[Decimal]` in generated
code has nowhere to learn why. `docs/src/` alone: the *measurement* is dated internal
evidence that would clutter a user-facing page, and a `sphinx-build -W` failure would then
block a planning artifact. Splitting them puts each in the tier that owns it.

**If the decision doc lands in `docs/src/explanation/`, three CLAUDE.md obligations attach:**

1. The plan's `<execution_context>` MUST include `@.claude/skills/semolina-docs-author/SKILL.md`
   (new page ⇒ full workflow, mandatory).
2. `docs/src/explanation/index.rst` toctree must gain the new entry — it currently lists only
   `semantic-views`.
3. `just docs-build` runs with `-W`; any warning fails the build.

Content-type check against the project's own rules: this page states background and design
rationale with no step-by-step instructions, so **Explanation** is correct — not How-to.

## Validation Architecture

### Test framework

| Property | Value |
|----------|-------|
| Framework | pytest (`pytest>=8.0.0`, dev group); pytest 9.x resolved in `.venv` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/type_fidelity -x` |
| Full suite command | `just test` (`uv run pytest` + `pushd semolina-jaffle-shop; uv run pytest`) |

Note `addopts` includes `--doctest-modules` and `testpaths = ["tests", "src"]`, so docstring
examples in the probe module are executed. Keep probe docstring examples non-executing or
correct.

### Phase requirements → test map

| Req | Behavior | Test type | Automated command | Exists? |
|-----|----------|-----------|-------------------|---------|
| TYPE-01 | Probe produces a row per (backend, field) with raw type, mapped annotation, Arrow type, Python value type | unit | `uv run pytest tests/type_fidelity/test_probe.py::test_probe_covers_all_backends -x` | ❌ Wave 0 |
| TYPE-01 | Regenerating the table yields byte-identical output to the committed file | unit | `uv run pytest tests/type_fidelity/test_probe.py::test_table_is_not_stale -x` | ❌ Wave 0 |
| TYPE-01 | Each of the four named disagreements has a dedicated assertion on a measured value | unit | `uv run pytest tests/type_fidelity/test_disagreements.py -x` | ❌ Wave 0 |
| TYPE-01 | Snowflake probe replays from a copied cassette | integration | `uv run pytest tests/type_fidelity/test_snowflake_replay.py -x` | ❌ Wave 0 |
| TYPE-02 | Decision doc exists and states all four required answers | manual + docs build | `just docs-build` for build; content is a `checkpoint:human-verify` | ❌ Wave 0 |
| TYPE-02 | Per-driver `ExecuteSchema` answer is recorded | manual | reviewer reads the doc's driver table | ❌ Wave 0 |

### Sampling rate

- **Per task commit:** `uv run pytest tests/type_fidelity -x`
- **Per wave merge:** `just test`
- **Phase gate:** `just test` green plus `just docs-build` green before `/gsd-verify-work`

### Wave 0 gaps

- [ ] `tests/type_fidelity/__init__.py`
- [ ] `tests/type_fidelity/probe.py` — the probe driver
- [ ] `tests/type_fidelity/test_probe.py` — coverage + staleness guard
- [ ] `tests/type_fidelity/test_disagreements.py` — the four named disagreements
- [ ] `tests/type_fidelity/test_snowflake_replay.py` — cassette-replay probe
- [ ] Copied Snowflake cassette directories under `tests/integration/cassettes/`
- [ ] `just type-fidelity` recipe
- [ ] Framework install: none needed

### How a reviewer validates that the comparison is HONEST

This is the phase's central risk, so it gets explicit machinery rather than a promise.

**The failure mode:** the probe reads a type through Semolina's own type map, so the artifact
restates the map back at the reader and every row says "match". Three concrete vectors:
(a) comparing `IntrospectedField.data_type` against a value derived from the same
`_*_TYPE_MAP`; (b) sourcing the "warehouse" side from the unit-test mocks in
`tests/unit/test_snowflake_engine.py`; (c) sourcing the "probe" side from
`DESCRIBE SELECT`, which for DuckDB is the very statement `introspect()` already runs.

**Four defences, each mechanically checkable:**

1. **A known-mismatch canary.** At least one row must be a mismatch that is asserted *by
   value*, not by "differs". Use the DuckDB decimal metric:
   introspection yields `TODO: DECIMAL(38,2)`, the probe yields `decimal128(38, 2)`, the
   value is `Decimal`. If a future refactor accidentally routes both columns through the same
   source, this assertion flips to "match" and the test fails. A comparison that cannot
   produce a mismatch is not measuring anything.

2. **Provenance is a column, not prose.** Every cell carries how it was obtained:
   `live` / `cassette-replay` / `derived-from-code` / `driver-source`. A reviewer scanning for
   `derived-from-code` in the *probe* column has found circularity immediately. The Snowflake
   introspection column will legitimately read `derived-from-code` under option (b) — that is
   the point of labelling it.

3. **The probe column never imports `semolina.codegen.type_map`.** Enforceable as a test:
   assert the raw Arrow types recorded in the table are drawn from pyarrow's vocabulary
   (`decimal128(38, 2)`, `int64`, `double`) and never from the map's value vocabulary
   (`int`, `float`, `str`, `datetime.date`). Two disjoint vocabularies make accidental
   crossover visible.

4. **Third-party corroboration for at least one row per backend.** The Arrow types must agree
   with the vendor's documented aggregate return type where one is published — Databricks'
   `sum(DECIMAL(p,s)) → DECIMAL(p + min(10, 31-p), s)` and `avg(...) → DOUBLE` are the
   available anchors. Snowflake publishes neither for SUM precision nor AVG at all; mark
   those cells `undocumented — measured only` rather than inventing a rule.

**What a reviewer should do, in order:**

1. Run `just type-fidelity` and confirm `git diff` is empty. A dirty diff means the committed
   table is stale, which means Phase 48's spec is stale.
2. Scan the provenance column for any `derived-from-code` in a probe cell.
3. Confirm the canary row still reports a mismatch.
4. Spot-check one Snowflake row against the raw cassette by opening
   `000_result.arrow` with `pyarrow.ipc.open_file` — bypassing every line of Semolina code.
   If that number disagrees with the table, the table is fiction.

## State of the Art

| Old approach | Current approach | When changed | Impact |
|--------------|------------------|--------------|--------|
| ADBC driver docs at `arrow.apache.org/adbc/current/driver/*` | Drivers moved to the ADBC Driver Foundry (`adbc-drivers.org`, `github.com/adbc-drivers/*`); the old Apache URLs now serve a JS redirect stub | Snowflake driver no longer under `apache/arrow-adbc/go/adbc/driver/` | Driver capability questions must be answered from `github.com/adbc-drivers/<name>`, not the Apache docs site |
| `adbc-driver-snowflake` from Apache | Foundry-tagged `go/v1.10.x`–`go/v1.12.0`; PyPI latest 1.11.0 | ongoing | Repo pins 1.10.0 transitively via poolhouse; the `ExecuteSchema` behaviour is identical at v1.10.0 and main (both verified) |
| Databricks ADBC driver unavailable | `adbc-drivers/databricks` exists, latest `go/v0.1.3` | 2026-01-28 announcement | Still 0.1.x — `ExecuteSchema` absent; expect it to gain the method eventually, so the decision doc should say "as of v0.1.3" |

**Deprecated / outdated in this repo's assumptions:**

- The originating todo says the probe "may be `NOT_IMPLEMENTED`" per driver. That is now
  resolved: Snowflake yes-with-caveat, Databricks no, DuckDB yes.
- The todo's "CI wrinkle: `--check` could run offline via pytest-adbc-replay cassettes" is
  confirmed feasible — `ReplayCursor.adbc_execute_schema` exists in 1.1.1.

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | pydantic v2 supports `Decimal` fields natively | Decimal policy | Low — widely known, but Phase 49 depends on it; one-line check |
| A2 | `pyarrow.Table.to_pandas()` renders decimal128 as `object`-dtype `Decimal`, not float64 | Decimal policy | Medium — changes the `fetch_df()` story in Phase 49; measure in the probe |
| A3 | polars Decimal support is feature-gated / partial | Decimal policy | Medium — affects `fetch_polars()` (RESULT-02, Phase 49); out of scope here but flag |
| A4 | `adbc_driver_manager` surfaces `StatusNotImplemented` as `NotSupportedError` | Code Examples | Medium — the fallback `except` clause would not fire; first task should confirm empirically |
| A5 | Databricks accepts a `WHERE 1=0` wrapper around a `MEASURE(...) ... GROUP BY ALL` metric-view query | Zero-row fallback | High for Phase 48/50 — if the metric-view planner rejects it, Databricks has neither ExecuteSchema nor a fallback. Needs a live check or an explicit evidence-limited note |
| A6 | Snowflake `AVG(NUMBER(p,s))` result precision/scale rule | Four disagreements | Medium — undocumented by Snowflake; do not state a rule, mark measured-only |
| A7 | arrowmodel handles Arrow decimal128 → pydantic `Decimal` | Decimal policy | Medium — Phase 49's concern, not this phase's |
| A8 | The maintainer has live Snowflake credentials available to re-record | Snowflake evidence gap | Low — option (b) is the planned floor, so this only affects whether option (a) is reachable |

## Open Questions

1. **Should the Snowflake fixture gain a `NUMBER(10,2)` column?**
   - Known: the current fixture uses bare `NUMBER` = `NUMBER(38,0)`, already at max precision,
     so Snowflake decimal *widening* is not demonstrable from existing cassettes.
   - Unclear: whether the phase is willing to spend a re-recording session.
   - Recommendation: not required for TYPE-01 (DuckDB demonstrates widening, and Databricks
     documents its rule). Record it as a follow-up todo so the gap is visible rather than
     silently absent.

2. **Does Databricks' metric-view planner accept the zero-row wrapper?** (A5)
   - Known: Databricks has no `ExecuteSchema`, so the fallback is its only path.
   - Unclear: whether `SELECT * FROM (SELECT MEASURE(m) FROM v GROUP BY ALL) WHERE 1=0` plans.
   - Recommendation: a `checkpoint:human-verify` task, or an explicit
     "Databricks probe: unverified" row. Do not assert it.

3. **Metric nullability — policy, since the probe cannot answer it.**
   - Known: Arrow reports `nullable=True` for everything, including COUNT; the real rule is
     per-aggregate (COUNT never NULL, SUM/AVG/MIN/MAX NULL-able on empty input).
   - Unclear: whether Semolina can see the aggregate expression at codegen time. It can on
     DuckDB (`DESCRIBE SEMANTIC VIEW` returns `EXPRESSION` = `SUM(o.order_total)`, observed
     this session) and on Databricks (`view_text` YAML carries `expr: SUM(revenue)`, present
     in the recorded payload). Snowflake's `SHOW COLUMNS` does not obviously carry it, though
     `SHOW SEMANTIC METRICS` exists and returns `data_type` per metric
     [CITED: docs.snowflake.com/en/sql-reference/sql/show-semantic-metrics].
   - Recommendation: the decision doc should choose a *uniform* stance (all metrics
     `T | None`, with COUNT as a documented over-approximation) rather than an
     expression-sniffing heuristic that works on two backends out of three. Note the
     `SHOW SEMANTIC METRICS` / `SHOW SEMANTIC DIMENSIONS` commands as a possible future
     replacement for `SHOW COLUMNS IN VIEW` — they are semantic-view-native and return
     `data_type`, but Semolina does not use them today.

4. **Should this phase also answer the todo's filter-value-typing question?**
   - Known: it is research question 4 in the originating todo and is not in the ROADMAP
     success criteria for Phase 47.
   - Recommendation: answer it in the decision doc if cheap (the answer is almost certainly
     "lenient widening, per the project's exact-return/lenient-arg typing rule"), but do not
     let it gate the phase.

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `duckdb` + `semantic_views` community extension | DuckDB live probe | ✓ | 1.5.5 (extension installed from community during this session's probe) | none needed |
| `adbc_driver_duckdb` | DuckDB ADBC path | ✓ | present in `.venv` | none needed |
| `adbc_driver_snowflake` | Snowflake replay path | ✓ | 1.10.0 | none needed |
| Databricks ADBC shared library | Databricks live probe | ✗ (Foundry-distributed, not on PyPI) | — | cassette replay only |
| Live Snowflake credentials | re-recording introspection cassette | ✗ (not in this session) | — | derivation path, option (b) |
| Live Databricks credentials | verifying the zero-row fallback | ✗ | — | mark evidence-limited |
| `pytest-adbc-replay` | cassette replay | ✓ | 1.1.1 | none needed |
| `pyarrow` | schema reading | ✓ | 24.0.0 | none needed |
| `gh` CLI | driver-source verification (research only) | ✓ | authenticated | — |

**Missing with no fallback:** none that block the phase.
**Missing with fallback:** live Snowflake creds (→ derivation, labelled); live Databricks
creds (→ evidence-limited row for the fallback claim only — the metadata-vs-result comparison
is fully covered by existing cassettes).

## Security Domain

`security_enforcement` is not set in `.planning/config.json` (absent = enabled), so this
section is included. The phase's attack surface is small but not zero.

### Applicable ASVS categories

| ASVS category | Applies | Standard control |
|---------------|---------|------------------|
| V2 Authentication | no | No auth code touched; the probe uses placeholder replay credentials |
| V3 Session management | no | No sessions |
| V4 Access control | no | No access-control surface |
| V5 Input validation | yes | The probe interpolates field and view names into SQL. Reuse `duckdb.py`'s existing `_sql_str_literal` (`engines/duckdb.py:42`), which doubles embedded single quotes, rather than writing a new interpolation |
| V6 Cryptography | no | None |
| V7 Error handling & logging | yes | The artifact must not embed credentials or row data. `pytest-adbc-replay`'s `CassetteMissError` deliberately "carries only raw/normalised SQL and the cassette path — never recorded row data or param values" (`_cursor.py:222-227`); the probe's own error paths should hold the same line |

### Known threat patterns

| Pattern | STRIDE | Standard mitigation |
|---------|--------|---------------------|
| SQL injection via catalog-sourced identifiers in `semantic_view('...')` | Tampering | `_sql_str_literal` quote doubling (already in-repo) |
| Credential leakage into a committed artifact | Information disclosure | Probe runs against replay placeholders (`account="replay"`, `password=SecretStr("replay")`) and in-memory DuckDB; `adbc_scrub_keys = ["password", "token", "access_token"]` already scrubs recordings. If option (a) re-recording happens, verify the new cassette's `000_params.json` before committing |
| Data leakage — real warehouse row values landing in a public artifact | Information disclosure | The comparison table records *types*, never values. Explicitly forbid a "sample value" column of real data; the synthetic fixture values (1000/2000/500) are safe, but the rule should be stated so it survives a future re-record against a real dataset |

## Sources

### Primary (HIGH confidence — read or executed this session)

- `src/semolina/engines/{snowflake,databricks,duckdb}.py` — introspection statements and parse loops
- `src/semolina/codegen/type_map.py` — all three type maps, quoted verbatim
- `src/semolina/codegen/introspector.py:39-43` — `IntrospectedField` shape
- `src/semolina/cursor.py:281` — `batch.to_pylist()`
- `src/semolina/codegen/python_renderer.py:103-122` — `TODO:` → `Any` handling
- `tests/conftest.py:95-131`, `tests/integration/conftest.py:184-202,293-317`,
  `semolina-jaffle-shop/tests/conftest.py:32-135` — all three fixture DDLs
- `tests/integration/cassettes/**/000_result.arrow` — 18 recorded Arrow schemas, read with pyarrow
- `.venv/.../pytest_adbc_replay/_cursor.py:186-188, 222-239, 364-397` — cassette keying and `adbc_execute_schema`
- `.venv/.../adbc_driver_manager/dbapi.py:1127-1143` — `adbc_execute_schema`
- `github.com/adbc-drivers/snowflake` `go/statement.go` (tags `go/v1.10.0` and `main`), `go/driver.go:74-80`, `go/record_reader.go:316-400,642-690`
- `github.com/adbc-drivers/databricks` `go/statement.go` (no `ExecuteSchema`; embeds `driverbase.StatementImplBase`)
- `github.com/adbc-drivers/driverbase-go` `driverbase/statement.go:127-129`
- Live DuckDB 1.5.5 + `semantic_views` runs: introspection, `adbc_execute_schema`, zero-row
  fallback, real execution, aggregate widening matrix, NULL-group behaviour
- Live cassette-replay run proving `adbc_execute_schema` served from a copied Snowflake cassette

### Secondary (MEDIUM confidence — official vendor docs)

- docs.databricks.com/aws/en/sql/language-manual/functions/sum — `DECIMAL(p + min(10, 31-p), s)`
- docs.databricks.com/aws/en/sql/language-manual/functions/avg — `DECIMAL(p+4, s+4)`, else `DOUBLE`
- docs.snowflake.com/en/sql-reference/functions/sum — "equivalent or larger data type" only
- docs.snowflake.com/en/sql-reference/sql/show-semantic-metrics — output columns incl. `data_type`
- docs.snowflake.com/en/sql-reference/sql/show-semantic-dimensions — output columns incl. `data_type`
- pypi.org JSON API — `adbc-driver-snowflake` 1.11.0, `arrowmodel` 1.0.0 provenance

### Tertiary (LOW confidence — noted, not relied upon)

- adbc-drivers.org — confirms no published feature matrix exists (a negative result)
- WebSearch summary of the Databricks driver announcement (0.1.2, early-stage) — corroborates
  the 0.1.x maturity read from tags, but the tags are the evidence

## Metadata

**Confidence breakdown:**

- Introspection behaviour: **HIGH** — every module read this session, values quoted verbatim
- `adbc_execute_schema` per driver: **HIGH** for Snowflake and Databricks (driver source at
  the pinned versions) and DuckDB (executed); the *fallback's* viability on Databricks is
  **LOW** (A5, unrun)
- The four disagreements: **HIGH** on DuckDB (measured), **HIGH** on Databricks SUM/AVG
  (vendor-documented + cassette), **MEDIUM** on Snowflake (cassette evidence for SUM;
  AVG undocumented and unmeasured)
- Offline probe mechanics: **HIGH** — the Snowflake cassette replay was executed end to end,
  including the two failure modes that had to be worked through
- Decimal policy inputs: **HIGH** on the driver/Arrow/Python side, **MEDIUM** downstream
  (pandas/polars/arrowmodel are assumptions A1–A3, A7)
- Artifact placement: **MEDIUM** — a judgement call, not a measurement; the CLAUDE.md
  obligations it triggers are HIGH

**Research date:** 2026-08-12
**Valid until:** 2026-09-11 (30 days). Shorten to 7 days for the Databricks driver row —
`adbc-drivers/databricks` is at 0.1.3 and moving; `ExecuteSchema` could land at any release.
