---
phase: 49
slug: into-dto-typed-results
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-14
---

# Phase 49 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `49-RESEARCH.md` §Validation Architecture (lines 1084–1164).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥8.0.0 (+ pytest-xdist, pytest-cov, syrupy, pytest-adbc-replay ≥1.1.1) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (root) and `semolina-jaffle-shop/pyproject.toml` |
| **Root addopts** | `-v --doctest-modules --doctest-continue-on-failure`, `testpaths = ["tests", "src"]` |
| **Quick run command** | `uv run pytest tests/unit/test_dto.py -x -q` |
| **Full suite command** | `just test` — root `uv run pytest` **then** `semolina-jaffle-shop` `uv run pytest` |
| **Estimated runtime** | ~60 seconds (both suites) |
| **Extra gates** | `prek run --all-files`, `just docs-build`, `uv run python tests/type_fidelity_probe.py --check` |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_dto.py -x -q` plus the specific file the task touched
- **After every plan wave:** Run `just test` (both suites) + `prek run --all-files`
- **Before `/gsd-verify-work`:** `just test`, `prek run --all-files`, `just docs-build`,
  `uv run python tests/type_fidelity_probe.py --check`, and a green CI `packaging-smoke` job
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Populated per task by the planner / executor. Requirement → behaviour → command mapping
> is fixed by the table below; task IDs bind to it once plans exist.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | DTO-01 | — | N/A | unit | `uv run pytest tests/unit/test_dto.py -k into_returns -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DTO-01 | — | N/A | integration (live DuckDB) | `uv run pytest tests/unit/test_dto_duckdb.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DTO-02 | — | N/A | unit | `uv run pytest tests/unit/test_dto.py -k iter_into -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DTO-02 | T-49-03 | Async cursor closed via `async with`; no leaked pool slot | unit (asyncio+trio matrix) | `uv run pytest tests/unit/test_dto_async.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DTO-02 | — | N/A | unit | `uv run pytest tests/unit/test_dto.py -k lazy -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DTO-03 | T-49-01 | Error names field + both types; carries no row values | unit | `uv run pytest tests/unit/test_dto.py -k mismatch -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DTO-03 | — | N/A | unit | `uv run pytest tests/unit/test_dto.py -k reports_every -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DTO-03 | — | N/A | unit (non-vacuous) | `uv run pytest tests/unit/test_dto.py -k raises_at_call -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DTO-03 | T-49-01 | Decimal→float blocked on **both** validate settings | unit | `uv run pytest tests/unit/test_dto.py -k decimal_into_float -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DTO-04 | — | N/A | unit | `uv run pytest tests/unit/test_dto.py -k untyped -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DTO-04 | — | N/A | unit | `uv run pytest tests/unit/test_dto.py -k default -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DTO-05 | T-49-04 | `uv.lock` regenerated in the same task | unit (reads pyproject) | `uv run pytest tests/unit/test_dto_packaging.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DTO-05 | T-49-02 | Base install pulls no arrowmodel/pandas/polars | unit (child interpreter) | `uv run pytest tests/unit/test_dto_packaging.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DTO-05 | T-49-02 | Clean-venv install asserts absence | CI job | `packaging-smoke` in `.github/workflows/ci.yml` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | DTO-06 | — | N/A | docs gate | `just docs-build` | ✅ | ⬜ pending |
| TBD | TBD | TBD | RESULT-01 | — | N/A | unit + DuckDB-live | `uv run pytest tests/unit/test_cursor.py -k fetch_df -x` | ✅ files exist | ⬜ pending |
| TBD | TBD | TBD | RESULT-02 | — | N/A | unit (`find_spec` patch) | `uv run pytest tests/unit/test_cursor.py -k missing_dependency -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | RESULT-02 | — | N/A | unit | `uv run pytest tests/unit/test_cursor.py -k missing_dependency -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | D-16 | — | N/A | artifact gate | `uv run python tests/type_fidelity_probe.py --check` | ✅ harness | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_dto.py` — DTO-01/02/03/04 pre-check and conversion behaviour
- [ ] `tests/unit/test_dto_async.py` — DTO-02 async twin; **must satisfy `tests/unit/test_asyncio_trio_matrix.py`**, which selects modules by content via an AST walk
- [ ] `tests/unit/test_dto_duckdb.py` — live DuckDB end-to-end, decimal `isinstance` proof (mirrors `test_type_fidelity_duckdb.py`)
- [ ] `tests/unit/test_dto_packaging.py` — DTO-05 extras contract + child-interpreter import check (copy `tests/unit/test_async_packaging.py`)
- [ ] new tests in `tests/unit/test_cursor.py` / `test_async_cursor.py` — RESULT-01/02 and the four pyarrow guards
- [ ] `.github/workflows/ci.yml` `packaging-smoke` — extend the base-install assertion to arrowmodel/pandas/polars
- [ ] **Dependency prerequisite, not a test file:** `polars` and `arrowmodel` are absent from `.venv`. The `pyproject.toml` + `uv.lock` + `uv sync` task is a hard wave-ordering constraint — D-16 cannot produce a real row before it.

*No framework install needed — pytest and every plugin are already in the dev group.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `.into()` against a live Snowflake / Databricks warehouse | DTO-01 | No live warehouse in CI; cassettes cover replay only. Research assumption A4 flags that a live-warehouse `.into()` has never been run | Run the DTO-06 docs example against a real warehouse; confirm column aliasing (`AGG("REVENUE")`) resolves via `Field(validation_alias=...)` |
| DTO-06 docs read correctly for the target audience | DTO-06 | Diataxis classification and voice are editorial | Apply `.claude/skills/semolina-docs-author/SKILL.md`; humanizer pass |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
