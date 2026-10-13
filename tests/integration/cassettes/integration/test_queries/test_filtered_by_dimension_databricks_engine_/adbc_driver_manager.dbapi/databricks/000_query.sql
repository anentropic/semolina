SELECT
  MEASURE("revenue") AS "revenue",
  MEASURE("cost") AS "cost",
  "country" AS "country"
FROM "sales_view"
WHERE
  "country" = 'US'
GROUP BY ALL
ORDER BY
  "country" ASC
