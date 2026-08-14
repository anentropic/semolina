---
phase: 49-into-dto-typed-results
plan: 03
subsystem: evidence
tags: [polars, decimal, type-fidelity, probe, measurement, decision-record, broken-windows]

requires:
  - phase: 47-type-fidelity-probe-decision-doc
    provides: "The type-fidelity probe, its Downstream Decimal section, and assumption A3 left open because polars was not installed"
  - phase: 49-into-dto-typed-results
    plan: 01
    provides: "The [polars] and [pandas] extras inside [all], and the sync that put polars 1.43.2 in .venv — the one thing A3 was blocked on"
provides:
  - "A measured polars row in 47-TYPE-FIDELITY.md: decimal128 maps to a native Decimal(precision=38, scale=2) dtype holding decimal.Decimal"
  - "_measure_polars(table) — a real measurement replacing a hard-coded not-measured row"
  - "Dated in-body corrections in 47-DECISIONS.md closing A3 without editing the original text"
  - "The evidence Plan 05 needs to decide whether fetch_polars() owes a Decimal caveat"
affects: [49-05-fetch-df-polars, 49-07-docs, 50-codegen-dtos]

actuals:
  tokens: 8374
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Fix the generator, not the artifact: prose in a generated document is edited in the function that emits it, or --check re-emits the stale text"
    - "Correct an approved decision record by addition — a dated correction beneath the original, never a rewrite"

key-files:
  created:
    - .planning/phases/49-into-dto-typed-results/49-03-SUMMARY.md
  modified:
    - tests/type_fidelity_probe.py
    - .planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md
    - .planning/phases/47-type-fidelity-probe-decision-doc/47-DECISIONS.md
    - .planning/WINDOWS.md

key-decisions:
  - "polars' DataFrame | Series union is narrowed with isinstance + get_column, not silenced with Any or a type: ignore — and from_arrow is kept as the measured call because it is the call fetch_polars() itself makes"
  - "The decimal256 Rust panic is recorded as one conditional clause inside the closing paragraph, not as its own paragraph or admonition — a hazard no supported backend can reach does not get a banner"
  - "The decimal256 clause names its provenance (measured during Phase 49 research) rather than implying this probe exercised it"
  - "WINDOWS.md entry 10 was closed alongside entry 3: it is this plan's own deliverable, and leaving it open would have been a broken window about a fixed broken window"
  - "47-DECISIONS.md:126's pydantic 2.12.5 citation was left uncorrected — it is a true record of when the measurement was taken, not a claim a reader can act on wrongly"

patterns-established:
  - "A generated document's prose and its table move in one commit, because --check diffs the whole rendered text and not just the rows"

requirements-completed: []

coverage:
  - id: E1
    description: "The committed artifact's polars row is a real measurement naming the polars version, the observed dtype and the observed element type"
    requirement: RESULT-01
    verification:
      - kind: other
        ref: "grep '^| polars |' .planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md"
        status: pass
      - kind: unit
        ref: "tests/unit/test_type_fidelity_table.py::test_committed_table_is_not_stale"
        status: pass
    human_judgment: false
  - id: E2
    description: "The artifact regenerates byte-identically from the committed generator — the prose was fixed in render_downstream_decimal, not in the markdown"
    verification:
      - kind: other
        ref: "uv run python tests/type_fidelity_probe.py --check"
        status: pass
      - kind: unit
        ref: "tests/unit/test_type_fidelity_table.py::test_regeneration_is_deterministic"
        status: pass
    human_judgment: false
  - id: E3
    description: "47-DECISIONS.md's two stale polars statements carry a dated correction beneath the original, and the diff for that file deletes nothing"
    verification:
      - kind: other
        ref: "git diff --numstat HEAD~1 HEAD -- .planning/phases/47-type-fidelity-probe-decision-doc/47-DECISIONS.md → 14 0"
        status: pass
    human_judgment: true
    rationale: "That the correction is placed and worded so a reader cannot act on the stale line, while the original still reads as the record of what was known, is a judgment about documentation form. The additive-diff half is machine-checked; the readable-supersession half is not."

duration: 13min
completed: 2026-08-14
status: complete
---

# Phase 49 Plan 03: Closing Assumption A3 by Measurement Summary

**polars 1.43.2 gives a warehouse `decimal128(38, 2)` metric a native `Decimal(precision=38, scale=2)` dtype holding `decimal.Decimal` — measured on the live probe result, put in the committed artifact, and used to correct two statements in an approved decision record without editing either of them.**

## Performance

- **Duration:** ~13 min
- **Tasks:** 2, both `type="auto"`, no checkpoints
- **Files modified:** 4 (1 created, 4 modified)

## Task Commits

1. **Task 1: Measure polars for real and regenerate the artifact** — `ba9eadc` (test)
2. **Task 2: Dated corrections in 47-DECISIONS.md** — `e46540a` (docs)

## The measurement, literally as committed

The polars observed cell, byte-for-byte from `47-TYPE-FIDELITY.md:200`:

```
| polars | polars 1.43.2: dtype `Decimal(precision=38, scale=2)`, elements `decimal.Decimal` | measured | A3 |
```

It matches `49-RESEARCH.md` § Q6 exactly, and it was produced by really calling
`polars.from_arrow(table)` on the same probe table the pandas and pydantic rows describe —
not copied from RESEARCH.md. A3's answer is **positive and better than pandas'**: pandas
falls back to an untyped `object` column, polars carries a typed decimal column.

**What this means for Plan 05.** `fetch_polars()` needs no precision caveat. The Decimal
survives, and RESEARCH.md § Q6 further measured it surviving `sum()`, `group_by().agg()` and
arithmetic. The only caveat available to write is the conditional `decimal256` one, and it is
unreachable on all three supported backends.

## Every cell that moved in the artifact diff

Three, exactly as the plan predicted — and **nothing moved in `## Field type comparison`**,
which was the finding to look for:

| Row / region | Before | After |
|---|---|---|
| `polars` observed | `not measured — polars not installed` | `polars 1.43.2: dtype \`Decimal(precision=38, scale=2)\`, elements \`decimal.Decimal\`` |
| `polars` status | `not measured` | `measured` |
| `pydantic` observed | `pydantic 2.12.5: …` | `pydantic 2.13.4: …` |
| closing prose | A3 "stays open"; pandas "not a declared dependency … arrives transitively through `databricks-sql-connector[pyarrow]`" | A1/A2/A3 all closed, A3's answer named, `decimal256` condition noted; both extras named as the declared route |

The pydantic move is the arrowmodel-driven floor bump from Plan 01 landing in the same
regeneration. Expected, recorded, not fought.

**Surviving `not measured` occurrences: exactly one**, at line 218, and it is prose, not a
table cell:

> `--extra all` will legitimately flip them to `not measured`, and that is the artifact
> reporting its environment rather than a fault.

## The generator, not just the artifact

Two sentences in `render_downstream_decimal` *generated* claims this phase falsifies, so
editing the markdown alone would have failed `--check` on the next run:

1. **"A3 stays open"** → all three assumptions now close, A3's answer is named, and one
   clause records the `decimal256` `PanicException` with its provenance (measured during
   Phase 49 research, not by this probe) and the reason it is unreachable — Snowflake
   `NUMBER` stops at precision 38, and no Databricks decimal column has ever been recorded
   here. One clause inside the paragraph, deliberately not a banner.
2. **"pandas is not a declared dependency … arrives transitively"** → both pandas and polars
   are now published extras inside `all`. The honest half is kept: a sync omitting
   `--extra all` still flips both rows to `not measured`, and that is the artifact reporting
   its environment.

## The corrections in 47-DECISIONS.md

**Date used on both: 2026-08-14.** Marker form copied from the `46-VERIFICATION.md`
precedent (a bold `**Correction — <ISO date> (<who>)**` lead-in, prose beneath the text it
supersedes), adapted from a trailing section to an indented in-body block so no heading is
renumbered and no bullet moves.

- **Correction 1**, beneath Decision 1's polars bullet (`:141`): states the measured
  behaviour in the artifact's own terms, points at `47-TYPE-FIDELITY.md` § "Downstream
  Decimal behaviour", names Phase 49's `polars` extra as what made it possible, carries the
  `decimal256` condition, and says plainly that the bullet above is left as the record of
  what was known.
- **Correction 2**, beneath the "polars is unmeasured (assumption A3)" bullet in the "Two
  further limits" block (`:366`): two lines, cross-referencing correction 1 rather than
  restating the measurement.

**The diff deletes nothing: `git diff --numstat` reads `14  0`.** No original line was
reflowed, rewritten or removed.

## Broken windows closed

| Entry | Why it closed |
|---|---|
| 3 | The "pandas is not a declared dependency" premise is gone — Plan 01 published `[pandas]` inside `[all]` (D-12) and this plan regenerated the artifact so its caveat names the extra. What remains, stated in the prose, is that a sync omitting `--extra all` still flips the row — now a declared install choice rather than an undeclared transitive accident. |
| 10 | `--check` is green; `_measure_polars` was edited, not just the artifact. |

Both were closed with `gsd-tools windows fixed <id>`, with the closure reasoning appended to
each description first (Phase 48's precedent — the tool has no description-edit verb).
`open_count` moved 10 → 8.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] basedpyright strict rejects the plan's literal `_measure_polars` body**
- **Found during:** Task 1
- **Issue:** The plan specifies `polars.from_arrow(table)[DECIMAL_PROBE_FIELD]`. `from_arrow`
  is annotated `-> DataFrame | Series` **unconditionally** (no overloads — read from the
  installed source), so indexing the union resolves against `Series.__getitem__`, which
  rejects a `str` key. Two `reportCallIssue` / `reportArgumentType` errors.
- **Fix:** Narrowed the union honestly instead of silencing it — `assert isinstance(frame,
  polars.DataFrame)` then `frame.get_column(DECIMAL_PROBE_FIELD)`. No `# type: ignore`, no
  `Any` for the frame. `from_arrow` was **kept** as the measured call rather than switching to
  the `polars.DataFrame(table)` form polars' own docstring suggests for this exact typing
  problem, because `from_arrow` is the call ADBC's `fetch_polars()` makes and the probe should
  measure the shipping path. A comment records both points.
- **Files modified:** `tests/type_fidelity_probe.py`
- **Verification:** `prek run --all-files` → basedpyright Passed.
- **Committed in:** `ba9eadc`

**2. [Rule 2 — Missing] WINDOWS.md entry 10 closed as well as entry 3**
- **Found during:** Task 1
- **Issue:** The plan names only entry 3. Entry 10 records this exact `--check` failure and
  names Plan 03 as its owner; leaving it open would be a broken window about a closed one.
- **Fix:** Closed with the same convention and the same closure-note treatment.
- **Committed in:** `ba9eadc`

---

**Total deviations:** 2 auto-fixed. No scope creep; the measurement itself is exactly what
the plan specified.

## Findings recorded rather than fixed

**1. `47-DECISIONS.md:126` still cites "measured at pydantic 2.12.5 in `47-TYPE-FIDELITY.md`",
and the artifact now reads 2.13.4.** Deliberately not corrected. Unlike the polars bullet, the
sentence is not a claim a reader can act on wrongly — pydantic v2 does handle `Decimal` fields
natively, and 2.12.5 is a true record of the version the measurement was taken at. The plan
named two statements and warned against making one fact live in three places; the artifact
itself carries the current version. Flagged here so a future reader following the citation is
not surprised.

**2. The second bullet of the "Two further limits" block still says window 3 remains open**,
which Task 1 closed. Left untouched because the plan explicitly prohibits adding a third
correction there ("`WINDOWS.md` is where that closure is recorded"), and correction 2 sits
directly above it carrying the date. Self-correcting for any reader who checks the ledger.

**3. `gsd-tools windows` is absent from the CLI's own command list** but present and
functional (`windows fixed <id>` returned the updated ledger). Noted so a future agent does
not conclude from `--help` that the verb was removed and hand-edit the ledger instead.

## Verification Results

| Gate | Result |
|---|---|
| `uv run python tests/type_fidelity_probe.py --check` | exit 0 |
| `uv run pytest tests/unit/test_type_fidelity_table.py -x -q` | 9 passed, **none skipped** |
| `uv run pytest -q` (root) | **1350 passed, 16 skipped, 2 xfailed, 0 failed** |
| `just test` (jaffle-shop half) | 16 passed, 15 skipped |
| `prek run --all-files` | all hooks passed, incl. basedpyright strict, **no suppression comment added** |
| `git diff --numstat` on `47-DECISIONS.md` | `14  0` — zero deletions |
| `git show --stat ba9eadc` | lists `tests/type_fidelity_probe.py` **and** `47-TYPE-FIDELITY.md` |

The inherited RED test is closed: the root suite went from `1 failed, 1349 passed` to
`1350 passed`, and it was closed by making the measurement real, not by weakening the
staleness gate — `test_committed_table_is_not_stale` is unmodified.

## Known Stubs

None. `_measure_polars` no longer returns a hard-coded string on either branch: the present
branch measures, and the absent branch reports an honest environment fact.

## Requirement Status

`RESULT-01` is left **Pending**. This plan is its *evidence source*, not its implementation —
`fetch_polars()` ships in Plan 05, which owns the requirement. Following the phase's standing
precedent that a box is ticked for shipped, measured work only.

## Next Phase Readiness

Ready, and Plan 05 is now unblocked on the question it could not answer:

- **`fetch_polars()` needs no precision caveat.** Decimal survives `from_arrow` as a typed
  column. If a caveat is written at all, it is the conditional `decimal256` one, worded as
  unreachable rather than as a hazard.
- **Plan 05 should call `polars.from_arrow`,** which is what ADBC does and what is now
  measured — and should expect the same `DataFrame | Series` typing friction if it annotates a
  return type (Pitfall: the union is unconditional).
- **Plan 07 (docs)** can state the polars Decimal behaviour as measured fact with a citation
  that now resolves.

## Self-Check: PASSED

All four claimed files exist on disk (`tests/type_fidelity_probe.py`, `47-TYPE-FIDELITY.md`,
`47-DECISIONS.md`, `.planning/WINDOWS.md`) and this SUMMARY was written. Both claimed commits
resolve in `git log`: `ba9eadc`, `e46540a`.

---
*Phase: 49-into-dto-typed-results*
*Completed: 2026-08-14*
