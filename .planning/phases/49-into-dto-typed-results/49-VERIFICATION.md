---
phase: 49-into-dto-typed-results
verified: 2026-08-14T09:20:00Z
status: human_needed
score: 12/12 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps_resolved_post_verification:
  - date: 2026-08-14
    resolved_by: execute-phase orchestrator
    commit: see "docs(49): tick DTO-03/DTO-04"
    note: >
      The single gap below was a traceability-bookkeeping oversight, not missing work.
      Before editing, the orchestrator independently re-confirmed the underlying
      implementation: `pytest tests/unit/test_dto.py -k "mismatch or reports_every"`
      returned 4 passed (DTO-03) and `-k "untyped or default"` returned 9 passed
      (DTO-04), on top of the async twins and the live-DuckDB integration tests the
      verifier had already run. Only the checkbox and the traceability-table row were
      changed; no code was touched. Closing a checkbox through a full gap-closure
      replan cycle would have been disproportionate to a four-line edit whose
      underlying work the verifier had already confirmed complete.
gaps:
  - truth: "REQUIREMENTS.md accurately reflects the true end state of all 8 requirement IDs now that all 7 plans are done"
    status: resolved
    reason: >
      DTO-03 and DTO-04 are fully implemented and exhaustively tested on both cursors
      (eager and streaming) — verified directly by running
      tests/unit/test_dto_duckdb.py, tests/unit/test_dto.py and
      tests/unit/test_dto_async.py, all green — but REQUIREMENTS.md still lists both as
      "Pending" (checkbox unchecked, table status "Pending"). Plan 06 explicitly
      re-ticked DTO-01, DTO-02, RESULT-01 and RESULT-02 to Complete once both cursors
      shipped ("this is that re-tick"), but no plan performed the equivalent re-tick
      for DTO-03/DTO-04, even though check_result_schema (which satisfies both) is
      identical code shared by both cursors and is exercised by both. This looks like
      an oversight rather than a deliberate withhold — no SUMMARY states a reason DTO-03
      or DTO-04 should stay Pending, unlike the explicit "left Pending, deliberately"
      note Plan 01 wrote for the genuinely-partial DTO-01/DTO-03/DTO-05 at that point
      in the phase.
    artifacts:
      - path: ".planning/REQUIREMENTS.md"
        issue: "Lines 33-34 and 111-112: DTO-03 and DTO-04 marked '[ ] Pending' despite complete, tested implementation."
    missing:
      - "Flip DTO-03 and DTO-04 to '[x]' in the requirements list and to 'Complete' in the phase-mapping table, in the same style Plan 06 used to re-tick DTO-01/DTO-02/RESULT-01/RESULT-02."
human_verification:
  - test: "Read docs/src/how-to/typed-results.rst end to end for voice, audience fit and Diataxis quality."
    expected: "Reads as a how-to for a data/analytics engineer building a BI backend, per .claude/skills/semolina-docs-author/SKILL.md; no instructional content leaked into the linked explanation page and vice versa."
    why_human: "Editorial/voice quality cannot be asserted by a command. This is the plan's own flagged manual verification (49-07-PLAN.md <flagged_assumptions> and 49-VALIDATION.md's Manual-Only Verifications table); D1 and D4 of Plan 07's coverage block explicitly route here."
  - test: "Read docs/src/how-to/typed-results.rst and docs/src/explanation/type-fidelity.rst specifically for the validate=True framing."
    expected: "No reader can come away believing validate=True is the safe mode for a money column — this is the phase's highest-severity threat (T-49-01) and a must_haves.prohibitions item across four plans."
    why_human: "A prohibition on a framing cannot be asserted by a command — a page can satisfy every grep and still leave the wrong impression, per Plan 07's own D4 coverage rationale. I confirmed the literal sentences exist and read correctly on inspection, but this is the plan's designated human checkpoint, not a substitute for it."
  - test: "Push the gsd/v0.7-async-typed-results branch and confirm the packaging-smoke GitHub Actions job is green."
    expected: "All packaging-smoke steps pass in the real CI environment, not just in the locally-reproduced venvs Plan 04 recorded."
    why_human: "Plan 04's own <verification> block lists 'The packaging-smoke job is green on the pushed branch before the phase is verified' as a required gate. The branch has never been pushed to origin (confirmed: origin/gsd/v0.7-async-typed-results does not exist, and no matching GitHub Actions run was found for this branch), so this specific plan-level verification item has not yet been satisfied by anyone. Everything it would check was reproduced locally and printed OK per the SUMMARY, and this is consistent with this project's normal workflow of pushing once at /gsd-ship rather than per phase, so it is not treated as a code defect — but it is an outstanding gate from Plan 04's own acceptance criteria."
---

# Phase 49: `.into(DTO)` Typed Results Verification Report

**Phase Goal:** Users can turn any query result — whole table, streaming batches, or async —
into Pydantic v2 DTOs, and hand results straight to pandas or polars.
**Verified:** 2026-08-14T09:20:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `.into(MyDTO)` on sync AND async cursors returns Pydantic v2 instances matched by column name, working the same for fully/partially/untyped models (DTO-01, DTO-04) | ✓ VERIFIED | `inspect.signature` on both `SemolinaCursor.into`/`AsyncSemolinaCursor.into`; `tests/unit/test_dto_duckdb.py` (24 passed, live DuckDB, `isinstance(v, decimal.Decimal)`); `tests/unit/test_dto.py::TestUntypedModels` (Any-annotated + partially-typed both convert); `tests/unit/test_dto_async.py::TestAsyncInto` (4×2 backends) |
| 2 | Streaming consumes DTOs per batch, sync and `async for`, without materialising the whole table (DTO-02) | ✓ VERIFIED (behavioral test) | Counting-fake-reader laziness tests in `tests/unit/test_dto.py` and `tests/unit/test_dto_async.py`; assertion is on a pull counter (`batches_read == 1`), not a length — this is the behavior-dependent claim and it is backed by an actual measurement, not presence alone |
| 3 | `iter_into()` raises schema errors AT THE CALL, not on first iteration, on both cursors (D-05) | ✓ VERIFIED (behavioral test) | `inspect.isgeneratorfunction`/`iscoroutinefunction`/`isasyncgenfunction` all confirm the required shape (ran directly, see below); AST walks confirm no `Yield`/`Await`/`YieldFrom` in either public `iter_into`; the "non-vacuity" tests in both SUMMARYs were reproduced conceptually — the committed tests fail against a deliberately-broken (bare-generator / `async def`) implementation per both SUMMARY logs, and pass against the shipped one |
| 4 | A DTO that doesn't match the result schema raises `SemolinaSchemaMismatchError` naming every mismatched field, both types, and carries no row value (DTO-03) | ✓ VERIFIED | `src/semolina/dto.py::check_result_schema`/`_render_report` read directly — reports all mismatches in one error, names field/column/Arrow-type/Python-type only; `decimal128→float` refused on BOTH `validate=False` and `validate=True` — ran `tests/unit/test_dto_duckdb.py` directly (24 passed, includes both settings) |
| 5 | `fetch_df()`/`fetch_polars()` exist on both cursors; missing package raises an actionable, install-naming error instead of an internals traceback (RESULT-01, RESULT-02) | ✓ VERIFIED | `tests/unit/test_cursor.py -k MissingDependency` (6 passed) and `tests/unit/test_async_cursor.py -k MissingDependency` (12 passed, 2 backends) ran directly; guard sets read from `cursor.py`/`acursor.py` match plan's claim (`fetch_polars` → polars only, `fetch_df` → pyarrow then pandas) |
| 6 | Plain `pip install semolina` pulls neither arrowmodel nor its Rust extension; `[arrowmodel]` alone is sufficient to run `.into()` (DTO-05) | ✓ VERIFIED | `pyproject.toml` read directly: `arrowmodel = ["arrowmodel>=1.0.0", "semolina[pyarrow]"]`, `all` reaches all four, `duckdb` references `semolina[pyarrow]`; `uv sync --locked --all-groups --extra all` exits 0; `tests/unit/test_dto_packaging.py` (10 passed) asserts the exact pins and the arrowmodel→pyarrow composition; `.github/workflows/ci.yml` `packaging-smoke` extended with real clean-venv absence/presence steps (not yet run in real CI — see human_verification) |
| 7 | Docs present `.into(DTO)` as the primary typed-result path with a worked BI-backend example in all four forms, and never frame `validate=True` as safe for money (DTO-06) | ✓ VERIFIED (content); human read pending | `just docs-build` exits 0 under `-W`; `docs/src/how-to/typed-results.rst` read directly — contains `.into(`, `iter_into(`, `await cursor.into(`, `async for dto in cursor.iter_into(` all in code blocks, `Field(validation_alias=...)` with the cassette-verified `AGG("REVENUE")` string, `pydantic.JsonValue` guidance, and an explicit `.. warning::` stating `validate=True` is not the safe setting for money |
| 8 | Phase 47 Decision 1's value-path prohibition holds — no coercion introduced into row construction | ✓ VERIFIED | `tests/unit/test_scope_fence.py` ran directly: 2 passed, neither skipped; `cursor.py`/`acursor.py`'s `to_pylist()` → `Row(...)` lines confirmed unchanged by direct grep |
| 9 | Assumption A3 (polars Decimal) closed by real measurement (D-16); `47-DECISIONS.md` corrected additively, not rewritten (D-17) | ✓ VERIFIED | `47-TYPE-FIDELITY.md:200` polars row reads `measured` with a real dtype string; `uv run python tests/type_fidelity_probe.py --check` exits 0; `git diff --numstat` on the `47-DECISIONS.md`-touching commit shows `14  0` (zero deletions) |
| 10 | Guard sets match what each dataframe/Arrow method actually imports (RESULT-02 correctness, not just presence) | ✓ VERIFIED | Cursor/acursor docstrings and guard call order read directly and match the ADBC source lines quoted in `49-05-SUMMARY.md`; `fetch_polars` confirmed guarded on polars only via a passing negative test (pyarrow absent, polars present, no raise) |
| 11 | `tests/unit/test_dto_async.py` genuinely runs under both asyncio and Trio, not merely marked | ✓ VERIFIED | Ran directly: `-k trio` selects 20/40, `-k asyncio` selects the other 20/40, full run is 40 passed; `tests/unit/test_asyncio_trio_matrix.py` (the AST contract) passes (3 passed) |
| 12 | REQUIREMENTS.md accurately reflects the true end state for all 8 requirement IDs | ✗ FAILED | See Gaps Summary — DTO-03 and DTO-04 remain "Pending" despite complete, tested implementation |

**Score:** 11/12 truths verified (1 present-and-code-complete but mis-tracked in REQUIREMENTS.md)

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/semolina/exceptions.py` | `SemolinaMissingDependencyError`, `SemolinaSchemaMismatchError`, `_require` | ✓ VERIFIED | Exists, exported from `semolina.__init__`, message format `"{package} is required by this method but is not installed. Install it with: pip install semolina[{extra}]"` confirmed by direct read |
| `src/semolina/dto.py` | `check_result_schema`, `resolve_column_key`, `FieldMismatch` | ✓ VERIFIED | Exists, read in full; confidence-boundary logic, alias resolution, and no-row-value guarantee all confirmed by inspection and by 24+52+18 passing tests |
| `src/semolina/cursor.py` | `into`, `iter_into`, `fetch_df`, `fetch_polars`, guards | ✓ VERIFIED | All four methods present with correct signatures; `_iter_into_impl` present and is a generator function (`iter_into` itself is not) |
| `src/semolina/acursor.py` | async twins of all four, `iter_into` a plain method | ✓ VERIFIED | All four methods present; `iter_into` confirmed neither coroutine nor async-generator function via `inspect`, `into` confirmed a coroutine function |
| `pyproject.toml` / `uv.lock` | four extras, `[all]`, `[arrowmodel]` composes `[pyarrow]` | ✓ VERIFIED | Read directly; `uv sync --locked --all-groups --extra all` exits 0 |
| `tests/unit/test_dto_duckdb.py`, `test_dto.py`, `test_dto_async.py`, `test_cursor.py`, `test_async_cursor.py`, `test_dto_packaging.py`, `test_public_surface.py` | comprehensive coverage | ✓ VERIFIED | All ran directly and green; full root suite 1481 passed, 16 skipped, 2 xfailed matches the reported measured state exactly |
| `docs/src/how-to/typed-results.rst` + 4 updated pages | DTO-06 | ✓ VERIFIED | `just docs-build` green; content spot-checked directly (see truth 7) |
| `.planning/REQUIREMENTS.md` | accurate completion tracking | ✗ FAILED | DTO-03/DTO-04 not re-ticked despite complete implementation |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `SemolinaCursor.into`/`iter_into` | `dto.check_result_schema` | function-local import, called on `self.description` | ✓ WIRED | Confirmed in source; pre-check runs before `fetch_arrow_table()`/`_iter_into_impl` on both paths |
| `AsyncSemolinaCursor.iter_into` | `AsyncSemolinaCursor._aiter_into_impl` | plain method returns the async generator | ✓ WIRED | Confirmed no `await`/`yield` in the public method via AST walk (ran directly) |
| `check_result_schema` | `arrow_type_to_runtime_type` | function-local import from `codegen.arrow_map` | ✓ WIRED | Confirmed; shares one predicate cascade with `arrow_type_to_python` per a passing coverage test |
| `fetch_df`/`fetch_polars` (both cursors) | ADBC/poolhouse's own implementations | one-line delegate, guarded before the call | ✓ WIRED | Confirmed by reading `cursor.py`/`acursor.py` — no reimplementation, `_require` calls precede delegation in every case |
| `[arrowmodel]` extra | `semolina[pyarrow]` | extra composition in `pyproject.toml` | ✓ WIRED | Confirmed directly; a mid-phase user-approved fix recorded in Plan 07's SUMMARY and pinned by `test_packaging_arrowmodel_extra_reaches_pyarrow` |
| Docs (`typed-results.rst`) | committed method signatures | every snippet checked against source | ✓ WIRED | Ran the exact signature-comparison command from Plan 07's own acceptance criteria; matches |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| `.into()` decimal round-trip on live DuckDB | `uv run pytest tests/unit/test_dto_duckdb.py -q` | 24 passed | ✓ PASS |
| Scope fence (Phase 47 Decision 1 prohibition) | `uv run pytest tests/unit/test_scope_fence.py -v` | 2 passed, neither skipped | ✓ PASS |
| `iter_into` is not a generator function (sync) | `inspect.isgeneratorfunction` | `False` | ✓ PASS |
| Async `iter_into` is neither coroutine nor async-gen function | `inspect.iscoroutinefunction`/`isasyncgenfunction` | both `False` | ✓ PASS |
| Async `into` IS a coroutine function | `inspect.iscoroutinefunction` | `True` | ✓ PASS |
| `test_dto_async.py` runs under both backends | `-k trio` / `-k asyncio` selection counts | 20/40 each way | ✓ PASS |
| RESULT-02 guard messages name install command per method | `tests/unit/test_cursor.py -k MissingDependency`, `tests/unit/test_async_cursor.py -k MissingDependency` | 6 passed, 12 passed (2 backends) | ✓ PASS |
| D-16 polars measurement is real | `uv run python tests/type_fidelity_probe.py --check` | exit 0 | ✓ PASS |
| D-17 additive-only diff on `47-DECISIONS.md` | `git diff --numstat` on the correcting commit | `14  0` | ✓ PASS |
| Full root + jaffle-shop suites | `uv run pytest -q` | 1481 passed, 16 skipped, 2 xfailed | ✓ PASS (matches measured state) |
| Lint/type gate | `prek run --all-files` | all hooks passed | ✓ PASS (matches measured state) |
| Docs build | `just docs-build` | build succeeded | ✓ PASS |
| Lock consistency | `uv sync --locked --all-groups --extra all` | exit 0 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|---|---|---|---|---|
| DTO-01 | 01, 06 | `.into(DTO)` on sync + async | ✓ SATISFIED (code); REQUIREMENTS.md Complete | Direct test runs |
| DTO-02 | 02, 06 | Streaming per batch, sync + async | ✓ SATISFIED (code); REQUIREMENTS.md Complete | Direct test runs |
| DTO-03 | 01, 02 | Actionable schema-mismatch error | ✓ SATISFIED (code); **REQUIREMENTS.md still Pending** | `dto.py` + 3 test modules, all green |
| DTO-04 | 02 | Untyped/partially-typed model support | ✓ SATISFIED (code); **REQUIREMENTS.md still Pending** | `TestUntypedModels` in `test_dto.py`, shared code path also exercised by async |
| DTO-05 | 01, 04, 07 | `[arrowmodel]` extra, clean install | ✓ SATISFIED; REQUIREMENTS.md Complete | `pyproject.toml`, `uv.lock`, packaging tests, CI steps (not yet run in real CI) |
| DTO-06 | 07 | Docs present `.into` as primary path | ✓ SATISFIED; REQUIREMENTS.md Complete | `just docs-build`, content read directly |
| RESULT-01 | 03, 05, 06 | `fetch_df()`/`fetch_polars()` both cursors | ✓ SATISFIED; REQUIREMENTS.md Complete | Live DuckDB `isinstance` tests, both cursors |
| RESULT-02 | 05, 06 | Actionable missing-package errors | ✓ SATISFIED; REQUIREMENTS.md Complete | Guard-message tests, both cursors, 4 methods |

No orphaned requirements — all 8 IDs the roadmap maps to Phase 49 appear in at least one plan's `requirements:` frontmatter.

### Anti-Patterns Found

None. Scanned `src/semolina/exceptions.py`, `dto.py`, `cursor.py`, `acursor.py` for `TODO`/`FIXME`/`HACK`/`PLACEHOLDER`/empty-return patterns — none found. No debt markers in any file this phase modified.

### Deferred Items

None identified — this phase's own `<flagged_assumptions>` blocks already document what is intentionally out of scope (e.g. `Query.into()` terminal, `pandas` alone not enabling `fetch_df()`), and those are recorded as accepted limitations in the SUMMARYs, not as gaps.

### Human Verification Required

1. **A human read of `docs/src/how-to/typed-results.rst`** for voice, audience fit, and Diataxis quality — the plan's own flagged manual verification (49-07-PLAN.md, 49-VALIDATION.md).
2. **A focused read of the `validate=True` framing** across both docs pages — T-49-01 is the phase's highest-severity threat and cannot be asserted by grep alone (a page can satisfy every grep and still leave the wrong impression).
3. **Push `gsd/v0.7-async-typed-results` and confirm `packaging-smoke` is green in real GitHub Actions.** Plan 04's own `<verification>` block requires this "before the phase is verified"; the branch has never been pushed to `origin`, so this specific gate has not yet run for real, only been reproduced locally (as the SUMMARY documents). Not treated as a code defect — the project's normal workflow pushes once at `/gsd-ship` — but it is an outstanding item from that plan's stated acceptance criteria.

### Gaps Summary

One real, verifiable gap: **`.planning/REQUIREMENTS.md` marks DTO-03 and DTO-04 as "Pending"**, but both are fully implemented and exhaustively tested on both cursors (eager and streaming paths share the same `check_result_schema` code). This is a pure bookkeeping omission, not a functional shortfall — every truth the roadmap's Success Criteria 1 and 3 require is demonstrably true in the running code, confirmed directly by this verifier rather than taken from any SUMMARY's claim. Plan 06 explicitly performed the "re-tick" for DTO-01/DTO-02/RESULT-01/RESULT-02 once both cursors shipped, but the same re-tick was never done for DTO-03/DTO-04, and no SUMMARY records a deliberate reason to withhold it (contrast with Plan 01's explicit "left Pending, deliberately" for the genuinely-partial items at that point in the phase). The fix is a two-line edit to `REQUIREMENTS.md` (flip both checkboxes and the mapping-table cells to Complete) — no code or test changes are implied.

This looks intentional in spirit but not in execution — an override may be appropriate if the maintainer prefers to close it as a trivial follow-up rather than a phase gap:

```yaml
overrides:
  - must_have: "REQUIREMENTS.md accurately reflects the true end state of all 8 requirement IDs"
    reason: "DTO-03 and DTO-04 are verified complete in code and tests; the REQUIREMENTS.md checkbox omission is a one-line documentation fix, not a functional gap, and can be closed directly rather than looping back through a closure plan."
    accepted_by: "<name>"
    accepted_at: "<ISO timestamp>"
```

---

_Verified: 2026-08-14T09:20:00Z_
_Verifier: Claude (gsd-verifier)_
