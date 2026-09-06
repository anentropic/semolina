---
phase: 44-engine-owns-the-pool
plan: 03
subsystem: engine-core
tags: [adbc, poolhouse, introspection, snowflake, duckdb, create_engine, codegen, public-api]

# Dependency graph
requires:
  - phase: 44-engine-owns-the-pool
    provides: "Plan 02 Engine base (connect()/execute()/_pool), create_engine factory, name→Engine registry; Plan 01 RED engine/CLI tests"
provides:
  - "Snowflake introspect() runs SHOW COLUMNS IN VIEW over the engine's ADBC pool (no native snowflake.connector); db-qualification reads self._config.database"
  - "DuckDB introspect() runs the two-pass DESCRIBE over the engine's ADBC pool; semantic_views loaded by the pool connect-event (no per-call INSTALL/LOAD)"
  - "Engine base now holds the source poolhouse config (self._config) so introspectors read connection metadata without re-reading TOML"
  - "codegen CLI _resolve_backend builds every backend via create_engine; native *_connect_kwargs deleted"
  - "Public surface final: create_engine + register + get_engine exported; pool_from_config/get_pool absent"
affects: [44-04, 44-05, 44-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Introspection over the owned pool: `with self.connect() as conn: cur = conn.cursor()` replaces the native-driver connect; SQL + parsers byte-for-byte unchanged (spike-proven identical over ADBC)"
    - "ADBC error translation: catch adbc_driver_manager.{ProgrammingError,OperationalError,Error} (PEP-249) and re-raise SemolinaViewNotFoundError/SemolinaConnectionError with view-name context only"
    - "Engine holds its source config (self._config) for backend introspection metadata (Snowflake database for view-name qualification)"
    - "cast(Literal[...]) instead of `# type: ignore[arg-type]` for runtime-string → IntrospectedField.field_type Literal (CLAUDE.md no-type-ignore gate)"
    - "Record-mode-only native-connector kwargs glue lives in tests/integration/conftest.py next to its only consumer, not in the library"

key-files:
  created: []
  modified:
    - src/semolina/engines/snowflake.py
    - src/semolina/engines/duckdb.py
    - src/semolina/engines/base.py
    - src/semolina/config.py
    - src/semolina/cli/codegen.py
    - tests/unit/test_snowflake_engine.py
    - tests/unit/test_duckdb_engine.py
    - tests/unit/codegen/test_cli.py
    - tests/unit/codegen/test_codegen_e2e.py
    - tests/integration/conftest.py

key-decisions:
  - "Engine base __init__ gained an optional config=None param; create_engine threads wh_config through so SnowflakeEngine.introspect reads self._config.database (the native _connection_params seam is gone)"
  - "Snowflake ADBC error mapping: ProgrammingError → SemolinaViewNotFoundError, OperationalError → SemolinaConnectionError (was native ProgrammingError/DatabaseError)"
  - "DuckDB ADBC error mapping: a single adbc_driver_manager.Error is classed view-not-found by message (does not exist / not found / catalog error / did you mean), else connection error"
  - "CLI DuckDB branch builds DuckDBConfig(database=..., read_only=True) → create_engine, matching snowflake/databricks; the two CLI tests that pinned DuckDBEngine(database=...) were migrated to the create_engine contract"
  - "Native *_connect_kwargs deleted from config.py; their record-mode DDL use moved to local helpers in the integration conftest (RESEARCH Open Q1 was slightly off — the helpers, not just the connectors, were still imported there)"

patterns-established:
  - "Per-backend introspect = swap the connection (self.connect()) and the caught error class; keep the SQL + parser identical so recorded cassettes stay green"
  - "Test migration on GREEN: RED-first pyright pragmas replaced with narrow test-only scope-disables (reportUnknownMemberType / reportPrivateUsage), never `# type: ignore`"

requirements-completed: []

# Metrics
duration: 32min
completed: 2026-06-24
---

# Phase 44 Plan 03: Snowflake + DuckDB Introspection on the ADBC Pool Summary

**Migrated Snowflake and DuckDB introspection off the native drivers onto the Engine's owned ADBC pool (SHOW COLUMNS / two-pass DESCRIBE unchanged, only the connection + caught error class swapped), rewired the codegen CLI onto `create_engine`, deleted the dead native `*_connect_kwargs`, and finalized the public surface.**

## Performance

- **Duration:** ~32 min
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- **Snowflake introspect over ADBC (Task 1):** `SnowflakeEngine.introspect()` now does `with self.connect() as conn: cur = conn.cursor()` instead of `snowflake.connector.connect(**self._connection_params)`. The `SHOW COLUMNS IN VIEW` SQL and the 13-column parser are byte-for-byte unchanged; the `< 3 parts → prepend database` qualification now reads `self._config.database` (the Engine holds the poolhouse config). Errors are caught as `adbc_driver_manager.ProgrammingError` (→ `SemolinaViewNotFoundError`) / `OperationalError` (→ `SemolinaConnectionError`). All `snowflake.connector` references are gone.
- **DuckDB introspect over the pool (Task 1):** `DuckDBEngine.introspect()` checks out `self.connect()`; the per-call `duckdb.connect(read_only=True)` + `INSTALL/LOAD semantic_views` are removed (the extension loads via the pool connect-event wired in `create_engine`). Both DESCRIBE passes and parsers are unchanged; `adbc_driver_manager.Error` is mapped to view-not-found vs connection error by message.
- **Engine holds its config (Task 1):** `Engine.__init__(*, pool, dialect, config=None)`; `create_engine` passes `wh_config`, giving introspectors connection metadata without re-reading TOML.
- **CLI on Engines (Task 2):** `cli/codegen.py::_resolve_backend` collapses the three native branches — snowflake/databricks resolve `warehouse_config(backend) → create_engine(config)`; duckdb builds `DuckDBConfig(database=..., read_only=True) → create_engine`. The `typer.BadParameter` ValidationError wrapping and the dotted-path custom-engine escape hatch are preserved. The `snowflake_connect_kwargs`/`databricks_connect_kwargs` imports (and the deferred pyright pragma) are gone.
- **Dead helpers deleted + public surface final (Task 3):** `snowflake_connect_kwargs`/`databricks_connect_kwargs` deleted from `config.py` with zero remaining importers; their record-mode DDL use moved into local `_snowflake_native_kwargs`/`_databricks_native_kwargs` helpers in the integration conftest. `import semolina` exposes `create_engine`/`get_engine` and not `pool_from_config`/`get_pool`.
- **Green where it counts:** `test_snowflake_engine` (16), `test_duckdb_engine` (5), `test_cli` (37), `test_registry`/`test_pool`/`test_config` (58), and the Snowflake/DuckDB `codegen-e2e` cases all pass; **Snowflake integration cassettes replay 7/7 green** (recorded SQL untouched — only plumbing moved). `prek run --all-files` (ruff + basedpyright strict, no new `# type: ignore`) and `just docs-build` pass.

## Task Commits

Each task was committed atomically:

1. **Task 1: Snowflake + DuckDB introspection onto the ADBC pool** - `d916f09` (feat)
2. **Task 2: codegen CLI onto create_engine; drop native kwargs imports** - `7f8c44c` (feat)
3. **Task 3: delete native *_connect_kwargs; finalize public surface** - `0a2591b` (refactor)

_query.py `execute()`/`using()` already resolved Engines via `get_engine` + `engine.execute()` (landed in Plan 02), so Task 2 required no query.py change._

## Files Created/Modified

- `src/semolina/engines/snowflake.py` — introspect() over `self.connect()`; ADBC error translation; db-qualification from `self._config`; native driver + stale class docstring removed; `cast(Literal[...])` over `# type: ignore`.
- `src/semolina/engines/duckdb.py` — introspect() over `self.connect()`; per-call INSTALL/LOAD removed; ADBC `Error` mapping; updated class docstring; `cast(Literal[...])`.
- `src/semolina/engines/base.py` — `Engine.__init__` gained optional `config` stored as `self._config`.
- `src/semolina/config.py` — `create_engine` passes `config=wh_config`; `snowflake_connect_kwargs`/`databricks_connect_kwargs` deleted.
- `src/semolina/cli/codegen.py` — `_resolve_backend` builds every backend via `create_engine`; native kwargs imports + deferred pragma removed.
- `tests/unit/test_snowflake_engine.py` — removed the RED pragma block; fixed the error test to build `adbc ProgrammingError(status_code=NOT_FOUND)`.
- `tests/unit/test_duckdb_engine.py` — removed the RED pragma block; DDL now declares `PRIVATE internal_cost`.
- `tests/unit/codegen/test_cli.py` — two DuckDB CLI tests migrated to the `create_engine(DuckDBConfig(...))` contract.
- `tests/unit/codegen/test_codegen_e2e.py` — Snowflake case migrated onto the ADBC-cursor seam; Databricks case left on the native constructor under a narrowed pragma (Plan 04).
- `tests/integration/conftest.py` — record-mode native-connector kwargs mapping moved into local helpers; replay path + Snowflake cassettes unchanged.

## Decisions Made

- **Engine holds its source config:** the cleanest way to give Snowflake introspection its database without resurrecting the `_connection_params` seam — `create_engine` already has `wh_config` in hand.
- **DuckDB error-by-message classification:** ADBC collapses DuckDB's `CatalogException`/`IOException` into one `adbc_driver_manager.Error`; the view-not-found vs connection split is reconstructed from the message (the only RED contract is "missing view → SemolinaViewNotFoundError").
- **CLI DuckDB via create_engine:** keeps all three backends on one construction path; the two tests pinning `DuckDBEngine(database=...)` were testing the pre-Phase-44 constructor and were migrated to assert the new contract (same pattern Plan 02 used for `test_query.py`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed two RED engine-test fixtures that could not exercise the contract**
- **Found during:** Task 1 verification
- **Issue:** The Plan-01 RED fixtures were authored slightly wrong: the DuckDB DDL created `internal_cost` as a default-PUBLIC metric (DuckDB has no implicit PRIVATE), so `test_introspect_private_fields_excluded` could never pass; the Snowflake error test built `adbc ProgrammingError("msg")` without the required `status_code` kwarg, raising `TypeError` at setup.
- **Fix:** DDL now uses `PRIVATE o.internal_cost AS SUM(o.cost)` (verified against the duckdb-semantic-views grammar: `METRICS ( PRIVATE <name> AS ... )`); the error test builds `ProgrammingError(msg, status_code=AdbcStatusCode.NOT_FOUND)`.
- **Files modified:** `tests/unit/test_duckdb_engine.py`, `tests/unit/test_snowflake_engine.py`
- **Verification:** both modules 21/21 green.
- **Committed in:** `d916f09` (Task 1 commit)

**2. [Rule 3 - Blocking] Migrated Snowflake codegen-e2e + two DuckDB CLI tests to the new construction contract**
- **Found during:** Task 2 verification (`just test`)
- **Issue:** `test_codegen_e2e.py::test_codegen_snowflake_field_types` drove the deleted native `SnowflakeEngine(account=...)` constructor; `test_cli.py`'s `test_duckdb_resolve_creates_engine_with_database` and `test_envvar_path_normalized` pinned the CLI to `DuckDBEngine(database=...)` — both incompatible with the Engine `(*, pool, dialect, config)` signature and the CLI's move to `create_engine`. All three are in this plan's GREEN scope (Plan 02 deferred them here).
- **Fix:** the Snowflake e2e test now builds via `create_engine(SnowflakeConfig(...))` with a mocked `create_pool` and a patched `engine.connect()` (mirroring `test_snowflake_engine.py`); the two CLI tests assert `create_engine` is called with a `DuckDBConfig` carrying the normalized database.
- **Files modified:** `tests/unit/codegen/test_codegen_e2e.py`, `tests/unit/codegen/test_cli.py`
- **Verification:** `test_cli` 37/37 green; e2e Snowflake + DuckDB green.
- **Committed in:** `7f8c44c` (Task 2 commit)

**3. [Rule 3 - Blocking] Moved record-mode native-connector kwargs into the integration conftest before deleting the helpers**
- **Found during:** Task 3 (confirming zero importers)
- **Issue:** RESEARCH Open Q1 assumed the integration conftest record-mode DDL used the native connectors directly; in fact it imported `snowflake_connect_kwargs`/`databricks_connect_kwargs`. Deleting them first would have broken record mode.
- **Fix:** added local `_snowflake_native_kwargs`/`_databricks_native_kwargs` helpers (record-mode-only glue) in `tests/integration/conftest.py`; then deleted the library functions. The runtime/replay path is untouched.
- **Files modified:** `tests/integration/conftest.py`, `src/semolina/config.py`
- **Verification:** `grep` shows zero importers under `src/`+`tests/`; Snowflake cassettes replay 7/7 green.
- **Committed in:** `0a2591b` (Task 3 commit)

**4. [Rule 2 - Correctness] Replaced stale class docstrings + `# type: ignore` with current ADBC docs and `cast`**
- **Found during:** Task 1
- **Issue:** The `SnowflakeEngine`/`DuckDBEngine` class docstrings described the deleted native-connector design and `SnowflakeEngine(**connection_params)` / `DuckDBEngine(database=...)` construction (now built via `create_engine`); the parser carried `# type: ignore[arg-type]` on the `field_type` Literal (CLAUDE.md forbids `# type: ignore`).
- **Fix:** rewrote both class docstrings to the `create_engine` + ADBC-pool design (CLAUDE.md mandates docs follow API-surface changes); used `typing.cast("Literal['metric','dimension','fact']", ...)` instead of `# type: ignore`.
- **Files modified:** `src/semolina/engines/snowflake.py`, `src/semolina/engines/duckdb.py`
- **Verification:** `grep -c 'snowflake.connector'` == 0; basedpyright strict + `just docs-build` pass.
- **Committed in:** `d916f09` (Task 1 commit)

---

**Total deviations:** 4 (1 bug, 2 blocking, 1 correctness)
**Impact on plan:** All necessary to land the GREEN wave through `just test` (minus the Plan-04 Databricks suite) and basedpyright strict while honoring the no-`# type: ignore` gate. No scope creep beyond the plan's explicit deferral of Databricks to Plan 04.

## Issues Encountered

- ADBC `adbc_driver_manager.ProgrammingError`/`Error` require a keyword-only `status_code` and collapse DuckDB's native exception hierarchy into one `Error` class — resolved by message-based classification for DuckDB and an explicit `AdbcStatusCode` in the Snowflake error test.

## Known Stubs

None. Databricks `introspect()` remains on the pre-Phase-44 native seam (explicitly Plan 04), not a stub returning placeholder data.

## Deferred Issues (out of this plan's scope)

Logged in `.planning/phases/44-engine-owns-the-pool/deferred-items.md`. All Databricks-only:

- `tests/unit/test_databricks_engine.py` (30) — legacy native `DatabricksEngine(server_hostname=...)` suite; rewire onto the ADBC seam in **Plan 04**.
- `tests/unit/codegen/test_codegen_e2e.py::test_codegen_databricks_field_types` (1) — same native constructor; **Plan 04**.
- `tests/integration/test_queries.py[databricks_engine]` (7) — **pre-existing**: Databricks cassettes never recorded (STATE blocker "Databricks integration recording hangs"); fail identically on clean `main`. Snowflake integration replays 7/7 green.

## Threat Surface

No new trust boundaries beyond the plan's `<threat_model>`. T-44-05 (ADBC error translation) is mitigated: introspectors catch `adbc_driver_manager.{ProgrammingError,OperationalError,Error}` and re-raise the Semolina error classes with view-name context only — no raw connection strings/secrets leaked. T-44-04 (identifier f-string injection) carried over unchanged; the redesign does not widen the surface.

## Next Phase Readiness

- The Snowflake+DuckDB critical path is fully on the owned ADBC pool; every introspector and the runtime query path flow through one pool (closing RESEARCH's "two parallel worlds").
- **Plan 04** rewires Databricks `introspect()` onto ADBC (spike-gated, driver-acquisition first) and migrates `test_databricks_engine` + the e2e/integration Databricks cases — removing the narrowed pragmas left here.
- **Plan 05** is the formal cassette-replay gate; Snowflake replay is already verified green here.
- **Plan 06** migrates docs to the `create_engine`/`register(engine)` surface (now final).
- No new blockers introduced.

---
*Phase: 44-engine-owns-the-pool*
*Completed: 2026-06-24*

## Self-Check: PASSED

- SUMMARY file present: `.planning/phases/44-engine-owns-the-pool/44-03-SUMMARY.md`
- Deferred-items log present: `.planning/phases/44-engine-owns-the-pool/deferred-items.md`
- Task commits present: `d916f09`, `7f8c44c`, `0a2591b`
- Modified source files present on disk (`engines/snowflake.py`, `engines/duckdb.py`, `engines/base.py`, `config.py`, `cli/codegen.py`)
- Key symbols verified: `self.connect()` in both introspectors; `SHOW COLUMNS IN VIEW` retained; `snowflake.connector` count 0; `*_connect_kwargs` deleted with zero importers; `import semolina` exposes `create_engine`/`get_engine`, not `pool_from_config`/`get_pool`
