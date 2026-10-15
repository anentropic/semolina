SELECT
  MEASURE("revenue") AS "revenue",
  "country" AS "country"
FROM "sales_view"
GROUP BY ALL
HAVING
  MEASURE("revenue") < 0
