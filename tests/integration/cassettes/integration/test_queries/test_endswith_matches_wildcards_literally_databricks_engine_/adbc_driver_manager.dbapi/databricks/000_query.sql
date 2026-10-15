SELECT
  MEASURE("revenue") AS "revenue",
  "region" AS "region"
FROM "sales_view"
WHERE
  (
    "region" LIKE '%th' ESCAPE '!' OR "region" LIKE '%!%est' ESCAPE '!'
  )
GROUP BY ALL
