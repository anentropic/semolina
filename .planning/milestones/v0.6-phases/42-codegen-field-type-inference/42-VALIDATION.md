---
phase: 42
slug: codegen-field-type-inference
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-09
---

# Phase 42 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via `uv run pytest`); syrupy >=5.1.0 for snapshots |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths `["tests", "src"]`, `--doctest-modules`) |
| **Quick run command** | `uv run pytest tests/unit/codegen/ -x` |
| **Full suite command** | `just test` (`uv run pytest` + jaffle-shop `uv run pytest`) |
| **Snapshot update** | `uv run pytest tests/unit/codegen/ --snapshot-update` (syrupy) |
| **Estimated runtime** | ~10 seconds (codegen unit subset); full `just test` longer |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/codegen/ -x`
- **After every plan wave:** Run `just test`
- **Before `/gsd:verify-work`:** `prek run --all-files` + `just test` + `just docs-build` all green
- **Max feedback latency:** ~10 seconds (quick), full suite at wave boundaries

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 42-W0-01 | TBD | 0 | DKGEN-05 (crit 4) | — / — | N/A | unit | `uv run pytest tests/unit/codegen/test_python_renderer.py -x` | ❌ W0 | ⬜ pending |
| 42-W0-02 | TBD | 0 | DKGEN-05 (crit 2) | — / — | N/A | snapshot | `uv run pytest tests/unit/codegen/ -k snowflake -x` | ❌ W0 | ⬜ pending |
| 42-W0-03 | TBD | 0 | DKGEN-05 (crit 3) | — / — | N/A | snapshot | `uv run pytest tests/unit/codegen/ -k databricks -x` | ❌ W0 | ⬜ pending |
| 42-impl | TBD | 1 | DKGEN-05 (crit 4) | — / — | N/A | unit | `uv run pytest tests/unit/codegen/test_python_renderer.py -x` | ✅ | ⬜ pending |
| 42-duck | TBD | 1 | DKGEN-05 (crit 1) | — / — | N/A | snapshot | `uv run pytest tests/unit/codegen/test_codegen_e2e.py -x` | ✅ | ⬜ pending |
| 42-docs | TBD | 2 | DKGEN-05 (crit 5) | — / — | N/A | doc-build | `just docs-build` | ✅ | ⬜ pending |
| 42-close | TBD | 2 | DKGEN-05 (crit 5) | — / — | N/A | doc-inspect | REQUIREMENTS.md DKGEN-05 `[x]` + PROJECT.md Key Decisions row | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs are provisional — the planner assigns real plan/task IDs.*

---

## Wave 0 Requirements

- [ ] `tests/unit/codegen/test_python_renderer.py` — NEW `_field_class_for` raise-path test
      (`pytest.raises(ValueError)` for an unrecognized role) — written BEFORE the impl change
      per the bug-fix-first-test-then-fix discipline. Covers rewritten criterion 4.
- [ ] Snowflake codegen snapshot test + `.ambr` — offline introspect→render with synthetic
      `SHOW COLUMNS IN VIEW` rows (METRIC/DIMENSION/FACT). Covers criterion 2.
- [ ] Databricks codegen snapshot test + `.ambr` — offline introspect→render with synthetic
      `DESCRIBE TABLE EXTENDED ... AS JSON` payload (`is_measure` true/false; no Fact).
      Covers criterion 3.
- Framework already present (pytest + syrupy) — no install needed.
- Synthetic metadata rows: check reuse of fixtures already in
  `tests/unit/test_snowflake_engine.py` / `tests/unit/test_databricks_engine.py` first.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Snowflake/Databricks emission against a REAL warehouse | DKGEN-05 (crit 2,3) | No live warehouse access (trial expired); offline mocked snapshots are the contracted verification | N/A — intentionally covered by offline snapshot fixtures, not live integration |

*All automated-testable phase behaviors have automated verification. The single manual
row above is explicitly out of scope per the locked offline-testing decision.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (3 new tests)
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
