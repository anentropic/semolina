SELECT
  "country" AS "country",
  "region" AS "region"
FROM "sales_view"
GROUP BY ALL
ORDER BY
  "region" ASC,
  "country" ASC
