---
phase: 47-type-fidelity-probe-decision-doc
plan: 04
subsystem: docs
tags: [decimal, nullability, execute-schema, type-map, codegen, diataxis, decision-doc]

# Dependency graph
requires:
  - phase: 47-type-fidelity-probe-decision-doc
    plan: 01
    provides: "tests/type_fidelity_probe.py, the committed artifact, just type-fidelity, and the canary that keeps a mismatch visible"
  - phase: 47-type-fidelity-probe-decision-doc
    plan: 02
    provides: "The four named disagreements, the empty-group nullability measurements, and the downstream Decimal consumer rows"
  - phase: 47-type-fidelity-probe-decision-doc
    plan: 03
    provides: "The Snowflake and Databricks rows, the driver-capability table from driver source, and the six-entry evidence-limitations section"
provides:
  - "47-DECISIONS.md — the normative specification Phases 48 and 50 are planned against: five decision sections, each claim cited to an artifact section or a source path"
  - "Decimal policy: decimal.Decimal on all three backends, covering the whole Snowflake FIXED family including scale 0, explicitly annotation-only"
  - "Metric-nullability stance: uniform T | None with COUNT as a documented over-approximation"
  - "Source of truth: query-time result schema primary, warehouse introspection metadata a labelled fallback, result schema wins on disagreement"
  - "Per-driver adbc_execute_schema answers with the version each was checked at, plus a dated staleness note"
  - "A 'What Phase 48 must change' table naming the exact type_map.py keys and branches"
  - "docs/src/explanation/type-fidelity.rst — user-facing Diataxis Explanation page, reachable from the explanation toctree"
  - "Two follow-up todos capturing the two gaps this phase chose not to close"
affects: [48-type-map, 49-into-dto, 50-codegen-dtos]

actuals:
  tokens: 9700
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "A normative planning doc and a derived docs page, one-directional: the page links nowhere into .planning/, so the two cannot form a citation cycle"
    - "Scope stated as a prohibition next to the decision it bounds — 'annotation-only, Phase 48 must not add runtime coercion' sits inside Decision 1 rather than in a note at the end"

key-files:
  created:
    - .planning/phases/47-type-fidelity-probe-decision-doc/47-DECISIONS.md
    - .planning/todos/pending/2026-08-12-record-snowflake-introspection-cassette.md
    - .planning/todos/pending/2026-08-12-verify-databricks-zero-row-fallback.md
    - docs/src/explanation/type-fidelity.rst
  modified:
    - docs/src/explanation/index.rst
    - .planning/phases/47-type-fidelity-probe-decision-doc/47-VALIDATION.md

key-decisions:
  - "Decimal policy is decimal.Decimal on all three backends and covers the whole Snowflake FIXED family including scale 0 — the driver returns Decimal128 for every FIXED column while use_high_precision is enabled, which is its default and which adbc_poolhouse never changes"
  - "The Decimal policy is annotation-only and says so as a prohibition: batch.to_pylist() feeding Row(...) is the whole value path and carries no coercion, so Phase 48 touches type_map.py plus the renderer and must not touch cursor.py or results.py"
  - "Metric nullability is uniform T | None with COUNT named as an over-approximation, chosen over expression sniffing because the aggregate expression is reachable on DuckDB and Databricks but not from Snowflake's SHOW COLUMNS IN VIEW"
  - "The query-time result schema is promoted to primary and warehouse metadata demoted to a labelled fallback, with the precedence rule stated for disagreement and the route recorded on the annotation"
  - "The Snowflake FIXED generalisation is labelled driver-source evidence rather than measurement, because only one scale-0 column was actually measured"
  - "The two documents are one-directional: 47-DECISIONS.md is normative, the docs page is derived from it, and the page carries no .planning/ link"

patterns-established:
  - "Automate every automatable step of a human-verify gate before returning it, so the reviewer is left only with the judgement steps"
  - "Where the evidence does not settle a question, label the sentence a policy call or an open assumption in the same breath rather than letting a decision inherit the authority of the measurements around it"

requirements-completed: []  # TYPE-02's substance is met by 47-DECISIONS.md, but requirement status is set by the phase-completion step; see "Requirement status" below.

coverage:
  - id: D22
    description: "A normative decision doc states all four required answers plus a fifth non-gating one, each claim citing a named artifact section or a source path"
    requirement: TYPE-02
    verification:
      - kind: integration
        ref: "test -f 47-DECISIONS.md && grep -qF 'decimal.Decimal' && grep -qF 'use_high_precision'"
        status: pass
    human_judgment: true
    rationale: "Citational, so no test settles whether a citation actually supports its claim. The reviewer gate's step 6 checked each of the three policy calls for a citation rather than a preference and approved all three as a set."
  - id: D23
    description: "The per-driver adbc_execute_schema answer is carried forward with the version each was checked at and a dated staleness note, so Phases 48 and 50 do not rediscover it"
    requirement: TYPE-02
    verification: []
    human_judgment: true
    rationale: "Three driver rows reproduced from the artifact's capability table, each with a version string, plus a note naming go/v0.1.3 as the row that moves. A reviewer confirms the capability claim is never sourced from a replayed probe."
  - id: D24
    description: "A user-facing Diataxis Explanation page explains why a money column is a Decimal, what is nullable, and where the catalogue and the result disagree, reachable from the toctree and building clean under sphinx-build -W"
    requirement: TYPE-02
    verification:
      - kind: integration
        ref: "just docs-build && grep -qF 'type-fidelity' docs/src/explanation/index.rst && grep -qF '_explanation-type-fidelity:' docs/src/explanation/type-fidelity.rst"
        status: pass
    human_judgment: false
  - id: D25
    description: "A human walked the anti-circularity procedure end to end, finishing at a raw .arrow file no Semolina code touched, and accepted the three interlocking policy calls as a set"
    requirement: TYPE-01, TYPE-02
    verification: []
    human_judgment: true
    rationale: "checkpoint:human-verify gate=blocking, approved 2026-08-12. Executor ran steps 1-5 and 8; the human ran steps 6 and 7."

duration: ~40min
completed: 2026-08-12
status: complete
---

# Phase 47 Plan 04: The Decision Doc Summary

**Four measured answers became one specification: a money column maps to `decimal.Decimal`, every metric annotation admits `None`, the query-time result schema outranks the catalogue, and each driver's `adbc_execute_schema` answer is written down with the version it was checked at.**

## Performance

- **Duration:** ~40 min of execution, plus the review gate
- **Tasks:** 3 (two authoring tasks, one blocking review gate)
- **Files modified:** 6 (4 created, 2 modified)

## The four answers, and what decided each

| Question | Answer | What decided it |
|---|---|---|
| Decimal policy | `decimal.Decimal` on all three backends, whole Snowflake `FIXED` family included | `to_pylist()` already returns `Decimal`, plus the driver's `use_high_precision` default |
| Metric nullability | Uniform `T \| None`, COUNT a documented over-approximation | The empty-group measurement; explicitly *not* the Arrow `nullable` flag |
| Source of truth | Result schema primary, metadata a labelled fallback | The three-way decimal disagreement the co-equal treatment produced |
| Per-driver `ExecuteSchema` | Snowflake yes-with-caveat, Databricks no, DuckDB yes | Driver source at pinned versions, never a replayed probe |

A fifth section answers the originating todo's filter-value-typing question (lenient widening) and is marked non-gating, so a later phase can revisit it without treating it as settled.

## The Snowflake `FIXED` scope, and why it is labelled the way it is

The policy covers scale 0, not only scale-above-0 columns. That is the sharpest thing in the document, because it means a Snowflake `NUMBER(38,0)` column annotates as `Decimal` rather than `int`, and Snowflake reports plain `NUMBER` as `NUMBER(38,0)`.

The evidence behind it is uneven, and the doc says so rather than smoothing it. One scale-0 column was measured: `AGG("REVENUE")`, metadata `{"type": "FIXED", "scale": 0}`, result `decimal128(38, 0)`, value `decimal.Decimal`. The generalisation to the whole `FIXED` family rests on the driver docstring quoted from `go/driver.go` lines 74-80, which is driver-source evidence and is labelled as such. The doc also flags the consequence nobody has measured — a Snowflake `COUNT` is reported as `NUMBER(38,0)`, so it annotates as `Decimal` too, and no recording in this repo carries one.

## The gate, and the one edit it produced

Task 3 was a `checkpoint:human-verify` with `gate="blocking"`, and it was **approved by a human on 2026-08-12, not auto-approved**. The plan is `autonomous: false` and the orchestrator's instruction was explicit that the gate could not be self-decided.

Before returning it, the executor ran every automatable step of the reviewer procedure so the human was left only with the judgement:

| Step | Check | Result |
|---|---|---|
| 1 | `just type-fidelity` then `git diff` on the artifact | byte-identical, no drift |
| 2 | `derived-from-code` in a result cell | absent — appears only in the two Snowflake metadata cells |
| 3 | Canary row still a mismatch | `TODO: DECIMAL(38,2)` / `decimal128(38, 2)` / `decimal.Decimal` / `mismatch` |
| 4 | Raw `pyarrow.ipc.open_file` read of the Snowflake cassette | `AGG("REVENUE"): decimal128(38, 0)`, matching the table |
| 5 | Capability and comparison header tuples | intersection is the empty set |
| 8 | `just test`, `prek run --all-files`, `just docs-build` | 1073 passed / 16 skipped plus 16 / 15; clean; zero warnings under `-W` |

**The deciding factor was scope.** The reviewer probed whether the Decimal policy was annotation-only or whether it implied runtime coercion, and confirmed against the code before approving: `batch.to_pylist()` feeding `Row(...)` (`src/semolina/cursor.py:281`) is the whole value path, and neither `cursor.py` nor `results.py` contains a `Decimal(`, `float(`, or `int(` conversion anywhere on it. So a money column already yields `Decimal` today and Phase 48 touches only `type_map.py` plus the renderer.

That was not stated unmistakably in the doc as written, so the gate produced one edit: a `### Scope: this policy is annotation-only` subsection inside Decision 1, written as a prohibition — a change to `cursor.py` or `results.py` to make a value match its annotation is out of scope and inverts the decision, because the annotation is corrected to the value and never the reverse. Committed as `d5dcc2c`.

## The docs page

`docs/src/explanation/type-fidelity.rst` is Diataxis **Explanation**: why a metric has no declared type, where the catalogue and the result disagree, why money is a `Decimal`, what can be NULL, and when Semolina can ask the warehouse versus read the catalogue. No step-by-step instructions; action items link out to the how-tos.

Two choices worth recording. Disagreements are stated as the Python type that lands in a row rather than as Arrow spellings, which meant being honest that the `COUNT`-vs-`MIN` width difference is *invisible* in a `Row` (both are `int`) and only surfaces through `fetch_arrow_table()`. And the page carries a `.. note::` separating claims about today's runtime, which are true in the present tense, from the generated annotations the type map has not caught up with — a Snowflake `NUMBER` column may still be annotated `int` or `float` today, and the note tells the reader to trust the runtime value over the annotation until it is.

The humanizer pass changed two things: an opening rewritten from one stiff compound sentence into three of varying length, and a participial construction describing the Snowflake driver option ("has an option for exactly that, returning...") rewritten to name the behaviour rather than invert the flag's polarity — `use_high_precision` defaults to *on* and produces decimals, so calling the float-producing path "an option that is off by default" risked confusing anyone who looked the flag up. Greps confirmed zero AI-vocabulary hits, zero em dashes in prose, zero curly quotes, zero planning vocabulary, and sentence-case headings throughout.

## Deviations from Plan

**None on tasks 1 and 2.** Both were written as specified, and both automated verifies passed on the first run.

One process note that is not a deviation: `blacken-docs` reformatted the page's Python code block on the first commit attempt and failed the hook, as it is designed to. The reformatted file was re-staged, `just docs-build` re-run, and the commit retried clean. No content changed.

The gate produced the annotation-only scope edit described above. That is the gate working as intended rather than a deviation from the plan — the plan's own reversibility note says the `checkpoint:human-verify` in Task 3 is where a human accepts all three policy calls together.

## Carried forward, honoured not re-litigated

- **Verdict vocabulary stays two-valued.** Nothing in either document reintroduces `mapping-gap`.
- **`.planning/REQUIREMENTS.md` untouched.** See below.
- **Broken windows 2, 3 and 4 stay open**, and `47-DECISIONS.md` § "Evidence limitations carried forward" names all three as open rather than implying coverage. Window 2 in particular: the zero-row fallback has still never fired against a driver that refuses `ExecuteSchema`, and Decision 3 states that if the Databricks planner rejects the wrapper, Databricks has neither route and that is a Phase 48 blocker.
- **Capability and result-type claims stay separate.** Decision 4 restates once, in its own words, that a replayed `adbc_execute_schema` call is evidence about result types and never about driver capability.
- **The Databricks result column is `measure(revenue)`.** Neither document spells it `MEASURE("revenue")`.

## Requirement status

`.planning/REQUIREMENTS.md` was **not** touched, on explicit instruction from the orchestrator — TYPE-01 and TYPE-02 are marked by the phase-completion step. This is the same instruction plan 47-03 received and recorded.

For whoever does mark them: TYPE-02 reads "a committed type-mapping decision doc covering the Decimal policy, the metric-nullability stance, and which source of truth codegen uses". All three are stated with citations, the fourth ROADMAP criterion (per-driver `adbc_execute_schema`) is answered in Decision 4, and a human has walked the anti-circularity procedure. The substance of TYPE-02 is met. TYPE-01 was met by plan 47-03.

The originating todo `2026-08-01-research-warehouse-type-fidelity-for-field-typing.md` carries `resolves_phase: 47` and was left in `pending/` for the phase-close step to retire.

## Validation

`47-VALIDATION.md` gained three rows for this plan and `nyquist_compliant` is now **true**. The map is genuinely complete: every task across all four plans has a row, and the sign-off checklist holds.

Task `47-04-03` carries no automated command, which is correct rather than a gap — it is a review gate, and it is listed under Manual-Only Verifications. Sampling continuity is unaffected, since `47-04-01` and `47-04-02` both carry automated verification immediately before it, so no three consecutive tasks lack automated feedback.

The second manual-only verification, the Databricks zero-row fallback, was **not** run: no workspace was available. It took the documented alternative (record it as evidence-limited) rather than being skipped silently, and it is now stated in four places — Decision 3, the artifact's evidence limitations, broken window 2, and a follow-up todo. `wave_0_complete` also flipped to true, since both Wave 0 checkboxes have been ticked since plan 47-03.

`status` stays `draft`. The file's own lifecycle comment says `validated` is set by `/gsd-validate-phase` §6, not by an executor.

## Known Stubs

None. Both documents are complete prose with no placeholder text, no TODO markers, and no section left to a later plan.

## Broken windows

None recorded by this plan, and none closed. Windows 2, 3 and 4 remain open exactly as inherited.

## User Setup Required

None for this plan. The two follow-up todos each name what they need: live Snowflake credentials for the introspection cassette, and a live Databricks workspace plus the Foundry ADBC shared library for the zero-row fallback.

## Task Commits

1. **Task 1: The normative decision doc and the two follow-up todos** — `f33d549` (docs)
2. **Task 2: The user-facing explanation page and the toctree entry** — `a9e1641` (docs)
3. **Task 3: Review gate approved; annotation-only scope recorded** — `d5dcc2c` (docs)

## Verification

- `just type-fidelity` then `git diff` on the artifact — byte-identical, no drift.
- Raw Arrow bypass: `pyarrow.ipc.open_file` on the committed Snowflake cassette prints `AGG("REVENUE"): decimal128(38, 0)`.
- Capability and comparison header tuples — intersection empty.
- Task 1 automated verify — three files exist; `decimal.Decimal` and `use_high_precision` present in the decision doc; `NUMBER(10,2)` present in the cassette todo.
- Task 2 automated verify — `just docs-build` exits 0 under `sphinx-build -W` with zero warnings; `type-fidelity` in the toctree; the `_explanation-type-fidelity:` anchor present.
- Both todos parse as YAML front matter (`created`, `title`, `area`, `files`) followed by markdown.
- `47-DECISIONS.md` structure: exactly 5 `## Decision` headings; `test_snowflake_engine.py` named once, in a sentence stating the mock was deliberately not used; `Evidence limitations carried forward` carries all six artifact gaps plus polars and the three open windows.
- `just test` — 1073 passed, 16 skipped (main suite); 16 passed, 15 skipped (jaffle-shop).
- `prek run --all-files` — clean.
- No `# type: ignore` or `# pyright: ignore` added; no source file under `src/` touched.

## Self-Check: PASSED

All four created files exist on disk. Both modified files exist. All three task commits (`f33d549`, `a9e1641`, `d5dcc2c`) resolve in `git log`. `47-DECISIONS.md` carries five `## Decision` headings, a `### Scope: this policy is annotation-only` subsection inside Decision 1 citing `src/semolina/cursor.py:281`, a three-row capability table with a version string per row and a staleness note naming `go/v0.1.3`, and an `## Evidence limitations carried forward` section. `docs/src/explanation/type-fidelity.rst` begins with the `.. _explanation-type-fidelity:` anchor, contains one `.. code-block:: python` and zero triple-backtick fences, one `.. note::`, and a "See also" section referencing `explanation-semantic-views`.

---
*Phase: 47-type-fidelity-probe-decision-doc*
*Completed: 2026-08-12*
