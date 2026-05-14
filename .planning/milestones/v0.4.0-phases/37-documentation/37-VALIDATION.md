---
phase: 37
slug: documentation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-27
---

# Phase 37 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Sphinx (docs build) + pytest (unit tests) |
| **Config file** | `docs/src/conf.py` |
| **Quick run command** | `just docs-build` |
| **Full suite command** | `just docs-build && just test` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `just docs-build`
- **After every plan wave:** Run `just docs-build && just test`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 37-01-01 | 01 | 1 | DOCS-01 | — | N/A | build | `just docs-build` | ❌ W0 | ⬜ pending |
| 37-01-02 | 01 | 1 | DOCS-01 | — | N/A | build | `just docs-build` | ❌ W0 | ⬜ pending |
| 37-02-01 | 02 | 1 | DOCS-02 | — | N/A | build | `just docs-build` | ❌ W0 | ⬜ pending |
| 37-02-02 | 02 | 1 | DOCS-02 | — | N/A | build | `just docs-build` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `docs/src/how-to/arrow-output.rst` — new file for DOCS-01
- [ ] `docs/src/how-to/backends/duckdb.rst` — new file for DOCS-02

*Existing infrastructure (Sphinx + shibuya theme + sphinx-design) covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| New pages appear in navigation | DOCS-01, DOCS-02 | Requires visual browser check | Run `just docs-build`, open `docs/build/html/index.html`, verify pages in nav |
| `.semolina.toml` examples are accurate | DOCS-02 | Configuration correctness | Compare TOML examples against `DuckDBConfig`, `SnowflakeConfig`, `DatabricksConfig` source |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
