---
phase: 46-async-query-surface
plan: 07
subsystem: testing
tags: [phase-gate, packaging, cassettes, anyio, trio, gsd-tooling, git]

# Dependency graph
requires:
  - phase: 46-async-query-surface (plan 01)
    provides: the async extra, the poolhouse floor, the TID251 Posture A gate, the ASYNC-04 packaging test
  - phase: 46-async-query-surface (plan 03)
    provides: the recorded cassette-tree digest this gate re-checks, and the four copied cassette trees
  - phase: 46-async-query-surface (plan 04)
    provides: the async registry and _Query.aexecute the full suite exercises
  - phase: 46-async-query-surface (plan 05)
    provides: the loop-matrix invariant this gate runs against the complete module set, and the measured cancellation baseline
  - phase: 46-async-query-surface (plan 06)
    provides: the async documentation the strict docs build compiles
provides:
  - an executed phase-level gate result covering all six sibling plans at once, recorded command by command
  - the loop-matrix invariant's first run against the complete set of async test modules (5 modules, both waves)
  - proof that no plan in the phase wrote to the cassette trees — digest identical to Plan 03's recorded value
  - "`git.branching_strategy` restored to `milestone`, as the phase's final commit"
affects: [gsd-tooling, git-workflow, ci, async, testing]

actuals:
  tokens: 6100
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "phase-close gate: run every plan's verification together at the end, because cross-plan invariants (a structural checker's module set, a shared artifact's digest) are only complete once every plan has landed"
    - "record the command and its output, not the conclusion — a gate that reports 'green' without the numbers cannot be audited later"

key-files:
  created:
    - .planning/phases/46-async-query-surface/46-07-SUMMARY.md
  modified:
    - .planning/config.json
    - .planning/phases/46-async-query-surface/deferred-items.md

key-decisions:
  - "The packaging metadata assertion was run against 1.6.2 rather than the 1.6.1 the plan's criterion names, because the orchestrator's floor bump (00b0b31) moved both pins after the plan was written; the criterion's intent — base and async extra agree on one pinned floor, and `all` includes async — is what was checked"
  - "The config flip was committed with plain `git commit`, not the GSD helper, because the helper reads the value the same task just changed"
  - "TOOL-01 is marked complete in the docs commit that immediately precedes the flip, since nothing may follow the flip in this phase"

patterns-established:
  - "A gate task that declares no files still produces a deliverable: the recorded result, including every skip named with its reason"

requirements-completed: [TOOL-01]

coverage:
  - id: D1
    description: "The whole phase holds together at once — the full suite, the quality gate, the strict docs build, and the packaging smoke assertion are all green simultaneously"
    verification:
      - kind: other
        ref: "just test → 1029 passed / 16 skipped (root) + 16 passed / 15 skipped (jaffle-shop)"
        status: pass
      - kind: other
        ref: "prek run --all-files → all hooks Passed"
        status: pass
      - kind: other
        ref: "just docs-build → build succeeded under sphinx-build -W"
        status: pass
      - kind: other
        ref: "local reproduction of the CI packaging-smoke base-install assertion in a throwaway venv → OK, no anyio spec"
        status: pass
    human_judgment: false
  - id: D2
    description: "The loop-matrix invariant passes against the complete set of async test modules, including the ones sibling plans landed in parallel waves"
    requirement: ASYNC-05
    verification:
      - kind: unit
        ref: "tests/unit/test_asyncio_trio_matrix.py → 3 passed; _async_test_modules() selects 5 modules spanning waves 2, 3 and 4"
        status: pass
    human_judgment: false
  - id: D3
    description: "The copied cassette trees are byte-identical to their sources after every plan has run — nothing in the phase recorded live traffic"
    verification:
      - kind: other
        ref: "four-tree shasum digest = d81ddfd054f68538a13e653eeec4d5028411d28e, identical to Plan 03's recorded value; git status --porcelain tests/integration/cassettes empty"
        status: pass
    human_judgment: false
  - id: D4
    description: "`.planning/config.json` carries `git.branching_strategy` set to `milestone`, reverting the temporary `none` set during v0.6"
    requirement: TOOL-01
    verification:
      - kind: other
        ref: "uv run python -c \"import json; assert json.load(open('.planning/config.json'))['git']['branching_strategy']=='milestone'\" → TOOL-01 ok"
        status: pass
    human_judgment: false
  - id: D5
    description: "The configuration flip is the phase's final commit, one line, on the branch the phase was worked on"
    requirement: TOOL-01
    verification:
      - kind: other
        ref: "git show --stat HEAD → 1 file changed, 1 insertion(+), 1 deletion(-); git rev-parse --abbrev-ref HEAD = gsd/v0.7-milestone, unchanged across the commit"
        status: pass
    human_judgment: false

# Metrics
duration: 35min
completed: 2026-08-03
status: complete
---

# Phase 46 Plan 07: Phase Gate and TOOL-01 Summary

**Every plan's work verified together in one pass — full suite, quality gate, strict docs
build, packaging smoke, and an unwritten cassette tree — then the one-line revert of
`git.branching_strategy` as the phase's last commit**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-08-03
- **Tasks:** 2
- **Files modified:** 1 created, 2 modified (no source file)

## The gate, command by command

Run in cheapest-signal-first order. Every row is an observed result, not an assertion.

| # | Command | Result |
|---|---------|--------|
| 1 | `uv run pytest tests/unit -k async -q` | **103 passed**, 887 deselected, 16.37s |
| 2 | `uv run pytest tests/unit/test_asyncio_trio_matrix.py -q` | **3 passed**, 0.20s |
| 3 | `uv run pytest tests/integration -k async -q` | **8 passed**, 15 deselected |
| 4 | cassette four-tree digest | `d81ddfd054f68538a13e653eeec4d5028411d28e` — **identical** to Plan 03's recorded value |
| 5 | `git status --porcelain tests/integration/cassettes` | empty |
| 6 | `uv run ruff check src/semolina` (TID251 Posture A) | All checks passed |
| 7 | `prek run --all-files` | all hooks **Passed** (ShellCheck skipped — no shell files) |
| 8 | `just test` | root **1029 passed / 16 skipped** in 19.97s; jaffle-shop **16 passed / 15 skipped** in 0.53s |
| 9 | `just docs-build` (`sphinx-build -W`) | **build succeeded** |
| 10 | local packaging-smoke base-install reproduction | **OK** — see below |
| 11 | packaging metadata assertion | `packaging intact` at the landed 1.6.2 floor — see the deviation below |
| 12 | `git status --porcelain` after the gate | empty; the gate changed no source file |

### The loop-matrix invariant saw the whole phase for the first time

This was its first complete run. `_async_test_modules()` selects **5 modules**, and they
span three waves — so the invariant was genuinely incomplete when Plan 05 wrote it:

```
tests/integration/test_async_queries.py   (wave 3, Plan 03)
tests/unit/test_async_cancel.py           (wave 3, Plan 05)
tests/unit/test_async_cursor.py           (wave 2, Plan 02)
tests/unit/test_async_engine.py           (wave 2, Plan 02)
tests/unit/test_async_query.py            (wave 3, Plan 04)
```

Selection is by content, so `test_async_packaging.py` and the checker itself are correctly
outside the set despite their names. All five carry the anyio marker and a both-backends
fixture.

### Nothing in the phase wrote to a cassette

The digest of the four copied trees, recomputed after every plan has run:

```
Plan 03 recorded: d81ddfd054f68538a13e653eeec4d5028411d28e
46-07 gate:       d81ddfd054f68538a13e653eeec4d5028411d28e
```

`git status --porcelain tests/integration/cassettes` is empty. This was the last
opportunity to catch a plan having recorded live traffic, and it is checked rather than
assumed (T-46-05).

### The packaging smoke assertion reproduced locally

A throwaway venv outside the repository tree (`mktemp -d`), the project installed with no
extras, then CI's own assertion:

```
OK: base install imports semolina, no anyio spec
(no anyio in pip list)
```

The venv was removed afterwards and its absence confirmed. This reproduces the
`Base install pulls no anyio (ASYNC-04)` step of the `packaging-smoke` job.

### Cancellation, re-measured on this machine

Plan 05's fixture measures rather than assumes, so a re-run produces its own numbers:

| Quantity | Plan 05 recorded | 46-07 gate |
|----------|------------------|-----------|
| Cost rung reached | 4,000,000 rows, digest depth 32 | same — first rung cleared the floor |
| Uncancelled `semantic_view()` aggregate | 3.07s | **3.23s** |
| Uncancelled plain-SQL twin | 3.11s | **3.09s** |
| Deadline (measurement ÷ 10) | ~0.31s | ~0.31s |
| Cancelled call under that deadline | 0.317s (asyncio), 0.315s (Trio) | asserted, not printed — see below |

Within noise of Plan 05's numbers, and no rung was skipped. The abort-evidence assertion
(`elapsed < 0.5 × 3.09s = 1.55s`) held on both backends — that is what "10 passed" in
`tests/unit/test_async_cancel.py` means. **The exact cancelled elapsed is asserted inside
the test rather than printed**, so this gate cannot quote it without editing the test,
which a gate task must not do. What is recorded is what is observable: the fixture's
measurement, and the fact that the fivefold-margin assertion passed.

## Skips, each named with its reason

A skip nobody mentions is a gap, so:

- **16 skipped in the root suite** — all doctest `+SKIP` directives
  (`_pytest/doctest.py:458`), not credential gates. Unchanged from the baseline.
- **15 skipped in the jaffle-shop suite** — `tests/test_warehouse_queries.py`, gated on
  live warehouse credentials that are not present here.
- **ShellCheck hook skipped** — no shell files in scope.
- **The `[duckdb]`-extra half of the CI `packaging-smoke` job was not reproduced** — only
  the base-install / no-anyio assertion, which is the half the phase gate names for
  ASYNC-04. CI runs both on every push. Logged in `deferred-items.md`.
- **No live Databricks async verification** — the Databricks ADBC driver is
  Foundry-distributed, so cassette replay is the only path (a phase coverage caveat, not
  something this gate could close).
- **No cancellation test skipped** — the cost ladder's first rung cleared
  `MIN_MEASURED_SECONDS`, so the measure-then-skip arm did not fire.

## Task Commits

1. **Task 1: Run the phase gate and record the result** — no commit of its own. The task
   declares no files and changed none; its deliverable is this record, which lands in the
   docs commit below. `git status --porcelain` was empty before and after it.
2. **Task 2: Restore `git.branching_strategy` to `milestone`** — the phase's final commit,
   `.planning/config.json` only, one insertion and one deletion, made with plain
   `git commit` on `gsd/v0.7-milestone`.

Its hash is by construction not quotable here: this SUMMARY is committed immediately
before it, because nothing may follow the flip in this phase.

## Operator note — branch auto-switching is live again

**From the TOOL-01 commit onward, the GSD commit helper may switch branch at commit time**,
deriving a branch name from the STATE milestone and the ROADMAP heading. That is the
behaviour turned off during v0.6 after it stranded commits in Phase 44, and restoring it is
what TOOL-01 asked for.

Practical consequences:

- Branches have been managed manually since v0.6. That convention now conflicts with the
  tooling, which will act on its own.
- Any commit made after the flip — a state update, a phase manifest, a verifier artifact —
  is made under the new setting. This phase's own wrap-up was deliberately sequenced
  **before** it for exactly that reason (D-18).
- Work is currently on `gsd/v0.7-milestone`, which matches the milestone template
  (`gsd/{milestone}-{slug}` → `gsd/v0.7-async-typed-results`) only in prefix, not in full.
  The next GSD commit may therefore propose a *different* branch than the one v0.7 has been
  worked on. Watch the first one.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The packaging metadata criterion named a floor that had already moved**

- **Found during:** Task 1
- **Issue:** The plan's acceptance criterion asserts
  `s.startswith('adbc-poolhouse>=1.6.1')` and
  `od['async'] == ['adbc-poolhouse[async]>=1.6.1']`. Run verbatim it fails with
  `AssertionError` — because commit `00b0b31`, made by the orchestrator between Plans 05
  and 07 to unblock ASYNC-06, raised both pins to `>=1.6.2` (the upstream cancel-path
  deadlock fix, anentropic/adbc-poolhouse#43). The criterion was written before that bump.
- **Fix:** None to the code — the code is correct and the criterion is stale. The
  criterion's *intent* was checked instead: that the base dependency and the async extra
  still name the same pinned floor, and that `all` still includes async. At the landed
  floor:

  ```
  uv run python -c "... '>=1.6.2' ..."  →  packaging intact
  ```

  `[project] dependencies` carries `adbc-poolhouse>=1.6.2`, the `async` extra carries
  `adbc-poolhouse[async]>=1.6.2`, and `all` is
  `semolina[snowflake,databricks,duckdb,async]`. Both halves of the criterion's intent
  hold. The failing verbatim run is recorded here rather than quietly replaced, because a
  criterion that no longer matches reality is a finding in its own right.
- **Files modified:** none
- **Verification:** both commands above were run and both outputs are quoted.

---

**Total deviations:** 1 (a stale acceptance criterion, recorded rather than silently
rewritten). No source file changed in this plan.

## Coherence check on the phase's two recorded deviations

The prompt named two earlier deviations that must not be silently "fixed". Both were
checked for coherence and left alone:

1. **46-01's rewording of ROADMAP success criterion 4.** The criterion now describes the
   import-graph invariant TID251 actually enforces and names the residual dynamic-lookup
   gap. Verified coherent: `uv run ruff check src/semolina` passes, and the only
   `importlib.import_module` under `src/semolina/` is the codegen CLI's user-model loader
   (`cli/codegen.py:131`) — not an `asyncio` lookup by string, so the named residual gap is
   theoretical rather than present. The criterion also already carries the 1.6.2 floor.
2. **46-05's split of the ASYNC-06 claims and its elapsed-time comparison.** Verified
   coherent: `tests/unit/test_async_cancel.py` is 10 passed, the reach claim runs over the
   interruptible plain-SQL twin, and the `aexecute` test asserts transparency and pool
   recovery while explicitly making no early-abort claim. The re-measured numbers above
   reproduce Plan 05's within noise.

## Issues Encountered

**`WINDOWS.md` entry 1's stated cause is now stale.** It records the async
cancellation/timeout/client-disconnect docs as omitted *pending* adbc-poolhouse 1.6.2.
1.6.2 has since released, the floor moved to it, and Plan 05 measured the behaviour those
sections would describe. The entry stays `open` — the sections are genuinely still
unwritten — but it is now a writing task, not a wait, and it needs a follow-up doc plan
before `/gsd-ship`. Recorded in `deferred-items.md` rather than resolved here, because
resolving it means writing four documentation sections, which is not this plan's scope.

**Two stale `1.6.1` prose references survive.** `tests/conftest.py:222` and
`.planning/ROADMAP.md:143`. Neither is false — 1.6.2 subsumes 1.6.1 — and neither is a
criterion: ROADMAP success criterion 4 and `REQUIREMENTS.md` ASYNC-04 both carry 1.6.2
correctly. Not touched, because Task 1 declares no source file and its acceptance criteria
require no uncommitted source change attributable to it. Logged in `deferred-items.md`.

**A sequencing artifact worth naming.** TOOL-01 is checked off in `REQUIREMENTS.md` in the
docs commit that *precedes* the config flip. D-18 forbids anything following the flip, so
the two cannot both be last. The requirement is true one commit later than its checkbox
claims; the alternative — leaving the requirement dangling — would be worse for the
traceability table.

## User Setup Required

None.

## Next Phase Readiness

- **Phase 46 is closed.** All seven plans executed; ASYNC-01 through ASYNC-06 and TOOL-01
  are complete. Full suite 1029 passed / 16 skipped, quality gate clean, docs build clean
  under `-W`.
- **Watch the first GSD commit after this one** for an unexpected branch switch, per the
  operator note above.
- **Two open items carried out of the phase:** the four unwritten async cancellation doc
  sections (`WINDOWS.md` entry 1, now unblocked), and whether to file the DuckDB
  `semantic_views` non-interruptible table function upstream (Plan 05 coverage item D7).
- **Phase 47** (Type Fidelity Probe & Decision Doc) is independent of 46 and gates Phases
  48 and 50.

## Known Stubs

None. This plan shipped no code.

## Threat Flags

None. The plan's own register is discharged as planned:

- **T-46-15** (re-arming branch auto-switching) — mitigated by all four planned layers:
  sequenced last per D-18, a clean-tree precondition asserted before the edit, plain `git`
  rather than the helper that reads the changed value, and the branch name asserted
  unchanged after the commit.
- **T-46-16** (collateral edits to the planning config) — mitigated: a scoped one-line
  edit, with every other key's exact value asserted afterwards and a one-insertion
  one-deletion diff.
- **T-46-05** (cassette information disclosure) — mitigated and machine-checked: the digest
  is unchanged from Plan 03's recorded value across the whole phase.

## Estimate vs Actual

The plan estimated 25000 tokens at `confidence: low`; the realized diff is ~6100 on the
same chars/4 scale. The estimate priced the risk that the gate would *fail* — a red suite,
a moved digest, or a docs regression from a sibling plan would each have meant diagnosis
and a fix inside this plan. Everything was green on the first run, so none of that was
spent. The one thing that did fail was an acceptance criterion, not the code, and it cost a
paragraph. Read the gap as "the priced risk did not materialize", not as an over-estimate
of the work if it had.

## Self-Check: PASSED

- `.planning/phases/46-async-query-surface/46-07-SUMMARY.md` — FOUND
- `.planning/config.json` — FOUND
- `.planning/phases/46-async-query-surface/deferred-items.md` — FOUND (46-07 section added)
- `tests/unit/test_asyncio_trio_matrix.py`, `tests/unit/test_async_cancel.py` — FOUND
- Sibling commits cited above (`00b0b31`, `a596859`, `638a800`, `4b9c128`, `5e5cbcb`,
  `72ab636`) — all FOUND in history
- This plan's own two commits cannot be self-checked from inside a file committed by the
  first of them; the docs commit carries this SUMMARY, and the config commit follows
  immediately with `.planning/config.json` as its only path.

---
*Phase: 46-async-query-surface*
*Completed: 2026-08-03*
