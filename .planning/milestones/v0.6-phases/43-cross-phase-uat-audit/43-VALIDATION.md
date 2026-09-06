---
phase: 43
slug: cross-phase-uat-audit
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-09
---

# Phase 43 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

This is a **code-free audit phase.** No product code ships, so "validation"
means the audit's own verdict is **reproducible and evidence-gated** — every
success criterion marked PASSED cites a concrete observable check (file:line or
command), and re-running those checks yields the same result. There is no new
test suite to install.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) — only invoked if an in-phase code/doc fix lands |
| **Config file** | `pyproject.toml` (pytest config) + `tests/conftest.py` |
| **Quick run command** | `gsd-sdk query audit-uat --raw` (baseline) + the targeted greps below |
| **Full suite command** | `just test` (only required if an in-phase code fix lands) |
| **Estimated runtime** | ~2 s (greps + audit-uat query); ~5 s for `just test` if needed |

---

## Sampling Rate

- **After every task commit:** Re-run the relevant verification grep(s) for the SC just audited.
- **After the audit report is drafted:** Re-run the full grep set to confirm the verdict is reproducible.
- **Before milestone archival:** REQUIREMENTS.md list and Traceability table must agree; audit `status: passed`.
- **Max feedback latency:** ~5 seconds.

---

## Per-Task Verification Map

Each row is a v0.5 success criterion the audit must confirm against the shipped
surface (the observable check, not "VERIFICATION.md says so"). All commands were
run during research and confirmed to match.

| SC / Item | Phase | Requirement | Observable check (reproducible command) | Expected | Status |
|-----------|-------|-------------|------------------------------------------|----------|--------|
| Empty UAT queue baseline | — | AUDIT-01 | `gsd-sdk query audit-uat --raw` | `total_items: 0` | ⬜ pending |
| `fetch_record_batch` shipped | 39 | STREAM-01 | `grep -n "def fetch_record_batch" src/semolina/cursor.py` | match (`:164`) | ⬜ pending |
| lazy row iteration shipped | 39 | STREAM-02 | `grep -nE "def __(iter\|next)__" src/semolina/cursor.py` | match (`:222/:237`) | ⬜ pending |
| streaming how-to exists | 40 | STREAM-03 | `ls docs/src/how-to/ \| grep -i stream` | guide present | ⬜ pending |
| path normalization shipped | 41 | DKGEN-04 | `grep -n "_normalize_database_path" src/semolina/cli/codegen.py` | match (`:29`) | ⬜ pending |
| per-backend metadata queries | 42 | DKGEN-05 | `grep -rnE "SHOW COLUMNS IN VIEW\|DESCRIBE TABLE EXTENDED\|DESCRIBE SEMANTIC VIEW" src/semolina/engines/` | all three | ⬜ pending |
| strict role raise | 42 | DKGEN-05 | `grep -nE "_ROLE_TO_CLASS\|_field_class_for" src/semolina/codegen/python_renderer.py` | match (`:22/:66/:82`) | ⬜ pending |
| API names match requirement text (lesson #1) | 39–42 | all | grep set above — every named API exists under that exact name | clean | ⬜ pending |
| traceability list==table (lesson #2) | — | all | `grep -nE "STREAM-0[12]" .planning/REQUIREMENTS.md` | list `[ ]` vs table `Complete` → reconcile to agree | ⬜ pending |
| AUDIT-01 flipped last | 43 | AUDIT-01 | REQUIREMENTS.md AUDIT-01 row → `Complete` only after verdict PASSED | gated | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- None. No new test files are needed — the existing suite plus the `audit-uat`
  query and the targeted greps above are sufficient to validate the audit.

*Wave 0 work only arises if the audit elects to close a trivial functional gap
in-phase, which would then follow CLAUDE.md's failing-test-first rule.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Audit verdict is sound (each SC genuinely observable, not rubber-stamped) | AUDIT-01 | Judgement call — "observably true against the shipped surface" requires a human-readable evidence trail | Read `v0.5-MILESTONE-AUDIT.md`: every PASSED SC must carry a file:line or command citation; any SC without cited evidence is recorded as a gap, not a pass |
| SC3 gap disposition correct | AUDIT-01 | Doc/traceability gaps fix in-phase; functional gaps defer to v0.6 — disposition is a policy judgement | Confirm each surfaced gap is either closed by a follow-up plan in this phase or noted in REQUIREMENTS.md Future Requirements with a v0.6 tag |

---

## Validation Sign-Off

- [ ] Every audited SC maps to a concrete observable check (file:line or command)
- [ ] Audit verdict is reproducible: re-running the grep set yields the same PASS/gap result
- [ ] No SC marked PASSED without cited evidence
- [ ] Traceability defect resolved (list and table agree) before `status: passed`
- [ ] AUDIT-01 flipped to Complete last, gated on PASSED verdict
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
