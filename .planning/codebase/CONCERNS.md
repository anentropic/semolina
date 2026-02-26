# Codebase Concerns

**Analysis Date:** 2026-02-17

## Tech Debt

**WHERE clause is a permanent placeholder:**
- Issue: `SQLBuilder._build_where_clause()` returns `"WHERE 1=1"` unconditionally — filters stored in `Q` objects never reach generated SQL, making `.filter()` a no-op in real queries
- Files: `src/cubano/engines/sql.py` (lines 418–438)
- Impact: Queries with `.filter()` conditions silently produce incorrect SQL; filters are built and stored correctly in the `Query` object but are never translated to SQL. The comment says "implemented in Phase 4" but there is no Phase 4 code
- Fix approach: Implement a Q-to-SQL compiler that walks the `Q` tree and emits `field op value` fragments using the dialect's quote_identifier method; replace the placeholder return

**MockEngine.execute() ignores query fields and filter conditions:**
- Issue: `MockEngine.execute()` only extracts the view name and returns all fixture rows regardless of selected fields, applied filters, ordering, or limits
- Files: `src/cubano/engines/mock.py` (lines 110–148)
- Impact: Tests using MockEngine do not exercise filter, order_by, or limit logic; bugs in SQL generation for these clauses are only detectable via `to_sql()` string inspection — not via end-to-end result verification
- Fix approach: Apply filter/ordering/limit to fixture rows so mock execution matches expected query semantics

**Databricks codegen template hardcodes SUM() aggregation:**
- Issue: The Databricks metric template emits `expr: SUM({{ m.name }})  # TODO: Replace SUM with correct aggregation` — all metrics become SUM regardless of intended aggregation
- Files: `src/cubano/codegen/templates/databricks.yaml.jinja2` (line 29)
- Impact: Generated Databricks YAML is always incomplete and requires manual editing before use; defeats automation purpose
- Fix approach: Add an optional `aggregation` attribute to the `Metric` field (e.g., `Metric(agg="AVG")`) and pass it through `FieldData` to the template

**Snowflake codegen template emits placeholder TABLES/RELATIONSHIPS stubs:**
- Issue: Generated Snowflake DDL always contains `-- TODO: Add TABLES (...)` and `-- TODO: Add RELATIONSHIPS (...)` comments
- Files: `src/cubano/codegen/templates/snowflake.sql.jinja2` (lines 7–8)
- Impact: All generated Snowflake SQL is invalid and requires manual editing; the table binding information does not exist anywhere in the model definition, so the generator cannot populate it
- Fix approach: Add optional `table` and `relationships` parameters to `SemanticView` definition; propagate via `ModelData`; render when present, omit stubs when absent

**`engines/__init__.py` eagerly imports real backend classes:**
- Issue: `from .databricks import DatabricksEngine` and `from .snowflake import SnowflakeEngine` at module import time. The actual connector (`databricks.sql`, `snowflake.connector`) is lazily guarded inside each class's `__init__`, but the class file itself is always imported
- Files: `src/cubano/engines/__init__.py`
- Impact: Low risk today (connectors not imported at module level), but any future top-level import added to `databricks.py` or `snowflake.py` would break for users without those extras. Also, `from cubano.engines import MockEngine` pulls in all engine files unnecessarily
- Fix approach: Make `SnowflakeEngine` and `DatabricksEngine` imports lazy inside `__init__.py` using `__getattr__`

**`pydantic` and `pydantic-settings` are dev-only but imported in installable `testing/` subpackage:**
- Issue: `src/cubano/testing/credentials.py` imports `pydantic` and `pydantic_settings` at the top level. These packages are listed only in `[dependency-groups] dev` in `pyproject.toml`, not in `[project.dependencies]`
- Files: `src/cubano/testing/credentials.py` (lines 17–18), `pyproject.toml` (lines 38–48)
- Impact: `from cubano.testing.credentials import SnowflakeCredentials` fails at runtime for any consumer who installed cubano without the dev dependency group. If the testing subpackage is intended to be user-facing, pydantic and pydantic-settings need to be proper optional dependencies
- Fix approach: Either add `pydantic>=2.0` and `pydantic-settings>=2.7` as a `[project.optional-dependencies] testing` extra, or ensure `cubano.testing` is excluded from the built wheel

**`make_stderr_console` ignores its `verbose` parameter:**
- Issue: `make_stderr_console(verbose=False)` creates an identical Console to `make_stderr_console(verbose=True)` — the parameter is accepted but never used
- Files: `src/cubano/cli/utils.py` (lines 17–28)
- Impact: `--verbose` flag has no effect on console output filtering; the parameter API is misleading
- Fix approach: Use `quiet=not verbose` or similar Console setting, or remove the parameter if verbosity control is handled at the caller

## Known Bugs

**`Q.__repr__` uses `# type: ignore[assignment]` to bypass an unsound union narrowing:**
- Symptoms: `Q.children` is typed `list[tuple[str, Any] | Q]`; repr checks `isinstance(children[0], tuple)` then casts the whole list, which is unsafe if children contains mixed types
- Files: `src/cubano/filters.py` (lines 101–116)
- Trigger: Calling `repr()` on a compound Q object where children contains a mix of tuples and Q objects (not currently possible via the public API, but possible if `_combine` is used with unusual inputs)
- Workaround: The public API never produces mixed-children nodes, so it cannot be triggered in practice today

**Cross-model queries silently use the first field's view name:**
- Symptoms: A query with `metrics(ModelA.revenue)` and `dimensions(ModelB.country)` silently generates `FROM model_a_view` — ModelB's view is ignored without error
- Files: `src/cubano/engines/sql.py` (lines 386–416, `_build_from_clause`)
- Trigger: Building a query mixing fields from two different `SemanticView` subclasses
- Workaround: None; no validation exists to catch this. This produces semantically incorrect SQL without any error

## Security Considerations

**No parameter binding — SQL identifiers are interpolated directly:**
- Risk: Field names and view names are injected into SQL via string formatting without parameterised queries. An attacker who can control a field name or view name string at runtime could inject SQL
- Files: `src/cubano/engines/sql.py` (all `_build_*` methods), `src/cubano/engines/snowflake.py`, `src/cubano/engines/databricks.py`
- Current mitigation: All field names come from Python class attributes validated by `Field.__set_name__` (which checks `isidentifier()`) and view names come from `SemanticView` class definitions, not user input. The injection surface is limited to trusted developer-controlled code
- Recommendations: Document that field names and view names must be developer-controlled. Add explicit validation that field names are valid SQL identifiers before interpolation

**Bare `except Exception` swallows all errors in credential loading:**
- Risk: Credential loading in `SnowflakeCredentials.load()` and `DatabricksCredentials.load()` catches all exceptions silently, including bugs (e.g., `AttributeError`, `TypeError`) that should propagate
- Files: `src/cubano/testing/credentials.py` (lines 94–95, 111–112, 182–183, 199–200)
- Current mitigation: The swallowed exception merely causes fallback to the next credential source, with a final `CredentialError` raised if all sources fail
- Recommendations: Narrow to `pydantic_settings.ValidationError` or `ValueError` only

## Performance Bottlenecks

**New Snowflake/Databricks connection per execute() call:**
- Problem: Each `engine.execute()` call opens a new TCP connection to the warehouse, executes the query, and closes the connection. No connection pooling
- Files: `src/cubano/engines/snowflake.py` (lines 196–212), `src/cubano/engines/databricks.py` (lines 195–212)
- Cause: Design choice; docstring says "No connection pooling (connections handled by Snowflake internally)". Snowflake does have connection pooling in its connector, but it is not used
- Improvement path: Accept an optional `connection_pool_size` parameter or allow passing a pre-existing connection object; alternatively, use connection context reuse across multiple queries in the same session

**`Jinja2 Environment` is recreated per `render_view()` call:**
- Problem: `render_view()` calls `_make_environment()` which constructs a fresh `Environment` and `FileSystemLoader` on every render
- Files: `src/cubano/codegen/renderer.py` (lines 27–76)
- Cause: No caching of the Jinja2 environment at module level
- Improvement path: Move `_make_environment()` result to a module-level constant or use `functools.lru_cache()`

## Fragile Areas

**`_build_from_clause` uses `assert` to guard against None view names:**
- Files: `src/cubano/engines/sql.py` (lines 386–416)
- Why fragile: Six `assert` statements guard runtime conditions (`metric.name is not None`, `owner is not None`, `view_name is not None`). These become no-ops under `python -O` (optimised mode) and produce unhelpful `AssertionError` instead of descriptive errors
- Safe modification: Replace with explicit `if ... is None: raise ValueError(...)` checks
- Test coverage: Covered implicitly by SQL generation tests but no explicit tests for the None field name / None owner cases

**`SemanticViewMeta` freezing is only enforced by `_frozen` flag, not by Python's type system:**
- Files: `src/cubano/models.py` (lines 14–87)
- Why fragile: The immutability guarantee depends on `getattr(cls, "_frozen", False)` — any code that bypasses `SemanticViewMeta.__setattr__` (e.g., calling `type.__setattr__` directly) can mutate model metadata silently
- Safe modification: Avoid using `type.__setattr__` directly on SemanticView subclasses

**`load_module_from_path` uses a path-derived string as module name:**
- Files: `src/cubano/codegen/loader.py` (lines 40–78)
- Why fragile: Module name is derived from file path by replacing `/` with `_` — two files at paths that differ only in slashes vs underscores would collide in `sys.modules`. The `lstrip('_')` also strips leading underscores from the path-derived name, potentially causing collisions for files with leading underscore paths
- Safe modification: Append a hash of the absolute path to guarantee uniqueness
- Test coverage: No test for module name collision scenarios

**`Q.children` type mixing is an unverified invariant:**
- Files: `src/cubano/filters.py` (lines 54–116)
- Why fragile: The type `list[tuple[str, Any] | Q]` does not distinguish leaf nodes (all-tuple children) from branch nodes (all-Q children). The `__repr__` and SQL compilation logic must infer node type from the first element. Any deviation from the "always all-tuples or always all-Qs" invariant would silently produce wrong output
- Safe modification: Use a tagged union or separate `LeafQ` and `BranchQ` classes instead of a shared mutable `children` list

## Scaling Limits

**`MockEngine._fixtures` dict grows unboundedly:**
- Current capacity: No limit
- Limit: Holds all fixture rows in memory; large fixture datasets in tests would consume heap
- Scaling path: Not a production concern (MockEngine is test-only), but large integration test fixtures should be generated lazily

**`SQLBuilder` has no query complexity limits:**
- Current capacity: No restriction on number of metrics, dimensions, or order-by fields
- Limit: Extremely wide queries (thousands of columns) would produce very long SQL strings. Neither Snowflake nor Databricks impose strict column count limits, but network payload size and server-side query plan compilation overhead apply
- Scaling path: Add optional validation or warnings for very large field counts

## Dependencies at Risk

**`pydantic-settings` is a runtime requirement for `cubano.testing` but declared only in dev group:**
- Risk: Version mismatch or removal from dev group would silently break integration test infrastructure for users not running `uv sync --all-groups`
- Impact: `SnowflakeCredentials.load()` and `DatabricksCredentials.load()` would raise `ImportError`
- Migration plan: Add as proper optional extra or document the requirement explicitly in testing docs

**`typer`, `rich`, and `jinja2` are runtime dependencies for all cubano users:**
- Risk: These three packages are listed in `[project.dependencies]`, making them required for all users even those who only use the Python query API and never touch the CLI or codegen
- Impact: Unnecessary transitive dependencies for library consumers who only need `SemanticView`, `Query`, and engine classes
- Migration plan: Move `typer`, `rich`, and `jinja2` to a `[project.optional-dependencies] cli` extra; import them lazily or guard behind `try/except ImportError`

## Missing Critical Features

**No validation that query fields belong to the same SemanticView:**
- Problem: `Query.metrics(ModelA.revenue).dimensions(ModelB.country)` is accepted silently and generates SQL referencing only `ModelA`'s view. There is no cross-model consistency check
- Blocks: Correct multi-model query handling; meaningful error messages for developer mistakes
- Priority: High — silent semantic incorrectness

**No aggregation function specification on Metric fields:**
- Problem: `Metric()` has no way to specify the aggregation (SUM, AVG, COUNT, etc.). The Snowflake codegen template assumes `AGG()` (which is correct for Snowflake semantic views), but the Databricks template defaults to `SUM()` as a placeholder
- Blocks: Correct Databricks codegen; any future backends with explicit aggregation syntax

**`Q`-object filters are never executed — not by MockEngine, not by real engines:**
- Problem: `.filter(Q(...))` stores the condition correctly but neither `MockEngine.execute()` nor `SQLBuilder._build_where_clause()` uses it
- Blocks: Any filtering behaviour; testing filter logic end-to-end

## Test Coverage Gaps

**`_build_where_clause` has no unit tests:**
- What's not tested: The WHERE clause builder is tested indirectly only by checking that `"WHERE 1=1"` appears when filters are applied. No test validates that a real filter condition would produce correct SQL because that functionality does not exist yet
- Files: `src/cubano/engines/sql.py` (lines 418–438), `tests/test_sql.py`
- Risk: If a real implementation is added, existing tests will not catch regressions in filter SQL structure
- Priority: High

**Cross-view query validation has no tests:**
- What's not tested: Mixing fields from two different SemanticView subclasses in one query
- Files: `src/cubano/engines/sql.py` (`_build_from_clause`), `tests/test_sql.py`
- Risk: Silent semantic errors undetected
- Priority: High

**`engines/__init__.py` eager import path is not tested for ImportError protection:**
- What's not tested: Whether importing `cubano.engines` raises `ImportError` when optional connectors are absent
- Files: `src/cubano/engines/__init__.py`, `tests/test_engines.py`
- Risk: A change to engine module top-level imports could break users without extras installed
- Priority: Medium

**Codegen with models that have no facts, no dimensions, or no metrics:**
- What's not tested: Models with only metrics (no dimensions/facts) or only dimensions (no metrics) through the full codegen pipeline
- Files: `src/cubano/codegen/generator.py`, `tests/codegen/test_generator.py`
- Risk: Template rendering may produce empty or malformed sections
- Priority: Medium

**`make_stderr_console` verbose flag is not tested:**
- What's not tested: Whether verbose mode changes console output behaviour
- Files: `src/cubano/cli/utils.py`, `tests/codegen/test_utils.py`
- Risk: Parameter is accepted but unused; no test would catch if the flag was accidentally wired to something that breaks output
- Priority: Low

---

*Concerns audit: 2026-02-17*
