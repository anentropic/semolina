# Domain Pitfalls

**Domain:** Python ORM / Query Builder for Data Warehouse Semantic Views
**Researched:** 2026-02-14
**Confidence:** MEDIUM (based on training knowledge of ORM design patterns, no current web sources available)

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: Metaclass Parameter Contamination via Mutable Defaults
**What goes wrong:** When metaclass-based models use mutable defaults (lists, dicts) for field definitions, all instances share the same object, causing cross-contamination between model classes.

**Why it happens:** Python evaluates default arguments once at function definition time. With metaclasses processing multiple classes, a field descriptor with `default=[]` becomes a shared reference across all models.

**Consequences:**
- Field metadata corruption across unrelated models
- Registry pollution where one model's fields leak into another
- Extremely difficult to debug (appears as intermittent, order-dependent bugs)
- Can corrupt query generation, selecting wrong fields or applying wrong filters

**Prevention:**
- Use `None` as default and initialize mutables in `__init__` or descriptor `__get__`
- In metaclass `__new__`, create fresh copies of field descriptors per class
- Freeze field metadata after model class creation (use `dataclasses.FrozenInstanceError` pattern)
- Add metaclass test that instantiates multiple model classes and verifies field isolation

**Detection:**
- Test fails when you define two models in different order
- Field attributes appear on wrong models
- Registry contains fields from unrelated models
- `dir(ModelA)` shows fields from `ModelB`

**Phase impact:** Phase 1 (Model System) — must be correct from the start or entire metaclass foundation is unsound.

---

### Pitfall 2: Immutable Query Builder Accidental Mutation
**What goes wrong:** Immutable query builders that use `dataclasses.replace()` or manual copy can accidentally share nested mutable state (filter lists, selected field sets) across "copies."

**Why it happens:** Python's copy semantics are shallow by default. When you copy a query object with `replace(self, filters=...)`, if `filters` is a list reference, both the old and new query share the same list object.

**Consequences:**
- `query1 = Model.query().filter(x=1); query2 = query1.filter(y=2)` causes `query1` to also have `y=2` filter
- Reusing base queries becomes impossible (a common pattern for applying shared filters)
- Subtle bugs where queries mysteriously gain extra filters or selections
- Thread-safety issues if queries are shared across async contexts

**Prevention:**
- Use `tuple` instead of `list` for internal collections (filters, selected fields, order_by clauses)
- If lists are necessary, deep copy in every query-modifying method: `filters=self._filters + [new_filter]` (creates new list)
- Implement `__post_init__` that freezes mutable attributes into immutable equivalents
- Add test: `base = Model.query(); q1 = base.filter(x=1); q2 = base.filter(y=2); assert q1 != q2`

**Detection:**
- Test: create base query, branch into two queries, verify independence
- Print `id(query1._filters)` vs `id(query2._filters)` — should differ
- Watch for filters "mysteriously" appearing in queries that never added them

**Phase impact:** Phase 2 (Query Builder) — core architecture decision. Fixing later requires rewriting every query-modifying method.

---

### Pitfall 3: SQL Injection via Unparameterized Field Names
**What goes wrong:** Treating field references as safe identifiers without sanitization allows SQL injection when field names are dynamically constructed or user-influenced.

**Why it happens:** Developer assumes "field refs only, no strings" means no injection risk, but forgets that `Field` objects contain string names that get interpolated into SQL: `SELECT {field.name} FROM ...`

**Consequences:**
- SQL injection vulnerability if field names can be influenced (e.g., via codegen, introspection, or dynamic model creation)
- Even with field refs, malicious model classes can inject SQL: `evil_revenue = Metric(name="revenue; DROP TABLE--")`
- Destroys the security benefit of parameterized queries

**Prevention:**
- **Always** quote identifiers: use backend-specific quoting (`"field"` for Snowflake/Databricks, backticks for MySQL)
- Validate field names against `^[a-zA-Z_][a-zA-Z0-9_]*$` regex during model class creation (in metaclass)
- Use SQL builder library's identifier quoting (e.g., SQLAlchemy's `quoted_name`) instead of manual string interpolation
- Never allow user input to directly influence field names, even indirectly
- In MockEngine, assert that all generated SQL uses quoted identifiers

**Detection:**
- Test with field named `revenue"; DROP TABLE users--` — should either reject during model creation or safely quote in SQL
- SQL output should show `SELECT "field_name"` not `SELECT field_name`
- Grep for f-strings or `.format()` calls in SQL generation — replace with parameterization

**Phase impact:** Phase 3 (SQL Generation) — security issue must be addressed before any production use.

---

### Pitfall 4: Lazy Engine Resolution with Stale Registry State
**What goes wrong:** Lazy engine resolution at `.fetch()` time allows models to be imported before engines are registered, but creates confusion when engines are registered, then cleared, then re-registered — old query objects still hold stale references or fail with cryptic errors.

**Why it happens:** Query object creation happens at `Model.query()` time (early), but engine lookup happens at `.fetch()` time (late). If registry is mutated between these two points, the query has no idea the world changed.

**Consequences:**
- Test isolation breaks: one test mutates registry, next test's queries fail
- In multi-threaded apps, query built in one context fails when executed in another
- Django app reload (dev server) can leave stale engines in registry
- Error messages like "engine 'default' not found" appear on queries that worked before

**Prevention:**
- Make registry immutable after initial population — raise error on double-registration
- Provide explicit `registry.reset()` method for tests only (not importable from main package)
- Document that queries are lazy — don't build queries in module scope, build them in functions
- In tests, use fixture with cleanup: `yield; registry.reset()`
- Consider making Query store engine name, not engine reference, and re-resolve on every `.fetch()`

**Detection:**
- Test: register engine, build query, unregister engine, call `.fetch()` — should fail with clear error
- Test: register engine1, build query, register engine2 with same name, fetch query — should use engine2 or fail clearly
- Check for `UnboundLocalError` or `AttributeError` when fetching queries

**Phase impact:** Phase 4 (Engine Registry) — must establish rules before framework integrations (Django, FastAPI) are built, or every integration will have different broken behavior.

---

### Pitfall 5: Implicit GROUP BY Miscalculation with Window Functions
**What goes wrong:** When deriving GROUP BY from selected dimensions, the logic fails to account for fields that look like dimensions but are actually window function results, causing invalid SQL.

**Why it happens:** Semantic views can have "derived dimensions" that are calculated via window functions (e.g., `RANK() OVER (...)`). These cannot appear in GROUP BY, but the query builder assumes "dimension = add to GROUP BY."

**Consequences:**
- SQL errors: `column "rank" must appear in GROUP BY clause or be used in aggregate function`
- Valid queries in the warehouse UI fail when generated by Cubano
- Users have to manually specify GROUP BY, defeating the purpose of implicit derivation

**Prevention:**
- Track metadata on fields: `is_aggregate: bool`, `is_window: bool`
- Exclude window functions from automatic GROUP BY derivation
- In SQL generation, inspect field expressions for `OVER (...)` clause — if present, exclude from GROUP BY
- Document that window-function-based dimensions require explicit handling
- For Snowflake/Databricks semantic views, this may not be an issue if the view definition disallows window functions in dimensions (verify in docs)

**Detection:**
- Test with a dimension defined as `RANK() OVER (PARTITION BY category ORDER BY sales DESC)`
- Verify generated SQL does not include that field in GROUP BY
- Execute against MockEngine with validation that simulates warehouse SQL parser

**Phase impact:** Phase 3 (SQL Generation) — likely won't appear until real-world usage with complex semantic views. Can be deferred if window functions in dimensions are rare/unsupported.

---

### Pitfall 6: Backend-Specific Metric Syntax Hardcoded in Wrong Layer
**What goes wrong:** SQL generation layer assumes all backends use `AGG(metric)` or `MEASURE(metric)`, hardcoding the syntax choice instead of delegating to the Engine.

**Why it happens:** Design notes say "SnowflakeEngine generates AGG(), DatabricksEngine generates MEASURE()" but if this logic lives in a shared SQL builder, it becomes a tangled mess of `if backend == "snowflake"` checks.

**Consequences:**
- Adding a third backend (e.g., Cube.dev, which uses different syntax) requires editing core SQL generation
- SQL generation becomes untestable in isolation (needs to know about all backends)
- MockEngine either has to fake a real backend's syntax or becomes inconsistent with production

**Prevention:**
- Each Engine subclass implements `.render_metric(field: Field) -> str` and `.render_dimension(field: Field) -> str`
- Query builder calls `engine.render_metric(metric)` instead of hardcoding `f"AGG({metric.name})"`
- SQL generation layer is backend-agnostic; all dialect knowledge lives in Engine classes
- MockEngine can use simplified syntax (e.g., just return field name) for testing

**Detection:**
- Grep for `"AGG("` or `"MEASURE("` in query builder code — should only appear in Engine subclasses
- Test: swap in a MockEngine with different syntax, verify queries still generate correctly
- Add a third fake backend in tests, ensure no core code changes needed

**Phase impact:** Phase 3 (SQL Generation) + Phase 5 (Backend Engines) — architectural decision. Fixing later requires rewriting SQL generation.

---

### Pitfall 7: Dynamic Row Class Attribute Conflicts with Python Built-ins
**What goes wrong:** Custom Row class dynamically adds attributes for each selected field (`row.revenue`, `row.country`). If a field is named `items`, `keys`, `values`, `get`, etc., it shadows the dict-like methods Row should provide.

**Why it happens:** Row class provides both attribute access (`row.revenue`) and dict-like access (`row['revenue']`, `row.keys()`). Dynamic `__setattr__` or `__getattr__` doesn't check for conflicts with built-in method names.

**Consequences:**
- `row.keys()` returns field value instead of dict keys
- `row.get('other')` fails because `.get` is a field value, not a method
- Confusing errors when Row is used in contexts expecting dict-like behavior
- Python's type checker (mypy) can't catch these conflicts

**Prevention:**
- Use separate namespaces: `row.fields.revenue` for attribute access, `row['revenue']` for dict-like access
- OR: Reserved keywords list — raise error if field name conflicts with Row methods (`keys`, `values`, `items`, `get`)
- OR: Prefix field attributes: `row.f_revenue`, `row.f_country` to avoid all conflicts
- Document the trade-off: convenience vs. safety
- Implement `__dir__` to show both fields and methods correctly for IDE autocomplete

**Detection:**
- Test with field names: `keys`, `values`, `items`, `get`, `pop`, `update`
- Verify `row.keys()` returns keys, not field value
- Verify `row['keys']` returns field value (if field is named 'keys')

**Phase impact:** Phase 6 (Result Handling) — can be fixed later if convention is established early (e.g., never select fields named 'keys'), but better to address architecturally.

---

### Pitfall 8: Q-Object Deep Copy Breaks with Field References
**What goes wrong:** Q-objects hold field references (e.g., `Q(Sales.revenue > 1000)`). When queries are copied (for immutability), if Q-objects are shallow-copied, the field references can become stale or point to wrong model classes.

**Why it happens:** Field descriptors are class-level objects. If model classes are dynamically created or reloaded (e.g., in Django dev server), the field reference `Sales.revenue` in an old Q-object points to the old `Sales` class, not the new one.

**Consequences:**
- Filter logic uses wrong model class
- Field name lookups fail: `AttributeError: 'Field' object has no attribute 'model'`
- Query behavior changes after code reload

**Prevention:**
- Q-objects should store field names (strings) and model references, not direct field objects
- OR: Q-objects are immutable and never copied — always create fresh Q-objects
- OR: Implement `__deepcopy__` on Q-objects to handle field references correctly
- Document that Q-objects should not be reused across model reloads

**Detection:**
- Test: create Q-object with field ref, reload model class, apply Q-object to new query
- In Django integration, test that dev server reload doesn't break existing Q-objects

**Phase impact:** Phase 2 (Query Builder - Q-objects) — can be deferred until framework integrations where model reloading is an issue, but better to design correctly from start.

---

## Moderate Pitfalls

### Pitfall 9: Time Dimension Ambiguity (Dimension vs. Fact vs. Metric)
**What goes wrong:** Semantic views have "time dimensions" (DATE_REPORTING_LOCAL) that can be selected like dimensions, but some queries need to aggregate over time (e.g., `DATE_TRUNC('month', date)`). The model system doesn't distinguish between "time as dimension" and "time as aggregation target."

**Prevention:**
- For MVP, treat time dimensions as regular dimensions (per design decision: "time dims are just dimensions")
- Document that time granularity transformations (month, quarter) must be defined in the semantic view itself, not in Cubano queries
- Defer convenience API (`.time(field, granularity='month')`) to later milestone
- Ensure semantic view YAML examples include pre-aggregated time dimensions at different granularities

**Detection:**
- User tries to query `.dimensions(Sales.date.month)` and expects automatic DATE_TRUNC
- Error message should guide: "Time granularity must be defined in semantic view. Select the pre-defined monthly dimension instead."

---

### Pitfall 10: Metric-Dimension Validity Not Enforced
**What goes wrong:** Not all metric-dimension combinations are valid in semantic views (e.g., can't combine metrics from different fact tables without a join). Cubano doesn't validate this until execution, causing cryptic warehouse errors.

**Prevention:**
- For MVP: explicitly out-of-scope (per design decision: "defer validation to warehouse")
- Document that invalid combinations produce warehouse errors, not Cubano errors
- In later phase, add optional validation via semantic view introspection
- MockEngine should include a "strict mode" that rejects invalid combinations for testing

**Detection:**
- User selects incompatible metrics/dimensions, gets warehouse error
- Error message from warehouse is exposed directly (don't hide it)

---

### Pitfall 11: Fact vs. Dimension Confusion in Query Building
**What goes wrong:** Facts (non-aggregated values like `vehicle_odometer`) behave like dimensions in queries but are conceptually different. Users might try to use them as metrics (`SUM(fact)`) or be confused about when to use `.dimensions()` vs. `.metrics()`.

**Prevention:**
- Design decision already addresses this: "Facts selected via `.dimensions()` (behave like dimensions in queries)"
- Document clearly: Facts are non-aggregated values, selected like dimensions, not metrics
- Error message if user passes Fact to `.metrics()`: "field_name is a Fact, not a Metric. Use .dimensions(field_name) instead."
- In field type hierarchy, consider `Fact` as subclass of `Dimension` to make this relationship explicit in code

**Detection:**
- Test: `Sales.query().metrics(Sales.vehicle_odometer)` should raise error
- Test: `Sales.query().dimensions(Sales.vehicle_odometer)` should succeed

---

### Pitfall 12: MockEngine Divergence from Real Backend Behavior
**What goes wrong:** MockEngine is built first (per design decision) but doesn't faithfully replicate real backend constraints (e.g., Snowflake's requirement that metrics use `AGG()`, Databricks' `MEASURE()`). Tests pass on MockEngine but fail on real backends.

**Prevention:**
- Make MockEngine configurable: `MockEngine(dialect='snowflake')` vs. `MockEngine(dialect='databricks')`
- Dialect mode enforces backend-specific SQL generation rules
- Include "strict" mode that validates SQL syntax rules (GROUP BY presence, metric wrapper functions, identifier quoting)
- Integration tests against real Snowflake/Databricks instances (even if just sandboxes)

**Detection:**
- All tests pass on MockEngine, fail on SnowflakeEngine
- SQL generated for MockEngine looks different from SQL for SnowflakeEngine
- Add test: generate same query for MockEngine(dialect='snowflake') and SnowflakeEngine, compare SQL strings

---

### Pitfall 13: Registry Race Conditions in Multi-threaded Apps
**What goes wrong:** Registry is populated at app startup, but if engines are registered from multiple threads (e.g., FastAPI lifespan + background tasks), race conditions can occur.

**Prevention:**
- Registry uses thread-safe dict (or locks) for mutation
- Document that registration should happen single-threaded at startup only
- After initial population, make registry read-only (raise error on further `.register()` calls)
- Provide `registry.finalize()` method that locks the registry

**Detection:**
- Test: register engines from multiple threads simultaneously, verify no corruption
- Test: call `.finalize()`, then try to register another engine, should raise error

---

### Pitfall 14: Field Name Collision Between Model Attributes and Class Methods
**What goes wrong:** User defines `class Sales(SemanticView): query = Metric()`. This shadows the `Sales.query()` class method, breaking query construction.

**Prevention:**
- In metaclass `__new__`, check for field name collisions with reserved names: `query`, `using`, `fetch`, etc.
- Raise error: `"Field name 'query' is reserved. Rename this field."`
- Document reserved field names
- Consider namespacing: all fields live in `Sales.fields.revenue`, while `Sales.query()` is separate

**Detection:**
- Test: define model with field named `query`, verify error is raised
- Test: all reserved method names (`query`, `objects`, `meta`, etc.)

---

### Pitfall 15: ORDER BY Field Not in SELECT Clause
**What goes wrong:** User calls `.order_by(Sales.revenue)` but doesn't include `Sales.revenue` in `.metrics()`. Some databases allow this, some don't. Snowflake/Databricks behavior may differ.

**Prevention:**
- Auto-add ORDER BY fields to SELECT clause (implicit inclusion)
- OR: Validate and raise error: `"Cannot order by 'revenue' without selecting it. Add .metrics(Sales.revenue) to your query."`
- Document the behavior clearly
- Test on real backends to determine actual constraint

**Detection:**
- Test: `.dimensions(Sales.country).order_by(Sales.revenue).fetch()` — verify behavior
- Check generated SQL: does it include `revenue` in SELECT?

---

## Minor Pitfalls

### Pitfall 16: Missing `__repr__` on Query Objects Hinders Debugging
**What goes wrong:** When debugging, `print(query)` shows `<Query object at 0x...>` instead of human-readable representation of selected fields, filters, etc.

**Prevention:**
- Implement `__repr__` on Query class showing: model, selected metrics/dimensions, filters, order_by, limit
- Example: `<Query: Sales | metrics=[revenue, orders] | dimensions=[country] | filters=[country=US] | limit=100>`
- Include `.to_sql()` in `__str__` for even more debugging detail

---

### Pitfall 17: Empty Query Generates Invalid SQL
**What goes wrong:** `Sales.query().fetch()` with no metrics or dimensions selected generates `SELECT FROM sales` (invalid SQL).

**Prevention:**
- Validate before SQL generation: must select at least one metric or dimension
- Raise error: `"Query must select at least one field. Use .metrics() or .dimensions()."`
- OR: Default to `SELECT * FROM view` (but this may not work with semantic views)

**Detection:**
- Test: `Sales.query().fetch()` should raise error, not attempt execution

---

### Pitfall 18: Filter on Non-selected Dimension
**What goes wrong:** User calls `.filter(Sales.country == 'US')` but doesn't select `Sales.country` in `.dimensions()`. This is valid SQL (`WHERE` clause doesn't require field to be in `SELECT`), but might confuse users.

**Prevention:**
- Allow it (valid SQL)
- Document that filters don't require selection
- Optional warning in strict mode

---

### Pitfall 19: Forgetting to Call `.fetch()` Returns Query Object, Not Results
**What goes wrong:** User writes `results = Sales.query().metrics(Sales.revenue)` and expects data, but gets Query object.

**Prevention:**
- This is standard ORM behavior (Django, SQLAlchemy both work this way)
- Document clearly with examples
- Consider implementing `__iter__` on Query that auto-calls `.fetch()`: `for row in Sales.query().metrics(...): ...`

**Detection:**
- User error: "expected list, got Query object"

---

### Pitfall 20: Connection Pooling Exhaustion
**What goes wrong:** Each `.fetch()` call opens a new connection, never closing it. Connection pool exhausts.

**Prevention:**
- Document that connection pooling is backend driver concern (Snowflake connector, Databricks connector)
- Engine wraps backend client, which should handle pooling
- Add context manager support: `with engine: query.fetch()` for explicit connection lifecycle
- OR: Document that `Engine` should be singleton per process

**Detection:**
- After many `.fetch()` calls, new queries fail with "connection pool exhausted"

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Phase 1: Metaclass Model System | Mutable defaults in field descriptors (Pitfall 1) | Use tuple/frozenset, create fresh copies per class |
| Phase 1: Metaclass Model System | Field name collisions with class methods (Pitfall 14) | Reserved name validation in metaclass |
| Phase 2: Query Builder | Accidental mutation in immutable builder (Pitfall 2) | Use tuples for internal state, deep copy tests |
| Phase 2: Q-objects | Field reference staleness on copy (Pitfall 8) | Store field names + model refs, not field objects |
| Phase 3: SQL Generation | SQL injection via field names (Pitfall 3) | Validate and quote all identifiers |
| Phase 3: SQL Generation | Backend syntax hardcoded (Pitfall 6) | Delegate rendering to Engine subclasses |
| Phase 3: SQL Generation | Implicit GROUP BY with window functions (Pitfall 5) | Track field metadata, exclude window functions |
| Phase 4: Registry | Lazy resolution with stale state (Pitfall 4) | Make registry immutable post-init, clear reset semantics |
| Phase 4: Registry | Multi-threaded registration races (Pitfall 13) | Thread-safe dict, finalize() method |
| Phase 5: Backend Engines | MockEngine divergence (Pitfall 12) | Dialect modes, strict validation, integration tests |
| Phase 6: Result Handling | Row class attribute conflicts (Pitfall 7) | Reserved keyword check or namespace separation |
| Phase 7: Snowflake/Databricks | Metric-dimension validity not enforced (Pitfall 10) | Document warehouse errors, defer validation to later |
| Phase 7: Snowflake/Databricks | Time dimension aggregation confusion (Pitfall 9) | Document view-side granularity, defer convenience API |

---

## Data Warehouse Semantic Layer Specific Warnings

### Snowflake Semantic Views
- **AGG() requirement**: All metrics MUST be wrapped in `AGG()`, even when selecting a single metric. This is non-negotiable.
- **SEMANTIC_VIEW() clause**: Cubano design chooses standard SQL instead, but verify this works with all Snowflake semantic view features.
- **Fact table fan-out**: Snowflake semantic views can join multiple fact tables, causing row multiplication. Users expect automatic fan-out protection (Snowflake provides this, but Cubano must not break it).

### Databricks Metric Views
- **MEASURE() requirement**: Similar to Snowflake's AGG(), but different function name.
- **Unity Catalog namespacing**: Metric views are catalog/schema/view (three-part names). Ensure model system supports fully-qualified view names.
- **Parameter binding**: Databricks SQL connector has different parameter binding syntax than Snowflake (`:param` vs `?`). Ensure backend abstraction handles this.

### General Semantic Layer
- **Metric aggregation assumptions**: Semantic views pre-define aggregation logic (SUM, AVG, COUNT). Cubano must not try to re-aggregate metrics (no `SUM(AGG(revenue))`).
- **Security/access control**: Semantic views have row-level security and column-level access. Cubano queries should not bypass or break these (don't construct raw SQL that goes around the view).
- **Caching and materialization**: Some semantic views are materialized, some are virtual. Query performance can vary wildly. Cubano can't control this but should document it.

---

## Sources

**Confidence: MEDIUM**

This research is based on:
- Training knowledge of ORM design patterns (SQLAlchemy, Django ORM, Peewee, Pony ORM architecture)
- Training knowledge of Python metaclass pitfalls and descriptor protocols
- Training knowledge of immutable data structure patterns in Python
- Project context from .planning/PROJECT.md and .resources/design/notes.md
- Semantic view YAML examples from .resources/ifm-semantic-layer/

**Limitations:**
- Web search was unavailable, so no current (2026) sources on Snowflake/Databricks semantic view gotchas
- Cannot verify current best practices for semantic layer query libraries
- Cannot confirm whether Snowflake/Databricks have updated their SQL syntax or constraints since training cutoff (January 2025)

**Recommended validation:**
- Verify Snowflake AGG() and Databricks MEASURE() requirements in official 2026 documentation
- Check if window functions are supported in semantic view dimensions
- Review SQLAlchemy 2.x and Django 5.x ORM recent issues/discussions for modern pitfalls
- Test actual Snowflake/Databricks semantic view behavior with edge cases (empty queries, missing GROUP BY, etc.)
