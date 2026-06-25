---
phase: 44-engine-owns-the-pool
plan: 06
subsystem: docs
tags: [docs, create_engine, register, engine, connection-pools, migration, diataxis]

# Dependency graph
requires:
  - phase: 44-engine-owns-the-pool
    provides: "Plan 03 final public surface: create_engine + register(name, engine) + get_engine; pool_from_config/get_pool/*_connect_kwargs deleted; Plan 04 Databricks Path B (introspect NotImplementedError)"
provides:
  - "All 12 docs pages document the create_engine + register(name, engine) connection API"
  - "connection-pools.rst is the canonical two-pattern guide (direct Engine + named registry)"
  - "databricks.rst notes codegen/introspection is pending the Foundry ADBC driver (querying works)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Connection examples build one Engine via create_engine(config | name); pool sizing lives on the config object / TOML fields (create_pool(...) kwargs are gone from the public path)"
    - "Two documented usage patterns: direct engine.execute(query) / engine.connect(), and named registry register(name, engine) + Query.using(name)"
    - "Engine pool reached as engine._pool for close_pool() in lifecycle/teardown examples"
    - "blacken-docs (prek hook) reformats every .. code-block:: python block; expect a re-stage + re-commit cycle per task"

key-files:
  created: []
  modified:
    - docs/src/how-to/connection-pools.rst
    - docs/src/reference/config.rst
    - docs/src/tutorials/first-query.rst
    - docs/src/how-to/queries.rst
    - docs/src/index.rst
    - docs/src/how-to/warehouse-testing.rst
    - docs/src/how-to/codegen-credentials.rst
    - docs/src/how-to/backends/overview.rst
    - docs/src/how-to/backends/snowflake.rst
    - docs/src/how-to/backends/databricks.rst
    - docs/src/how-to/backends/duckdb.rst
    - docs/src/how-to/web-api.rst

key-decisions:
  - "Pool sizing documented on the config object / TOML fields, since create_engine calls create_pool(wh_config) with no pool kwargs — the config classes carry pool_size/max_overflow/timeout/recycle"
  - "Clean break per [[feedback_v03_engine_removal]]: zero deprecation notices, no 'previously you would' asides anywhere"
  - "connection-pools.rst retitled 'How to connect an engine to your warehouse' and rebuilt as the canonical two-pattern guide; other pages cross-link to it instead of duplicating setup"
  - "databricks.rst gained a note that codegen/introspection is pending the Foundry ADBC driver (Plan 04 Path B); querying/execution still works"

requirements-completed: []

# Metrics
duration: ~40min
completed: 2026-06-24
---

# Phase 44 Plan 06: Docs Migration to create_engine / register(engine) Summary

**Migrated every connection example across all 12 documentation pages from the deleted `pool_from_config` / `create_pool` / 3-arg `register(name, pool, dialect)` surface to the shipped `create_engine(config | name)` + `register(name, engine)` API, rebuilt `connection-pools.rst` as the canonical two-pattern guide, and noted the Databricks codegen caveat — `just docs-build` passes clean.**

## Performance

- **Duration:** ~40 min
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- **Canonical connection guide (Task 1):** `connection-pools.rst` is rewritten as the two-pattern guide. The **direct engine** pattern (`engine = create_engine(...)` then `engine.execute(query)` / `with engine.connect() as conn:`) and the **named registry** pattern (`register("default", create_engine("default"))` then `Query.using(...)`) are each shown end to end, with both the config-object and `.semolina.toml` connection-name arms of `create_engine`. Pool sizing moved onto the config object / TOML fields (the public path no longer takes `create_pool(...)` kwargs). `config.rst` prose now references `create_engine` instead of `pool_from_config`; the page's TOML-format reference (hand-written, not autoapi) was the only part touched.
- **Tutorial + general how-tos (Task 2):** `first-query.rst` (runnable tutorial) registers an engine via `create_engine` + `register("default", engine)` and keeps its DuckDB complete-example runnable with the same expected output (`US 1500` / `CA 2000`). `index.rst` quick example, `queries.rst` (`.using()` + execute prose), `warehouse-testing.rst` (the in-memory fixture now builds a DuckDB engine and seeds via `engine._pool`'s connect event), and `codegen-credentials.rst` all moved to the new API; how-to pages cross-link to the canonical guide rather than duplicating setup.
- **Backend + web-api (Task 3):** the four backend pages (`overview`, `snowflake`, `databricks`, `duckdb`) show `create_engine(<Config>(...))` and the `.semolina.toml` name arm; `web-api.rst` wires the FastAPI lifespan to `register("default", create_engine(SnowflakeConfig(...)))` and uses per-endpoint `.using(...)`. `databricks.rst` gained a note that querying works but codegen/introspection is pending the Foundry-distributed Databricks ADBC driver (Plan 04 Path B → `NotImplementedError`).
- **Gates green:** full `grep -rE 'pool_from_config|get_pool|register(...dialect=)|create_pool' docs/src` is empty; no deprecation/"previously" language anywhere; `just docs-build` exits 0 with `-W` (zero Sphinx warnings, no broken cross-references); `prek run --all-files` passes (blacken-docs reformatted the Python blocks, basedpyright strict clean).

## Task Commits

Each task was committed atomically (each required a re-stage + re-commit because the `blacken-docs` prek hook reformats the `.. code-block:: python` blocks on first run):

1. **Task 1: rewrite connection guide + config reference** — `994c1ef` (docs)
2. **Task 2: migrate tutorial, queries, index, testing, codegen** — `a020508` (docs)
3. **Task 3: migrate backend + web-api pages; docs build green** — `6a6590e` (docs)

## Files Created/Modified

- `docs/src/how-to/connection-pools.rst` — canonical two-pattern engine guide (direct + named registry), both `create_engine` arms, pool sizing on the config/TOML, lifecycle via `engine._pool` + `close_pool`, multi-engine `.using()`.
- `docs/src/reference/config.rst` — prose references `create_engine` (file location, connection selection, See-also); autoapi directives untouched (none on this hand-written page).
- `docs/src/tutorials/first-query.rst` — "Register an engine" step + runnable DuckDB complete example via `create_engine` + `register("default", engine)`.
- `docs/src/how-to/queries.rst` — "Choose the engine" `.using()` section + execute prose talk engines; cross-link to the connection guide.
- `docs/src/index.rst` — quick example uses `register("default", create_engine("default"))`.
- `docs/src/how-to/warehouse-testing.rst` — in-memory `sales_engine` fixture builds a DuckDB engine, seeds via `engine._pool` connect event, closes via `close_pool(engine._pool)`; cassette section reworded to engines.
- `docs/src/how-to/codegen-credentials.rst` — intro + See-also reference `create_engine`.
- `docs/src/how-to/backends/overview.rst` — "Register an engine" with name-arm and per-backend config-object arm; "Query with a registered engine".
- `docs/src/how-to/backends/snowflake.rst` / `duckdb.rst` — `create_engine("default")` + manual `create_engine(<Config>(...))` + `register(engine)`.
- `docs/src/how-to/backends/databricks.rst` — same migration + the codegen/introspection-pending note (Foundry ADBC driver / Path B).
- `docs/src/how-to/web-api.rst` — FastAPI lifespan builds the engine; per-endpoint `.using(...)`; engine-lifecycle wording.

## Decisions Made

- **Pool sizing documented on the config object / TOML, not `create_pool` kwargs.** `create_engine` calls `create_pool(wh_config)` with no pool keyword arguments, and the `adbc-poolhouse` config classes carry `pool_size` / `max_overflow` / `timeout` / `recycle`. TOML sections instantiate the config class directly (`config_cls(**section)`), so the same fields flow through by name. Examples set these on the config / in the TOML section.
- **Clean break, no deprecation notices** ([[feedback_v03_engine_removal]]). The old symbols are gone from Plan 03, so the docs simply describe the current surface.
- **One canonical guide, cross-linked.** `connection-pools.rst` owns the full two-pattern explanation; tutorial/backends/web-api link to it rather than repeating connection setup, matching the semolina-docs-author how-to guidance (one guide, one goal; reader supplies setup).
- **Databricks caveat surfaced** because Plan 04 shipped Path B: `DatabricksEngine.introspect()` raises `NotImplementedError` pending the Foundry ADBC driver. Querying/execution is unaffected, so the note scopes the limitation to codegen/introspection only.

## Deviations from Plan

None — plan executed exactly as written. The three tasks, their files, and their acceptance greps all match the plan; the only repeated mechanical step was re-staging after `blacken-docs` reformatted the Python code blocks (a standard prek hook, not a deviation).

## semolina-docs-author skill application

Applied per CLAUDE.md on every touched page:

- **Diataxis classification honoured:** `first-query.rst` kept tutorial-shape (one runnable path, imports + expected output); the how-to pages kept illustrative snippets and defer full setup to the canonical guide; `config.rst` reference prose updated without hand-writing autoapi output.
- **Tab-sets with `:sync-group: warehouse`** preserved/used for dialect-specific connection examples (Snowflake/Databricks/DuckDB).
- **Voice:** second person, warm-but-efficient; "See also" sections refreshed at page bottoms.
- **Humanizer pass** on the rewritten `connection-pools.rst` prose: removed promotional language, kept copulas (`An engine is...`), trimmed em dashes, avoided rule-of-three and superficial -ing openers.

## Authentication Gates

None.

## Known Stubs

None. The Databricks codegen limitation is the real shipped behaviour (Plan 04 Path B `NotImplementedError`), documented as a scoped note — not a docs stub or placeholder.

## Threat Surface

Honoured the plan's `<threat_model>` T-44-10: every connection example sources secrets from `.semolina.toml` / `SNOWFLAKE_*` / `DATABRICKS_*` env or uses obvious placeholders (`password="..."`, `token="dapi..."`); no real literal token/password modelled. No new trust boundaries introduced (docs-only).

---
*Phase: 44-engine-owns-the-pool*
*Completed: 2026-06-24*

## Self-Check: PASSED

- SUMMARY file present: `.planning/phases/44-engine-owns-the-pool/44-06-SUMMARY.md`
- Task commits present: `994c1ef`, `a020508`, `6a6590e`
- Modified docs pages present on disk (connection-pools.rst, backends/databricks.rst, all 12)
- Gate verified: full `docs/src` old-API sweep empty; `just docs-build` exit 0 (`-W`, no warnings); `prek run --all-files` passes
