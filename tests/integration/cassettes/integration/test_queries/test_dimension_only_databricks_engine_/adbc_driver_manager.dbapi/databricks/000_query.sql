SELECT
  "country",
  "region"
FROM "sales_view"
GROUP BY ALL
ORDER BY
  "region" ASC,
  "country" ASC
