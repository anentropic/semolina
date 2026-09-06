SELECT
  MEASURE("revenue"),
  "country"
FROM "sales_view"
GROUP BY ALL
ORDER BY
  "country" ASC
