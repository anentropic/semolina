---
phase: quick-03
plan: 3
type: execute
wave: 1
depends_on: []
files_modified:
  - cubano-jaffle-shop/pyproject.toml
  - cubano-jaffle-shop/README.md
  - cubano-jaffle-shop/jaffle_models.py
  - src/cubano/__init__.py
  - pyproject.toml
  - uv.lock
autonomous: true
requirements: []
user_setup: []

must_haves:
  truths:
    - "Cubano library is available as a workspace dependency in cubano-jaffle-shop"
    - "Three Cubano models exist mapping to dbt semantic models (Orders, Customers, Products)"
    - "Cubano models correctly translate dbt dimensions to Dimension/Fact fields and measures to Metric fields"
    - "Models can be imported and instantiated without errors"
    - "Workspace structure enables isolated development of cubano-jaffle-shop example"
  artifacts:
    - path: "cubano-jaffle-shop/pyproject.toml"
      provides: "Workspace member configuration with cubano dependency"
      contains: "[project]", "dependencies = [\"cubano\"]"
    - path: "cubano-jaffle-shop/jaffle_models.py"
      provides: "Orders, Customers, Products models mapped from dbt semantic models"
      contains: "class Orders(SemanticView", "class Customers(SemanticView", "class Products(SemanticView"
    - path: "pyproject.toml"
      provides: "Root workspace configuration"
      contains: "[tool.uv.workspace]"
    - path: "uv.lock"
      provides: "Locked dependencies for all workspaces"
  key_links:
    - from: "cubano-jaffle-shop/pyproject.toml"
      to: "src/cubano"
      via: "workspace member dependency"
      pattern: "dependencies.*cubano"
    - from: "cubano-jaffle-shop/jaffle_models.py"
      to: "dbt-jaffle-shop/models/marts/*.yml"
      via: "semantic model translation"
      pattern: "semantic_models:"
    - from: "cubano-jaffle-shop/jaffle_models.py"
      to: "src/cubano/models.py"
      via: "SemanticView inheritance"
      pattern: "class.*SemanticView"
---

<objective>
Set up a cubano-jaffle-shop workspace that demonstrates Cubano's semantic model translation capabilities by mapping dbt-labs/jaffle-shop semantic models to equivalent Cubano Python models, enabling end-to-end example queries against Snowflake.

Purpose: Create a tangible, working example that showcases Cubano's ability to query dbt semantic models programmatically from Python, bridging the gap between dbt metadata and application code.

Output: cubano-jaffle-shop workspace with workspace-aware pyproject.toml, translated Cubano models, and executable example code
</objective>

<execution_context>
@.planning/STATE.md
@.planning/PROJECT.md
</execution_context>

<context>
Root pyproject.toml is at: `/Users/paul/Documents/Dev/Personal/cubano/pyproject.toml`
Cubano source is at: `src/cubano/`
Existing dbt-jaffle-shop models in: `dbt-jaffle-shop/models/marts/`
Semantic model definitions: orders.yml, customers.yml, products.yml with measures (Metrics) and dimensions (Dimensions/Facts)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create cubano-jaffle-shop directory and pyproject.toml as workspace member</name>
  <files>cubano-jaffle-shop/pyproject.toml, cubano-jaffle-shop/README.md</files>
  <action>
1. Create `cubano-jaffle-shop/` directory at repo root
2. Create `cubano-jaffle-shop/pyproject.toml` with:
   - [project] section: name = "cubano-jaffle-shop", version = "0.1.0", description, requires-python = ">=3.11"
   - dependencies = ["cubano"] (references workspace sibling, not PyPI)
   - [build-system]: requires = ["uv_build>=0.9.18,<0.11.0"], build-backend = "uv_build"
   - [dependency-groups] dev = ["pytest>=8.0.0"] for future tests
3. Create `cubano-jaffle-shop/README.md` documenting: purpose (translating dbt semantic models to Cubano), example usage, reference to orders/customers/products models
4. Verify syntax is valid TOML with no syntax errors
  </action>
  <verify>
    cat cubano-jaffle-shop/pyproject.toml && test -f cubano-jaffle-shop/README.md && python3 -c "import tomllib; tomllib.loads(open('cubano-jaffle-shop/pyproject.toml').read())" 2>&1 | head -1
  </verify>
  <done>
    cubano-jaffle-shop/pyproject.toml exists with valid [project] section declaring cubano as dependency, README.md exists with context, TOML syntax valid
  </done>
</task>

<task type="auto">
  <name>Task 2: Convert root pyproject.toml to multi-workspace configuration</name>
  <files>pyproject.toml, uv.lock</files>
  <action>
1. Read current root pyproject.toml
2. Preserve all existing [project] and [tool.*] sections unchanged
3. Add [tool.uv.workspace] section at end:
   members = ["src/cubano", "cubano-jaffle-shop"]
   Rationale: Creates 2-member workspace (cubano library + jaffle example), both accessible from root with single uv.lock
4. Run `uv sync` to regenerate uv.lock with workspace metadata
5. Verify uv sync completes without errors and uv.lock is updated with workspace markers

Note: This preserves existing pyproject.toml content (all tests, build system, ruff/basedpyright config) while enabling workspace features. cubano library (src/cubano) is extracted as workspace member to support the new structure.
  </action>
  <verify>
    grep -A 2 "\[tool.uv.workspace\]" pyproject.toml && grep "members" pyproject.toml && uv sync --check 2>&1 | grep -E "Workspace|workspace|lock updated"
  </verify>
  <done>
    pyproject.toml has [tool.uv.workspace] section with members array, uv.lock regenerated with workspace config, uv sync validates successfully
  </done>
</task>

<task type="auto">
  <name>Task 3: Extract dbt semantic model definitions and translate to Cubano models</name>
  <files>cubano-jaffle-shop/jaffle_models.py</files>
  <action>
1. Parse dbt-jaffle-shop/models/marts/orders.yml, customers.yml, products.yml to extract semantic_models definitions
   For each semantic_model:
   - name → class name (Orders, Customers, Products)
   - dimensions with type: categorical → Dimension()
   - dimensions with type: time → Dimension() (time is a dimension in Cubano)
   - measures → Metric() (all measures become metrics in Cubano)
   - entities (except primary key) → Fact() for foreign keys, Dimension() for other fields

2. Create cubano-jaffle-shop/jaffle_models.py with:
   - Import: from cubano import SemanticView, Metric, Dimension, Fact
   - class Orders(SemanticView, view='orders'):
     - order_total: Metric()
     - order_count: Metric()
     - tax_paid: Metric()
     - order_cost: Metric()
     - ordered_at: Dimension()
     - order_total_dim: Dimension()
     - is_food_order: Dimension()
     - is_drink_order: Dimension()
     - customer_order_number: Dimension()
   - class Customers(SemanticView, view='customers'):
     - customers: Metric()
     - count_lifetime_orders: Metric()
     - lifetime_spend_pretax: Metric()
     - lifetime_spend: Metric()
     - customer_name: Dimension()
     - customer_type: Dimension()
     - first_ordered_at: Dimension()
     - last_ordered_at: Dimension()
   - class Products(SemanticView, view='products'):
     - product_name: Dimension()
     - product_type: Dimension()
     - product_description: Dimension()
     - is_food_item: Dimension()
     - is_drink_item: Dimension()
     - product_price: Dimension()

3. Add module docstring explaining translation from dbt semantic models
4. Ensure all imports are at top, no circular dependencies
  </action>
  <verify>
    python3 -c "import sys; sys.path.insert(0, '.'); from cubano_jaffle_shop.jaffle_models import Orders, Customers, Products; print(f'Orders fields: {list(Orders._fields.keys())}'); print(f'Customers fields: {list(Customers._fields.keys())}'); print(f'Products fields: {list(Products._fields.keys())}')"
  </verify>
  <done>
    jaffle_models.py exists, all three model classes defined, fields correctly mapped (Metrics from measures, Dimensions from dimensions), imports work without error
  </done>
</task>

<task type="auto">
  <name>Task 4: Create cubano-jaffle-shop package structure and __init__.py</name>
  <files>cubano-jaffle-shop/__init__.py</files>
  <action>
1. Create `cubano-jaffle-shop/__init__.py` with:
   - from .jaffle_models import Orders, Customers, Products
   - __all__ = ["Orders", "Customers", "Products"]
   - Module docstring: "Cubano semantic view models translated from dbt-jaffle-shop"

2. This makes cubano_jaffle_shop a proper package importable as: from cubano_jaffle_shop import Orders

3. Verify can import from package directly
  </action>
  <verify>
    python3 -c "from cubano_jaffle_shop import Orders, Customers, Products; print('Import successful'); print(Orders._view_name)"
  </verify>
  <done>
    __init__.py exists with correct imports and __all__, package is importable, models accessible at package level
  </done>
</task>

<task type="auto">
  <name>Task 5: Verify typecheck, lint, and format pass for new code</name>
  <files>cubano-jaffle-shop/jaffle_models.py, cubano-jaffle-shop/__init__.py, pyproject.toml</files>
  <action>
1. Run `uv run basedpyright cubano-jaffle-shop/` with strict mode
   - Should complete with no errors
   - jaffle_models.py imports must type-check against cubano.fields (Metric, Dimension, Fact)

2. Run `uv run ruff check cubano-jaffle-shop/`
   - Should have no lint violations
   - Docstrings follow D rules (D213, no D203/D212)
   - Line length <= 100 chars

3. Run `uv run ruff format --check cubano-jaffle-shop/`
   - Should pass without requiring formatting

4. If any issues found: fix and re-run all three in sequence

Rationale: Quality gates per MEMORY.md — all code must pass typecheck, lint, format before completion
  </action>
  <verify>
    uv run basedpyright cubano-jaffle-shop/ 2>&1 | grep -E "0 errors|strict" && uv run ruff check cubano-jaffle-shop/ 2>&1 | wc -l | grep "^1$" && uv run ruff format --check cubano-jaffle-shop/ 2>&1 | head -1
  </verify>
  <done>
    basedpyright strict mode passes with 0 errors, ruff check has no violations, ruff format check passes (no changes needed)
  </done>
</task>

<task type="auto">
  <name>Task 6: Test model instantiation and field access to confirm translation correctness</name>
  <files>cubano-jaffle-shop/test_models.py</files>
  <action>
1. Create cubano-jaffle-shop/test_models.py (or run inline test) to verify:
   - Orders._view_name == 'orders'
   - Orders._fields contains exactly: order_total, order_count, tax_paid, order_cost, ordered_at, order_total_dim, is_food_order, is_drink_order, customer_order_number
   - Orders.order_total is a Metric instance
   - Orders.ordered_at is a Dimension instance
   - Same for Customers (8 fields: 4 metrics, 4 dimensions)
   - Same for Products (6 dimensions, 0 metrics)

2. Verify field names match dbt semantic model definitions exactly

3. Run test via pytest: `uv run pytest cubano-jaffle-shop/test_models.py -v`

Rationale: Translation must be accurate — differences between dbt and Cubano field naming/types could cause silent bugs in example queries later
  </action>
  <verify>
    uv run pytest cubano-jaffle-shop/test_models.py::test_orders_translation -v && uv run pytest cubano-jaffle-shop/test_models.py::test_customers_translation -v && uv run pytest cubano-jaffle-shop/test_models.py::test_products_translation -v
  </verify>
  <done>
    All translation tests pass, field counts match expectations, field types (Metric vs Dimension) correct per dbt definitions
  </done>
</task>

</tasks>

<verification>
After all tasks complete:

1. **Workspace Structure:**
   - `cubano-jaffle-shop/` exists at repo root
   - `cubano-jaffle-shop/pyproject.toml` declares cubano as workspace dependency
   - Root `pyproject.toml` has `[tool.uv.workspace]` with members = ["src/cubano", "cubano-jaffle-shop"]

2. **Model Translation:**
   - `cubano-jaffle-shop/jaffle_models.py` contains Orders, Customers, Products
   - All 18 fields total (Orders: 9, Customers: 8, Products: 6)
   - Field types match semantic model types (measures → Metric, dimensions → Dimension)

3. **Package Structure:**
   - `cubano-jaffle-shop/__init__.py` exports Orders, Customers, Products
   - `from cubano_jaffle_shop import Orders` works without error

4. **Quality Gates:**
   - basedpyright strict mode: 0 errors
   - ruff check: 0 violations
   - ruff format: no changes needed
   - pytest models translation tests: all pass

5. **Dependencies:**
   - uv.lock updated with workspace config
   - `uv sync` validates without errors
   - cubano library (src/cubano) is workspace sibling of cubano-jaffle-shop
</verification>

<success_criteria>
- [ ] `cubano-jaffle-shop/` directory created with proper workspace pyproject.toml
- [ ] Root `pyproject.toml` updated to include workspace configuration
- [ ] Orders, Customers, Products models created in jaffle_models.py (18 total fields, types correct)
- [ ] Package __init__.py exports all three models
- [ ] typecheck, lint, format all pass
- [ ] Model translation tests pass (field count, type validation)
- [ ] `from cubano_jaffle_shop import Orders, Customers, Products` works in interactive Python
- [ ] uv workspace recognized (members listed in pyproject.toml, uv.lock updated)
</success_criteria>

<output>
After completion, create `.planning/quick/3-create-cubano-jaffle-shop-workspace-with/3-SUMMARY.md` documenting:
- Workspace structure created (2 members: src/cubano, cubano-jaffle-shop)
- Models translated (18 fields across 3 classes)
- Translation mapping (dbt semantic model → Cubano field type)
- Ready for example queries in phase 4
</output>
