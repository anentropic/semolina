---
phase: 44-engine-owns-the-pool
verified: 2026-06-24T00:00:00Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
deferred:
  - truth: "Databricks ADBC introspection executes DESCRIBE TABLE EXTENDED AS JSON over the pool"
    addressed_in: "Post-Phase 44 follow-up (spike gated on Foundry driver availability)"
    evidence: >
      CONTEXT open items and 44-04-PLAN explicitly accept NotImplementedError fallback.
      DatabricksEngine.introspect() raises NotImplementedError with actionable guidance.
      databricks_engine CassetteMissError failures (7/7) are the pre-existing known blocker
      documented in CONTEXT and ROADMAP. Phase goal explicitly scopes this as a gated spike.
---

# Phase 44: Engine Owns the Pool Verification Report

**Phase Goal:** Make `Engine` own its ADBC pool + dialect (SQLAlchemy-style) and serve
both introspection and execution from it; `create_engine(config|name)` + `register("name",
engine)` replace the bare `(pool, dialect)` tuple. ADBC-only — native connectors removed.
Clean break of the v0.5 connection API (pre-1.0).

**Verified:** 2026-06-24T00:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `create_engine(config_obj)` and `create_engine("name")` exist; dialect derived from config type via `_CONFIG_MAP`; no URL-string form | VERIFIED | `config.py:187-247` — `create_engine()` dispatches on `isinstance(config, str)`; str path calls `_read_connection` (TOML); object path calls `_dialect_for_config_type` reverse-lookup against `_CONFIG_MAP`; no URL dispatch path exists |
| 2 | `Engine` owns one ADBC pool + dialect; `engine.connect()` checks out ADBC connection; `engine.execute(query)` runs through pool and returns `SemolinaCursor`; CR-01 connection-leak fix present on error path | VERIFIED | `base.py:88-149` — `connect()` returns `self._pool.connect()`; `execute()` wraps `cur.execute()` in `try/except BaseException: conn.close(); raise` before returning `SemolinaCursor(cur, conn, self._pool)` — CR-01 fix confirmed |
| 3 | Snowflake introspection (`SHOW COLUMNS IN VIEW`) and DuckDB introspection (`DESCRIBE SEMANTIC VIEW`) run through engine's ADBC pool; Databricks `introspect()` raises `NotImplementedError` (gated spike) | VERIFIED | `engines/snowflake.py:162-163` uses `with self.connect() as conn:` then `cur.execute(f"SHOW COLUMNS IN VIEW {qualified_name}")`; `engines/duckdb.py:156-157` same pattern with `DESCRIBE SEMANTIC VIEW`; `engines/databricks.py:102-149` raises `NotImplementedError` with explicit documentation of why and how to resolve |
| 4 | `register("name", engine)` accepts an Engine; registry maps name→Engine; `Query.using("name").execute()` resolves the Engine via `get_engine`; `get_pool` is gone | VERIFIED | `registry.py:20` — `register(name: str, engine: Engine)`; `registry.py:52` — `get_engine(name)`; `query.py:414-419` — `execute()` calls `get_engine(self._using)` then `engine.execute(self)`; no `get_pool` anywhere in `src/` |
| 5 | `snowflake_connect_kwargs()` / `databricks_connect_kwargs()` deleted; `pool_from_config` internal-only (not in `__init__.py`); public surface = `create_engine`, `register`, `SemanticView`/fields, config classes; per-backend Engine subclasses internal | VERIFIED | `grep snowflake_connect_kwargs src/` — no results; `grep databricks_connect_kwargs src/` — no results; `__init__.py` exports: `create_engine`, `register`, `get_engine`, `unregister`, `SemanticView`, fields, `Dialect`, cursor/error classes — `pool_from_config` not exported; Engine subclasses not exported |
| 6 | No native-connector code path in library; Snowflake cassettes replay 7/7 green; docs migrated to new API | VERIFIED | `grep snowflake-connector-python src/` — only a comment in `_expand_private_key_path` docstring (explains *why* the function exists, not a call site); `just test` result: 7 failed (all `databricks_engine` CassetteMissError — pre-existing known blocker), 872 passed, 16 skipped; Snowflake cassettes: all 7 replay GREEN; `docs/src/` — all examples use `create_engine`/`register` with no `pool_from_config` or old tuple-register calls |

**Score:** 6/6 truths verified

---

### Deferred Items

Items not yet met but explicitly accepted as out-of-scope by CONTEXT decisions.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Databricks ADBC introspection (live path, not NotImplementedError) | Post-Phase 44 follow-up spike | CONTEXT open items: "Databricks introspection over ADBC is NOT yet validated"; 44-04-PLAN: "Path B — NotImplementedError fallback + standalone spike"; `databricks.py` module docstring and introspect() docstring document the gap and the resolution path |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/semolina/engines/base.py` | Engine ABC with connect()/execute() owning pool | VERIFIED | 181 lines; full implementation with CR-01 fix at lines 136-147 |
| `src/semolina/engines/snowflake.py` | SnowflakeEngine with ADBC introspect() | VERIFIED | `SHOW COLUMNS IN VIEW` over `self.connect()` context manager |
| `src/semolina/engines/duckdb.py` | DuckDBEngine with ADBC introspect() | VERIFIED | Two-step `DESCRIBE SEMANTIC VIEW` + `DESCRIBE SELECT` over `self.connect()` |
| `src/semolina/engines/databricks.py` | DatabricksEngine with NotImplementedError introspect() | VERIFIED | Clearly documented NotImplementedError with spike instructions |
| `src/semolina/config.py` | `create_engine()` factory; `_read_connection`; no `*_connect_kwargs` | VERIFIED | `create_engine` at line 187; `_read_connection` at 250; no `snowflake_connect_kwargs` or `databricks_connect_kwargs` in file |
| `src/semolina/registry.py` | `register(name, engine)` / `get_engine(name)` | VERIFIED | Signature confirmed; `get_pool` absent from file |
| `src/semolina/query.py` | `execute()` resolves Engine via `get_engine` | VERIFIED | Lines 414-419; calls `get_engine(self._using)` then `engine.execute(self)` |
| `src/semolina/cli/codegen.py` | `_resolve_backend` returns Engine via `create_engine` | VERIFIED | Lines 86-112; calls `warehouse_config()` + `create_engine(config)` |
| `src/semolina/__init__.py` | Public surface: `create_engine`, `register`, `get_engine`; no old API | VERIFIED | All 4 new surface symbols present; `pool_from_config` absent |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `Query.execute()` | `Engine.execute()` | `get_engine(self._using)` | WIRED | `query.py:418-419` |
| `Engine.execute()` | ADBC pool | `self.connect()` / `conn.cursor()` | WIRED | `base.py:136-149`; error path closes conn |
| `SnowflakeEngine.introspect()` | ADBC pool | `with self.connect() as conn:` | WIRED | `snowflake.py:162-163` |
| `DuckDBEngine.introspect()` | ADBC pool | `with self.connect() as conn:` | WIRED | `duckdb.py:156-157` |
| `create_engine(str)` | TOML config | `_read_connection()` | WIRED | `config.py:232-233` |
| `create_engine(config_obj)` | Engine subclass | `_engine_cls_for_dialect()` + `create_pool()` | WIRED | `config.py:238-247` |
| `_resolve_backend` (CLI) | Engine | `warehouse_config()` + `create_engine()` | WIRED | `codegen.py:89-112` |

---

### Behavioral Spot-Checks (Test Gate)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 7/7 Snowflake cassettes replay green | `just test` | 872 passed, 16 skipped, 7 failed (Databricks only) | PASS |
| prek ruff + basedpyright strict | `prek run --all-files` | All hooks Passed | PASS |
| Docs build zero warnings | `just docs-build` | "build succeeded" with -W flag | PASS |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `engines/databricks.py` | 134 | `TODO(Phase 44):` | INFO | References formal phase context; intentional deferred-spike marker. Acceptable per anti-pattern gate rules (references formal follow-up work). Not a blocker. |

No `TBD`, `FIXME`, or `XXX` markers found in any phase-modified source files.

Note: `pool_from_config` survives in `config.py` but is NOT exported from `__init__.py`. Its docstring's claim that the returned `(pool, Dialect)` tuple is "ready for `register()`" is stale (WR-04 from code review) — this is a warning-level issue documented in REVIEW.md, not a phase-goal blocker. The phase goal requires the *new* surface to work correctly, which it does. Removal of `pool_from_config` is a follow-up cleanup.

---

### Human Verification Required

None. All goal-defining behaviors are verifiable programmatically and confirmed green.

---

### Gaps Summary

No gaps. All six must-haves are VERIFIED. The only known deficiencies (WR-01 through WR-06 from the code review) are lifecycle warnings and maintenance debt — none block the phase goal. The Databricks `NotImplementedError` fallback is explicitly accepted in the CONTEXT decisions as the correct Phase 44 outcome for the gated spike.

---

_Verified: 2026-06-24T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
