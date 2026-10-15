SELECT
  MEASURE("total_qty") AS "total_qty",
  "sold" AS "sold",
  "price" AS "price"
FROM "typed_view"
WHERE
  (
    "sold" = ? AND "price" = ?
  )
GROUP BY ALL
