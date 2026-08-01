---
phase: 40
slug: streaming-how-to-guide
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-14
---

# Phase 40 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Sphinx strict build (`-W` warnings-as-errors) + semolina-docs-author skill checklist (Diataxis + humanizer) |
| **Config file** | `docs/src/conf.py` (already configured) |
| **Quick run command** | `uv run sphinx-build -W docs/src docs/_build` |
| **Full suite command** | `just docs-build` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run sphinx-build -W docs/src docs/_build`
- **After every plan wave:** Run `just docs-build` + manual humanizer review (per `.claude/skills/semolina-docs-author/SKILL.md` Step 3)
- **Before `/gsd-verify-work`:** Sphinx -W clean + humanizer pass applied + REQUIREMENTS.md traceability flipped + `prek run --all-files` clean
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Filled in by the planner. Each task in `40-NN-PLAN.md` MUST have a row here.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 40-01-01 | 01 | 1 | STREAM-03 | — | N/A (docs-only) | structural | `test -f docs/src/how-to/streaming.rst && grep -q "^.. _howto-streaming:" docs/src/how-to/streaming.rst` | ❌ W0 | ⬜ pending |
| 40-01-02 | 01 | 1 | STREAM-03 (SC-1) | — | N/A | structural | `grep -q "fetch_record_batch" docs/src/how-to/streaming.rst && grep -q "code-block:: python" docs/src/how-to/streaming.rst` | ❌ W0 | ⬜ pending |
| 40-01-03 | 01 | 1 | STREAM-03 (SC-1) | — | N/A | structural | `grep -qE "for [a-z_]+ in cursor" docs/src/how-to/streaming.rst` | ❌ W0 | ⬜ pending |
| 40-01-04 | 01 | 1 | STREAM-03 (SC-2) | — | N/A | structural | `grep -qE "(\.\. tip::\|\.\. note::)" docs/src/how-to/streaming.rst && grep -q "fetch_arrow_table" docs/src/how-to/streaming.rst` | ❌ W0 | ⬜ pending |
| 40-01-05 | 01 | 1 | STREAM-03 (SC-3) | — | N/A | structural | `grep -q "^Backend notes$" docs/src/how-to/streaming.rst && grep -qiE "(drain\|exhaust\|empty)" docs/src/how-to/streaming.rst && grep -qE "batch siz" docs/src/how-to/streaming.rst` | ❌ W0 | ⬜ pending |
| 40-01-06 | 01 | 1 | STREAM-03 (SC-1) | — | N/A | structural | `grep -q "^   streaming$" docs/src/how-to/index.rst` | ❌ W0 | ⬜ pending |
| 40-01-07 | 01 | 2 | STREAM-03 (SC-4) | — | N/A | build | `uv run sphinx-build -W docs/src docs/_build` | exists | ⬜ pending |
| 40-01-08 | 01 | 2 | STREAM-03 (SC-4) | — | N/A | doc (humanizer grep) | `for term in "powerful" "seamlessly" "leverage" "delve" "ensure that" "it's worth noting" "robust" "comprehensive"; do ! grep -iq "$term" docs/src/how-to/streaming.rst \|\| exit 1; done` | ❌ W0 | ⬜ pending |
| 40-01-09 | 01 | 2 | STREAM-03 (SC-5) | — | N/A | doc | `grep -qE "STREAM-03\s*\\\|\s*Phase 40\s*\\\|\s*Complete" .planning/REQUIREMENTS.md` | exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `docs/src/how-to/streaming.rst` — new page with anchor, sections, runnable snippets, decision rule, backend notes, See also
- [ ] `docs/src/how-to/index.rst` — add `streaming` entry to toctree
- [ ] `.planning/REQUIREMENTS.md` — flip STREAM-03 Pending → Complete + footer timestamp on close

*No framework install needed — `docs` dep group already provides Sphinx + shibuya + sphinx-design + sphinx-autoapi.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Diataxis how-to classification (goal-oriented, illustrative, reader supplies setup) | STREAM-03 (SC-4) | Classification is a judgment call about page voice/intent — grep cannot detect tutorial-drift | Apply `.claude/skills/semolina-docs-author/SKILL.md` Step 1 checklist before commit |
| Humanizer pass — full review beyond term grep | STREAM-03 (SC-4) | Grep catches only the worst offenders; em-dash overuse, rule-of-three, vague attributions need reading | Apply `.claude/skills/humanizer/SKILL.md` after first draft |
| Decision rule covers all 3 axes (memory, latency, downstream consumer pattern) | STREAM-03 (SC-2) | Grep can confirm `.. tip::` exists but cannot confirm all 3 axes are addressed substantively | Read the admonition; confirm explicit mention of all three tradeoff axes |
| Backend notes cover Phase 39 findings (shared state, drained reader, empty batches, batch sizes, cursor lifetime) | STREAM-03 (SC-3) | Grep checks individual terms; cannot confirm topic coverage is faithful to Phase 39 RESEARCH.md §Common Pitfalls | Compare Backend notes section against Phase 39's pitfall list |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
