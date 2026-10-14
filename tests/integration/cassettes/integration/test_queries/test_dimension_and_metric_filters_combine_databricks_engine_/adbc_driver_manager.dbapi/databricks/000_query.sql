SELECT
  MEASURE("revenue") AS "revenue",
  "country" AS "country"
FROM "sales_view"
WHERE
  "country" <> 'MX'
GROUP BY ALL
HAVING
  MEASURE("revenue") > 1400
ORDER BY
  "country" ASC
