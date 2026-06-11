# Editor Report

**Generated:** 2026-06-09
**Files reviewed:** 26 (.rst)
**Mode:** Report-only (no doc files edited)
**Changes made:** 0 (audit only)

Issue counts (would-be changes):
- BLOCKING: 5
- SUGGESTION: 9
- NITPICK: 6

## Summary

The documentation is well-structured, terminologically consistent, and largely free of AI-writing tells; Diataxis type integrity is strong across tutorials, how-to guides, and explanation. The most serious issues are two source-verified accuracy mismatches and a how-to guide (`warehouse-testing.rst`) built entirely on the deprecated dialect-less `register()` engine path, which contradicts the project's documented clean break from the Engine API.

---

## Source verification performed

| Claim | Doc location | Source | Result |
|-------|--------------|--------|--------|
| Snowflake introspects via `SHOW COLUMNS IN VIEW` | codegen.rst:53 | `engines/snowflake.py:268,328` | Accurate |
| Snowflake introspects via `SHOW COLUMNS IN SEMANTIC VIEW` | models.rst:148 | `engines/snowflake.py` uses `SHOW COLUMNS IN VIEW` | **Mismatch** |
| Databricks introspects via `DESCRIBE TABLE EXTENDED AS JSON` | codegen.rst:56 | `engines/databricks.py:330` | Accurate |
| DuckDB introspects via `DESCRIBE SEMANTIC VIEW` | codegen.rst:59 | `engines/duckdb.py:202` | Accurate |
| Version `0.4.0` | installation.rst:110 | `pyproject.toml:3` | Accurate |
| `.to_sql()` always Snowflake-style regardless of pool | queries.rst:370, warehouse-testing.rst:142 | `query.py:353-381` (MockDialect) | Accurate |
| `register(name, engine)` without `dialect=` | warehouse-testing.rst:28,68,93 | `registry.py:56-67` emits `DeprecationWarning` | **Uses deprecated path** |
| Cursor fetch methods (`fetchall_rows`, `fetchone_row`, `fetchmany_rows`, `fetch_arrow_table`, `fetch_record_batch`) | multiple | `cursor.py:68,79,92,138,164` | Accurate |
| `pool_size=5`, `max_overflow=3`, `timeout=30`, `recycle=3600` defaults | connection-pools.rst, config.rst | adbc-poolhouse (external dep; not in src) | Unverifiable (external) |

---

## docs/src/how-to/models.rst

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| "Fact fields" (line 148) | Accuracy mismatch: doc says Snowflake introspects with ``SHOW COLUMNS IN SEMANTIC VIEW``, but `engines/snowflake.py:268,328` executes ``SHOW COLUMNS IN VIEW``. codegen.rst:53 already states the correct form, so this page also contradicts a sibling page. | Change ``SHOW COLUMNS IN SEMANTIC VIEW`` to ``SHOW COLUMNS IN VIEW``. |

---

## docs/src/how-to/warehouse-testing.rst

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| "Set up MockEngine" (line 28), "Use a named engine" (line 93), pytest fixture (line 68) | All `MockEngine` registrations call ``register("default", engine)`` / ``register("test", engine)`` with no ``dialect=``. Per `registry.py:56-67` this takes the legacy engine-registry branch and emits a ``DeprecationWarning``. This contradicts the project's documented clean break from the Engine API (MEMORY: "v0.3 docs: clean break from Engine API, no deprecation notices"). Readers following this guide will get deprecation warnings in their test suites. | Author decision required (not an Editor fix). Confirm the intended non-deprecated registration path for `MockEngine`. If `MockEngine` is still the supported test seam, the registry/API needs a non-deprecated registration form and the docs must use it; if `MockEngine` is itself deprecated in favor of a DuckDB-based testing pattern, this page should be removed or rewritten. |

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| Whole page vs. `:ref:` graph | `warehouse-testing.rst` (MockEngine) and `backends/duckdb.rst` + the first-query DuckDB tip both present "test without a warehouse" stories. The overview (`backends/overview.rst:113`) and installation tutorial both steer readers to DuckDB for local testing, while this page steers them to MockEngine. Clarify when to use which so the two paths do not compete. | Add a one-line note distinguishing MockEngine (pure in-memory unit tests, no extension) from DuckDB (integration-style local backend). |

---

## docs/src/reference/cli.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| "Environment variables" Snowflake table (line 103) vs codegen-credentials.rst:33 | `cli.rst` lists `SNOWFLAKE_DATABASE` with no "optional" marker (implying required) and marks `SNOWFLAKE_WAREHOUSE` "(optional)". `codegen-credentials.rst:30-35` marks BOTH `SNOWFLAKE_WAREHOUSE` and `SNOWFLAKE_DATABASE` as Required="Yes". `backends/snowflake.rst:59-66` marks the TOML `database` and `warehouse` fields as Required="No". The status of `database`/`warehouse` is stated three different ways across three pages. | Reconcile against the actual credential loader (`testing/credentials.py` / config validation). Pick one required/optional answer per field and apply consistently across cli.rst, codegen-credentials.rst, and backends/snowflake.rst. |

### NITPICK

| Section | Description | Fix |
|---------|-------------|-----|
| Whole page | Hand-written CLI reference under `reference/`. CLAUDE.md says reference is auto-generated via sphinx-autoapi, but a CLI is not Python-API surface and autoapi cannot generate it — this page is legitimately hand-written. Flagged only so the "don't hand-write reference" rule is not mis-applied. No change needed. | None. |

---

## docs/src/reference/config.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| "Common fields" (line 53) vs backends/*.rst | config.rst documents `pool_size`, `max_overflow`, `timeout`, `recycle` as TOML "Common fields", but the per-backend pages (`backends/snowflake.rst`, `backends/databricks.rst`, `backends/duckdb.rst`) omit these pooling fields from their TOML field tables. A reader on a backend page will not learn these keys exist. | Add a cross-reference from each backend TOML table to config.rst "Common fields", or note that pooling keys are documented centrally. |

### NITPICK

| Section | Description | Fix |
|---------|-------------|-----|
| Whole page | Hand-written config-file reference under `reference/`. Like cli.rst, this documents a TOML file format (not Python API surface), so it is correctly hand-written despite the autoapi rule. No change. | None. |

---

## docs/src/how-to/backends/snowflake.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| TOML field table (line 45) | Manual `SnowflakeConfig(...)` examples here and across `connection-pools.rst`, `web-api.rst` always pass `database` and `warehouse`, but the field table marks both "No" (optional). If they are practically required to run a query, "No" understates that. Cross-check against codegen-credentials.rst which calls them required. | Align with config.rst once the required/optional question (see cli.rst SUGGESTION) is resolved. |

---

## docs/src/how-to/backends/databricks.rst

### NITPICK

| Section | Description | Fix |
|---------|-------------|-----|
| TOML uses `host`; codegen uses `DATABRICKS_SERVER_HOSTNAME` | The pool TOML/`DatabricksConfig` field is `host` (databricks.rst:28,45,91), while the codegen env var is `DATABRICKS_SERVER_HOSTNAME` (codegen-credentials.rst:64). These are two genuinely separate config surfaces (pool vs codegen), so the naming difference is expected — but a reader switching between them may be confused. | Optional: one sentence noting the pool config (`host`) and codegen env vars (`DATABRICKS_SERVER_HOSTNAME`) are distinct surfaces. |

---

## docs/src/how-to/streaming.rst

### NITPICK

| Section | Description | Fix |
|---------|-------------|-----|
| "Rule of thumb" tip (line 119) | Duplicated word: "when the result is larger than memory (memory)," — the parenthetical "(memory)" repeats the preceding word. | Remove the stray "(memory)" so it reads "larger than memory,". |

---

## docs/src/tutorials/first-query.rst

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| "4. Read the results" expected output (lines 213-220) | The shown output is internally inconsistent with the "Complete example" output. Step 4 runs `print(row.country, row.revenue)` plus `print(row["country"])` per row, and the displayed block shows three un-aggregated raw rows (``US 1000`` / ``US`` / ``CA 2000`` / ``CA`` / ``US 500`` / ``US``), while the "Complete example" (lines 271-272) shows two aggregated rows (``US 1500`` / ``CA 2000``) from the same model and query shape. A tutorial's expected output must be runnable-accurate (CLAUDE.md: tutorials = runnable code with expected output shown). The two output blocks disagree on whether results are aggregated. | Author must regenerate the real output. Reconcile the step-4 output with the actual aggregated result, or explain in prose why the per-row dict-access print produces the interleaved form. |

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| Whole page | The DuckDB setup-script `.. tip::` (lines 125-158) shows a `CREATE SEMANTIC VIEW` DDL (lines 146-157) whose shape differs from the warehouse-mapping SQL earlier on the same page (lines 47-59). Two different DuckDB/Snowflake DDL shapes for the same `sales` view may confuse a learner. | Author: confirm the tip's DuckDB DDL actually runs and align it with the earlier mapping example, or note explicitly that the tip shows DuckDB-specific syntax. |

---

## docs/src/index.rst (Overview) and cross-link audit

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| Landing grid (index.rst:34) + reference/index.rst:11 + cli.rst | Doc links target `reference/api/semolina/index`, but context.md states autoapi is configured with `autoapi_root = "reference"` outputting under `reference/semolina/`. If autoapi emits `reference/semolina/`, every `api/semolina/index` link is broken; if it emits `reference/api/semolina/`, context.md is stale. The two are inconsistent. | Author/build: verify the actual autoapi output path and make `autoapi_root`, the toctree entry, and all `:link:` targets agree (either all `reference/semolina/index` or all `reference/api/semolina/index`). Build-breaking link mismatch. |

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| Landing grid + first-query "See also" grid (lines 281-298) use `:link-type: doc` | Project convention (sphinx-shibuya.md "Cross-References") strongly discourages `:doc:`/file-path links in favor of `:ref:` labels that survive moves. Every prose cross-reference already uses `:ref:`; only the grid cards use `:link-type: doc`. Targets all have labels (`tutorial-installation`, `howto-models`, `howto-queries`, `howto-filtering`). | Convert grid-card `:link:`/`:link-type: doc` to `:ref:`-based links. (The `reference/api/semolina/index` card has no label since it is autoapi-generated; resolve via the BLOCKING item above.) |

---

## Pass-by-pass notes (no per-file issues beyond those above)

### Pass 1 — Terminology Consistency
Clean. All API symbols match `terminology.yaml` canonical forms. No `Github`, no `Semantic View`/`Metric View` title-case drift in prose, no `OrderTerms` misuse. `pyarrow` (lowercase) appears only in inline package/code references (installation.rst:82, schema dumps), the documented correct form. `MockEngine`, `SemolinaCursor`, `Row`, `NullsOrdering`, `OrderTerm`, `Predicate`, `Lookup` all consistent. `Lookup` correctly referenced as `semolina.filters.Lookup` (it is not in `semolina/__init__.__all__`).

### Pass 2 — Diataxis Type Integrity
Strong. Tutorials (installation, first-query) are correctly learning-oriented (prerequisites + numbered steps + expected output). How-to guides are goal-oriented with illustrative SQL tab-sets. Explanation (`semantic-views.rst`) stays conceptual and links out for action items (no embedded step-by-step). Reference index/cli/config are information-oriented. No structural type blur. Minor note: `streaming.rst` opens with a long abstract that leans slightly explanatory but stays in service of the how-to goal and links appropriately — not blur.

### Pass 3 — Humanizer
Very clean. No prose em-dash parentheticals beyond standard RST `--` list separators (acceptable). No chatbot artifacts, sycophancy, significance inflation, copula avoidance, or promotional language. Tone matches configured warm-businesslike, second-person voice. Only prose defect: the duplicated "(memory)" in streaming.rst:119 (NITPICK above).

### Pass 4 — Cross-Reference Linking
Inline API mentions are well-linked via `:py:class:`/`:py:func:`/`:py:meth:` roles throughout. Chained builder methods (`.metrics()`, `.where()`, `.execute()`) are plain inline code rather than linked — acceptable, since these are methods on `_Query`/`SemolinaCursor` and the project convention links classes/functions, not every chained method. The one real cross-reference risk is the `reference/api/semolina/index` vs `reference/semolina/index` path mismatch (BLOCKING under index.rst).

### Note on RST title underlines
All section-title underline lengths were checked against their titles in models.rst, queries.rst, and first-query.rst — they match exactly (>= title length), so no underline-length build warnings were found. No action needed.
