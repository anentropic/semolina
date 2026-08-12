---
phase: 47-type-fidelity-probe-decision-doc
fixed_at: 2026-08-12T11:20:00Z
review_path: .planning/phases/47-type-fidelity-probe-decision-doc/47-REVIEW.md
iteration: 2
fix_scope: all
findings_in_scope: 5
fixed: 4
skipped: 1
status: partial
---

# Phase 47: Code Review Fix Report

**Fixed at:** 2026-08-12T11:20:00Z
**Source review:** `.planning/phases/47-type-fidelity-probe-decision-doc/47-REVIEW.md`
**Iteration:** 2 (cumulative — iteration 1 covered `critical_warning`, iteration 2 covers `all`)

**Summary across both iterations:**

| Finding | Outcome | Commit | Iteration |
|---|---|---|---|
| WR-01 | fixed | `a325ca9` | 1 |
| WR-02 | fixed | `b1b2d1e` | 1 |
| WR-03 | fixed (review's own suggestion rejected on measured evidence) | `93dafac` | 1 |
| IN-01 | fixed by deletion | `567568c` | 2 |
| IN-02 | **skipped deliberately** — measured, and the proposed change is a net loss | — | 2 |

- Findings in scope: 5
- Fixed: 4
- Skipped: 1 (IN-02, on measurement — see below)

Three files changed in total, all under `tests/`. No source file in `src/semolina/` was
touched, no dependency was added, and the committed artifact `47-TYPE-FIDELITY.md` is
byte-identical.

## Verification environment

**Iteration 1** ran its gates in an isolated worktree (`/tmp/claude-501/sv-47-reviewfix-HrzGE8`,
branch `gsd-reviewfix/47-20762`), then re-ran `--check` and the type-fidelity tests in the main
checkout after the fast-forward.

**Iteration 2** ran its gates in a second isolated worktree
(`/tmp/claude-501/sv-47-reviewfix-fEFkPq`, branch `gsd-reviewfix/47-81088`), whose `.venv` was
synced with `uv sync --dev --extra all`. That worktree matched the main checkout's dependency
profile on the two packages that change the artifact's output — confirmed indirectly and
decisively by `--check` returning 0 there, which it cannot do if the pandas/polars profile
differs. **After the fast-forward, everything below was re-run in the main checkout** and
reproduces identically, so no claim here depends on a worktree that no longer exists.

| Gate (iteration 2) | Where | Result |
|---|---|---|
| `prek run --all-files` | worktree | all hooks passed (ruff, ruff-format, basedpyright, uv-lock, blacken-docs) |
| `uv run pytest` | worktree | 1079 passed, 16 skipped — matches baseline exactly |
| jaffle-shop `uv run pytest` | worktree | 16 passed, 15 skipped — matches baseline exactly |
| `uv run python tests/type_fidelity_probe.py --check` | worktree **and** main checkout | exit 0 |
| `just type-fidelity` then `git status` | worktree | no diff — artifact regenerates byte-identically |
| 28 type-fidelity tests (table + duckdb + integration) | main checkout | 28 passed |
| `git diff a325ca9~1..HEAD -- pyproject.toml uv.lock 47-TYPE-FIDELITY.md` | main checkout | empty across all four fix commits |

No `# type: ignore` was added. No measured type literal was changed. No anti-circularity guard
was touched in iteration 2.

## Fixed Issues

### WR-01: Committed artifact path pinned inside the phase's own directory

**Files modified:** `tests/type_fidelity_probe.py`, `tests/unit/test_type_fidelity_table.py`
**Commit:** `a325ca9` (iteration 1)

**Approach taken — option 1 (glob), as constrained.** `resolve_artifact_path()` searches
`.planning/phases/47-.../` first and then
`.planning/milestones/*-phases/47-.../`, so the artifact is followed wherever `gsd-cleanup`
puts it. The artifact was **not** moved (option 2) and no cleanup exclusion was added
(option 3) — `47-DECISIONS.md` rated its placement deliberately.

**The silent fallback is gone.** `--check` previously read
`ARTIFACT_PATH.read_text(...) if ARTIFACT_PATH.exists() else ""`, so a missing file was
treated as "nothing committed yet" and compared against an empty document. It now raises
`FileNotFoundError` naming both searched locations. A missing artifact is a broken checkout,
and reporting it as drift is exactly how a staleness guard stops being believed.

`ARTIFACT_PATH` survives as a module constant for the guards that read it
(`resolve_artifact_path(required=False)`); `main()` re-resolves per invocation, strictly under
`--check` and permissively under `--write` so a first generation still has somewhere to land.

An incidental duplicate `REPO_ROOT` definition (previously declared twice with identical
bodies, at the new call site and again above `_cassette_root`) was collapsed to one —
basedpyright flags the second as `reportConstantRedefinition`.

**Verified:**

- Three new tests: archived location found, live location preferred over an archived copy,
  and missing-in-both raises. Confirmed red first (`ImportError` on the not-yet-existing
  symbols), green after.
- **End-to-end archival simulation.** `git mv`'d the whole phase directory to
  `.planning/milestones/v0.7-phases/`, then ran `--check` (exit 0) and the full guard module
  (8 passed), then restored. This is the actual failure the finding predicts, and it no longer
  happens.
- `--write` after the change leaves the artifact byte-identical.

### WR-02: Table-cell rendering did not escape `|`

**Files modified:** `tests/type_fidelity_probe.py`, `tests/unit/test_type_fidelity_table.py`
**Commit:** `b1b2d1e` (iteration 1)

Fixed on **both** sides so the value round-trips, rather than by loosening the parser:

- `escape_cell()` backslash-escapes `|` and flattens line breaks, applied at all three table
  renderers — `render_artifact` (headers and rows), `render_capability_table` (headers and
  rows), and `render_downstream_decimal`. The review named only the first two; the third
  builds rows the same way from the same kind of measured strings, and leaving one renderer
  unescaped would have been the next instance of this bug.
- `_split_row()` in the guard module splits on unescaped pipes only and restores the literal.
  Splitting on every `|`, as before, would have undone the escaping the generator applies.

**This strengthens the guard rather than loosening it.** A row whose cell count does not match
the header count is still a hard failure — `render_artifact`'s existing `ValueError` and the
new positional assertion both stand. What changed is that such a row can no longer be
*produced* by a measured value containing a pipe.

**Verified:**

- New test `test_a_pipe_in_a_cell_cannot_shift_the_table_columns` reproduces the bug exactly
  before the fix: a synthetic `UNION(a INTEGER | b VARCHAR)` row parsed as **11 cells against
  10 columns**. Green after, and the pathological value round-trips back out of the parser
  unchanged, so the escape is reversible rather than lossy.
- The synthetic type is labelled in the source as synthetic. No measured literal was touched.
- Artifact byte-identical after `just type-fidelity` — confirming no cell in the current
  document carries a pipe or a newline, so escaping is a no-op today.

### WR-03: `describe_raw_types` emitted invalid SQL with both field lists empty

**Files modified:** `tests/type_fidelity_probe.py`, `tests/unit/test_type_fidelity_duckdb.py`
**Commit:** `93dafac` (iteration 1)

**The review's suggested fix was rejected, on measured evidence.** The review proposed
`args = ", ".join([view_literal, *parts])`, which drops the trailing comma and emits
`semantic_view('view')`. Probed against a live in-memory DuckDB, that statement is *also*
rejected:

```
Binder Error: semantic_view: semantic view 'type_fidelity_view': specify at least
dimensions := [...], metrics := [...], or facts := [...]
```

So the suggested fix only trades a parser error for a binder error — still surfacing several
layers from the caller that asked for nothing. Under constraint 6 ("a guard or explicit error
is fine"), an empty request now raises `ValueError` at the boundary and runs no SQL. The
query builder was not restructured; this is one `if not parts:` guard plus a `Raises:` entry.

**Verified:**

- `test_describe_raw_types_refuses_an_empty_field_request` — confirmed red first
  (`DID NOT RAISE ValueError`), green after. Also asserts a recording cursor saw **zero**
  statements, so the guard fires before any SQL is built.
- `test_semantic_view_needs_at_least_one_field_list` — runs both spellings against the live
  probe cursor and asserts each is rejected. This is what makes the rejection of the review's
  approach evidence rather than an opinion; if a future DuckDB starts accepting either form,
  this test goes red and the decision gets revisited.

### IN-01: `collect_rows()` was dead code

**Files modified:** `tests/type_fidelity_probe.py`
**Commit:** `567568c` (iteration 2)

**Deleted, not wired in.** The review offered two options — call it from `main()`, or delete
it. Calling it from `main()` was checked first and ruled out, for a reason the review could
not see from the two line ranges it cited.

The two paths do produce the same rows in the same order: `collect_rows()` returns
`collect_duckdb_rows() + collect_snowflake_rows() + collect_databricks_rows()`, and
`collect_duckdb_rows()` is exactly `measure_duckdb().rows`, which is what `main()`
concatenates the same two cassette collectors onto. So content and order match.

What does not match is the *number of live probe runs*. `main()` needs both halves of one
`DuckDBMeasurement`: `measurement.rows` feeds the comparison table **and**
`render_disagreements`, while `measurement.evidence` feeds `render_capability_table` and the
disagreement prose. It therefore calls `measure_duckdb()` once and keeps the result.
`collect_rows()` reaches DuckDB through `collect_duckdb_rows()`, which calls `measure_duckdb()`
again. Routing the table through the aggregator would run the live in-memory DuckDB probe a
second time and let the table describe a different measurement run from the prose printed
beside it. For a document whose whole value is that its table and its narrative describe one
observation, that is a regression dressed as a cleanup.

A comment now sits where the function was, recording why the aggregator is absent, so the next
reader does not reintroduce it. The function was a leftover from the plan-01/plan-02 design
(both summaries describe extending `collect_rows()` as the way to add backends); the
implementation wired `main()` to `measure_duckdb()` directly instead, and the aggregator was
never updated or called.

**Verified:**

- `grep` over `tests/`, `src/`, `docs/`, `justfile` and the whole repo: exactly one occurrence
  of the name — the definition. No `__all__` in the module, no importer, no doctest reference.
- `prek run --all-files` green, including basedpyright strict (an unused-symbol deletion is
  precisely where a missed reference would surface).
- Full suite 1079 passed / 16 skipped and jaffle-shop 16 / 15 — both match baseline exactly.
- `--check` exit 0 and `just type-fidelity` leaves no diff, so the artifact is unaffected.

## Skipped Issues

### IN-02: Import-time filesystem/import side effects in a doctest-collected module

**File:** `tests/type_fidelity_probe.py` (`NOT_IMPLEMENTED_ERRORS`, `CASSETTE_ROOT`, and since
WR-01 also `ARTIFACT_PATH`)
**Outcome:** **skipped deliberately.** Not "out of scope" this time — attempted, measured, and
declined on the evidence.

The review rated this low priority itself and conditioned it on "if collection-time cost
becomes a real friction point". It has not, and the fix would cost more than the problem.

**The premise checks out; the cost does not.** pytest does import this module at collection —
confirmed with a `pytest_collection_finish` hook that found `type_fidelity_probe` in
`sys.modules` after a `--collect-only` run — and it contributes zero doctest items in return.
But the measured cost of the three constants is:

| Import-time work | Measured (mean of 200 calls) |
|---|---|
| `_resolve_not_implemented_errors()` | **0.0001 ms** |
| `_cassette_root()` | 0.3913 ms |
| `resolve_artifact_path(required=False)` | 0.0474 ms |
| **Total** | **0.44 ms** |

For scale, in the same module and on the same run: importing the whole probe module with its
dependencies already warm costs **4.79 ms**, and the two unconditional module-level imports it
opens with — `pyarrow` (243 ms) and `semolina` (1040 ms) — cost **1.28 s**. A full
`--collect-only` collects 1095 tests in 0.24–1.01 s. The three constants are ~9% of this
module's own import and ~0.03% of what the module pays for `pyarrow` + `semolina` regardless.

**The "eager `import adbc_driver_manager`" is not an import at all.** `semolina` already
imports `adbc_driver_manager`, and the probe module imports `semolina` at line 46 —
unconditionally, and *before* line 212. By the time `_resolve_not_implemented_errors()` runs,
the module is already in `sys.modules`, which is why it measures at 0.0001 ms. This part of
the finding is based on a cost that does not exist.

**The remaining argument — misconfiguration exposure — is not eliminable here.**
`tests/integration/test_type_fidelity.py` carries its own module-level
`CASSETTE_ROOT = _cassette_root()` (line 67), reading the same `adbc_cassette_dir` key from
the same `pyproject.toml`. It is a normal test module and pytest imports it at collection
unconditionally. Deferring the probe module's copy would move that collection-time `KeyError`
one module over, not remove it. And `adbc_cassette_dir` is the ini key pytest-adbc-replay
itself consumes, so a misconfiguration there is a genuinely broken test setup, not a spurious
failure worth insulating one module from.

**Deferral is also not low-risk — it would weaken a guard.** Keeping the public names working
lazily means a PEP 562 module `__getattr__`. That was tested against this project's actual
basedpyright strict configuration before deciding, with a throwaway module and a caller:

```python
from _in02_probe.lazymod import CASSETTE_ROOT
from _in02_probe.lazymod import TYPO_THAT_DOES_NOT_EXIST
```

`uv run basedpyright` reported **0 errors, 0 warnings, 0 notes** — including on
`TYPO_THAT_DOES_NOT_EXIST`, a name that does not exist and whose `__getattr__` raises
`AttributeError` at runtime. A module `__getattr__` makes every name importable from it
unverifiable, converting an import typo from a type error into a runtime `ImportError`.

That matters specifically here. `tests/unit/test_type_fidelity_table.py` imports
`ARTIFACT_PATH` and `tests/unit/test_type_fidelity_duckdb.py` imports
`NOT_IMPLEMENTED_ERRORS` from this module — the guard modules' only handle on the evidence.
Trading static verification of those imports for 0.44 ms is the kind of quiet weakening the
phase's constraints exist to prevent, on a project whose CLAUDE.md forbids `# type: ignore`
and whose point is strong typing. The experiment directory was removed; nothing from it was
committed.

**Revisit when:** the probe module gains a genuinely expensive import-time constant (a network
call, a warehouse connection, a large file read), or `_cassette_root()`'s 0.39 ms grows by
orders of magnitude. Neither is on the horizon. The `ARTIFACT_PATH` note from iteration 1
still stands and is the shape any future fix should keep: it is resolved with
`required=False` precisely so that a missing artifact cannot turn into a whole-suite
collection failure, which would be worse than the bug WR-01 fixed.

## Follow-up for the orchestrator

`.planning/todos/pending/2026-08-12-type-fidelity-artifact-path-survives-cleanup.md` records
WR-01 as its problem statement, WR-02/WR-03 under "Also from the same review", and IN-01/IN-02
under "What is left". WR-01, WR-02, WR-03 and IN-01 are now fixed, and IN-02 is closed as a
recorded decision rather than an outstanding task — so that todo has nothing left in it. It
was left in `pending/` rather than moved, because `.planning/` artifact management belongs to
the workflow, not the fixer.

---

_Fixed: 2026-08-12T11:20:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
