SELECT
  MEASURE("revenue") AS "revenue",
  "is_online" AS "is_online"
FROM "sales_view"
WHERE
  "is_online" = TRUE
GROUP BY ALL
