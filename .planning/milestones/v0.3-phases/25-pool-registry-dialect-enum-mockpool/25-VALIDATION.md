---
phase: 25
slug: pool-registry-dialect-enum-mockpool
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/unit/ -x -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ -x -q`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 25-01-01 | 01 | 1 | CONN-01 | unit | `uv run pytest tests/unit/test_dialect.py -x` | ❌ W0 | ⬜ pending |
| 25-01-02 | 01 | 1 | CONN-01 | unit | `uv run pytest tests/unit/test_registry.py -x` | ✅ (needs new tests) | ⬜ pending |
| 25-01-03 | 01 | 1 | CONN-02 | unit | `uv run pytest tests/unit/test_query.py -x` | ✅ (needs new tests) | ⬜ pending |
| 25-02-01 | 02 | 1 | CONN-03 | unit | `uv run pytest tests/unit/test_sql.py -x` | ✅ (verify dialect dispatch) | ⬜ pending |
| 25-02-02 | 02 | 1 | CONN-04 | unit | `uv run pytest tests/unit/test_pool.py -x` | ❌ W0 | ⬜ pending |
| 25-02-03 | 02 | 1 | CONN-04 | unit | `uv run pytest tests/unit/test_pool.py -x` | ❌ W0 | ⬜ pending |
| 25-02-04 | 02 | 1 | CONN-04 | unit | `uv run pytest tests/unit/test_pool.py -x` | ❌ W0 | ⬜ pending |
| 25-XX-XX | XX | X | - | unit | `uv run pytest tests/unit/test_registry.py -x` | ✅ (must still pass) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_dialect.py` — stubs for CONN-01, CONN-03 (Dialect StrEnum tests)
- [ ] `tests/unit/test_pool.py` — stubs for CONN-04 (MockPool, MockConnection, MockCursor tests)
- [ ] Existing `tests/unit/test_registry.py` needs new tests for pool+dialect registration (CONN-01)
- [ ] Existing `tests/unit/test_query.py` needs new tests for pool-based execution path (CONN-02)

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
