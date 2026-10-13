# D4 live probe: metric filters on Snowflake and Databricks

Measured 2026-10-13 16:42 UTC by `probe_metric_filter_live.py` (rerun it to refresh; do not edit by hand).

Every candidate filters on `revenue > 1500` over the integration fixture's data. Post-aggregation (HAVING) semantics return `CA 2800`; row-level semantics return `CA 2000`. The unselected-metric shape selects `cost`, so it expects `CA 280`; the metric-only shape filters `> 1000` and expects the 5800 total.

## snowflake

| Shape | Tests | Outcome | Rows or error |
|---|---|---|---|
| `where_bare` | what Semolina sends today: the bare metric name in WHERE | refused (InternalError) | INTERNAL: [Snowflake] 010236 (42601): SQL compilation error: |
| `where_wrapped` | the wrapped metric in WHERE | refused (InternalError) | INTERNAL: [Snowflake] 002035 (42601): SQL compilation error: |
| `having_wrapped` | the wrapped metric in HAVING, metric selected | accepted, post-aggregation | [(2800, 'CA')] |
| `having_alias` | the select alias in HAVING, metric selected | accepted, post-aggregation | [(2800, 'CA')] |
| `having_wrapped_unselected` | the wrapped metric in HAVING, metric not selected | accepted, post-aggregation | [(280, 'CA')] |
| `having_wrapped_no_dimensions` | HAVING on a metric-only query, which has no GROUP BY | accepted, post-aggregation | [(5800,)] |
| `outer_where_alias` | the aggregate query as a subquery, filtered outside on the alias | accepted, post-aggregation | [(2800, 'CA')] |

SQL sent:

```sql
-- where_bare
SELECT AGG("REVENUE") AS "revenue", "COUNTRY" AS "country" FROM "SALES_VIEW" WHERE "REVENUE" > 1500 GROUP BY ALL ORDER BY "country"
-- where_wrapped
SELECT AGG("REVENUE") AS "revenue", "COUNTRY" AS "country" FROM "SALES_VIEW" WHERE AGG("REVENUE") > 1500 GROUP BY ALL ORDER BY "country"
-- having_wrapped
SELECT AGG("REVENUE") AS "revenue", "COUNTRY" AS "country" FROM "SALES_VIEW" GROUP BY ALL HAVING AGG("REVENUE") > 1500 ORDER BY "country"
-- having_alias
SELECT AGG("REVENUE") AS "revenue", "COUNTRY" AS "country" FROM "SALES_VIEW" GROUP BY ALL HAVING "revenue" > 1500 ORDER BY "country"
-- having_wrapped_unselected
SELECT AGG("COST") AS "cost", "COUNTRY" AS "country" FROM "SALES_VIEW" GROUP BY ALL HAVING AGG("REVENUE") > 1500 ORDER BY "country"
-- having_wrapped_no_dimensions
SELECT AGG("REVENUE") AS "revenue" FROM "SALES_VIEW" HAVING AGG("REVENUE") > 1000
-- outer_where_alias
SELECT * FROM (SELECT AGG("REVENUE") AS "revenue", "COUNTRY" AS "country" FROM "SALES_VIEW" GROUP BY ALL) WHERE "revenue" > 1500 ORDER BY "country"
```

## databricks

| Shape | Tests | Outcome | Rows or error |
|---|---|---|---|
| `where_bare` | what Semolina sends today: the bare metric name in WHERE | refused (InternalError) | INTERNAL: [Databricks] failed to execute query: databricks: execution error: failed to execute query: unexpected operation state ERROR_STATE: [METRIC_VIEW_MISSING_MEASURE_FUNCTION] The usage of measure column [revenue] of a metric view requires a MEASURE() (or AGG()) function to produce results. SQL |
| `where_wrapped` | the wrapped metric in WHERE | refused (InternalError) | INTERNAL: [Databricks] failed to execute query: databricks: execution error: failed to execute query: unexpected operation state ERROR_STATE: [MISSING_ATTRIBUTES.RESOLVED_ATTRIBUTE_APPEAR_IN_OPERATION] Resolved attribute(s) "revenue" missing from "revenue", "cost", "__mv_src_v37_jaffle_test__d4__e6e |
| `having_wrapped` | the wrapped metric in HAVING, metric selected | accepted, post-aggregation | [(2800, 'CA')] |
| `having_alias` | the select alias in HAVING, metric selected | accepted, post-aggregation | [(2800, 'CA')] |
| `having_wrapped_unselected` | the wrapped metric in HAVING, metric not selected | accepted, post-aggregation | [(280, 'CA')] |
| `having_wrapped_no_dimensions` | HAVING on a metric-only query, which has no GROUP BY | accepted, post-aggregation | [(5800,)] |
| `outer_where_alias` | the aggregate query as a subquery, filtered outside on the alias | accepted, post-aggregation | [(2800, 'CA')] |

SQL sent:

```sql
-- where_bare
SELECT MEASURE(`revenue`) AS `revenue`, `country` AS `country` FROM `sales_view` WHERE `revenue` > 1500 GROUP BY ALL ORDER BY `country`
-- where_wrapped
SELECT MEASURE(`revenue`) AS `revenue`, `country` AS `country` FROM `sales_view` WHERE MEASURE(`revenue`) > 1500 GROUP BY ALL ORDER BY `country`
-- having_wrapped
SELECT MEASURE(`revenue`) AS `revenue`, `country` AS `country` FROM `sales_view` GROUP BY ALL HAVING MEASURE(`revenue`) > 1500 ORDER BY `country`
-- having_alias
SELECT MEASURE(`revenue`) AS `revenue`, `country` AS `country` FROM `sales_view` GROUP BY ALL HAVING `revenue` > 1500 ORDER BY `country`
-- having_wrapped_unselected
SELECT MEASURE(`cost`) AS `cost`, `country` AS `country` FROM `sales_view` GROUP BY ALL HAVING MEASURE(`revenue`) > 1500 ORDER BY `country`
-- having_wrapped_no_dimensions
SELECT MEASURE(`revenue`) AS `revenue` FROM `sales_view` HAVING MEASURE(`revenue`) > 1000
-- outer_where_alias
SELECT * FROM (SELECT MEASURE(`revenue`) AS `revenue`, `country` AS `country` FROM `sales_view` GROUP BY ALL) WHERE `revenue` > 1500 ORDER BY `country`
```
