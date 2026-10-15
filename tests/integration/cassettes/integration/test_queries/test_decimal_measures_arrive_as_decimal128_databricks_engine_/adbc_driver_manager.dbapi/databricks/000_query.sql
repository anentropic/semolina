SELECT
  MEASURE("total_price") AS "total_price",
  MEASURE("avg_price") AS "avg_price",
  MEASURE("total_qty") AS "total_qty",
  "country" AS "country"
FROM "typed_view"
GROUP BY ALL
ORDER BY
  "country" ASC
