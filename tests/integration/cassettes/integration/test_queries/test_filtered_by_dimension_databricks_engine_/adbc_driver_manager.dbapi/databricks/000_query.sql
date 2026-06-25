SELECT
  MEASURE("revenue"),
  MEASURE("cost"),
  "country"
FROM "sales_view"
WHERE
  "country" = 'US'
GROUP BY ALL
ORDER BY
  "country" ASC
