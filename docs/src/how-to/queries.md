# How to build queries

Build queries using Cubano's fluent, immutable API. Chain `.metrics()`, `.dimensions()`,
`.where()`, `.order_by()`, and `.limit()` to shape your query, then call `.execute()` to
get results.

This guide uses the `Sales` model from [First Query](../tutorials/first-query.md):

```python
from cubano import SemanticView, Metric, Dimension


class Sales(SemanticView, view="sales"):
    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()
```

## Select metrics

Use `.metrics()` to choose which aggregated measures to include:

```python
query = Sales.query().metrics(Sales.revenue)
query = Sales.query().metrics(Sales.revenue, Sales.cost)
```

=== "Snowflake"

    ```sql
    SELECT AGG("revenue"), AGG("cost")
    FROM "sales"
    ```

=== "Databricks"

    ```sql
    SELECT MEASURE(`revenue`), MEASURE(`cost`)
    FROM `sales`
    ```

Passing a non-`Metric` field raises `TypeError`:

```python
Sales.query().metrics(
    Sales.country
)  # TypeError: metrics() requires Metric fields
```

At least one field is required -- calling `.metrics()` with no arguments raises `ValueError`.

## Select dimensions

Use `.dimensions()` to group results by `Dimension` or `Fact` fields:

```python
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
)
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country, Sales.region)
)
```

=== "Snowflake"

    ```sql
    SELECT AGG("revenue"), "country"
    FROM "sales"
    GROUP BY ALL
    ```

=== "Databricks"

    ```sql
    SELECT MEASURE(`revenue`), `country`
    FROM `sales`
    GROUP BY ALL
    ```

Passing a `Metric` field raises `TypeError`. At least one field is required.

## Filter with `.where()`

Add filter conditions using field operators. Multiple `.where()` calls are **ANDed** together.
Pass `None` as a no-op (useful for conditional filters):

```python
# Single filter
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.country == "US")
)

# Multiple filters — equivalent to: WHERE country = 'US' AND revenue > 1000
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.country == "US")
    .where(Sales.revenue > 1000)
)

# Varargs — all conditions ANDed together
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.country == "US", Sales.revenue > 1000)
)
```

=== "Snowflake"

    ```sql
    SELECT AGG("revenue")
    FROM "sales"
    WHERE "country" = 'US'
    ```

=== "Databricks"

    ```sql
    SELECT MEASURE(`revenue`)
    FROM `sales`
    WHERE `country` = 'US'
    ```

See [Filtering](filtering.md) for the full operator reference, named methods, and boolean
composition.

## Order results

Order results by one or more fields. Pass a bare field for default ascending order,
or use `.asc()` / `.desc()` for explicit direction:

```python
# Ascending (default)
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .order_by(Sales.revenue)
)

# Descending
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .order_by(Sales.revenue.desc())
)

# Multiple fields
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .order_by(Sales.revenue.desc(), Sales.country.asc())
)
```

=== "Snowflake"

    ```sql
    SELECT AGG("revenue")
    FROM "sales"
    ORDER BY "revenue" ASC
    ```

=== "Databricks"

    ```sql
    SELECT MEASURE(`revenue`)
    FROM `sales`
    ORDER BY `revenue` ASC
    ```

See [Ordering and limiting](ordering.md) for NULL handling and combined examples.

## Limit result count

Limit the result set to `n` rows. Must be a positive integer:

```python
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .limit(10)
)
```

=== "Snowflake"

    ```sql
    SELECT AGG("revenue"), "country"
    FROM "sales"
    GROUP BY ALL
    LIMIT 10
    ```

=== "Databricks"

    ```sql
    SELECT MEASURE(`revenue`), `country`
    FROM `sales`
    GROUP BY ALL
    LIMIT 10
    ```

Passing zero or a negative value raises `ValueError`. Passing a non-integer raises `TypeError`.

## Override the engine

Use `.using()` to select a different registered engine. Engine resolution is lazy -- it
happens at `.execute()` time, not during query construction:

```python
# Uses the engine registered as "warehouse" instead of "default"
query = (
    Sales.query().metrics(Sales.revenue).using("warehouse")
)
```

If no `.using()` call is made, Cubano uses the engine registered as `"default"`.

## Execute and read results

Call `.execute()` to run the query and get back a list of `Row` objects:

```python
results = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .execute()
)

for row in results:
    print(row.country, row.revenue)  # attribute access
    print(row["country"])  # dict-style access
```

`.execute()` validates the query (at least one metric or dimension required), resolves the
engine, calls `engine.execute()`, and wraps each result dict in a `Row`.

## Inspect generated SQL

Use `.to_sql()` to see the SQL that would be sent to the warehouse without executing it:

```python
sql = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .to_sql()
)
print(sql)
```

=== "Snowflake"

    ```sql
    SELECT AGG("revenue"), "country"
    FROM "sales"
    GROUP BY ALL
    ```

=== "Databricks"

    ```sql
    SELECT MEASURE(`revenue`), `country`
    FROM `sales`
    GROUP BY ALL
    ```

!!! tip "Inspect SQL before executing"
    Use `.to_sql()` during development to verify SQL generation before hitting the warehouse:

    ```python
    query = (
        Sales.query()
        .metrics(Sales.revenue, Sales.cost)
        .dimensions(Sales.country)
        .where(Sales.country == "US")
        .order_by(Sales.revenue.desc())
        .limit(100)
    )

    print(query.to_sql())
    ```

    For backend-specific SQL, call `engine.to_sql(query)` on a bound engine instance.

## Fork queries with immutable chaining

Every method returns a **new** `Query` instance. The original is unchanged.
You can fork a base query without affecting other uses of it:

```python
# Build a base query once
base = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
)

# Fork into specialised variants — base is unchanged
us_only = base.where(Sales.country == "US")
top_10 = base.limit(10)
us_top_10 = base.where(Sales.country == "US").limit(10)

# All three are independent queries; base still has no filter or limit
print(base._filters)  # None
print(base._limit_value)  # None
```

## Build queries incrementally

Because queries are immutable, you can build them up across function boundaries
and store intermediate queries safely:

```python
def add_revenue_filter(query, threshold: int):
    return query.where(Sales.revenue > threshold)


base = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
)
filtered = add_revenue_filter(base, 1000)
results = filtered.execute()
```

## See also

- [Filtering](filtering.md) -- field operators and boolean composition
- [Ordering and limiting](ordering.md) -- sort results and control row counts
- [Defining models](models.md) -- define SemanticView subclasses with field types
- [Backends overview](backends/overview.md) -- SQL differences between Snowflake and Databricks
