# Phase 31: Fix MockPool Documentation Example - Research

**Researched:** 2026-04-18
**Domain:** Documentation fix (RST how-to guide), MockPool behavior
**Confidence:** HIGH

## Summary

The `warehouse-testing.rst` how-to guide contains a `test_filtered_query()` example (lines 99-117) that asserts `len(rows) == 1` after calling `.where(Sales.country == "US")`. This is incorrect because `_Query.execute()` goes through the DBAPI 2.0 `cursor.execute(sql, params)` path, and `MockCursor.execute()` does not parse or apply WHERE predicates -- it returns all fixture rows for the matched view name. The v0.3 audit report confirmed this as a broken E2E flow.

The fix is a documentation-only change: rewrite the "Test conditional filters" section so the example correctly reflects MockPool's behavior. The existing "Inspect generated SQL" section (lines 119-141) already demonstrates `to_sql()` for structural SQL assertions, so the fix should avoid duplicating that pattern. Instead, the section should show that MockPool returns all fixture data regardless of filters, and demonstrate the correct assertion pattern.

**Primary recommendation:** Rewrite the "Test conditional filters" section to (a) assert `len(rows) == 2` (all fixture rows returned), (b) explain that MockPool does not evaluate WHERE predicates, and (c) point readers to the existing `to_sql()` section for verifying filter SQL structure.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DOCS-03 | How-to guides updated for Arrow fetch methods and Row convenience methods | The warehouse-testing.rst fix closes the remaining gap in DOCS-03 by correcting the `test_filtered_query()` assertion to match actual MockPool DBAPI behavior |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Quality gates:** `uv run basedpyright`, `uv run ruff check`, `uv run ruff format --check`, `uv run --extra dev pytest`, `uv run sphinx-build -W docs/src docs/_build`
- **Docs skill:** For doc-writing tasks, load `@.claude/skills/semolina-docs-author/SKILL.md` in PLAN.md execution_context
- **How-to guide scope rule:** Since this is a minor fix (well under 50% of page changed), the full docs-author workflow (Diataxis classification + humanizer pass) is NOT required
- **RST format:** Documentation uses reStructuredText, not markdown
- **Writing voice:** Warm but efficient, second person ("you"), for data/analytics engineers
- **Sphinx -W flag:** Build must pass with warnings-as-errors

## Standard Stack

No new libraries required. This is a documentation-only change.

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Sphinx | (project-installed) | Build docs with `-W` flag | Required quality gate [VERIFIED: pyproject.toml] |

## Architecture Patterns

### MockPool Execute Path (Critical Understanding)

The key architectural fact driving this fix:

```
_Query.execute()  [src/semolina/query.py:429-439]
  -> SQLBuilder.build_select_with_params(query)   # generates SQL + params
  -> pool.connect() -> conn.cursor()
  -> cur.execute(sql, params)                      # DBAPI 2.0 path
```

`MockCursor.execute(sql, params)` extracts the view name from the SQL `FROM` clause via regex and returns ALL fixture rows for that view. It does NOT parse WHERE clauses or apply predicate filtering. [VERIFIED: src/semolina/pool.py:116-147]

The separate `MockCursor._execute_query(query)` method DOES apply predicate filtering via `_eval_predicate()`, but this method is NEVER called by `_Query.execute()` -- it is only used in unit tests that call it directly. [VERIFIED: src/semolina/pool.py:149-201, src/semolina/query.py:429-439]

### Existing Test Proof

The test `test_execute_returns_all_fixture_data` in `tests/unit/test_pool.py:327-352` explicitly verifies this behavior: a query with `.where(Sales.country == "US")` on 3 fixture rows returns all 3 rows, not the 2 matching ones. [VERIFIED: tests/unit/test_pool.py:327-352]

### Current Document Structure

`warehouse-testing.rst` has these sections:
1. "Set up MockPool" (lines 9-29)
2. "Write a pytest test" (lines 31-80)
3. "Use a named pool for isolation" (lines 82-97)
4. **"Test conditional filters" (lines 99-117)** -- THE BROKEN SECTION
5. "Inspect generated SQL" (lines 119-141) -- already shows `to_sql()`
6. "Clean up between tests" (lines 143-148)
7. "See also" (lines 150-155)

[VERIFIED: docs/src/how-to/warehouse-testing.rst]

## Don't Hand-Roll

Not applicable for a documentation-only fix.

## Common Pitfalls

### Pitfall 1: Duplicating the to_sql() Pattern
**What goes wrong:** The natural instinct is to rewrite the "Test conditional filters" section to show `to_sql()` for verifying filters. But section 5 ("Inspect generated SQL") already does this with the exact same `.where(Sales.country == "US")` predicate.
**Why it happens:** The fix direction from the assumptions discussion suggested using `to_sql()`, which risks duplicating lines 119-141.
**How to avoid:** Keep the "Test conditional filters" section focused on what MockPool actually returns. Cross-reference the "Inspect generated SQL" section for SQL structure verification.
**Warning signs:** If the rewritten section looks nearly identical to the "Inspect generated SQL" section below it.

### Pitfall 2: Changing the Section Title Without Updating Content Flow
**What goes wrong:** If the section title changes (e.g., from "Test conditional filters" to something else), surrounding sections may reference it or the narrative flow may break.
**Why it happens:** The current title promises filter testing, which MockPool cannot do.
**How to avoid:** The new title and content should accurately describe what MockPool does with filters -- return all data, with the SQL containing the correct WHERE clause.
**Warning signs:** Reading the page top-to-bottom produces a disjointed narrative.

### Pitfall 3: sphinx-build -W Failure on RST Syntax
**What goes wrong:** Minor RST formatting issues (incorrect indentation, missing blank lines before/after directives) cause warnings that become errors with `-W`.
**Why it happens:** RST whitespace sensitivity differs from markdown.
**How to avoid:** Run `uv run sphinx-build -W docs/src docs/_build` after any change.
**Warning signs:** Build warnings about unexpected indentation or malformed directives.

## Code Examples

### Current Broken Example (lines 99-117)
```rst
Test conditional filters
------------------------

Build queries with optional filters and verify the results change with different
fixture data:

.. code-block:: python

   def test_filtered_query():
       cursor = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .where(Sales.country == "US")
           .execute()
       )
       rows = cursor.fetchall_rows()
       assert len(rows) == 1
       assert rows[0].country == "US"
```

[VERIFIED: docs/src/how-to/warehouse-testing.rst:99-117]

### What MockPool Actually Returns

With the fixture data from the `mock_pool` fixture (2 rows: US and CA), `MockCursor.execute()` returns ALL 2 rows regardless of the `.where()` clause. The assertion `len(rows) == 1` would fail at runtime. [VERIFIED: src/semolina/pool.py:116-147, tests/unit/test_pool.py:327-352]

### Correct Assertion Pattern

```python
def test_filtered_query():
    cursor = (
        Sales.query()
        .metrics(Sales.revenue)
        .dimensions(Sales.country)
        .where(Sales.country == "US")
        .execute()
    )
    rows = cursor.fetchall_rows()
    assert len(rows) == 2  # MockPool returns all fixture rows
```

[VERIFIED: consistent with tests/unit/test_pool.py:349 which asserts `len(rows) == 3` for 3 fixture rows]

### to_sql() Output Format for WHERE

For a `.where(Sales.country == "US")` query, `to_sql()` uses MockDialect and produces inline-rendered SQL:
- Contains `WHERE "country" = 'US'` [VERIFIED: tests/unit/test_sql.py:828-835]
- Uses `AGG("revenue")` for metrics [VERIFIED: tests/unit/test_sql.py:464-466]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (configured in pyproject.toml) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `uv run --extra dev pytest tests/unit/test_pool.py -x` |
| Full suite command | `uv run --extra dev pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DOCS-03 | warehouse-testing.rst example assertions match MockPool behavior | docs build | `uv run sphinx-build -W docs/src docs/_build` | N/A (doc build, not test file) |
| DOCS-03 | No runtime assertion errors in example code | manual-only | Review corrected assertion against `tests/unit/test_pool.py:327-352` | N/A |

### Sampling Rate
- **Per task commit:** `uv run sphinx-build -W docs/src docs/_build`
- **Per wave merge:** Full quality gates (basedpyright, ruff, pytest, sphinx-build)
- **Phase gate:** `uv run sphinx-build -W docs/src docs/_build` green

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. The primary validation is `sphinx-build -W` (already configured) and manual review of assertion correctness against existing unit tests.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The fix should keep the "Test conditional filters" section rather than removing it entirely | Common Pitfalls | LOW -- section provides value by explaining MockPool's filter behavior |
| A2 | The section title may need adjustment to avoid implying MockPool evaluates filters | Common Pitfalls | LOW -- title could stay the same if prose explains the behavior clearly |

## Open Questions (RESOLVED)

1. **Should the section title change?**
   - What we know: "Test conditional filters" implies MockPool tests filter behavior, but it does not
   - What's unclear: Whether to rename to something like "Understand MockPool filter behavior" or keep the current title with better explanatory prose
   - Recommendation: Update the title to reflect what the section actually demonstrates. Planner's discretion on exact wording.

2. **How much explanation about MockPool's two execute paths?**
   - What we know: The doc is a how-to guide, not an explanation page. How-tos should be minimal and goal-oriented.
   - What's unclear: How much to explain about why MockPool does not filter
   - Recommendation: One sentence explaining MockPool returns all fixture data, then cross-reference the "Inspect generated SQL" section. Keep it brief per Diataxis how-to principles.

## Sources

### Primary (HIGH confidence)
- `src/semolina/pool.py` - MockCursor.execute() implementation (lines 116-147), _execute_query() (lines 149-201)
- `src/semolina/query.py` - _Query.execute() DBAPI path (lines 429-439)
- `tests/unit/test_pool.py` - test_execute_returns_all_fixture_data (lines 327-352)
- `docs/src/how-to/warehouse-testing.rst` - current document with broken example
- `.planning/v0.3-MILESTONE-AUDIT.md` - audit identifying the gap

### Secondary (MEDIUM confidence)
- `tests/unit/test_sql.py` - WHERE clause SQL output format verification

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies, documentation-only change
- Architecture: HIGH - MockPool behavior verified from source code and existing tests
- Pitfalls: HIGH - pitfalls identified from direct code analysis

**Research date:** 2026-04-18
**Valid until:** indefinite (documentation fix, stable codebase)
