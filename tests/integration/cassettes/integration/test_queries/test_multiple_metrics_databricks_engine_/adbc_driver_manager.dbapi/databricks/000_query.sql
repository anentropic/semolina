SELECT
  MEASURE("revenue"),
  MEASURE("cost")
FROM "sales_view"
ORDER BY
  MEASURE("revenue") ASC
