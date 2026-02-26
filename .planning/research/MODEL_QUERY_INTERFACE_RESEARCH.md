# Model/Query Interface Architecture Research

**Date:** 2026-02-17
**Question:** Should Cubano support cross-semantic-view composition or simplify to model-centric Django-style queries?
**Hypothesis to test:** Analytics reporting doesn't need cross-view joins; each semantic view is independent. Dashboards compose multiple independent queries.

---

## Executive Summary

**Is cross-view composition needed for analytics use cases?**
No — and the warehouse vendors agree. Snowflake Semantic Views explicitly prohibit `AGG()` usage across multiple semantic views in a single query. Databricks Metric Views only support joins from a metric view to regular tables, not to other metric views. Every major semantic layer — Cube.dev, Looker, Metabase — converges on a model-centric pattern where each query is logically scoped to one primary entity/view/explore. Cross-view composition is either unavailable, a secondary workaround with severe limitations (Looker Merged Results: 5,000-row cap), or an advanced feature accessed through pre-defined join paths within a single model definition.

**Does a Django-style model-centric interface fit?**
Yes — strongly. The Django ORM pattern (`Model.objects.filter().aggregate()`) is the best available analogy. Boring Semantic Layer, one of the most cited modern Python semantic layer implementations, uses `model.query(dimensions=[...], measures=[...])` — which is precisely a model-centric interface. Every warehouse-native and BI semantic layer queried in this research exposes a model/view as the anchor point, not a free-floating multi-model join space.

**Recommendation: keep current design vs simplify?**
The current Cubano design already has the right instinct — one Query per one SemanticView (the `_from_clause` derives the view name from the first field's owner). However, the query API forces users to compose `Query()` independently rather than starting from the model. A model-centric entry point (`Sales.query()` or `Orders.query()`) would more closely match industry precedent and reduce the risk of accidentally mixing fields from two views in one query, which would produce undefined behavior in the current implementation. The simplification is low-risk because cross-view composition is out-of-scope both for Cubano's current backends (Snowflake, Databricks) and for dashboard use cases.

---

## Semantic Layer Architecture Comparison

### Cube.dev

**View/cube composition model**

Cube.dev uses a two-tier model:
- **Cubes** represent business entities (orders, customers, line_items). Each cube defines measures, dimensions, and join relationships to other cubes. Joins are defined *within cubes*, not views.
- **Views** are facades that sit above the cube graph. A single view can compose dimensions and measures from *multiple connected cubes*. Users query views; cubes are typically kept private.

The recommended practice per Cube.dev documentation: "all cubes should be made non-public; instead, views should be defined on top of cubes and exposed to BIs."

**Join patterns**

Joins are defined within individual cubes via a `joins` property, with explicit join type (`one_to_many`, `many_to_one`, `one_to_one`). When a query references members from multiple cubes, Cube.dev builds a "join tree" internally and traverses it. Views can "encapsulate join paths and completely remove the possibility of ambiguous join path errors." Cube.dev supports multi-cube queries, but the recommended interface is to query a view that has already resolved the join topology.

**Query interface example**

Cube.dev provides REST, GraphQL, and a Postgres-compatible SQL API. Through the SQL API:
```sql
-- Query against a view (recommended user-facing pattern)
SELECT customer_market_segment, AGG(order_average_value)
FROM sales_analysis_view
GROUP BY customer_market_segment
```
The MEASURE() function is also supported in the SQL API for metric references. At the view level, the user sees one surface. The internal join resolution happens inside Cube.

**Assessment:** Model-centric at the user-facing (view) level. Cross-view joins are resolved by Cube internally, not by the user explicitly joining views in their query.

---

### Looker LookML

**Explore/view/dimension organization**

LookML has three layers:
- **Views**: Define fields (dimensions and measures) and their linkage to underlying tables. Views map to tables or derived tables.
- **Explores**: The entry point for queries. An Explore defines which views are joined together. The Explore is effectively the query boundary — users cannot span two different Explores in a single Looker query.
- **Dimensions/Measures**: Fields within a view.

An Explore defines `join` statements that connect additional views to the base view. The recommended size: "2-3 views joined together is the sweet spot, and 5-6 is the absolute upper limit." Single-view Explores are explicitly acceptable.

**Cross-view capabilities**

Each query runs against *one* Explore. Looker provides a "Merged Results" feature for combining data from different Explores, but it is explicitly positioned as a **secondary workaround**, not the primary pattern. The Merged Results documentation states: "it is best to use a single Explore to examine your data." Merged Results also carries a hard 5,000-row limit per merged query and can "overtax Looker instance resources."

The best practice recommendation: "Whenever possible, you should use data from a single Explore." Cross-explore queries are deliberately discouraged.

**LookML query example**

Users build queries through the Explore UI field picker (no user-written LookML at query time). Programmatically:
```yaml
# model file — defines explore boundaries
explore: orders {
  join: order_items {
    type: left_outer
    sql_on: ${orders.id} = ${order_items.order_id} ;;
    relationship: one_to_many
  }
}
```
At query time, users pick dimensions/measures within the scope of a single Explore.

**Assessment:** Query-per-explore is the primary pattern. Cross-explore composition is an advanced secondary feature with hard limitations. Strongly model-centric.

---

### Metabase

**Semantic modeling approach**

Metabase's semantic layer operates on two tiers:
- **Models**: Named, curated derived tables. A model can be built from one or multiple tables, and it encapsulates joins and filters internally. Users query a model, not its underlying tables.
- **Metrics**: Reusable aggregation definitions (e.g., "total revenue") defined at the semantic layer and reused across charts/questions.

The semantic layer acts as a translation between raw warehouse tables and business concepts. Metabase's architecture is described as: "Models are your clean, curated datasets... like a well-organized spreadsheet that combines data from different places."

**Query composition patterns**

Queries in Metabase are "per model." The visual query builder starts from a model (or table) as the anchor, and joins to other tables can be defined within the query, but the mental model is: one model as the starting point per question. SQL-based questions can reference multiple models via CTEs (`{{#1-customer-model}}`), but this is a power-user feature.

Dashboard charts each have their own independent query against a model. There is no native pattern for a single question spanning two separate semantic-level models and combining their metrics.

**Assessment:** Model-centric. Each question is anchored to one model. Metrics are reusable single-model definitions. Dashboard is composed of independent per-chart queries.

---

### Django ORM

**Model-centric query pattern**

Django's ORM is the canonical example of model-centric queries:
```python
# Filter and aggregate on a single model
Book.objects.filter(name__startswith="Django").aggregate(Avg("price"))

# Group-by annotation pattern
Order.objects.values("region").annotate(total=Sum("revenue"))
```

Each QuerySet starts from a Manager on one model class: `Model.objects`. Queries stay within that model's table unless explicitly using `.select_related()` or `.prefetch_related()` (which traverse foreign keys). The user never constructs a free-floating multi-model query; relationships are resolved through the model's defined associations.

**Aggregation/filtering approach**

- `.filter()` narrows the dataset before aggregation
- `.aggregate()` computes summary values across the entire filtered set (returns a dict)
- `.annotate()` adds per-row calculations (returns a QuerySet)
- `.values()` sets the GROUP BY columns
- Chaining is immutable-style: each call returns a new QuerySet

**Applicability to analytics**

The Django ORM pattern maps naturally to semantic view queries:
| Django | Cubano semantic view |
|--------|---------------------|
| `Model.objects` | `Sales.query()` |
| `.filter(region='US')` | `.filter(Q(region='US'))` |
| `.values('region')` | `.dimensions(Sales.region)` |
| `.annotate(total=Sum('revenue'))` | `.metrics(Sales.revenue)` |
| `.aggregate(avg=Avg('price'))` | `.metrics(Sales.avg_price)` (view-defined) |

The key difference: in analytics/semantic views, the aggregation logic is pre-defined in the view (not specified by the caller). The user selects *which* metrics to include, not *how* they aggregate. This actually makes the model-centric interface *simpler* than Django ORM, not more complex.

**Assessment:** Django ORM is directly applicable. The model-centric entry point (`Sales.query()`) is the right translation. The semantic view handles aggregation definition; the query builder handles selection and filtering.

---

## Analytics Use Case Patterns

### Typical dashboard component architectures

Modern BI dashboards (Superset, Looker, Metabase, Grafana, Redash) all follow the same pattern: each chart/visualization is powered by an **independent query** against a single semantic model or table. Superset stores "all information needed to create charts in its thin data layer, including the query, chart type, options selected, and name" — per chart, not per dashboard.

When a dashboard has 10 charts, there are 10 independent queries. Each query is against one model/explore/view. Dashboards are themselves a composition layer above independent queries, not a structure that forces cross-model JOINs.

### Do they use single queries or multiple?

The universal pattern across all BI tools: **multiple independent queries per dashboard, one query per visualization.** Dashboards with 25+ tiles in Looker are explicitly cited as problematic, but the solution is optimizing individual queries (caching, pre-aggregation, shared query groups), not merging them into a single cross-view SQL statement.

Shared optimization in Databricks SQL warehouses happens when queries share the same `GROUP BY` criteria, allowing result reuse — but this is an execution-layer optimization, not a schema-level concern. It confirms the design: queries are logically independent, and the engine handles sharing.

### Cross-view join frequency in real dashboards?

From all evidence gathered: **rare in direct user-facing query construction, and when needed, handled by pre-defining join paths in the semantic model, not by the user joining views at query time.**

The Boring Semantic Layer explicitly reinforces this: "the end user can now query carrier information without having to think about any joins" — joins are hidden inside the model definition, not exposed to the query interface.

Looker's Merged Results (cross-explore composition) is positioned as an escape hatch for when "Looker developers haven't created the relationships you need" — meaning the right fix is to update the model to include the join, not to encourage cross-view queries at the user layer.

---

## Architectural Comparison Table

| Aspect | Cube.dev | Looker | Metabase | Django ORM | Current Cubano | Proposed Cubano |
|--------|----------|--------|----------|------------|----------------|-----------------|
| **Model-centric?** | Yes (view-centric) | Yes (explore-centric) | Yes (model-centric) | Yes | Partially (Query is free-floating) | Yes (SemanticView.query()) |
| **Cross-view joins** | Internal (pre-defined in cube joins) | Secondary workaround only (5K row limit) | SQL CTEs only (power user) | Via FK traversal | Not implemented (from clause from first field) | Not needed (by design) |
| **Query entry point** | View (user-facing) or direct cube SQL | Explore | Model | Model.objects | Query() constructor | SemanticView.query() |
| **Join control** | Pre-defined in schema | Pre-defined in LookML | Pre-defined in model | FK relationships on Model | N/A | N/A |
| **Aggregation definition** | In cube (measure definitions) | In LookML (measure definitions) | In model/metric | Inline at query time | In semantic view (warehouse) | In semantic view (warehouse) |
| **Aggregation selection** | User picks measures in query | User picks measures in Explore | User picks metrics in question | User defines aggregate | .metrics() | .metrics() |
| **Query interface** | REST/GraphQL/SQL API | UI field picker, LookML API | Query builder, SQL editor | Model.objects.filter().aggregate() | Query().metrics().dimensions() | SemanticView.query().metrics().dimensions() |
| **Immutability** | N/A (server-side) | N/A | N/A | Django QS are lazy, not frozen | Yes (dataclass frozen=True) | Yes |
| **Warehouse-native?** | No (middleware layer) | No (BI tool) | No (BI tool) | No (RDBMS ORM) | Yes (Snowflake/Databricks) | Yes |
| **Type safety** | No | No | No | Python runtime only | Yes (Field descriptors) | Yes |

---

## Architectural Implications of Each Choice

### Keep current design (free-floating Query builder)

**Pros:**
- More flexible — theoretically allows cross-view queries (though currently undefined behavior)
- No breaking API change
- Works as-is for single-view queries (which are the only real use case)

**Cons:**
- Users can accidentally mix fields from two different SemanticViews in one Query — current `_build_from_clause` takes the view name from the first field's owner, silently ignoring all other owners
- Doesn't match industry precedent (every major semantic layer is model-centric)
- Harder to discover: `Query()` doesn't guide users toward which views exist
- IDE autocomplete doesn't chain naturally: `Query().metrics(` doesn't know which model is being queried

### Simplify to model-centric (SemanticView.query())

**Pros:**
- Matches industry precedent exactly (Boring Semantic Layer, Cube.dev views, Looker explores, Metabase models)
- Eliminates mixed-view bugs by design: `Sales.query()` can only select `Sales.*` fields
- Better discoverability: `Sales.query().metrics(Sales.` autocompletes to valid options
- Cleaner mental model: "I want to query my Orders model" not "I want to build a query and add fields from somewhere"
- Aligns with Snowflake/Databricks constraint: single semantic view per query is exactly what the backends enforce
- Django-style familiarity: `Model.objects.filter()` → `SemanticView.query().filter()`

**Cons:**
- API change from `Query()` constructor (though v0.1 hasn't been widely adopted yet)
- Would need to decide if `Query` class is kept for internal use or removed
- Must decide how `.using()` (engine selection) propagates from the model-centric entry

### Hybrid approach: Both entry points

Keep `Query()` as the internal/low-level API, but add `SemanticView.query()` as the primary user-facing entry point that returns a Query pre-scoped to that view. This allows:
```python
# Recommended model-centric (new)
Sales.query().metrics(Sales.revenue).dimensions(Sales.region).fetch()

# Advanced/internal: still possible
Query().metrics(Sales.revenue).dimensions(Sales.region).fetch()
```

The model-centric entry could enforce view consistency (reject fields from other views at construction time). The raw `Query()` remains for internal use and advanced scenarios.

---

## Recommendation

### Should Cubano support cross-view composition?

**No.** The warehouse backends (Snowflake, Databricks) enforce single-view queries at the SQL level. Snowflake's `AGG()` function only works within a single semantic view context. Databricks Metric Views only join to regular tables, not to other metric views. Building cross-view composition in Cubano would require either CTE workarounds that may not work with semantic view syntax, or joining regular tables (bypassing the semantic layer entirely). The use case is not needed for dashboard analytics.

### What interface style best fits analytics?

**Model-centric**, anchored to `SemanticView.query()`. This matches:
- How every other semantic layer (Cube, Looker, Metabase, Boring Semantic Layer) exposes queries
- How Django ORM works (the closest general-purpose analogy)
- The underlying warehouse constraint (one semantic view per query)
- The actual dashboard use case (one model per chart, many independent charts per dashboard)

### Django-style feasibility for warehouse queries

**High feasibility, low risk.** The translation is direct:

```python
# Django ORM
Book.objects.filter(genre='Analytics').values('author').annotate(avg_price=Avg('price'))

# Proposed Cubano (model-centric)
Books.query().filter(Q(genre='Analytics')).dimensions(Books.author).metrics(Books.avg_price).fetch()
```

The warehouse-native difference (aggregation logic lives in the view, not the query) simplifies Cubano's interface relative to Django ORM: users don't specify `Sum()`, `Avg()`, etc. — they just name the metric. This makes model-centric even *more* natural in the analytics context than in Django's OLTP context.

The current `Query` class implementation (frozen dataclass, fluent chaining) is an excellent foundation. Adding `SemanticView.query()` as a class method that returns a `Query` pre-bound to the view's context is a small, low-risk addition that provides large ergonomic gains.

---

## Confidence Levels

| Finding | Confidence |
|---------|-----------|
| Snowflake prohibits AGG() across multiple semantic views in one query | [HIGH] — confirmed from official Snowflake documentation |
| Databricks Metric Views do not support joining two metric views | [HIGH] — confirmed from official Databricks documentation |
| Dashboard analytics uses one query per chart (not cross-view joins) | [HIGH] — confirmed across Superset, Looker, Metabase, Grafana architecture documentation |
| Looker cross-explore Merged Results is a secondary workaround (not primary) | [HIGH] — confirmed from official Looker documentation with explicit warnings |
| Cube.dev joins are resolved internally, not exposed to users at query time | [HIGH] — confirmed from Cube.dev documentation |
| Boring Semantic Layer uses model.query() interface | [HIGH] — confirmed from primary source |
| Django ORM model-centric pattern is directly applicable to analytics | [MEDIUM] — conceptual translation; semantic views differ from RDBMS in that aggregation is pre-defined |
| Model-centric interface would improve Cubano discoverability and correctness | [MEDIUM] — inferred from industry patterns; no direct user research on Cubano |
| Cross-view composition is never needed for analytics use cases | [MEDIUM] — strong pattern evidence, but complex reporting (e.g., blending revenue and headcount data from different semantic domains) may need it in enterprise scenarios |
| Adding SemanticView.query() is low-risk | [HIGH] — it would wrap existing Query infrastructure, not replace it |

---

## Sources

- Snowflake Semantic Views Documentation: https://docs.snowflake.com/en/user-guide/views-semantic/querying
- Snowflake SEMANTIC_VIEW clause reference: https://docs.snowflake.com/en/sql-reference/constructs/semantic_view
- Databricks Metric Views - Joins: https://docs.databricks.com/aws/en/metric-views/data-modeling/joins
- Cube.dev Introduction: https://cube.dev/docs/product/introduction
- Cube.dev Joins Between Cubes: https://cube.dev/docs/product/data-modeling/concepts/working-with-joins
- Cube.dev Views for metrics: https://cube.dev/blog/complementing-data-graph-with-views
- Looker LookML Terms and Concepts: https://docs.cloud.google.com/looker/docs/lookml-terms-and-concepts
- Looker Explores Best Practices (dbt Labs): https://www.getdbt.com/blog/looker-explores-best-practices
- Looker Merged Results: https://docs.cloud.google.com/looker/docs/merged-results
- Metabase Models Documentation: https://www.metabase.com/docs/latest/data-modeling/models
- MetricFlow About: https://docs.getdbt.com/docs/build/about-metricflow
- Boring Semantic Layer: https://juhache.substack.com/p/the-boring-semantic-layer
- Semantic Layer Architectures Explained (2025): https://www.typedef.ai/resources/semantic-layer-architectures-explained-warehouse-native-vs-dbt-vs-cube
- Semantic Layer MetricFlow vs Snowflake vs Databricks: https://www.typedef.ai/resources/semantic-layer-metricflow-vs-snowflake-vs-databricks
- Django Aggregation Documentation: https://docs.djangoproject.com/en/6.0/topics/db/aggregation/
- Building Dashboards over Semantic Layer (Cube + Superset): https://cube.dev/blog/building-dashboards-over-semantic-layer-with-superset-and-cube
- Apache Superset Architecture: https://superset.apache.org/docs/installation/architecture/
