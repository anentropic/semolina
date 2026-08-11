# Phase 47: Type Fidelity Probe & Decision Doc - Pattern Map

**Mapped:** 2026-08-12
**Files analyzed:** 9 new/modified
**Analogs found:** 8 / 9

Upstream input was `47-RESEARCH.md` only (no CONTEXT.md). The file list below comes from
RESEARCH.md §"Wave 0 gaps" and §"Artifact placement".

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tests/type_fidelity/probe.py` | utility (test-tier) | transform (introspect + schema probe → rows) | `src/semolina/engines/snowflake.py` `introspect()` (lines 140-214) | role-match |
| `tests/type_fidelity/conftest.py` (if needed) | test fixture | request-response | `tests/conftest.py` `duckdb_pool` (136-163) + `semolina-jaffle-shop/tests/conftest.py` `_make_pool` (200-223) | exact |
| `tests/type_fidelity/test_probe.py` | test (coverage + staleness) | batch | `tests/unit/codegen/test_codegen_e2e.py` (syrupy snapshot guard) | role-match |
| `tests/type_fidelity/test_disagreements.py` | test (live DuckDB, **unmarked**) | request-response | `semolina-jaffle-shop/tests/test_duckdb_queries.py` (22-70) | exact |
| `tests/type_fidelity/test_snowflake_replay.py` | test (cassette replay) | request-response | `tests/integration/test_introspect.py` (whole file, 51 lines) | exact |
| `tests/integration/cassettes/integration/test_type_fidelity/...` | fixture data (copied cassette) | file-I/O | `tests/integration/cassettes/integration/test_queries/test_metric_with_dimension_snowflake_engine_/adbc_driver_snowflake.dbapi` | exact |
| `.planning/phases/47-.../47-TYPE-FIDELITY.md` (generated table) | generated artifact | batch | `tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr` (only committed-generated precedent; see caveat) | partial |
| `justfile` (+ `type-fidelity` recipe) | config | batch | `justfile` `test:` / `docs-build:` recipes | exact |
| `docs/src/explanation/type-fidelity.rst` + `index.rst` toctree | docs | — | `docs/src/explanation/semantic-views.rst` + `docs/src/explanation/index.rst` | exact |

---

## Pattern Assignments

### `tests/type_fidelity/test_snowflake_replay.py` (cassette-replay test)

**Analog:** `tests/integration/test_introspect.py` — the smallest complete cassette test in the repo.

**Marker idiom** (`tests/integration/test_introspect.py:18-25`, verbatim):

```python
from __future__ import annotations

from typing import Any

import pytest

# Records/replays an ADBC cassette; the plugin intercepts the pool's connection.
pytestmark = pytest.mark.adbc_cassette
```

`tests/integration/test_queries.py:43-46` states the naming rule the probe depends on:

```python
# Every test in this module records/replays an ADBC cassette. The cassette name
# is auto-derived from the node id (including the [snowflake_engine] /
# [databricks_engine] parameter), so each test+backend gets its own recording.
pytestmark = pytest.mark.adbc_cassette
```

**Test body shape** (`test_introspect.py:28-36`):

```python
def test_databricks_introspect_metric_view(databricks_engine: Any) -> None:
    """DESCRIBE TABLE EXTENDED AS JSON over ADBC -> IntrospectedView."""
    view = databricks_engine.introspect("sales_view")

    assert view.view_name == "sales_view"
    by_name = {field.name: field for field in view.fields}
```

**Fixture to reuse:** `snowflake_engine` / `databricks_engine` from
`tests/integration/conftest.py:129` and `:245`. Replay arm builds a placeholder pool
(`conftest.py:226-242`, verbatim) — the placeholder *values are load-bearing* because the
cassette SQL was generated under them:

```python
        # Replay: placeholder config — connections are intercepted by the plugin.
        config = SnowflakeConfig(
            account="replay",
            user="replay",
            password=SecretStr("replay"),
            warehouse="replay",
            database="replay",
            role="replay",
            schema="REPLAY",  # type: ignore[call-arg]  # populated via field alias
        )
        engine = create_engine(config)
        semolina.register("test", engine)
```

If the probe test needs its own fixture, `tests/integration/conftest.py:380-421`
(`snowflake_async_engine`) is the copy-cassette precedent — replay-only, no recording arm.
Its docstring is the exact justification text to mirror.

**Cassette-copy precedent** (documented at `tests/integration/conftest.py:20-24`, verbatim):

> The async fixtures (``snowflake_async_engine``, ``databricks_async_engine``) are
> **replay-only** — they have no recording branch at all. Their cassettes were
> copied from the sync tests' recordings rather than recorded again, because the
> async path reuses the sync SQL builder unchanged, so the SQL the driver receives
> is byte-identical.

**Cassette directory layout** (verified on disk):

```
tests/integration/cassettes/integration/test_queries/
  test_metric_with_dimension_snowflake_engine_/
    adbc_driver_snowflake.dbapi/
      000_params.json
      000_query.sql
      000_result.arrow
```

Copy target follows the new test's node id, e.g.
`cassettes/integration/test_type_fidelity/test_snowflake_probe/adbc_driver_snowflake.dbapi/`.
Note the leading `integration/` segment inside `cassettes/` — the cassette root is
`adbc_cassette_dir = "tests/integration/cassettes"` (pyproject) and the node-id path is
appended under it. If the probe lives at `tests/type_fidelity/...` its cassette path becomes
`cassettes/type_fidelity/<module>/<test>/`, **not** `cassettes/integration/...`. Decide the
probe test's location before copying, or the copy lands in the wrong directory.

**SQL must be built, not pasted** — reuse `SQLBuilder` (`src/semolina/engines/sql.py:559`,
docstring example at `:572-595`):

```python
from semolina.engines.sql import SQLBuilder, SnowflakeDialect

query = Sales.query().metrics(Sales.revenue).dimensions(Sales.country)
builder = SQLBuilder(SnowflakeDialect())
sql = builder.build_select(query)
# SELECT AGG("REVENUE"), "COUNTRY" FROM "sales_view" GROUP BY ALL
```

Model declaration to copy (`tests/integration/test_queries.py:49-60`):

```python
class Sales(SemanticView, view="sales_view"):
    """Synthetic SemanticView for integration query tests."""

    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()
```

---

### `tests/type_fidelity/test_disagreements.py` (live DuckDB, **no cassette marker**)

**Analog:** `semolina-jaffle-shop/tests/test_duckdb_queries.py` — the contrast case. Note what
it does **not** contain: no `pytestmark = pytest.mark.adbc_cassette`, no `_is_recording`, no
placeholder config. Its whole import block (`lines 12-15`, verbatim):

```python
from decimal import Decimal

import pytest
from semolina_jaffle_shop.jaffle_models import Customers, Orders, Products
```

and a whole test (`lines 22-31`, verbatim) — note it already asserts a `Decimal`, which is the
phase's headline:

```python
    def test_single_metric(self, orders_pool) -> None:
        """A metrics-only query returns one aggregated row with the SUM."""
        with Orders.query().metrics(Orders.order_total).execute() as cursor:
            result = cursor.fetchall_rows()

        # semantic_view() aggregates: one row, column named after the metric.
        assert len(result) == 1, "Metrics-only query returns a single aggregated row"
        assert "order_total" in result[0], "Selected column is the metric 'order_total'"
        # SUM of all 12 fixture order_total values.
        assert result[0]["order_total"] == Decimal("656.54")
```

**Contrast rule (RESEARCH.md Pitfall 4):** an unmarked test runs live in-process even though
DuckDB routes through `adbc_driver_manager.dbapi`, which *is* in `adbc_auto_patch`. Adding the
marker would divert it into replay **and** normalise its SQL as the `databricks` dialect
(`pyproject.toml` `adbc_dialect`). Do not add the marker to any DuckDB probe.

**Decimal fixture source** (`semolina-jaffle-shop/tests/conftest.py:32-45`, the only decimal
DDL in the repo):

```python
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER,
            order_total DECIMAL(10, 2),
            order_count INTEGER,
            tax_paid DECIMAL(10, 2),
            order_cost DECIMAL(10, 2),
            ...
```

with metrics (`:75-81`): `o.order_total AS SUM(o.order_total)`, etc.

**Cross-project warning:** `semolina-jaffle-shop` is a separate uv project with its own pytest
run (`justfile`: `pushd semolina-jaffle-shop; uv run pytest; popd`). A probe in the root
`tests/` cannot use `orders_pool`. To get decimals in the root suite, copy the DDL pattern into
a root-suite fixture rather than importing across projects.

---

### `tests/type_fidelity/conftest.py` (DuckDB fixture)

**Analog A:** `tests/conftest.py:91-163`. Connect-listener idiom (this is the answer to
Pitfall 5 — data must be created in the listener):

```python
def _setup_sales_data(dbapi_conn: Any, _connection_record: Any) -> None:
    """
    Create sales_data table and sales_view semantic view on each new connection.

    ADBC poolhouse creates independent DuckDB instances per physical
    connection (``source.adbc_clone``), so tables and semantic views must
    be set up on every new physical connection via a ``connect`` event.
    """
    cur = dbapi_conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales_data (...)
    """)
    ...
    cur.close()
    dbapi_conn.commit()


@pytest.fixture
def duckdb_pool() -> Generator[Any, None, None]:
    pytest.importorskip("adbc_driver_duckdb")
    from adbc_poolhouse import DuckDBConfig, close_pool
    from sqlalchemy import event

    import semolina
    from semolina.config import create_engine

    engine = create_engine(DuckDBConfig(database=":memory:", pool_size=1))
    event.listen(engine._pool, "connect", _setup_sales_data)

    semolina.register("default", engine)
    yield engine._pool
    semolina.unregister("default")
    close_pool(engine._pool)
```

`pool_size=1` is already the in-memory default here and is exactly the Pitfall-5 mitigation.

**Analog B (multi-view composition):** `semolina-jaffle-shop/tests/conftest.py:200-223`
`_make_pool(*setups)` — attach several `connect` listeners to one engine. Use this shape if the
probe needs both a `sales_view` and a decimal `orders` view on one pool.

**Analog C (file-backed, session-scoped):** `tests/conftest.py:193-231`
`duckdb_file_backed_db` — the alternative Pitfall-5 mitigation, and the fixture
`test_codegen_e2e.py` already consumes for real end-to-end introspection.

---

### `tests/type_fidelity/probe.py` (probe driver)

**Analog:** `SnowflakeEngine.introspect` (`src/semolina/engines/snowflake.py:140-214`) — the
closest existing "open a connection, run a metadata statement, build typed rows" routine.

**Connection + metadata-statement pattern** (`snowflake.py:162-179`, verbatim):

```python
        try:
            with self.connect() as conn:
                cur = conn.cursor()
                cur.execute(f"SHOW COLUMNS IN VIEW {qualified_name}")

                # Build column name list from cursor description (lowercase for safe access)
                columns = [desc[0].lower() for desc in cur.description]

                fields: list[IntrospectedField] = []
                for row in cur.fetchall():
                    d: dict[str, Any] = dict(zip(columns, row, strict=True))
                    field_type = cast(
                        "Literal['metric', 'dimension', 'fact']", str(d["kind"]).lower()
                    )
                    type_json: dict[str, object] = json.loads(d["data_type"])
                    py_type = snowflake_json_type_to_python(type_json)
                    data_type = f"TODO: {d['data_type']}" if py_type is None else py_type
```

Two things to copy and one to **not** copy:

- Copy: the `dict(zip(columns, row, strict=True))` row-shaping and the lazy in-function imports.
- Copy: the raw `d["data_type"]` capture — this is the only place the raw warehouse type exists
  before mapping. The probe must record it *before* calling the mapper (RESEARCH.md Pitfall 1).
- **Do not** copy the `f"TODO: {...}"` collapse into the probe's raw column; the probe stores raw
  and mapped as two separate fields.

**Type-map call surface** (`src/semolina/codegen/type_map.py`, signatures read this session):

```python
def snowflake_json_type_to_python(type_json: dict[str, object]) -> str | None: ...   # :47
def databricks_type_to_python(type_obj: dict[str, object]) -> str | None: ...        # :97
def duckdb_type_to_python(type_name: str) -> str | None: ...                         # :163
```

These belong to the *introspection* column only. RESEARCH.md defence #3: the probe column must
never import `semolina.codegen.type_map`.

**Arrow → Python boundary** (`src/semolina/cursor.py:279-283`, verbatim — the Decimal policy
turns on this line):

```python
            if batch.num_rows == 0:
                continue
            self._batch_rows = batch.to_pylist()
            self._batch_pos = 0
        row = Row(self._batch_rows[self._batch_pos])
```

Schema-without-rows passthrough already exists at `cursor.py:165-197`
(`fetch_record_batch() -> pyarrow.RecordBatchReader`) — that is the zero-row fallback's read
point; no new accessor is needed.

**SQL-literal safety** (RESEARCH.md V5): reuse `_sql_str_literal` at
`src/semolina/engines/duckdb.py:42` rather than writing new interpolation.

**Doctest constraint:** `pyproject.toml` `[tool.pytest.ini_options]` sets
`addopts = ["-v", "--doctest-modules", "--doctest-continue-on-failure"]` and
`testpaths = ["tests", "src"]`. Docstring examples in `probe.py` **will execute**. Use the
CLAUDE.md `.. code-block:: python` form (non-doctest) rather than `>>>` prompts.

**Package layout:** `tests/unit/`, `tests/integration/` have no `__init__.py`; the root
`tests/conftest.py` does `from models import Sales`, i.e. rootdir-relative imports work.
RESEARCH.md's Wave-0 list includes `tests/type_fidelity/__init__.py` — the repo precedent is
*no* `__init__.py`. Match the repo, not the research list, unless an import collision appears.

---

### `tests/type_fidelity/test_probe.py` (staleness / drift guard)

**Analog:** `tests/unit/codegen/test_codegen_e2e.py` — the repo's one committed-generated-output
guard, via syrupy. Its shape (`lines 12-53`):

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typer.testing import CliRunner

from semolina.cli import app

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion

runner = CliRunner()


def test_codegen_file_backed_duckdb(
    duckdb_file_backed_db: Path,
    snapshot: SnapshotAssertion,
) -> None:
    result = runner.invoke(app, ["codegen", "sales_view", "--backend", "duckdb", ...])
    assert result.exit_code == 0, result.output
    assert result.output == snapshot
```

Committed artifact: `tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr`;
regeneration recipe: `uv run pytest --snapshot-update` (syrupy's standard flag — the repo has no
`just` wrapper for it).

**Caveat, stated plainly:** this is the *only* committed-generated-file precedent in the repo,
and it is a syrupy `.ambr` under `__snapshots__/`, not a markdown artifact under `.planning/`
with a `just` recipe. There is **no existing precedent** for the exact artifact RESEARCH.md
proposes. Two viable routes, and the planner should pick one explicitly:

- **(i)** Follow the syrupy precedent (snapshot the table, `--snapshot-update` regenerates).
  Zero new machinery; but the artifact lands under `tests/`, not `.planning/`.
- **(ii)** Build the `just type-fidelity` recipe + a plain-file comparison test, as RESEARCH.md
  recommends. New machinery, but puts the table where Phase 48 reads it.

RESEARCH.md's reviewer workflow ("run `just type-fidelity` and confirm `git diff` is empty")
presupposes (ii).

---

### `justfile` — `type-fidelity` recipe

**Analog:** existing recipes, verbatim:

```make
# Run all tests (unit + jaffle-shop mock)
test:
    uv run pytest
    pushd semolina-jaffle-shop; uv run pytest; popd

# Build the docs site (strict mode)
docs-build:
    uv run sphinx-build -W docs/src docs/_build
```

Pattern: a `#` comment line above every recipe (it feeds `just --list`, which is the default
recipe), and `uv run <tool>` as the command. Match it exactly.

---

### `docs/src/explanation/type-fidelity.rst` (+ toctree)

**Analog page:** `docs/src/explanation/semantic-views.rst`. Opening pattern (lines 1-11,
verbatim) — note the explicit label anchor, the `===` title underline, and the per-warehouse
`**bold**` lead-ins with inline external links:

```rst
.. _explanation-semantic-views:

What is a semantic view?
========================

A semantic view is a database object that sits on top of your raw tables and
defines business metrics and dimensions in one governed place. ...

How warehouses implement them
-----------------------------

**Snowflake** calls them *semantic views*. You create one with
`CREATE SEMANTIC VIEW <https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view>`_,
```

**Toctree — the `-W` build breaker.** `docs/src/explanation/index.rst` in full (10 lines):

```rst
.. _explanation:

Explanation
===========

Background concepts and design decisions.

.. toctree::
   :maxdepth: 1

   semantic-views
```

Add `type-fidelity` under `semantic-views`. A page not in a toctree emits a warning, and
`just docs-build` runs `sphinx-build -W`, so the build fails.

**CLAUDE.md obligation:** new docs page ⇒ that plan's `<execution_context>` MUST include
`@.claude/skills/semolina-docs-author/SKILL.md`.

---

## Shared Patterns

### Lazy in-function imports of optional backends
**Source:** `tests/conftest.py:149-154`, `tests/integration/conftest.py:147-150`,
`semolina/engines/snowflake.py:141-149`
**Apply to:** every new fixture and the probe driver

```python
    pytest.importorskip("adbc_driver_duckdb")
    from adbc_poolhouse import DuckDBConfig, close_pool
    from sqlalchemy import event

    import semolina
    from semolina.config import create_engine
```

Backend imports are always function-local, never module-level, so a suite without an optional
driver installed still collects.

### Register / unregister symmetry
**Source:** `tests/conftest.py:159-162`, `tests/integration/conftest.py:236-242`,
`semolina-jaffle-shop/tests/conftest.py:219-222`
**Apply to:** every pool fixture

```python
    semolina.register("default", engine)
    yield engine._pool
    semolina.unregister("default")
    close_pool(engine._pool)   # or engine.dispose()
```

The root suite additionally has an autouse `clean_registry` fixture
(`tests/conftest.py:45-51`) resetting the registry after each test.

### Module docstring carries the record/replay contract
**Source:** `tests/integration/test_queries.py:1-32`, `tests/integration/test_introspect.py:1-16`
**Apply to:** every new test module in this phase

Each warehouse test module opens with a docstring stating: what replays vs runs live, the
re-record command (`pytest --adbc-record=once tests/integration/...`), and a pointer to
`docs/src/how-to/warehouse-testing.rst`. The type-fidelity modules should carry the same
disclosure, plus the *evidence-provenance* label RESEARCH.md requires.

### Backend-normalising helper before assertion
**Source:** `tests/integration/test_queries.py:63-82` (`_norm` / `_rows`)
**Apply to:** carefully — this is an **anti-pattern for this phase**. `_norm` deliberately
collapses `Decimal` to `int`/`float` so backends compare equal. The probe must record exactly
the distinction `_norm` erases. Do not import or imitate it.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.planning/phases/47-.../47-TYPE-FIDELITY.md` (generated, committed, `just`-regenerated markdown) | generated artifact | batch | The repo has exactly one committed generated file — a syrupy `.ambr` snapshot under `tests/unit/codegen/__snapshots__/` regenerated by `pytest --snapshot-update`. There is **no** precedent for a `just`-driven generated markdown artifact, and none for generated content under `.planning/`. Planner must choose route (i) or (ii) above rather than copy an existing pattern. |

---

## Metadata

**Analog search scope:** `tests/`, `tests/integration/`, `tests/unit/`,
`semolina-jaffle-shop/tests/`, `src/semolina/engines/`, `src/semolina/codegen/`,
`src/semolina/cursor.py`, `docs/src/explanation/`, `justfile`, `pyproject.toml`
**Files scanned:** 14 read, plus directory listings of cassettes / tests / docs
**Pattern extraction date:** 2026-08-12
