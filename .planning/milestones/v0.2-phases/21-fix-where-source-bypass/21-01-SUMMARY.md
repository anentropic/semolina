---
phase: 21-fix-where-source-bypass
plan: "01"
subsystem: sql-generation
tags: [filters, predicate-ir, where-clause, source-override, tdd, sql-builder]

# Dependency graph
requires:
  - phase: 20.1-implement-filter-lookup-system-and-where-clause-compiler
    provides: "source= parameter on Field, _resolve_col_name for SELECT/ORDER BY, Lookup IR, _compile_predicate"
provides:
  - "Lookup.source field propagates source= override through WHERE clause IR"
  - "All 17 Field operator/method callsites pass source=self.source to Lookup constructors"
  - "_compile_predicate uses source verbatim when set (mirrors _resolve_col_name)"
  - "TestWhereClauseSourceOverride: 3 regression tests confirming WHERE/SELECT column name consistency"
affects: [sql-generation, filters, engines, where-clause, future-predicates]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "source-aware column resolution: node.source if node.source is not None else normalize_identifier(f)"
    - "repr=False on optional Lookup fields to preserve existing repr assertions"
    - "TDD: failing tests committed before fix, confirms bug exists before implementation"

key-files:
  created:
    - .planning/phases/21-fix-where-source-bypass/21-01-SUMMARY.md
  modified:
    - src/cubano/filters.py
    - src/cubano/fields.py
    - src/cubano/engines/sql.py
    - tests/unit/test_sql.py

key-decisions:
  - "repr=False on Lookup.source preserves all existing repr assertions — source is metadata about SQL binding, not predicate identity"
  - "node.source accessed via match variable (not pattern-extracted f) because match node: makes full instance available in all case branches"
  - "Multiline ternary (parens wrapping) used for 101-char source resolution expression to satisfy ruff E501"
  - "Field ordering in Lookup dataclass: field_name, value, source — default fields must follow non-default fields"

patterns-established:
  - "Mirror pattern: _compile_predicate source resolution mirrors _resolve_col_name exactly"

requirements-completed: []

# Metrics
duration: 9min
completed: 2026-02-25
---

# Phase 21 Plan 01: Fix WHERE source= Bypass Summary

**Lookup.source field added and propagated through all 17 Field operators and 16 _compile_predicate branches, making WHERE/SELECT column names consistent for source=-overridden fields**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-25T15:27:32Z
- **Completed:** 2026-02-25T15:36:00Z
- **Tasks:** 3 (TDD: RED + GREEN + refactor)
- **Files modified:** 4

## Accomplishments

- Added `source: str | None = field(default=None, repr=False)` to `Lookup` dataclass in filters.py — backward-compatible, preserves all existing repr output
- Updated all 17 Field operator/method callsites in fields.py to pass `source=self.source` to Lookup constructors
- Updated all 16 leaf case branches in `_compile_predicate` to use `node.source if node.source is not None else dialect.normalize_identifier(f)` — mirrors `_resolve_col_name` exactly
- Added `TestWhereClauseSourceOverride` class with 3 regression tests (SC-1, SC-2, SC-3) — tests were committed failing first (TDD RED), then made green by the fix

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing regression tests (RED)** - `d125990` (test)
2. **Task 2: Fix Lookup dataclass and propagate source= (GREEN)** - `c12b2b6` (fix)
3. **Task 3: Update STATE.md decision and create SUMMARY** - (this commit)

## Files Created/Modified

- `src/cubano/filters.py` - Added `field` to dataclasses import; added `source: str | None = field(default=None, repr=False)` to Lookup after `value: T`; updated docstring
- `src/cubano/fields.py` - All 17 operator/method return statements now pass `source=self.source`
- `src/cubano/engines/sql.py` - Comment block updated to describe source-aware resolution; all 16 leaf case branches use `node.source if node.source is not None else normalize_identifier(f)`
- `tests/unit/test_sql.py` - Added `TestWhereClauseSourceOverride` class with SC-1, SC-2, SC-3 test methods

## Decisions Made

- **repr=False on Lookup.source** — preserves all existing repr assertions (`Exact(field_name='country', value='US')` not changed). Source is metadata about SQL binding, not the logical identity of the predicate. Consistent with project pattern of `field(default=None, repr=False)` on internal fields.
- **node.source access via match variable** — Python `match node:` makes `node` (full instance) accessible in all case branches. Pattern match captures sub-fields as `f`, `v` but `node.source` accesses the whole instance attribute, correctly bypassing the `f` variable which holds only `field_name`.
- **Multiline ternary** — expression `node.source if node.source is not None else self.dialect.normalize_identifier(f)` is 101 chars with indentation; wrapped in parens and reformatted by `ruff format` to keep inner line at exactly 100 chars.

## Deviations from Plan

None — plan executed exactly as written. Three files changed as specified, 17 callsites updated, 16 case branches updated. The only minor deviation was discovering the line-length violation during Task 2 and wrapping the ternary expression (Rule 2-level auto-fix, no user decision needed).

## Issues Encountered

- Line length: the source-aware resolution expression was 101 chars. Fixed by wrapping in parentheses; `ruff format` produced the correct 100-char inner line automatically.
- Test command: `uv run --extra dev pytest` failed because dev is in `[dependency-groups]` not `[optional-dependencies]` — correct command is `uv run --group dev pytest`.

## Next Phase Readiness

- WHERE/SELECT column name consistency is now guaranteed for all source=-overridden fields
- All 731 tests pass, 0 typecheck errors, lint clean, format clean
- No blockers for subsequent phases

## Self-Check: PASSED

- filters.py: FOUND (source field with repr=False: 1 occurrence)
- fields.py: FOUND (source=self.source: 17 occurrences)
- sql.py: FOUND (node.source resolution: 16 occurrences)
- test_sql.py: FOUND (TestWhereClauseSourceOverride: 1 class)
- SUMMARY.md: FOUND
- Commit d125990 (test): FOUND
- Commit c12b2b6 (fix): FOUND

---
*Phase: 21-fix-where-source-bypass*
*Completed: 2026-02-25*
