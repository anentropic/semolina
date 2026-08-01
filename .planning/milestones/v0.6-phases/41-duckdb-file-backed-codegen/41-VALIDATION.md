---
phase: 41
slug: duckdb-file-backed-codegen
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-15
---

# Phase 41 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + syrupy 5.1+ (snapshot) |
| **Config file** | `pyproject.toml` ([tool.pytest.ini_options]) |
| **Quick run command** | `uv run pytest tests/unit/test_duckdb_engine.py tests/unit/codegen/test_cli.py -x` |
| **Full suite command** | `just test` |
| **Estimated runtime** | ~30 seconds quick / ~3 minutes full |

---

## Sampling Rate

- **After every task commit:** Run quick command (subset relevant to task)
- **After every plan wave:** Run `just test`
- **Before `/gsd-verify-work`:** Full suite must be green + `prek run --all-files` clean
- **Max feedback latency:** 30 seconds for quick path

---

## Per-Task Verification Map

> Populated by planner — see PLAN.md frontmatter and `<acceptance_criteria>` blocks. The table below is the target shape; planner fills the rows.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 41-01-01 | 01 | 0 | DKGEN-04 | — | N/A | unit (fixture) | `uv run pytest tests/conftest.py --collect-only` | ❌ W0 | ⬜ pending |
| 41-01-02 | 01 | 1 | DKGEN-04 | — | Path expansion handles `~`, relative, absolute; skips `:memory:`; covers env-var path | unit | `uv run pytest tests/unit/codegen/test_cli.py -k path` | ❌ W0 | ⬜ pending |
| 41-01-03 | 01 | 1 | DKGEN-04 | — | INSTALL+LOAD runs on native non-ADBC conn | unit | `uv run pytest tests/unit/test_duckdb_engine.py -k extension` | ✅ | ⬜ pending |
| 41-01-04 | 01 | 1 | DKGEN-04 | — | `[duckdb]` extra installs in clean env | CI smoke | `.github/workflows/ci.yml` job `packaging-smoke` | ❌ W0 | ⬜ pending |
| 41-01-05 | 01 | 2 | DKGEN-04 | — | E2E codegen against fixture `.db` matches syrupy snapshot | integration | `uv run pytest tests/unit/codegen/test_codegen_e2e.py` | ❌ W0 | ⬜ pending |
| 41-01-06 | 01 | 2 | DKGEN-04 | — | How-to amended; docs build clean | docs | `just docs-build` | ✅ | ⬜ pending |
| 41-01-07 | 01 | 2 | DKGEN-04 | — | REQUIREMENTS.md traceability updated | manual | grep DKGEN-04 in REQUIREMENTS.md | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — session-scoped fixture that generates a DuckDB `.db` file with a small semantic view, mirroring the existing `_setup_sales_data` DDL pattern (`tests/conftest.py:118-160`). Uses `tmp_path_factory.mktemp` for xdist safety.
- [ ] `tests/unit/codegen/test_cli.py` — test stubs for path expansion (relative / absolute / `~` / `:memory:` passthrough / env-var route). Create file if it doesn't already exist.
- [ ] `tests/unit/codegen/test_codegen_e2e.py` — E2E codegen test stub against the fixture, syrupy snapshot.
- [ ] Loosen existing test `tests/unit/test_duckdb_engine.py::test_introspect_loads_semantic_views_extension_before_describe` at line 514 — current `executed_sqls[0] == "LOAD semantic_views"` assertion will break once INSTALL precedes LOAD.

*Existing framework (pytest + syrupy) covers all phase needs — no new dev dependency required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| First-run network access to `community.duckdb.org` for INSTALL | DKGEN-04 | First-run only; cached after; covered by CI when extension cache is cold | After clearing `~/.duckdb/extensions/`, run `uv run semolina codegen --backend duckdb --database <fixture.db>` and confirm INSTALL succeeds |
| REQUIREMENTS.md DKGEN-04 wording amendment | DKGEN-04 | Wording conflict: line 22 says "fixture `.db` committed" — needs amending to reflect fixture-generation strategy | Verify REQUIREMENTS.md DKGEN-04 row mentions fixture generation rather than committed blob; verify traceability table now lists the phase as Complete |

---

## Validation Sign-Off

- [ ] All tasks have `<acceptance_criteria>` verifiable by grep / test command / CLI output
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all `❌ W0` references in Per-Task Verification Map
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s for quick path
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
