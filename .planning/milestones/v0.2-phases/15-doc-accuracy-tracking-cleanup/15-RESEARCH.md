# Phase 15: Doc Accuracy & Tracking Cleanup (GAP CLOSURE) - Research

**Researched:** 2026-02-22
**Domain:** Documentation accuracy, project tracking, CI consistency, dead code removal
**Confidence:** HIGH

## Summary

Phase 15 is a cleanup/gap-closure phase closing 2 minor integration gaps identified in the v0.2 milestone audit (DOCS-04-IEXACT and DOCS-04-AND-PARENS) plus 5 actionable tech debt items (stale comments, orphaned fixtures, tracking checkbox gaps, CI workflow version inconsistency). No new libraries, no new patterns, no architectural decisions. Every change has been precisely located and verified.

All 7 success criteria map to specific lines in specific files. The changes are mechanical: text edits to documentation, checkbox updates, line deletions, and a version bump in a YAML file. No code logic changes. No test behavior changes. Quality gates (typecheck, lint, format, tests, docs build) should pass without issue since no production code is modified.

**Primary recommendation:** Execute all 7 changes as 3 small, focused plans grouped by concern (docs accuracy, tracking/stale-code, CI/fixtures). Each plan is independently verifiable.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DOCS-04 | Query language guide: Q-objects and AND/OR composition | Fix 2 SQL examples in `filtering.md` to match actual compiler output: iexact uses ILIKE (not LOWER), AND wraps in outer parens |
</phase_requirements>

## Standard Stack

No new libraries or tools. All changes use existing project infrastructure:

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| MkDocs | existing | Documentation build (`mkdocs build --strict`) | Already configured; verifies doc changes |
| basedpyright | existing | Typecheck (strict mode) | Validates no type regressions from fixture removal |
| ruff | existing | Lint + format | Validates no lint regressions |
| pytest | existing | Test suite | Validates no test regressions from fixture removal |

### Supporting
None needed.

### Alternatives Considered
None -- this is a cleanup phase with no design decisions.

## Architecture Patterns

No new patterns. All changes follow existing project conventions.

### Change Locations (Precise File Map)

```
docs/src/how-to/filtering.md          # Success criteria 1, 2
.planning/REQUIREMENTS.md             # Success criteria 3
tests/integration/test_queries.py     # Success criteria 4
src/cubano/cli/codegen.py             # Success criteria 5
tests/integration/conftest.py         # Success criteria 6
.github/workflows/docs.yml           # Success criteria 7
```

### Pattern: SQL Example Accuracy

Documentation SQL examples in `filtering.md` must match actual `sql.py` compiler output. The compiler source of truth is `src/cubano/engines/sql.py`:

- **IExact** (line 460-461): `case IExact(field_name=f, value=v): return f"{q(f)} ILIKE {ph}", [v]`
  - Correct SQL: `"country" ILIKE 'united states'` (Snowflake) / `` `country` ILIKE 'united states' `` (Databricks)
  - Current doc (wrong): `LOWER("country") = 'united states'`

- **And** (line 392-395): `case And(left=left, right=right): return f"({l_sql} AND {r_sql})", l_params + r_params`
  - Correct SQL: `("country" = 'US' AND "revenue" > 500)` (outer parens present)
  - Current doc (wrong): `"country" = 'US' AND "revenue" > 500` (no outer parens)

### Anti-Patterns to Avoid
- **Editing compiler to match docs:** The compiler is correct; docs must match compiler, not the reverse.
- **Scope creep:** Other tech debt items from the audit (snapshot discrimination, pre-existing test failures, LIKE escaping) are explicitly out of scope for Phase 15.

## Don't Hand-Roll

Not applicable -- no custom solutions needed. All changes are text edits.

## Common Pitfalls

### Pitfall 1: Orphaned Fixture Removal Breaking Tests
**What goes wrong:** Removing fixtures that are still transitively depended upon by other fixtures or tests.
**Why it happens:** Fixtures reference each other; removing one can break the chain.
**How to avoid:** The 3 orphaned fixtures (`snowflake_connection`, `databricks_connection`, `test_schema_name`) are only referenced by each other within `conftest.py` (verified via grep). The `snowflake_credentials` and `databricks_credentials` fixtures they depend on are also used by the Phase 12 `snowflake_engine`/`databricks_engine` fixtures and must NOT be removed. Run full test suite after removal.
**Warning signs:** `pytest --collect-only` errors or fixture not found errors.

### Pitfall 2: AND Parens in Nested Examples
**What goes wrong:** Fixing the simple AND example but missing that nested examples also show AND.
**Why it happens:** Multiple SQL examples in filtering.md show AND composition.
**How to avoid:** The simple AND example at lines 306/312 needs outer parens added. The complex nested example at lines 397-398/404-405 already shows correct parens because it uses both OR and AND (the OR sub-expression gets parens, and the entire expression gets parens). Only the simple `&` example on lines 306 and 312 needs fixing.
**Warning signs:** Inconsistency between simple and complex examples.

### Pitfall 3: REQUIREMENTS.md Checkbox Formatting
**What goes wrong:** Breaking markdown rendering by incorrect checkbox syntax.
**Why it happens:** Manual text editing of checkboxes.
**How to avoid:** Change `- [ ]` to `- [x]` for exactly these 11 lines: INT-02, INT-03, INT-04, INT-05, CODEGEN-01 through CODEGEN-08. Verify the file still renders correctly.
**Warning signs:** Malformed markdown in `REQUIREMENTS.md`.

### Pitfall 4: docs.yml checkout version
**What goes wrong:** Using a version that doesn't exist or has breaking changes.
**Why it happens:** Blindly bumping versions.
**How to avoid:** All other workflows (`ci.yml`, `release.yml`, `pr.yml`) already use `actions/checkout@v6` successfully. The change is safe -- just consistency alignment.
**Warning signs:** Workflow failures on next push to main.

## Code Examples

### Fix 1: filtering.md iexact SQL (lines 243-251)

Current (wrong):
```markdown
=== "Snowflake"

    ```sql
    WHERE LOWER("country") = 'united states'
    ```

=== "Databricks"

    ```sql
    WHERE LOWER(`country`) = 'united states'
    ```
```

Corrected:
```markdown
=== "Snowflake"

    ```sql
    WHERE "country" ILIKE 'united states'
    ```

=== "Databricks"

    ```sql
    WHERE `country` ILIKE 'united states'
    ```
```

### Fix 2: filtering.md AND composition SQL (lines 305-313)

Current (wrong):
```markdown
=== "Snowflake"

    ```sql
    WHERE "country" = 'US' AND "revenue" > 500
    ```

=== "Databricks"

    ```sql
    WHERE `country` = 'US' AND `revenue` > 500
    ```
```

Corrected:
```markdown
=== "Snowflake"

    ```sql
    WHERE ("country" = 'US' AND "revenue" > 500)
    ```

=== "Databricks"

    ```sql
    WHERE (`country` = 'US' AND `revenue` > 500)
    ```
```

### Fix 3: REQUIREMENTS.md checkboxes (lines 13-28)

Change these 11 lines from `- [ ]` to `- [x]`:
```
- [x] **INT-02**: Integration tests validate queries with various field combinations
- [x] **INT-03**: Integration tests verify correct result ordering and limiting
- [x] **INT-04**: Integration tests handle edge cases
- [x] **INT-05**: Test suite isolates data in separate schema
- [x] **CODEGEN-01**: User can run `cubano codegen` CLI
- [x] **CODEGEN-02**: Codegen generates CREATE SEMANTIC VIEW SQL
- [x] **CODEGEN-03**: Codegen generates metric view definitions for Databricks
- [x] **CODEGEN-04**: Codegen processes all models in a file
- [x] **CODEGEN-05**: Generated code passes syntax validation
- [x] **CODEGEN-06**: Codegen validates no circular relationships
- [x] **CODEGEN-07**: User specifies output file and target backend
- [x] **CODEGEN-08**: Generated SQL is formatted for readability
```

### Fix 4: test_queries.py stale comment (lines 15-16)

Remove these two lines from the module docstring:
```python
Note: WHERE clause filtering is not yet compiled to SQL (WHERE 1=1 placeholder in sql.py).
Filter integration tests are deferred until the Q-object SQL compiler is implemented.
```

### Fix 5: codegen.py stale stub comment (line 74)

Current:
```python
    # Generate SQL (stub: implemented in 09-03)
```

Replace with:
```python
    # Generate SQL for all discovered models
```

### Fix 6: Remove 3 orphaned fixtures from conftest.py

Remove fixtures `test_schema_name` (lines 72-89), `snowflake_connection` (lines 92-141), and `databricks_connection` (lines 143-191) from `tests/integration/conftest.py`. Keep `snowflake_credentials`, `databricks_credentials`, `TEST_DATA`, `_redact_credential`, `snapshot`, `snowflake_engine`, `databricks_engine`, and `backend_engine`.

### Fix 7: docs.yml checkout version (line 28)

Change:
```yaml
        uses: actions/checkout@v4
```

To:
```yaml
        uses: actions/checkout@v6
```

## State of the Art

Not applicable -- no technology choices or version decisions in this phase.

## Open Questions

None. All 7 changes are precisely located and mechanically verifiable. No ambiguity remains.

## Sources

### Primary (HIGH confidence)
- `src/cubano/engines/sql.py` lines 392-395 (And compiler), lines 460-461 (IExact compiler) -- verified compiler behavior
- `docs/src/how-to/filtering.md` lines 243-251 (iexact SQL), lines 305-313 (AND SQL) -- verified current doc content
- `.planning/v0.2-MILESTONE-AUDIT.md` -- source of all 7 gap items
- `tests/integration/conftest.py` -- verified orphaned fixtures not referenced by any test files
- `tests/integration/test_queries.py` lines 15-16 -- verified stale comment
- `src/cubano/cli/codegen.py` line 74 -- verified stale stub comment
- `.github/workflows/docs.yml` line 28 -- verified `@v4` vs `@v6` in other workflows
- `.planning/REQUIREMENTS.md` lines 13-28 -- verified 11 unchecked boxes

### Secondary (MEDIUM confidence)
None needed.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new tools, all changes use existing infrastructure
- Architecture: HIGH -- no architectural changes; purely mechanical edits
- Pitfalls: HIGH -- all changes verified by direct file inspection; grep confirms no hidden dependencies

**Research date:** 2026-02-22
**Valid until:** indefinite (cleanup phase, no external dependencies that could change)
