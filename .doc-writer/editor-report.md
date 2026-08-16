# Editor Report

**Generated:** 2026-08-16
**Doc set:** 30 `.rst` files under `docs/src/` (excluding sphinx-autoapi-generated `docs/src/reference/api/`)
**Files changed:** 12
**Changes made:** 14
  - BLOCKING: 7
  - SUGGESTION: 6
  - NITPICK: 1

**Gate:** `just docs-build` (`sphinx-build -W`, `nitpicky = True`) **passes with zero warnings** after the edits.

## Summary

The prose is in unusually good shape: the terminology and humanizer passes found almost
nothing left to do, and the Phase 49 corrections to the six protected pages all hold up
when re-measured. What this run found instead was seven factual errors in code output and
behaviour tables, every one of them confirmed by running the code rather than by reading
it. The largest is a `how-to/models.rst` section documenting a feature that does not
exist.

---

## Method note

Every accuracy claim recorded below was checked by executing code against the installed
libraries, not inferred from source reading:

- generated SQL, via `query.to_sql(dialect=...)` for all three dialects
- pool defaults, via `adbc_poolhouse` config construction
- drained-stream behaviour, via a real DuckDB engine over the tutorial database
- driver exception classes, via deliberately broken queries
- the tutorial's end-to-end example, run start to finish

The four protected Phase 49 fact groups were re-measured and **all confirmed**. Nothing in
them was revised:

| Protected fact | Re-measured result |
|---|---|
| Databricks extra installs `databricks-sql-connector[pyarrow]`, no extra installs an ADBC driver | Confirmed against `pyproject.toml` |
| `fetch_df()`, `fetch_polars()`, `into()`, `fetch_arrow_table()` raise on a drained/taken stream | Confirmed: `InternalError` / `ProgrammingError` |
| `fetchone()` returns `None` exactly once past the end, then raises; raises on first call if taken | Confirmed exactly |
| `validate=` is per-call, not per-field | Confirmed in `cursor.py` signature |
| "no intermediate Python dictionaries" scoped to the default path only | Confirmed in `pyproject.toml` extra comment |

---

## docs/src/how-to/backends/snowflake.rst

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| Generated SQL | Showed `SELECT AGG("revenue"), "country" FROM "sales"` in lower case. `to_sql(dialect="snowflake")` actually emits `SELECT AGG("REVENUE"), "COUNTRY" FROM "SALES"`. The page's own warning three sections earlier states that Snowflake folds to upper case, so the page contradicted itself on the single most load-bearing fact in the doc set. | Corrected to the measured output and added one sentence naming the folding rule that produces it. |

---

## docs/src/how-to/models.rst

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| "Add field docstrings for codegen" | Documented a feature that does not exist. It claimed docstrings assigned to field instances "appear as comments in `semolina codegen` SQL output". Nothing in `src/semolina/` reads a field's `__doc__` (verified by grep across the package), and codegen emits Python, not SQL. The real behaviour is the reverse direction: all three introspectors read the warehouse column's `comment` into `IntrospectedField.description`, and `templates/python_model.py.jinja2` renders it as a `"""docstring"""` under the generated field. | Section retitled "Carry a field description from your warehouse" and rewritten to describe the actual one-way flow. |

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| Access field descriptors | The expected-output comment `# <class 'semolina.fields.Metric'>` sat *above* the `print(type(field))` that produces it, inverting the convention every other page uses. | Moved the comment below the `print`. |

---

## docs/src/how-to/streaming.rst

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| Backend notes, "Shared state with other fetch methods" | The table grouped `fetch_record_batch()` with cursor iteration and `iter_into()` under "Zero rows, no error". Measured against DuckDB today, on a stream drained any of three ways (`fetch_arrow_table()`, cursor iteration, or a prior `fetch_record_batch()`), the `fetch_record_batch()` *call* returns a reader and the first batch pulled from it raises `OSError`. The page's own mechanism paragraph already implied this, so the table contradicted the prose beside it. | `fetch_record_batch()` given its own row with the measured behaviour, and the mechanism paragraph extended to name the reason: `SemolinaCursor` normalizes the drained reader's `OSError` to `StopIteration` for iteration and `iter_into()`, but `fetch_record_batch()` hands back the raw reader with nothing wrapping it. |

---

## docs/src/how-to/backends/duckdb.rst

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| Configure with .semolina.toml (note) | "DuckDB defaults to `pool_size=1`" is the class-attribute default only. `DuckDBConfig`'s `default_pool_size_for_file` model validator raises it to 5 whenever the database is a file and `pool_size` was not set explicitly. The page's own TOML example uses `database = "/path/to/warehouse.db"`, so the documented default was wrong for the exact configuration shown above it. | Rewritten to state 5 for file-backed and 1 for `":memory:"`, keeping the `ValidationError` note. Now agrees with `how-to/connection-pools.rst`, which already had it right. |

---

## docs/src/reference/config.rst

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| Common fields | Same defect: `pool_size` documented as "default 5 (DuckDB: 1)". | Changed to "default 5 (DuckDB in-memory: 1)" with a sentence covering both DuckDB cases. |

---

## docs/src/tutorials/first-query.rst

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| Read the results / Complete example | Both blocks showed `US 1500` then `CA 2000`. Running the tutorial end to end (setup script, then `demo.py`) produces `CA 2000` then `US 1500`. A tutorial's expected output is its verification step, so a learner comparing output would conclude they had done something wrong. | Both blocks corrected to the measured order, plus one sentence noting that row order is not guaranteed without `.order_by()`, linking to `howto-ordering`. |

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| 2. Register an engine | Type blur (tutorial toward how-to): a three-tab `tab-set` whose Snowflake, Databricks and DuckDB tabs contained byte-identical Python, immediately followed by "The same Python code works for every backend." The tabs presented a choice where none exists, against the project rule that a tutorial offers one clear path. | Replaced with a single code block; the following sentence now says why there are no tabs. |

---

## docs/src/how-to/warehouse-testing.rst

### BLOCKING

| Section | Description | Fix |
|---------|-------------|-----|
| Record your warehouse with pytest-adbc-replay | The `@pytest.mark.adbc_cassette` example took the `sales_engine` fixture, which is the in-memory DuckDB fixture defined at the top of the same page. The DuckDB tab four paragraphs above explicitly says never to mark a DuckDB test with `adbc_cassette` ("looks like evidence and is none"), so the example demonstrated the anti-pattern the page had just warned against. The same snippet also read results via `row.country` / `row.revenue`, which cannot work against a replayed Snowflake cassette. | Fixture renamed to `snowflake_engine` with an explicit "not the in-memory DuckDB fixture" aside; result access changed to `row["COUNTRY"]` / `row['AGG("REVENUE")']`, with a short paragraph explaining that a cassette replays the warehouse's own column spellings and linking to `howto-result-column-names`. |

---

## docs/src/how-to/serialization.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| Select specific fields for the response | Closing paragraph said attribute and dict-style access "both work. Use whichever fits your style", directly contradicting the page's own warning admonition that `row.revenue` raises `AttributeError` on Snowflake and Databricks. `Row.__getattr__` only resolves keys that are valid Python identifiers. | Rewritten to state that dict-style access reaches every column while attribute access reaches only identifier-shaped ones, naming `AGG("REVENUE")` and `measure(revenue)` as the cases it cannot reach. |

---

## docs/src/explanation/type-fidelity.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| Databricks decimals and intervals arrive as strings | "[pandas] arrives transitively under the `all` extra". Since the Phase 49 extras split, `pandas` is a named extra (`pandas>=2.0.0`) that `all` composes directly, so nothing about it is transitive any more. | Changed to "arrives with the `pandas` extra, which the `all` extra includes". The surrounding claim (Semolina does not depend on pandas; having it is a property of your environment) is unchanged and still correct. |

---

## docs/src/how-to/arrow-output.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| Intro | "This gives you zero-copy interop with pandas and polars" is promotional language that the page itself refutes 100 lines later, where it documents a `decimal128` column falling back to a pandas `object` column of `Decimal` values, which is not zero-copy. | Replaced with the factual claim: hands the result to pandas or polars in the format the driver already produced. |

---

## docs/src/how-to/codegen.rst

### SUGGESTION

| Section | Description | Fix |
|---------|-------------|-----|
| Understand the generated output | Rule 4: first prose mention of `Metric`, `Dimension` and `Fact` on this page was plain inline code with no link, while `SemanticView` and `create_engine` on the same page were both linked. | Linked all three to their `semolina.fields` reference entries. Later repeat mentions left as plain inline code, matching the convention elsewhere in the doc set. |

---

## docs/src/how-to/dto-codegen.rst

### NITPICK

| Section | Description | Fix |
|---------|-------------|-----|
| Check a committed DTO in CI | Two literal U+2014 em dashes, the only two in the whole doc set; every other page uses the `--` form that Sphinx smartquotes renders. | Replaced both with `--`. |

---

## Not fixed: structural, for the Author to decide

These are recorded rather than edited, because fixing them means splitting or moving whole
sections rather than restructuring sentences.

| File | Observation |
|------|-------------|
| `tutorials/installation.rst` | The "Optional: dataframes and typed results" section is roughly 55 lines of reference material inside a tutorial: four extras, their version floors (`pyarrow>=17.0.0`, `polars>=1.0.0`, `pandas>=2.0.0`, `arrowmodel>=1.0.0`), and an explanation of why `semolina[pandas]` pulls PyArrow while `semolina[polars]` does not. All of it is accurate and freshly measured. It is reference and explanation content sitting in the tutorial quadrant, and `howto-arrow-output` plus `howto-typed-results` are where a reader would look for it. Consider moving the version floors and the pandas/polars rationale into an extras table in the reference section, leaving the tutorial with the install commands and the verification step. |
| `how-to/queries.rst` and `how-to/ordering.rst` | The "There is no `.offset()`" note, including the keyset-pagination paragraph, is duplicated verbatim in both files (11 lines each). Self-contained pages are the house style, so this may be deliberate, but the two copies will drift. Consider a shared include or making one page the authority. |

---

## Pass results

| Pass | Outcome |
|------|---------|
| 1. Terminology consistency | **No changes needed.** Scanned for every variant listed in `.doc-writer/terminology.yaml`: no `behavior`/`-ise` spellings, no `Polars`/`Pandas` capitals, no `Semantic View` title case, no bare `semolina.toml`, no `register a pool`, no cross-warehouse term misuse (`semantic view` never used for Databricks, `metric view` never for Snowflake). `terminology.yaml` v2 is current and was left unmodified. |
| 2. Diataxis type integrity | One fixable blur (the identical tab-set in `first-query.rst`); two structural observations recorded above. All pages carry a "See also" section and link out across types rather than inlining. |
| 3. Humanizer | Near-empty. Grepped the full pattern inventory (promotional, AI vocabulary, filler, copula avoidance, hedging, chatbot artifacts, knowledge-cutoff disclaimers, trailing participles, sycophancy) and found two hits worth acting on: `zero-copy` and the two em dashes. No curly quotes. |
| 4. Cross-reference linking | API reference is sphinx-autoapi with `nitpicky = True` under `-W`, so every existing `:py:` role is validated by the build. One genuine gap found and fixed in `codegen.rst`. |

## Terminology Changes

None. No non-canonical variant was found in any file.
