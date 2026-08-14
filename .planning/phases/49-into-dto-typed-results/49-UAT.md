---
status: testing
phase: 49-into-dto-typed-results
source: [49-VERIFICATION.md]
started: 2026-08-14T09:30:00Z
updated: 2026-08-14T09:30:00Z
---

## Current Test

number: 1
name: Read the typed-results how-to end to end for voice, audience fit and Diataxis quality
expected: |
  Reads as a how-to for a data/analytics engineer building a BI backend, per
  .claude/skills/semolina-docs-author/SKILL.md; no instructional content leaked into the
  linked explanation page and vice versa.
awaiting: user response

## Tests

### 1. Docs voice and Diataxis fit

file: `docs/src/how-to/typed-results.rst`
expected: Reads as a how-to for a data/analytics engineer building a BI backend, per
  `.claude/skills/semolina-docs-author/SKILL.md`. Goal-oriented with illustrative snippets
  (reader supplies setup), not a tutorial. No instructional content leaked into the linked
  explanation page and vice versa.
why_human: Editorial and voice quality cannot be asserted by a command. This is Plan 07's own
  flagged manual verification, and `49-VALIDATION.md`'s Manual-Only Verifications table routes
  D1 and D4 of Plan 07's coverage block here.
result: [pending]

### 2. The `validate=True` framing

files: `docs/src/how-to/typed-results.rst`, `docs/src/explanation/type-fidelity.rst`
expected: No reader can come away believing `validate=True` is the safe mode for a money
  column. Measured in research: a `decimal128(38,2)` column into a `float` field is **silently
  coerced** under `validate=True` — precision lost, no error — so the structural pre-check is
  the only guard on that case, on either path.
why_human: This is the phase's highest-severity threat (T-49-01) and a `must_haves.prohibitions`
  item across four plans. A prohibition on a *framing* cannot be asserted by grep — a page can
  satisfy every literal check and still leave the wrong impression. The verifier confirmed the
  literal sentences exist and read correctly, but that is not a substitute for the designated
  human checkpoint.
result: [pending]

### 3. `packaging-smoke` green in real CI

action: Push `gsd/v0.7-async-typed-results` and confirm the `packaging-smoke` GitHub Actions job
  passes.
expected: All `packaging-smoke` steps pass in the real CI environment, not just in the
  locally-reproduced clean venvs Plan 04 recorded.
why_human: Plan 04's own `<verification>` block lists "the packaging-smoke job is green on the
  pushed branch" as a required gate. The branch has never been pushed (confirmed:
  `origin/gsd/v0.7-async-typed-results` does not exist and no matching Actions run was found).
  Everything the job checks was reproduced locally and printed OK per the SUMMARY, and pushing
  once at `/gsd-ship` rather than per phase is this project's normal workflow — so this is an
  outstanding gate, not a code defect.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
