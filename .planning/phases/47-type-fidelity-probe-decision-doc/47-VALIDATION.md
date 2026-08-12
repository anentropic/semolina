---
phase: 47
slug: type-fidelity-probe-decision-doc
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-12
---

# Phase 47 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (uv-managed), plus `pytest-adbc-replay` ≥1.1.1 for Snowflake cassette replay |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`); jaffle-shop suite has its own `semolina-jaffle-shop/pyproject.toml` |
| **Quick run command** | `uv run pytest tests/<probe-test-file> -q` |
| **Full suite command** | `just test` (runs `uv run pytest` then the jaffle-shop suite) |
| **Estimated runtime** | ~30–60 seconds full suite |

---

## Sampling Rate

- **After every task commit:** Run the quick command for the file that task touched
- **After every plan wave:** Run `just test`
- **Before `/gsd-verify-work`:** `just test` green AND `prek run --all-files` clean
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

*Seeded as draft by plan-phase. The executor fills one row per task from the generated PLAN.md files.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 47-01-01 | 01 | 1 | TYPE-01 | T-47-02 | View and field names reach `semantic_view('...')` only through `_sql_str_literal`, which doubles embedded quotes | tracer | `uv run python tests/type_fidelity_probe.py --write && uv run python tests/type_fidelity_probe.py --check` | ✅ | ✅ green |
| 47-01-02 | 01 | 1 | TYPE-01 | — | N/A | unit | `uv run pytest tests/unit/test_type_fidelity_duckdb.py -x -q` | ✅ | ✅ green |
| 47-01-03 | 01 | 1 | TYPE-01 | T-47-01, T-47-03 | `FidelityRow` declares no value-bearing field and the table header carries no sample-value column, so warehouse row data has no path into the committed artifact; a stale artifact cannot ship as Phase 48's specification | unit | `uv run pytest tests/unit/test_type_fidelity_table.py -x -q` | ✅ | ✅ green |
| 47-02-01 | 02 | 2 | TYPE-01 | T-47-01, T-47-03 | The named-disagreements section reports `None` and `0` for the empty group and reduces any other observation to its type name, so a future re-seed against real data cannot leak a value; the drift guard runs unchanged over the widened artifact | integration | `just type-fidelity && uv run python tests/type_fidelity_probe.py --check && uv run pytest tests/unit/test_type_fidelity_table.py -x -q` | ✅ | ✅ green |
| 47-02-02 | 02 | 2 | TYPE-01 | — | N/A | unit | `uv run pytest tests/unit/test_type_fidelity_duckdb.py -x -q` | ✅ | ✅ green |
| 47-02-03 | 02 | 2 | TYPE-01 | T-47-04, T-47-SC | pandas, pydantic, and polars are resolved inside the measuring function and an absent package yields a `not measured` row rather than an install; `pyproject.toml` and `uv.lock` are unchanged by this plan | unit | `uv run pytest tests/unit/test_type_fidelity_duckdb.py -x -q && git diff --exit-code pyproject.toml uv.lock` | ✅ | ✅ green |
| 47-03-01 | 03 | 3 | TYPE-01 | T-47-05, T-47-07, T-47-08 | The copied cassettes were greped for `password`, `token`, `account`, and both vendor hostname suffixes with no matches; `git status --porcelain` on the source recordings is empty, so nothing was re-recorded; `test_databricks_probe`'s docstring states that replay proves result types and proves nothing about driver capability | integration | `uv run pytest tests/integration/test_type_fidelity.py -x -q` | ✅ | ✅ green |
| 47-03-02 | 03 | 3 | TYPE-01 | T-47-08 | The artifact's Snowflake and Databricks numbers are checkable without a warehouse: the replayed schema and a raw `pyarrow.ipc.open_file` read of the same recording are asserted equal field for field | integration | `uv run pytest tests/integration/test_type_fidelity.py -x -q` | ✅ | ✅ green |
| 47-03-03 | 03 | 3 | TYPE-01 | T-47-06, T-47-08 | `FidelityRow` records the type of a value and never the value, so reading `to_pylist()` off real recordings cannot leak row data; the capability table and the comparison table share no column, so no cell carries both a capability claim and a result-type claim | integration | `just type-fidelity && uv run python tests/type_fidelity_probe.py --check && uv run pytest tests/unit/test_type_fidelity_table.py tests/integration/test_type_fidelity.py -x -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Probe test module(s) under `tests/` — stubs for TYPE-01. Landed in plan 47-01 as
  `tests/type_fidelity_probe.py` (driver, not a test module), `tests/unit/test_type_fidelity_duckdb.py`
  (live canary), and `tests/unit/test_type_fidelity_table.py` (drift + circularity guards).
  They are working tests rather than stubs.
- [x] Copied Snowflake cassette directory keyed to the probe's pytest node id (the Phase 46 precedent — cassette paths derive from the node id, so the directory must be copied, not referenced).
  Landed in plan 47-03: `tests/integration/cassettes/integration/test_type_fidelity/test_snowflake_probe/adbc_driver_snowflake.dbapi/`,
  plus its Databricks counterpart under `test_databricks_probe/adbc_driver_manager.dbapi/databricks/`.
  Both were copied from the `test_queries` recordings of `test_metric_with_dimension`; neither
  was re-recorded.

Plan 47-01 covered the DuckDB half only, which is why the cassette item stayed open until the
plan that added `collect_snowflake_rows()`.

*Existing pytest + `pytest-adbc-replay` infrastructure otherwise covers this phase; no framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Databricks zero-row (`WHERE 1=0`) fallback against a real metric view | TYPE-02 | No Databricks cassette exists and `adbc_execute_schema` is not implemented on that driver; nobody has run the fallback against a metric view | Either run once against a live Databricks workspace and record the observation, or record the row as evidence-limited in the decision doc with the gap stated |
| Decision-doc claims are non-circular | TYPE-01, TYPE-02 | Judgement: a reviewer must confirm the evidence came from the warehouse, not from Semolina restating its own type map | Follow the reviewer procedure in RESEARCH.md `## Validation Architecture` — ending in reading a raw `.arrow` file with pyarrow, bypassing every line of Semolina code |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
