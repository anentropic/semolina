---
phase: 48
slug: type-map-implementation-databricks-literals
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| TYPE-03 | All three mappers return `"decimal.Decimal"` for an equivalent decimal column | unit | `uv run pytest tests/unit/codegen/test_type_map.py -x` | exists — assertions change |
| TYPE-03 | End-to-end codegen emits the same annotation on all three backends | snapshot | `uv run pytest tests/unit/codegen/test_codegen_e2e.py -x` | exists — `.ambr` regenerates |
| TYPE-04 | A metric renders `Metric[T \| None]`; a dimension does not | unit | `uv run pytest tests/unit/codegen/test_python_renderer.py -x` | exists |
| TYPE-04 | A nullable datetime metric still emits `import datetime` (pitfall 1 guard) | unit | `uv run pytest tests/unit/codegen/test_python_renderer.py -k import -x` | ❌ Wave 0 |
| TYPE-05 | Each measured DuckDB gap maps to the measured Python type (D-03) | unit (parametrised) | `uv run pytest tests/unit/codegen/test_type_map.py -k duckdb -x` | exists — new cases |
| TYPE-05 | Databricks `interval` resolves from `start_unit`/`end_unit` | unit | `uv run pytest tests/unit/codegen/test_type_map.py -k interval -x` | ❌ Wave 0 |
| TYPE-05 | `HUGEINT` maps to `decimal.Decimal` (D-05) | unit | `uv run pytest tests/unit/codegen/test_type_map.py -k hugeint -x` | ❌ Wave 0 |
| TYPE-06 | VARIANT maps to the `JsonValue` union; `semolina.JsonValue` is importable and in `__all__` | unit | `uv run pytest tests/unit/codegen/test_type_map.py -k variant tests/unit/test_models.py -x` | ❌ Wave 0 |
| TYPE-07 | `arrow_type_to_python` covers every Arrow type the three backends produce | unit | `uv run pytest tests/unit/codegen/test_arrow_map.py -x` | ❌ Wave 0 |
| TYPE-07 | `--check` exits 0 on a matching model and non-zero on a drifted one, over live DuckDB, **fetching no rows** | integration (live DuckDB via CliRunner) | `uv run pytest tests/unit/codegen/test_cli.py -k check -x` | ❌ Wave 0 |
| TYPE-07 | `--check` reports which route produced the schema (`execute-schema` / `zero-row` / `metadata`) | unit | same module | ❌ Wave 0 |
| TYPE-07 | `semolina.codegen.probe` does not import `semolina.codegen.type_map` (Phase 47 defence 3, preserved at the promoted location) | unit (AST or importlib) | `uv run pytest tests/unit/codegen/test_probe.py -k circular -x` | ❌ Wave 0 |
| DBX-04 | `render_literal` renders `date`, naive `datetime`, aware `datetime`, `Decimal` | unit | `uv run pytest tests/unit/test_sql.py -k RenderLiteralDatabricks -x` | exists — **negative assertions invert** |
| DBX-04 | A `.where()` on a date produces inlined SQL with `DATE '...'` and empty params | unit | `uv run pytest tests/unit/test_sql.py -k DatabricksLiteralInlining -x` | exists |
| DBX-04 | Non-finite `Decimal` raises `ValueError`, not `NotImplementedError` | unit | same | ❌ Wave 0 |
| all | Phase 47's artifact regenerates byte-identically after the map change (D-10) | unit | `uv run pytest tests/unit/test_type_fidelity_table.py -x` | exists — needs `just type-fidelity` first |
| all | The circularity canary still produces a real mismatch on a still-unmapped type (D-10) | unit | `uv run pytest tests/unit/test_type_fidelity_duckdb.py -x` | exists — **must be re-pointed, not deleted** |
| fence | `cursor.py` / `acursor.py` / `results.py` untouched (scope fence) | shell gate | `git diff --name-only <base>..HEAD \| grep -E 'src/semolina/(cursor\|acursor\|results)\.py' && exit 1 \|\| exit 0` | ❌ Wave 0 |

---

## Wave 0 Requirements

- [ ] `tests/unit/codegen/test_arrow_map.py` — covers TYPE-07's Arrow→Python mapper
- [ ] `tests/unit/codegen/test_cli.py` — new `--check` cases (module exists; cases do not)
- [ ] `tests/unit/codegen/test_python_renderer.py` — the `import datetime` emission guard for
      TYPE-04 (pitfall 1: `needs_datetime` is an exact string membership test, so `| None`
      applied upstream silently drops the import and generated models raise `NameError`)
- [ ] `tests/unit/test_sql.py` — positive `date`/`datetime`/`Decimal` cases added **before** the
      two existing negative assertions (which assert `render_literal` *raises*) are inverted
- [ ] a test asserting `semolina.codegen.probe` does not import `semolina.codegen.type_map`
- [ ] the `cursor.py` / `acursor.py` / `results.py` untouched shell gate
- [ ] Framework install: **none** — existing pytest + `pytest-adbc-replay` + `syrupy`
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

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
