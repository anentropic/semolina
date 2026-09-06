# Phase 43: Cross-Phase UAT Audit — Context

**Gathered:** 2026-06-09
**Status:** Ready for planning
**Source:** Captured from `/gsd-discuss-phase 43 --assumptions` discussion (assumptions surfaced, one direction decision locked)

<domain>
## Phase Boundary

A structured cross-phase audit that confirms the v0.5 milestone (Phases 39–42)
ships as designed, **before** `/gsd-complete-milestone` archives it. The
deliverable is an audit report plus whatever traceability/wording corrections the
audit surfaces — **no production code ships in this phase.**

**Clarified during discussion (important — the phase was confusing as written):**

- This is **NOT catch-up for neglected UAT runs.** Every v0.5 phase was already
  verified at close: `39-`, `40-`, `41-`, `42-VERIFICATION.md` all exist. There
  is no backlog of un-run tests and **zero outstanding UAT-queue items** (no
  `*-UAT.md` / `*-HUMAN-UAT.md` files anywhere).
- Because the UAT queue is empty, running `/gsd-audit-uat` literally (per the
  AUDIT-01 wording) would return "All Clear" trivially and prove nothing. **The
  user explicitly chose to make this a *real* milestone-style SC audit**, not a
  queue sweep. The substance mirrors `/gsd-audit-milestone` (SC/intent-oriented),
  even though AUDIT-01 names `/gsd-audit-uat`.
- Historically (v0.2/v0.3/v0.4.0) this audit was produced *at archive time* by
  `/gsd-complete-milestone` → `vX-MILESTONE-AUDIT.md`, never as a standalone
  phase. Phase 43 is the first time it's carved out as tracked phase work — a
  deliberate reaction to the v0.4.0 retrospective (see decisions).

Out of scope: new features; fixing *functional* product bugs silently (those
become deferred gaps or their own follow-up plans, never quiet edits here); the
actual milestone archival (`/gsd-complete-milestone` is the **next** step, not
this phase).

</domain>

<decisions>
## Implementation Decisions

### This is a real SC audit, not a UAT-queue sweep (LOCKED — user decision)
- Re-verify each v0.5 **success criterion** for Phases 39–42 against the
  *observably shipped surface* — actual API names, actual CLI behaviour, actual
  docs — not just "VERIFICATION.md says passed." The existing four
  VERIFICATION.md files are the recorded trail to **confirm against**, not to
  take on faith (SC2).
- Produce a verdict (`PASSED` / `gaps_found`). `PASSED` is the gate that unblocks
  `/gsd-complete-milestone` (SC5).
- User chose this branch over (a) folding into milestone-completion and dropping
  the phase, and (b) doing the literal trivial `audit-uat` sweep.

### Bake in the two v0.4.0 retrospective lessons (LOCKED)
The v0.4.0 milestone audit caught two hygiene failures *late*; SC4 exists to stop
v0.5 repeating them. Both are explicit audit targets:

1. **Requirement text vs. shipped API names.** v0.4.0 shipped
   `fetch_arrow_table()` while ROADMAP SC text said `to_arrow()`. For v0.5,
   verify every requirement's named API actually exists under that name in the
   shipped code. Concrete checks surfaced during discussion:
   - STREAM-01 claims `cursor.fetch_record_batch()` returns a
     `pyarrow.RecordBatchReader` — confirm the method is shipped under exactly
     that name on `SemolinaCursor`.
   - STREAM-03 / DKGEN-05 reference `fetch_arrow_table()` and the per-backend
     metadata queries — confirm names match reality.
2. **Stale / inconsistent traceability.** v0.4.0's table sat at `Pending` for
   everything despite all of it shipping. For v0.5, the table must be fully
   populated and internally consistent. **A concrete inconsistency already
   exists and MUST be reconciled:** in `REQUIREMENTS.md`, STREAM-01 and STREAM-02
   are unchecked (`- [ ]`) in the requirements list but their Traceability rows
   say `Complete` (Phase 39). The audit decides the true state (Phase 39 is
   marked Complete in ROADMAP, so the checkboxes are almost certainly the stale
   side) and makes list + table agree.
- On a clean audit, flip **AUDIT-01** itself to `[x]` / `Complete`.

### Output artifact (LOCKED intent, naming is Claude's discretion)
- Write a hand-authored audit report with YAML frontmatter and a `status:` /
  verdict field, modelled on `.planning/milestones/v0.4.0-MILESTONE-AUDIT.md`
  (frontmatter shape: `milestone`, `audited`, `status`, `scores`, `gaps`).
- SC1 names `.planning/milestones/v0.5-UAT-AUDIT.md`; the established prior
  pattern is `v0.5-MILESTONE-AUDIT.md`. Planner picks one and is consistent —
  prefer whichever keeps `/gsd-complete-milestone` happy downstream (verify which
  filename that command expects before committing to a name).

### Gap handling (LOCKED — from SC3)
- Any gap the audit surfaces is **either** closed by a follow-up plan *within*
  Phase 43, **or** explicitly deferred to v0.6 with a note added to
  `REQUIREMENTS.md` Future Requirements. No gap is left silently open.
- Distinguish *documentation/traceability* gaps (fix in-phase — that's the
  point) from *functional* gaps (likely defer to v0.6 unless trivial).

### Claude's Discretion
- Exact report filename (`v0.5-UAT-AUDIT.md` vs `v0.5-MILESTONE-AUDIT.md`) —
  resolve against what `/gsd-complete-milestone` reads.
- Whether to invoke the `/gsd-audit-uat` tool at all as a *baseline input* (it's
  cheap and documents the empty queue) vs. going straight to the manual SC walk.
  Reasonable to run it once for completeness and note "0 outstanding items" in
  the report, then do the real SC audit by hand.
- How deep to re-test live behaviour vs. trust VERIFICATION.md where the SC is
  purely internal (e.g. a passing snapshot test) — apply judgement, spend the
  effort on the user-observable surface (API names, CLI, docs).
- Whether the STREAM-01/02 checkbox reconciliation is its own tiny commit or
  folded into the traceability-population task.

</decisions>

<specifics>
## Specific Ideas

- The audit should read like the prior `vX-MILESTONE-AUDIT.md` files: a
  per-phase PASSED/gaps line with must-haves scored, a per-requirement
  traceability confirmation, an explicit notes/lessons section, and a final
  verdict.
- Concrete v0.5 success criteria to walk (from ROADMAP Phases 39–42):
  - **39 (Streaming Arrow):** `fetch_record_batch()` → `RecordBatchReader`
    passthrough; lazy `for row in cursor:` without full materialisation.
  - **40 (Streaming How-To):** the how-to guide exists and covers stream vs.
    `fetch_arrow_table()`.
  - **41 (DuckDB file-backed codegen):** `semolina codegen --backend duckdb
    --database <path>` works against a `.db` file (rel/`~`/abs, read-only).
  - **42 (Field-type inference):** per-role `Metric`/`Dimension`/`Fact` emission
    across all three backends + strict raise on unrecognized role.
- The user's framing: this phase is *insurance against shipping v0.5 with the
  same doc/traceability drift v0.4.0 nearly did* — treat the v0.4.0 audit's
  "Notes for Future Milestones" as the checklist of what not to repeat.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Audit scope & contract
- `.planning/ROADMAP.md` — Phase 43 section is the authoritative scope/success-
  criteria contract; Phases 39–42 sections hold the per-phase success criteria
  this audit must verify.
- `.planning/REQUIREMENTS.md` — v0.5 requirements (STREAM-01/02/03, DKGEN-04/05,
  AUDIT-01) + Traceability table. **Contains the STREAM-01/02 checkbox-vs-table
  inconsistency to reconcile; AUDIT-01 to flip on clean audit.**

### Recorded verification trail (confirm against reality — do NOT take on faith)
- `.planning/phases/39-streaming-arrow-output/39-VERIFICATION.md`
- `.planning/phases/40-streaming-how-to-guide/40-VERIFICATION.md`
- `.planning/phases/41-duckdb-file-backed-codegen/41-VERIFICATION.md`
- `.planning/phases/42-codegen-field-type-inference/42-VERIFICATION.md`

### Report format precedent (model the new report on these)
- `.planning/milestones/v0.4.0-MILESTONE-AUDIT.md` — closest precedent;
  frontmatter shape, per-phase scoring, "Notes for Future Milestones" (the source
  of the two lessons SC4 encodes).
- `.planning/milestones/v0.3-MILESTONE-AUDIT.md`,
  `.planning/milestones/v0.2-MILESTONE-AUDIT.md` — additional format references.

### Tooling
- `~/.claude/get-shit-done/workflows/audit-uat.md` — the literal AUDIT-01 tool
  (UAT-queue sweep; expected to report "All Clear" here).
- `~/.claude/get-shit-done/workflows/audit-milestone.md` — the workflow whose
  *substance* this phase actually performs (SC/intent audit).
- `gsd-sdk query audit-uat --raw` — structured baseline input.

### Shipped surface to verify API names against (v0.4.0 lesson #1)
- `src/semolina/cursor.py` — `SemolinaCursor`: confirm `fetch_record_batch()`,
  `fetch_arrow_table()`, and row iteration are shipped under the names the
  requirements claim.
- `src/semolina/codegen/` + `src/semolina/engines/` — codegen CLI surface and
  per-backend metadata queries named in DKGEN-04/05.
- `docs/src/how-to/` — streaming guide (STREAM-03) and codegen how-to (DKGEN-05)
  exist and describe the real API.

### Project Standards
- `CLAUDE.md` — `prek run --all-files`, `just test`, `just docs-build`; doc edits
  apply `.claude/skills/semolina-docs-author/SKILL.md`. (Most Phase 43 work is
  audit + `.planning`/REQUIREMENTS edits, but any docs touch-up follows this.)

</canonical_refs>

<deferred>
## Deferred Ideas

- Any *functional* gap the audit uncovers in 39–42 → defer to v0.6 with a
  `REQUIREMENTS.md` Future Requirements note (per SC3), unless trivial enough to
  fix in-phase.
- The Phase 42 code-review info items (IN-01/02/03) were left out of scope at
  fix time; if the audit deems them worth tracking, they belong in a backlog/v0.6
  note, not this audit's gap list.

</deferred>

---

*Phase: 43-cross-phase-uat-audit*
*Context gathered: 2026-06-09 via /gsd-discuss-phase --assumptions*
