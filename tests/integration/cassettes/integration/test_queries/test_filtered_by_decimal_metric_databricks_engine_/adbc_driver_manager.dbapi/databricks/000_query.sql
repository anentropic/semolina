SELECT
  MEASURE("total_price") AS "total_price",
  "country" AS "country"
FROM "typed_view"
GROUP BY ALL
HAVING
  MEASURE("total_price") > ?
