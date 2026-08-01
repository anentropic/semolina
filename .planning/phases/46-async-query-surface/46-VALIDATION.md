---
phase: 46
slug: async-query-surface
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-01
---

# Phase 46 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `46-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.0.0 + anyio pytest plugin (auto-registered) + pytest-xdist + syrupy |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests", "src"]`, `--doctest-modules`) |
| **Quick run command** | `uv run pytest tests/unit -k async -x` |
| **Full suite command** | `just test` (root `uv run pytest`, then jaffle-shop `uv run pytest`) |
| **Estimated runtime** | ~15s quick / ~90s full |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit -k async -x` plus `prek run --all-files` (includes the new TID251 Posture A gate)
- **After every plan wave:** Run `just test`
- **Before `/gsd-verify-work`:** Full suite green, `just docs-build` clean under `-W`, and the `packaging-smoke` base-install assertion passing
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

Task IDs are assigned once PLAN.md files exist; `/gsd-validate-phase` fills them in.
Rows below are the requirement-level contract every task must map onto.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | 1 | ASYNC-04 | — | Optional dep stays optional; no anyio in a base install | packaging | `uv run pytest tests/unit -k packaging -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | ASYNC-05 | — | No `asyncio.*` / anyio import in `src/semolina/` | lint | `uv run ruff check src/semolina` (TID251) | ❌ W0 (rule) | ⬜ pending |
| TBD | TBD | 2 | ASYNC-01 | T-46-02 | `await engine.aexecute(q)` returns rows; connection returned to pool | unit | `uv run pytest tests/unit/test_async_engine.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | ASYNC-01 | T-46-01 | Event loop stays free under concurrency (file-backed DuckDB) | unit | `uv run pytest tests/unit/test_async_engine.py -k concurrency -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | ASYNC-03 | — | `async for row in cursor` streams `Row` batch by batch, no whole-table materialization | unit | `uv run pytest tests/unit/test_async_cursor.py -k stream -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | ASYNC-03 | T-46-02 | Close order reader→cursor→conn; no `ConnectionBusyError`; pool `checkedout()` returns to 0 | unit | `uv run pytest tests/unit/test_async_cursor.py -k close -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | ASYNC-02 | — | `await Sales.query()...aexecute()` matches the sync result surface | unit | `uv run pytest tests/unit/test_async_query.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | ASYNC-06 | T-46-03 | Cancellation reaches the driver via `adbc_cancel`, not merely abandoned | unit (real DuckDB) | `uv run pytest tests/unit/test_async_cancel.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | ASYNC-05 | — | Async tests green under asyncio **and** Trio | unit (parametrized) | `uv run pytest tests/unit -k "async and trio" -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | ASYNC-01, ASYNC-03 | T-46-05 | Snowflake + Databricks dialects replay through the async path | integration (cassette) | `uv run pytest tests/integration -k async` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | TOOL-01 | — | N/A — planning config only | inspection | `python -c "import json;assert json.load(open('.planning/config.json'))['git']['branching_strategy']=='milestone'"` | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — `[async]` extra, `all` includes `async`, dev gains `trio`, poolhouse floor bump, `TID` in `select` + `banned-api` + `per-file-ignores` (gates everything; D-11)
- [ ] `tests/unit/test_async_engine.py` — stubs for ASYNC-01
- [ ] `tests/unit/test_async_cursor.py` — stubs for ASYNC-03 (streaming + close ordering)
- [ ] `tests/unit/test_async_query.py` — stubs for ASYNC-02
- [ ] `tests/unit/test_async_cancel.py` — stubs for ASYNC-06 (real DuckDB, long-running query)
- [ ] `tests/conftest.py` — `async_duckdb_engine` fixture on the existing `duckdb_file_backed_db`; async-aware `registry.reset()` teardown (Finding 3)
- [ ] Per-module `anyio_backend` parametrized fixtures — the ASYNC-05 loop matrix
- [ ] `tests/integration/` — `snowflake_async_engine` / `databricks_async_engine` fixtures + named cassette copies
- [ ] `.github/workflows/ci.yml` — extend `packaging-smoke` with the base-install no-anyio assertion (ASYNC-04)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-warehouse async execution against live Snowflake / Databricks | ASYNC-01, ASYNC-03 | Needs live credentials; CI runs replay cassettes only | Set warehouse env vars, run `uv run pytest tests/integration -k async --adbc-record` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
