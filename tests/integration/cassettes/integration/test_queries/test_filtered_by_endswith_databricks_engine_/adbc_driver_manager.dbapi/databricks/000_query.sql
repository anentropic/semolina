SELECT
  MEASURE("revenue") AS "revenue",
  "region" AS "region"
FROM "sales_view"
WHERE
  "region" LIKE ? ESCAPE '!'
GROUP BY ALL
ORDER BY
  "region" ASC
