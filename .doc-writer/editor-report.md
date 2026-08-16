# Editor Report

**Generated:** 2026-08-16
**Docs reviewed:** 30 `.rst` pages under `docs/src/` (the sphinx-autoapi output at
`docs/src/reference/api/` was excluded as build output and never touched)
**Files edited:** 14
**Build verification:** `just docs-build` — **build succeeded** (sphinx-build `-W`,
`nitpicky = True`). A baseline build was run before editing and also succeeded, so the
green result is attributable rather than inherited.

**Changes made:** 37
  - BLOCKING: 6
  - SUGGESTION: 18
  - NITPICK: 13

**Reported but deliberately not edited:** 13 (2 BLOCKING, 7 SUGGESTION, 4 NITPICK)

## Summary

The corpus is in unusually good shape. The humanizer pass found almost nothing: no
promotional language, no chatbot artifacts, no sycophancy, no filler phrases, no curly
quotes, no copula avoidance, no significance inflation. Prose reads as human-authored
throughout and the measurement-provenance style (dates, driver versions, "measured
against X") is a genuine strength. The real findings are consistency-level: a split
between `-ise` and `-ize` spellings that contradicts the project's own recorded rule, a
handful of pre-v0.6 "pool" survivals where the object is now an engine, twelve literal
em dashes against a corpus-wide `--` convention, and six public API symbols named in
prose without a link. The two freshly rewritten pages (`how-to/dto-codegen.rst`,
`reference/cli.rst`) verified accurate against `src/semolina/cli/dto_codegen.py` and
`src/semolina/codegen/query_resolver.py` on every claim checked — routes, exit codes,
precedence, and the identifier rules. The one substantive accuracy problem is on an
older page: `how-to/codegen.rst` still gives a reason for the Databricks `--check`
caveat that the project's own record falsified on 2026-08-15.

---

## Accuracy verification performed

Claims checked against source and the project record, all of which held:

| Claim | Page | Verified against |
|-------|------|------------------|
| Three mutually exclusive routes; combining exits `2` | `dto-codegen`, `cli` | `dto_codegen.py:_resolve_inputs` (lines 377-392) |
| `--name` with >1 DTO or with `--config` exits `2` | `dto-codegen`, `cli` | `dto_codegen.py:_named` (lines 219-225) |
| Field names must be a non-keyword identifier, not reserved | `dto-codegen`, `cli` | `query_resolver.py:is_valid_field_name` (soft keywords rejected too) |
| `--output` directory must exist, not created | `dto-codegen`, `cli` | `dto_codegen.py:_check_output` |
| Flag beats config for `--backend`/`--database`/`--output` | `dto-codegen`, `cli` | `dto_codegen.py:_resolve_inputs` (lines 418-431) |
| `--database` falls back to `DUCKDB_DATABASE`, then config | `cli` | typer `envvar="DUCKDB_DATABASE"` resolves before config merge — order as documented |
| Unrecognized config keys are errors | `dto-codegen`, `cli` | `dto_config.load_dto_config` via `_load_config` |
| Extra floors: `pyarrow>=17.0.0`, `polars>=1.0.0`, `pandas>=2.0.0`, `arrowmodel>=1.0.0`, `adbc-poolhouse[async]>=1.6.2` | `tutorials/installation` | `pyproject.toml` `[project.optional-dependencies]` |
| `semolina[duckdb]` installs `duckdb` and `pyarrow` | `tutorials/installation`, `backends/duckdb` | `pyproject.toml` (`duckdb==1.5.5` + `semolina[pyarrow]`) |
| `validate=True` costs roughly 2-5x | `typed-results` | `cursor.py:343` states the same figure — docs and source agree |
| Databricks zero-row probe route, measured 2026-08-15 | `dto-codegen` | `.planning/todos/completed/2026-08-12-verify-databricks-zero-row-fallback.md` |

No referenced source file was missing.

---

## docs/src/how-to/codegen.rst

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| "Check a committed model for drift" (the `.. warning::` at the end) | The warning says `--check` on Databricks is unverified "because that driver answers no describe-only call **and the zero-row route has not yet been confirmed against a live metric view**". The second half is stale. The zero-row route *was* confirmed against a live metric view on 2026-08-15 (`.planning/todos/completed/2026-08-12-verify-databricks-zero-row-fallback.md`; WINDOWS entry 12 closed), and `how-to/dto-codegen.rst` § "Read the probe route in the header" now states that measurement explicitly. The two pages contradict each other. The *conclusion* is still correct — WINDOWS entry 9 is open and CLI `--check` has only ever run end-to-end against DuckDB — so only the stated reason is wrong. | **Not edited** (per instruction 6: this is a measured-provenance claim). Suggested rewording for the author: keep "unverified on Databricks", replace the reason with "because `semolina codegen --check` has not been run end-to-end against a live metric view; the zero-row probe route it would use *was* confirmed there on 2026-08-15." |
| "Check a committed model for drift" | Missing known limitation. WINDOWS entry 17 (open, recorded 2026-08-16) records that `semolina codegen` and `codegen --check` disagree on every Databricks `variant` column: the metadata route annotates `JsonValue`, the probe route resolves `str`, so `--check` reports drift on a *correct* model. The page documents both the VARIANT → `JsonValue` annotation (§ "Read a VARIANT column's annotation") and `--check`, but never warns that combining them produces a guaranteed false positive on Databricks. A reader wiring `--check` into CI will hit this. | **Not edited** — writing the missing warning is authoring, not editing. Recommend the author add it beside the existing Databricks `--check` warning. |

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| "See also" | Three entries described the backend pages as "pool configuration". Since v0.6 the reader builds an *engine* that owns a pool, and the linked pages are about connection settings, not pool tuning. `backends/overview.rst` already describes the same three pages as "TOML configuration and connection details". | Changed "Snowflake / Databricks / DuckDB **pool** configuration" to "**connection** configuration" (3 lines). |

### NITPICK (reported, not edited)

| Section | Description | Recommendation |
|---------|-------------|----------------|
| Headings | Four section headings are not task-shaped for a how-to: "Understand the generated output", "Understand field type mapping", "Read a VARIANT column's annotation", "Read the raw warehouse type from a field comment". "Understand X" names a state of mind rather than a goal the reader can complete, which is mild blur toward explanation/reference. | Not edited — renaming a heading changes its underline and is a structural choice. Consider "Read the generated output" / "Map warehouse roles to field types" if the author agrees. |

---

## docs/src/how-to/dto-codegen.rst

Reviewed with the same scrutiny as the rest, as instructed. Every technical claim checked
resolved correctly against `src/semolina/cli/dto_codegen.py`.

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| "Declare every DTO in pyproject.toml"; "Exit codes" | `unrecognised` used twice, against the project's recorded Oxford `-ize` rule (`terminology.yaml` `spelling`, which lists `recognize` and rejects `recognise`). The same page's sibling `how-to/codegen.rst` already spells it `unrecognized`. | Normalized both to `unrecognized`. |

### NITPICK

| Section | Description | Fix |
|---------|-------------|-----|
| Six locations | Six literal em dashes (`—`) against a corpus-wide `--` convention (hundreds of instances, zero other literal em dashes outside this file and `type-fidelity.rst`). | Replaced ` — ` with ` -- `. Sentence structure and wording untouched: the surrounding prose uses the same dash construction, and several of these sentences carry dated measurements. |

### NITPICK (reported, not edited)

| Section | Description | Recommendation |
|---------|-------------|----------------|
| "Declare every DTO in pyproject.toml" | The page says `--database` "overrides what the section says", which is true, but does not mention that a `DUCKDB_DATABASE` environment variable *also* beats the config's `database` (typer resolves the envvar as the option value before the config merge). A stray env var silently wins over a committed config. `reference/cli.rst` states the full order correctly. | Consider one clause naming the env var here too. |
| Whole page | The "Exit codes" list-table and the two `[tool.semolina.dto]` key tables are duplicated verbatim-in-substance in `reference/cli.rst`. I verified the two copies currently agree on every row. This is deliberate under the project's self-contained-pages rule, so it is not blur — but it is two places to edit when an exit code moves. | Flagged only. No change recommended unless the author wants the how-to to defer to the reference for exit codes. |

---

## docs/src/reference/cli.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| `codegen-dto` § "Configuration" and § "Exit codes" | `Unrecognised` / `unrecognised` used twice, while the *same file* spells it `unrecognized` in the `codegen` exit-code table (line 83). An internal contradiction inside one reference page. | Normalized both to `unrecognized`, matching line 83 and the terminology rule. |

---

## docs/src/explanation/type-fidelity.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| "What can be NULL" | `recognising` → `-ize` rule. | Changed to `recognizing`. |

### NITPICK

| Section | Description | Fix |
|---------|-------------|-----|
| Six locations | Six literal em dashes against the corpus `--` convention. | Replaced ` — ` with ` -- `. No annotation, version number, or measurement text altered. |

---

## docs/src/explanation/duckdb-vs-warehouse.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| "Why Semolina does not smooth this over" | `normalising` → `-ize` rule (`streaming.rst` and `warehouse-testing.rst` already use `normalizes` / `normalized`). | Changed to `normalizing`. |

### SUGGESTION (reported, not edited)

| Section | Description | Recommendation |
|---------|-------------|----------------|
| "Driver errors, mostly unmeasured" | "The recorded cassettes **the test suite replays** contain only successful queries" references Semolina's own internal test suite, which a reader cannot act on (universal Rule 1). The provenance itself is valuable and clearly deliberate. | Not edited — rewording risks weakening a measurement-provenance statement the project values. Suggested phrasing if the author agrees: "Neither has been measured: no observation exists of what either driver raises for those four failures." |

---

## docs/src/how-to/web-api.rst

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| "Handle errors", the `SemolinaViewNotFoundError` note | Three public API symbols named in prose as plain inline literals with no link (Rule 4): `SemolinaViewNotFoundError`, `SemolinaConnectionError`, and `Engine.introspect()`. All three are documented in the generated reference. | Linked all three in the note body: `:py:exc:`~semolina.engines.base.SemolinaViewNotFoundError``, `:py:exc:`~semolina.engines.base.SemolinaConnectionError``, `:py:meth:`Engine.introspect() <semolina.engines.base.Engine.introspect>``. The admonition *title* was left as plain literals to avoid a role in a directive argument. |

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| "Handle errors" | `optimisation` → `-ize` rule. | Changed to `optimization`. |

### SUGGESTION (reported, not edited)

| Section | Description | Recommendation |
|---------|-------------|----------------|
| "Handle errors", after the driver-exception table | Two Rule 1 leaks: "the recorded test cassettes contain only successful queries" (Semolina's internal suite) and 'Treat those two drivers as "catch `Error`" **until someone fills the column in**', which addresses a contributor rather than a user. | Not edited, same reason as `duckdb-vs-warehouse.rst`. Suggest replacing the second with "…until you have measured your own driver." |
| Whole page (662 lines) | The page pursues at least six distinct goals (engine setup, sync endpoint, async endpoint, error handling, timeouts, client disconnect, multi-engine routing) and carries substantial explanation-mode passages inside them — "That asymmetry is not an oversight…", "The pool rejects the concurrent access rather than serializing it on purpose: a lock would let two tasks' statements interleave…". Mild blur toward explanation, plus a length that makes it hard to scan for one goal. | Not fixed: this is structural, and splitting a page is the author's call. Candidate split: cancellation/timeout/disconnect material into its own how-to, which `howto-web-api-timeouts` and `howto-web-api-client-disconnect` are already labelled for. |

---

## docs/src/how-to/connection-pools.rst

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| "Two ways to use an engine"; "Open a raw connection"; "Manage the engine lifecycle" | Three public `Engine` methods named in prose as plain literals with no link (Rule 4): `engine.execute(query)`, `engine.connect()`, `engine.dispose()`. All three are in the generated reference, and the page already links `create_engine`, `register`, `get_engine` and `unregister`, so the omission was inconsistent within the page. | Linked all three at first mention, keeping the displayed text: `:py:meth:`engine.execute(query) <semolina.engines.base.Engine.execute>``, `:py:meth:`engine.connect() <semolina.engines.base.Engine.connect>``, `:py:meth:`engine.dispose() <semolina.engines.base.Engine.dispose>``. |

### NITPICK (reported, not edited)

| Section | Description | Recommendation |
|---------|-------------|----------------|
| Title / `:ref:` label | The label is `howto-connection-pools` and the toctree entry is `connection-pools`, but the title is "How to connect an engine to your warehouse" and the page is mostly about engines. Fifteen cross-references point at the old label. | Not changed — renaming the label would break every inbound `:ref:`. Noted only so the mismatch is a known one. |

---

## docs/src/how-to/typed-results.rst

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| "Annotate a VARIANT column", the warning | `semolina.JsonValue` named in prose as a plain literal with no link, in the exact place a reader most needs to tell it apart from `pydantic.JsonValue` (Rule 4). `how-to/codegen.rst` already links the same symbol. | Linked as `:py:obj:`semolina.JsonValue <semolina.types.JsonValue>``, preserving the displayed spelling. |

---

## docs/src/how-to/warehouse-testing.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| "Set up an in-memory engine fixture" | Two near-identical `.. note::` admonitions about `engine._pool` being private — one before the fixture code, one after — separated by a single paragraph. Each carried one clause the other lacked ("pin your Semolina version" / "call `dispose()` rather than touching it directly"). | Consolidated into the first note, folding in the second's unique guidance, and removed the duplicate. Both pieces of advice survive; the repetition does not. |

### NITPICK

| Section | Description | Fix |
|---------|-------------|-----|
| "Set up an in-memory engine fixture" | `:meth:` used without the `py:` prefix — the only such role in all 30 pages; every other one of ~150 roles is `:py:class:` / `:py:meth:` / `:py:func:`. | Changed to `:py:meth:`. Resolves identically; consistency only. |

---

## docs/src/how-to/backends/duckdb.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| "Configure manually" | The lead-in read "When credentials come from a vault or secrets manager, pass a config object…". DuckDB has no credentials — the page's own field table lists only `database` and `read_only`. The sentence is copy-pasted from the Snowflake and Databricks pages, where it is correct. | Rewritten to "When the database path comes from your own code rather than a TOML file, pass a config object to `create_engine()`". Only the premise changed; the instruction and the code sample are untouched. |

### NITPICK (reported, not edited)

| Section | Description | Recommendation |
|---------|-------------|----------------|
| The `semantic_views` version note | This page states a floor of extension v0.8.0. `how-to/web-api.rst` states that aborting a `semantic_view()` query needs 0.12.0 or newer, which is what the pinned `duckdb==1.5.5` installs. Not a contradiction — different floors for different capabilities — but a reader who lands here first takes 0.8.0 away as the whole answer. | Consider a clause pointing at the cancellation floor. Neither version number was altered. |

---

## docs/src/how-to/backends/snowflake.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| The `database` / `warehouse` note | "optional for the query **pool**" — pre-v0.6 vocabulary for what is now an engine. | Changed to "optional for the query **engine**". The contrast with `semolina codegen` that the sentence exists to draw is unchanged. |

---

## docs/src/how-to/arrow-output.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| Intro | "works with any ADBC-backed **pool** (Snowflake, Databricks, DuckDB)" — pre-v0.6 vocabulary. | Changed to "any ADBC-backed **engine**". |

### NITPICK (reported, not edited)

| Section | Description | Recommendation |
|---------|-------------|----------------|
| "When to use Arrow output" | The closing line reads "All four consume the same underlying stream, so pick one per cursor", but the bullet list above names five methods (`fetch_df`, `fetch_polars`, `fetch_arrow_table`, `fetchall_rows`, `into`) across four bullets. Ambiguous whether "four" counts bullets or methods. | Not edited — I will not change a count without knowing which reading was intended. |

---

## docs/src/how-to/codegen-credentials.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| "See also" | Same "pool configuration" survival as `codegen.rst`, on the same three links. | Changed to "connection configuration" (3 lines). |

---

## docs/src/tutorials/installation.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| "Install a backend extra" | "use a local in-memory DuckDB **pool**" — pre-v0.6 vocabulary; the linked page builds an engine. | Changed to "in-memory DuckDB **engine**". |

### SUGGESTION (reported, not edited)

| Section | Description | Recommendation |
|---------|-------------|----------------|
| "Optional: dataframes and typed results" | The section enumerates four extras, the method each unlocks, which extras compose which, and a line of exact version floors (`pyarrow>=17.0.0`, `polars>=1.0.0`, `pandas>=2.0.0`, `arrowmodel>=1.0.0`). That is reference material inside a tutorial — the learner installing Semolina for the first time does not need the floor table to reach a first query. All values verified accurate against `pyproject.toml`. | Not fixed: relocating it needs a home in `reference/`, which is authoring. If the author agrees, a one-line pointer would keep the tutorial on its path. |

---

## Cross-page findings (reported, not edited)

### SUGGESTION

| Where | Description | Recommendation |
|-------|-------------|----------------|
| `how-to/queries.rst`, `how-to/filtering.rst`, `how-to/models.rst`, `how-to/ordering.rst` | Every `.. tab-set::` on these four pages declares `:sync-group: warehouse` but offers only **Snowflake** and **Databricks** tab-items — no DuckDB. Eleven other tab-sets across the docs (`dto-codegen`, `typed-results`, `codegen`, `codegen-credentials`, `connection-pools`, `backends/overview`, `warehouse-testing`) offer all three. Because the group is synced, a reader who selects DuckDB on any of those pages and then opens `filtering.rst` gets the Snowflake tab with no indication that their choice was dropped — on the very backend most readers develop against. Rule 3 (consistent structure). | Author task: add a DuckDB tab showing the `semantic_view()` form, or drop `:sync-group:` from the two-tab sets so the mismatch is not silent. |
| `how-to/ordering.rst` § "Build 'top N' queries" | Uses `row.country` / `row.revenue` attribute access with no "Column keys are whatever your warehouse called them" warning. That warning appears on `queries.rst`, `serialization.rst`, `web-api.rst` and `tutorials/first-query.rst` in near-identical wording, and `explanation/duckdb-vs-warehouse.rst` calls attribute access the single trap that breaks on leaving DuckDB. `ordering.rst` is the only page showing the pattern unguarded. | Author task: add the same warning admonition, or switch the example to `row["COUNTRY"]`. |

---

## Terminology Changes

| Term | Before | After | Authority | Files |
|------|--------|-------|-----------|-------|
| unrecognized | `unrecognised` (4) | `unrecognized` | `terminology.yaml` `spelling` `-ize` rule; `codegen.rst:506` and `cli.rst:83` already used it | `dto-codegen.rst`, `cli.rst` |
| recognizing | `recognising` | `recognizing` | same rule (`recognize` is a named example) | `type-fidelity.rst` |
| normalizing | `normalising` | `normalizing` | same rule; `streaming.rst` already uses `normalizes` | `duckdb-vs-warehouse.rst` |
| optimization | `optimisation` | `optimization` | same rule | `web-api.rst` |
| engine | "ADBC-backed pool", "DuckDB pool", "the query pool" | "engine" | `terminology.yaml` `project_terms`: prefer "engine" over "pool" for the thing the reader holds; v0.6 Engine-owns-pool model | `arrow-output.rst`, `installation.rst`, `backends/snowflake.rst` |
| connection configuration | "pool configuration" (6) | "connection configuration" | as above; matches `backends/overview.rst`'s own description of the same three pages | `codegen.rst`, `codegen-credentials.rst` |

`behaviour` (9 uses, 0 `behavior`) was already consistent with the recorded `-our` rule
and was left alone. `labelling` was left alone (British doubling is orthogonal to the
`-ize` rule). `PyArrow`/`pyarrow`, `polars`, `pandas` and the semantic view / metric view
split were all already correct and needed no normalization.

## Not changed, by instruction

No type annotation, alias string, exit code, version number, date, or measured result was
altered anywhere in this pass. Where a claim looked wrong it was reported above rather
than edited — one case, the Databricks `--check` rationale in `how-to/codegen.rst`.
`docs/src/reference/api/` was not read or written.
