SELECT
  MEASURE("revenue") AS "revenue",
  MEASURE("cost") AS "cost"
FROM "sales_view"
ORDER BY
  "revenue" ASC
