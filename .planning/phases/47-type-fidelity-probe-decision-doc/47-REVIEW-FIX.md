---
phase: 47-type-fidelity-probe-decision-doc
fixed_at: 2026-08-12T09:40:00Z
review_path: .planning/phases/47-type-fidelity-probe-decision-doc/47-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 2
status: all_fixed
---

# Phase 47: Code Review Fix Report

**Fixed at:** 2026-08-12T09:40:00Z
**Source review:** `.planning/phases/47-type-fidelity-probe-decision-doc/47-REVIEW.md`
**Iteration:** 1
**Fix scope:** `critical_warning` (WR-01, WR-02, WR-03)

**Summary:**

- Findings in scope: 3
- Fixed: 3
- Skipped: 2 (IN-01, IN-02 — out of scope, not attempted)

Three files changed, all under `tests/`. No source file in `src/semolina/` was touched, no
dependency was added, and the committed artifact `47-TYPE-FIDELITY.md` is byte-identical.

## Verification environment

**Every gate below ran in the isolated worktree** (`/tmp/claude-501/sv-47-reviewfix-HrzGE8`,
branch `gsd-reviewfix/47-20762`), not in the main checkout. That worktree's `.venv` was
synced with `uv sync --dev --extra all` and confirmed to match the main checkout's dependency
profile on the two packages that change the artifact's output — `pandas` present, `polars`
absent — which is why the byte-identity claim below is reproducible.

After the fast-forward, `uv run python tests/type_fidelity_probe.py --check` (exit 0) and the
23 type-fidelity tests were re-run **in the main checkout** and reproduce identically, so the
result does not depend on the now-removed worktree.

| Gate | Result |
|---|---|
| `prek run --all-files` | all hooks passed (ruff, ruff-format, basedpyright, uv-lock, blacken-docs) |
| `uv run pytest` | 1079 passed, 16 skipped (baseline 1073/16, +6 new tests) |
| jaffle-shop `uv run pytest` | 16 passed, 15 skipped (matches baseline exactly) |
| `uv run python tests/type_fidelity_probe.py --check` | exit 0 |
| `just type-fidelity` then `git status` | no diff — artifact regenerates byte-identically |
| `git diff 6f614e5..HEAD -- pyproject.toml uv.lock` | empty — dependency files untouched |

No `# type: ignore` was added. No measured type literal was changed.

## Fixed Issues

### WR-01: Committed artifact path pinned inside the phase's own directory

**Files modified:** `tests/type_fidelity_probe.py`, `tests/unit/test_type_fidelity_table.py`
**Commit:** `a325ca9`

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
**Commit:** `b1b2d1e`

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
**Commit:** `93dafac`

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

## Skipped Issues

### IN-01: `collect_rows()` is dead code

**File:** `tests/type_fidelity_probe.py:1149-1156`
**Reason:** skipped — out of scope. Fix scope is `critical_warning`; Info findings were not
attempted.

### IN-02: Import-time filesystem/import side effects in a doctest-collected module

**File:** `tests/type_fidelity_probe.py:212`, `tests/type_fidelity_probe.py:918`
**Reason:** skipped — out of scope.

Worth one note for whoever picks it up: WR-01 adds a third import-time constant,
`ARTIFACT_PATH = resolve_artifact_path(required=False)`. It was deliberately kept
non-raising for exactly the reason IN-02 identifies — an import-time exception in a module
pytest collects for doctests on every run would turn a missing artifact into a whole-suite
collection failure, which is worse than the bug WR-01 fixes. The strict resolution happens
inside `main()` instead.

## Follow-up for the orchestrator

`.planning/todos/pending/2026-08-12-type-fidelity-artifact-path-survives-cleanup.md` records
WR-01 as its problem statement and WR-02/WR-03 under "Also from the same review". All three
are now fixed, so that todo is resolved. It was left in `pending/` rather than moved, because
`.planning/` artifact management belongs to the workflow, not the fixer.

---

_Fixed: 2026-08-12T09:40:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
