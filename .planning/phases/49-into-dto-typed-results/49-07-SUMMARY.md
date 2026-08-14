---
phase: 49-into-dto-typed-results
plan: 07
subsystem: docs
tags: [sphinx, diataxis, arrowmodel, pydantic, pyarrow, pandas, polars, packaging]

requires:
  - phase: 49-into-dto-typed-results
    provides: "Plans 01-06 — the `.into()` / `iter_into()` surface on both cursors, the four extras, the schema pre-check in dto.py, the two new errors, and the pyarrow/pandas/polars guards on the Arrow methods"
  - phase: 47-type-fidelity-probe-decision-doc
    provides: "the Decimal policy and the measured Arrow nullable-flag finding the explanation page's new section rests on"
provides:
  - "docs/src/how-to/typed-results.rst — the worked BI-backend example in four forms (DTO-06)"
  - "the corrected `[arrowmodel]` extra: it now composes `semolina[pyarrow]`, so one command actually enables `.into()`"
  - "arrow-output.rst leading with fetch_df() / fetch_polars() (RESULT-01's docs ask)"
  - "installation.rst documenting all four result extras (DTO-05's user-facing half)"
  - "type-fidelity.rst explaining what the DTO schema pre-check promises and what it deliberately does not"
  - "the two folded todos retired to .planning/todos/completed/ with accurate records"
affects: [50-codegen-dtos, v0.7-milestone-close]

actuals:
  tokens: 21945
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "An extra that names a feature must install everything that feature needs — `[arrowmodel]` composes `semolina[pyarrow]` the way `[duckdb]` already did"
    - "Every column name quoted in a doc page is read from a committed cassette, not derived from the dialect code"

key-files:
  created:
    - docs/src/how-to/typed-results.rst
  modified:
    - pyproject.toml
    - uv.lock
    - tests/unit/test_dto_packaging.py
    - docs/src/how-to/index.rst
    - docs/src/how-to/arrow-output.rst
    - docs/src/how-to/streaming.rst
    - docs/src/tutorials/installation.rst
    - docs/src/explanation/type-fidelity.rst
    - .planning/todos/completed/2026-07-10-arrowmodel-result-serialization-integration.md
    - .planning/todos/completed/2026-05-15-fetch-df-and-fetch-polars-adbc-passthrough.md
    - .planning/todos/pending/2026-02-25-runtime-type-coercion-validation-on-row-construction.md

key-decisions:
  - "49-07: the `[arrowmodel]` extra now composes `semolina[pyarrow]` (orchestrator-directed, user-approved). Both DTO methods guard pyarrow BEFORE arrowmodel, so the extra named for DTO support did not enable it — `pip install semolina[snowflake,arrowmodel]` reached SemolinaMissingDependencyError on the first `.into()`. Extras are new this phase and unreleased, so nothing breaks."
  - "49-07: the worked example uses the sibling pages' `Sales` model (revenue + country) rather than jaffle-shop's `Orders`, against the plan's docs-shape preference. The must_haves truth requires the cassette-verified string `AGG(\"REVENUE\")`, and `Sales.revenue` / `Sales.country` are exactly the two columns the committed Snowflake cassette carries — so every column name on the page is measured rather than derived from dialect code."
  - "49-07: the alias section is a measured three-warehouse table, not a Snowflake footnote — Snowflake `AGG(\"REVENUE\")` / `COUNTRY`, Databricks `measure(revenue)` / `country`, DuckDB bare names, each read from a committed cassette. The dimension column differs too, which the plan did not anticipate."
  - "49-07: Diataxis classification confirmed as how-to against the skill's own table, agreeing with the planner's reading; toctree placed after `serialization` and before `arrow-output`."
  - "49-07: an unverified GIL-release claim about arrowmodel was cut from the async section during the humanizer pass — nothing in this phase measured it."
  - "49-07: the retired RESULT-01 todo records one acceptance line as only partly met — no per-backend integration test calls fetch_df/fetch_polars — rather than claiming coverage that does not exist."
  - "49-07: todo-retirement convention found and followed is `git mv` from `pending/` to `completed/` plus an `updated:` frontmatter key and a leading `## Status` section (the 2026-08-12 precedent). The older `done/` directory is v0.2-era and was not used."

patterns-established:
  - "Warehouse-specific column names in docs are quoted from committed cassettes and named as such, so a dialect change makes the page stale rather than silently wrong"
  - "A docs claim about library behaviour that this project has not measured does not go in the page, even when it is probably true"

requirements-completed: [DTO-06]

coverage:
  - id: D1
    description: "A how-to page presents `.into(DTO)` as the primary typed-result path with one worked BI-backend scenario in four forms — whole-result, streaming, and both async twins (DTO-06)"
    requirement: DTO-06
    verification:
      - kind: other
        ref: "just docs-build (sphinx-build -W)"
        status: pass
      - kind: other
        ref: "grep: .into( x5, iter_into( x5, await x8, 'async for' x2 in docs/src/how-to/typed-results.rst"
        status: pass
    human_judgment: true
    rationale: "Whether the page reads correctly for data/analytics engineers is editorial. The plan's own flagged assumption names this as a manual verification: the docs skill's workflow plus a humanizer pass is the mitigation, a human read is the check."
  - id: D2
    description: "The worked example survives leaving DuckDB: it carries `Field(validation_alias='AGG(\"REVENUE\")')` and a measured per-warehouse column-name table"
    requirement: DTO-06
    verification:
      - kind: other
        ref: "pyarrow.ipc.open_file over tests/integration/cassettes/.../test_snowflake_probe and .../async_streaming_iteration_databricks — column names read, not derived"
        status: pass
      - kind: unit
        ref: "tests/unit/test_dto.py (Plan 02's alias tests, unchanged by this plan)"
        status: pass
    human_judgment: false
  - id: D3
    description: "`[arrowmodel]` composes `semolina[pyarrow]`, so `pip install semolina[arrowmodel]` actually enables `.into()`"
    verification:
      - kind: unit
        ref: "tests/unit/test_dto_packaging.py::test_packaging_arrowmodel_extra_reaches_pyarrow"
        status: pass
      - kind: unit
        ref: "tests/unit/test_dto_packaging.py::test_packaging_declares_arrowmodel_extra"
        status: pass
      - kind: other
        ref: "uv lock — resolved arrowmodel extra now includes pyarrow"
        status: pass
    human_judgment: false
  - id: D4
    description: "The docs never present `validate=True` as the safe mode for a money column, and name the schema pre-check as what protects it"
    verification:
      - kind: other
        ref: "docs/src/how-to/typed-results.rst 'What validate=True does, and what it does not' + docs/src/explanation/type-fidelity.rst 'What a DTO's annotations are checked against'"
        status: pass
    human_judgment: true
    rationale: "A prohibition on a framing cannot be asserted by a command — a page can satisfy every grep and still leave the wrong impression. This is the phase's highest-severity threat (T-49-01) and warrants a human read."
  - id: D5
    description: "arrow-output.rst prefers fetch_df() / fetch_polars(), names the extras, and carries the polars first-consuming-call rule and the Decimal difference"
    verification:
      - kind: other
        ref: "grep: fetch_polars first at line 13, manual pl.from_arrow at line 142; semolina[polars] present"
        status: pass
      - kind: other
        ref: "just docs-build"
        status: pass
    human_judgment: false
  - id: D6
    description: "installation.rst documents all four new extras and states that a plain install brings none of them (DTO-05's user-facing half)"
    verification:
      - kind: other
        ref: "tomllib cross-check: every `semolina[...]` string in the four touched pages names an extra declared in pyproject.toml; all four extras present in installation.rst"
        status: pass
    human_judgment: false
  - id: D7
    description: "Both folded todos retired by the repo's own convention with accurate notes; the deferred coercion todo untouched in pending/"
    verification:
      - kind: other
        ref: "ls .planning/todos/completed/ and .planning/todos/pending/ — both retired files present in completed/, 2026-02-25-runtime-type-coercion... still in pending/"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-14
status: complete
---

# Phase 49 Plan 07: Docs for typed results Summary

**A new `typed-results` how-to carrying one BI-backend scenario through `.into()`, `iter_into()` and both async twins, with the Snowflake alias trap, the `validate=True` money trap and the two `JsonValue` spellings in the prose — plus a packaging fix that makes `pip install semolina[arrowmodel]` actually work.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-14T08:45:00Z (approx)
- **Completed:** 2026-08-14T09:09:06Z
- **Tasks:** 3 (plus one authorized scope addition)
- **Files modified:** 13 (12 plus `uv.lock`)

## Accomplishments

- `docs/src/how-to/typed-results.rst` presents `.into(DTO)` as the typed-result path, one scenario in four forms, with the four hard-won facts as prose rather than asides.
- The `[arrowmodel]` extra was a broken promise and now is not. It installed arrowmodel but not pyarrow, while both DTO methods guard pyarrow *first* — so the extra advertising DTO support raised `SemolinaMissingDependencyError` on the very call it advertised.
- The alias section is a measured three-warehouse table rather than a Snowflake aside. Databricks and the dimension columns both diverge from what the plan predicted, and both are now on the page.
- `arrow-output.rst` leads with `fetch_df()` / `fetch_polars()`, closing the RESULT-01 todo's docs ask, and a false claim on that page ("no extra dependencies beyond the backend driver") was corrected.
- The explanation page now covers what the schema pre-check promises, the two things it deliberately stays silent about, and why validation cannot substitute for it.

## Task Commits

1. **Scope addition: `[arrowmodel]` composes `semolina[pyarrow]`** — `cda10cc` (fix)
2. **Task 1: the typed-results how-to, worked example in four forms** — `2c87274` (docs)
3. **Task 2: point arrow-output, streaming and installation at the new surface** — `88f48a4` (docs)
4. **Task 3: the explanation page's typed-result section, and retire two folded todos** — `0af9978` (docs)

## Files Created/Modified

- `docs/src/how-to/typed-results.rst` — NEW. The worked BI-backend example, the alias table, the `validate=` tradeoff, the `JsonValue` warning, and the mismatch-error walkthrough.
- `docs/src/how-to/index.rst` — one toctree entry, placed between `serialization` and `arrow-output`.
- `docs/src/how-to/arrow-output.rst` — leads with the two passthrough methods; adds the polars first-consuming-call rule and the Decimal difference; corrects the pyarrow-dependency claim; demotes but keeps the manual conversion route.
- `docs/src/how-to/streaming.rst` — `iter_into()` added as a third entry point; the shared-stream bullet now names `into()` and `iter_into()`.
- `docs/src/tutorials/installation.rst` — a new `Optional: dataframes and typed results` section with a `tutorial-installation-result-extras` label; all four extras, one honest line per floor.
- `docs/src/explanation/type-fidelity.rst` — a `What a DTO's annotations are checked against` section between the Decimal section and `What can be NULL`.
- `pyproject.toml`, `uv.lock` — the `[arrowmodel]` composition.
- `tests/unit/test_dto_packaging.py` — asserts the composition rather than leaving it to a comment.
- Two todos retired to `.planning/todos/completed/`; one cross-reference added to the todo that stays deferred.

## Decisions Made

**The Diataxis classification.** Confirmed as a how-to against the skill's own table, agreeing with the planner's reading in `<flagged_assumptions>`. The reader has a semantic layer, a query that already runs, and a goal ("give my API layer typed objects"), and supplies their own setup. Snippets are illustrative rather than runnable, which is the how-to contract in `CLAUDE.md`. The `validate=` tradeoff and the pre-check's promises went to the explanation page in Task 3, as planned.

**The toctree placement.** After `serialization`, before `arrow-output`. That is the path a reader walks: I have rows, I have typed objects, I have Arrow. `serialization` is the untyped predecessor and links forward; `arrow-output` is the escape hatch for anyone who wants the buffers rather than the objects.

**The example's schema.** The plan preferred jaffle-shop's models for realism, calling it "a docs-shape preference rather than a finding". A `must_haves` truth requires the cassette-verified string `AGG("REVENUE")`, which jaffle-shop's `Orders.order_total` cannot supply. The sibling how-to pages already reuse a `Sales` model with `revenue` and `country`, and the committed Snowflake cassette carries exactly those two columns. Choosing it keeps one schema across four how-to pages and makes every column name on the page a measured value.

**Humanizer pass: applied.** The skill was loaded and its checklist run over the new page. What it changed: a `.. danger::` directive switched to `.. warning::` (the rest of the docs use four admonition types and `danger` was not one), two em dashes removed, a vague "One case surprises people" replaced with the rule it introduces, and an unverified claim that arrowmodel releases the GIL during conversion cut outright. That last one is worth flagging — it is probably true and the phase measured nothing that supports it.

**The todo-retirement convention.** `git mv` from `.planning/todos/pending/` to `.planning/todos/completed/`, add an `updated:` key to the frontmatter, and lead the body with a `## Status` section. That is the shape of `2026-08-12-type-fidelity-code-review-findings.md`, the most recent retirement. The parallel `done/` directory is v0.2-era (every file in it landed in one commit on 2026-02-26) and was not used.

## Deviations from Plan

### Authorized scope addition

**1. [Orchestrator-directed, user-approved] `[arrowmodel]` now composes `semolina[pyarrow]`**
- **Found during:** Plan 04, which surfaced it as an "open gap, surfaced not closed"; decided by the user before this plan started.
- **Issue:** `cursor.py:378-379` and `455-456` (and the async twins) call `_require("pyarrow", ...)` before `_require("arrowmodel", ...)`. The `[arrowmodel]` extra installed arrowmodel alone, so `pip install semolina[snowflake,arrowmodel]` reached `SemolinaMissingDependencyError` on the first `.into()` — the extra existing to enable DTO support did not enable it.
- **Fix:** `[arrowmodel]` now lists `semolina[pyarrow]` alongside `arrowmodel>=1.0.0`, the same composition `[duckdb]` already used, with a comment explaining the guard order. `uv.lock` regenerated in the same commit because CI runs `uv sync --locked`.
- **Files modified:** `pyproject.toml`, `uv.lock`, `tests/unit/test_dto_packaging.py`
- **Verification:** `tests/unit/test_dto_packaging.py::test_packaging_arrowmodel_extra_reaches_pyarrow` (new) plus the updated equality assertion; the lock diff shows `pyarrow` under the resolved `arrowmodel` extra.
- **Committed in:** `cda10cc`

The extras are new in this phase and have never been released, so this breaks no existing install.

### Auto-fixed Issues

**2. [Rule 1 - Bug] `arrow-output.rst` claimed `fetch_arrow_table()` needs no extra dependencies**
- **Found during:** Task 2
- **Issue:** The page said "``fetch_arrow_table()`` delegates to the underlying ADBC cursor. No extra dependencies beyond the backend driver are needed." Plan 05 put a `_require("pyarrow", "pyarrow")` guard on that method, so the sentence became false in this phase. A reader on `semolina[snowflake]` would follow it into the error.
- **Fix:** Replaced with the real requirement, naming `semolina[pyarrow]` and noting that `semolina[duckdb]` already brings it.
- **Files modified:** `docs/src/how-to/arrow-output.rst`
- **Verification:** `just docs-build`; the guard read from `src/semolina/cursor.py:182`.
- **Committed in:** `88f48a4`

**3. [Rule 1 - Bug] An acceptance claim in the retired RESULT-01 todo was not true as first written**
- **Found during:** Task 3
- **Issue:** The retirement note initially recorded "Tests across all three backends" as satisfied. Grepping the test tree showed no integration test calls `fetch_df` or `fetch_polars` at all — coverage is unit tests on both cursors plus one live DuckDB measurement in `tests/type_fidelity_probe.py`.
- **Fix:** The note now records that line as partly met, names what does cover the methods, and gives the reason it was accepted (both are pure ADBC passthroughs with no Semolina-side branch by backend).
- **Files modified:** `.planning/todos/completed/2026-05-15-fetch-df-and-fetch-polars-adbc-passthrough.md`
- **Verification:** `grep -rln "fetch_polars\|fetch_df" tests/` returns only unit tests and the probe.
- **Committed in:** `0af9978`

**4. [Rule 2 - Missing critical] The `typed-results` See-also had no anchor to link to**
- **Found during:** Task 2
- **Issue:** Task 1's plan text asks the page to link "the installation page's extras section", which did not exist until Task 2 created it. Task 1 shipped with a link to the whole installation page rather than a forward reference that would have failed `sphinx-build -W`.
- **Fix:** Task 2 added the `tutorial-installation-result-extras` label and re-pointed the See-also line at it. This touches `typed-results.rst`, which is not in Task 2's declared file list.
- **Files modified:** `docs/src/tutorials/installation.rst`, `docs/src/how-to/typed-results.rst`
- **Verification:** `just docs-build`
- **Committed in:** `88f48a4`

---

**Total deviations:** 1 authorized scope addition, 3 auto-fixed (2 bugs, 1 missing critical)
**Impact on plan:** The scope addition was pre-authorized and is the difference between an extra that works and one that does not. The two bug fixes are both cases of this phase's own work falsifying a committed claim. No scope creep.

## Issues Encountered

**The `AGG("REVENUE")` requirement and the jaffle-shop preference could not both be honoured.** Resolved in favour of the `must_haves` truth, using the model the sibling how-to pages already share. Recorded above under Decisions.

**The plan predicted only the Snowflake metric column would need an alias.** Reading the cassettes showed the Snowflake *dimension* column also diverges (`COUNTRY`, upper-cased), and Databricks diverges differently again (`measure(revenue)`, lower case, dimension untouched). The page carries all six measured spellings rather than the one the plan named.

**`blacken-docs` reformats RST code blocks at line length 60** and rejected the first draft's query-chain line breaks. It rewrote them; the rewritten form is what shipped.

## User Setup Required

None.

## Next Phase Readiness

DTO-06 is complete and Phase 49's docs are done. Phase 50 (codegen'd DTOs) inherits a documented public surface it can point at rather than describe: `docs/src/how-to/typed-results.rst` is where a generated DTO's alias story belongs, and the alias table there is the fact a generator has to reproduce.

Two things a verifier should look at rather than take on trust:

- The new page has not been read by a human. That is the plan's own flagged manual verification, and D1 and D4 in the coverage block route to it.
- `semolina[pandas]` on its own still does not enable `fetch_df()`, which needs pyarrow as well. The docs say so plainly in two places. Whether `[pandas]` should compose `semolina[pyarrow]` the way `[arrowmodel]` now does is the same question the user just answered for arrowmodel, and it was deliberately not extended here without authorization.

---
*Phase: 49-into-dto-typed-results*
*Completed: 2026-08-14*

## Self-Check: PASSED

All 9 declared artifacts exist on disk; all 5 commits resolve in `git log`.
