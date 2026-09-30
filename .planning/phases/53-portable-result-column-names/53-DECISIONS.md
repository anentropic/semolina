# Phase 53 decisions: portable result column names (D2)

**Status:** proposed at the 53-01 checkpoint, 2026-09-30. **Blocking human review:** 53-02
and 53-03 wait on it.
**Gates:** ALIAS-01..05. Interacts with D4 (FILT-04, Phase 54).

## The problem, from the recordings

Result keys are whatever the warehouse calls the column. The committed cassettes show it
directly, for the same model on each backend:

| Backend | SQL sent | Result columns |
|---------|----------|----------------|
| Snowflake | `SELECT AGG("REVENUE"), "COUNTRY" FROM "SALES_VIEW" GROUP BY ALL` | `AGG("REVENUE")`, `COUNTRY` |
| Databricks | `SELECT MEASURE(`revenue`), `country` FROM sales_view GROUP BY ALL` | `measure(revenue)`, `country` |
| DuckDB | `SELECT * FROM semantic_view('sales_view', dimensions := ['country'], metrics := ['revenue'])` | `country`, `revenue` |

So `row.revenue` works only on DuckDB, and on Snowflake even `row.country` fails, because
dimensions come back upper-cased. A DTO needs a per-backend `validation_alias`.

DuckDB has a second defect, ALIAS-05. `WHERE` and `ORDER BY` sit outside
`semantic_view()`, so every field they mention must be in its output, and the builder adds
filtered and ordered fields to `dimensions := [...]`. A filter on an unselected dimension
therefore regroups the result by it. Measured on the fixture data, revenue by region
filtered to US and CA:

| Query shape | Result |
|-------------|--------|
| today: `dimensions := ['region', 'country']` then an outer `WHERE country IN (...)` | `(East, US, 500)`, `(West, CA, 2000)`, `(West, US, 1000)` |
| `dimensions := ['region'], where_clause := $$country IN ('US','CA')$$` | `(East, 500)`, `(West, 3000)` |

## Decisions proposed

### D2-1. Alias every selected field to its exact Python field name

Snowflake and Databricks put `AS <quoted python name>` on every select item. DuckDB gets an
explicit outer projection in place of `SELECT *`:

| Dialect | Metric | Dimension |
|---------|--------|-----------|
| Snowflake | `AGG("REVENUE") AS "revenue"` | `"COUNTRY" AS "country"` |
| Databricks | ``MEASURE(`revenue`) AS `revenue` `` | ``country AS `country` `` |
| DuckDB | `SELECT "revenue" AS "revenue", … FROM semantic_view(...)` | same |

The alias is the Python attribute name exactly, quoted so the warehouse keeps its case. It
is not the dialect-folded name: the point is that one model yields one set of keys
everywhere. A field with `source=` still selects its source column and returns under its
Python name. Duplicate names cannot arise, because 52-03 refuses a field selected twice.

**Evidence:**
- **Databricks:** its own query docs alias measures (``MEASURE(`Total Revenue`) AS
  total_revenue``).
- **DuckDB:** measured. An outer `SELECT "revenue" AS "total"` over `semantic_view()`
  returns `total`.
- **Snowflake: not proven.** Its docs show aliases only inside the `SEMANTIC_VIEW()` clause
  (`DIMENSIONS customer.customer_market_segment AS segment`), not on `AGG()` in a plain
  `SELECT`, and no cassette uses `AS`. 53-04 records it live. If Snowflake rejects the
  alias, the fallback is the `SEMANTIC_VIEW()` clause form, which documents aliases.

### D2-2. `WHERE` and `ORDER BY` keep referring to the warehouse's expression

Snowflake and Databricks keep `ORDER BY AGG("REVENUE")` and `WHERE "COUNTRY" = ?`, never
the alias. The cassettes prove that spelling works. Whether a warehouse lets `ORDER BY`
see a select-list alias varies, and nothing here needs it.

### D2-3. DuckDB filters go where they can be applied

- **Dimension and fact predicates** go inside the call as `where_clause := ?`. The whole
  clause is bound as one parameter, and values are rendered into it through the dialect's
  existing `render_literal`. Measured: a `?` *inside* the clause fails type inference, but
  binding the clause string works. `O'Neill` matches its row, and `x' OR 1=1 --` stays a
  literal and matches nothing. This fixes the grain bug.
- **Metric predicates** stay in the outer `WHERE`, with the metric added to `metrics :=`
  if it is not selected, and left out of the outer projection. A metric does not group, so
  adding one changes no grain. The extension refuses a metric in `where_clause` ("the
  filter is applied before metrics are computed"), so the outer `WHERE` is the only place,
  and it is HAVING in effect.
- **Mixing both kinds under `OR` or `NOT`** cannot be split into a pre-aggregation and a
  post-aggregation part, so it raises `ValueError` at build time, naming the fields. A
  top-level `AND` splits cleanly.

### D2-4. Ordering by an unselected field

- **An unselected metric:** allowed. DuckDB adds it to `metrics :=` without projecting it.
  Snowflake and Databricks order by its expression as they do today.
- **An unselected dimension:** refused with `ValueError` at build time on every dialect,
  naming the field and saying to select it. On DuckDB it would regroup the result, the
  ALIAS-05 bug, and the outer `ORDER BY` cannot see a column the call did not return
  (measured: `Referenced column "country" not found`). On Snowflake and Databricks,
  ordering an aggregate query by a column it does not group by should be refused by the
  warehouse anyway; 53-04 confirms that live.

### D2-5. What the aliasing retires, and what keeps working unchanged

- **`Dialect.metric_result_column_name`** leaves the query path. It survives only to read
  pre-53 recordings, and is deleted in 53-05 once the cassettes are re-recorded.
- **`codegen-dto` and `--check` need no binding change.** Their candidate list
  (`annotation_check._result_field_names`) already tries `field.name` first, so they bind
  to the alias. For ALIAS-03, 53-05 makes the renderer omit `validation_alias` when it
  equals the field name, which then is always.
- **`.into()`** matches columns by name, so plain DTOs work on every backend (ALIAS-02).

### D2-6. No compatibility shim (settled going in)

`.into()` and `codegen-dto` are unreleased. The `Row`-key change on Snowflake and
Databricks is `0.6.0`-visible (`COUNTRY` becomes `country`, `AGG("REVENUE")` becomes
`revenue`) and is a changelog entry. `row.revenue` raises there today, so no working code
depends on the old keys.

### D2-7. Consequences for the plans

- **53-02:** every exact-SQL expectation from 52.1-05 changes. Rewrite them test-first to
  the D2-1 shapes, one dialect at a time.
- **53-03:** implements D2-3 and D2-4, flips the `test_filtering_on_an_unselected_dimension_keeps_the_selected_grain`
  xfail, and rewrites the two `test_sql.py` tests that pin the widening mechanism.
- **53-04:** must record, besides the planned cassettes:
  - an aliased `AGG()`, the D2-1 Snowflake proof;
  - an `ORDER BY` on an unselected dimension on both warehouses, for D2-4;
  - a metric in `WHERE`/`HAVING`, which feeds D4.

## Questions for the checkpoint

1. **Alias spelling.** Exact Python name (recommended), or the dialect-folded name? Folded
   would keep Snowflake keys upper-case and so fail the goal.
2. **Unselected dimension in `order_by`.** Refuse on every dialect (recommended), or only on
   DuckDB and leave the warehouses to answer?
3. **Mixed dimension/metric predicates under `OR`/`NOT`.** Refuse on DuckDB now
   (recommended), knowing D4 decides the Snowflake/Databricks side in Phase 54? D2-3 already
   points D4 towards HAVING: Snowflake's docs say "in the HAVING clause, you can only
   specify metrics".
4. **The unproven Snowflake alias.** Proceed with 53-02/53-03 on D2-1 and prove it in 53-04,
   with the `SEMANTIC_VIEW()` form as the fallback (recommended)? Or record the Snowflake
   case before any builder change? That needs credentials, so it has to be run locally.
