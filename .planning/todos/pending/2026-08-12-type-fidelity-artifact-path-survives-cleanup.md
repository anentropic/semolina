---
created: 2026-08-12T08:00:00.000Z
title: "Make the type-fidelity artifact path survive milestone archival"
area: testing
files:
  - tests/type_fidelity_probe.py
  - tests/unit/test_type_fidelity_table.py
---

## Problem

`ARTIFACT_PATH` in `tests/type_fidelity_probe.py` (around line 486) hardcodes the phase
directory:

```
Path(__file__).resolve().parents[1]
    / ".planning" / "phases" / "47-type-fidelity-probe-decision-doc" / "47-TYPE-FIDELITY.md"
```

`gsd-cleanup` archives completed milestones' phase directories into
`.planning/milestones/v{X.Y}-phases/`. When v0.7 closes and that cleanup runs, the path stops
resolving, `--check` fails, and `test_committed_table_is_not_stale` turns red — breaking
`just test` and CI during whatever unrelated change happens to be in flight at the time. The
failure will look like drift in the type-fidelity evidence when it is really a moved file.

This is finding **WR-01** from `47-REVIEW.md` (Phase 47 code review, no blockers). It is
recorded here rather than only in that review because the review file lives in the same
directory that gets archived.

## Options

1. Resolve the artifact by glob across both `.planning/phases/` and
   `.planning/milestones/*-phases/`, so it follows the directory wherever cleanup puts it.
2. Move the artifact somewhere cleanup does not touch (for example `tests/fixtures/` or
   `docs/`), and leave a pointer from the phase directory. Note that Phase 47 rated the
   artifact's placement deliberately — `47-DECISIONS.md` treats `.planning/` as the home of the
   normative evidence — so this option reopens a rated decision rather than just fixing a path.
3. Add a `gsd-cleanup` exclusion for this file.

Option 1 is the smallest change and does not reopen the placement decision.

## Also from the same review (lower priority)

- **WR-02** — markdown table cells are not escaped for `|`
  (`tests/type_fidelity_probe.py` ~570-578, ~1710-1713). A stray pipe in a type string would
  silently corrupt column alignment and weaken
  `test_result_and_mapped_vocabularies_are_disjoint`, which is one of the anti-circularity
  guards.
- **WR-03** — `describe_raw_types` (~393-405) emits invalid SQL with a trailing comma if called
  with both `dimensions` and `metrics` empty. Currently unreachable, but latent.
- **IN-01 / IN-02** — dead `collect_rows()`, and import-time I/O side effects in a module that
  pytest collects for doctests.

## Context

Phase 47 (Type Fidelity Probe & Decision Doc), completed 2026-08-12. The code review found no
blockers; the anti-circularity contract holds throughout. These are forward-looking robustness
gaps, not present-day correctness defects.
