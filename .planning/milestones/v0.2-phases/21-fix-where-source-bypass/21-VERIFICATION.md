---
phase: 21-fix-where-source-bypass
verified: 2026-02-25T16:00:00Z
status: passed
score: 4/4 must-haves verified
re_verification: false
---

# Phase 21: Fix WHERE source= Bypass — Verification Report

**Phase Goal:** WHERE clause correctly uses the warehouse column name for fields with `source=` overrides, matching the SELECT column name resolution behavior.
**Verified:** 2026-02-25
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `Metric[int](source="revenue_usd")` filtered in `.where()` emits `"revenue_usd"` in SQL WHERE, not the Python attribute name | VERIFIED | `TestWhereClauseSourceOverride::test_metric_with_source_uses_source_in_where` passes; asserts `'"revenue_usd"' in sql` and `'"revenue_usd_field"' not in sql` |
| 2 | SELECT and WHERE column names for the same source=-overridden field are always identical | VERIFIED | `TestWhereClauseSourceOverride::test_select_and_where_column_names_match_when_source_set` passes; `'"revenue_usd"' in sql` confirmed, normalized Python name absent |
| 3 | Fields without source= still receive dialect normalization in the WHERE clause | VERIFIED | `TestWhereClauseSourceOverride::test_field_without_source_where_still_normalized` passes; `Exact("revenue", "US")` with SnowflakeDialect produces `'"REVENUE" = %s'` |
| 4 | All existing WHERE clause normalization tests remain green | VERIFIED | Full suite: 751 passed, 16 skipped, 0 failures |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/cubano/filters.py` | `Lookup` dataclass with `source: str | None = field(default=None, repr=False)` after `value: T` | VERIFIED | Line 105: `source: str | None = field(default=None, repr=False)` — correct field ordering (field_name, value, source), `dataclass, field` imported |
| `src/cubano/fields.py` | All 17 Field operator/method callsites pass `source=self.source` to Lookup constructors | VERIFIED | `grep -c "source=self.source"` returns 17; covers __eq__, __ne__, __lt__, __le__, __gt__, __ge__, between, in_, like, ilike, startswith, istartswith, endswith, iendswith, iexact, isnull, lookup |
| `src/cubano/engines/sql.py` | `_compile_predicate` uses `node.source if node.source is not None else normalize_identifier(f)` in all 16 leaf case branches | VERIFIED | `grep -c "node.source"` returns 16; all branches: Exact, NotEqual, Gt, Gte, Lt, Lte, In, Between, IsNull, StartsWith, IStartsWith, EndsWith, IEndsWith, Like, ILike, IExact |
| `tests/unit/test_sql.py` | `TestWhereClauseSourceOverride` class with 3 test methods (SC-1, SC-2, SC-3) | VERIFIED | Class at line 957; 3 methods confirmed substantive with real assertions, not placeholders |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `fields.py` Field operators (`__gt__` etc.) | `filters.py` `Lookup.source` | `source=self.source` keyword at construction | WIRED | 17 occurrences confirmed; `grep -n "source=self.source"` shows all operator/method return statements updated |
| `engines/sql.py` `_compile_predicate` | `Lookup.source` | `node.source if node.source is not None else normalize_identifier(f)` | WIRED | 16 occurrences confirmed; pattern used in every leaf case branch; In-branch early return for empty value preserved before nf resolution |

### Anti-Patterns Found

None. No TODOs, stubs, placeholder returns, or console.log-only implementations found in modified files.

### Human Verification Required

None. The fix is fully verifiable programmatically:
- Column name resolution is deterministic (no UI, no external service, no real-time behavior)
- All test assertions operate on SQL string output
- Quality gates pass cleanly

### Quality Gate Results

| Gate | Result | Detail |
|------|--------|--------|
| Tests (`uv run --group dev pytest`) | PASSED | 751 passed, 16 skipped, 0 failed |
| `TestWhereClauseSourceOverride` specifically | PASSED | 3/3 tests pass |
| Typecheck (`uv run basedpyright`) | PASSED | 0 errors, 0 warnings, 0 notes |
| Lint (`uv run ruff check`) | PASSED | All checks passed |
| Format (`uv run ruff format --check`) | PASSED | 3 files already formatted |

### STATE.md Update

STATE.md decision updated at line 202:

> [Phase 20.1/21]: WHERE predicates store Python field_name strings AND optional source= override (Lookup.source field with repr=False); column resolution in _compile_predicate mirrors _resolve_col_name: use source verbatim when set, else normalize_identifier(field_name)

Current position block updated: Phase 21 COMPLETE.

### Implementation Correctness

The fix mirrors `_resolve_col_name` exactly (as designed):

```python
# _resolve_col_name (SELECT/ORDER BY) — existing correct logic
def _resolve_col_name(self, field: Any) -> str:
    if field.source is not None:
        return field.source
    return self.dialect.normalize_identifier(field.name)

# _compile_predicate (WHERE) — now matches
nf = node.source if node.source is not None else self.dialect.normalize_identifier(f)
```

Key design choices verified correct:
- `repr=False` on `Lookup.source` preserves all existing repr assertions
- `In` branch: empty-collection early return `"1 = 0", []` correctly placed before `nf` resolution
- Field ordering in `Lookup`: `field_name`, `value`, `source` — default field last, no `TypeError`

---

_Verified: 2026-02-25_
_Verifier: Claude (gsd-verifier)_
