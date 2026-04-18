---
phase: 31
slug: fix-mockpool-doc-example
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-18
---

# Phase 31 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Sphinx build (documentation validation) |
| **Config file** | `docs/src/conf.py` |
| **Quick run command** | `uv run sphinx-build -W docs/src docs/_build` |
| **Full suite command** | `uv run sphinx-build -W docs/src docs/_build` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run sphinx-build -W docs/src docs/_build`
- **After every plan wave:** Run `uv run sphinx-build -W docs/src docs/_build`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 31-01-01 | 01 | 1 | DOCS-03 | — | N/A | build | `uv run sphinx-build -W docs/src docs/_build` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Example narrative reads naturally | DOCS-03 | Prose quality | Read "Test conditional filters" section for coherence |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
