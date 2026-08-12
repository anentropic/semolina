---
phase: 48-type-map-implementation-databricks-literals
plan: 06
subsystem: docs
tags: [docs, diataxis, type-fidelity, codegen, check, phase-gate, broken-windows]

requires:
  - phase: 47-type-fidelity-probe-decision-doc
    provides: "47-DECISIONS.md, normative and one-directionally upstream of docs/src/explanation/type-fidelity.rst"
  - phase: 48-type-map-implementation-databricks-literals
    plan: 01
    provides: "the raw-type comment channel and uniform metric nullability that the docs now describe"
  - phase: 48-type-map-implementation-databricks-literals
    plan: 03
    provides: "the shipped annotation contract — Decimal on all three backends, JsonValue, str for UUID/JSON/ENUM — and its three evidence limits"
  - phase: 48-type-map-implementation-databricks-literals
    plan: 05
    provides: "the --check surface, EXIT_ANNOTATION_DRIFT = 5, and the Rich epilog string this page duplicates"
provides:
  - "docs/src/explanation/type-fidelity.rst no longer tells readers to distrust generated annotations; it states what a generated annotation names, the TIMESTAMP_NS caveat, and why --check can disagree with codegen"
  - "docs/src/how-to/codegen.rst § 'Check a committed model for drift' — the shipped --check surface, with the Databricks route documented as unverified"
  - "an exit-code table whose row 5 matches the CLI epilog word for word"
  - "a reconciled .planning/WINDOWS.md, three todos in step with what the phase actually verified, and a 48-VALIDATION.md naming only tests that exist"
affects: [phase-49-into-dto, phase-50-typed-dtos]

actuals:
  tokens: 11763
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "A published page derived from a normative internal document carries no link back to it, so the two cannot form a citation cycle"
    - "A duplicated string across code and docs is copied verbatim rather than paraphrased, and each copy names the other"
    - "A ledger's markdown table and JSON block are edited from one string in one pass, then re-verified against each other and against the frontmatter counters"

key-files:
  created:
    - .planning/phases/48-type-map-implementation-databricks-literals/48-06-SUMMARY.md
  modified:
    - docs/src/explanation/type-fidelity.rst
    - docs/src/how-to/codegen.rst
    - .planning/WINDOWS.md
    - .planning/todos/pending/2026-08-12-verify-databricks-zero-row-fallback.md
    - .planning/todos/pending/2026-08-12-record-snowflake-introspection-cassette.md
    - .planning/phases/48-type-map-implementation-databricks-literals/48-VALIDATION.md

key-decisions:
  - "The falsified `.. note::` was replaced with two body sections rather than another admonition. An admonition is a sidebar; what a generated annotation promises is the page's subject, not an aside on it."
  - "The Databricks --check limitation is stated as a `.. warning::` that claims neither success nor failure — 'unverified', with the reason. Broken window 2 and its todo both stay open."
  - "VARIANT is documented as honestly loose: on Databricks the value arrives as JSON text, so a reader is told they may get a `str` to parse rather than a ready-made `dict`."
  - "blacken-docs (line length 60) rewrapped the JsonValue import block. Accepted rather than worked around: the page already wraps a generated class signature for the same reason, so the file follows one convention."
  - "WINDOWS.md entries 2 and 3 were hand-edited because `gsd-tools windows` offers only status/append/waive/fixed. Both representations were written from one string in one script and re-verified three ways, which is the mitigation T-48-29 asks for."
  - "TYPE-05 was NOT marked complete. It is partial by decision (Databricks interval unmapped, broken window 7), and REQUIREMENTS.md keeps it Pending."
  - "48-VALIDATION.md's `nyquist_compliant` set true, with the sign-off stating explicitly that it means every row has a green automated command — not that every requirement is fully delivered."

patterns-established:
  - "When a doc rewrite would need a cross-reference to a label a later task creates, link the coarser existing label first and re-point it in that task, so every intermediate commit builds clean under -W"
  - "Verify a doc cross-reference resolved by inspecting the built HTML for an anchor, not by trusting a green build: Sphinx is not nitpicky by default and silently renders an unresolved py xref as plain text"

requirements-completed: []
requirements-partial: []

coverage:
  - id: D1
    description: "Neither documentation page carries a claim Phase 48 falsified"
    verification:
      - kind: manual
        ref: "grep for the two removed sentences returns 0; the three generated-output examples and the field-type table now match tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr"
        status: pass
    human_judgment: false
  - id: D2
    description: "The exit-code table agrees word for word between the CLI epilog and the how-to"
    verification:
      - kind: manual
        ref: "grep -n 'Annotation drift' src/semolina/cli/__init__.py docs/src/how-to/codegen.rst — identical string in both"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every docs edit builds warning-free under sphinx-build -W"
    verification:
      - kind: integration
        ref: "just docs-build — build succeeded, run after each of the two docs commits"
        status: pass
    human_judgment: false
  - id: D4
    description: "The scope fence runs rather than skips, and passes"
    verification:
      - kind: unit
        ref: "SEMOLINA_SCOPE_FENCE_BASE=9f3c8b9 uv run pytest tests/unit/test_scope_fence.py -x — 1 passed, 0 skipped"
        status: pass
    human_judgment: false
  - id: D5
    description: "No documentation claim asserts behaviour against a live Databricks workspace (D-09)"
    verification:
      - kind: manual
        ref: "the how-to's Databricks paragraph is a `.. warning::` reading 'unverified'; broken window 2 and the zero-row-fallback todo are both still open"
        status: pass
    human_judgment: false

duration: 13min
completed: 2026-08-12
status: complete
---

# Phase 48 Plan 06: Documentation Realignment & Phase Gate Summary

**The explanation page stopped telling readers to distrust generated annotations, the how-to
stopped listing VARIANT among the `Any` types and gained a `--check` section that says plainly
what has not been verified on Databricks — and the phase gate ran every check rather than
assuming any of them.**

## Performance

- **Duration:** 13 min
- **Tasks:** 3 (3 commits)
- **Files changed:** 6 modified, 1 created

## The phase gate, verbatim

Every command below was executed at HEAD (`fffaf14`), not inferred. The last four ran as one
chained `&&` invocation, which exited **0**.

| Gate | Command | Result |
|---|---|---|
| Root test suite | `just test` (first half) | **1288 passed, 16 skipped, 2 xfailed** in 20.27s; 3 snapshots passed |
| jaffle-shop suite | `just test` (second half) | **16 passed, 15 skipped** in 0.62s |
| Lint / format / typecheck | `prek run --all-files` | **clean** — 6 hooks passed in `dbt-jaffle-shop`, 10 passed and 1 skipped in `.`; ruff, ruff-format, uv-lock, basedpyright and blacken-docs all Passed |
| Docs, strict | `just docs-build` (`sphinx-build -W`) | **build succeeded** |
| Artifact staleness | `uv run python tests/type_fidelity_probe.py --check` | **exit 0** |
| Chained verify | `just test && prek run --all-files && just docs-build && uv run python tests/type_fidelity_probe.py --check` | **exit 0** |
| Scope fence, base set explicitly | `SEMOLINA_SCOPE_FENCE_BASE=9f3c8b9 uv run pytest tests/unit/test_scope_fence.py -x` | **1 passed, 0 skipped** |
| Fenced files in the phase diff | `git diff --name-only 9f3c8b9..HEAD \| grep -E 'src/semolina/(cursor\|acursor\|results)\.py'` | **no output** |
| `47-DECISIONS.md` in the phase diff | `git diff --name-only 9f3c8b9..HEAD \| grep 47-DECISIONS.md` | **no output** |

The two xfails are the deliberate strict expected failures on `c_interval`, both documented
(48-03, 48-04, broken window 6). They execute and fail for the recorded reason.

### `# type: ignore` across the phase

Counted at the phase base and at HEAD, over `src/semolina` only.

| | Count |
|---|---|
| Pre-phase (`9f3c8b9`) | **32** |
| Post-phase (`HEAD`) | **32** |
| Added by Phase 48 | **0** |

Not merely equal in total — the two sets are the same suppressions in the same files, at shifted
line numbers: one `no-any-return` in `cli/codegen.py`, one in `codegen/python_renderer.py`, one
in `engines/sql.py`, one `name-defined`, and 28 `reportPrivateUsage` on `_Query` attribute reads
in `engines/sql.py`. The phase's five new modules (`types.py`, `codegen/probe.py`,
`codegen/arrow_map.py`, `codegen/model_reader.py`, `codegen/annotation_check.py`) carry none.

### The scope fence, set explicitly

The plan was right to insist on the env var. `tests/unit/test_scope_fence.py` **skips loudly**
rather than failing when it cannot resolve a base ref (48-01 built it that way on purpose, and
proved the skip path non-vacuous), so a bare run is not evidence. With
`SEMOLINA_SCOPE_FENCE_BASE=9f3c8b9` it reports `1 passed` and no skips. The independent git-diff
gate agrees: of the 47 files the phase touched, none is `cursor.py`, `acursor.py`, `results.py`,
or `47-DECISIONS.md`.

## What changed in the docs

### `docs/src/explanation/type-fidelity.rst`

The closing `.. note::` said the generated annotations "do not all agree with that yet", named
`int`/`float`/`Any` for the three backends' decimal columns, and told the reader to "trust the
value you get at runtime over the annotation in a generated model". Phase 48 falsified every one
of those claims.

It was **replaced with two body sections rather than another admonition**. An admonition is a
sidebar, and what a generated annotation promises is now the page's subject rather than an aside
on it. Diataxis-wise the page stays Explanation throughout: background and reasoning, no
step-by-step, action deferred to the how-to.

**What a generated annotation names** states that a decimal column annotates `decimal.Decimal` on
all three backends, that metric fields annotate `T | None`, that the raw warehouse type is kept
as a comment above any field whose annotation does not name it, and that `UUID`/`JSON`/`ENUM`
annotate `str` because a `str` is what arrives. It then states the D-04 caveat without softening
it: a `TIMESTAMP_NS` column annotates `datetime.datetime`, the value is a `pandas.Timestamp` when
pandas is importable, and without pandas pyarrow truncates to microsecond resolution and raises
`ValueError` on sub-microsecond input. pandas is named as a transitive arrival under the `all`
extra, not a Semolina dependency.

**Why a fresh model can fail its own check** explains D-02 as background. `codegen` builds from
the catalogue, `--check` resolves from the result schema and falls back to the catalogue with a
label, and the two are the sources the page has been comparing all along — so `--check`
immediately after `codegen` can report drift. The worked example is the DuckDB `INTERVAL` case
48-05 measured: catalogue says `datetime.timedelta`, the probe resolves nothing, and the probe is
the half telling the truth.

**No `.planning/` link and no planning vocabulary.** `grep -c '.planning'` is 0. Decision 3 is
described by what it does — result schema primary, catalogue a labelled fallback — rather than
cited, so the one-directional derivation from `47-DECISIONS.md` survives intact.

### `docs/src/how-to/codegen.rst`

Five edits, all How-to voice: imperative-verb-first headings, illustrative snippets, reader
supplies setup.

1. **VARIANT removed from the `Any` list.** The parenthetical is now `(GEOGRAPHY, ARRAY, MAP,
   STRUCT)`. A new § "Read a VARIANT column's annotation" documents `JsonValue`, the automatic
   import, and — plainly — that on Databricks the value arrives as JSON **text**, so you get a
   `str` to parse rather than a `dict`. The union is explained as correct under both outcomes,
   which is exactly why 48-03 kept it where it reverted the interval guess.
2. **A new § "Read the raw warehouse type from a field comment"** covers the 48-01 channel: a
   `DECIMAL(10,2)` and a `DECIMAL(38,2)` both annotate `decimal.Decimal`, so the comment is where
   the precision and scale live.
3. **A new § "Check a committed model for drift"** (label `howto-codegen-check`), placed after
   the TODO sections and before § "Exit codes". Covers the invocation shape, the `--model`
   pairing and its exit 2, that the comparison is per field against the result schema rather than
   against regenerated source, that no data row is fetched, that stdout stays empty and the report
   goes to stderr, the three routes in a `list-table`, and that exit 5 means drift. It reproduces
   the real captured `--check` table from 48-05 rather than a mock-up.
4. **The exit-code `list-table` gained row 5.**
5. **A `See also` entry** pointing back to the explanation for the *why*.

The three generated-output tab examples and the field-type-mapping table were **also** corrected —
see Deviations.

### The Databricks limitation, stated without overclaiming

The `--check` section carries a `.. warning::` that claims neither success nor failure:

> `--check` is exercised end to end against DuckDB, and its comparison logic is exercised against
> a recorded Snowflake result schema. On Databricks it is **unverified** [...] Treat a Databricks
> `--check` result as unconfirmed either way until that gap is closed.

That is D-09 as 48-05 actually narrowed it, not as the plan predicted it: the Snowflake claim is
the **comparison core only**, because no Snowflake introspection cassette exists (broken window
9). Neither broken window 2 nor the zero-row-fallback todo was closed.

### Threat T-48-26: no credential shape in any example

The `--check` examples use `path/to/models.py` and `./analytics.db`. No token, password, account
identifier or hostname appears, and the section says credentials come from the environment "so
nothing secret belongs on this command line". The page's existing `DUCKDB_DATABASE` env-var route
stays the recommended shape.

### Threat T-48-28: the duplicated exit-code table

Copied verbatim, not paraphrased:

```
src/semolina/cli/__init__.py:31:  "  [yellow]5[/yellow]  Annotation drift -- a committed model no longer matches the "
docs/src/how-to/codegen.rst:454:     - Annotation drift -- a committed model no longer matches the result schema
```

Both copies name the other in a comment, so a future editor of either is told the pair exists.

## `.planning/WINDOWS.md` — every entry's disposition and why

`open_count` **8**, `total_count` **9**, unchanged. No entry was closed, waived, or added.

| id | Kind | Disposition | Why |
|---|---|---|---|
| 1 | deviation (46) | **fixed**, untouched | Closed before this phase |
| 2 | unrun-verify (47) | **open**, description extended | 48-04's driver re-read confirmed there is still no `ExecuteSchema` at `go/v0.1.2` or `v0.1.3`, so the zero-row fallback remains the only Databricks route *and* remains unexercised. The plan's conditional ("if the driver now implements ExecuteSchema") did not fire. The re-read finding, its shas and its date are now in the entry so nobody repeats it |
| 3 | deviation (47) | **open**, description extended | Not fixed by this phase. D-04 documented the user-facing half instead, and Task 1 wrote that documentation — the entry now names the page. It also carries 48-01's correction: regenerate under `uv sync --all-groups --extra all`, not `--dev --extra all`, which prunes the docs group |
| 4 | deviation (47) | **open**, untouched | Untouched by this phase, as the plan states |
| 5 | unrun-verify (48) | **open**, untouched | DBX-04's literal forms are still unverified against a live Databricks workspace (48-02) |
| 6 | deviation (48) | **open**, untouched | DuckDB `INTERVAL` stays known-wrong by decision (D-06), pinned by two strict xfails |
| 7 | unrun-verify (48) | **open**, untouched | TYPE-05's Databricks-interval half; the annotation was reverted for want of a measurement (48-03) |
| 8 | unrun-verify (48) | **open**, untouched | `VARIANT` → `JsonValue` is unmeasured; kept because the union holds under both plausible outcomes (48-03) |
| 9 | unrun-verify (48) | **open**, untouched | `--check` end to end is DuckDB-only; no Snowflake introspection cassette exists (48-05) |

**No new entry was needed.** Every deviation recorded across 48-01 … 48-05 is either an auto-fix
that landed in the same plan (so nothing was left behind) or is already carried by entries 5–9.
This plan itself left no stub, no skipped test, and no unrun `<verify>`.

**On the hand-edit.** `gsd-tools windows` offers only `status`, `append`, `waive` and `fixed` — no
description edit — so entries 2 and 3 were updated by a script that writes the markdown cell and
the JSON object **from one string in one pass**. Verified afterwards three ways: ids, statuses and
descriptions match between the markdown table and the JSON block; `open` counts to 8 in the
frontmatter, the markdown and the JSON; `total` counts to 9 in all three; and no description
contains a `|` that could break the table. `gsd-tools windows status` parses the result cleanly.
That is the mitigation T-48-29 asks for.

## Todos left pending, and why

| Todo | Status | Why |
|---|---|---|
| `2026-08-12-verify-databricks-zero-row-fallback.md` | **pending**, log appended | Nothing in Phase 48 ran the wrapper against a live metric view. A dated `## Log` entry records 48-04's driver re-read in full — the tag, the sha, the byte-identical `v0.1.3` file, the `driver.go:1581-1605` type-assertion failure, and the fact that the installed 0.1.2 comes from a machine-local ADBC manifest rather than `uv.lock` — so the next person does not repeat the reading. What is missing is a workspace |
| `2026-08-12-record-databricks-interval-column.md` | **pending**, untouched | 48-03 created it when it reverted the interval annotation. It already names exactly the measurement window 7 needs, so the plan's "add one new todo if the answer still has no measurement" was already satisfied; a second todo would have been a duplicate |
| `2026-08-12-record-snowflake-introspection-cassette.md` | **pending**, extended | Two Phase 48 windows have no closer other than this one recording session, and neither was named in it. Added as steps 5 and 6: a `VARIANT` column on the fixture plus the cassette-backed `isinstance` assertion (closes window 8), and a replayed CLI `--check` test beside the live-DuckDB ones (closes window 9) |

The phase deliberately planned no recording, so all three stay open. The evidence limits sit in
the ledger and in 48-02's and 48-03's summaries.

## `48-VALIDATION.md` rows corrected

Four rows named a test path or selector that reality contradicted. Each was corrected in place,
not dropped, and every one of the 18 rows was then **executed** and its count recorded.

| Row | Was | Now | Why |
|---|---|---|---|
| TYPE-07 circularity | `tests/unit/codegen/test_probe.py -k circular` | `tests/unit/test_type_fidelity_table.py::test_promoted_probe_does_not_import_the_type_map` | The file never existed and no test matches `-k circular`. As seeded the command collected **0 tests** and exited on "9 deselected", which pytest does not treat as a failure. First flagged by 48-04 |
| TYPE-06 JsonValue | `... -k variant tests/unit/test_models.py` | `... -k variant tests/unit/test_public_surface.py` | `test_models.py` exists but holds no `JsonValue` test. Worse, `-k variant` applied to the second path too and silently deselected all four of its tests, so the row passed while checking none of what it named |
| TYPE-05 Databricks interval | "resolves from `start_unit`/`end_unit`" | "stays unmapped and still emits a `TODO:`" | 48-02 wrote that branch and 48-03 reverted it. The row now describes the refusal `TestDatabricksIntervalType` actually asserts |
| fence | a `git diff \| grep` shell one-liner | `SEMOLINA_SCOPE_FENCE_BASE=9f3c8b9 uv run pytest tests/unit/test_scope_fence.py -x` | Superseded by the runnable test 48-01 built, with the env var named because a skipped fence is not a passing fence |

Two more rows had no command at all (`same module`, `same`) and were given explicit ones —
`-k 'check and route'` (1 pass) and `-k non_finite` (4 pass).

`status: validated`, `wave_0_complete: true` and `nyquist_compliant: true` were set. The sign-off
states explicitly what that last flag means and does not mean: every requirement row has an
executed green automated command, but **TYPE-05 remains partial** and `--check`'s Databricks route
remains unrun by design. `REQUIREMENTS.md` keeps TYPE-05 **Pending** for the same reason.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 - Bug] The how-to's three generated-output examples and its field-type table showed
output codegen no longer produces**

- **Found during:** Task 2, while checking the `Understand field type mapping` list-table against
  `test_codegen_e2e.ambr`.
- **Issue:** The plan flagged the table as one that "may want a nullability row". It needed more
  than that — the table's Metric row read `Metric[T]()` and all three tab-set examples showed
  `Metric[int]()`, both falsified by 48-01's TYPE-04 change. The Snowflake example additionally
  showed `Metric[int]()` for a `SUM`, which 48-03 made unreachable (Snowflake `FIXED` now maps to
  `decimal.Decimal` at every scale), and the Snowflake and Databricks examples showed the
  pre-48-01 unsorted `from semolina import SemanticView, Metric, Dimension, Fact` import line.
  A how-to whose "Produces:" block does not match what the tool produces is the same class of
  defect as the note Task 1 removed.
- **Fix:** all three examples reconciled against the committed snapshots — `| None` on every
  metric, the sorted import line, and the Snowflake example given its `import decimal`, its
  `# {"type": "FIXED", "scale": 0}` raw-type comment and `Metric[decimal.Decimal | None]()`. The
  table's Metric row became `Metric[T | None]()` with a paragraph explaining that only metrics
  admit `None`, linking to the explanation for the three null cases.
- **Files modified:** `docs/src/how-to/codegen.rst`
- **Commit:** `4cc41a5`

**2. [Rule 3 - Blocking] The Task 1 cross-reference had no anchor to point at yet**

- **Found during:** Task 1.
- **Issue:** The plan asks Task 1 to "add a cross-reference to the new `--check` how-to section",
  but that section and its `howto-codegen-check` label are Task 2's work. Referencing a label that
  does not exist yet is a warning, and `sphinx-build -W` turns it into a failed build — so Task 1's
  own `<verify>` would have gone red on a commit that was otherwise correct.
- **Fix:** Task 1 linked the coarser `howto-codegen` label, which exists; Task 2 created
  `howto-codegen-check` and re-pointed both the in-body link and the `See also` entry. Every
  intermediate commit builds clean under `-W`. Consequence: **Task 2 touched
  `docs/src/explanation/type-fidelity.rst`, which is outside its `<files>`** — two lines, both
  re-pointing links Task 1 deliberately left coarse.
- **Files modified:** `docs/src/explanation/type-fidelity.rst`
- **Commit:** `4cc41a5`

**3. [Rule 2 - Missing] Broken windows 8 and 9 had no todo naming the work that closes them**

- **Found during:** Task 3, reconciling `.planning/todos/pending/`.
- **Issue:** Both entries say their closer is a recording taken "in the same session" as the
  Snowflake gaps, and the Snowflake recording todo predates 48-03 and 48-05 — it names neither a
  `VARIANT` column nor a replayed `--check` test. Two open windows therefore pointed at a session
  whose own todo did not include their work, which is how a closer gets lost.
- **Fix:** steps 5 and 6 appended to `2026-08-12-record-snowflake-introspection-cassette.md`,
  each naming its window and the assertion that closes it. One session, four gaps, one todo, rather
  than two more files.
- **Files modified:** `.planning/todos/pending/2026-08-12-record-snowflake-introspection-cassette.md`
- **Commit:** `fffaf14`

### Tool-directed change

**4. blacken-docs rewrapped the `JsonValue` import block.** The hook runs at `-l 60`, and
`from semolina import Dimension, Fact, JsonValue, Metric, SemanticView` is 72 characters at that
indent, so it became a parenthesised multi-line import. Accepted rather than worked around: the
page already wraps a generated class signature (`class OrdersView(\n SemanticView, ...)`) purely
for width, so the file follows one convention rather than two. The first commit attempt failed on
this hook; the second passed with the rewrite in place.

## Findings

**A grep-based acceptance criterion held this time, but a green build did not.**
`grep -c 'howto-codegen'` counts the substring, so both `howto-codegen` and `howto-codegen-check`
satisfy it — the criterion could not tell whether the page pointed at the new section or merely
at the page containing it. The intent was verified directly instead, by reading the built HTML.
That check caught a real miss: `:py:obj:`semolina.JsonValue`` **did not resolve**. Sphinx is not
nitpicky by default, so the build stayed green while the reference rendered as plain code with no
anchor. autoapi documents the alias at `semolina.types.JsonValue`; the corrected
`:py:obj:`~semolina.types.JsonValue`` produces a real `<a href=...>`. Every other cross-reference
on the two pages was then checked the same way — `decimal.Decimal`, `uuid.UUID`,
`datetime.datetime`, `ValueError` and the implicit `What can be NULL`_ section target all resolve.

**The lesson from five misfired criteria generalises past greps.** 48-01, 48-03, 48-04 and 48-05
each recorded a criterion that a comment or docstring tripped. This plan's near-miss is the same
shape one level up: the *build exit code* is as coarse a proxy for "the cross-reference works" as
`grep -c` is for "the rule is followed". Assert on the artifact — parsed code, or in this case
rendered HTML.

**The plan's Task 3 instruction to update broken window 2 rested on a condition that did not
fire.** It says to update the description "if 48-04 found the Databricks driver now implements
`ExecuteSchema`". 48-04 found the opposite, and judged that entry 2 warranted no change because
its text "still describes reality exactly". That judgement is correct about the *defect*; it left
the *evidence* undocumented, so a sixth reader would have had cause to re-read `go/statement.go`
a third time. The re-read is now recorded in both the entry and the todo, with an explicit "do
not repeat this".

## Known Stubs

None. No stub values, no skipped tests, and no `<verify>` block went unrun. The two `xfail(strict)`
tests on `c_interval` are deliberate expected failures documented in 48-03 and 48-04, not stubs —
they execute and would report a failure if their recorded reason stopped holding.

## Threat Flags

None new. The four `mitigate` dispositions this plan owned are implemented:

- **T-48-26** (credentials in a copied example) — every `--check` example uses obvious
  placeholders, and the section directs readers to the environment for credentials.
- **T-48-27** (documenting an unverified Databricks capability) — the limitation is a
  `.. warning::` claiming neither outcome; broken window 2 and the zero-row-fallback todo both
  stay open; no acceptance criterion in this plan depends on Databricks.
- **T-48-28** (the duplicated exit-code table diverging) — row 5's wording is byte-identical to
  the epilog string, verified by grepping both files, and each copy carries a comment naming the
  other.
- **T-48-29** (the ledger's three representations drifting) — both representations written from
  one string in one pass, then verified three ways plus a clean parse by `gsd-tools windows status`.

T-48-30 and T-48-SC stay `accept` as planned. No packages were installed.

## Self-Check: PASSED

- `docs/src/explanation/type-fidelity.rst` — FOUND
- `docs/src/how-to/codegen.rst` — FOUND
- `.planning/WINDOWS.md` — FOUND
- `.planning/todos/pending/2026-08-12-verify-databricks-zero-row-fallback.md` — FOUND (still pending)
- `.planning/todos/pending/2026-08-12-record-databricks-interval-column.md` — FOUND (still pending)
- `.planning/todos/pending/2026-08-12-record-snowflake-introspection-cassette.md` — FOUND (still pending)
- `.planning/phases/48-type-map-implementation-databricks-literals/48-VALIDATION.md` — FOUND
- Commits `15e16e1`, `4cc41a5`, `fffaf14` — all FOUND in `git log`
