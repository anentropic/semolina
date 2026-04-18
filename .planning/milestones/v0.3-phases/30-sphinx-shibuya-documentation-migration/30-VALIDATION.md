---
phase: 30
slug: sphinx-shibuya-documentation-migration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 30 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | sphinx-build (not pytest-based -- validation is the build itself) |
| **Config file** | `docs/src/conf.py` (created in Wave 0 / Plan 30-01) |
| **Quick run command** | `uv run sphinx-build -W docs/src docs/_build` |
| **Full suite command** | `uv run sphinx-build -W docs/src docs/_build` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run sphinx-build -W docs/src docs/_build`
- **After every plan wave:** Full build + manual inspection of rendered output
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 30-01-01 | 01 | 1 | SPHINX-01 | — | N/A | smoke | `uv run sphinx-build -W docs/src docs/_build` | No -- Wave 0 | ⬜ pending |
| 30-02-01 | 02 | 2 | SPHINX-02 | — | N/A | smoke | `uv run sphinx-build -W docs/src docs/_build` | ✅ after 30-01 | ⬜ pending |
| 30-03-01 | 03 | 2 | SPHINX-02 | — | N/A | smoke | `uv run sphinx-build -W docs/src docs/_build` | ✅ after 30-01 | ⬜ pending |
| 30-04-01 | 04 | 3 | SPHINX-03, SPHINX-04 | — | N/A | smoke + manual | `uv run sphinx-build -W docs/src docs/_build` + CI check | ✅ after 30-01 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `docs/src/conf.py` — Sphinx configuration with shibuya theme, autoapi, sphinx-design
- [ ] Sphinx packages installed — `uv sync --group docs` after pyproject.toml update in Plan 30-01
- [ ] No pytest-based tests for docs — validation is the build itself

*Wave 0 is Plan 30-01 (scaffold and configuration).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tab sync works across Snowflake/Databricks groups | SPHINX-02 | Browser JavaScript behavior | Open built site, click Snowflake tab, verify all tab groups switch |
| Dark mode toggle works | SPHINX-01 | Browser visual behavior | Open built site, toggle dark mode, verify theme switches |
| CI deploys correctly | SPHINX-04 | Requires push to branch + GitHub Actions run | Push branch, check Actions run, verify Pages deployment |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
