---
phase: 38
slug: packaging-fix-test-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-01
---

# Phase 38 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.0.0 |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/unit/test_pool.py tests/unit/test_query.py -x` |
| **Full suite command** | `just test` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_pool.py tests/unit/test_query.py -x`
- **After every plan wave:** Run `just test`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 38-01-01 | 01 | 1 | DUCK-01 | — | N/A | smoke | `uv pip install -e ".[duckdb]" --dry-run` | N/A | ⬜ pending |
| 38-01-02 | 01 | 1 | DUCK-01 | — | N/A | smoke | `uv pip install -e ".[all]" --dry-run` | N/A | ⬜ pending |
| 38-01-03 | 01 | 1 | DUCK-01 | — | N/A | lint | `grep sphinx-autobuild pyproject.toml` | N/A | ⬜ pending |
| 38-01-04 | 01 | 1 | DUCK-01 | — | N/A | unit | `uv run pytest tests/unit/test_pool.py tests/unit/test_query.py -x` | Yes | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. The xfail-marked tests already exist and just need their markers removed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | — |

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
