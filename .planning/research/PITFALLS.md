# Domain Pitfalls

**Domain:** Python ORM / Query Builder for Data Warehouse Semantic Views
**Researched:** 2026-02-17
**Confidence:** MEDIUM-HIGH (existing pitfalls HIGH confidence from prior research; new v0.2 pitfalls MEDIUM confidence from 2026 ecosystem research)

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

### Pitfall 21: Generated Code Diverges from Model Source Definition (Codegen Drift)

**What goes wrong:** Codegen produces model classes from warehouse schema, but the source semantic view definition evolves independently. Users edit generated models by hand, or the warehouse schema drifts, leaving generated code inconsistent with reality. Regenerating code clobbers manual edits.

**Why it happens:**
- Generated code is often treated as "source of truth" by users who hand-edit it
- Schema drift in the warehouse (ALTER TABLE, column renames) isn't reflected in generated models
- Codegen tool is run once at project setup, then ignored as source files evolve
- No versioning strategy for generated artifacts — regenerating doesn't preserve compatibility

**Consequences:**
- Running codegen a second time clobbers user customizations (custom method, type overrides)
- Generated models reference deleted warehouse columns, causing runtime errors
- TypeChecking falsely passes (mypy says field exists) but warehouse rejects the query at execution
- Different versions of code running against same warehouse produce different SQL
- Users forced to maintain manual mapping between old generated code and new warehouse schema

**Prevention:**
- **Store codegen metadata in generated file** — include schema version hash, generation timestamp, source view name, incompatibility warnings
- **Generate with comments, not executable code** — don't auto-apply changes; ask user to review diffs: `codegen diff` command shows what changed
- **Never overwrite without backup** — `cubano codegen --mode merge` merges new fields while preserving custom methods; or `--mode diff` shows changes without applying
- **Version-lock semantic view references** — generated models reference view version: `from_view("sales@v2.1.3")` catches schema drift at import time
- **Validation at runtime** — before first query, introspect warehouse schema and validate it matches generated model definition, raise if drift detected
- **Separate generated and custom code** — generated base class lives in `_generated.py`, user extends in `models.py` to preserve edits across regeneration
- **Track field lineage** — store mapping between Cubano field and warehouse column path, validate on fetch

**Detection:**
- Run codegen twice without changes to source, diff the output — should be identical (including comments, field ordering)
- After warehouse schema change, existing queries fail with "column doesn't exist" but generated code still references it
- Regenerate code that users had customized — custom code is lost without warning
- User sees different generated SQL in two different parts of the codebase

**Warning signs:**
- Generated file modification timestamps change between runs
- Comments in generated file reference wrong schema version
- Runtime error: "SELECT <field> from <view>" but field doesn't exist in warehouse
- Two generated models reference same warehouse view but have different field names

**Phase to address:** Phase 8 (Codegen) — CRITICAL. Must establish generation and merge strategy before users create their first models, or face painful migration later.

---

### Pitfall 22: Integration Tests Depend on Shared Warehouse State (Flaky, Expensive, Slow)

**What goes wrong:** Integration tests run against a shared test warehouse, but don't isolate test data. One test creates rows, another test expects clean state. Tests fail intermittently when run in different order or in parallel. Test runs incur warehouse costs even for failed tests.

**Why it happens:**
- Developers write integration tests assuming sequential execution and clean state
- No test fixture for data isolation — tests query "live" data in test warehouse
- Test data accumulates across runs (no teardown), or is stale if old tests never clean up
- Parallel test execution (pytest-xdist, tox) creates race conditions on shared tables
- Warehouse connection pooling/credentials scattered across test files — no centralized management
- No distinction between expensive warehouse I/O and cheap local validation

**Consequences:**
- Test suite takes 30+ minutes to run (every `.fetch()` hits warehouse)
- Test failures are non-deterministic (depend on test order, background jobs, data cleanup timing)
- CI/CD pipeline becomes unreliable ("flaky tests erode trust")
- Warehouse costs spiral (100 test runs × 50 tests × warehouse I/O = expensive)
- Debugging is nightmarish (same test passes locally, fails in CI on 9th retry)
- Team stops running tests (too slow) and bugs slip into production

**Prevention:**
- **Fixture-based isolation with cleanup**: Every integration test uses a fixture that creates fresh test data and guarantees cleanup
  ```python
  @pytest.fixture
  def test_warehouse(warehouse_connector):
      # Create isolated test schema
      test_schema = f"test_{uuid4()}"
      yield warehouse_connector.with_schema(test_schema)
      # Cleanup: drop test schema
  ```
- **Testcontainers or local mock warehouse** for fast, cheap feedback: `pytest-snowflake-local` or similar for testing without hitting real warehouse
- **Separate unit tests (fast, local) from integration tests (slow, warehouse)**:
  - Unit tests: MockEngine, no warehouse dependency, run in ~100ms
  - Integration tests: Real warehouse, separate `tests/integration/` directory, marked with `@pytest.mark.integration`, run on-demand or in CI only
- **Test data management**:
  - Use temporary tables per test, not shared permanent tables
  - Provide `warehouse_fixture_factory` that creates/destroys data safely
  - Document: "never SELECT from production schema in tests"
- **Connection management**:
  - Centralize warehouse credentials in one fixture (`@pytest.fixture(scope='session')` for credentials)
  - Provide `warehouse_engine` fixture that handles connection pooling and cleanup
  - Never hardcode credentials in test files
- **Parallel-safe test naming**:
  - If tests must use shared table names, use `pytest-xdist` worker ID: `f"test_data_{worker_id}"`
  - OR: Use temporary schema per worker
- **Cost tracking**:
  - Monitor test warehouse spend; add cost budgets to CI
  - Document which tests require warehouse (expensive) vs. which can use mock
  - Alert if test spend spikes (sign of missing cleanup or inefficient fixture)

**Detection:**
- Test passes when run alone, fails when run with other tests
- Test fails if tests run in parallel (`pytest -n auto` fails, `-n 0` passes)
- Test fails in CI but passes locally (environ difference, stale test data in CI warehouse)
- Warehouse spend doubles after adding 10 new tests (no cleanup)
- Same test fails 2/5 times in CI reruns (flakiness indicator)

**Warning signs:**
- Tests take >1 second each (should be <100ms without warehouse I/O)
- No `conftest.py` managing warehouse fixtures
- Credentials in `tests/*.py` files (not centralized in config)
- Tests query `PROD.PUBLIC.SALES` (should use `TEST.SCHEMA_<UUID>.SALES`)
- Test cleanup code commented out ("will run manually later")

**Phase to address:** Phase 9 (Integration Tests) — CRITICAL. Must establish test infrastructure before writing first integration test, or face mounting technical debt and flaky CI.

---

### Pitfall 23: Documentation Examples Become Stale as API Changes (Broken Code Examples)

**What goes wrong:** Documentation includes code examples showing how to use Cubano (`query.metrics(Sales.revenue).filter(...).fetch()`). After API refactoring, the example syntax no longer works, but docs aren't updated. Users copy-paste broken examples, file issues.

**Why it happens:**
- Examples are written as markdown snippets, decoupled from actual code
- API changes (e.g., `.metrics()` renamed to `.select_metrics()`, parameter renamed) don't trigger doc updates
- No automated test of code examples (Sphinx `.doctest` not enabled, or skipped)
- Documentation lives in `/docs` directory, code lives in `/src`, no mechanism to keep them in sync
- Doc build pipeline doesn't validate that example imports work (`from cubano import ...` fails silently)

**Consequences:**
- Users copy broken examples, get import/syntax errors, spend hours debugging
- Support time wasted on "this doesn't work" issues that are actually broken docs
- Users lose trust ("docs are lies")
- New contributors copy broken examples into their code
- Documentation drifts so far that it becomes useless (users rely on source code reading instead)

**Prevention:**
- **Executable code blocks in docs**: Use Sphinx `pytest.ext.doctest` or `sphinx-gallery` to compile and execute code examples as part of doc build
  ```rst
  .. doctest::
     >>> from cubano import SemanticView
     >>> class Sales(SemanticView):
     ...     pass
     >>> Sales.query().metrics(Sales.revenue).fetch()  # doctest: +SKIP (if needs warehouse)
  ```
- **Separate fixture examples from docstrings**: Examples that need fixtures go in `.py` test files (which are always run), not markdown
- **Real imports in examples**: Never show pseudocode like `from cubano import ...` without verifying import works
- **Docstring examples in source code**: Put examples in docstrings of methods, let Sphinx autodoc extract them
  ```python
  def filter(self, **kwargs):
      """
      Filter results by dimension values.

      Example:
          >>> query = Sales.query()
          >>> query.filter(country="US").fetch()  # doctest: +SKIP
      """
  ```
- **Generate docs from generated code**: If using codegen, doc generation must re-run after codegen to show correct API
- **Doc validation in CI**: Add step that checks all code blocks parse and import correctly (even if they don't run)
- **Link docs to versions**: Show version-specific docs; warn users viewing outdated version: "You're viewing docs for v0.1, current is v0.2"
- **Change.md documents API changes**: Every breaking change must list "docs that need updates" in migration guide

**Detection:**
- Run `sphinx-build -W` with warnings as errors; if `.doctest` is enabled, broken examples fail build
- Copy example from docs into REPL — get `ImportError` or `SyntaxError`
- Release notes show "API changed" but docs still show old API
- GitHub issues with title "doesn't work" where user copied exact code from docs

**Warning signs:**
- `.doctest` extension disabled or skipped in `conf.py`
- `/docs` directory has `*.md` files with code blocks, but no test pipeline for them
- Last doc update was 3 months ago, but 5 API changes in commits since then
- Examples reference deleted/renamed methods or parameters

**Phase to address:** Phase 10 (Documentation) — Start with Phase 1, ensure at least one working example stays up-to-date. Don't defer; it's easier to keep one example working than to fix 20 broken examples later.

---

### Pitfall 24: Codegen + Docs Generation Out of Sync (Generated Models Undocumented, Or Docs Reference Wrong Fields)

**What goes wrong:** Codegen produces model classes, but Sphinx autodoc generation runs before codegen (or independently), so generated models don't appear in docs, or docs show fields from old schema version.

**Why it happens:**
- Build pipeline: `cubano codegen` runs manually on developer machine, then `make docs` builds docs from `.py` files, but docs don't re-run codegen
- CI/CD pipeline: docs build step doesn't depend on codegen step, so docs build against stale generated code
- Generated models use `@dataclass` or metaclasses that Sphinx autodoc doesn't introspect properly
- Documentation generation cache is stale (Sphinx doesn't invalidate cache when generated code changes)

**Consequences:**
- Generated models not in API reference (users think they don't exist)
- Field docstrings missing from auto-generated documentation
- Docs show fields from v1 schema, but generated code has v2 schema (mismatch confuses users)
- User manually defines model instead of using generated version
- Documentation build silently fails to include new generated module (no error, just missing)

**Prevention:**
- **Codegen as first doc-build step**: Makefile/CI must run `cubano codegen` before `sphinx-build`, ensures generated code exists
  ```makefile
  docs: codegen
    sphinx-build -b html docs build/docs
  ```
- **Document generated models explicitly**: In `.rst` source, use explicit `.. automodule::` directives for generated modules:
  ```rst
  .. automodule:: myapp._generated_models
     :members:
  ```
- **Clear Sphinx cache on codegen change**: Add touch of codegen output to `docs/conf.py` source_suffix logic, or use `sphinx-build -E` (invalidate cache) in CI
- **Version-specific docs**: Store generated models with version: `src/cubano/v0_2/generated/models.py`, docs reference versioned path
- **Schema version in generated module docstring**:
  ```python
  """
  Auto-generated models from schema version 2.1.3.
  Generated: 2026-02-17 14:30:00
  Regenerate with: cubano codegen --schema-version latest
  """
  ```
- **CI step validates doc build includes all generated models**: Grep generated code for `class.*SemanticView`, verify each appears in generated HTML docs

**Detection:**
- `sphinx-build` output shows generated models not in API reference
- Docs from published version don't match code in repo (different field names, types)
- User reports "I can't find the Sales model in docs" but it exists in source
- Regenerating code changes generated file, but docs don't update (cache issue)

**Warning signs:**
- `docs/conf.py` doesn't reference generated model locations
- Build pipeline doesn't run `cubano codegen` before `sphinx-build`
- CI logs show "2 warnings" but don't detail them (broken Sphinx autodoc)
- Generated model comments are generic ("Auto-generated") with no version info

**Phase to address:** Phase 8-10 (Codegen + Documentation overlap) — Must synchronize these two phases. If codegen is Phase 8 and docs is Phase 10, Phase 9 must ensure the dependency chain.

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

### Pitfall 25: Codegen Produces Invalid Python (Syntax Errors, Import Failures)

**What goes wrong:** Codegen produces `models.py` with syntax errors (mismatched quotes, invalid identifiers, circular imports). Generated file doesn't pass `python -m py_compile` or `import models` fails.

**Why it happens:**
- Codegen templates are brittle, escaping field names inconsistently
- Warehouse schema allows field names that are invalid in Python (e.g., field named `123abc` or `class`)
- Circular import: generated model A references model B which references model A
- Generated code has undefined type references (imports missing)

**Consequences:**
- Generated code doesn't import; entire project fails to load
- Type checking fails: mypy can't analyze generated code
- IDE can't autocomplete generated model fields
- CI fails on syntax check before tests even run

**Prevention:**
- **Validate generated code before writing**: Codegen must compile the generated `.py` file with `py_compile.compile()` before writing to disk; if compilation fails, show user the error with line numbers
- **Escape invalid identifiers**: If field name is Python keyword or invalid identifier, prefix with `_` (e.g., `class` becomes `_class`)
- **Validate field names in warehouse schema**: Before codegen, check if any field names are invalid Python identifiers; error with list of offending field names and remediation steps
- **Generate type stubs** (`.pyi` files) separately: If generated code gets too complex, generate `.pyi` type hints instead of full executable code
- **Use `__future__` annotations** for forward references to avoid circular imports:
  ```python
  from __future__ import annotations
  ```
- **Import all types at top**: Codegen must insert all required imports before class definitions
- **Test generated code in CI**: Build step must `import models` and verify no errors; don't just check syntax

**Detection:**
- `python -m py_compile src/generated_models.py` fails
- `python -c "from myapp.generated_models import Sales"` raises `ImportError` or `SyntaxError`
- mypy errors on generated file (undefined names, type issues)
- IDE shows red squiggles in generated code (Pylance detects syntax error)

**Warning signs:**
- Codegen output shown to user before validation (user commits broken code)
- No test step that imports generated code
- Field names from warehouse schema contain hyphens, spaces, or leading numbers

**Phase to address:** Phase 8 (Codegen) — CRITICAL. Must validate before generating, or broken code spreads immediately.

---

### Pitfall 26: Integration Tests Credentials Exposed in Source Control

**What goes wrong:** Integration tests need warehouse credentials (API key, username/password), but developers hardcode credentials in test files, commit to git, and credentials are exposed in git history.

**Why it happens:**
- Developer wants to "just run the test" locally without setup complexity
- No centralized secrets management tool (HashiCorp Vault, AWS Secrets Manager)
- Git pre-commit hooks not enforced; repo has no `.env` file in `.gitignore`

**Consequences:**
- Credentials exposed in git history (can't be "unburned" without rotating)
- Security breach: anyone with repo access has warehouse credentials
- CI/CD pipelines must fetch secrets from secure store, but tests hardcode them locally, creating inconsistency

**Prevention:**
- **Centralized fixture for credentials**: One `conftest.py` fixture that loads credentials from environment variables, never from source
  ```python
  @pytest.fixture(scope='session')
  def warehouse_credentials():
      return {
          'account': os.environ['SNOWFLAKE_ACCOUNT'],
          'user': os.environ['SNOWFLAKE_USER'],
          'password': os.environ['SNOWFLAKE_PASSWORD'],
      }
  ```
- **.gitignore and `.env` files**: Repository must have `.env` in `.gitignore` (example: `.env.example` shows structure without secrets)
- **Pre-commit hooks**: Use `detect-secrets` or similar to scan for credentials before commit
- **Secret rotation policy**: If credentials accidentally leaked, rotate them immediately; alert team
- **CI/CD secrets management**: Use native secrets support (GitHub Actions `secrets`, GitLab CI variables, etc.), not environment files in repo
- **Document setup**: README must explain "create `.env` file with these keys" instead of hardcoding

**Detection:**
- Search repo history: `git log -S "api_key\|password" --all` — if found, credentials were committed
- `grep -r "snowflake_password" src/` — should find 0 results (credentials only in `.env`, not source)
- Pre-commit hook blocks commit if credentials detected

**Warning signs:**
- `.env` file checked into git (should be `.gitignored`)
- Test file contains `account="xyz"` hardcoded
- CI logs show credentials in plaintext (environment variable values printed)

**Phase to address:** Phase 9 (Integration Tests) — Set up before writing first integration test. It's easier to prevent than to rotate compromised credentials later.

---

### Pitfall 27: Test Data Inconsistency Across Warehouse + Local Environments

**What goes wrong:** Integration tests are written assuming test data exists in warehouse, but test environment is misconfigured, or data was deleted by another user/job. Test data freshness is unknown; tests may be validating against stale, incorrect data.

**Why it happens:**
- Tests assume test tables are populated and stable, but setup is manual or automated without validation
- Multiple developers share test warehouse schema; one person's cleanup deletes another's test data
- No test data version tracking (tests written for "today's data" but data is from last week)
- Test assumes schema version X, but warehouse has schema version Y

**Consequences:**
- Intermittent test failures (data exists Monday, deleted Tuesday)
- Tests fail in CI/CD but pass locally (different data state)
- Debugging takes hours: "why does this test fail in CI but pass on my machine?"
- Test results are unreliable; team loses confidence in test suite

**Prevention:**
- **Test data fixtures (not shared state)**: Each test creates its own data, doesn't rely on pre-existing data
  ```python
  @pytest.fixture
  def sales_data(warehouse_engine):
      # INSERT test rows, return created data
      yield warehouse_engine.insert_test_data('sales', [{'country': 'US', 'revenue': 100}])
      # Cleanup: DELETE inserted rows
  ```
- **Data freshness validation**: Before running tests, validate test data is present and matches expected schema version
  ```python
  def validate_test_environment():
      schema_version = warehouse.get_schema_version('TEST_SCHEMA')
      assert schema_version == EXPECTED_VERSION, f"Schema mismatch: {schema_version} != {EXPECTED_VERSION}"
  ```
- **Isolated test schemas**: Each test suite (or each developer) gets its own schema: `TEST_<USERNAME>_<UUID>`, not shared `TEST_SCHEMA`
- **Data versioning**: Include `GENERATED_AT` and `SCHEMA_VERSION` metadata in test data, validate at test start
- **Documentation**: Clearly document how test data is created and maintained
- **Cleanup verification**: Don't just `DROP TABLE`; verify table was actually deleted before next test runs

**Detection:**
- Same test passes 1/5 times in CI (flakiness due to data race)
- Local test passes, CI test fails (data mismatch between local and CI warehouse)
- Test assumes field `revenue_usd` exists, but warehouse has `revenue` (schema drift)

**Warning signs:**
- Tests query `TEST.PUBLIC.SALES` (shared table, not isolated)
- No test data setup in conftest; tests just query existing tables
- No schema validation before tests run
- Test teardown is commented out or missing

**Phase to address:** Phase 9 (Integration Tests) — Set up test data isolation before writing test suite. It's foundational to reliability.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcode field names in generated code instead of iterating over schema | Fast codegen, clear output | Can't change field names after generation, manual regeneration required | Never — this locks users into manual maintenance |
| Skip documentation of generated models | Faster to ship codegen feature | Users can't find generated models in docs, support burden | Never — doc generation must be part of codegen |
| Run integration tests against production warehouse instead of test warehouse | Avoids test data setup, immediate verification | Production data contamination risk, actual costs incurred, unreliable tests | Never — always use isolated test environment |
| Cache generated code in CI and skip regenerating | Faster CI pipeline | Missed schema changes, stale generated code ships to users | Never — regenerate every build to ensure freshness |
| Hand-edit generated models instead of regenerating after schema change | Preserves custom logic | Drift between generated and source, circular edit loop | Only if using `--mode merge` and merge is validated |
| Skip doctest validation of examples in docs | Faster doc builds | Broken examples ship, users copy-paste broken code | Never — doctest is non-negotiable quality gate |
| Reuse test data across test runs instead of cleanup/reset | Fewer warehouse queries, faster tests | Test pollution, flaky failures, hidden dependencies between tests | Only in single-threaded, sequential test execution with explicit documentation |
| Store warehouse credentials in environment.yml or .env checked into git | No external secret store setup | Credentials leaked in git history, security breach | Never — use `.env` in `.gitignore`, load from CI secrets |
| Skip schema validation in tests (tests just assume schema is correct) | Fewer schema queries at test start | Tests pass but queries fail in production with schema drift | Never — validate schema matches expectations before tests run |

---

## Integration Gotchas

Common mistakes when connecting to external services (codegen, integration tests, docs generation, warehouse integrations).

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **Codegen + Warehouse** | Read schema once at codegen time, assume it never changes | Version-lock schema in generated code; validate schema at runtime on first query; include schema version hash in generated file |
| **Integration Tests + Warehouse Credentials** | Hardcode credentials in test files or environment | Load from `os.environ` or centralized config; never commit `.env` file; use CI secrets management |
| **Integration Tests + Shared Test Data** | Multiple tests modify same test tables, causing race conditions | Each test creates isolated data in separate schema; cleanup guaranteed via fixture teardown |
| **Codegen + Type Checking** | Generated code references undefined types (missing imports) | Validate generated code with `mypy` before writing to disk; include all imports at module top |
| **Docs + Code Changes** | Update code but forget to update docs; ship docs with broken examples | Use Sphinx doctest to compile and execute examples as part of doc build; fail doc build if examples don't run |
| **Codegen + Version Control** | Regenerate code, git shows massive diffs even though schema unchanged | Generate with consistent field ordering and formatting; include generation metadata in comment so git diffs are minimal |
| **Generated Models + Custom Methods** | Regenerate code and lose custom methods users added | Use separate files: `_generated.py` + `models.py` (user extends generated classes); or use `--mode merge` to preserve custom code |
| **Integration Tests + Parallel Execution** | Tests pass sequentially, fail when run in parallel | Use `pytest-xdist` with isolated test schemas (e.g., `test_schema_{worker_id}`); never share test tables |
| **Docs Generation + Generated Code** | Generate models, then build docs, but docs don't include generated models | Docs build must depend on codegen task; Sphinx must run after codegen completes; verify generated models appear in final docs |
| **Integration Tests + Flakiness Detection** | Flaky tests hidden in noisy log output; same test fails sometimes, passes others | Track flaky test passes/failures over time (`pytest-rerunfailures`, `allure`); quarantine flaky tests; investigate root cause (data, timing, env) |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **Integration test suite with no parallelization** | 1000 tests × 5 seconds each = 1.4 hours test time | Use `pytest-xdist` with isolated test schemas; tests run in parallel, same results | >100 tests (becomes unacceptable to run every commit) |
| **Codegen reads entire schema on each run** | Codegen takes 30+ seconds even for tiny schema changes | Cache schema introspection; only re-read if schema version changed; delta-generate only changed fields | Schema with 100+ tables or 1000+ columns |
| **Generated code includes all fields even if not used** | Generated models 10+ MB, mypy type-checking takes 30+ seconds | Optional: selective code generation; users specify which fields/models to generate | Very large semantic views (100+ fields) |
| **Test fixture creates full warehouse environment per test** | Each test spends 5 seconds setting up, 0.5 seconds running | Use session-scoped fixtures for shared setup; test-scoped fixtures only for test-specific data | >1000 tests (setup time dominates) |
| **Integration tests query real data instead of test data** | Warehouse costs scale with test count; $500/month for test queries | Isolate test data; use cheaper query patterns (COUNT instead of full SELECT) | >10k tests or high test frequency (CI on every commit) |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| **Codegen produces models with SQLi-vulnerable field names** | SQL injection if field names from user input influence model definition | Validate field names against strict regex; never allow user input to shape field names; quote all identifiers in generated SQL |
| **Warehouse credentials in test files** | Credentials leaked in git history, unauthorized warehouse access | Load from environment; use `.env` in `.gitignore`; rotate credentials immediately if leaked |
| **Generated code exposes internal schema structure** | Users reverse-engineer semantic view schema, bypass access controls | Generated models only expose intended public fields; include comments about access restrictions; consider obfuscating field mappings |
| **Integration tests run with elevated privileges** | Overly permissive test credentials allow tests to delete/modify production data | Test credentials should have minimal permissions (SELECT only, specific test schemas); separate test and prod credentials |
| **Codegen doesn't validate warehouse response** | Malicious warehouse (or MITM attack) could inject SQL or code into generated models | Validate schema response structure; sign/checksum generated code; use TLS for warehouse connection |
| **Test data contains sensitive information** | Test warehouse data accidentally exposed in logs, backups, or shared environments | Test data should be synthetic, never real PII; scrub any real data before using in test warehouse; encrypt test warehouse if possible |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| **Vague codegen error messages** | "Code generation failed" with no details | "Error reading Snowflake schema: column 'INVALID_COLUMN' has no type annotation. Check warehouse for schema errors." |
| **Generated model field names don't match warehouse** | User selects field in warehouse UI, can't find it in generated model (`revenue` in UI, `REVENUE` in model) | Preserve case from warehouse; if case mismatch, show mapping in docs or error message |
| **Docs show examples with deleted API** | User tries API from docs, gets error, assumes docs are authoritative | Keep examples in docstrings and validate with doctest; fail docs build if examples break |
| **No migration guide for schema changes** | User regenerates code, gets field name changes, breaks existing code | Generated file includes compatibility notes; docs include "if you see field X was renamed to Y, here's how to update your code" |
| **Codegen creates unsearchable field names** | Generated field name is `_field_1` instead of `revenue`, user can't find it | If warehouse field name is invalid Python, suggest rename in error; don't auto-rename without user acknowledgment |
| **Integration test failures show cryptic warehouse errors** | "ERROR: INVALID_COLUMN_SPECIFICATION at line 5" (user doesn't know what line 5 is) | Query object should include line number; error message should show generated SQL with line numbers; suggest "run `query.to_sql()` to see generated code" |
| **No documentation of test environment setup** | User writes tests, can't get them to pass locally (wrong warehouse, missing credentials, schema mismatch) | README must include "Set up for testing: 1) Create `.env`, 2) Run `make test-env-setup`, 3) `pytest`" |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Codegen feature:** Generates models ✓, but doesn't validate generated code compiles or imports work — verify with `python -m py_compile` and `import models` in CI
- [ ] **Codegen feature:** Generates models ✓, but docs don't include generated models — verify all generated models appear in Sphinx autodoc output
- [ ] **Codegen feature:** Generates models ✓, but no strategy for regenerating without losing user customizations — verify `--mode merge` exists and merges correctly
- [ ] **Codegen feature:** Generates models ✓, but no test showing round-trip (schema → codegen → query → warehouse) — add integration test
- [ ] **Integration tests:** Tests run and pass ✓, but no isolation (share test data) — verify with `pytest -n auto` (parallel execution) that tests still pass
- [ ] **Integration tests:** Tests run ✓, but credentials hardcoded — audit test files for `api_key=`, `password=`, search git history with `git log -S "password"`
- [ ] **Integration tests:** Tests run ✓, but no fixtures for cleanup — verify teardown removes all created data, or test run two times in sequence without errors
- [ ] **Documentation:** Docs build and render ✓, but examples don't work — run `sphinx-build -W` with doctest enabled; all examples must execute without errors
- [ ] **Documentation:** Docs reference API ✓, but don't mention codegen — verify docs include "Generated models" section with examples of generated model usage
- [ ] **Documentation:** Docs reference generated models ✓, but generated code doesn't exist yet (placeholder text) — verify generated models actually appear in rendered HTML docs, not as stubs

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Generated code diverged from model source (Pitfall 21) | HIGH (manual merge of changes) | 1) Save user's custom code to separate file, 2) Regenerate all code fresh, 3) Manually reapply custom code, 4) Test thoroughly. Prevent: use `--mode merge` next time |
| Integration tests flaky due to shared data (Pitfall 22) | MEDIUM (rewrite test fixtures) | 1) Identify flaky test (run 10x), 2) Add isolated test data fixture, 3) Rewrite test to use fixture, 4) Verify passes 10x in parallel. Prevent: data isolation from start |
| Documentation examples broken (Pitfall 23) | LOW-MEDIUM (update examples) | 1) Identify broken examples with doctest, 2) Update docstrings/markdown, 3) Run doctest to verify, 4) Rebuild docs. Prevent: enable doctest in build pipeline |
| Codegen + docs out of sync (Pitfall 24) | LOW (re-run codegen + docs) | 1) Run `cubano codegen`, 2) Run `make docs`, 3) Verify generated models appear in docs. Prevent: make docs depend on codegen |
| Generated code syntax errors (Pitfall 25) | MEDIUM-HIGH (debug template, regenerate) | 1) Find invalid syntax in generated file, 2) Identify field causing error (e.g., field name is keyword), 3) Fix codegen template, 4) Regenerate, 5) Retry. Prevent: validate generated code before writing |
| Credentials leaked in git (Pitfall 26) | HIGH (rotate credentials) | 1) Identify leaked credential, 2) Rotate in warehouse (change password/key), 3) Audit logs for misuse, 4) Rewrite git history or accept compromise. Prevent: never commit credentials |
| Test data inconsistent across environments (Pitfall 27) | MEDIUM (recreate test environment) | 1) Validate test schema matches expected version, 2) Clear test data, 3) Re-populate from fixtures, 4) Verify tests pass. Prevent: use isolated schemas + fixtures |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Pitfall 1: Metaclass mutable defaults | Phase 1 (Model System) | Instantiate multiple models, verify field isolation with `dir(Model)` and `id(field._default)` |
| Pitfall 2: Immutable query builder mutation | Phase 2 (Query Builder) | Branch queries, modify one, verify other unchanged (test with `id()` checks) |
| Pitfall 3: SQL injection via field names | Phase 3 (SQL Generation) | Test with field name `"revenue; DROP"`, verify quoted in generated SQL |
| Pitfall 4: Lazy registry resolution stale state | Phase 4 (Engine Registry) | Register, build query, unregister, fetch — should fail with clear error |
| Pitfall 5: GROUP BY with window functions | Phase 3 (SQL Generation) | Test semantic view with window-function dimension, verify not in GROUP BY |
| Pitfall 6: Backend-specific syntax hardcoded | Phase 3 (SQL Generation) + Phase 5 (Engines) | Generate same query with MockEngine(dialect='snowflake') and SnowflakeEngine, compare SQL |
| Pitfall 7: Row class attribute conflicts | Phase 6 (Result Handling) | Create Row with field named `keys`, verify `row.keys()` works as method |
| Pitfall 8: Q-object field reference staleness | Phase 2 (Query Builder) | Create Q-object, reload model, apply to query — should fail with clear error or auto-resolve |
| Pitfall 21: Generated code diverges (codegen drift) | Phase 8 (Codegen) | Regenerate code twice, diff output — should be identical; validate schema version in generated file |
| Pitfall 22: Integration tests flaky/shared state | Phase 9 (Integration Tests) | Run tests in parallel (`pytest -n auto`), verify pass rate >99%; check warehouse cost stays constant |
| Pitfall 23: Documentation examples stale | Phase 10 (Documentation) | Enable Sphinx doctest, build docs, fail if any example breaks; verify examples in each doc version match API |
| Pitfall 24: Codegen + docs out of sync | Phase 8-10 (Codegen + Docs) | Build docs after codegen; verify generated models appear in HTML output; CI step validates this |
| Pitfall 25: Generated code syntax errors | Phase 8 (Codegen) | Validate generated code with `py_compile` before writing; `import models` in test; mypy type check succeeds |
| Pitfall 26: Credentials in source control | Phase 9 (Integration Tests) | `git log -S "password"` finds nothing; test files have no hardcoded credentials; CI uses secrets management |
| Pitfall 27: Test data inconsistency | Phase 9 (Integration Tests) | Validate test schema version at test start; create isolated test schemas; run tests 10x in parallel, verify consistent results |

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

## v0.2 Specific Warnings: Codegen, Integration Tests, Documentation

### Codegen Concerns
- **Schema versioning**: Track source schema version in generated code; validate at runtime
- **Field name mapping**: Preserve warehouse field names exactly; document any transformations
- **Import errors**: Validate generated code before shipping; include all imports
- **User customization**: Support merging custom methods with regenerated code, or separate user code from generated code
- **Circular dependencies**: Generated models may reference each other; use `from __future__ import annotations` to avoid import cycles

### Integration Test Concerns
- **Warehouse access**: Credentials must be centralized, never hardcoded in test files
- **Data isolation**: Each test should use isolated schema/tables; parallel execution should not cause interference
- **Cost monitoring**: Track test warehouse spend; alert if spike (missing cleanup or inefficient fixtures)
- **Flakiness**: Same test should pass consistently (not 8/10 times); investigate and fix flaky tests before shipping

### Documentation Concerns
- **Example freshness**: Examples must be tested (doctest) as part of docs build; fail build if examples break
- **Generated model docs**: Codegen must run before docs build; generated models must appear in API reference
- **Version-specific docs**: Old versions of docs should be available; warn users viewing outdated docs
- **Migration guides**: Each breaking API change must include doc showing how to update code

---

## Sources

**Overall Confidence: MEDIUM-HIGH**

**Existing pitfalls (Pitfalls 1-20):** HIGH confidence from prior research (training knowledge of ORM patterns, project context).

**New v0.2 pitfalls (Pitfalls 21-27) and integration concerns:** MEDIUM confidence from 2026 web research sources:

- [Modern Data Warehouse Testing Strategy Guide for 2026](https://blog.qasource.com/how-to-build-an-end-to-end-data-warehouse-testing-strategy)
- [Flaky Tests in 2026: Key Causes, Fixes, and Prevention](https://www.accelq.com/blog/flaky-tests/)
- [How to Automate API Documentation Updates with GitHub Actions and OpenAPI Specifications](https://www.freecodecamp.org/news/how-to-automate-api-documentation-updates-with-github-actions-and-openapi-specifications/)
- [Automatically Keep Your API Documentation in Sync with DeepDocs AI](https://techifysolutions.com/blog/api-documentation-with-deepdocs-ai/)
- [How AI generated code compounds technical debt - LeadDev](https://leaddev.com/technical-direction/how-ai-generated-code-accelerates-technical-debt)
- [The Hidden Costs of Flaky Tests: A Deep Dive into Test Reliability](https://www.stickyminds.com/article/hidden-costs-flaky-tests-deep-dive-test-reliability-0)
- [Avoid integration testing against shared environments](https://medium.com/@ievgen.degtiarenko/avoid-integration-testing-against-shared-environments-5b04de9d933c)
- [GitHub - agronholm/sqlacodegen](https://github.com/agronholm/sqlacodegen) (SQLAlchemy code generation patterns)
- [What is Schema Drift? The Ultimate Guide](https://litedatum.com/what-is-schema-drift)
- [pytest fixtures documentation](https://docs.pytest.org/en/stable/how-to/fixtures.html)
- [pytest-postgresql · PyPI](https://pypi.org/project/pytest-postgresql/)
- [Sphinx autodoc extension documentation](https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html)

**Limitations:**
- Unable to access Snowflake/Databricks 2026-specific semantic view documentation; recommendations based on 2025 knowledge
- Codegen pitfalls drawn from general SQLAlchemy/datamodel-codegen patterns, not Cubano-specific testing
- Some recommendations (e.g., "use testcontainers") are industry best practices but not yet validated in Cubano context
- Integration test cost monitoring assumes cloud warehouse provider cost APIs available

**Recommended validation:**
- Test codegen pitfalls (21-27) against actual Snowflake/Databricks semantic views
- Measure integration test costs and flakiness in real CI/CD pipeline
- Validate docs build pipeline with actual generated models
- Benchmark schema introspection performance at scale (100+ models)

---

*Pitfalls research for: Python ORM for Data Warehouse Semantic Layers (Cubano v0.2)*
*Researched: 2026-02-17*
