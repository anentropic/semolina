# Architecture

**Analysis Date:** 2026-02-17

## Pattern Overview

**Overall:** Pythonic ORM over warehouse semantic views, with a layered Model/Query/Engine design

**Key Characteristics:**
- Immutability enforced throughout: frozen dataclasses, metaclass-locked models, immutable `Row` results
- Zero side effects during query construction — all mutation returns new instances via `dataclasses.replace()`
- Backend-agnostic query building; SQL dialect is injected at engine level, not at query level
- Lazy engine resolution — `.using('name')` stores a string; the engine is looked up at `.fetch()` time
- Zero runtime dependencies for core ORM; warehouse connectors are optional extras (`[snowflake]`, `[databricks]`)

## Layers

**Model Layer:**
- Purpose: Define semantic view schemas as typed Python classes
- Location: `src/cubano/models.py`, `src/cubano/fields.py`
- Contains: `SemanticView` base class, `Field` descriptors (`Metric`, `Dimension`, `Fact`), `OrderTerm`
- Depends on: Nothing (pure Python stdlib)
- Used by: Query layer (fields passed as arguments), codegen loader

**Query Layer:**
- Purpose: Build immutable query objects via fluent API
- Location: `src/cubano/query.py`, `src/cubano/filters.py`
- Contains: `Query` dataclass (frozen), `Q` filter composition object
- Depends on: Model layer (validates field types at `.metrics()` / `.dimensions()` call time)
- Used by: Engine layer (receives `Query` for SQL generation and execution)

**Engine Layer:**
- Purpose: SQL generation and query execution against backends
- Location: `src/cubano/engines/`
- Contains: `Engine` ABC, `SQLBuilder`, `Dialect` ABC, concrete engines and dialects
- Depends on: Query layer (reads `Query._metrics`, `_dimensions`, etc.), optional warehouse drivers
- Used by: Registry (stored by name), `Query.fetch()` (via registry lookup)

**Registry:**
- Purpose: Named engine store for lazy resolution
- Location: `src/cubano/registry.py`
- Contains: Module-level `_engines: dict[str, Any]` dict; `register()`, `get_engine()`, `unregister()`, `reset()`
- Depends on: Nothing
- Used by: `Query.fetch()` to resolve engine by name at execution time

**Results Layer:**
- Purpose: Wrap raw query results in a typed, immutable access object
- Location: `src/cubano/results.py`
- Contains: `Row` — immutable, supports both `row.field` and `row['field']` access, full dict protocol
- Depends on: Nothing
- Used by: `Query.fetch()` (wraps each dict from `engine.execute()` in a `Row`)

**Codegen Subsystem:**
- Purpose: CLI tool to generate warehouse DDL from Python model files
- Location: `src/cubano/codegen/`, `src/cubano/cli/`
- Contains: loader (dynamic import + introspection), renderer (Jinja2), generator (orchestrator), validator (error collection)
- Depends on: Model layer (introspects `SemanticView` subclasses), Jinja2 (runtime dep)
- Used by: `cubano codegen` CLI command only

**Testing Utilities:**
- Purpose: Credential management for integration tests
- Location: `src/cubano/testing/`
- Contains: `SnowflakeCredentials`, `DatabricksCredentials` (pydantic-settings), `CredentialError`
- Depends on: `pydantic-settings` (dev-only dependency)

## Data Flow

**Query Construction (no side effects):**

1. User defines a `SemanticView` subclass with `Metric`, `Dimension`, `Fact` fields
2. User constructs `Query()` and chains `.metrics(Model.field)`, `.dimensions(...)`, `.filter(Q(...))`, `.order_by(...)`, `.limit(n)`, `.using('engine')`
3. Each chain method calls `dataclasses.replace(self, ...)` returning a new frozen `Query` — original unchanged
4. Field type validation (Metric vs Dimension vs Fact) happens at chain-call time, not execution time

**Query Execution (`Query.fetch()`):**

1. `_validate_for_execution()` checks at least one metric or dimension is selected
2. `get_engine(self._using)` resolves engine from module-level registry dict
3. `engine.execute(query)` is called — engine generates SQL via `SQLBuilder(dialect).build_select(query)` then runs it
4. Raw `list[dict[str, Any]]` rows returned from engine
5. `Query.fetch()` wraps each dict in `Row(data)` and returns `list[Row]`

**SQL Generation (inside Engine.execute):**

1. `SQLBuilder(dialect).build_select(query)` called
2. `_build_select_clause()`: metrics wrapped via `dialect.wrap_metric(name)` (→ `AGG("x")` or `MEASURE(\`x\`)`); dimensions quoted via `dialect.quote_identifier(name)`
3. `_build_from_clause()`: view name extracted from `query._metrics[0].owner._view_name`
4. Optional clauses appended: `WHERE 1=1` (placeholder — full Q→SQL translation not yet implemented), `GROUP BY ALL`, `ORDER BY ...`, `LIMIT n`
5. Clauses joined with newlines

**Codegen Pipeline (`cubano codegen <input> --backend <backend>`):**

1. CLI resolves input spec to `list[Path]` via `resolve_input_paths()`
2. `generate_sql_for_files()` iterates files: validate syntax → `load_module_from_path()` → `extract_models_from_module()` → `render_view(model, backend)`
3. Jinja2 template (`snowflake.sql.jinja2` or `databricks.yaml.jinja2`) renders `ModelData` to SQL/YAML string
4. All rendered blocks joined with `\n\n` and written to stdout or `--output` file
5. Errors are collected across all files and reported together; any error exits with code 1

## Key Abstractions

**SemanticView (Model Definition):**
- Purpose: Declares which fields a warehouse semantic view exposes, and maps them to Python names
- Examples: `src/cubano/models.py` (base), user-defined subclasses like `class Orders(SemanticView, view='orders')`
- Pattern: `__init_subclass__` collects `Field` descriptors into `_fields: MappingProxyType`; `SemanticViewMeta` freezes the class after creation

**Field Descriptors:**
- Purpose: Class-level typed references that are passed directly into `Query.metrics()` and `Query.dimensions()`
- Examples: `src/cubano/fields.py` — `Metric`, `Dimension`, `Fact` (all subclass `Field`)
- Pattern: Descriptor protocol — `__get__` returns `self` for class access (`Sales.revenue` → `Metric` instance); raises `AttributeError` for instance access; `__set_name__` validates names at class creation time

**Query (Immutable Builder):**
- Purpose: Accumulate query parameters without mutating state; validate field types eagerly
- Examples: `src/cubano/query.py`
- Pattern: `@dataclass(frozen=True)` with `dataclasses.replace()` for every mutation method; engine resolved lazily at `.fetch()` time

**Q Filter Object:**
- Purpose: Compose filter conditions with boolean operators (`&`, `|`, `~`)
- Examples: `src/cubano/filters.py`
- Pattern: Tree structure — leaf nodes hold `list[tuple[str, Any]]` kwargs; branch nodes hold child `Q` objects with a connector (`'AND'` / `'OR'`) and optional `negated` flag

**Engine / Dialect:**
- Purpose: Separate SQL syntax rules (Dialect) from connection lifecycle (Engine)
- Examples: `src/cubano/engines/base.py`, `src/cubano/engines/sql.py`
- Pattern: `Engine` ABC defines `to_sql(query) -> str` and `execute(query) -> list[Any]`; each engine holds a `Dialect` instance and delegates SQL building to `SQLBuilder(self.dialect)`

**SQLBuilder:**
- Purpose: Compose SQL clauses from a `Query` object using a given `Dialect`
- Examples: `src/cubano/engines/sql.py` — `SQLBuilder.build_select(query)`
- Pattern: Clause-by-clause assembly (not AST); `GROUP BY ALL` used for both Snowflake and Databricks to avoid manually listing dimension columns

## Entry Points

**Library API:**
- Location: `src/cubano/__init__.py`
- Exports: `SemanticView`, `Metric`, `Dimension`, `Fact`, `Query`, `Q`, `OrderTerm`, `NullsOrdering`, `register`, `get_engine`, `unregister`, `Row`
- Usage: `import cubano` or `from cubano import SemanticView, Metric, Query`

**CLI Entry Point:**
- Location: `src/cubano/__main__.py` → `src/cubano/cli/__init__.py`
- Triggers: `python -m cubano` or `cubano` (via `[project.scripts]` in `pyproject.toml`)
- Responsibilities: Typer app with `codegen` subcommand; `--version` flag

**Codegen Command:**
- Location: `src/cubano/cli/codegen.py` — `codegen()` function
- Triggers: `cubano codegen <input> --backend snowflake|databricks`
- Responsibilities: Input resolution, delegating to `generate_sql_for_files()`, writing output to stdout or file

## Error Handling

**Strategy:** Eager validation at construction time for type errors; deferred validation at execution time for completeness

**Patterns:**
- `TypeError` raised immediately in `.metrics()`, `.dimensions()`, `.filter()`, `.order_by()`, `.using()` when wrong type passed
- `ValueError` raised at `.fetch()` / `.to_sql()` if no fields selected (not at construction — allows incremental building)
- `ValueError` raised by `registry.get_engine()` with helpful message listing available engines
- Warehouse errors (`ProgrammingError`, `DatabaseError`, `OperationalError`) are caught and re-raised as `RuntimeError` with context
- Codegen errors (`SyntaxError`, `ImportError`, generic `Exception`) are collected across all files into `list[CodegenError]` and reported together at end

## Cross-Cutting Concerns

**Logging:** None — no logging framework used anywhere; diagnostic output uses Rich `Console(file=sys.stderr)`
**Validation:** Two-phase — type validation at query build time; completeness validation at execution time
**Authentication:** Delegated entirely to warehouse connectors; `SnowflakeEngine` / `DatabricksEngine` store `**connection_params` and pass them to the connector's `connect()` call
**Immutability:** Enforced at three levels — `SemanticViewMeta.__setattr__`, `@dataclass(frozen=True)` on `Query` and `OrderTerm`, `object.__setattr__` bypass in `Row.__init__`
**Lazy Imports:** Warehouse connector packages (`snowflake.connector`, `databricks.sql`) are imported inside `__init__` of their respective engines — core package has zero warehouse dependencies

---

*Architecture analysis: 2026-02-17*
