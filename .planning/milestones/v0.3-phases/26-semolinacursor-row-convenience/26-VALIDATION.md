---
phase: 26
slug: semolinacursor-row-convenience
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 26 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run --extra dev pytest tests/unit/test_cursor.py -x` |
| **Full suite command** | `uv run --extra dev pytest` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --extra dev pytest tests/unit/test_cursor.py tests/unit/test_query.py tests/unit/test_pool.py -x`
- **After every plan wave:** Run `uv run --extra dev pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 26-01-01 | 01 | 1 | CURS-01 | unit | `uv run --extra dev pytest tests/unit/test_cursor.py -x` | ❌ W0 | ⬜ pending |
| 26-01-02 | 01 | 1 | CURS-02 | unit | `uv run --extra dev pytest tests/unit/test_cursor.py::TestFetchallRows -x` | ❌ W0 | ⬜ pending |
| 26-01-03 | 01 | 1 | CURS-03 | unit | `uv run --extra dev pytest tests/unit/test_cursor.py::TestFetchmanyRows -x` | ❌ W0 | ⬜ pending |
| 26-01-04 | 01 | 1 | CURS-04 | unit | `uv run --extra dev pytest tests/unit/test_cursor.py::TestFetchoneRow -x` | ❌ W0 | ⬜ pending |
| 26-01-05 | 01 | 1 | CURS-05 | unit | `uv run --extra dev pytest tests/unit/test_results.py -x` | ✅ | ⬜ pending |
| 26-02-01 | 02 | 2 | CURS-01 | unit | `uv run --extra dev pytest tests/unit/test_query.py -x` | ✅ (needs update) | ⬜ pending |
| 26-02-02 | 02 | 2 | - | unit | `uv run --extra dev pytest tests/unit/test_pool.py -x` | ✅ (needs update) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_cursor.py` — new file for CURS-01 through CURS-04
- [ ] MockCursor needs `execute(sql, params)` and `fetchmany()` methods
- [ ] Existing `tests/unit/test_query.py` needs updates for SemolinaCursor return type
- [ ] Existing `tests/unit/test_pool.py` needs updates for SemolinaCursor return type

*Framework install: not needed — pytest already configured*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
