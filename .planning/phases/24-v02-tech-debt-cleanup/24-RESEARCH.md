# Phase 24: v0.2 Tech Debt Cleanup - Research

**Researched:** 2026-02-26
**Domain:** Python testing, dead-code removal, documentation bookkeeping
**Confidence:** HIGH

## Summary

Phase 24 is a pure housekeeping phase with no new product features. All four planned items
are well-understood and have clear implementation paths visible directly in the codebase.
No external library research is required.

The four work streams are independent of each other and can be planned and executed in the
order described in the roadmap without any risk of conflict. The MockEngine filter fix
(24-01) is the only item with meaningful implementation complexity; the others are text
edits, file deletions, and `requirements_completed` field population.

**Primary recommendation:** Execute plans 24-01 through 24-04 in roadmap order. 24-01 is
TDD (write failing test first, then implement). 24-02 through 24-04 are straightforward
text/file changes requiring only quality gates (lint, typecheck, test, docs build).

---

## Standard Stack

No new dependencies. All work uses existing project tooling.

| Tool | Purpose | Already in project |
|------|---------|-------------------|
| pytest | Run tests (24-01 TDD) | Yes |
| basedpyright | Typecheck (24-01 code change) | Yes |
| ruff check/format | Lint + format | Yes |
| mkdocs build --strict | Docs gate (24-02 docs edits) | Yes |

---

## Architecture Patterns

### 24-01: MockEngine WHERE Filter Fix

**Current state (confirmed by code inspection):**

`MockEngine.execute()` in `/Users/paul/Documents/Dev/Personal/cubano/src/cubano/engines/mock.py`
(lines 124–162) ignores `query._filters` entirely. It validates the query, extracts the view
name, and returns all fixture rows for that view with no filtering applied.

`TestFiltering` in
`/Users/paul/Documents/Dev/Personal/cubano/cubano-jaffle-shop/tests/test_mock_queries.py`
(lines 122–150) has two test methods:
- `test_filter_boolean` — asserts `len(result) > 0` only (vacuous)
- `test_filter_comparison` — asserts `len(result) > 0` only (vacuous)

Both docstrings claim "MockEngine evaluates WHERE predicates via the WHERE clause compiler
(Phase 13.1)" which is false. This is misleading documentation.

**Design decision needed (two options):**

Option A — Implement in-memory filtering in MockEngine.execute():
- Write a Python predicate evaluator that walks the Predicate tree and applies it
  in-memory against fixture rows
- The filters module (`src/cubano/filters.py`) has 16 Lookup subclasses plus And/Or/Not
- MockDialect.normalize_identifier() is identity (field names stay as-is) — this means
  fixture row keys can be matched directly to Predicate.field_name
- Non-trivial to implement (string LIKE/ILIKE semantics, Between, In, IsNull, etc.)
- Benefit: non-vacuous assertions validate actual filter correctness

Option B — Update docstrings/comments to clearly state MockEngine validates query
construction only, and adjust test assertions to be honest about what is validated:
- Simpler: no code change, only documentation correction
- The docstring in `MockEngine.execute()` already says "returns fixture data for that view"
  with no mention of filtering — consistent with Option B
- Test docstrings just need truthful wording
- Test assertions stay `> 0` but comments explain they validate query construction
- The class docstring can explicitly state ORDER BY and WHERE are not evaluated

**Recommendation:** Option A (implement filtering) is the correct choice given the success
criterion: "MockEngine.execute() applies query._filters (or docstrings clearly state
'query construction validation only'); TestFiltering assertions are non-vacuous." The
first clause (apply _filters) enables non-vacuous assertions. Option B satisfies only the
docstring clause and leaves assertions vacuous — explicitly excluded by the criterion text
"TestFiltering assertions are non-vacuous."

**Implementation approach for Option A:**

The predicate tree types are frozen dataclasses with match/case already implemented in
`SQLBuilder._compile_predicate()`. A parallel `_eval_predicate(node, row)` function can
use the same structural pattern matching to evaluate predicates against a Python dict row.

Key matching logic:
- `Exact(field_name=f, value=v)` → `row.get(f) == v`
- `Gt/Gte/Lt/Lte(field_name=f, value=v)` → standard comparisons
- `In(field_name=f, value=v)` → `row.get(f) in v` (empty In → always False)
- `Between(field_name=f, value=(lo, hi))` → `lo <= row.get(f) <= hi`
- `IsNull(field_name=f, value=v)` → `(row.get(f) is None) == v`
- `StartsWith/EndsWith/Like` → string prefix/suffix (str() coercion + `.startswith()`)
- `IStartsWith/IEndsWith/ILike/IExact` → case-insensitive string ops (`.lower()`)
- `And(left, right)` → `_eval_predicate(left, row) and _eval_predicate(right, row)`
- `Or(left, right)` → `_eval_predicate(left, row) or _eval_predicate(right, row)`
- `Not(inner)` → `not _eval_predicate(inner, row)`
- `NotEqual` → `row.get(f) != v`

`source=` handling: Lookup.source (repr=False field) provides the warehouse column name
when set. In-memory filter should use `node.source if node.source is not None else f` for
the row key lookup, mirroring how `_compile_predicate()` handles `source=`.

The MockDialect's `normalize_identifier()` is identity (returns name unchanged), meaning
fixture row keys are already lowercase Python names matching `Predicate.field_name`.

**Fixture data for non-vacuous assertions:**

For `test_filter_boolean`: `orders_data` has both `is_food_order=True` and
`is_food_order=False` rows. After filtering `is_food_order == True`, result count should
be less than total fixture count. Non-vacuous assertion: count result rows and compare.

For `test_filter_comparison`: `orders_data` has `order_total` Decimal values including
some > 50 and some <= 50. After filtering `order_total > 50`, result count should be
less than total fixture count. Additionally, assert each returned row satisfies the filter.

**TDD approach (per roadmap):**
1. Write failing tests first (tests that would pass only if filtering is applied)
2. Implement `_eval_predicate()` in MockEngine or as module-level function
3. Hook it into `execute()` via `[r for r in rows if _eval_predicate(query._filters, r)]`

**Where to place tests:** Adjacent to `TestMockEngineExecute` in
`tests/unit/test_engines.py`.

### 24-02: Dead Code + REQUIREMENTS.md Bookkeeping

**Dead code (confirmed by code inspection):**

`/Users/paul/Documents/Dev/Personal/cubano/src/cubano/codegen/models.py` contains
`FieldData` and `ModelData` frozen dataclasses. Zero callers exist in source or tests
(grep confirms no imports of `cubano.codegen.models` anywhere outside of the file and
`__pycache__`). Safe to delete.

The `codegen/` directory after deletion will contain:
- `__init__.py` (keep — it's an empty package init)
- `introspector.py` (keep — used by reverse codegen)
- `python_renderer.py` (keep — used by reverse codegen)
- `type_map.py` (keep — used by reverse codegen)
- `templates/` (keep — used by python_renderer)

**REQUIREMENTS.md changes needed:**

1. CODEGEN-01 through CODEGEN-08 (lines 21–28): These describe forward codegen (Python →
   SQL/YAML) which was intentionally deleted in Phase 20. Add a supersession note after
   each `[x]` line, or add a block note before/after the CODEGEN section. Suggested
   format: append `<!-- Superseded by Phase 20 reverse codegen; forward codegen CLI
   deleted in Phase 20-04 -->` after the CODEGEN section, or annotate each entry. The
   simplest approach is a single block annotation above or below the CODEGEN group.

2. DOCS-03 (line 34): Change `.filter()` → `.where()` to reflect Phase 10.1 rename.
   Current text: `Query language guide: .metrics(), .dimensions(), .filter(), .order_by(),
   .limit()`
   Corrected text: `Query language guide: .metrics(), .dimensions(), .where(), .order_by(),
   .limit()`

3. DOCS-04 (line 35): Change `Q-objects` → `Predicate &/|/~` to reflect Phase 13.1
   replacement.
   Current text: `Query language guide: Q-objects and AND/OR composition`
   Corrected text: `Query language guide: Predicate composition with &, |, ~ operators`

4. Phase 19 plan frontmatter (`19-01-PLAN.md`): The `requirements: [DOCS-04]` entry is
   wrong — DOCS-04 is Q-objects/Predicate composition, unrelated to Fact field
   documentation. Phase 19 has no formal REQUIREMENTS.md entry. Corrected:
   `requirements: []`

**Note on 19-01-SUMMARY.md:** The SUMMARY file also has `requirements-completed: [DOCS-04]`
(line 37). This should be corrected to `requirements-completed: []` for consistency.

### 24-03: Populate requirements_completed in SUMMARY.md Files

**Current state:** 49/63 SUMMARY.md files already have `requirements_completed` populated.
14 are missing. The `10.1-PLANNING-SUMMARY.md` has no YAML frontmatter at all (it is a
special planning-phase summary document, not a plan execution summary) — this should be
excluded from the requirement since it has no frontmatter block to add to.

That leaves 13 true execution SUMMARY.md files needing `requirements_completed` added:

| File | Phase | Plan | Requirements per PLAN.md |
|------|-------|------|--------------------------|
| 08-01-SUMMARY.md | 08 | 01 | INT-06 |
| 08-02-SUMMARY.md | 08 | 02 | INT-01, INT-05 |
| 08-03-SUMMARY.md | 08 | 03 | INT-02, INT-03 |
| 08-04-SUMMARY.md | 08 | 04 | INT-01, INT-02, INT-03, INT-04 |
| 08-05-SUMMARY.md | 08 | 05 | INT-06 |
| 08-06-SUMMARY.md | 08 | 06 | INT-06 |
| 09-04-SUMMARY.md | 09 | 04 | CODEGEN-04 through CODEGEN-08 (test plan covers remaining) |
| 10-04-SUMMARY.md | 10 | 04 | DOCS-08, DOCS-09 |
| 10.1-07-SUMMARY.md | 10.1 | 07 | (none — API removal has no formal requirement) |
| 10.1-08-SUMMARY.md | 10.1 | 08 | (none — verification plan) |
| 11-02-SUMMARY.md | 11 | 02 | (tech debt — cubano-jaffle-shop update) |
| 20-02-SUMMARY.md | 20 | 02 | CODEGEN-WAREHOUSE, CODEGEN-REVERSE (partial) |
| 23-01-SUMMARY.md | 23 | 01 | (none — housekeeping only) |

**Convention pattern (from existing populated files):**

Frontmatter uses `requirements-completed: [LIST]` (hyphenated key, not underscore).
Examples from Phase 13 and 20 summaries show the pattern clearly:
```yaml
requirements-completed: [INT-01, INT-06]
requirements-completed: []
```

Plans without formal requirements use `requirements-completed: []`.

For plans that don't map to specific requirement IDs (Phase 10.1-07, 10.1-08, 11-02,
23-01), use `requirements-completed: []`.

**Determining correct requirement lists:**

Phase 09-04: The PLAN.md says "All 8 CODEGEN requirements covered". Plans 09-01 claimed
CODEGEN-01, 09-02 claimed CODEGEN-02/03. Plan 09-04 (tests) validates all 8; it
completed the test coverage. A defensible entry is `requirements-completed: [CODEGEN-04,
CODEGEN-05, CODEGEN-06, CODEGEN-07, CODEGEN-08]` (the ones not claimed by 01-03).
Plan 09-03 was already marked `requirements-completed: []` (validation layer, no new req).

Phase 20-02: SnowflakeEngine.introspect() and DatabricksEngine.introspect() are the
core implementations for CODEGEN-REVERSE and CODEGEN-WAREHOUSE. A reasonable entry is
`requirements-completed: []` (partial implementation, final reqs satisfied in Phase 20-04
which has the full CLI). The 20-04 SUMMARY does not yet list these either; cross-check
needed during execution.

### 24-04: Add Snapshot Re-record Note

**Current state:** The test `test_filtered_by_dimension` does not exist in the current
codebase. It was previously removed (git commit: "test: remove test_filtered_by_dimension
until WHERE clause compiler is implemented"). The actual snapshot file is
`tests/integration/__snapshots__/test_queries.ambr`.

The success criterion says: "`test_snapshot_queries.py::test_filtered_by_dimension` has a
comment/marker noting it needs real Snowflake credentials to re-record". The roadmap uses
the old filename — the actual test file is `tests/integration/test_queries.py`. The test
does not currently exist in that file.

**Options:**

Option A — Add `test_filtered_by_dimension` to `test_queries.py` with a clear comment
explaining it needs real credentials to record, and mark it `pytest.mark.skip` or wrap it
in a conditional so it doesn't fail in CI.

Option B — Add only a comment to `test_queries.py` (e.g., in the module docstring or a
placeholder function) noting the test was removed and needs re-recording.

**Recommendation:** Option A is more robust — add a real test function that would work
correctly once `MockEngine` applies filters (which Phase 24-01 implements). After 24-01,
the MockEngine will return filtered data. The snapshot would still need re-recording with
real Snowflake credentials because the current snapshots were bootstrapped from MockEngine
data (all 5 rows, no WHERE applied). Add a `pytest.mark.skip` with a clear reason string
plus a comment explaining the re-record workflow.

Actually: with 24-01 complete, the MockEngine will apply filtering correctly in replay
mode. So the snapshot for `test_filtered_by_dimension` would be recorded with the filtered
results — but only if `--snapshot-update` is run with real Snowflake credentials (for the
`[snowflake_engine]` variant). The MockEngine variant (`[databricks_engine]` if it uses
mock in replay) would work from 24-01. The note/comment should explain specifically the
Snowflake recording gap.

**Simpler approach:** Add the test function with a `# NOTE:` comment block in the body
explaining the snapshot needs re-recording with real Snowflake credentials. No skip marker
needed since the snapshot file won't have an entry — syrupy will fail with "snapshot does
not exist" rather than a logic failure. Add `pytest.mark.xfail(strict=False, reason=...)`
or use `--snapshot-warn-unused`. Given the CI already uses `--snapshot-warn-unused`, the
safest approach is to add the function with a clear docstring comment and let CI guidance
cover it.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| In-memory predicate eval | New evaluator from scratch | Port pattern from `SQLBuilder._compile_predicate()` using same match/case structure | Already proven, same predicate types |
| Requirement-to-plan mapping | Manual cross-ref | Read PLAN.md `requirements:` fields for each plan | Already defined, just not copied to SUMMARY |

---

## Common Pitfalls

### Pitfall 1: PLANNING-SUMMARY.md Has No Frontmatter
**What goes wrong:** Attempting to add `requirements-completed:` to `10.1-PLANNING-SUMMARY.md`
which has no YAML frontmatter block at all.
**How to avoid:** Treat it as excluded from the 63-file target. It's a planning artifact,
not a plan execution summary.

### Pitfall 2: requirements_completed Key Spelling
**What goes wrong:** Using `requirements_completed` (underscore) instead of
`requirements-completed` (hyphen).
**How to avoid:** The existing 49 populated files all use `requirements-completed` with a
hyphen. Match that convention.

### Pitfall 3: MockEngine _eval_predicate Column Key Matching
**What goes wrong:** Fixture row keys may not exactly match Lookup.field_name.
For example, `Orders.order_total` has `field_name="order_total"` but the fixture rows use
key `"order_total_dim"` for the dimension-facing column and `"order_total"` for the metric
column. Verify field names match fixture keys before writing assertions.
**How to avoid:** Inspect `mock_data.py` fixture rows carefully. The `order_total` Metric
maps to `"order_total"` key (Decimal). The `is_food_order` Dimension maps to key
`"is_food_order"` (bool). Confirm each field_name before writing the eval.

### Pitfall 4: Decimal Comparison in Python
**What goes wrong:** `Decimal("50") > 50` may behave unexpectedly.
**How to avoid:** Python's `Decimal.__gt__` handles comparison with int correctly
(`Decimal("78.25") > 50` is `True`). This is not a problem; just confirm in tests.

### Pitfall 5: test_filtered_by_dimension doesn't exist in test_queries.py
**What goes wrong:** The roadmap refers to "test_snapshot_queries.py" (old name) and the
test doesn't exist in the current file `tests/integration/test_queries.py`.
**How to avoid:** The plan for 24-04 needs to add the function. Research confirms it was
removed in a prior commit ("test: remove test_filtered_by_dimension until WHERE clause
compiler is implemented"). With 24-01 fixing the MockEngine, this test can be reinstated.

### Pitfall 6: source= in MockEngine predicate evaluation
**What goes wrong:** A field with `source="revenue_usd"` would have `Lookup.source="revenue_usd"`.
The in-memory evaluator must use `source` as the row key when set (not field_name).
**How to avoid:** Mirror `_compile_predicate()`'s logic: use `node.source if node.source
is not None else node.field_name` for the dict key. MockDialect.normalize_identifier() is
identity so no casing is needed.

---

## Code Examples

### MockEngine In-Memory Filter Evaluator Pattern

```python
# In src/cubano/engines/mock.py
# New private function using same structural pattern as SQLBuilder._compile_predicate

from cubano.filters import (
    And, Between, Exact, Gt, Gte, In, IsNull, Like, ILike,
    Lookup, Lt, Lte, Not, NotEqual, Or, Predicate,
    StartsWith, IStartsWith, EndsWith, IEndsWith, IExact,
)

def _eval_predicate(node: Predicate, row: dict[str, Any]) -> bool:
    """Evaluate a Predicate tree against a fixture row dict."""
    match node:
        case And(left=left, right=right):
            return _eval_predicate(left, row) and _eval_predicate(right, row)
        case Or(left=left, right=right):
            return _eval_predicate(left, row) or _eval_predicate(right, row)
        case Not(inner=inner):
            return not _eval_predicate(inner, row)
        case Exact(field_name=f, value=v):
            key = node.source if node.source is not None else f
            return row.get(key) == v
        case Gt(field_name=f, value=v):
            key = node.source if node.source is not None else f
            return row.get(key) > v  # type: ignore[operator]
        # ... etc.
```

Then in `MockEngine.execute()`:
```python
rows = self._fixtures.get(view_name, [])
if query._filters is not None:
    rows = [r for r in rows if _eval_predicate(query._filters, r)]
return rows
```

### Non-Vacuous TestFiltering Assertions

```python
class TestFiltering:
    def test_filter_boolean(self, orders_engine) -> None:
        all_rows = Orders.query().dimensions(Orders.is_food_order).execute()
        filtered = (
            Orders.query()
            .dimensions(Orders.is_food_order)
            .where(Orders.is_food_order == True)  # noqa: E712
            .execute()
        )
        # Filter reduces the result set
        assert len(filtered) < len(all_rows)
        # All returned rows match the filter condition
        assert all(row["is_food_order"] is True for row in filtered)
```

### REQUIREMENTS.md Annotation Pattern for Superseded Requirements

```markdown
### Codegen

<!-- SUPERSEDED: CODEGEN-01–08 describe forward codegen (Python → SQL/YAML) intentionally
deleted in Phase 20-04 (old forward codegen teardown). The shipped behavior is reverse
codegen (warehouse → Python), tracked as CODEGEN-REVERSE and CODEGEN-WAREHOUSE. -->

- [x] **CODEGEN-01**: User can run `cubano codegen` CLI...
```

### SUMMARY.md requirements-completed Field Pattern

```yaml
---
phase: 08-integration-testing
plan: 01
...
requirements-completed: [INT-06]
...
---
```

Plans with no formal requirements:
```yaml
requirements-completed: []
```

---

## Implementation Order for Plans

### 24-01 (TDD — MockEngine WHERE filter fix)
Files affected:
- `src/cubano/engines/mock.py` — add `_eval_predicate()` and wire into `execute()`
- `tests/unit/test_engines.py` — add non-vacuous `TestMockEngineFiltering` class
- `cubano-jaffle-shop/tests/test_mock_queries.py` — update `TestFiltering` assertions

Quality gates: typecheck, lint, format, tests (731 → same or more).

### 24-02 (Text/file edits — dead code + REQUIREMENTS.md bookkeeping)
Files affected:
- `src/cubano/codegen/models.py` — DELETE
- `.planning/REQUIREMENTS.md` — annotate CODEGEN-01–08, fix DOCS-03, fix DOCS-04
- `.planning/phases/19-document-fact-field-type-for-databricks-and-snowflake-users/19-01-PLAN.md` — fix requirements field
- `.planning/phases/19-document-fact-field-type-for-databricks-and-snowflake-users/19-01-SUMMARY.md` — fix requirements-completed field

Quality gates: typecheck (fewer files to check), lint, format, tests (should still pass —
no callers of deleted code), docs build.

### 24-03 (Frontmatter population — 13 SUMMARY.md files)
Files affected: 13 SUMMARY.md files (listed above).
No code changes. No quality gate failures expected. Run typecheck + tests as sanity.

### 24-04 (Snapshot re-record note — add test function)
Files affected:
- `tests/integration/test_queries.py` — add `test_filtered_by_dimension` with docstring
  explaining re-record requirement
- `tests/integration/__snapshots__/test_queries.ambr` — snapshot entry needed or test
  marked appropriately

Quality gates: tests must pass (either with xfail/skip marker, or with new snapshot entry
bootstrapped via MockEngine).

---

## Open Questions

1. **24-01: Option A depth question — how many Lookup types to implement in `_eval_predicate()`?**
   - What we know: 16 Lookup subclasses plus And/Or/Not composites exist
   - What's unclear: Whether LIKE/ILIKE/StartsWith/EndsWith semantics need Python
     equivalents for the TestFiltering tests (the current tests only use `==` and `>`)
   - Recommendation: Implement all types for completeness (the match/case pattern makes
     it easy); the TestFiltering assertions need only Exact and Gt covered.

2. **24-03: What requirements did Phase 09-04 complete?**
   - What we know: PLAN.md says "All 8 CODEGEN requirements covered"; 09-01 claimed
     CODEGEN-01, 09-02 claimed CODEGEN-02/03
   - What's unclear: Whether to attribute CODEGEN-04–08 to 09-04 (test coverage plan)
     or to the plan that implemented each feature
   - Recommendation: 09-04 is the test verification plan; use `requirements-completed:
     [CODEGEN-04, CODEGEN-05, CODEGEN-06, CODEGEN-07, CODEGEN-08]` since tests validated
     them.

3. **24-04: Use xfail or skip for test_filtered_by_dimension?**
   - What we know: After 24-01, MockEngine will apply filtering; the test would "pass"
     with a MockEngine-generated snapshot; Snowflake-specific snapshot needs re-recording
   - What's unclear: Whether the parametrized `[snowflake_engine]` variant will fail in
     CI (no snapshot exists)
   - Recommendation: Add `test_filtered_by_dimension` without xfail/skip, then record
     the MockEngine-based snapshot immediately with `--snapshot-update` using MockEngine
     in replay mode. The Snowflake-engine variant will also use MockEngine in CI replay
     mode (same snapshot). A `# NOTE:` comment in the test body explains the Snowflake
     re-recording need.

---

## Validation Architecture

nyquist_validation is not set in `.planning/config.json` — config has only `mode`,
`depth`, `parallelization`, `commit_docs`, `model_profile`, `workflow`, and `git` keys.
No `workflow.nyquist_validation` key. Skipping the Validation Architecture section.

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `src/cubano/engines/mock.py` — confirmed execute() ignores _filters
- Direct code inspection of `src/cubano/engines/sql.py` — confirmed _compile_predicate() pattern
- Direct code inspection of `src/cubano/filters.py` — confirmed 16 Lookup subclasses
- Direct code inspection of `src/cubano/codegen/models.py` — confirmed dead code, zero callers
- Direct grep of imports — confirmed no callers of `cubano.codegen.models`
- Direct read of `.planning/REQUIREMENTS.md` — confirmed DOCS-03 `.filter()`, DOCS-04 Q-objects text
- Direct read of `19-01-PLAN.md` — confirmed wrong `requirements: [DOCS-04]`
- Direct read of `.planning/v0.2-MILESTONE-AUDIT.md` — confirmed 7 tech debt items
- File count via grep — confirmed 14 SUMMARY.md files missing `requirements-completed`
  (63 total, 49 have it, 14 missing; `10.1-PLANNING-SUMMARY.md` has no frontmatter)
- Git log inspection — confirmed test_filtered_by_dimension was removed in prior commit
- pytest --collect-only — 731 tests currently in suite

### Secondary (MEDIUM confidence)
- `.planning/phases/08-integration-testing/08-*-PLAN.md` — requirements fields per plan
- `cubano-jaffle-shop/tests/fixtures/mock_data.py` — fixture data structure (Decimal,
  bool, has both True/False is_food_order rows, has order_total values above/below 50)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, all in-project
- Architecture: HIGH — all patterns read directly from codebase
- Pitfalls: HIGH — confirmed by code inspection
- Implementation scope: HIGH — 4 narrow, independent work items

**Research date:** 2026-02-26
**Valid until:** Stable (no moving parts; all based on current codebase)
