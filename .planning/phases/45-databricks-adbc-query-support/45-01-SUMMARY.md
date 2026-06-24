---
phase: 45-databricks-adbc-query-support
plan: 01
subsystem: api
tags: [databricks, sql-generation, dialect, adbc, sql-injection, spark-sql]

# Dependency graph
requires:
  - phase: 44-engine-owns-pool
    provides: Engine owns ADBC pool + dialect; build_select_with_params is the single SQL seam
provides:
  - "Dialect.supports_parameterized_queries capability flag (True default, False on Databricks)"
  - "Dialect.render_literal() — single audited SQL-literal escaper (standard SQL + Spark override)"
  - "SQLBuilder._render_literal_sql() post-pass that inlines WHERE literals when the dialect lacks bind-param support"
  - "Databricks .where() now emits inline literals + empty params; Snowflake/DuckDB unchanged"
affects: [45-03-databricks-cassette-recording, databricks-query-execution]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Capability-flag dispatch on the Dialect ABC (no isinstance in the builder)"
    - "Single audited render_literal escaper as the only user-value-into-SQL surface"
    - "Literal-inlining post-pass reusing render_inline's left-to-right single-replace discipline"

key-files:
  created: []
  modified:
    - src/semolina/engines/sql.py
    - tests/unit/test_sql.py

key-decisions:
  - "Spark string escaping: escape backslash first (\\ -> \\\\), then single quote (' -> \\'); order matters"
  - "Standard-SQL default doubles the single quote ('' ); int/float via repr() unquoted; NULL/TRUE/FALSE keywords"
  - "Unsupported literal types (date/Decimal) raise NotImplementedError — fail loud, never mis-escape"
  - "Post-pass is the only new control point; the 16 _compile_predicate arms are untouched"
  - "TDD RED+GREEN committed together per task (not test-only-first) because basedpyright strict rejects a test referencing not-yet-existent attributes and --no-verify is disallowed"

patterns-established:
  - "supports_parameterized_queries flag: backends whose driver rejects binds opt out in one line"
  - "render_literal is the single injection surface, tested adversarially"

requirements-completed: [DBX-01, DBX-01b, DBX-01c]

# Metrics
duration: ~25min
completed: 2026-06-24
---

# Phase 45 Plan 01: Databricks Literal-Inlining Summary

**Databricks `.where()` now inlines WHERE values as safe Spark-SQL literals (empty params) via a `supports_parameterized_queries` flag + single audited `render_literal` escaper, while Snowflake/DuckDB stay on `?` + bound params.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-24T21:50:00Z (approx)
- **Completed:** 2026-06-24T22:14:15Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `Dialect.supports_parameterized_queries` capability flag — `True` on the ABC, overridden `False` on `DatabricksDialect` only. The builder branches on the flag and never `isinstance`-checks a concrete dialect.
- `Dialect.render_literal()` — the single audited SQL-literal escaper. Standard-SQL default (double the quote) on the ABC; Spark override (escape backslash first, then quote) on `DatabricksDialect`. Handles str/int/float/bool/None; raises `NotImplementedError` for unsupported types.
- `SQLBuilder._render_literal_sql()` post-pass — reuses `render_inline`'s left-to-right single-replace loop shape but substitutes `render_literal(param)` (never unsafe `repr`). Wired into both `build_select_with_params` and the `DuckDBSQLBuilder` override.
- DBX-01: Databricks string + IN-list + adversarial filters inline correctly with `params == []`. DBX-01b: Snowflake/DuckDB no-regression tests confirm `?` + params unchanged. DBX-01c: adversarial unit tests (`O'Reilly`, `a\b`, `'; DROP TABLE x; --`, NULL, bool) pass.

## Task Commits

1. **Task 1 (RED): failing render_literal + capability-flag tests** — staged but blocked by basedpyright strict (see deviation); RED signal confirmed via direct pytest run (AttributeError).
2. **Task 1 (GREEN): flag + render_literal** — `8e32957` (feat) — Dialect ABC + DatabricksDialect, 18 tests pass.
3. **Task 2 (RED): failing Databricks-inlining tests** — confirmed failing (still emitting `?`) before the post-pass.
4. **Task 2 (GREEN): literal-inlining post-pass** — `2bb8fd8` (feat) — `_render_literal_sql` + flag branch in both builders; full 154-test SQL suite green.

**Plan metadata:** committed with this SUMMARY.

_RED was demonstrated (failing run captured) for each task; the RED + GREEN landed in one commit per task — see Deviations._

## Files Created/Modified
- `src/semolina/engines/sql.py` — added `supports_parameterized_queries` flag + `render_literal` on the `Dialect` ABC and `DatabricksDialect`; added `_render_literal_sql` post-pass and the flag branch in `SQLBuilder.build_select_with_params` and `DuckDBSQLBuilder.build_select_with_params`.
- `tests/unit/test_sql.py` — `TestSupportsParameterizedQueries`, `TestRenderLiteralStandardSql`, `TestRenderLiteralDatabricks`, `TestDatabricksLiteralInlining`, `TestParameterizedNoRegression`.

## Decisions Made
- Spark escaping order is load-bearing: `\` → `\\` **before** `'` → `\'`, so a value containing both (`a\'b` → `'a\\\'b'`) is not corrupted. Verified by `test_backslash_then_quote_ordering`.
- Standard SQL (Snowflake/DuckDB default) doubles the single quote; numbers via `repr()` unquoted; `None`→`NULL`, bool→`TRUE`/`FALSE` (lowercase on Databricks).
- Per RESEARCH Open Question 2, no Date/Decimal handling now — `render_literal` raises `NotImplementedError` for unsupported types rather than mis-escaping.
- The post-pass is the sole new control point; no `_compile_predicate` arm was edited (`grep -c 'def _compile_predicate'` unchanged at 1). The left-to-right single-replace preserves the qmark-count == param-count invariant the `In` arm relies on.

## Deviations from Plan

### Process deviation (RED/GREEN sequencing)

**1. [Constraint reconciliation] TDD RED and GREEN landed in one commit per task instead of separate RED-test-first commits**
- **Found during:** Task 1 commit attempt.
- **Issue:** The project bug-fix protocol wants a failing-test (RED) commit before the fix. But `basedpyright` (CLAUDE.md hard gate, runs in the pre-commit hook) rejects a test-only commit that references `render_literal` / `supports_parameterized_queries` before they exist (`reportAttributeAccessIssue`), and the run was instructed not to use `--no-verify`. These two hard constraints conflict for a strict-typed RED commit.
- **Fix:** For each task I authored the tests first and captured a real failing run (Task 1: `AttributeError`; Task 2: 3 inlining tests fail while the 2 regression tests pass), then committed tests + implementation together so the commit passes basedpyright strict. The RED signal is preserved in this summary; the typing gate and the no-`--no-verify` rule are both honored.
- **Files modified:** n/a (process only).
- **Verification:** RED runs shown in the execution log; GREEN runs: 18 then 154 SQL tests pass.

### Auto-fixed Issues

**2. [Rule 3 - Blocking] `isinstance` tuple form rejected by the pinned hook ruff**
- **Found during:** Task 1 commit (pre-commit hook).
- **Issue:** The ruff-pre-commit hook is pinned to `v0.9.6`, which flags `isinstance(value, (int, float))` (UP038) even though the repo's newer `uv run ruff` does not.
- **Fix:** Used `isinstance(value, int | float)` in both `render_literal` implementations; moved `import datetime` to module top in the test file.
- **Files modified:** `src/semolina/engines/sql.py`, `tests/unit/test_sql.py`.
- **Verification:** `prek run --all-files` passes (ruff + ruff-format + basedpyright strict all green).

---

**Total deviations:** 1 process reconciliation + 1 auto-fixed (blocking).
**Impact on plan:** No scope change. All plan artifacts and behaviors delivered exactly as specified; only the commit granularity for RED differs, with rationale above. No `# type: ignore` added.

## Issues Encountered
- `just test` reports 7 failing Databricks integration tests (cassettes not recorded — DBX-03, deferred to a live-creds task) and 28 jaffle-shop collection errors (`ModuleNotFoundError: semolina.testing.credentials`, a stale conftest import). Both are pre-existing and out of scope for 45-01 (my code touches only `sql.py` + `test_sql.py`). Logged to `deferred-items.md`. The 892 unit + src-doctest tests and all 154 SQL-builder tests pass; `prek run --all-files` is clean.

## Known Stubs
None — both behaviors are fully wired (no placeholder data paths).

## Threat Flags
None — the only new SQL surface is the planned, audited `render_literal` inlining (threat T-45-01, mitigated with adversarial tests). No new endpoints, auth paths, or schema changes.

## User Setup Required
None — no external service configuration required for this plan (live Databricks recording is a separate, later, operator-gated task).

## Next Phase Readiness
- DBX-01/01b/01c complete and unit-verified offline. The flag is a one-line flip back to `True` if the upstream ADBC Databricks driver gains bind-param support.
- 45-03 (cassette recording) is unblocked from the SQL side: the recorded Databricks `000_query.sql` will now show inline literals (`` `country` = 'US' ``) and `000_params.json == []`. It still needs live creds + the Foundry ADBC driver (operator-gated, `autonomous: false`).

## Self-Check: PASSED

- Files: `src/semolina/engines/sql.py`, `tests/unit/test_sql.py`, `45-01-SUMMARY.md` all present.
- Commits `8e32957`, `2bb8fd8` present in git log.
- Source markers: `supports_parameterized_queries`, `def render_literal`, `def _render_literal_sql` all present.

---
*Phase: 45-databricks-adbc-query-support*
*Completed: 2026-06-24*
