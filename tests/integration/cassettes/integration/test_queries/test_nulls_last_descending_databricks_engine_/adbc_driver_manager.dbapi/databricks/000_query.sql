SELECT
  MEASURE("revenue") AS "revenue",
  "is_online" AS "is_online"
FROM "sales_view"
GROUP BY ALL
ORDER BY
  "is_online" DESC
