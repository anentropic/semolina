SELECT
  MEASURE("revenue") AS "revenue",
  "region" AS "region"
FROM "sales_view"
WHERE
  "region" LIKE 'We%' ESCAPE '!'
GROUP BY ALL
