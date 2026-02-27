# How to order and limit results

Control the order and size of your result set using `.order_by()` and `.limit()`.

This guide uses the `Sales` model from [First Query](../tutorials/first-query.md):

```python
from semolina import SemanticView, Metric, Dimension


class Sales(SemanticView, view="sales"):
    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()
```

## Sort ascending

Pass a bare field to `.order_by()` for ascending sort:

```python
# ORDER BY revenue ASC
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .order_by(Sales.revenue)
)
```

Use `.asc()` on a field to be explicit about the direction:

```python
# ORDER BY revenue ASC  (same result as bare field)
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .order_by(Sales.revenue.asc())
)
```

## Sort descending

Use `.desc()` for descending sort:

```python
# ORDER BY revenue DESC
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .order_by(Sales.revenue.desc())
)
```

## Control NULL positioning

By default, NULL positioning follows the warehouse backend's behavior. Use `NullsOrdering` to
override it:

```python
from semolina import NullsOrdering

# NULLs appear first (before non-NULL values)
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .order_by(Sales.revenue.desc(NullsOrdering.FIRST))
)

# NULLs appear last (after non-NULL values)
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .order_by(Sales.revenue.asc(NullsOrdering.LAST))
)
```

| Value | SQL generated | Meaning |
|-------|--------------|---------|
| `NullsOrdering.FIRST` | `NULLS FIRST` | NULLs sort before non-NULL values |
| `NullsOrdering.LAST` | `NULLS LAST` | NULLs sort after non-NULL values |
| `NullsOrdering.DEFAULT` | *(no NULLS clause)* | Backend decides (default) |

Import `NullsOrdering` directly from semolina:

```python
from semolina import NullsOrdering
```

## Sort by multiple fields

Pass multiple fields to `.order_by()` to sort by several columns. Fields are applied
left to right:

```python
# ORDER BY revenue DESC, country ASC
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .order_by(Sales.revenue.desc(), Sales.country.asc())
)
```

=== "Snowflake"

    ```sql
    SELECT AGG("revenue"), "country"
    FROM "sales"
    GROUP BY ALL
    ORDER BY "revenue" DESC, "country" ASC
    ```

=== "Databricks"

    ```sql
    SELECT MEASURE(`revenue`), `country`
    FROM `sales`
    GROUP BY ALL
    ORDER BY `revenue` DESC, `country` ASC
    ```

## Limit the result count

Use `.limit(n)` to cap the number of rows returned:

```python
# LIMIT 10
query = Sales.query().metrics(Sales.revenue).limit(10)
```

`n` must be a positive integer. Passing zero or negative raises `ValueError`.
Passing a non-integer raises `TypeError`.

## Build "top N" queries

Combine `.order_by()` and `.limit()` for "top N" queries:

```python
# Top 10 countries by revenue
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .order_by(Sales.revenue.desc())
    .limit(10)
)

results = query.execute()
for row in results:
    print(f"{row.country}: {row.revenue}")
```

## Store and reuse OrderTerms

`.asc()` and `.desc()` return `OrderTerm` instances. You can store and reuse them:

```python
from semolina import NullsOrdering

# Create reusable sort terms
revenue_desc = Sales.revenue.desc(NullsOrdering.LAST)
country_asc = Sales.country.asc()

query = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .order_by(revenue_desc, country_asc)
)
```

## See also

- [Building queries](queries.md) -- the full query API
- [Filtering](filtering.md) -- filter queries before ordering
