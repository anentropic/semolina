# Phase 16: Doc Accuracy & Jaffle-Shop Test Fix - Research

**Researched:** 2026-02-22
**Domain:** Documentation accuracy, test correctness
**Confidence:** HIGH

## Summary

Phase 16 closes three non-blocking gaps identified by the v0.2 milestone audit. All three are small, surgical fixes with zero architectural risk: two documentation inaccuracies in `filtering.md` and one test bug in the jaffle-shop example project. The fixes require changing a total of approximately 10 lines across 2 files.

The root causes are well-understood. The filtering.md SQL examples were written before the compiler's parenthesization behavior was finalized, and the jaffle-shop test incorrectly uses `.dimensions()` on a Metric field. All three fixes are independently verifiable by inspection and require no new dependencies or patterns.

**Primary recommendation:** Implement all three fixes in a single plan with three tasks (one per gap). No new libraries, patterns, or architecture needed.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DOCS-04 | Query language guide: Q-objects and AND/OR composition | Gaps DOCS-04-NESTED-PARENS and DOCS-04-ESCAPE-HATCH identified in filtering.md; exact corrections documented in Findings below |
| INT-02 | Integration tests validate queries with various field combinations (metrics, dimensions, filters) | Gap JAFFLE-SHOP-DIMENSIONS-BUG: test uses `.dimensions()` on a Metric field; fix documented in Findings below |
</phase_requirements>

## Findings

### Finding 1: DOCS-04-NESTED-PARENS (Complex nested WHERE SQL missing outer AND parens)

**Confidence:** HIGH (verified by reading compiler source + existing tests)

**Current state (filtering.md lines 394-406):**

The complex nested condition example shows SQL output as:

```sql
WHERE ("country" = 'US' OR "country" = 'CA')
    AND NOT ("revenue" < 100)
```

**What the compiler actually produces:**

The `SQLBuilder._compile_predicate()` method at `src/cubano/engines/sql.py` line 392-395 always wraps AND nodes in outer parentheses:

```python
case And(left=left, right=right):
    l_sql, l_params = self._compile_predicate(left)
    r_sql, r_params = self._compile_predicate(right)
    return f"({l_sql} AND {r_sql})", l_params + r_params
```

For the expression `(country == "US" | country == "CA") & ~(revenue < 100)`:
- Top node: `And(left=Or(...), right=Not(Lt(...)))`
- Or compiles to: `("country" = 'US' OR "country" = 'CA')`
- Not(Lt) compiles to: `NOT ("revenue" < 100)`
- And compiles to: `(("country" = 'US' OR "country" = 'CA') AND NOT ("revenue" < 100))`

The existing test at `tests/unit/test_sql.py` line 653-658 confirms this pattern:

```python
def test_compile_and(self):
    """And(l, r) -> '({l_sql} AND {r_sql})', l_params + r_params."""
    pred = Exact("country", "US") & Gt("revenue", 1000)
    sql, params = self.builder._compile_predicate(pred)
    assert sql == '("country" = %s AND "revenue" > %s)'
```

**Required fix:** Add outer parentheses to both Snowflake and Databricks SQL examples:

Snowflake:
```sql
WHERE (("country" = 'US' OR "country" = 'CA')
    AND NOT ("revenue" < 100))
```

Databricks:
```sql
WHERE ((`country` = 'US' OR `country` = 'CA')
    AND NOT (`revenue` < 100))
```

**Verification:** Visual inspection that parens match compiler output format.

### Finding 2: DOCS-04-ESCAPE-HATCH (Escape hatch references "engine's" method, should be SQLBuilder)

**Confidence:** HIGH (verified by reading source code)

**Current state (filtering.md line 472-473):**

```
To compile custom lookups into SQL, add a `case RegexpMatch(...)` branch
to your engine's `_compile_predicate()` method.
```

**Actual location:** `_compile_predicate()` is defined on `SQLBuilder` (at `src/cubano/engines/sql.py` line 369), not on any Engine class (SnowflakeEngine, DatabricksEngine, MockEngine). The engines delegate SQL building to SQLBuilder.

**Required fix:** Change "your engine's" to "`SQLBuilder`'s":

```
To compile custom lookups into SQL, add a `case RegexpMatch(...)` branch
to `SQLBuilder._compile_predicate()`.
```

**Verification:** `grep -n "_compile_predicate" src/cubano/engines/sql.py` shows the method is on SQLBuilder at line 369. No Engine class defines this method.

### Finding 3: JAFFLE-SHOP-DIMENSIONS-BUG (test uses .dimensions() on a Metric field)

**Confidence:** HIGH (verified by reading model definition + test code)

**Current state (`cubano-jaffle-shop/tests/test_warehouse_queries.py` lines 280-286):**

```python
result = (
    Customers.query()
    .dimensions(Customers.lifetime_spend)
    .where(Customers.lifetime_spend > 100)
    .limit(50)
    .execute()
)
```

**The bug:** `lifetime_spend` is declared as `Metric()` in `jaffle_models.py` line 53, but the test calls `.dimensions(Customers.lifetime_spend)`. Against a real warehouse, this would generate incorrect SQL because metrics require aggregation wrapping (AGG/MEASURE), not dimension handling.

**Required fix:** Change `.dimensions(Customers.lifetime_spend)` to `.metrics(Customers.lifetime_spend)`:

```python
result = (
    Customers.query()
    .metrics(Customers.lifetime_spend)
    .where(Customers.lifetime_spend > 100)
    .limit(50)
    .execute()
)
```

**Verification:** Run `cd cubano-jaffle-shop && uv run pytest tests/ -m mock -v` to confirm mock tests still pass. The jaffle-shop test must be run from within the `cubano-jaffle-shop/` subdirectory (per Phase 13-04 findings).

## Standard Stack

No new libraries or dependencies. This phase modifies only documentation and test files.

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| N/A | N/A | N/A | No new dependencies needed |

## Architecture Patterns

No architectural changes. All three fixes are surgical edits to existing files.

### Files to Modify

```
docs/src/how-to/filtering.md        # Gaps 1 and 2 (lines 394-406, 472-473)
cubano-jaffle-shop/tests/test_warehouse_queries.py  # Gap 3 (line 282)
```

### Edit Pattern

Each fix is a simple text replacement:

1. **DOCS-04-NESTED-PARENS:** Add `(` before the first quote char and `)` after the last on the SQL WHERE block in both Snowflake and Databricks tabs (lines 394-406)
2. **DOCS-04-ESCAPE-HATCH:** Replace "your engine's `_compile_predicate()` method" with "`SQLBuilder._compile_predicate()`" (line 473)
3. **JAFFLE-SHOP-DIMENSIONS-BUG:** Replace `.dimensions(Customers.lifetime_spend)` with `.metrics(Customers.lifetime_spend)` (line 282)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| N/A | N/A | N/A | No custom solutions needed for simple text edits |

## Common Pitfalls

### Pitfall 1: Forgetting to update both Snowflake AND Databricks SQL tabs

**What goes wrong:** Fixing only one SQL dialect tab while leaving the other with the old (incorrect) formatting.
**Why it happens:** The tabbed SQL blocks in filtering.md have parallel Snowflake/Databricks examples that must stay in sync.
**How to avoid:** Always edit both `=== "Snowflake"` and `=== "Databricks"` blocks together.
**Warning signs:** Only one tab touched in the diff.

### Pitfall 2: Running jaffle-shop tests from repo root instead of subdirectory

**What goes wrong:** `ModuleNotFoundError: No module named 'cubano_jaffle_shop'` when running pytest from repo root.
**Why it happens:** The jaffle-shop is a separate package with its own pyproject.toml; uv resolves it from its own directory.
**How to avoid:** Always `cd cubano-jaffle-shop` before running `uv run pytest tests/ -m mock -v`.
**Warning signs:** ModuleNotFoundError in test output.

### Pitfall 3: Breaking MkDocs Material admonition/tab indentation

**What goes wrong:** Rendering breaks if tab content indentation (4 spaces) is disrupted.
**Why it happens:** MkDocs Material uses indentation to scope content within `===` tabs.
**How to avoid:** Preserve the 4-space indentation inside tabbed blocks and verify with `uv run mkdocs build --strict`.
**Warning signs:** Build warnings or visually broken tab content.

## Code Examples

### Fix 1: Nested parens (filtering.md lines 394-406)

Before:
```markdown
=== "Snowflake"

    ```sql
    WHERE ("country" = 'US' OR "country" = 'CA')
        AND NOT ("revenue" < 100)
    ```

=== "Databricks"

    ```sql
    WHERE (`country` = 'US' OR `country` = 'CA')
        AND NOT (`revenue` < 100)
    ```
```

After:
```markdown
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
```

### Fix 2: Escape hatch reference (filtering.md line 472-473)

Before:
```markdown
To compile custom lookups into SQL, add a `case RegexpMatch(...)` branch
to your engine's `_compile_predicate()` method.
```

After:
```markdown
To compile custom lookups into SQL, add a `case RegexpMatch(...)` branch
to `SQLBuilder._compile_predicate()`.
```

### Fix 3: Jaffle-shop test (test_warehouse_queries.py line 282)

Before:
```python
.dimensions(Customers.lifetime_spend)
```

After:
```python
.metrics(Customers.lifetime_spend)
```

## State of the Art

No evolution since the compiler was finalized in Phase 13.1. The SQL output format is stable.

## Open Questions

None. All three fixes are fully understood and require no design decisions.

## Sources

### Primary (HIGH confidence)

- `src/cubano/engines/sql.py` line 369-395 -- `SQLBuilder._compile_predicate()` definition and And/Or/Not compilation logic
- `tests/unit/test_sql.py` line 653-658 -- `test_compile_and` confirms AND always wraps in outer parens
- `tests/unit/test_sql.py` line 674-682 -- `test_compile_nested_and_or_not` confirms nested compilation behavior
- `cubano-jaffle-shop/src/cubano_jaffle_shop/jaffle_models.py` line 53 -- `lifetime_spend = Metric()` confirms field type
- `.planning/v0.2-MILESTONE-AUDIT.md` -- audit gap definitions (DOCS-04-NESTED-PARENS, DOCS-04-ESCAPE-HATCH, JAFFLE-SHOP-DIMENSIONS-BUG)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies needed
- Architecture: HIGH -- no architectural changes, all surgical edits
- Pitfalls: HIGH -- verified against past session notes (Phase 13-04 jaffle-shop path issue)

**Research date:** 2026-02-22
**Valid until:** indefinite (fixes are stable, no external dependency drift)
