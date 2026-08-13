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
| 01-T2 | 49-01 | 1 | DTO-05 | T-49-04, T-49-SC | Legitimacy checkpoint precedes install; `uv.lock` regenerated in the same commit | packaging | `uv sync --locked --all-groups --extra all` | ✅ pyproject exists | ⬜ pending |
| 01-T3 | 49-01 | 1 | DTO-01, DTO-03 | T-49-01, T-49-05 | Pre-check is schema-only; error names types, never values | integration (live DuckDB) | `uv run pytest tests/unit/test_dto_duckdb.py -x` | ❌ W0 | ⬜ pending |
| 01-T3 | 49-01 | 1 | DTO-03 | T-49-01 | Decimal→float blocked on **both** validate settings | integration (live DuckDB) | `uv run pytest tests/unit/test_dto_duckdb.py -k decimal_into_float -x` | ❌ W0 | ⬜ pending |
| 01-T3 | 49-01 | 1 | DTO-01 | — | N/A | unit (map coverage) | `uv run pytest tests/unit/codegen/test_arrow_map.py -x` | ✅ file exists | ⬜ pending |
| 01-T3 | 49-01 | 1 | DTO-03 | T-49-01 | Value-path prohibition stays runnable after the fence is narrowed (PD-06) | gate | `uv run pytest tests/unit/test_scope_fence.py -x` | ✅ exists, narrowed | ⬜ pending |
| 02-T2 | 49-02 | 2 | DTO-02 | — | N/A | unit | `uv run pytest tests/unit/test_dto.py -k iter_into -x` | ❌ W0 | ⬜ pending |
| 02-T2 | 49-02 | 2 | DTO-02 | — | One batch in memory: assert on the fake reader's pull counter | unit | `uv run pytest tests/unit/test_dto.py -k lazy -x` | ❌ W0 | ⬜ pending |
| 02-T2 | 49-02 | 2 | DTO-03 | T-49-01 | Fails at the call, before any batch moves | unit (non-vacuous — must fail against a bare-generator impl) | `uv run pytest tests/unit/test_dto.py -k raises_at_call -x` | ❌ W0 | ⬜ pending |
| 02-T3 | 49-02 | 2 | DTO-03 | T-49-01, T-49-05 | Error names field + both types; carries no row values | unit | `uv run pytest tests/unit/test_dto.py -k mismatch -x` | ❌ W0 | ⬜ pending |
| 02-T3 | 49-02 | 2 | DTO-03 | — | All mismatches reported at once (D-11) | unit | `uv run pytest tests/unit/test_dto.py -k reports_every -x` | ❌ W0 | ⬜ pending |
| 02-T3 | 49-02 | 2 | DTO-04 | — | N/A | unit | `uv run pytest tests/unit/test_dto.py -k untyped -x` | ❌ W0 | ⬜ pending |
| 02-T3 | 49-02 | 2 | DTO-04 | — | Missing column allowed only when the field is not required (D-08) | unit | `uv run pytest tests/unit/test_dto.py -k default -x` | ❌ W0 | ⬜ pending |
| 02-T3 | 49-02 | 2 | DTO-06 | T-49-09 | Snowflake `AGG("REVENUE")` resolves only via an explicit alias | unit | `uv run pytest tests/unit/test_dto.py -k alias -x` | ❌ W0 | ⬜ pending |
| 03-T1 | 49-03 | 2 | RESULT-01 (D-16) | T-49-05 | Artifact records types only; no value column | artifact gate | `uv run python tests/type_fidelity_probe.py --check` | ✅ harness | ⬜ pending |
| 03-T1 | 49-03 | 2 | RESULT-01 (D-16) | T-49-05 | Committed artifact matches the generator | unit | `uv run pytest tests/unit/test_type_fidelity_table.py -x` | ✅ exists | ⬜ pending |
| 03-T2 | 49-03 | 2 | RESULT-01 (D-17) | T-49-06 | Correction is additive; no deleted lines in the decision record | review gate | `git diff -U0 .planning/phases/47-type-fidelity-probe-decision-doc/47-DECISIONS.md` shows no `-` lines | ✅ exists | ⬜ pending |
| 04-T1 | 49-04 | 2 | DTO-05 | T-49-04 | Extras declared with exact pins; `[all]` reaches all four | unit (reads pyproject) | `uv run pytest tests/unit/test_dto_packaging.py -x` | ❌ W0 | ⬜ pending |
| 04-T1 | 49-04 | 2 | DTO-05 | T-49-04 | `import semolina` pulls no arrowmodel/polars | unit (child interpreter) | `uv run pytest tests/unit/test_dto_packaging.py -k import -x` | ❌ W0 | ⬜ pending |
| 04-T2 | 49-04 | 2 | DTO-05 | T-49-04, T-49-07 | Clean-venv install asserts absence; every claim measured before written | CI job | `packaging-smoke` in `.github/workflows/ci.yml` | ✅ extend | ⬜ pending |
| 05-T2 | 49-05 | 3 | RESULT-01 | — | Returns proven by `isinstance` off the live driver path | unit + DuckDB-live | `uv run pytest tests/unit/test_cursor.py -k fetch_df -x` | ✅ file exists | ⬜ pending |
| 05-T2 | 49-05 | 3 | RESULT-01 | T-49-03 | `fetch_polars` must be the first consuming call | unit + DuckDB-live | `uv run pytest tests/unit/test_cursor.py -k fetch_polars -x` | ✅ file exists | ⬜ pending |
| 05-T2 | 49-05 | 3 | RESULT-02 | T-49-08 | Message names the package and the install command | unit (`find_spec` patch) | `uv run pytest tests/unit/test_cursor.py -k missing_dependency -x` | ❌ W0 | ⬜ pending |
| 06-T1 | 49-06 | 3 | DTO-02, DTO-03 | T-49-01 | Async `iter_into` is neither a coroutine nor an async generator function | unit (introspection gate) | `uv run pytest tests/unit/test_dto_async.py -k raises_at_call -x` | ❌ W0 | ⬜ pending |
| 06-T3 | 49-06 | 3 | DTO-01, DTO-02 | T-49-03 | Async cursor closed via `async with`; no leaked pool slot | unit (asyncio+trio matrix) | `uv run pytest tests/unit/test_dto_async.py -W error::ResourceWarning -x` | ❌ W0 | ⬜ pending |
| 06-T3 | 49-06 | 3 | DTO-02 | — | AST matrix contract satisfied by the new module | gate | `uv run pytest tests/unit/test_asyncio_trio_matrix.py -x` | ✅ exists | ⬜ pending |
| 06-T3 | 49-06 | 3 | RESULT-01, RESULT-02 | T-49-08 | Async returns and guard messages | unit + DuckDB-live | `uv run pytest tests/unit/test_async_cursor.py -k "fetch_df or fetch_polars or missing_dependency" -x` | ✅ file exists | ⬜ pending |
| 07-T1 | 49-07 | 4 | DTO-06 | T-49-01, T-49-09 | `validate=True` never presented as the safe mode for money; example survives leaving DuckDB | docs gate | `just docs-build` | ✅ | ⬜ pending |
| 07-T2 | 49-07 | 4 | DTO-05, DTO-06 | — | Every documented install command names a real extra | docs gate | `just docs-build` | ✅ | ⬜ pending |
| 07-T3 | 49-07 | 4 | DTO-06 | T-49-05 | Explanation links out rather than instructing; no real warehouse output | docs gate | `just docs-build` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_dto_duckdb.py` — **owned by 49-01 Task 3 (wave 1)**. Live DuckDB end-to-end, decimal `isinstance` proof (mirrors `test_type_fidelity_duckdb.py`); also hosts the `_require` two-branch test
- [ ] `tests/unit/test_dto.py` — **owned by 49-02 Tasks 2 and 3 (wave 2)**. DTO-02/03/04 pre-check and streaming behaviour, on fakes rather than a warehouse
- [ ] `tests/unit/test_dto_packaging.py` — **owned by 49-04 Task 1 (wave 2)**. DTO-05 extras contract + child-interpreter import check (copy `tests/unit/test_async_packaging.py`); parametrised over `arrowmodel` and `polars` only, because `pandas` and `pyarrow` were measured already present in `sys.modules` after `import semolina`
- [ ] new tests in `tests/unit/test_cursor.py` — **owned by 49-05 Task 2 (wave 3)**. RESULT-01/02 and the guards
- [ ] `tests/unit/test_dto_async.py` — **owned by 49-06 Task 3 (wave 3)**. DTO-02 async twin; **must satisfy `tests/unit/test_asyncio_trio_matrix.py`**, which selects modules by content via an AST walk
- [ ] new tests in `tests/unit/test_async_cursor.py` — **owned by 49-06 Task 3 (wave 3)**. Async RESULT-01/02
- [ ] `.github/workflows/ci.yml` `packaging-smoke` — **owned by 49-04 Task 2 (wave 2)**. Extend the base-install assertion; measure each absence claim in a real clean venv before writing it
- [ ] **Dependency prerequisite, not a test file:** `polars` and `arrowmodel` are absent from `.venv`. The `pyproject.toml` + `uv.lock` + `uv sync` task is **49-01 Task 2, wave 1** — a hard wave-ordering constraint, because D-16 (49-03) cannot produce a real row before it.
- [ ] **Pre-existing gate that would otherwise go red, not a new file:** `tests/unit/test_scope_fence.py` fails on any diff naming `cursor.py` / `acursor.py`. **49-01 Task 3 (wave 1)** narrows it to a value-path content fence per PD-06. Every later plan asserts it still passes without a skip.

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
