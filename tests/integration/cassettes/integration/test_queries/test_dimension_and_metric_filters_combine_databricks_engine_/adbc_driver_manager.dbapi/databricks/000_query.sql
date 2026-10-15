SELECT
  MEASURE("revenue") AS "revenue",
  "country" AS "country"
FROM "sales_view"
WHERE
  "country" <> ?
GROUP BY ALL
HAVING
  MEASURE("revenue") > ?
ORDER BY
  "country" ASC
