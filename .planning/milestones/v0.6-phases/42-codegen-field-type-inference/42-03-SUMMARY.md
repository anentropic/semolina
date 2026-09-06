---
phase: 42-codegen-field-type-inference
plan: 03
subsystem: codegen
tags: [codegen, docs, how-to, closeout, traceability, snowflake, databricks, duckdb]

# Dependency graph
requires:
  - phase: 42-codegen-field-type-inference
    plan: 02
    provides: Strict _field_class_for (raise on unrecognized role) — the behaviour this plan documents
provides:
  - Codegen how-to documenting 3-backend per-role emission + Databricks no-Fact + strict-raise
  - DKGEN-05 closed (checkbox + Traceability Complete)
  - ROADMAP Phase 42 criterion 4 rewritten (no Field() fallback framing); Phase 42 marked Complete 3/3
  - PROJECT.md Key Decisions: per-backend metadata-query paths + strict-raise decision
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Keep requirement/criterion text in lock-step with the shipped behaviour at phase close (criterion 4 rewrite)"

key-files:
  created:
    - .planning/phases/42-codegen-field-type-inference/42-03-SUMMARY.md
  modified:
    - docs/src/how-to/codegen.rst
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/PROJECT.md

key-decisions:
  - "Criterion 4 reworded from 'Field() fallback preserved' to 'every column resolves to a concrete role; unrecognized role raises ValueError' — the locked Phase 42 decision removed the fallback concept entirely"
  - "DKGEN-05 description expanded with the three per-backend metadata-query paths so REQUIREMENTS reads consistently with the rewritten ROADMAP criterion and PROJECT.md decisions"

patterns-established:
  - "Phase close-out keeps ROADMAP criterion + REQUIREMENTS requirement + PROJECT.md decision text mutually consistent"

requirements-completed: [DKGEN-05]

# Metrics
duration: ~10min
completed: 2026-06-09
---

# Phase 42 Plan 03: Codegen How-To Amendment + Phase Close-Out Summary

**Amended the codegen how-to to document concrete-role field-type emission across all three backends plus the strict-raise behaviour, rewrote ROADMAP criterion 4 and REQUIREMENTS DKGEN-05 from the obsolete "Field() fallback preserved" framing to "every column resolves to a concrete role; unrecognized role raises ValueError", closed DKGEN-05, and logged the per-backend metadata-query paths in PROJECT.md.**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-06-09
- **Tasks:** 3
- **Files modified:** 4 (1 doc + 3 planning/tracking)

## Accomplishments

- `docs/src/how-to/codegen.rst`: added a lead-in stating every column gets a concrete field type (no bare `Field()` for known roles); expanded the Databricks no-Fact `.. note::` to read as an intentional two-role constraint; added new prose explaining that an unrecognized role string stops codegen with a `ValueError` rather than mislabeling the column. The existing tab-set already named all three backends (Snowflake Metric/Dimension/Fact, Databricks Metric/Dimension, DuckDB all three), so that part was verified rather than rebuilt.
- `just docs-build` (Sphinx `-W` strict) exits 0 — no warnings.
- ROADMAP: criterion 4 rewritten; the three Phase 42 Plans checklist items confirmed `[x]`; Progress table Phase 42 row updated to `3/3 | Complete | 2026-06-09`.
- REQUIREMENTS: DKGEN-05 checkbox `[x]`, Traceability row `Complete`, description expanded with the three metadata-query paths and the raise behaviour; footer updated.
- PROJECT.md Key Decisions: two new rows — the per-backend metadata-query paths (DuckDB `DESCRIBE SEMANTIC VIEW`, Snowflake `SHOW COLUMNS IN VIEW` `kind`, Databricks `DESCRIBE TABLE EXTENDED ... AS JSON` `is_measure`) and the strict-raise-on-unrecognized-role decision; footer updated to Phase 42.

## Task Commits

1. **Task 1: Amend the codegen how-to** - `7a41710` (docs)
2. **Task 2: Rewrite criterion 4 / DKGEN-05 and close traceability** - `1f1df41` (docs)
3. **Task 3: Record metadata-query paths + strict-raise in PROJECT.md** - `4e920c5` (docs)

## Files Created/Modified

- `docs/src/how-to/codegen.rst` - Lead-in on concrete-role emission; expanded Databricks no-Fact note; new strict-raise prose. (+19/-3)
- `.planning/ROADMAP.md` - Criterion 4 rewrite; 42-03 checklist `[x]`; Progress row 3/3 Complete.
- `.planning/REQUIREMENTS.md` - DKGEN-05 `[x]` + Traceability Complete + reworded description + footer.
- `.planning/PROJECT.md` - Two Key Decisions rows (metadata paths + strict-raise); footer.

## Decisions Made

- **Criterion 4 rewrite over deletion**: kept criterion 4 in place but reworded to the locked "concrete role / raise" framing so the ROADMAP success-criteria contract stays complete and matches the shipped behaviour from Plan 02.
- **DKGEN-05 description expansion**: the original DKGEN-05 text did not claim a Field() fallback, so it only needed the per-backend metadata paths and the raise statement added for consistency with the rewritten criterion and the PROJECT.md decisions — no contradictory text to remove.

## Deviations from Plan

None - plan executed exactly as written. The how-to tab-set already named all three backends for per-role emission, so Task 1 verified that part and focused the new prose on the strict-raise behaviour and the intentional Databricks no-Fact note, as the plan's action anticipated.

## Threat Model Outcome

- **T-42-03 (Information disclosure — documented metadata-query paths):** accepted as planned. The query strings (`DESCRIBE SEMANTIC VIEW`, `SHOW COLUMNS IN VIEW`, `DESCRIBE TABLE EXTENDED`) are public warehouse DDL syntax, not secrets.
- **T-42-SC (package installs):** no package installs in this plan.

## Issues Encountered

- `just docs-build` (which wraps `uv run sphinx-build`) panicked under the command sandbox (`system-configuration` NULL object / Tokio executor), the same environment issue noted in Plans 01 and 02. Resolved by running the build and commits with the sandbox disabled. No content impact.

## Verification

- `just docs-build` → **build succeeded** (Sphinx `-W` strict, no warnings).
- Task 2 deterministic grep verify → `OK` (no stale "Field()` fallback behaviour is preserved" text; "resolves to a concrete role" present; Progress row `3/3 | Complete | 2026-06-09`; DKGEN-05 `[x]`; Traceability `Complete`).
- Task 3 grep verify → `OK` (all three metadata-query strings present in PROJECT.md).
- How-to field-type section names all three backends; new prose contains "ValueError"/"Failing loudly"; Databricks no-Fact stated as intentional.

## User Setup Required

None.

## Next Phase Readiness

- Phase 42 is complete (3/3 plans). DKGEN-05 closed.
- Remaining v0.5 work: Phase 43 cross-phase UAT audit (AUDIT-01). No blockers.

---
*Phase: 42-codegen-field-type-inference*
*Completed: 2026-06-09*

## Self-Check: PASSED

- FOUND: .planning/phases/42-codegen-field-type-inference/42-03-SUMMARY.md
- FOUND: docs/src/how-to/codegen.rst
- FOUND commit: 7a41710 (Task 1)
- FOUND commit: 1f1df41 (Task 2)
- FOUND commit: 4e920c5 (Task 3)
- FOUND commit: f53bf19 (SUMMARY)
