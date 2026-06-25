---
phase: 45
slug: databricks-adbc-query-support
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-24
---

# Phase 45 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 45-RESEARCH.md "## Validation Architecture". Both code fixes are
> unit-testable OFFLINE (SQL-string + URI-string assertions); only the cassette
> recording needs a live warehouse.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (+ pytest-adbc-replay plugin) |
| **Config file** | `pyproject.toml` (markers `unit`, `adbc_cassette`; `adbc_auto_patch` for replay) |
| **Quick run command** | `uv run pytest tests/unit -x` |
| **Full suite command** | `just test` (unit + jaffle-shop mock) |
| **Estimated runtime** | ~30 seconds (unit); integration replay adds the recorded backends |

> Run tooling with the command sandbox disabled (uv/prek/basedpyright panic under it).

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit -x` (SQL-generation + URI assertions — fast, offline)
- **After every plan wave:** Run `just test` + `prek run --all-files`
- **Before `/gsd-verify-work`:** `uv run pytest tests/integration` green (all backends replay, incl. the 7 Databricks + 7 Snowflake)
- **Max feedback latency:** ~30 seconds (offline tasks)

---

## Per-Task Verification Map

| Req ID | Behavior | Threat Ref | Test Type | Automated Command | File Exists | Status |
|--------|----------|------------|-----------|-------------------|-------------|--------|
| DBX-01 | Databricks `.where()` emits inline literal + empty params | T-45-01 | unit | `uv run pytest tests/unit -k "databricks and where" -x` | ❌ W0 | ⬜ pending |
| DBX-01b | Snowflake/DuckDB `.where()` STILL emit `?` + params (no regression) | — | unit | `uv run pytest tests/unit -k "where and (snowflake or duckdb)" -x` | ⚠️ extend | ⬜ pending |
| DBX-01c | `render_literal` escapes `'`, `\`, NULL, bool, IN-list for Databricks | T-45-01 | unit | `uv run pytest tests/unit -k render_literal -x` | ❌ W0 | ⬜ pending |
| DBX-02 | poolhouse `to_adbc_kwargs()` URI carries `?catalog=&schema=` (none when both None) | T-45-02 | unit (cross-repo) | `pytest -k to_adbc_kwargs` (in adbc-poolhouse) | ❌ W0 | ⬜ pending |
| DBX-03 | All 7 Databricks integration tests replay GREEN from recorded cassettes | — | integration (replay) | `uv run pytest tests/integration -k databricks` | ❌ record first | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_databricks_dialect_literals.py` (or adjacent to existing dialect tests) — stubs for DBX-01, DBX-01c
- [ ] Extend existing dialect / SQL-builder unit tests — assert Snowflake/DuckDB stay parameterized (DBX-01b)
- [ ] adbc-poolhouse `tests/test_databricks_config.py` — DBX-02 (cross-repo, in the poolhouse repo)
- [ ] No framework install needed — pytest + pytest-adbc-replay already present

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Record the 7 Databricks cassettes | DBX-03 | Needs live Databricks creds + warm warehouse + the Foundry ADBC driver; cannot run in CI | `uv run pytest --adbc-record=all tests/integration -k databricks`, then commit cassettes. Plan task marked `autonomous: false`. |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
