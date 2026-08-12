---
created: 2026-08-12T08:00:00.000Z
updated: 2026-08-12T09:30:00.000Z
title: "Type-fidelity probe: remaining Info-level code review items"
area: testing
files:
  - tests/type_fidelity_probe.py
---

## Status

The three Warning-level findings from the Phase 47 code review (`47-REVIEW.md`) are **fixed** —
see `47-REVIEW-FIX.md` and commits `a325ca9`, `b1b2d1e`, `93dafac`:

- **WR-01 (artifact path vs milestone archival)** — `resolve_artifact_path()` now searches both
  `.planning/phases/<dir>/` and `.planning/milestones/*-phases/<dir>/`, and raises with a clear
  message if neither has the file. Proven end to end by `git mv`-ing the phase directory into
  `.planning/milestones/v0.7-phases/`, confirming `--check` exits 0 and all guards pass, then
  restoring. The artifact was deliberately **not** moved — its placement is a rated decision in
  `47-DECISIONS.md`.
- **WR-02 (unescaped `|` in table cells)** — fixed on both sides: `escape_cell()` escapes, and
  `_split_row()` splits on unescaped pipes only and restores the literal. Escaping the renderer
  alone would have made it worse, since the parser split on every `|`. Reproduced first with a
  synthetic `UNION(a INTEGER | b VARCHAR)` row that parsed as 11 cells against 10 columns.
- **WR-03 (trailing comma on an empty field request)** — the review's suggested
  `", ".join([view_literal, *parts])` was **rejected on evidence**: probed against a live
  in-memory DuckDB, it trades a parser error for a binder error (`semantic_view: … specify at
  least dimensions := [...], metrics := [...], or facts := [...]`). A `ValueError` is raised at
  the boundary instead, with `test_semantic_view_needs_at_least_one_field_list` asserting both
  spellings are rejected.

## What is left

Two Info-level items, deliberately out of scope for the `critical_warning` fix pass. Recorded
here rather than only in `47-REVIEW.md`, because that file lives in the phase directory and is
archived at milestone close.

- **IN-01** — dead code: `collect_rows()` in `tests/type_fidelity_probe.py` is unused.
- **IN-02** — import-time I/O side effects in a module pytest collects for doctests.

Neither affects correctness. Pick them up opportunistically, or fold them into Phase 48 when that
work is already touching the probe module.

To fix both: `/gsd-code-review 47 --fix --all`.
