SELECT
  MEASURE("total_qty") AS "total_qty",
  "what?" AS "what"
FROM "typed_view"
WHERE
  "what?" = ?
GROUP BY ALL
