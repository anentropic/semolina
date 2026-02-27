# How to filter queries

Filter query results using Python operators and named Field methods. Compose
conditions with `&` (AND), `|` (OR), and `~` (NOT) for arbitrary boolean logic.

This guide uses the `Sales` model from [First Query](../tutorials/first-query.md):

```python
from semolina import SemanticView, Metric, Dimension


class Sales(SemanticView, view="sales"):
    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()
```

## Use comparison operators

Standard Python comparison operators work directly on fields:

| Operator | Meaning | Example |
|----------|---------|---------|
| `==` | Equals | `Sales.country == "US"` |
| `!=` | Not equals | `Sales.country != "US"` |
| `>` | Greater than | `Sales.revenue > 1000` |
| `>=` | Greater than or equal | `Sales.revenue >= 500` |
| `<` | Less than | `Sales.revenue < 100` |
| `<=` | Less than or equal | `Sales.revenue <= 999` |

```python
# Revenue greater than 1000
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.revenue > 1000)
)

# Country equals US
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.country == "US")
)

# Revenue between bounds (explicit)
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .where((Sales.revenue >= 500) & (Sales.revenue <= 2000))
)
```

=== "Snowflake"

    ```sql
    SELECT AGG("revenue")
    FROM "sales"
    WHERE "revenue" > 1000
    ```

=== "Databricks"

    ```sql
    SELECT MEASURE(`revenue`)
    FROM `sales`
    WHERE `revenue` > 1000
    ```

## Use named filter methods

Fields provide named methods for common SQL operations beyond simple comparisons.

### `.between(lo, hi)`

Range check (inclusive):

```python
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.revenue.between(500, 2000))
)
```

=== "Snowflake"

    ```sql
    WHERE "revenue" BETWEEN 500 AND 2000
    ```

=== "Databricks"

    ```sql
    WHERE `revenue` BETWEEN 500 AND 2000
    ```

### `.in_(values)`

Membership in a collection:

```python
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.country.in_(["US", "CA", "MX"]))
)
```

=== "Snowflake"

    ```sql
    WHERE "country" IN ('US', 'CA', 'MX')
    ```

=== "Databricks"

    ```sql
    WHERE `country` IN ('US', 'CA', 'MX')
    ```

### `.isnull()`

Null check:

```python
# Find rows where region IS NULL
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.region.isnull())
)
```

=== "Snowflake"

    ```sql
    WHERE "region" IS NULL
    ```

=== "Databricks"

    ```sql
    WHERE `region` IS NULL
    ```

### `.like(pattern)` and `.ilike(pattern)`

SQL LIKE pattern matching with `%` and `_` wildcards. `.ilike()` is
case-insensitive:

```python
# Case-sensitive
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.country.like("U%"))
)

# Case-insensitive
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.country.ilike("u%"))
)
```

=== "Snowflake"

    ```sql
    WHERE "country" LIKE 'U%'
    ```

=== "Databricks"

    ```sql
    WHERE `country` LIKE 'U%'
    ```

### `.startswith(prefix)` and `.istartswith(prefix)`

Prefix match. `.istartswith()` is case-insensitive:

```python
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.country.startswith("U"))
)
```

=== "Snowflake"

    ```sql
    WHERE "country" LIKE 'U%'
    ```

=== "Databricks"

    ```sql
    WHERE `country` LIKE 'U%'
    ```

### `.endswith(suffix)` and `.iendswith(suffix)`

Suffix match. `.iendswith()` is case-insensitive:

```python
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.region.endswith("est"))
)
```

=== "Snowflake"

    ```sql
    WHERE "region" LIKE '%est'
    ```

=== "Databricks"

    ```sql
    WHERE `region` LIKE '%est'
    ```

### `.iexact(value)`

Case-insensitive equality (no wildcards):

```python
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.country.iexact("united states"))
)
```

=== "Snowflake"

    ```sql
    WHERE "country" ILIKE 'united states'
    ```

=== "Databricks"

    ```sql
    WHERE `country` ILIKE 'united states'
    ```

## Combine conditions with OR

Use `|` to combine two conditions with OR logic:

```python
# country = 'US' OR country = 'CA'
condition = (Sales.country == "US") | (
    Sales.country == "CA"
)

results = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(condition)
    .execute()
)
```

=== "Snowflake"

    ```sql
    SELECT AGG("revenue")
    FROM "sales"
    WHERE ("country" = 'US' OR "country" = 'CA')
    ```

=== "Databricks"

    ```sql
    SELECT MEASURE(`revenue`)
    FROM `sales`
    WHERE (`country` = 'US' OR `country` = 'CA')
    ```

## Combine conditions with AND

Use `&` to combine two conditions with AND logic:

```python
# country = 'US' AND revenue > 500
condition = (Sales.country == "US") & (Sales.revenue > 500)

results = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(condition)
    .execute()
)
```

=== "Snowflake"

    ```sql
    WHERE ("country" = 'US' AND "revenue" > 500)
    ```

=== "Databricks"

    ```sql
    WHERE (`country` = 'US' AND `revenue` > 500)
    ```

Multiple `.where()` calls are also ANDed together:

```python
# Equivalent to the & example above
results = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.country == "US")
    .where(Sales.revenue > 500)
    .execute()
)
```

You can also pass multiple conditions as arguments to a single `.where()` call:

```python
# Also equivalent -- varargs are ANDed together
results = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.country == "US", Sales.revenue > 500)
    .execute()
)
```

## Negate conditions with NOT

Use `~` to negate a condition:

```python
# NOT (country = 'US')
condition = ~(Sales.country == "US")

results = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(condition)
    .execute()
)
```

=== "Snowflake"

    ```sql
    WHERE NOT ("country" = 'US')
    ```

=== "Databricks"

    ```sql
    WHERE NOT (`country` = 'US')
    ```

Negation composes with AND and OR:

```python
# NOT (revenue < 100)
condition = ~(Sales.revenue < 100)
```

## Build complex nested conditions

Combine `|`, `&`, and `~` to express arbitrary conditions. Use parentheses to
control grouping:

```python
# (country = 'US' OR country = 'CA') AND NOT (revenue < 100)
condition = (
    (Sales.country == "US") | (Sales.country == "CA")
) & ~(Sales.revenue < 100)

results = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(condition)
    .execute()
)
```

=== "Snowflake"

    ```sql
    WHERE (("country" = 'US' OR "country" = 'CA')
        AND NOT ("revenue" < 100))
    ```

=== "Databricks"

    ```sql
    WHERE ((`country` = 'US' OR `country` = 'CA')
        AND NOT (`revenue` < 100))
    ```

## Build filters conditionally

Each `.where()` call ANDs with the accumulated filter. This is useful for
conditionally building filters in application code:

```python
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
)

if region_filter:
    query = query.where(Sales.region == region_filter)

if min_revenue:
    query = query.where(Sales.revenue >= min_revenue)

results = query.execute()
```

`.where()` also accepts `None` as a no-op, making conditional filters a one-liner:

```python
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .where(
        Sales.region == region_filter
        if region_filter
        else None
    )
    .where(
        Sales.revenue >= min_revenue
        if min_revenue
        else None
    )
)

results = query.execute()
```

## Use the escape hatch for custom lookups

For filter operations not covered by the built-in operators or named methods,
define a custom `Lookup` subclass and use `.lookup()`:

```python
from semolina.filters import Lookup


class RegexpMatch(Lookup[str]):
    """Regexp match: ``field REGEXP pattern``."""


# Use with the escape hatch
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .where(Sales.country.lookup(RegexpMatch, "^U.*S$"))
)
```

To compile custom lookups into SQL, add a `case RegexpMatch(...)` branch
to `SQLBuilder._compile_predicate()`.

!!! warning "Operator precedence: `&` binds tighter than `|`"
    Python evaluates `&` before `|` -- the same precedence as bitwise operators.
    This can produce unexpected results when mixing them:

    ```python
    # DANGEROUS: reads as a | (b & c)
    condition = (Sales.country == "US") | (
        Sales.revenue > 500
    ) & (Sales.cost < 100)

    # SAFE: parentheses make intent explicit
    condition = (
        (Sales.country == "US") | (Sales.revenue > 500)
    ) & (Sales.cost < 100)
    condition = (Sales.country == "US") | (
        (Sales.revenue > 500) & (Sales.cost < 100)
    )
    ```

    **Always use parentheses when mixing `|` and `&` in the same expression.**

## See also

- [Building queries](queries.md) -- the full query API with `.metrics()`, `.dimensions()`, `.execute()`
- [Defining models](models.md) -- field types and how they affect filtering
- [API reference: filters](../reference/semolina/filters.md) -- full Predicate and Lookup class documentation
