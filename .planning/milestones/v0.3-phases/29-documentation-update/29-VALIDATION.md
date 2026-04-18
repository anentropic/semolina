---
phase: 29
slug: documentation-update
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 29 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | mkdocs build --strict (docs build validation) + pytest (existing test suite) |
| **Config file** | mkdocs.yml |
| **Quick run command** | `uv run mkdocs build --strict 2>&1 | tail -5` |
| **Full suite command** | `uv run mkdocs build --strict && uv run --extra dev pytest` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run mkdocs build --strict 2>&1 | tail -5`
- **After every plan wave:** Run `uv run mkdocs build --strict && uv run --extra dev pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 29-01-01 | 01 | 1 | DOCS-04 | build | `uv run mkdocs build --strict` | ✅ | ⬜ pending |
| 29-01-02 | 01 | 1 | DOCS-04 | build | `uv run mkdocs build --strict` | ✅ | ⬜ pending |
| 29-02-01 | 02 | 1 | DOCS-01 | build | `uv run mkdocs build --strict` | ✅ | ⬜ pending |
| 29-02-02 | 02 | 1 | DOCS-01 | build+grep | `uv run mkdocs build --strict` | ✅ | ⬜ pending |
| 29-03-01 | 03 | 2 | DOCS-02 | build+grep | `uv run mkdocs build --strict` | ✅ | ⬜ pending |
| 29-03-02 | 03 | 2 | DOCS-02, DOCS-03 | build+grep | `uv run mkdocs build --strict` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. MkDocs Material + mkdocstrings + gen_ref_pages.py already configured.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Code examples are accurate | DOCS-01, DOCS-02, DOCS-03 | Examples show API usage patterns, not runnable tests | Review each code block against v0.3 source API |
| Cross-links resolve correctly | DOCS-01, DOCS-02 | mkdocs --strict catches broken links but not semantic correctness | Spot-check "See also" sections |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
