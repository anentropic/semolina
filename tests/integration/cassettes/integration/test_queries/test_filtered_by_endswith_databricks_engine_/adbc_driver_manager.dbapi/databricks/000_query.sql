SELECT
  MEASURE("revenue") AS "revenue",
  "region" AS "region"
FROM "sales_view"
WHERE
  "region" LIKE '%st' ESCAPE '!'
GROUP BY ALL
ORDER BY
  "region" ASC
