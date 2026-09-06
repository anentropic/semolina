# Phase 40: Streaming How-To Guide - Research

**Researched:** 2026-05-14
**Domain:** Documentation — Diataxis how-to authoring, Sphinx restructuredtext, streaming/Arrow API exposition
**Confidence:** HIGH

## Summary

Phase 40 is a single-page documentation phase. The streaming API surface — `SemolinaCursor.fetch_record_batch() -> pyarrow.RecordBatchReader` and `for row in cursor:` — already shipped in Phase 39 and is verifiable against `src/semolina/cursor.py` (lines 164–196 for `fetch_record_batch`, lines 222–284 for `__iter__`/`__next__`). The behaviour is well-characterised by Phase 39's RESEARCH.md and the two SUMMARY files: lazy batch pull, empty-batch skip, OSError→StopIteration normalisation on drained readers, no auto-close, and the cursor-must-outlive-reader contract.

The interesting work is in three places: (1) building a goal-oriented how-to page that classifies cleanly as Diataxis "how-to" (not tutorial, not explanation) — illustrative snippets, reader supplies setup, one goal per page; (2) articulating an explicit decision rule for streaming vs. `fetch_arrow_table()` that the success criteria call out by name — memory, latency, downstream consumer pattern; and (3) documenting backend behaviour observed in Phase 39 (the OSError-after-drain quirk, the shared-state semantics, ADBC normalisation across DuckDB / Snowflake / Databricks) under a "Backend notes" section without leaking implementation detail.

Everything else is mechanical: file lives at `docs/src/how-to/streaming.rst`, gets added to `docs/src/how-to/index.rst` toctree (likely between `arrow-output` and `codegen`), uses sphinx-design `.. tab-set:: :sync-group: warehouse` only if a snippet genuinely differs by dialect (most streaming snippets don't — ADBC normalises this), passes `uv run sphinx-build -W docs/src docs/_build` clean, and goes through the semolina-docs-author humanizer pass. The page must reference `:py:meth:` for API anchors so sphinx-autoapi cross-references resolve.

**Primary recommendation:** Create `docs/src/how-to/streaming.rst` with three goal-shaped sections (stream record batches, iterate rows lazily, choose between streaming and materialising), one explicit decision-rule callout, and one "Backend notes" subsection at the bottom. Use `.. code-block:: python` for runnable snippets; use `.. note::` / `.. warning::` directives for the cursor-lifetime contract; avoid the warehouse tab-set unless a snippet diverges by dialect. Cross-link to `:ref:`howto-arrow-output``, `:ref:`howto-queries``, and `:ref:`howto-serialization`` in the "See also" block.

<user_constraints>
## User Constraints (from CONTEXT.md)

CONTEXT.md does NOT exist for Phase 40 (`has_context: false` per init). Phase 40 was spawned directly into research without a prior `/gsd-discuss-phase` round.

The user's intent is fully captured by the phase's Success Criteria in ROADMAP.md (verbatim):

1. A new how-to page under `docs/src/how-to/` covers `fetch_record_batch()` and `for row in cursor:` with runnable example snippets.
2. The page articulates when to stream vs. when `fetch_arrow_table()` is preferable (memory, latency, downstream consumer pattern), with at least one explicit decision rule.
3. Any backend-specific behaviour observed during Phase 39 implementation (batch sizes, end-of-stream semantics) is documented under a "Backend notes" section.
4. Page passes the semolina-docs-author skill workflow (Diataxis how-to classification + humanizer pass) and the Sphinx `-W` build succeeds.
5. REQUIREMENTS.md Traceability for STREAM-03 is updated on close.

### Locked Decisions

- **Page type:** Diataxis how-to (goal-oriented, illustrative snippets, reader supplies setup) — anchored in CLAUDE.md "Documentation standards" and re-stated in the semolina-docs-author skill.
- **Mandatory workflow:** `@.claude/skills/semolina-docs-author/SKILL.md` (Diataxis classification + humanizer pass + sphinx-design tab-set rules) — CLAUDE.md "Mandatory skill" elevates this to a hard requirement, not a suggestion.
- **Build gate:** `uv run sphinx-build -W docs/src docs/_build` must pass (strict mode, warnings-as-errors).
- **Decision rule explicit:** SC-2 requires AT LEAST ONE explicit decision rule for streaming vs. `fetch_arrow_table()` (not buried in prose).
- **Backend notes section:** SC-3 requires a section by that name (or close to it) capturing Phase 39's observed behaviours.
- **Traceability update on close:** SC-5 — REQUIREMENTS.md STREAM-03 row flips `Pending → Complete` and footer timestamp gets updated, in the same close commit. This is the lesson baked in from Phase 39's Plan 02.

### Claude's Discretion

- Exact heading wording, subsection ordering, and how many distinct snippets to include.
- Whether to include a `.. tab-set::` for any snippet — only if a snippet genuinely diverges by warehouse (most streaming code is dialect-agnostic; the tab-set may be skipped entirely for this page if no SQL is shown).
- File slug — `streaming.rst` is the natural choice; the planner may pick `streaming-and-iteration.rst` or similar if useful.
- Position in the `docs/src/how-to/index.rst` toctree — likely between `arrow-output` and `codegen` since streaming extends Arrow output. Planner decides exact ordering.
- Whether to include a "common pitfalls" subsection (cursor lifetime, mixed-API state-sharing) inline in the relevant section or grouped at the end of the page.
- Whether to surface the Phase 39 deferred pyarrow-runtime-leak finding in any user-facing doc (recommendation: no — it's a pre-existing internal issue, not a streaming-API behaviour).

### Deferred Ideas (OUT OF SCOPE)

- STREAM-04 (user-controllable batch size knobs) — explicitly deferred to future milestone per REQUIREMENTS.md Future Requirements. The page may mention that batch sizes are ADBC-driver-determined today but MUST NOT propose a public API for tuning.
- `fetch_df()` / `fetch_polars()` ADBC passthrough — backlog item 999.1, surfaced during this Phase 40 discussion per ROADMAP.md Backlog. The page may mention batched `.to_pandas()` over `fetch_record_batch()` as the current path, but the backlog item is the eventual better answer. **Do not pre-document an API that doesn't exist.**
- `to_pandas_chunks()` / `.to_polars_chunks()` helpers — explicitly Out of Scope per REQUIREMENTS.md Out of Scope table.
- Async iteration (`__aiter__`) — Out of Scope per same table.
- Streaming via non-ADBC path — Out of Scope.
- Updates to other how-to pages beyond cross-linking — phase scope is one new page, not a docs sweep.
- The pre-existing pyarrow-runtime-leak via `semolina.config` (from Phase 39's `deferred-items.md`) — this is an internal-isolation concern, not a streaming-API behaviour. Not the right page for it.
- The pre-existing codegen import-order test failure (Phase 39 deferred-items.md) — unrelated to docs; belongs to codegen polish later in v0.5.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STREAM-03 | How-to guide under `docs/src/how-to/` covers streaming usage, when to stream vs. `fetch_arrow_table()`, and any backend-specific behaviour observed during implementation | Verified: streaming API is shipped (`src/semolina/cursor.py` lines 164–196, 222–284); existing how-to pattern is well-established (`docs/src/how-to/arrow-output.rst`, `serialization.rst`); Diataxis how-to classification is mandated by CLAUDE.md and the semolina-docs-author skill; build gate is `uv run sphinx-build -W docs/src docs/_build`; backend-specific notes have a concrete source (Phase 39 RESEARCH.md §Common Pitfalls and SUMMARY.md "Rule 1 fix"). |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

| Directive | Source | Compliance |
|-----------|--------|------------|
| When writing or modifying documentation, MUST load `@.claude/skills/semolina-docs-author/SKILL.md` | CLAUDE.md "Documentation standards → Mandatory skill" | Planner MUST add this skill reference to the PLAN.md `<execution_context>` block (CLAUDE.md "GSD planner instruction" makes this explicit). |
| New how-to pages: full workflow (mandatory) | CLAUDE.md "When to apply" | Phase 40 ships a NEW page → full Diataxis classification + humanizer pass, no exceptions. |
| How-to guides under `docs/src/how-to/` use illustrative snippets, reader supplies setup, goal-oriented | CLAUDE.md "Content types" | New page lives at `docs/src/how-to/streaming.rst`; snippets show key concept (iteration, batch consumption) not a runnable end-to-end tutorial. |
| sphinx-design tab-set with `:sync-group: warehouse` for SQL dialect examples | CLAUDE.md "Content types" | If no SQL is shown (likely the case for this page), no tab-set is needed. If any SQL or DDL appears, dialect-divergent variants MUST be tabbed. |
| Audience: data/analytics engineers with existing semantic view; building BI dashboard backend | CLAUDE.md "Writing voice" | Do not over-explain Python iteration basics; assume reader is comfortable with generators, context managers, and `for x in y:`. |
| Tone: warm but efficient (FastAPI/Stripe-like) | CLAUDE.md "Writing voice" | Avoid promotional language ("powerful", "seamlessly", etc. — explicitly listed in semolina-docs-author skill Step 3). Humanizer pass enforces this. |
| Perspective: second person ("you") | CLAUDE.md "Writing voice" | Lead with "Use `fetch_record_batch()` when..." not "One can use..." or "The library provides..." |
| Pages self-contained with "See also" links at bottom | CLAUDE.md "Writing voice" | Page MUST end with a `See also` block linking to `:ref:`howto-arrow-output``, `:ref:`howto-queries``, `:ref:`howto-serialization``, and `:py:meth:` API anchors. |
| Quality gates: `prek run --all-files` and `just test` must pass before commit | CLAUDE.md "Quality gates" | No code changes in this phase — `prek` and `just test` are essentially no-ops for the doc page but must remain green. Real gate is `just docs-build`. |
| Avoid `# type: ignore`; docstring conventions D213, line length 100 | CLAUDE.md "Code style" | Not directly relevant — page is RST, not Python. The only Python in the page is `.. code-block:: python` snippets, which should follow the same conventions for consistency. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Sphinx | >=8.0 | Static site generator; renders RST | Already in `dev-dependencies.docs` group at `pyproject.toml`. Build gate is `uv run sphinx-build -W` (strict). [VERIFIED: pyproject.toml lines 64–69] |
| shibuya theme | >=2025.1.1 | Theme used by the docs site | Already pinned. The site uses Diataxis-aligned tabs from this theme. [VERIFIED: pyproject.toml line 65; docs/src/conf.py `html_theme = "shibuya"`] |
| sphinx-design | >=0.6.0 | Provides `.. tab-set::` and `.. tab-item::` directives with `:sync-group:` for warehouse-synced examples | Used across the existing how-to pages (`queries.rst`, `filtering.rst`, etc.). [VERIFIED: pyproject.toml line 67; docs/src/how-to/queries.rst lines 33–50] |
| sphinx.ext.napoleon | bundled with Sphinx | Google-style docstring rendering for autoapi cross-references | Listed in `conf.py` extensions. [VERIFIED: docs/src/conf.py line 8] |
| sphinx.ext.intersphinx | bundled with Sphinx | Cross-references to Python stdlib types | Listed; mapping covers Python 3 stdlib. [VERIFIED: docs/src/conf.py lines 51–53] |
| sphinx-autoapi | >=3.6.0 | Auto-generates API reference from source docstrings; provides `:py:meth:` / `:py:class:` cross-reference targets | Used for `:py:meth:`~semolina.SemolinaCursor.fetch_record_batch`` anchors. Anchors generated automatically from `src/semolina/cursor.py` docstrings (already present from Phase 39). [VERIFIED: pyproject.toml line 66; conf.py lines 35–46] |
| sphinx-copybutton | >=0.5.2 | Adds copy-to-clipboard button on code blocks | Already configured. Nothing to do in this phase. [VERIFIED: pyproject.toml line 68] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sphinx-autobuild | >=2025.8.25 | Live-reload dev server via `just docs-serve` | Local development of the new page. Not part of CI. [VERIFIED: pyproject.toml line 69] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Single RST page at `docs/src/how-to/streaming.rst` | Adding sections to `arrow-output.rst` | Mixing two goals (materialising vs. streaming) into one page violates Diataxis "one guide, one goal". The phase brief and CLAUDE.md both call for a new page. Do not merge. |
| RST `.. tab-set::` | MyST markdown directives | Project is RST-only. `conf.py` does not configure `myst-parser`; existing how-tos are all `.rst`. Adopting MyST mid-doc-site is out of scope. |
| sphinx-design `.. tab-set::` for streaming code | No tabs at all | The streaming API is dialect-agnostic (ADBC normalises across DuckDB / Snowflake / Databricks). Unless a snippet shows backend-specific SQL or behaviour, tabs add noise. Default: no tabs on this page. |
| Hand-authored API reference | `:py:meth:`~semolina.SemolinaCursor.fetch_record_batch`` cross-references | Reference docs are auto-generated by sphinx-autoapi from source docstrings. Do not duplicate. Cross-reference instead. Already the project pattern. |

### Installation

No new packages. All deps already present in the `docs` dependency group.

```bash
uv sync --group docs
```

**Version verification (run during Wave 0 to confirm registry currency):**

```bash
uv pip show sphinx              # expect >=8.0
uv pip show sphinx-design       # expect >=0.6.0
uv pip show sphinx-autoapi      # expect >=3.6.0
uv pip show shibuya             # expect >=2025.1.1
```

## Architecture Patterns

### Recommended Implementation Shape

```
docs/src/how-to/
├── streaming.rst                NEW — Phase 40 deliverable
├── index.rst                    MODIFY — add `streaming` to toctree
├── arrow-output.rst             UNCHANGED — page this one complements
├── serialization.rst            UNCHANGED — page this one cross-links to
└── queries.rst                  UNCHANGED — page this one cross-links to
```

One new file, one one-line toctree edit. No other doc files touched.

### Pattern 1: How-to page skeleton

**What:** Goal-shaped RST page with anchor target, single H1, illustrative sections, See also.
**When to use:** Every new file under `docs/src/how-to/`.
**Example (derived from `docs/src/how-to/arrow-output.rst` lines 1–89):**

```rst
.. _howto-streaming:

How to stream large results
============================

Short opening paragraph: who this is for, what the goal is, the
one-sentence "what the page covers".

Stream record batches with fetch_record_batch
----------------------------------------------

Brief intro sentence. Then a runnable snippet showing the API:

.. code-block:: python

   from semolina import SemanticView, Metric, Dimension


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       country = Dimension()


   with Sales.query().metrics(Sales.revenue).execute() as cursor:
       reader = cursor.fetch_record_batch()
       for batch in reader:
           process(batch)

Short follow-up paragraph: what the snippet shows, what's important.

Iterate rows lazily with `for row in cursor:`
----------------------------------------------

...

When to stream vs. fetch_arrow_table
-------------------------------------

...

Backend notes
-------------

...

See also
--------

- :ref:`howto-arrow-output` -- materialise results as a PyArrow Table
- :ref:`howto-queries` -- build queries and access results
- :ref:`howto-serialization` -- convert Row objects to dicts and JSON
- :py:meth:`~semolina.SemolinaCursor.fetch_record_batch` -- API reference
- :py:meth:`~semolina.SemolinaCursor.fetch_arrow_table` -- API reference
```

The anchor target `.. _howto-streaming:` at the top is load-bearing — it's what `:ref:`howto-streaming`` references will resolve to from other pages and future cross-links. Pattern verified across all existing how-to pages.

### Pattern 2: Explicit decision rule (SC-2)

**What:** A `.. tip::` or `.. note::` admonition (or a bullet list) that articulates the decision rule in one place, not buried.
**When to use:** In the "When to stream vs. fetch_arrow_table" section.
**Example:**

```rst
When to stream vs. fetch_arrow_table
-------------------------------------

Use :py:meth:`~semolina.SemolinaCursor.fetch_arrow_table` when the result
fits comfortably in memory and you want to hand it to pandas, polars,
or other Arrow consumers as a single value.

Use :py:meth:`~semolina.SemolinaCursor.fetch_record_batch` or iterate the
cursor when the result is large enough that materialising the full Arrow
table would strain memory, or when your downstream consumer can already
process row batches.

.. tip::

   **Rule of thumb.** If the result fits in roughly 1 GB or you need a
   single ``pyarrow.Table`` for downstream work, materialise with
   ``fetch_arrow_table()``. If the result is unbounded, larger than
   memory, or already destined for a streaming sink (HTTP chunked
   response, file-by-batch write, message queue), stream with
   ``fetch_record_batch()`` or ``for row in cursor:``.
```

The `.. tip::` directive renders as a visually distinct callout in shibuya — the decision rule is unmissable. The rule itself must touch all three axes called out in SC-2: **memory**, **latency**, and **downstream consumer pattern**. The example above touches memory (size, "strain memory") and downstream consumer pattern (HTTP chunked, file-by-batch, message queue, single pandas/polars value). The planner should add a latency note — e.g. "streaming lets you start processing the first batch before the warehouse has finished computing the rest" — to satisfy all three axes.

### Pattern 3: Backend notes section (SC-3)

**What:** A subsection capturing the cross-backend behaviour observed during Phase 39 — not implementation detail, but user-visible quirks.
**When to use:** Once, near the end of the page (before "See also").
**Example structure (content sourced from Phase 39 RESEARCH.md §Common Pitfalls + SUMMARY.md "Rule 1 fix"):**

```rst
Backend notes
-------------

Streaming behaviour is normalised across Snowflake, Databricks, and
DuckDB through ADBC. There is no Semolina-side code path that differs
by backend. A few behaviours worth knowing:

**Shared state with other fetch methods.** ``fetch_record_batch()``,
``fetch_arrow_table()``, ``fetchone()``, and iterating the cursor all
consume from the same underlying ADBC stream. Pick one consumption
pattern per cursor and finish it before switching, or you will see
empty results from the second consumer.

**Drained-stream semantics.** After ``fetch_arrow_table()`` has run,
iterating the cursor yields zero rows -- no error. Re-iterating an
already-consumed cursor also yields zero rows. This matches Python's
DBAPI ``fetchone() -> None`` convention.

**Empty batches mid-stream.** Some ADBC drivers emit zero-row batches
before or between data batches. Semolina's row iteration skips them
automatically; if you consume the ``RecordBatchReader`` directly, your
code should skip ``batch.num_rows == 0`` batches too.

**Batch sizes.** Batch size is controlled by the ADBC driver and the
warehouse, not by Semolina. Snowflake's ADBC driver defaults to up
to 200 queued batches with up to 10 concurrent streams; DuckDB returns
data in driver-determined chunks; Databricks uses its own native
batching. User-tunable batch sizes are not exposed in this release.

**Cursor lifetime.** The ``RecordBatchReader`` depends on the cursor
and its connection staying alive. Consume the reader inside the
context manager (or before ``cursor.close()``). Returning the reader
from a closed cursor produces undefined behaviour.
```

All five bullets are sourced from verified Phase 39 findings:

- Shared state: Phase 39 RESEARCH.md §Pitfall 3 — verified against arrow-adbc `dbapi.py:1389-1409`.
- Drained-stream semantics: Phase 39 RESEARCH.md §Pitfall 4 + SUMMARY.md "Rule 1 fix" (OSError→StopIteration normalisation handles this in `__next__`).
- Empty batches: Phase 39 RESEARCH.md §Pitfall 2 — verified against arrow-adbc `dbapi.py:1491–1500`.
- Batch sizes: Phase 39 RESEARCH.md §Security Domain ("Snowflake: 200 queued batches default, 10 concurrent streams default") + Out of Scope (STREAM-04 deferred).
- Cursor lifetime: Phase 39 RESEARCH.md §Pitfall 1 — arrow-adbc issue #1893 + shipped docstring on `fetch_record_batch` in `cursor.py:178-179`.

### Pattern 4: Cross-references and "See also"

**What:** Use `:ref:`anchor`` for in-site links, `:py:meth:`~semolina.SemolinaCursor.method`` for API anchors, `:py:class:` for class anchors.
**When to use:** Every cross-reference in the page.
**Example (verified pattern in `docs/src/how-to/serialization.rst:140-143`):**

```rst
See also
--------

- :ref:`howto-arrow-output` -- materialise results as a PyArrow Table
- :ref:`howto-queries` -- build queries and access results
- :ref:`howto-serialization` -- convert Row objects to dicts and JSON
- :py:meth:`~semolina.SemolinaCursor.fetch_record_batch` -- API reference
- :py:meth:`~semolina.SemolinaCursor.fetch_arrow_table` -- API reference
- :py:class:`~semolina.SemolinaCursor` -- cursor class reference
```

The leading `~` shortens the displayed text to the last component (e.g. `fetch_record_batch` instead of `semolina.SemolinaCursor.fetch_record_batch`). Verified consistent across all existing how-to pages.

### Anti-Patterns to Avoid

- **Tutorial-mode prose:** Phrases like "first, install...", "next, configure...", "now you should see..." belong in tutorials, not how-tos. How-to readers supply their own setup. (Diataxis classification.)
- **Explaining iteration internals:** Why the cursor uses a state machine, why ADBC OSError gets normalised to StopIteration, the `_stream_exhausted` flag — these are implementation details. Surface only the observable behaviour. (Diataxis: explanation vs. how-to separation.)
- **Hand-rolled API reference:** Don't restate method signatures, parameter tables, or return types in prose — sphinx-autoapi handles that. Cross-reference with `:py:meth:` instead. (CLAUDE.md "Reference auto-generated via sphinx-autoapi. Do not hand-write API docs.")
- **Unnecessary `.. tab-set::`:** Don't tab snippets by warehouse if the snippet is identical across warehouses. The tab-set is for genuine SQL/DDL divergence. Most streaming code on this page is dialect-agnostic.
- **Promotional adjectives:** "Powerful", "seamless", "robust", "comprehensive", "effortlessly" — semolina-docs-author skill Step 3 explicitly flags these for removal during the humanizer pass.
- **AI vocabulary:** "Delve", "leverage", "streamline", "it's worth noting", "ensure that" — same source, same removal.
- **Vague attributions:** "This allows you to", "this enables", "this ensures" — replace with direct description of what the API does.
- **Em-dash overuse:** Max one per paragraph. semolina-docs-author skill explicit rule.
- **Rule of three:** Avoid listing concepts in threes for rhetorical effect. (Notice: this RESEARCH.md uses three-axis lists where genuinely three axes exist — that's fine. The anti-pattern is fabricated triplets.)
- **`fetch_df()` / `fetch_polars()` mentioned as if they exist:** They do not. Backlog 999.1. The page can show `pa.Table.from_batches(...).to_pandas()` as the current path. Do not claim methods that aren't shipped.
- **Tabs-vs-spaces mix in code blocks:** All snippets use 4-space indent, no tabs. Verified across existing how-to pages.
- **Curly quotes in code:** Use straight `"` quotes inside `.. code-block:: python`. Curly quotes break Python syntax in copyable examples.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| API reference for the new methods | Tables describing parameters / return types in the how-to page | `:py:meth:`~semolina.SemolinaCursor.fetch_record_batch`` cross-reference | sphinx-autoapi generates these from the existing docstrings in `cursor.py`. Duplicating them in prose creates drift risk and violates CLAUDE.md "Reference auto-generated... Do not hand-write API docs." |
| Streaming-versus-materialised decision table by hand | Multi-row table of pros/cons per axis | One `.. tip::` admonition with the decision rule in plain prose | Tables crystallise tradeoffs but mostly invite bikeshedding and become stale. A one-paragraph rule is easier to maintain and renders better in shibuya. SC-2 asks for "at least one explicit decision rule" — one rule, expressed clearly, exceeds the bar. |
| Backend comparison table (Snowflake-vs-Databricks-vs-DuckDB batch sizes) | Three-column table of "DuckDB: X, Snowflake: Y, Databricks: Z" with specific numbers | A short prose paragraph noting batch sizes are driver-controlled, with the one verified Snowflake default (200 queued, 10 concurrent) as a concrete example | Specific numbers for Databricks/DuckDB ADBC batch sizing are not verified in Phase 39 research and could go stale. The user-visible point is "you don't control this in v0.5" — single paragraph, not table. |
| Tutorial-mode runnable end-to-end example | Full app setup including pool registration, ADBC driver install, schema, execute | Illustrative snippet starting at `Sales.query()....execute()` with reader-supplied setup | Diataxis classification: how-to is goal-oriented, reader supplies setup. The full-setup pattern belongs in `docs/src/tutorials/`. Existing how-to pages (verify in `arrow-output.rst`, `serialization.rst`) all start at the query/cursor level, not at pool registration. |

**Key insight:** Phase 40 is a writing phase. The temptation is to over-document the API (tables, parameter lists, full-setup examples). Resist. The page exists to answer "how do I stream results?" — three or four short, illustrative snippets plus a decision rule plus a backend-notes section is the full deliverable. The reference content is generated; the page links to it.

## Runtime State Inventory

(Phase 40 is not a rename / refactor / migration phase — this section is omitted per the protocol. The work is additive: one new file, one toctree edit. No existing string is being renamed, no runtime state is being touched.)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` | All build/test commands | ✓ (project standard) | latest | — |
| `sphinx` | `just docs-build` | ✓ (in `docs` dep group) | >=8.0 | — |
| `sphinx-design` | `.. tab-set::` directives (if used) | ✓ | >=0.6.0 | — |
| `sphinx-autoapi` | `:py:meth:` cross-references resolve | ✓ | >=3.6.0 | — |
| `shibuya` | Theme | ✓ | >=2025.1.1 | — |
| `just` | Convenience commands (`just docs-build`) | (assumed; standard project tooling) | — | Direct invocation: `uv run sphinx-build -W docs/src docs/_build` |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None — all already in place from the `docs` dep group.

To verify before starting:

```bash
uv sync --group docs
uv run sphinx-build --version
```

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Sphinx strict build (`-W` flag → warnings-as-errors) + semolina-docs-author skill quality checklist |
| Config file | `docs/src/conf.py` (already configured) |
| Quick run command | `uv run sphinx-build -W docs/src docs/_build` |
| Full suite command | `just docs-build` (same command, wrapped) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STREAM-03 | New how-to page exists at `docs/src/how-to/streaming.rst` with anchor `_howto-streaming:` | structural | `test -f docs/src/how-to/streaming.rst && grep -q "^.. _howto-streaming:" docs/src/how-to/streaming.rst` | ❌ Wave 0 (file does not exist yet) |
| STREAM-03 | Page is added to the how-to toctree | structural | `grep -q "^   streaming$" docs/src/how-to/index.rst` | ❌ Wave 0 (toctree entry missing) |
| STREAM-03 | Page contains runnable `fetch_record_batch()` example | structural | `grep -q "fetch_record_batch" docs/src/how-to/streaming.rst` AND `grep -q "code-block:: python" docs/src/how-to/streaming.rst` | ❌ Wave 0 |
| STREAM-03 | Page contains `for row in cursor:` example | structural | `grep -qE "for [a-z_]+ in cursor" docs/src/how-to/streaming.rst` | ❌ Wave 0 |
| STREAM-03 (SC-2) | Page has an explicit decision rule (looks for `.. tip::` or `.. note::` discussing fetch_arrow_table tradeoff) | structural | `grep -qE "(\.\. tip::|\.\. note::)" docs/src/how-to/streaming.rst && grep -q "fetch_arrow_table" docs/src/how-to/streaming.rst` | ❌ Wave 0 |
| STREAM-03 (SC-3) | Page has a Backend notes section | structural | `grep -q "^Backend notes$" docs/src/how-to/streaming.rst` (followed by `---` underline) | ❌ Wave 0 |
| STREAM-03 (SC-3) | Backend notes mentions end-of-stream semantics (drained reader, re-iteration) and batch sizes | structural | `grep -qiE "(drain|exhaust|empty)" docs/src/how-to/streaming.rst` AND `grep -qE "batch siz" docs/src/how-to/streaming.rst` | ❌ Wave 0 |
| STREAM-03 (SC-4) | Sphinx -W build passes — no warnings, no broken references, no missing anchors | build | `uv run sphinx-build -W docs/src docs/_build` | exists |
| STREAM-03 (SC-4) | Page passes humanizer pass (no flagged AI patterns — "powerful", "seamlessly", "leverage", "delve", "ensure that", "it's worth noting") | doc / manual | `for term in "powerful" "seamlessly" "leverage" "delve" "ensure that" "it's worth noting" "robust" "comprehensive"; do ! grep -iq "$term" docs/src/how-to/streaming.rst; done` | ❌ Wave 0 |
| STREAM-03 (SC-5) | REQUIREMENTS.md Traceability row for STREAM-03 marked `Complete` after page lands | doc | `grep -qE "STREAM-03\s*\|\s*Phase 40\s*\|\s*Complete" .planning/REQUIREMENTS.md` | exists (currently `Pending`) |
| STREAM-03 (SC-5) | REQUIREMENTS.md footer timestamp updated on close | doc | `grep -qE "Last updated:.*STREAM-03.*Complete" .planning/REQUIREMENTS.md` (or similar footer rev) | exists |
| Cross-reference integrity | `:py:meth:` anchors for `fetch_record_batch` and `fetch_arrow_table` resolve | build | covered by `-W` build (autoapi missing-ref → warning → error) | covered by build |
| Cross-reference integrity | `:ref:`howto-arrow-output`` and `:ref:`howto-queries`` and `:ref:`howto-serialization`` resolve | build | covered by `-W` build (broken refs → warning → error) | covered by build |

### Sampling Rate

- **Per task commit:** `uv run sphinx-build -W docs/src docs/_build` (≤30 s; fast).
- **Per wave merge:** Same build + manual humanizer review (the humanizer pass is documented in `@.claude/skills/semolina-docs-author/SKILL.md` Step 3 and `@.claude/skills/humanizer/SKILL.md`).
- **Phase gate:** Sphinx -W clean + humanizer pass applied + REQUIREMENTS.md traceability row flipped + `prek run --all-files` clean (mechanical — no code changes — but project hygiene gate) before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `docs/src/how-to/streaming.rst` — new file with anchor, sections, runnable snippets, decision rule, backend notes, See also.
- [ ] `docs/src/how-to/index.rst` — add `streaming` to toctree (one-line edit between `arrow-output` and `codegen`).
- [ ] `.planning/REQUIREMENTS.md` — STREAM-03 row flipped Pending → Complete on close + footer timestamp updated.
- [ ] No framework install needed — `docs` dep group already has everything.

### Validation Dimensions

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Build | `uv run sphinx-build -W` | Strict mode catches missing references, broken anchors, duplicate labels, malformed RST. Already wired into `just docs-build`. |
| Diataxis classification | Manual review per semolina-docs-author skill Step 1 | Confirm page is how-to (goal-oriented, illustrative snippets, reader supplies setup) and does not drift into tutorial or explanation territory. |
| Humanizer | Manual + grep per semolina-docs-author skill Step 3 | Removes promotional / AI vocabulary / vague attributions / em-dash overuse. The grep checks in Validation Architecture cover the most common offenders. |
| Cross-references | Implicit in Sphinx -W build | `:py:meth:` anchors resolve via sphinx-autoapi (depend on `cursor.py` docstrings shipped in Phase 39 — verified present). `:ref:` anchors resolve to other how-to pages — verified existing in `arrow-output.rst:1`, `serialization.rst:1`, `queries.rst:1`. |
| Decision-rule explicitness (SC-2) | Manual + grep | The rule must touch memory, latency, downstream consumer pattern. Grep `.. tip::` or `.. note::` and visually confirm all three axes mentioned. |
| Backend-notes coverage (SC-3) | Manual review against Phase 39 RESEARCH.md §Common Pitfalls | At minimum: shared state, drained-stream semantics, empty batches, batch sizes (driver-controlled), cursor lifetime. |
| Traceability close (SC-5) | grep on REQUIREMENTS.md | Lesson from Phase 39 Plan 02 — close-time update, not archive-time. |

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Documentation-only phase; no auth surface. |
| V3 Session Management | no | No session state. |
| V4 Access Control | no | No access-control surface. |
| V5 Input Validation | no | No user input handled. |
| V6 Cryptography | no | No cryptographic operations. |

### Known Threat Patterns for documentation

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Documentation drift between requirement text and shipped API (the v0.4.0 `to_arrow()` → `fetch_arrow_table()` lesson) | Repudiation (drift = "what was promised vs. what shipped") | Parity audit at close: verify the method names cited in `streaming.rst` exactly match `src/semolina/cursor.py` (specifically `fetch_record_batch`, `fetch_arrow_table`, `for row in cursor:`). Grep `fetch_record_batch` in both files. Same parity audit pattern Phase 39 Plan 02 used. |
| Misleading users into a code path that leaks resources (returning the reader from a closed cursor) | Information Disclosure (silent data corruption rather than disclosure, but the same shape — undefined behaviour past trust boundary) | The Backend notes section's "Cursor lifetime" bullet documents the contract. The shipped docstring on `fetch_record_batch` (`cursor.py:178-179`) also calls it out. Both are required. |
| Snippets that look runnable but aren't (missing imports, undefined classes) | Tampering (false expectations) | All `.. code-block:: python` snippets show necessary imports inline (`from semolina import ...`) OR begin from a documented base (the `Sales` model defined earlier on the page). The pattern is `arrow-output.rst:18-32` (full imports for first snippet, model reuse for subsequent ones). |

No new security-relevant surface beyond what Phase 39 already shipped. This phase is documentation only.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `fetchmany_rows()` loop as the streaming pattern (documented in `docs/src/how-to/serialization.rst:94-117`) | `fetch_record_batch()` for Arrow-native streaming + `for row in cursor:` for row-level lazy iteration | Phase 39 (2026-05-14) | The new page describes the Arrow-native streaming path. The existing `fetchmany_rows()` pattern in `serialization.rst` is NOT obsoleted — it remains useful for row-level batched processing without Arrow involvement (e.g. straight to JSON). Cross-reference, don't deprecate. |
| Single `fetch_arrow_table()` for all Arrow output | `fetch_arrow_table()` for materialised, `fetch_record_batch()` for streaming, `for row in cursor:` for lazy row iteration | Phase 39 | The new page explains the choice. |
| Diataxis tabs scattered in shibuya navigation | Same — no doc-site framework changes in this phase | — | The new page slots into the existing how-to section. |

**Deprecated/outdated:** Nothing in the existing docs becomes wrong with this phase. The new page adds; it does not replace.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The page slug `streaming.rst` and toctree position between `arrow-output` and `codegen` are stylistic conventions, not load-bearing decisions | Architecture Patterns | Low — any reasonable slug and toctree position works; the planner can choose differently. |
| A2 | Most streaming snippets on this page will not need warehouse-specific tabs because ADBC normalises streaming across DuckDB / Snowflake / Databricks | Anti-Patterns; Architecture Patterns | Medium — if a Phase 40 reviewer wants per-warehouse tabs for parity with `queries.rst`, the planner can add `.. tab-set::` blocks. The grep checks in Validation Architecture don't require tabs, so this is presentation, not gating. |
| A3 | The "Rule of thumb" decision rule example (~1 GB cutoff, HTTP-chunked / file-by-batch / message-queue downstream sinks) is illustrative and may need warmth/tone adjustment during humanizer pass | Architecture Patterns Pattern 2 | Low — exact wording is the writer's call. The required content (memory + latency + downstream consumer pattern, in one explicit place) is the gate. |
| A4 | Backlog item 999.1 (`fetch_df()` / `fetch_polars()`) is NOT yet shipped and should not be documented as if it exists | Locked Decisions; Anti-Patterns | High if violated — would document an API that doesn't exist, breaking SC-1's "runnable" requirement and creating reader confusion. Mitigation: planner verifies via grep that the page does not mention `fetch_df` or `fetch_polars`. |

**Most claims in this research are `[VERIFIED]` against Phase 39 artifacts, the live `cursor.py` source, and existing how-to pages.** Risk surface is low — the open assumptions are about wording style, not technical correctness.

## Open Questions

1. **Should the page include a worked example writing batches to a file (e.g. parquet via `pyarrow.parquet.ParquetWriter`) or streaming over HTTP (e.g. FastAPI `StreamingResponse`)?**
   - What we know: SC-1 says "runnable example snippets" plural; SC-2 mentions "downstream consumer pattern". A worked example would strengthen both.
   - What's unclear: Does the planner want to keep the page tight (just the API surface) or broaden it with one downstream-sink example?
   - Recommendation: Include ONE short downstream-sink example — `pyarrow.parquet.ParquetWriter`-style or `FastAPI StreamingResponse` (the latter ties into the existing `:ref:`howto-web-api`` page). The example reinforces SC-2's "downstream consumer pattern" requirement and stays in scope. Keep it under ~15 lines so the page doesn't sprawl. Default: ParquetWriter, since it's the most universally applicable and doesn't pull in a web framework.

2. **Should the page reference the (unshipped) `fetch_df()` / `fetch_polars()` backlog item as "coming soon", or stay silent?**
   - What we know: ROADMAP.md backlog 999.1 surfaced explicitly during Phase 40 discussion and recommends the page "prefer these where applicable" — but the methods don't exist yet.
   - What's unclear: The backlog note is ambiguous. It could mean "when implemented, update the page" or "mention them now as future work."
   - Recommendation: Stay silent on `fetch_df` / `fetch_polars` for now. Show the current path (`pa.Table.from_batches(...)` over `fetch_record_batch()` → `.to_pandas()` / `pl.from_arrow()`), then update the page when 999.1 ships. Documenting unshipped methods violates SC-1's runnable-example requirement. The backlog item's "update where applicable" can be re-read as "update the page when the methods ship."

3. **Does the toctree edit need its own commit, or bundle with the page-create commit?**
   - What we know: Phase 39 Plan 02 bundled REQUIREMENTS.md flip + new test into separate task commits but one phase close.
   - What's unclear: Project commit-granularity preference.
   - Recommendation: Single commit `docs(40-01): streaming how-to page`. The toctree entry is one line and meaningless without the page. Phase close commit can be separate (`docs(40): close phase`).

4. **Should `:ref:`howto-arrow-output`` get a reverse cross-link back to `:ref:`howto-streaming`` (i.e. modify `arrow-output.rst`)?**
   - What we know: Phase scope is one new page, not a docs sweep.
   - What's unclear: Whether a one-line cross-link addition to `arrow-output.rst` counts as a sweep.
   - Recommendation: Yes — add one bullet to `arrow-output.rst`'s "See also" pointing at `:ref:`howto-streaming``. It's a single line, makes the two pages discoverable from each other, and matches the project's existing "self-contained pages with See also" pattern (CLAUDE.md). Treat as a minor amendment, not a rewrite — semolina-docs-author skill says "Minor fixes... small corrections: not required" for the full workflow, so the humanizer pass doesn't need to run on `arrow-output.rst`. Decision should go to planner.

## Sources

### Primary (HIGH confidence)

- **CLAUDE.md** (project root) — documentation standards, mandatory skill directive, content type classifications, writing voice, build gates, code style. All directives in the "Project Constraints" table above are quoted directly.
- **`.claude/skills/semolina-docs-author/SKILL.md`** — Diataxis classification, audience, voice, workflow (Step 1 classify, Step 2 write, Step 3 humanizer), quality checklist. Mandatory load for any doc-writing PLAN.md per CLAUDE.md.
- **`.claude/skills/humanizer/SKILL.md`** v2.1.1 — full pattern list (promotional language, AI vocabulary, vague attributions, superficial -ing analyses, rule of three, em-dash overuse, etc.). Patterns most relevant to technical docs are summarised in semolina-docs-author Step 3.
- **`src/semolina/cursor.py`** (lines 9–17 typing pattern; 138–162 `fetch_arrow_table`; 164–196 `fetch_record_batch`; 222–284 `__iter__`/`__next__`) — the shipped API surface this page documents. Verified directly in the working tree.
- **`.planning/phases/39-streaming-arrow-output/39-RESEARCH.md`** §Pattern 1 / §Common Pitfalls / §Security Domain / §Don't Hand-Roll — verified streaming behaviour, pitfalls (cursor lifetime, shared state, empty batches, drained reader), Snowflake prefetch defaults.
- **`.planning/phases/39-streaming-arrow-output/39-01-cursor-streaming-impl-SUMMARY.md`** — "Rule 1 fix" OSError→StopIteration normalisation; documents the actual shipped behaviour for drained readers.
- **`.planning/phases/39-streaming-arrow-output/39-02-cross-backend-and-traceability-SUMMARY.md`** — parity audit pattern (verify shipped method names match requirement text); close-time traceability update lesson.
- **`docs/src/how-to/arrow-output.rst`** — exact template / structure / cross-reference style for this new page.
- **`docs/src/how-to/serialization.rst`** — `fetchmany_rows()` batched-iteration pattern that this page complements rather than replaces.
- **`docs/src/how-to/index.rst`** — toctree structure; insertion point for `streaming` entry.
- **`docs/src/how-to/queries.rst`** — sphinx-design tab-set with `:sync-group: warehouse` reference pattern.
- **`docs/src/conf.py`** — Sphinx configuration; confirms extensions (autoapi, sphinx-design, copybutton, napoleon, intersphinx), theme (shibuya), strict mode.
- **`.planning/REQUIREMENTS.md`** — STREAM-03 row text, traceability table format, Out of Scope table (used to identify what NOT to document).
- **`.planning/ROADMAP.md`** Phase 40 section + Backlog (999.1) — success criteria, deferred follow-ups.
- **`pyproject.toml`** — docs dep group versions verified (sphinx, shibuya, sphinx-design, sphinx-autoapi, sphinx-copybutton, sphinx-autobuild).
- **`justfile`** — `docs-build` and `docs-serve` recipes confirm strict mode (`-W` flag).

### Secondary (MEDIUM confidence)

- **Phase 39 RESEARCH.md §Sources** — chain-of-trust back to arrow-adbc source code and pyarrow docs for behavioural claims surfaced in Backend notes. Not re-verified for Phase 40; relied on Phase 39's verification.
- **arrow-adbc issue #1893** — cited via Phase 39 RESEARCH.md for the cursor-lifetime-vs-reader rule.

### Tertiary (LOW confidence)

- None. Every claim in the planner-facing sections has a Primary or Secondary source.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all doc dependencies already present and version-verified in `pyproject.toml`; configuration verified in `docs/src/conf.py`.
- Architecture patterns: HIGH — patterns are directly derived from existing how-to pages (`arrow-output.rst`, `serialization.rst`, `queries.rst`), all of which build clean under the current Sphinx -W config.
- Pitfalls / Backend notes content: HIGH — sourced entirely from Phase 39's verified findings (RESEARCH.md §Common Pitfalls, SUMMARY.md "Rule 1 fix"); no new behavioural claims made.
- Validation architecture: HIGH — Sphinx -W is the existing build gate; the grep-based structural checks are mechanical and cover the page-shape success criteria; humanizer pass is documented in the skill.
- Open questions: open by design — they are stylistic / scope-edge decisions for the planner, not technical unknowns.

**Research date:** 2026-05-14
**Valid until:** 2026-06-13 (30 days — docs ecosystem and the shipped API surface are both stable; the only thing that could invalidate this research is a change to the streaming API in `cursor.py` or a Sphinx config rewrite, neither of which is in v0.5 scope)
