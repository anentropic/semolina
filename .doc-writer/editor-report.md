# Editor Report

**Generated:** 2026-09-05
**Files reviewed:** 27 `.rst` files under `docs/src/` (12 how-to, 6 tutorials, 4 explanation,
3 reference, root `index.rst`); `docs/src/reference/api/` excluded (sphinx-autoapi generated)
**Files edited:** 11
**Changes made:** 22
  - BLOCKING: 1 (3 edit sites)
  - SUGGESTION: 14
  - NITPICK: 7

## Summary

The consolidated how-to set holds together: the four merged pages read as single documents
rather than concatenations, and the `:sync-group: warehouse` tab-sets in the new
`backends.rst` genuinely deduplicate — no prose common to all three warehouses is hiding
inside a `tab-item`. The defects found were one accuracy contradiction between two pages
about what `semolina codegen --backend duckdb` reads, four places where merged material was
restated instead of integrated, three cross-links describing pages by titles they no longer
have, and one opener rhythm shared by three pages. `just docs-build` (`sphinx-build -W`,
`nitpicky = True`) passes after the edits.

---

## docs/src/how-to/codegen-credentials.rst

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| Intro, "Configure in .semolina.toml", "Troubleshooting" | Page claimed ``--backend duckdb`` reads ``[connections.duckdb]``, "the section name always matches the backend", and showed a ``[connections.duckdb]`` TOML example. `src/semolina/cli/codegen.py:155-163` short-circuits DuckDB to `DuckDBConfig(database=_normalize_database_path(database), read_only=True)` and never reaches `warehouse_config()`, so no TOML is read. This directly contradicted `backends.rst`, which had it right. | Narrowed the section-name rule to Snowflake and Databricks; added a paragraph stating DuckDB codegen reads no TOML and takes `--database` / `DUCKDB_DATABASE` only; replaced the DuckDB TOML tab-item with the equivalent command line (tab-set and `:sync:` preserved); scoped the exit-2 warning and troubleshooting entry per backend. |

---

## docs/src/how-to/backends.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| Snowflake / Databricks / DuckDB | Each per-backend section ended with a "Result column names" subsection restating what the common "Run a query" tab-set and its warning already said, plus the case-folding facts already stated in the "Inspect the generated SQL" tabs. Triplication of deduplicated material, against the page's own stated contract ("the per-backend sections cover the settings and quirks that belong to one warehouse only"). | Removed all three subsections. The common section is now the single home for column naming, and the DuckDB caveat it carried is preserved as a "See also" entry to `explanation-duckdb-vs-warehouse`. |
| Opening | Opened `:ref:`tutorial-first-query` runs ...`, the same construction as `queries.rst`. | Reworded to lead with the reader's warehouse rather than the tutorial's verb. |
| "Choose an extra" | Two consecutive sections with near-identical headings ("Choose an extra", "Install the extra"); the first is a three-column backend comparison of which only one column is about extras. | Retitled to "Pick your backend". |
| See also | No route from the page to the DuckDB-vs-warehouse explanation, which the removed DuckDB subsection had carried. | Added the entry. |

---

## docs/src/how-to/streaming.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| Intro | Four consecutive intro paragraphs, the third a roadmap sentence ("Both halves are below ... followed by the rule of thumb") duplicating the second. | Removed the roadmap sentence. |
| "Choose between the two" | The `.. tip:: Rule of thumb` restated, near-verbatim, the three paragraphs immediately above it, which in turn restate the intro. Three statements of one trade-off. | Removed the tip; kept the prose and the shape-vs-size bullet list. |
| "Fetch the result in batches" | "Feed a downstream sink" (a synchronous `fetch_record_batch()` example from the merged `arrow-output` material) sat after the async iteration and cancellation subsections, so the section ran sync → async → sync. An appended-annex seam. | Moved it to the end of the synchronous trio, before "Iterate rows lazily with ``async for row in cursor:``". Section order is now sync entry points, sink, async entry points, cancellation. |

---

## docs/src/how-to/queries.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| "Fetch methods" | The list of other result shapes gave `howto-arrow-output` and `howto-streaming` as two separate bullets, but since the merge both land on "How to fetch results in bulk". Presented one guide as two. | Merged into a single `howto-streaming` bullet covering whole-result and batched fetching; dropped the lead-in phrase "each with its own guide", which is no longer true. |
| See also | `- :ref:`howto-backends-overview` -- SQL differences between Snowflake and Databricks` described the deleted overview page, not the merged one (which covers three backends and connection configuration). | Retargeted to the `howto-backends` label used by the rest of the how-to set, with an accurate description. |

### NITPICK

| Section | Description | Fix |
|---------|-------------|-----|
| "Execute and read results" | Stray double blank line before the "Fetch methods" subheading. | Collapsed to one. |

---

## docs/src/how-to/connection-pools.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| "Size the pool" | Three admonitions stacked back to back (`warning`, `tip`, `note`), against the project's tone rule; the `note` also restated `backends.rst`'s in-memory DuckDB warning almost word for word. | Folded the sizing `tip` into prose under the parameter table where it belongs, and converted the DuckDB `note` to prose that keeps the sizing facts and defers the reason and the error class to `:ref:`howto-backends-duckdb``. One admonition remains. |
| "Size the pool" | Retitled page had to stop claiming warehouse connection setup; verified it now does (intro defers to `howto-backends`, and every inbound "connect to your warehouse" description elsewhere was checked). | No further change needed. |

### NITPICK

| Section | Description | Fix |
|---------|-------------|-----|
| "Size the pool" | ` ``adbc-poolhouse`` ` in prose about the library, where the rest of the doc set writes the name bare and reserves the literal for package specs and config classes. | Unwrapped. |
| "Size the pool" | Stray double blank line left by the removed `tip`. | Removed. |

---

## docs/src/how-to/web-api.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| Intro | Two consecutive orientation paragraphs: the first enumerates what this page covers, the second enumerates what the tutorial covers. After the trim from 709 lines the second list was mostly a second table of contents. | Compressed to the assumption plus two pointers. |

---

## docs/src/how-to/warehouse-testing.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| Opening | Third of three how-tos opening `:ref:`tutorial-X` builds ...` (with `connection-pools.rst` and `web-api.rst`). | Reworded to lead with the outcome the tutorial reached. The other two keep their distinct continuations. |

---

## docs/src/index.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| "Go further" card grid | Card titled "Connect to your warehouse" pointing at a page now titled "How to configure your warehouse backend". | Retitled to "Configure your warehouse backend". Card body was already accurate for all three backends. Link target left on the protected `howto-backends-overview` label. |

### NITPICK

| Section | Description | Fix |
|---------|-------------|-----|
| Tagline, "Define models" card | Two prose lines over the 100-character limit (148 and 129). | Wrapped. |

---

## docs/src/reference/config.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| See also | `-- choose and configure a backend` is the deleted page's title. | Replaced with "the connection settings each warehouse takes". |

---

## docs/src/tutorials/installation.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| See also | `-- connect to Snowflake or Databricks` reads like the deleted "How to connect to ..." pages and omits DuckDB, which the merged page treats as a shippable backend. | Replaced with "point the same query code at Snowflake, Databricks or DuckDB". |

---

## docs/src/how-to/typed-results.rst

### NITPICK

| Section | Description | Fix |
|---------|-------------|-----|
| `JsonValue` warning | One prose line at 104 characters. | Wrapped. |

---

## Verified and left unchanged

- **Every protected measured claim was re-checked, and none needed changing.** Confirmed
  against source: `SnowflakeConfig` requires only `account` (`_snowflake_config.py:36`);
  `DatabricksConfig`'s two connection forms; pool defaults 5 / 3 / 30 / 3600
  (`_base_config.py:111-121`); DuckDB `:memory:` pinning `pool_size` to 1 and raising a
  pydantic `ValidationError` above it, file paths defaulting to 5
  (`_duckdb_config.py:34-41, 104-125`); `.limit()` raising `TypeError` on non-`int` and
  `ValueError` on `n <= 0` at build time, `.where(None)` returning `self`, `order_by()`
  raising `TypeError` on anything that is not a `Field` or `OrderTerm`
  (`query.py:202-302`); `semolina codegen --backend duckdb` reading no TOML
  (`cli/codegen.py:150-167`, shared by `codegen-dto` via `cli/dto_codegen.py:63`).
- **The two deliberate omissions are intact.** No per-warehouse NULL-ordering default was
  added; the `decimal256` → polars `PanicException` note is untouched.
- **`connection-pools.rst` repeats the same eight-line `SnowflakeConfig` / `create_engine`
  snippet seven times**, and its "Build an engine from a config object or a connection name"
  section overlaps `backends.rst`'s two "Configure ..." sections. Left alone: each instance
  illustrates a different step (direct pattern, config object, async, sizing, lifecycle,
  async lifecycle, two engines), the page was not part of the merge, and collapsing them
  would cost more than the repetition does. Worth the author's judgement on a later pass.
- **`streaming.rst` "Backend notes" restates the empty-batch sentence** from the
  `fetch_record_batch()` subsection. Left: "Backend notes" is a scannable recap list and a
  reader arriving there has not necessarily read the subsection.
- **`shaping-a-report.rst`'s "Order and limit results" card** now deep-links into
  `howto-ordering`, a section of "How to build queries", where a sibling card in the same
  grid points at the page as a whole. Left: the deep link is accurate, the label is
  protected, and both entry points are useful.
- **`streaming.rst` is the only how-to whose opener names no tutorial.** Left deliberately —
  eleven of twelve already name one, and adding a twelfth would deepen the rhythm the
  previous pass flagged rather than relieve it.
- **Diataxis integrity:** all twelve how-to pages stay goal-oriented. No tutorial-style
  hand-holding was absorbed during the merges; `backends.rst` is the most instructional of
  them but is organised by goal ("Install the extra", "Run a query"), not by lesson, and
  makes decisions for the reader rather than teaching alternatives. No structural blur to
  report.
- **Cross-reference linking:** the query builder's methods (`.metrics()`, `.to_sql()`,
  `.limit()`, `.using()`) are members of the private `_Query` class, which `autoapi_options`
  omits, so they have no reference target and correctly appear as plain literals. Public
  symbols (`create_engine`, `SemolinaCursor`, `Metric`, `into`, `fetch_arrow_table` ...) are
  linked with `:py:...:` roles at their substantive mentions. No missing or broken links
  found; `nitpicky = True` confirms the rest.

## Terminology Changes

| Term | Before | After | Authority |
|------|--------|-------|-----------|
| adbc-poolhouse | ` ``adbc-poolhouse`` ` (prose about the library, `connection-pools.rst`) | adbc-poolhouse | Dominant usage: bare in `web-api.rst` (5), `streaming.rst`, `warehouse-testing.rst`; literal reserved for package specs (`adbc-poolhouse[snowflake]`) and config classes |

No other normalizations were needed. `PyArrow` (prose) vs `pyarrow` (package/module),
`DataFrame` (class) vs "dataframe" (concept), and the three warehouse names are already
consistent everywhere outside code blocks and `:sync:` values. `.doc-writer/terminology.yaml`
(version 2) matches `semolina.__all__` and needed no update.
