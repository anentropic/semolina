---
phase: 48
slug: type-map-implementation-databricks-literals
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-12
---

# Phase 48 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded by plan-phase from `48-RESEARCH.md` § "Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`>=8.0.0`, `dev` group), uv-managed; `pytest-adbc-replay` for Snowflake/Databricks cassette replay; `syrupy` for snapshots |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests", "src"]`, `addopts = ["-v", "--doctest-modules", "--doctest-continue-on-failure"]`. The jaffle-shop suite has its own `semolina-jaffle-shop/pyproject.toml` |
| **Quick run command** | `uv run pytest tests/unit/codegen tests/unit/test_sql.py -x` |
| **Full suite command** | `just test` (root `uv run pytest` **plus** the jaffle-shop suite) |
| **Snapshot file** | `tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr` (sole `.ambr`) |
| **Cassette config** | `adbc_cassette_dir = "tests/integration/cassettes"`, `adbc_record_mode = "none"` |
| **Estimated runtime** | ~20 seconds full suite (~17s root + ~1s jaffle-shop) |

**Doctest warning:** `--doctest-modules` runs over `testpaths = ["tests", "src"]`, so every
`Example:` block in a new `src/semolina/codegen/arrow_map.py` or `src/semolina/codegen/probe.py`
docstring is **executed**. Keep them runnable and correct, or make them non-executing prose.

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/unit/codegen tests/unit/test_sql.py -x`
- **After every plan wave:** `just test` + `prek run --all-files`
- **Before `/gsd-verify-work`:** `just test` green, `prek run --all-files` clean,
  `just docs-build` clean under `-W`, and `uv run python tests/type_fidelity_probe.py --check`
  exiting 0
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

*Seeded as draft by plan-phase — the requirement-level map below is the contract; the executor
fills one row per task from the generated PLAN.md files as each lands.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| *(executor fills per task)* | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Requirement → test contract (seeded from RESEARCH.md)

| Req | Behavior | Test type | Automated command | File exists? |
|---|---|---|---|---|
| TYPE-03 | All three mappers return `"decimal.Decimal"` for an equivalent decimal column | unit | `uv run pytest tests/unit/codegen/test_type_map.py -x` | ✅ exists (161 pass) |
| TYPE-03 | End-to-end codegen emits the same annotation on all three backends | snapshot | `uv run pytest tests/unit/codegen/test_codegen_e2e.py -x` | ✅ exists (4 pass, 3 snapshots) |
| TYPE-04 | A metric renders `Metric[T \| None]`; a dimension does not | unit | `uv run pytest tests/unit/codegen/test_python_renderer.py -x` | ✅ exists (55 pass) |
| TYPE-04 | A nullable datetime metric still emits `import datetime` (pitfall 1 guard) | unit | `uv run pytest tests/unit/codegen/test_python_renderer.py -k import -x` | ✅ exists (14 pass) |
| TYPE-05 | Each measured DuckDB gap maps to the measured Python type (D-03) | unit (parametrised) | `uv run pytest tests/unit/codegen/test_type_map.py -k duckdb -x` | ✅ exists (76 pass) |
| TYPE-05 | Databricks `interval` stays unmapped and still emits a `TODO:` — **corrected 48-06**, see note 1 | unit | `uv run pytest tests/unit/codegen/test_type_map.py -k interval -x` | ✅ exists (6 pass) |
| TYPE-05 | `HUGEINT` maps to `decimal.Decimal` (D-05) | unit | `uv run pytest tests/unit/codegen/test_type_map.py -k hugeint -x` | ✅ exists (2 pass) |
| TYPE-06 | VARIANT maps to the `JsonValue` union; `semolina.JsonValue` is importable and in `__all__` | unit | `uv run pytest tests/unit/codegen/test_type_map.py -k variant tests/unit/test_public_surface.py -x` — **corrected 48-06**, see note 2 | ✅ exists (2 + 4 pass) |
| TYPE-07 | `arrow_type_to_python` covers every Arrow type the three backends produce | unit | `uv run pytest tests/unit/codegen/test_arrow_map.py -x` | ✅ exists (62 pass) |
| TYPE-07 | `--check` exits 0 on a matching model and non-zero on a drifted one, over live DuckDB, **fetching no rows** | integration (live DuckDB via CliRunner) | `uv run pytest tests/unit/codegen/test_cli.py -k check -x` | ✅ exists (10 pass) |
| TYPE-07 | `--check` reports which route produced the schema (`execute-schema` / `zero-row` / `metadata`) | unit | `uv run pytest tests/unit/codegen/test_cli.py -k 'check and route' -x` | ✅ exists (1 pass) |
| TYPE-07 | `semolina.codegen.probe` does not import `semolina.codegen.type_map` (Phase 47 defence 3, preserved at the promoted location) | unit (AST) | `uv run pytest 'tests/unit/test_type_fidelity_table.py::test_promoted_probe_does_not_import_the_type_map' -x` — **corrected 48-06**, see note 3 | ✅ exists (1 pass) |
| DBX-04 | `render_literal` renders `date`, naive `datetime`, aware `datetime`, `Decimal` | unit | `uv run pytest tests/unit/test_sql.py -k RenderLiteralDatabricks -x` | ✅ exists (20 pass; the two negative guards were re-pointed at `set`, not deleted) |
| DBX-04 | A `.where()` on a date produces inlined SQL with `DATE '...'` and empty params | unit | `uv run pytest tests/unit/test_sql.py -k DatabricksLiteralInlining -x` | ✅ exists (6 pass) |
| DBX-04 | Non-finite `Decimal` raises `ValueError`, not `NotImplementedError` | unit | `uv run pytest tests/unit/test_sql.py -k non_finite -x` | ✅ exists (4 pass) |
| all | Phase 47's artifact regenerates byte-identically after the map change (D-10) | unit | `uv run pytest tests/unit/test_type_fidelity_table.py -x` | ✅ exists (9 pass) |
| all | The circularity canary still produces a real mismatch on a still-unmapped type (D-10) | unit | `uv run pytest tests/unit/test_type_fidelity_duckdb.py -x` | ✅ exists (16 pass; re-pointed at `VARCHAR[]` with a positive decimal twin, not deleted) |
| fence | `cursor.py` / `acursor.py` / `results.py` untouched (scope fence) | unit (git gate) | `SEMOLINA_SCOPE_FENCE_BASE=9f3c8b9 uv run pytest tests/unit/test_scope_fence.py -x` — **corrected 48-06**, see note 4 | ✅ exists (1 pass, 0 skipped) |

Every row above was executed at the 48-06 phase gate on 2026-08-12 and reported the count shown.

#### Corrections made at the phase gate (48-06)

Four rows were seeded from `48-RESEARCH.md` before the code existed and named something that
reality then contradicted. Each is corrected above rather than quietly dropped.

1. **Databricks `interval`.** The seeded behaviour — "resolves from `start_unit`/`end_unit`" — is
   not what shipped. 48-02 wrote that branch and 48-03 **reverted** it: nothing in this repo has a
   Databricks interval column, so the `datetime.timedelta` answer was a guess sitting among
   measured rows. The branch and its two frozensets were deleted, and `TestDatabricksIntervalType`
   was re-pointed to assert the refusal. TYPE-05 is therefore **partial**, by decision and with
   evidence: broken window 7 plus
   `.planning/todos/pending/2026-08-12-record-databricks-interval-column.md`.
2. **`tests/unit/test_models.py`** exists but holds no `JsonValue` test — 48-03 put the public-surface
   assertions in `tests/unit/test_public_surface.py`. As seeded, `-k variant` also applied to the
   second path and silently deselected all four of its tests, so the row passed while checking
   none of what it named.
3. **`tests/unit/codegen/test_probe.py` does not exist**, and neither does a test matching
   `-k circular`. 48-04 landed the AST guard in `tests/unit/test_type_fidelity_table.py`, which was
   already the circularity-guard home. As seeded the command collected 0 tests and exited on
   "9 deselected", which pytest does not treat as a failure. First flagged in 48-04's summary.
4. **The fence row's shell one-liner** is superseded by `tests/unit/test_scope_fence.py` (48-01).
   `SEMOLINA_SCOPE_FENCE_BASE` must be set explicitly at the gate: the test **skips** rather than
   fails when it cannot resolve a base ref, and a skipped fence is not a passing fence.

---

## Wave 0 Requirements

- [x] `tests/unit/codegen/test_arrow_map.py` — covers TYPE-07's Arrow→Python mapper (62 tests, 48-04)
- [x] `tests/unit/codegen/test_cli.py` — new `--check` cases (10 tests, 48-05)
- [x] `tests/unit/codegen/test_python_renderer.py` — the `import datetime` emission guard for
      TYPE-04 (pitfall 1: `needs_datetime` is an exact string membership test, so `| None`
      applied upstream silently drops the import and generated models raise `NameError`)
- [x] `tests/unit/test_sql.py` — positive `date`/`datetime`/`Decimal` cases added **before** the
      two existing negative assertions (which assert `render_literal` *raises*) are inverted
- [x] a test asserting `semolina.codegen.probe` does not import `semolina.codegen.type_map`
      — `test_promoted_probe_does_not_import_the_type_map` (AST walk, 48-04)
- [x] the `cursor.py` / `acursor.py` / `results.py` untouched gate — landed as
      `tests/unit/test_scope_fence.py` (48-01), not a shell one-liner
- [x] Framework install: **none** — existing pytest + `pytest-adbc-replay` + `syrupy`
      infrastructure covers this phase

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `--check` against a live Databricks metric view | TYPE-07 | Databricks has no `adbc_execute_schema`, and nobody has confirmed its metric-view planner accepts the `SELECT * FROM (…) WHERE 1=0` wrapper. Broken window 2 is still open; todo `.planning/todos/pending/2026-08-12-verify-databricks-zero-row-fallback.md` | Run the wrapper once against a live workspace and record the observation. **Per D-09, `--check`'s acceptance criteria are scoped to DuckDB (live) and Snowflake (cassette); Databricks is recorded as evidence-limited.** Do not write an acceptance criterion nobody can run. |
| Databricks `interval` column type object | TYPE-05 | Unmeasured — no fixture, cassette, or recording in the repo has an interval column (`48-RESEARCH.md` A4/A7). The day-time family is assumed to be `timedelta`-describable; the year-month family almost certainly is not | Either record a cassette with an interval column, or ship day-time only and keep `TODO:` for year-month, stating the limit |
| Aware-`datetime` literal accepted by Databricks | DBX-04 | `48-RESEARCH.md` A6 — the docs page gave contradictory readings of the bare `+hh:mm` offset form. D-08 mitigates by normalising to UTC and emitting `Z`, which is unambiguously listed | If the plan departs from D-08 and emits `isoformat()`'s native offset, that needs a `checkpoint:human-verify` on a live Databricks query — it cannot be settled from the repo |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s (full suite 19.6s + 0.6s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** signed off at the 48-06 phase gate, 2026-08-12.

`nyquist_compliant: true` records that every requirement row has an executed, green automated
command — not that every requirement is fully delivered. **TYPE-05 remains partial**: its
Databricks-interval half is unmapped by decision, and the row above tests the refusal rather than
a mapping (correction 1, broken window 7). TYPE-07's `--check` is green on DuckDB live and on the
Snowflake comparison core; its Databricks route is unrun by design (D-09, broken windows 2 and 9).
Those limits are recorded in the ledger, not resolved by this sign-off.
