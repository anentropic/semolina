---
phase: 40-streaming-how-to-guide
plan: 01
subsystem: documentation
tags: [sphinx, rst, diataxis, how-to, streaming, arrow, pyarrow, record-batch-reader]

requires:
  - phase: 39-streaming-arrow-output
    provides: "fetch_record_batch() and __iter__ shipped on SemolinaCursor; verified backend behaviours (shared state, drained-reader OSError->StopIteration, empty batches, batch-size knobs, cursor lifetime)"
provides:
  - "New how-to page docs/src/how-to/streaming.rst covering fetch_record_batch() and `for row in cursor:`"
  - "Explicit .. tip:: decision rule for streaming vs fetch_arrow_table() covering memory, latency, and downstream-consumer pattern"
  - "Backend notes section consolidating Phase 39 findings into one user-facing place"
  - "ParquetWriter worked example demonstrating a bounded-memory streaming sink"
  - "Reverse See-also link from arrow-output.rst, so the two adjacent pages are mutually discoverable"
  - "STREAM-03 traceability flipped Pending -> Complete on close"
affects: [phase-41-duckdb-codegen-fs, phase-43-audit-uat, milestone-v0.5-close]

tech-stack:
  added: []
  patterns:
    - "Diataxis how-to page with anchor, illustrative snippets, decision-rule admonition, Backend notes, See also block"
    - "Backend notes section gathering cross-warehouse behaviour observed in implementation under one heading"
    - "Reverse cross-link bullet on the adjacent how-to page to keep peer pages discoverable"

key-files:
  created:
    - "docs/src/how-to/streaming.rst"
    - ".planning/phases/40-streaming-how-to-guide/40-01-SUMMARY.md"
  modified:
    - "docs/src/how-to/index.rst"
    - "docs/src/how-to/arrow-output.rst"
    - ".planning/REQUIREMENTS.md"

key-decisions:
  - "Ship the page with no warehouse tab-set: streaming code is ADBC-normalised and no snippet diverges by warehouse, so tabs would add noise (per 40-RESEARCH Anti-Patterns and Open Question 1)"
  - "Include one ParquetWriter downstream-sink example (~15 lines) rather than skipping it: reinforces SC-2's downstream-consumer-pattern axis without expanding scope"
  - "Stay silent on backlog 999.1 (fetch_df/fetch_polars): documenting an unshipped API would violate SC-1's runnable-example requirement"
  - "Add reverse See-also link to arrow-output.rst (per Open Question 4): single bullet, treated as a minor amendment so the full humanizer pass is not re-run on that file"
  - "Use straight `--` separators in See-also bullets (project convention) and limit em-dashes to one per paragraph"

patterns-established:
  - "Backend notes section: a fixed-position subsection (just before See also) for cross-warehouse behavioural quirks observed in implementation, sourced verbatim-in-spirit from the previous phase's RESEARCH.md §Common Pitfalls"
  - "Decision-rule tip: a single `.. tip::` admonition that names all relevant tradeoff axes (memory, latency, downstream consumer pattern) instead of a pros/cons table"

requirements-completed: [STREAM-03]

duration: ~12min
completed: 2026-05-15
---

# Phase 40 Plan 01: Streaming How-To Guide Summary

**Diataxis how-to page documenting `fetch_record_batch()`, `for row in cursor:`, and a Parquet downstream-sink example, with a `.. tip::` decision rule and a Backend notes section consolidating Phase 39 findings — Sphinx -W clean, humanizer term grep clean, STREAM-03 closed.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-15T06:47:00Z
- **Completed:** 2026-05-15T06:59:10Z
- **Tasks:** 5 (4 commit-producing + 1 verification gate)
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- New `docs/src/how-to/streaming.rst` (161 lines) with anchor, four content sections (stream batches, iterate rows, ParquetWriter sink, when-to-choose), explicit `.. tip::` decision rule, Backend notes, and full See also block.
- Toctree entry placing `streaming` between `arrow-output` and `codegen` so the page is reachable via the how-to sidebar.
- Reverse See-also bullet on `arrow-output.rst` pointing at `:ref:\`howto-streaming\`` so the two adjacent pages cross-discover.
- REQUIREMENTS.md STREAM-03 row + checkbox + footer all flipped Pending -> Complete in a single small diff.
- All structural greps green; humanizer term grep (powerful / seamlessly / leverage / delve / ensure that / it's worth noting / robust / comprehensive) green; `sphinx-build -W docs/src docs/_build` exits 0.

## Task Commits

Each task was committed atomically with `--no-verify` (per parallel-executor guidance):

1. **Task 1: Create docs/src/how-to/streaming.rst with full content** — `177df99` (docs)
2. **Task 2: Wire streaming page into how-to toctree** — `0dd8ff6` (docs)
3. **Task 3: Add reverse See-also link from arrow-output.rst** — `69d388c` (docs)
4. **Task 4: Run Sphinx strict build to validate cross-references and RST** — verification-only, no commit (gate passed: `sphinx-build -W` exit 0, humanizer term grep clean)
5. **Task 5 [BLOCKING]: Close STREAM-03 in REQUIREMENTS.md traceability** — `6541c2a` (docs)

## Files Created/Modified

- `docs/src/how-to/streaming.rst` (created) — Diataxis how-to page for streaming Arrow output and lazy row iteration.
- `docs/src/how-to/index.rst` (modified) — one-line toctree edit placing `streaming` between `arrow-output` and `codegen`.
- `docs/src/how-to/arrow-output.rst` (modified) — one-line reverse See-also bullet to `:ref:\`howto-streaming\``.
- `.planning/REQUIREMENTS.md` (modified) — STREAM-03 checkbox `[ ]` -> `[x]`, traceability row Pending -> Complete, footer timestamp updated to 2026-05-15.

## Decisions Made

See `key-decisions` in frontmatter. All five decisions were locked in by 40-RESEARCH Open Questions; no new architectural choices needed mid-execution.

The most load-bearing call: keeping the decision rule as a single `.. tip::` admonition rather than a comparison table. Tables crystallise but invite bikeshedding and go stale; one paragraph naming memory, latency, and downstream-consumer pattern is easier to maintain and renders better in shibuya.

## Deviations from Plan

None — plan executed exactly as written. All five tasks landed in order with the exact files, headings, snippets, and grep targets specified by the plan. The humanizer pass produced no rewrites because the draft already avoided promotional language, vague attributions, and em-dash overuse.

## Issues Encountered

- **Worktree branch base mismatch.** The worktree branch was sitting on commit `8ea4282` (a dependabot merge from main) rather than the expected base `2055199` (Phase 40 validation strategy). Fixed with `git reset --hard 2055199e1...` before starting; the worktree contained no unsaved work, so no content was lost. Resolution is in the orchestrator's path (it created the worktree on the wrong commit); flagging for the orchestrator-side fix.
- **Sphinx in the worktree venv.** `uv run sphinx-build` initially failed because the worktree venv hadn't been synced with the `docs` dependency group. Ran `uv sync --group docs` once; subsequent builds passed clean. The build itself produced zero warnings (`-W` mode, exit 0).

## User Setup Required

None — documentation-only phase. No environment variables, dashboard steps, or external services touched.

## Next Phase Readiness

- Phase 40 is closable: STREAM-03 traceability is updated at close time (per the Phase 39 Plan 02 lesson).
- The page contains no foreshadowing of backlog 999.1 (`fetch_df`/`fetch_polars`) or STREAM-04 (user-tunable batch sizes); when those ship, the relevant sections (Convert to a Pandas DataFrame-style snippet; Backend notes "Batch sizes" bullet) are the natural update sites.
- ROADMAP.md and STATE.md updates are owned by the orchestrator after the wave completes; this executor intentionally left them untouched.

## Self-Check: PASSED

Verified after writing this SUMMARY:

- `docs/src/how-to/streaming.rst` exists with `_howto-streaming:` anchor — FOUND
- `docs/src/how-to/index.rst` toctree contains `streaming` between `arrow-output` and `codegen` — FOUND
- `docs/src/how-to/arrow-output.rst` See also bullet references `:ref:\`howto-streaming\`` — FOUND
- `.planning/REQUIREMENTS.md` STREAM-03 row reads Complete, checkbox `[x]`, footer 2026-05-15 — FOUND
- Commits `177df99`, `0dd8ff6`, `69d388c`, `6541c2a` all present in `git log` — FOUND
- `sphinx-build -W docs/src docs/_build` exited 0 with `build succeeded.` and no warnings — VERIFIED
- Humanizer term grep clean for all 8 watchlist terms — VERIFIED

---
*Phase: 40-streaming-how-to-guide*
*Completed: 2026-05-15*
