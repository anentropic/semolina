---
phase: 43
plan: 01
subsystem: planning-audit
tags: [milestone-audit, traceability, v0.5, audit-uat]
requires:
  - "Phases 39-42 shipped surface (cursor.py, cli/codegen.py, engines/, python_renderer.py, docs/src/how-to/)"
  - "39/40/41/42-VERIFICATION.md (recorded trail)"
provides:
  - ".planning/v0.5-MILESTONE-AUDIT.md (PASSED verdict, gates AUDIT-01 close-out)"
affects:
  - "43-02-PLAN.md (consumes the PASSED verdict to reconcile traceability + flip AUDIT-01)"
tech-stack:
  added: []
  patterns:
    - "Evidence-gated milestone audit: every PASSED SC cites a re-verified file:line"
key-files:
  created:
    - ".planning/v0.5-MILESTONE-AUDIT.md"
  modified: []
decisions:
  - "Report named v0.5-MILESTONE-AUDIT.md at .planning/ root (NOT v0.5-UAT-AUDIT.md, NOT under milestones/) so the milestone.complete handler glob finds and archives it"
  - "STREAM-01/02 checkbox-vs-table drift classified as a doc/traceability finding (fix in-phase via Plan 02), not a functional gap — does not block status: passed"
metrics:
  duration: 2min
  completed: 2026-06-09T20:57:04Z
  tasks: 2
  files: 1
---

# Phase 43 Plan 01: v0.5 Cross-Phase Milestone Audit Summary

Ran the empty-UAT-queue baseline and a real SC-by-SC audit of Phases 39-42 against the observably
shipped surface, then wrote `.planning/v0.5-MILESTONE-AUDIT.md` with a reproducible **PASSED**
verdict that gates the AUDIT-01 close-out in Plan 02.

## What Was Done

### Task 1 — Baseline + SC-by-SC verification (read-only audit)

- **UAT baseline:** `gsd-sdk query audit-uat --raw` → `{"results": [], "summary": {"total_items": 0, ...}}`.
  Documented as the AUDIT-01 baseline ("0 outstanding items"); per the locked user decision this is a
  baseline line-item, not the deliverable.
- **Manual SC walk** — every v0.5 named API re-grep-confirmed at its exact cited line in the current tree:
  - STREAM-01: `cursor.py:164` `fetch_record_batch(self) -> pyarrow.RecordBatchReader`
  - STREAM-02: `cursor.py:222` `__iter__` / `:237` `__next__(self) -> Row`
  - STREAM-03: `docs/src/how-to/streaming.rst` exists (17 in-page references to fetch_record_batch/fetch_arrow_table)
  - DKGEN-04: `cli/codegen.py:29` `_normalize_database_path`, wired at `:110`; how-to `codegen.rst` amended
  - DKGEN-05: DuckDB `DESCRIBE SEMANTIC VIEW` (`duckdb.py:202`), Snowflake `SHOW COLUMNS IN VIEW`→`kind` (`snowflake.py:328`/`:336`), Databricks `DESCRIBE TABLE EXTENDED ... AS JSON`→`is_measure` (`databricks.py:330`/`:336-337`), strict `_ROLE_TO_CLASS` (`python_renderer.py:22`/`:66`) with `raise ValueError(...) from None` (`:84`)
- **Lesson #1 (API-name vs requirement-text drift):** CLEAN — all five named APIs match shipped code; the
  v0.4.0 `to_arrow()`-vs-`fetch_arrow_table()` drift does not recur.
- **Lesson #2 (traceability consistency):** one finding — REQUIREMENTS.md STREAM-01 (`:14`) / STREAM-02 (`:15`)
  unchecked `- [ ]` while the table (`:63-64`) says `Complete`. Stale checkboxes. Classified per SC3 as a
  documentation/traceability gap → fixed in-phase by Plan 02. NOT a functional gap.
- **Nyquist:** 4/4 — all of 39/40/41/42 have a VALIDATION.md.

### Task 2 — Write the audit report

- Created `.planning/v0.5-MILESTONE-AUDIT.md` (root, 149 lines), modelled on the v0.4.0 audit frontmatter
  and section structure. Frontmatter: `milestone: v0.5`, `audited`, `status: passed`, `scores` (requirements
  6/6, phases 4/4, integration/flows deferred), empty `gaps`, `tech_debt` (Phase 42 IN-01/02/03 as info-only),
  `nyquist` 4/4, and a `findings` block recording the STREAM-01/02 traceability finding with `disposition:
  fix_in_phase`, `fixed_by: 43-02`.
- Body sections: Scope, Requirements Coverage (every PASSED row carries a re-verified file:line), Phase
  Verification Summary, Cross-Phase Integration (audit-uat baseline + de facto wiring), Tech Debt, Notes for
  Future Milestones (lesson #1 CLEAN with grep evidence; lesson #2 finding + Plan 02 disposition; report
  naming rationale), and an explicit PASSED Verdict.

## Deviations from Plan

None — plan executed exactly as written. Task 1 is a read-only audit producing no file changes; its findings
fed directly into the Task 2 report write, which is the single committed artifact for this plan. The only
discrepancy surfaced (STREAM-01/02 checkbox drift) was the expected traceability finding called out in
RESEARCH and is deferred to Plan 02 for the fix per the plan's own instruction (this plan only audits and
records, it does NOT edit REQUIREMENTS.md).

## Verification

- Task 1 gate: `audit-uat` → `total_items: 0`; all `fetch_record_batch`/`__iter__`/`__next__`,
  `_normalize_database_path`, and the three engine metadata queries matched → PASS.
- Task 2 gate: report exists; `^status: passed`; cites `cursor.py:164` and `python_renderer.py`; no
  `*UAT-AUDIT*.md` artifact created → PASS.

## Self-Check: PASSED

- FOUND: `.planning/v0.5-MILESTONE-AUDIT.md`
- FOUND: commit `c562643` (report write)
