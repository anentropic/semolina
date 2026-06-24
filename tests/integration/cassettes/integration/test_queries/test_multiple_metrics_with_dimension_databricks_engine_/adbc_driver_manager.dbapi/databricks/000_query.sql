SELECT
  MEASURE("revenue"),
  MEASURE("cost"),
  "country"
FROM "sales_view"
GROUP BY ALL
ORDER BY
  "country" ASC
