SELECT
  MEASURE("revenue") AS "revenue",
  "is_online" AS "is_online"
FROM "sales_view"
WHERE
  "is_online" IS NULL
GROUP BY ALL
