---
phase: 44
slug: engine-owns-the-pool
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-23
---

# Phase 44 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `44-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.0 (+ pytest-xdist, pytest-adbc-replay >=1.1.1, syrupy, pytest-cov) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]` incl. `adbc_*` keys) |
| **Quick run command** | `just test` (unit + jaffle-shop mock) |
| **Full suite command** | `just test && pytest tests/integration` (replay mode, default) |
| **Estimated runtime** | ~60 seconds (unit + mock); integration replay adds ~30s |

---

## Sampling Rate

- **After every task commit:** Run `just test`
- **After every plan wave:** Run `just test && pytest tests/integration && just docs-build`
- **Before `/gsd-verify-work`:** Full suite green + `prek run --all-files` (ruff + basedpyright strict)
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

> No phase_req_ids mapped. Coverage derived from CONTEXT.md locked decisions (D1–D5).

| Decision | Behavior | Wave | Test Type | Automated Command | File Exists | Status |
|----------|----------|------|-----------|-------------------|-------------|--------|
| D1 | `create_engine(config)` builds Engine from config object | 1 | unit | `pytest tests/unit/test_config.py -k create_engine` | ❌ W0 (new) | ⬜ pending |
| D1 | `create_engine(name)` reads `[connections.<name>]` | 1 | unit | `pytest tests/unit/test_config.py -k from_toml` | ⚠️ adapt | ⬜ pending |
| D2 | Engine owns pool; `execute()` runs query through ADBC pool | 2 | unit | `pytest tests/unit/test_pool.py` | ✅ adapt | ⬜ pending |
| D3 | introspect via ADBC (Snowflake) `SHOW COLUMNS` | 2 | unit | `pytest tests/unit/test_snowflake_engine.py` | ✅ rewrite mocks | ⬜ pending |
| D3 | introspect via ADBC (Databricks) `DESCRIBE ... AS JSON` | 2 | spike+unit | spike script, then `pytest tests/unit/test_databricks_engine.py` | ⚠️ spike-gated | ⬜ pending |
| D3 | introspect via ADBC (DuckDB) `DESCRIBE SEMANTIC VIEW` | 2 | unit | `pytest tests/unit/test_duckdb_engine.py` | ✅ rewrite | ⬜ pending |
| D4 | `register("name", engine)`; `.using()` resolves Engine | 2 | unit | `pytest tests/unit/test_registry.py` | ✅ rewrite (3→2 arg) | ⬜ pending |
| D2/D3 | end-to-end replay — cassettes stay green | 3 | integration | `pytest tests/integration` | ✅ adapt fixtures | ⬜ pending |
| codegen | `_resolve_backend` builds Engine via `create_engine` | 2 | unit | `pytest tests/unit/codegen/test_cli.py` | ✅ adapt | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_config.py` — new `create_engine` tests (config-object + TOML-name dispatch); adapt existing `pool_from_config` mock tests (patch `semolina.config.create_pool`)
- [ ] `tests/unit/test_registry.py` — rewrite `register(pool, dialect=...)` → `register(engine)`; `get_pool` → `get_engine`
- [ ] `tests/unit/test_snowflake_engine.py` / `test_databricks_engine.py` / `test_duckdb_engine.py` — replace native-connector `sys.modules` mocks with ADBC-cursor mocks
- [ ] `tests/unit/test_pool.py` — update `register("test", pool, dialect=...)` call sites
- [ ] `tests/integration/conftest.py` — fixtures move from `create_pool` + `register(pool, dialect)` to `create_engine` + `register(engine)`
- [ ] `tests/conftest.py` + `src/semolina/conftest.py` (doctest) — `duckdb_pool` / `doctest_setup` fixtures move to Engine API
- [ ] Databricks ADBC introspection **spike script** (standalone, not pytest) — gated on Foundry-driver acquisition

---

## Manual-Only Verifications

| Behavior | Decision | Why Manual | Test Instructions |
|----------|----------|------------|-------------------|
| Databricks introspection over live ADBC | D3 | Foundry-distributed ADBC driver not on PyPI / not installed; recording hangs | Run spike script against a live Databricks ADBC connection (no recording) once Foundry driver is acquired; compare `DESCRIBE TABLE EXTENDED ... AS JSON` output to native |

*If the spike cannot be run, Databricks introspection ships as TODO and Snowflake+DuckDB carry the new API.*

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
