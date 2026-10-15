SELECT
  MEASURE("revenue") AS "revenue",
  "region" AS "region"
FROM "sales_view"
WHERE
  (
    "region" LIKE 'E%' ESCAPE '!' OR "region" LIKE '!_est%' ESCAPE '!'
  )
GROUP BY ALL
