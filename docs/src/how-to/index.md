# How-to guides

Practical guides for specific tasks. Each guide focuses on one topic and assumes
you already know the basics from the [tutorials](../tutorials/index.md).

## Backends

- [Backend overview](backends/overview.md) -- choose a backend and connect to your warehouse
- [Snowflake](backends/snowflake.md) -- connect to Snowflake semantic views
- [Databricks](backends/databricks.md) -- connect to Databricks metric views

## Models and queries

- [Defining models](models.md) -- map SemanticView subclasses to your warehouse views
- [Building queries](queries.md) -- chain `.metrics()`, `.dimensions()`, `.where()`, and more
- [Filtering](filtering.md) -- filter with field operators and boolean composition
- [Ordering and limiting](ordering.md) -- sort results and cap row counts

## Tools

- [Codegen CLI](codegen.md) -- generate warehouse-native SQL from your models
- [Warehouse testing](warehouse-testing.md) -- snapshot-based testing with syrupy
