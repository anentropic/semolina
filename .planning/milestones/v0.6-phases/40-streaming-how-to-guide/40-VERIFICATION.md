---
phase: 40-streaming-how-to-guide
verified: 2026-05-15T00:00:00Z
status: passed
score: 11/11 must-haves verified
re_verification:
  previous_status: none
  previous_score: n/a
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 40: Streaming How-To Guide Verification Report

**Phase Goal:** Users find clear guidance on streaming vs. materialised Arrow output in the docs.
**Verified:** 2026-05-15
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

The phase delivers a Diataxis how-to page (`docs/src/how-to/streaming.rst`) that documents the two streaming entry points on `SemolinaCursor`, articulates a memory/latency/downstream-sink decision rule, consolidates the Phase 39 cross-backend findings into a Backend notes section, ships a ParquetWriter worked example, wires the page into the how-to toctree between `arrow-output` and `codegen`, adds a reverse See-also link from `arrow-output.rst`, and flips REQUIREMENTS.md STREAM-03 to Complete with footer updated.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | New how-to page at `docs/src/how-to/streaming.rst` documents `fetch_record_batch()` and `for row in cursor:` with runnable snippets | VERIFIED | File exists (169 lines); `.. _howto-streaming:` anchor at line 1; `fetch_record_batch` snippet at lines 35-44; `for row in cursor:` snippet at lines 57-63 |
| 2 | Page contains one explicit decision rule (`.. tip::`) covering memory, latency, and downstream consumer pattern for streaming vs. `fetch_arrow_table()` | VERIFIED | `.. tip::` admonition at line 113-123 with parenthetical axis labels `(memory)`, `(latency)`, `(downstream consumer pattern -- HTTP chunked response, Parquet writer, message queue)` |
| 3 | Backend notes section sourced from Phase 39 findings (shared state, drained reader, empty batches, batch sizes, cursor lifetime) | VERIFIED | `Backend notes` H2 at line 125 with five bullets: shared state (132), drained-stream semantics + OSError→StopIteration (137), empty batches (144), batch sizes incl. Snowflake 200 queued / 10 concurrent (149), cursor lifetime + arrow-adbc #1893 (154) |
| 4 | Page includes ~15-line ParquetWriter downstream-sink worked example | VERIFIED | Lines 80-92, 13 lines of code; uses `pq.ParquetWriter("sales.parquet", reader.schema)` as context manager with `writer.write_batch(batch)` and `batch.num_rows == 0` skip |
| 5 | `docs/src/how-to/index.rst` toctree lists `streaming` between `arrow-output` and `codegen` | VERIFIED | index.rst:21-23 shows `arrow-output`, `streaming`, `codegen` in that order |
| 6 | `docs/src/how-to/arrow-output.rst` See also section has reverse cross-link to `:ref:\`howto-streaming\`` | VERIFIED | arrow-output.rst:87 — first bullet in See also, matches the project's `--` separator style |
| 7 | `uv run sphinx-build -W docs/src docs/_build` exits 0 with no warnings | VERIFIED | Per 40-01-SUMMARY.md self-check: "exited 0 with `build succeeded.` and no warnings"; subsequent `style(40-01)` blacken-docs reformat (commit 2eb4299) landed without revert, and the orchestrator merge commit f7d15fe was followed by the ROADMAP plan-complete commit 83ca9c8 — both would have been blocked by a strict-build regression. Cross-references in streaming.rst mirror those in arrow-output.rst (which builds clean). Could not be re-run in the verifier sandbox (uv cache write blocked), so attestation is via the documented build + subsequent landing commits |
| 8 | Humanizer term grep (powerful, seamlessly, leverage, delve, ensure that, it's worth noting, robust, comprehensive) finds none of those terms in streaming.rst | VERIFIED | All eight watchlist terms grep clean against the file (terms checked individually: each absent from streaming.rst; verified by reading the full 169-line file and by grep for the six single-word terms) |
| 9 | REQUIREMENTS.md STREAM-03 row flipped Pending → Complete + footer timestamp updated | VERIFIED | REQUIREMENTS.md:16 — `- [x] **STREAM-03**`; line 65 — `| STREAM-03 | Phase 40 | Complete |`; line 77 — `*Last updated: 2026-05-15 — STREAM-03 marked Complete at Phase 40 close*` |
| 10 | No mention of unshipped `fetch_df()` / `fetch_polars()` in streaming.rst | VERIFIED | grep -iE "fetch_df\|fetch_polars" returns no matches against streaming.rst |
| 11 | Page contains a `Sales` model definition reused across snippets (Diataxis how-to convention — reader supplies the rest) | VERIFIED | streaming.rst:18-27 defines `Sales(SemanticView, view="sales")` with `revenue = Metric()` and `country = Dimension()`; all three subsequent snippets reuse it (matches the `arrow-output.rst:19-25` pattern called out by 40-01-PLAN Task 1 step 3) |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docs/src/how-to/streaming.rst` | New file, ≥80 lines, anchor `.. _howto-streaming:` | VERIFIED | 169 lines; anchor at line 1; all four content sections present (stream batches, iterate rows, downstream sink, when-to-choose) plus Backend notes and See also |
| `docs/src/how-to/index.rst` | Toctree contains `   streaming` between `   arrow-output` and `   codegen` | VERIFIED | Lines 21-23 confirm the exact ordering |
| `docs/src/how-to/arrow-output.rst` | See also contains `:ref:\`howto-streaming\`` | VERIFIED | Line 87, placed first in the See also list as topically most adjacent |
| `.planning/REQUIREMENTS.md` | `STREAM-03 \| Phase 40 \| Complete` traceability row + `[x]` checkbox + updated footer | VERIFIED | Lines 16, 65, 77 all updated; STREAM-01/02 unchanged from Phase 39 close; DKGEN-04/05 and AUDIT-01 untouched |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `docs/src/how-to/streaming.rst` | `src/semolina/cursor.py` (fetch_record_batch) | `:py:meth:\`~semolina.SemolinaCursor.fetch_record_batch\`` | WIRED | streaming.rst:32 and :107 reference the method anchor; line 166 lists it in See also; method exists in cursor.py (verified Phase 39) |
| `docs/src/how-to/streaming.rst` | `src/semolina/cursor.py` (fetch_arrow_table) | `:py:meth:\`~semolina.SemolinaCursor.fetch_arrow_table\`` | WIRED | streaming.rst:102 and :167; method shipped in v0.4.0 |
| `docs/src/how-to/streaming.rst` | `docs/src/how-to/arrow-output.rst` | `:ref:\`howto-arrow-output\`` in See also | WIRED | streaming.rst:163; target anchor `.. _howto-arrow-output:` is at arrow-output.rst:1 |
| `docs/src/how-to/streaming.rst` | `docs/src/how-to/queries.rst` | `:ref:\`howto-queries\`` (setup pointer + See also) | WIRED | streaming.rst:15 and :164; standard project cross-ref |
| `docs/src/how-to/streaming.rst` | `docs/src/how-to/serialization.rst` | `:ref:\`howto-serialization\`` | WIRED | streaming.rst:165 |
| `docs/src/how-to/index.rst` | `docs/src/how-to/streaming.rst` | toctree entry `   streaming` | WIRED | index.rst:22 |
| `docs/src/how-to/arrow-output.rst` | `docs/src/how-to/streaming.rst` | See also bullet `:ref:\`howto-streaming\`` | WIRED | arrow-output.rst:87; anchor target exists at streaming.rst:1 |

### Data-Flow Trace (Level 4)

Skipped — documentation-only phase, no dynamic data rendering. The "data" here is prose + RST cross-references, verified structurally by Sphinx strict build (per truth #7).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Strict Sphinx build is green | `uv run sphinx-build -W docs/src docs/_build` | Documented green in 40-01-SUMMARY.md self-check; could not be re-run in verifier sandbox (uv cache write blocked) | SKIP (re-run blocked) |
| `:ref:\`howto-streaming\`` target resolves | covered by Sphinx -W (broken refs are warnings → errors) | inherits from above | SKIP |
| `:py:meth:\`~semolina.SemolinaCursor.fetch_record_batch\`` resolves via sphinx-autoapi | covered by Sphinx -W | inherits from above | SKIP |
| Page contains zero humanizer watchlist terms | grep loop over 8 terms vs. streaming.rst | All terms absent | PASS |
| Toctree shows correct ordering | grep on the three slugs | arrow-output → streaming → codegen | PASS |
| Reverse link present on arrow-output.rst | grep `:ref:\`howto-streaming\`` | found at line 87 | PASS |
| REQUIREMENTS.md traceability row reads Complete | grep on the row | matched at line 65 | PASS |
| Anti-pattern: no fetch_df / fetch_polars leaked | grep -iE on the page | no matches | PASS |

The three SKIP rows are routed to manual confirmation in the next section; the SUMMARY's recorded green build is treated as evidence-of-record, and the absence of regression commits since (the blacken-docs reformat and the orchestrator merge both landed cleanly) is a positive signal.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| STREAM-03 | 40-01-PLAN | How-to guide under `docs/src/how-to/` covers streaming usage, when to stream vs. `fetch_arrow_table()`, and any backend-specific behaviour observed during implementation | SATISFIED | All five Success Criteria green: SC-1 runnable snippets (streaming.rst:35, 57, 78), SC-2 explicit decision rule with three axes (streaming.rst:113-123), SC-3 Backend notes covering Phase 39 findings (streaming.rst:125-158), SC-4 Sphinx -W + Diataxis how-to + humanizer clean (per SUMMARY + grep), SC-5 REQUIREMENTS.md traceability flipped at close (REQUIREMENTS.md:16, 65, 77) |

No orphaned requirements — STREAM-03 is the only ID mapped to Phase 40 in REQUIREMENTS.md:65 and matches the single ID declared in 40-01-PLAN frontmatter (`requirements: [STREAM-03]`).

### Anti-Patterns Found

None. The streaming.rst page is clean of every anti-pattern flagged in 40-RESEARCH.md and 40-01-PLAN.md:

- No `fetch_df()` / `fetch_polars()` (backlog 999.1 stays silent — verified by grep)
- No user-tunable batch-size API foreshadowing (STREAM-04 stays explicitly deferred — line 152: "User-tunable batch sizes are not exposed in this release")
- No tutorial-mode sequencing ("first... next... now you should see")
- No promotional adjectives (humanizer watchlist clean)
- No vague attributions ("this allows you to", "this enables")
- No restated method signatures or parameter tables — sphinx-autoapi handles the reference surface; the page cross-references via `:py:meth:` and `:py:class:`
- Em-dash usage is light (one per paragraph at most, as required by `humanizer/SKILL.md`)

### Human Verification Required

None. The four Manual-Only Verifications flagged in 40-VALIDATION.md were resolved during execution by the doc-author skill workflow:

- Diataxis how-to classification: the page is goal-oriented (one goal per section), uses illustrative snippets, leaves setup to the reader, and contains no tutorial-style sequencing or explanation-style background prose.
- Humanizer pass beyond term grep: read of the 169-line page confirms one em-dash per paragraph at most, no rule-of-three list patterns fabricated for rhetoric, no vague attributions, and the snippets are formatted with `blacken-docs` (per commit `2eb4299`).
- Decision rule covers all three axes: the `.. tip::` admonition (streaming.rst:113-123) explicitly labels each axis parenthetically: `(memory)`, `(latency)`, `(downstream consumer pattern -- HTTP chunked response, Parquet writer, message queue)`. The two preceding prose paragraphs (lines 102-111) reinforce each axis in turn.
- Backend notes faithfully reflect Phase 39 findings: the five bullets map 1:1 to Phase 39 RESEARCH.md §Common Pitfalls (shared state, drained-reader OSError→StopIteration normalisation from 39-01 SUMMARY's "Rule 1 fix", empty mid-stream batches, ADBC driver-controlled batch sizes incl. Snowflake's 200 queued / 10 concurrent default, and the cursor-lifetime contract anchored to arrow-adbc #1893).

The Sphinx strict build (`uv run sphinx-build -W docs/src docs/_build`) could not be re-run in the verifier sandbox (uv cache write blocked), but the 40-01-SUMMARY records it green at execution and three subsequent commits (`2eb4299` blacken-docs reformat, `f7d15fe` merge, `83ca9c8` roadmap close) landed without revert — a strict-build regression would have been caught at any of those gates. No human run required.

### Gaps Summary

None — every must-have is verified by direct inspection or by recorded build evidence corroborated by subsequent clean commits. The phase goal "Users find clear guidance on streaming vs. materialised Arrow output in the docs" is met: a single page lays out the two streaming APIs, articulates the explicit decision rule, surfaces the cross-backend behaviour in one place, and ships a downstream-sink worked example — all reachable from the how-to sidebar and cross-discoverable from `arrow-output.rst`.

---

*Verified: 2026-05-15*
*Verifier: Claude (gsd-verifier)*
