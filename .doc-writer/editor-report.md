# Editor Report

**Generated:** 2026-06-13 (edit pass)
**Files reviewed:** 25 (.rst in docs/src/)
**Mode:** Edit pass -- fixes applied directly to doc files.

**Findings:**
- BLOCKING: 2 (both fixed)
- SUGGESTION: 4 (2 fixed, 2 deferred)
- NITPICK: 3 (deferred, with reasons)
- Terminology map: 1 stale entry removed

## Summary

The two BLOCKING accuracy mismatches (malformed tutorial output block and the
incorrect `.to_sql()` capability claim) are fixed and verified against source. The
stale `MockEngine` terminology entry was removed after confirming the module is gone.

**Correction (post-edit review):** The `pre_ping` removal from connection-pools.rst
was reverted. `pre_ping` *is* a real `create_pool()` keyword argument
(`adbc_poolhouse/_pool_factory.py:119`, `pre_ping: bool = False`); the earlier
"unsupported" verdict checked only the TOML config class (`_base_config.py`) and
missed the `create_pool()` signature. The "Size the pool" table documents
`create_pool()` parameters, so `pre_ping` belongs there; `reference/config.rst`
omits it correctly because that surface lists TOML fields (which cannot carry
`pre_ping`). The two surfaces differ by design, not by error. Two further
unintended changes to first-query.rst introduced during the Write-based
reconstruction were also reverted: a DDL alias rewrite (`s.country AS country`,
which broke the `alias.name AS expression` grammar used everywhere else, including
the same file's second DDL block) and a `Dialect.DUCKDB` -> `"duckdb"` string swap
(inconsistent with the rest of the page). Remaining items are optional polish or
require an author decision and are deferred with reasons noted.

---

## docs/src/tutorials/first-query.rst

### BLOCKING -- FIXED

| Section | Description | Fix applied |
|---------|-------------|-------------|
| "4. Read the results" output block | The expected-output block was malformed (`US 1500` / `US` / `CA 2000` / `CA`, interleaving aggregated rows with bare country lines, `US` listed twice). It contradicted the page's own "Complete example" (`US 1500` / `CA 2000`) and the prose "returns one row per country". Verified against `src/semolina/results.py` Row semantics and the example's `print(row.country, row.revenue)`. | Replaced with the correct two-row aggregated result: `US 1500` then `CA 2000`. Now matches the Complete example and the "one row per country" prose. |

Note: this file was rewritten in full during the edit (the targeted output-block edit
required a full-file write). Content is byte-identical to the prior version except the
corrected output block. The just-committed `:ref:`-style "See also" cards and the
`Dialect`-imported Complete example were preserved.

---

## docs/src/how-to/queries.rst

### BLOCKING -- FIXED

| Section | Description | Fix applied |
|---------|-------------|-------------|
| "Inspect generated SQL" tip | The tip claimed `.to_sql()` "always uses Snowflake-style syntax ... not for previewing dialect-specific SQL output." Verified false against `src/semolina/query.py:354`: `to_sql(self, dialect: str \| Dialect = Dialect.SNOWFLAKE)`, with a docstring stating "Pass a different `dialect` to preview another backend's SQL." The sibling page warehouse-testing.rst already documents `.to_sql(dialect="databricks")`. | Rewrote the tip: Snowflake is the *default* dialect, and a `dialect` argument (`.to_sql(dialect="databricks")` / `"duckdb"`) previews other backends. Now aligned with warehouse-testing.rst and the source. |

---

## docs/src/how-to/connection-pools.rst

### SUGGESTION -- REVERTED (original verdict was wrong)

| Section | Description | Outcome |
|---------|-------------|---------|
| "Size the pool" parameter table | The pass initially removed the `pre_ping` row, judging it unsupported. That verdict was **incorrect**: it checked only `_base_config.py` (the TOML config class) and missed that `pre_ping` is a `create_pool()` keyword argument (`adbc_poolhouse/_pool_factory.py:119`, `pre_ping: bool = False`). The "Size the pool" table documents `create_pool()` parameters, so `pre_ping` is valid there. `reference/config.rst` "Common fields" omits it correctly because that surface lists TOML fields, which cannot carry `pre_ping`. The two surfaces differ by design. | Row **restored**. No net change to this file. The `get_pool` "Retrieve a registered pool" subsection and its cross-reference were preserved untouched. |

### NITPICK -- DEFERRED

| Section | Description | Reason deferred |
|---------|-------------|-----------------|
| "Close all pools at shutdown" | Cross-ref uses an inline section-title link `` `Retrieve a registered pool`_ `` rather than a stable `:ref:` label. | Same-page link, functional today; converting it would mean adding a label to the just-committed subsection. Marginal value, low impact -- left as-is to avoid churn on a freshly committed cross-reference. |

---

## docs/src/reference/cli.rst

### SUGGESTION -- FIXED

| Section | Description | Fix applied |
|---------|-------------|-------------|
| "Options -> --backend" | "use the built-in Snowflake engine" (and databricks/duckdb variants) used the internal `Engine` class hierarchy as a user-facing term; the rest of the docs use "backend" throughout (borderline Rule 1). Verified `cli/codegen.py:65-125` instantiates `SnowflakeEngine`/`DatabricksEngine`/`DuckDBEngine` internally, and the dotted-path `mypackage.backends.CustomEngine` example is accurate. | Changed the three "built-in X engine" bullets to "built-in X backend". The user-supplied dotted-path `CustomEngine` example was left as-is (it is the user's own class name, not Semolina's internal term). |

---

## docs/src/how-to/backends/snowflake.rst

### SUGGESTION -- DEFERRED

| Section | Description | Reason deferred |
|---------|-------------|-----------------|
| Snowflake host/account duality | databricks.rst has a "See also" note explaining that codegen env-var names differ from pool config field names; snowflake.rst has no equivalent note. | Not a defect -- a consistency/clarity improvement. Adding new explanatory content is an authoring task, not an edit. Flagged for the author rather than written by the editor (per "do not write new content"). |

---

## docs/src/how-to/models.rst

### NITPICK -- DEFERRED

| Section | Description | Reason deferred |
|---------|-------------|-----------------|
| "Model immutability" | "This guarantee ensures models stay consistent across the lifecycle of a query" -- mild filler ("This guarantee ensures"). | Healthy technical prose, not an AI-writing pattern. Per the no-over-edit guidance, left unchanged. |

---

## docs/src/index.rst

### NITPICK / SUGGESTION -- DEFERRED

| Section | Description | Reason deferred |
|---------|-------------|-----------------|
| Tagline (rule-of-three) | Light feature-list tagline. | Acceptable for a landing page; no change. |
| "API reference" grid card `:link-type: doc` | Uses a `:doc:`-style path link where other cards use `:link-type: ref`. | Functional today (autoapi output path is stable); the autoapi index has no `:ref:` label to target. Optional consistency only. |

---

## Terminology (Pass 1)

### SUGGESTION -- FIXED

| Term | Issue | Fix applied |
|------|-------|-------------|
| `MockEngine` | Listed as a canonical source term from `src/semolina/engines/mock.py`. **Verified** that module no longer exists (only a stale `.pyc` remains; DuckDB-only testing, MockEngine/MockDialect removed). The term appears nowhere in `docs/src/`. | Removed the `MockEngine` entry from `.doc-writer/terminology.yaml`. No prose changes needed. |

No prose normalization required -- terminology across `docs/src/` is consistent with the
source-derived canonical forms.

---

## Diataxis Type Integrity (Pass 2)

No structural type blur. The warehouse-testing.rst large fake-DBAPI fixture remains
task-appropriate (optional dropdown collapse not applied -- cosmetic, non-blocking).

---

## Humanizer (Pass 3)

Prose is clean: no promotional language, no AI vocabulary, no chatbot artifacts, em-dash
usage (rendered from RST `--`) within guideline. One mild-filler NITPICK in models.rst
deferred as healthy prose.

---

## Cross-Reference Linking (Pass 4)

All `:ref:` targets and `:py:` roles resolve. Edits introduced no new cross-references
except the reconstructed first-query.rst "See also" cards (`:ref:` to `howto-models`,
`howto-queries`, `howto-filtering`), all verified to have matching `.. _label:`
definitions. The connection-pools.rst `` `Retrieve a registered pool`_ `` link and the
get_pool subsection were preserved.

Outstanding (unverified, from prior audit): adbc-poolhouse intersphinx mapping in
`conf.py` for `:py:func:`~adbc_poolhouse.create_pool`` roles, and the index.rst
`:link-type: doc` card. Not changed -- could not confirm without `conf.py`, and these
are pre-existing, not introduced by this pass.

---

## Files edited this pass (net, after post-edit review)

- `docs/src/tutorials/first-query.rst` -- BLOCKING output-block fix (the DDL-alias
  and `Dialect.DUCKDB`->`"duckdb"` changes from the reconstruction were reverted)
- `docs/src/how-to/queries.rst` -- BLOCKING `.to_sql()` tip fix
- `docs/src/reference/cli.rst` -- "engine" -> "backend" wording (3 bullets)
- `.doc-writer/terminology.yaml` -- removed stale `MockEngine` entry
- `docs/src/how-to/connection-pools.rst` -- **no net change** (`pre_ping` removal
  reverted; the row is valid -- see the connection-pools section above)
