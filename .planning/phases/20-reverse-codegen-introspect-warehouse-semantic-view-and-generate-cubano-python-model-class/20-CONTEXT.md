# Phase 20: Reverse Codegen - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite `cubano codegen` as a reverse codegen command: given one or more schema-qualified semantic view names in a warehouse, introspect the warehouse metadata and emit valid, pre-linted Cubano Python model class definitions. The existing forward codegen (Python model → CREATE SEMANTIC VIEW SQL) is broken and being **dropped** — this phase replaces it entirely.

Reading the warehouse's own metric/dimension classification is the source of truth. This is not heuristic column-type inference.

</domain>

<decisions>
## Implementation Decisions

### CLI interface
- Command name stays `cubano codegen` (replacing the broken forward codegen in-place)
- Primary input: one or more schema-qualified view names as positional args (e.g. `my_schema.my_view`)
- Multiple views supported: `cubano codegen schema.view1 schema.view2`
- `--backend` flag required (explicit, not auto-detected from credentials)
- `--backend` accepts short-form builtins (`snowflake`, `databricks`) or a dotted import path for custom user-provided backends (e.g. `my_package.backends.MyBackend`)
- Credential loading reuses the existing Phase 8 credential infrastructure

### Output destination
- Default: print to stdout (code only — pipeable to `> models.py`)
- Warnings and errors go to stderr, never mixed into stdout
- No `--output` file flag in this phase (user redirects stdout if they want a file)

### Field mapping
- Read metric/dimension/fact classification directly from the warehouse's semantic view definition — not column type heuristics
- Snowflake semantic views have explicit METRICS/DIMENSIONS sections; Databricks metric views have explicit MEASURE clauses
- TODO comment only when a SQL data type has no clean Python type equivalent (e.g. GEOGRAPHY, VARIANT, SUPER, OBJECT)
- All other fields should be emitted cleanly without TODO

### Generated code style
- Class name: PascalCase from view name (e.g. `sales_revenue_view` → `SalesRevenueView`)
- Field docstrings: use warehouse column/field descriptions if they exist; omit docstring if no description
- Imports: always include at top of output (`from cubano import SemanticView, Metric, Dimension, Fact`)
- Multiple views: all classes in one output block, single shared imports section at top
- Output is pre-linted using project ruff + isort rules before being printed to stdout

### Backend architecture
- Warehouse introspection logic lives inside each backend class, not in a standalone module
- Each backend implements an introspection interface (method/protocol TBD by researcher/planner) that the CLI calls
- Short-form names (`snowflake`, `databricks`) resolve to the built-in backend classes; dotted paths are imported dynamically at runtime
- Custom backends must implement the same introspection interface to be usable with `cubano codegen`

### Claude's Discretion
- Exact introspection interface/protocol design (method name, return type, ABC vs Protocol)
- Exact warehouse introspection API calls (INFORMATION_SCHEMA vs SHOW commands for Snowflake; Unity Catalog APIs for Databricks)
- Python type string mapping table for SQL types
- Error handling for views that don't exist or aren't accessible
- Whether to include a `__semantic_view__` name override when view name differs from class name

</decisions>

<specifics>
## Specific Ideas

- The feature is analogous to `pg_dump` for ORM mapping — familiar mental model for data engineers
- Forward direction (Python → SQL) is explicitly out of scope for this phase and being removed
- The `cubano codegen` command signature changes from taking file paths to taking view names

</specifics>

<deferred>
## Deferred Ideas

- `--output <path>` flag to write to a file directly (user can redirect stdout for now)
- Auto-detection of backend from credentials (keep explicit `--backend` flag for now)
- Syncing an existing model file with warehouse changes (drift detection)

</deferred>

---

*Phase: 20-reverse-codegen-introspect-warehouse-semantic-view-and-generate-cubano-python-model-class*
*Context gathered: 2026-02-24*
