# Phase 43: Cross-Phase UAT Audit - Research

**Researched:** 2026-06-09
**Domain:** GSD milestone auditing process (no production code); requirements traceability reconciliation; documentation hygiene
**Confidence:** HIGH (all claims verified against the GSD tooling source, the shipped Semolina code, and the on-disk planning artifacts)

## Summary

Phase 43 produces a hand-authored cross-phase audit report for the v0.5 milestone (Phases 39-42) plus the traceability/wording corrections that audit surfaces. **No production code ships.** The user has locked this as a *real* SC-by-SC milestone audit modelled on the prior `vX-MILESTONE-AUDIT.md` files, not a literal `audit-uat` queue sweep.

I confirmed the central premise empirically: `gsd-sdk query audit-uat --raw` returns `{"results": [], "summary": {"total_items": 0, ...}}` right now, so the literal AUDIT-01 tool reports "All Clear" and proves nothing [VERIFIED: ran the query]. The substance must therefore be a manual SC walk against the *observably shipped surface* (actual API names in `src/semolina/cursor.py` and `src/semolina/engines/`, actual CLI behaviour, actual docs), using the four existing VERIFICATION.md files as the recorded trail to **confirm against, not take on faith**.

I also resolved the two ambiguities CONTEXT.md flagged. **Filename:** the report MUST be named `v0.5-MILESTONE-AUDIT.md` (not the `v0.5-UAT-AUDIT.md` that SC1 names), written to root `.planning/` — because the `milestone.complete` handler globs for exactly `.planning/v{version}-MILESTONE-AUDIT.md` and the artifact regex only matches `v\d+\.\d+(?:\.\d+)?-MILESTONE-AUDIT.md` [VERIFIED: read `milestone.cjs:173-175` and `artifacts.cjs:31`]. **Known defect:** the STREAM-01/02 checkbox-vs-table inconsistency is real and confirmed (`- [ ]` in the list at REQUIREMENTS.md:14-15, but `Complete` in the table at :63-64) — the checkboxes are the stale side and must be flipped to `[x]`.

**Primary recommendation:** Run `audit-uat` once as a documented "0 outstanding items" baseline, then perform a manual SC-by-SC audit of Phases 39-42 against the shipped surface (every API name independently grep-confirmed — see the verification map below), write `.planning/v0.5-MILESTONE-AUDIT.md` modelled on the v0.4.0 audit's frontmatter, reconcile the STREAM-01/02 checkboxes and flip AUDIT-01 to `[x]`/`Complete` on a clean verdict, and emit `PASSED`.

## Architectural Responsibility Map

This is a process/audit phase. The "capabilities" are audit activities, mapped to where the work lands.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Empty-queue baseline | `gsd-sdk query audit-uat` | -- | Cheap, documents 0 outstanding items; the literal AUDIT-01 tool |
| SC-by-SC verification | Manual read of `src/semolina/` + `docs/src/how-to/` | The four 39-42 VERIFICATION.md files | Verify against shipped reality; VERIFICATION.md is corroborating evidence, not ground truth |
| Audit report artifact | `.planning/v0.5-MILESTONE-AUDIT.md` (root) | `.planning/milestones/` (post-archive) | `milestone.complete` reads root, then moves to `milestones/` |
| Traceability reconciliation | `.planning/REQUIREMENTS.md` edits | -- | Flip STREAM-01/02 checkboxes; flip AUDIT-01 on clean verdict |
| Gap disposition | `REQUIREMENTS.md` Future Requirements (defer) or in-phase follow-up plan (close) | -- | Per SC3: no gap left silently open |

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUDIT-01 | `/gsd-audit-uat` runs across all v0.5 phases and produces a structured audit report committed under `.planning/` | The literal `audit-uat` returns "All Clear" on the empty queue (verified). Per LOCKED user decision, this is satisfied by the *substance* of a milestone-style SC audit modelled on `audit-milestone.md` + the prior `vX-MILESTONE-AUDIT.md` precedents, with `audit-uat` run once as a documented baseline. The report path/name is resolved below (`v0.5-MILESTONE-AUDIT.md`). On a clean `PASSED` verdict, flip AUDIT-01 to `[x]`/`Complete`. |
</phase_requirements>

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **This is a real SC audit, not a UAT-queue sweep.** Re-verify each v0.5 success criterion for Phases 39-42 against the *observably shipped surface* (actual API names, actual CLI behaviour, actual docs) -- not just "VERIFICATION.md says passed." The four VERIFICATION.md files are the recorded trail to **confirm against**, not take on faith (SC2). Produce a verdict (`PASSED` / `gaps_found`); `PASSED` is the gate that unblocks `/gsd-complete-milestone` (SC5).
- **Bake in the two v0.4.0 retrospective lessons (SC4):**
  1. **Requirement text vs. shipped API names.** v0.4.0 shipped `fetch_arrow_table()` while ROADMAP SC text said `to_arrow()`. For v0.5, verify every requirement's named API actually exists under that name in the shipped code. Concrete checks: STREAM-01's `cursor.fetch_record_batch()` -> `pyarrow.RecordBatchReader` on `SemolinaCursor`; STREAM-03/DKGEN-05 references to `fetch_arrow_table()` and per-backend metadata queries.
  2. **Stale/inconsistent traceability.** The table must be fully populated and internally consistent. **A concrete inconsistency exists and MUST be reconciled:** STREAM-01 and STREAM-02 are unchecked (`- [ ]`) in the requirements list but their Traceability rows say `Complete` (Phase 39). The audit decides the true state (Phase 39 is Complete in ROADMAP, so the checkboxes are the stale side) and makes list + table agree.
  - On a clean audit, flip **AUDIT-01** itself to `[x]` / `Complete`.
- **Output artifact (LOCKED intent, naming is Claude's discretion):** Hand-authored audit report with YAML frontmatter and a `status:`/verdict field, modelled on `.planning/milestones/v0.4.0-MILESTONE-AUDIT.md` (frontmatter shape: `milestone`, `audited`, `status`, `scores`, `gaps`). SC1 names `v0.5-UAT-AUDIT.md`; the established prior pattern is `v0.5-MILESTONE-AUDIT.md`. Planner picks one consistently -- prefer whichever keeps `/gsd-complete-milestone` happy downstream.
- **Gap handling (SC3):** Any gap the audit surfaces is **either** closed by a follow-up plan *within* Phase 43, **or** explicitly deferred to v0.6 with a note in `REQUIREMENTS.md` Future Requirements. No gap left silently open. Distinguish *documentation/traceability* gaps (fix in-phase) from *functional* gaps (likely defer to v0.6 unless trivial).

### Claude's Discretion

- Exact report filename (`v0.5-UAT-AUDIT.md` vs `v0.5-MILESTONE-AUDIT.md`) -- resolve against what `/gsd-complete-milestone` reads. **(This research resolves it: `v0.5-MILESTONE-AUDIT.md`. See "Report Format + Path" below.)**
- Whether to invoke `/gsd-audit-uat` at all as a baseline input (cheap, documents the empty queue) vs. going straight to the manual SC walk. Reasonable to run it once for completeness and note "0 outstanding items," then do the real SC audit by hand.
- How deep to re-test live behaviour vs. trust VERIFICATION.md where the SC is purely internal (e.g. a passing snapshot test) -- apply judgement, spend effort on the user-observable surface (API names, CLI, docs).
- Whether the STREAM-01/02 checkbox reconciliation is its own tiny commit or folded into the traceability-population task.

### Deferred Ideas (OUT OF SCOPE)

- Any *functional* gap the audit uncovers in 39-42 -> defer to v0.6 with a `REQUIREMENTS.md` Future Requirements note (per SC3), unless trivial enough to fix in-phase.
- The Phase 42 code-review info items (IN-01/02/03) were left out of scope at fix time; if the audit deems them worth tracking, they belong in a backlog/v0.6 note, not this audit's gap list.
- New features; fixing *functional* product bugs silently; the actual milestone archival (`/gsd-complete-milestone` is the **next** step, not this phase).
</user_constraints>

## Project Constraints (from CLAUDE.md)

The actionable directives that bear on this phase:

- **Quality gates before committing:** `prek run --all-files` (ruff, basedpyright strict, shellcheck), `just test`, `just docs-build`. *This phase is mostly `.planning/` and `REQUIREMENTS.md` edits; those are not under `prek`'s code hooks, but any docs touch-up must pass `just docs-build` (`sphinx-build -W`).*
- **Documentation skill is mandatory** for new/heavily-rewritten docs pages: `@.claude/skills/semolina-docs-author/SKILL.md`. *Skill confirmed present at `.claude/skills/semolina-docs-author/`.* Most Phase 43 work touches no docs; **if** the audit surfaces a docs wording fix, apply the skill (full workflow for >50% rewrites; API-surface wording fixes do not require full rewrite).
- **Bug-fix discipline:** reproduce with a failing test first, then fix (failing test commit, then fix commit). *Applies only if the audit closes a trivial functional gap in-phase. Pure traceability/wording edits are not "bug fixes" in this sense.*
- **GSD planner instruction:** any PLAN.md with documentation tasks must add `@.claude/skills/semolina-docs-author/SKILL.md` to its `<execution_context>`.
- **Avoid `# type: ignore`;** prefer fixing the typing issue, pyproject-level exemptions as last resort. (Relevant only if an in-phase code fix is needed.)

## Standard Stack

No external packages are installed in this phase. **The "stack" is the GSD audit tooling already present on disk** plus the shipped Semolina surface being audited.

### Core (audit tooling)
| Tool | Location | Purpose | Notes |
|------|----------|---------|-------|
| `gsd-sdk query audit-uat --raw` | SDK query handler | Empty-queue baseline; returns JSON `{results, summary}` | Verified to return `total_items: 0` now |
| `~/.claude/get-shit-done/workflows/audit-uat.md` | workflow | The literal AUDIT-01 tool (UAT-queue sweep) | On `total_items == 0`, emits "## All Clear" and stops |
| `~/.claude/get-shit-done/workflows/audit-milestone.md` | workflow | The *substance* this phase performs (SC/intent audit) | 3-source cross-reference: VERIFICATION + SUMMARY frontmatter + traceability table |
| `.planning/milestones/v0.4.0-MILESTONE-AUDIT.md` | precedent | Closest report-format model | Frontmatter shape + per-phase scoring + "Notes for Future Milestones" |

### Supporting (precedent reports + recorded trail)
| Artifact | Purpose | When to Use |
|----------|---------|-------------|
| `v0.3-MILESTONE-AUDIT.md`, `v0.2-MILESTONE-AUDIT.md` | Additional frontmatter references | Confirm `scores`/`gaps`/`tech_debt` shape conventions |
| `39/40/41/42-VERIFICATION.md` | Recorded verification trail | Corroborate the manual SC walk; cite their evidence, then re-confirm against code |
| `39/40/41/42-VALIDATION.md` | Nyquist VALIDATION records (all four exist) | Feed the Validation Architecture section; all phases have VALIDATION.md |

**Installation:** None. No `pip`/`uv` installs; no Package Legitimacy Audit applies (no external packages).

## Report Format + Path (RESOLVED)

### Filename: `v0.5-MILESTONE-AUDIT.md` (NOT `v0.5-UAT-AUDIT.md`)

SC1 in ROADMAP names `.planning/milestones/v0.5-UAT-AUDIT.md "(or equivalent path)"`. **Use `v0.5-MILESTONE-AUDIT.md` instead.** The downstream `/gsd-complete-milestone` archival is hard-coded to this name:

- `milestone.cjs:173` computes `auditFile = .planning/v{version}-MILESTONE-AUDIT.md`, checks `existsSync`, and `renameSync`s it into `.planning/milestones/` [VERIFIED: read `~/.claude/get-shit-done/bin/lib/milestone.cjs:173-175`].
- `artifacts.cjs:31` recognises the pre-archive audit only via regex `/^v\d+\.\d+(?:\.\d+)?-MILESTONE-AUDIT\.md$/i` [VERIFIED: read `~/.claude/get-shit-done/bin/lib/artifacts.cjs:31`].
- `complete-milestone.md:497` lists `.planning/milestones/v[X.Y]-MILESTONE-AUDIT.md` in the archive commit [VERIFIED].

A file named `v0.5-UAT-AUDIT.md` matches **neither** the handler glob nor the regex, so it would be silently left behind (not archived) at milestone close. **`v0.5-MILESTONE-AUDIT.md` is the only name that keeps complete-milestone happy.**

### Write location: root `.planning/`, NOT `.planning/milestones/`

The handler reads from `.planning/v0.5-MILESTONE-AUDIT.md` (root) and *moves* it into `milestones/` itself [VERIFIED: `milestone.cjs:173`]. Every prior shipped audit lives in `milestones/` **because the handler put it there** -- e.g. `v0.1-MILESTONE-AUDIT.md` still sits in root `.planning/` precisely because it predates that move logic [VERIFIED: `ls` shows `.planning/v0.1-MILESTONE-AUDIT.md` in root, `v0.2/v0.3/v0.4.0` in `milestones/`].

**Recommendation for the planner:** write the report to **`.planning/v0.5-MILESTONE-AUDIT.md`** (root). Do not pre-place it in `milestones/`. Note: SC1's literal text says `.planning/milestones/v0.5-UAT-AUDIT.md` -- the planner should either treat SC1 as satisfied by the equivalent-path clause, or (cleaner) propose a one-line ROADMAP SC1 wording fix to match the chosen name, since this phase is precisely about traceability/wording consistency.

### Frontmatter shape to model (from v0.4.0)

```yaml
---
milestone: v0.5
audited: 2026-06-09T..:..:..Z
status: passed            # passed | gaps_found | tech_debt
scores:
  requirements: 6/6       # STREAM-01/02/03, DKGEN-04/05, AUDIT-01
  phases: 4/4             # 39-42 (43 is this audit, not counted)
  integration: deferred   # or N/M if an integration pass is run
  flows: deferred
gaps:
  requirements: []
  integration: []
  flows: []
tech_debt:
  - phase: ...
    items: [...]
nyquist:                  # all four phases have VALIDATION.md (see Validation Architecture)
  status: ...
---
```

Section structure to mirror (from v0.4.0): `# Title`, `## Scope` (phase table), `## Requirements Coverage` (per-REQ evidence table), `## Phase Verification Summary`, `## Cross-Phase Integration`, `## Tech Debt`, `## Notes for Future Milestones`, `## Verdict`.

## The Verification Work (per-SC observable checks)

Every API name the v0.5 requirements claim has been **independently grep-confirmed in the shipped code** during this research -- the planner can cite these directly, and the auditor should re-run them as the observable check rather than trusting VERIFICATION.md. This is the v0.4.0 lesson #1 discharge.

### Phase 39 - Streaming Arrow (STREAM-01, STREAM-02)
| SC | Observable check | Confirmed shipped surface |
|----|------------------|---------------------------|
| 39.1 | `fetch_record_batch()` returns `pyarrow.RecordBatchReader` on `SemolinaCursor` | `cursor.py:164` `def fetch_record_batch(self) -> pyarrow.RecordBatchReader:` [VERIFIED: grep] |
| 39.2 | `for row in cursor:` yields `Row` lazily | `cursor.py:222` `def __iter__`; `cursor.py:237` `def __next__(self) -> Row:` [VERIFIED: grep] |
| 39.3 | Cross-backend via ADBC passthrough, no backend-specific paths | One-line delegation `self._cursor.fetch_record_batch()` (per 39-VERIFICATION key-link table; re-confirm in `cursor.py`) |
| 39.4 | REQUIREMENTS text matches shipped names | STREAM-01 text says `cursor.fetch_record_batch()` -> matches `cursor.py:164`. **NOTE:** SC4 was claimed met at Phase 39 close, but the checkboxes are still `[ ]` -- see Traceability defect below |
| 39.5 | Traceability table updated | Table rows `Complete` at REQUIREMENTS.md:63-64 [VERIFIED] |

Also note `fetch_arrow_table()` exists at `cursor.py:138` (`-> pyarrow.Table`) [VERIFIED: grep] -- this is the v0.4.0 method STREAM-03/DKGEN docs reference.

### Phase 40 - Streaming How-To (STREAM-03)
| SC | Observable check | Confirmed |
|----|------------------|-----------|
| 40.1-40.4 | How-to page exists, covers stream vs `fetch_arrow_table()`, Backend notes, builds under `-W` | `docs/src/how-to/streaming.rst` exists [VERIFIED: ls]; wired in toctree per 40-VERIFICATION |
| 40.5 | Traceability for STREAM-03 | `[x]` at REQUIREMENTS.md:16; table `Complete` at :65 [VERIFIED] |

To observe live: optionally re-run `just docs-build` (`sphinx-build -W`) to confirm the page still builds. (Both Phase 40 verification SKIPs were sandbox cache-write blocks, not failures.)

### Phase 41 - DuckDB File-Backed Codegen (DKGEN-04)
| SC | Observable check | Confirmed shipped surface |
|----|------------------|---------------------------|
| 41.1 | `semolina codegen --backend duckdb --database <path>` (rel/`~`/abs, read-only) | `cli/codegen.py:29` `def _normalize_database_path(database: str) -> str:` [VERIFIED: grep] |
| 41.2 | INSTALL/LOAD `semantic_views` on native conn | `engines/duckdb.py` runs `INSTALL semantic_views FROM community` then `LOAD` (per 41-VERIFICATION :199-200; re-confirm) |
| 41.3 | Fixture `.db` + E2E test | `tests/conftest.py::duckdb_file_backed_db`; `tests/unit/codegen/test_codegen_e2e.py` |
| 41.5 | Traceability + how-to amended | `[x]` DKGEN-04; table `Complete` at :66; `docs/src/how-to/codegen.rst` amended [VERIFIED: ls codegen.rst] |

### Phase 42 - Field-Type Inference (DKGEN-05)
| SC | Observable check | Confirmed shipped surface |
|----|------------------|---------------------------|
| 42.1 | DuckDB `DESCRIBE SEMANTIC VIEW` -> Metric/Dimension/Fact | `engines/duckdb.py:202` `DESCRIBE SEMANTIC VIEW {unqualified}` [VERIFIED: grep] |
| 42.2 | Snowflake native metadata source | `engines/snowflake.py:328` `SHOW COLUMNS IN VIEW {qualified_name}` [VERIFIED: grep] |
| 42.3 | Databricks native metadata source | `engines/databricks.py:330` `DESCRIBE TABLE EXTENDED {view_name} AS JSON`; `is_measure` at :336-337 [VERIFIED: grep] |
| 42.4 | Every column resolves to concrete role; unrecognized raises `ValueError` | `python_renderer.py:22` `_ROLE_TO_CLASS = {"metric":..,"dimension":..,"fact":..}`; `:66` `_field_class_for`; `:82` dict lookup (raises `ValueError` on `KeyError`) [VERIFIED: grep] |
| 42.5 | Traceability + PROJECT.md decision log | `[x]` DKGEN-05; table `Complete` at :67; PROJECT.md Key Decisions records the three metadata paths (per STATE.md decision log) |

**All five v0.5 named-API claims are confirmed accurate against shipped code** -- the v0.4.0 `to_arrow()`-vs-`fetch_arrow_table()` drift does *not* recur in v0.5. This is a clean SC4 lesson-#1 result, and the audit should state so explicitly with these grep citations.

## The Two v0.4.0 Lessons as Audit Targets

### Lesson #1: API-name vs requirement-text drift -> CLEAN for v0.5
Method: for each REQ, extract the API name from the requirement text and grep it in `src/semolina/`. Result above: all five match. The audit records this as PASSED with the grep evidence, contrasting with v0.4.0 ARROW-02 (`to_arrow()` text vs `fetch_arrow_table()` shipped).

### Lesson #2: Traceability consistency -> ONE confirmed defect to reconcile
**The defect (confirmed):** REQUIREMENTS.md has STREAM-01 (`:14`) and STREAM-02 (`:15`) as unchecked `- [ ]` in the requirements list, while the Traceability table (`:63-64`) marks both `Complete` for Phase 39 [VERIFIED: grep showed both states].

**Resolution (decided by the evidence):** Phase 39 is `[x]` Complete in ROADMAP (`:93`), 39-VERIFICATION is `passed` 5/5, and 39-02-SUMMARY records the traceability close. The **checkboxes are the stale side** -- the Phase 39 close updated the table rows and footer but missed flipping the two list checkboxes. The audit flips `:14` and `:15` to `- [x]` so list + table agree.

**Why it happened (note for the report):** the STREAM-01/02 list items sit in the v0.4.0-carryover preamble block; the close-out edited the table but not the carryover checkboxes. Same class of "table edited, list not" drift the v0.4.0 audit warned about.

**Also in scope:** on a clean overall verdict, flip AUDIT-01 (`:29` `- [ ]`, table `:68` `Pending`) to `[x]`/`Complete` and update the REQUIREMENTS.md footer + Coverage block if needed. AUDIT-01 is the only `Pending` row remaining; everything else is `Complete`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Discovering outstanding UAT items | Custom file-walk for `*-UAT.md` | `gsd-sdk query audit-uat --raw` | Already does it; returns structured JSON; confirmed empty here |
| Report frontmatter schema | Invent a new YAML shape | Copy `v0.4.0-MILESTONE-AUDIT.md` frontmatter | Downstream tooling + convention already established |
| Audit file naming/placement | Guess a path | `v0.5-MILESTONE-AUDIT.md` in root `.planning/` | `milestone.complete` globs this exact name/location |
| Re-deriving requirement status | Trust a single source | 3-source cross-ref (VERIFICATION + SUMMARY frontmatter + traceability), per `audit-milestone.md` step 5 | Catches exactly the checkbox-vs-table drift this phase targets |

**Key insight:** the GSD `audit-milestone.md` workflow already encodes the correct methodology (3-source cross-reference, FAIL gate, orphan detection). The manual SC audit should *follow that workflow's structure* while substituting hand-verification of the shipped surface for the literal `audit-uat` queue sweep.

## Common Pitfalls

### Pitfall 1: Naming the report `v0.5-UAT-AUDIT.md` per SC1's literal text
**What goes wrong:** complete-milestone never finds it; the file is left un-archived in root `.planning/`.
**Why it happens:** SC1 names `v0.5-UAT-AUDIT.md`; the handler globs `v{version}-MILESTONE-AUDIT.md`.
**How to avoid:** use `v0.5-MILESTONE-AUDIT.md`; optionally fix SC1 wording in ROADMAP (in-scope, since this phase reconciles wording).
**Warning sign:** any plan task that writes a filename containing `UAT-AUDIT`.

### Pitfall 2: Treating "All Clear" from `audit-uat` as the deliverable
**What goes wrong:** the report proves nothing; the v0.4.0 retrospective gap is not actually closed.
**Why it happens:** AUDIT-01 literally names `/gsd-audit-uat`, and the queue is empty.
**How to avoid:** run it once as a baseline line-item, then do the manual SC walk (the LOCKED user decision).
**Warning sign:** a report whose body is just the "All Clear" block.

### Pitfall 3: Verifying SCs from VERIFICATION.md alone
**What goes wrong:** re-asserts the recorded trail without confirming reality -- exactly what v0.4.0 did (and still passed only because code happened to match).
**How to avoid:** re-grep each named API in `src/semolina/` (citations provided above); cite the line numbers in the report.
**Warning sign:** evidence column says "per 3X-VERIFICATION.md" with no code citation.

### Pitfall 4: Silently editing a functional bug if one is found
**What goes wrong:** violates SC3 and the phase boundary (no quiet functional edits).
**How to avoid:** classify every gap as doc/traceability (fix in-phase) vs functional (defer to v0.6 Future Requirements, or a tracked follow-up plan). Document the disposition.

### Pitfall 5: Flipping AUDIT-01 to Complete before the verdict is `PASSED`
**What goes wrong:** marks the requirement done while gaps remain open.
**How to avoid:** flip AUDIT-01 only as the final step, gated on `status: passed`.

## Runtime State Inventory

This phase edits `.planning/` markdown and (conditionally) docs. It registers no services, stores no data, and changes no runtime config. Per the rename/refactor checklist:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None -- no datastore keys touched | none |
| Live service config | None -- no external services | none |
| OS-registered state | None | none |
| Secrets/env vars | None | none |
| Build artifacts | None -- no package rename; no rebuild | none (unless an in-phase code fix lands, which would run normal `just test`) |

**Nothing found in any category:** verified -- the deliverable is a report plus `REQUIREMENTS.md`/(optional) docs edits.

## Validation Architecture

Nyquist validation is **enabled** (no `workflow.nyquist_validation` key in `.planning/config.json` -> default enabled) [VERIFIED: read config.json]. All four phases already have VALIDATION.md on disk [VERIFIED: ls found `39/40/41/42-VALIDATION.md`], so the milestone's Nyquist coverage is complete and the audit's `nyquist` frontmatter should record `4/4`.

Because this phase ships no product code, "validation" means **the audit's own correctness is reproducible and evidence-gated**, not a new test suite.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing); `just test` runs unit + jaffle-shop mock tests |
| Config file | `pyproject.toml` (pytest config) + `tests/conftest.py` |
| Quick run command | `gsd-sdk query audit-uat --raw` (baseline) + targeted greps below |
| Full suite command | `just test` (only if an in-phase code fix lands; otherwise not required) |

### Phase Requirement -> Validation Map
| Req | Behavior | Validation type | Reproducible command | Exists? |
|-----|----------|-----------------|----------------------|---------|
| AUDIT-01 | Empty queue documented | tool | `gsd-sdk query audit-uat --raw` -> `total_items: 0` | yes (verified) |
| 39.1 | `fetch_record_batch` shipped | grep | `grep -n "def fetch_record_batch" src/semolina/cursor.py` | yes (`:164`) |
| 39.2 | lazy iteration shipped | grep | `grep -nE "def __(iter|next)__" src/semolina/cursor.py` | yes (`:222/:237`) |
| 41.1 | path normalization shipped | grep | `grep -n "_normalize_database_path" src/semolina/cli/codegen.py` | yes (`:29`) |
| 42.x | per-backend metadata queries | grep | `grep -rn "SHOW COLUMNS IN VIEW\|DESCRIBE TABLE EXTENDED\|DESCRIBE SEMANTIC VIEW" src/semolina/engines/` | yes (all three) |
| 42.4 | strict raise | grep | `grep -n "_ROLE_TO_CLASS\|_field_class_for" src/semolina/codegen/python_renderer.py` | yes (`:22/:66/:82`) |
| Traceability | checkbox==table | grep | `grep -nE "STREAM-0[12]" .planning/REQUIREMENTS.md` shows `[ ]` (list) vs `Complete` (table) | yes (defect confirmed) |

### Audit self-validation invariants (the report must satisfy)
- **Every SC marked PASSED cites a concrete observable check** (file:line or command), not "VERIFICATION.md says so."
- **The verdict is reproducible:** re-running the greps above yields the same PASS/gap result.
- **No SC marked PASSED without cited evidence;** any unverifiable SC is a gap, not a pass.
- **The traceability defect is resolved before `status: passed`** (list and table agree; AUDIT-01 flipped last).

### Wave 0 Gaps
- None. No new test files needed; the existing suite + `audit-uat` query + targeted greps are sufficient. (Wave 0 work only arises if the audit elects to close a trivial functional gap in-phase, which would then follow CLAUDE.md's failing-test-first rule.)

## Code Examples

The "code" here is verification commands. Verified during research:

### Confirm all v0.5 named APIs exist (lesson #1 discharge)
```bash
# Source: ran during this research
grep -nE "def (fetch_record_batch|fetch_arrow_table|__iter__|__next__)" src/semolina/cursor.py
grep -nE "_ROLE_TO_CLASS|def _field_class_for|def _normalize_database_path" \
  src/semolina/codegen/python_renderer.py src/semolina/cli/codegen.py
grep -rnE "DESCRIBE SEMANTIC VIEW|SHOW COLUMNS IN VIEW|DESCRIBE TABLE EXTENDED|is_measure" \
  src/semolina/engines/
```

### Confirm the empty UAT baseline
```bash
gsd-sdk query audit-uat --raw   # -> {"results": [], "summary": {"total_items": 0, ...}}
```

### Confirm the traceability defect (lesson #2)
```bash
grep -nE "STREAM-0[12]" .planning/REQUIREMENTS.md
# :14/:15 show "- [ ]" (stale); :63/:64 show table "Complete" (true state)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Milestone audit produced at archive time by `/gsd-complete-milestone` (v0.2/v0.3/v0.4.0) | Carved out as a tracked phase (Phase 43) *before* archival | v0.5 (this phase) | Audit becomes a planned deliverable with its own verdict gate; deliberate reaction to the v0.4.0 retrospective |
| Trust VERIFICATION.md as ground truth | Confirm SCs against the observably shipped surface | v0.5 (SC2/SC4) | Catches API-name and traceability drift that v0.4.0 caught late |

**Deprecated/outdated:** nothing -- this phase *adds* rigor rather than replacing tooling.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The STREAM-01/02 checkboxes (not the table rows) are the stale side | Lesson #2 | Low -- corroborated by ROADMAP `[x]`, 39-VERIFICATION `passed`, and 39-02-SUMMARY's recorded close. If somehow the *table* were wrong instead, the resolution direction flips, but all evidence points one way |
| A2 | Running `audit-uat` once as a baseline satisfies the "tool ran" letter of AUDIT-01 alongside the manual substance | AUDIT-01 mapping | Low -- this is the LOCKED user reading of AUDIT-01 |

All other claims are `[VERIFIED]` against tooling source or shipped code. Two low-risk assumptions only.

## Open Questions

1. **SC1 path wording vs. chosen filename**
   - What we know: SC1 names `.planning/milestones/v0.5-UAT-AUDIT.md`; complete-milestone needs `.planning/v0.5-MILESTONE-AUDIT.md`.
   - What's unclear: whether to (a) lean on SC1's "(or equivalent path)" clause, or (b) also fix the SC1 wording in ROADMAP.
   - Recommendation: write `v0.5-MILESTONE-AUDIT.md`; since this phase is about wording consistency, a one-line ROADMAP SC1 amendment is the cleaner, in-character choice. Planner decides.

2. **Whether any in-phase functional gap will surface**
   - What we know: all four phases verified `passed`; all named APIs confirmed shipped.
   - What's unclear: a deep SC walk could still surface a minor doc inaccuracy.
   - Recommendation: pre-commit to the SC3 disposition rule (doc/traceability = fix in-phase; functional = defer to v0.6) so the plan has a branch ready either way.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `gsd-sdk` CLI | AUDIT-01 baseline + init | yes | n/a | none needed (ran successfully) |
| `git` (grep over repo) | SC verification | yes | n/a | -- |
| `just`/`uv`/`sphinx` | only if a docs/code fix lands | assumed (per CLAUDE.md gates) | -- | audit can complete without running them if no code/docs edit occurs |

**Missing dependencies with no fallback:** none. The audit's core (read code, run `audit-uat`, write markdown, edit REQUIREMENTS.md) needs only the GSD CLI and a shell, both confirmed working.

## Sources

### Primary (HIGH confidence)
- `~/.claude/get-shit-done/bin/lib/milestone.cjs:173-175` -- audit-file glob/move logic (filename resolution)
- `~/.claude/get-shit-done/bin/lib/artifacts.cjs:31` -- `v\d+\.\d+(?:\.\d+)?-MILESTONE-AUDIT.md` regex
- `~/.claude/get-shit-done/workflows/audit-uat.md`, `audit-milestone.md`, `complete-milestone.md` -- tooling behaviour
- `src/semolina/cursor.py`, `codegen/python_renderer.py`, `cli/codegen.py`, `engines/{snowflake,databricks,duckdb}.py` -- grep-confirmed shipped API names
- `.planning/REQUIREMENTS.md` (checkbox/table defect), `.planning/ROADMAP.md` (SCs), `.planning/config.json` (nyquist enabled)
- `.planning/milestones/v0.4.0-MILESTONE-AUDIT.md` (+ v0.3/v0.2 frontmatter) -- report-format precedent
- `39/40/41/42-VERIFICATION.md` and `*-VALIDATION.md` -- recorded trail
- `gsd-sdk query audit-uat --raw` live output -- empty-queue confirmation

### Secondary (MEDIUM confidence)
- `39-02`/`40-01`/`41-03`/`42-03`-SUMMARY.md `requirements-completed` frontmatter -- traceability cross-check source

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Audit tooling + filename/path resolution: HIGH -- read the handler source directly
- SC verification map (API names): HIGH -- every name grep-confirmed in shipped code
- Traceability defect + resolution direction: HIGH -- both states confirmed; resolution corroborated by 3 sources
- Report format: HIGH -- modelled on three on-disk precedents

**Research date:** 2026-06-09
**Valid until:** ~2026-07-09 (stable; the only volatility is the GSD tooling, which is local and unchanged)
