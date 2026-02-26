# Phase 21: Fix WHERE Clause source= Bypass - Research

**Researched:** 2026-02-25
**Domain:** SQL WHERE clause compilation, Lookup IR, Field descriptor source= parameter
**Confidence:** HIGH

## Summary

Phase 21 closes a correctness gap introduced in Phase 20.1: when a `Field` descriptor is defined with an explicit `source=` override, that override is correctly used in the SELECT and ORDER BY clauses (via `_resolve_col_name`) but is silently ignored in the WHERE clause (via `_compile_predicate`). The result is that a field defined as `revenue_usd = Metric[int](source="revenue_usd")` will emit `"REVENUE_USD"` (Snowflake-normalized Python name) in WHERE, while emitting `"revenue_usd"` (the source value) in SELECT — causing a SQL column name mismatch.

The root cause is architectural: the `Lookup` frozen dataclass in `filters.py` stores only `field_name: str` (the Python attribute name). Field operator methods (`__eq__`, `__gt__`, etc.) populate this with `self.name` — they have no mechanism to propagate `self.source`. At compile time, `_compile_predicate` applies `dialect.normalize_identifier(field_name)` to all lookups, which is correct when `source=None` but wrong when a `source=` override exists.

The fix requires adding `source: str | None = None` to the `Lookup` dataclass and updating all Field operator methods to pass `source=self.source` when constructing lookup nodes. `_compile_predicate` then mirrors `_resolve_col_name`'s logic: use `source` verbatim when set, otherwise apply `normalize_identifier`. This is a contained, surgical change with zero breaking API impact.

**Primary recommendation:** Add `source: str | None = None` to `Lookup`, update all 12 Field operator/method callsites to pass `source=self.source`, and mirror `_resolve_col_name` logic inside `_compile_predicate`.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python dataclasses | stdlib | `Lookup` IR node with frozen=True | Already used for all IR nodes |
| pytest | in dev deps | TDD regression test | Project standard |

No new dependencies required. This is a pure internal code fix.

## Architecture Patterns

### Current Flow (broken)

```
User code:
    revenue_usd = Metric[int](source="revenue_usd")
    ...where(MyView.revenue_usd > 100)

Field.__gt__:
    name = _check_name(self.name)     # "revenue_usd" (Python attr name)
    return Gt(field_name=name, value=100)
    # self.source ("revenue_usd") is NOT passed

_compile_predicate:
    case Gt(field_name=f, value=v):
        nf = self.dialect.normalize_identifier(f)   # "REVENUE_USD" (Snowflake)
        return f"{q(nf)} > {ph}", [v]
        # emits "REVENUE_USD" > %s  ← WRONG for source= fields
```

### Correct Flow (after fix)

```
Field.__gt__:
    name = _check_name(self.name)     # "revenue_usd"
    return Gt(field_name=name, source=self.source, value=100)
    # source="revenue_usd" is propagated

_compile_predicate:
    case Gt(field_name=f, value=v):
        nf = node.source if node.source is not None else self.dialect.normalize_identifier(f)
        return f"{q(nf)} > {ph}", [v]
        # emits "revenue_usd" > %s  ← CORRECT
```

### Pattern: Mirror _resolve_col_name

`_resolve_col_name` already has the correct logic for SELECT/ORDER BY:

```python
def _resolve_col_name(self, field: Any) -> str:
    assert field.name is not None
    if field.source is not None:
        return field.source
    return self.dialect.normalize_identifier(field.name)
```

The WHERE compiler must implement the same logic. The cleanest approach is to inline an equivalent expression inside each `case` branch in `_compile_predicate`, since the `case` pattern matching extracts `field_name=f` (the Python name). The source value must be accessed via `node.source` (not the pattern-matched `f`).

### Pattern: Frozen dataclass default field

`Lookup` is `@dataclass(frozen=True)`. Adding `source: str | None = None` with a default is valid Python dataclass syntax and backward-compatible — existing code constructing `Lookup(field_name="x", value=v)` continues to work unchanged, defaulting `source=None`.

```python
@dataclass(frozen=True)
class Lookup(Predicate, Generic[T]):
    field_name: str
    value: T
    source: str | None = None  # ← new field with default
```

The `source` field must come AFTER `value` because dataclass fields with defaults must follow fields without defaults. Both `field_name` and `value` are required (no default), so appending `source: str | None = None` at the end is valid.

### Pattern: _compile_predicate source resolution

Inside `_compile_predicate`, after the `case` pattern extracts `field_name=f`, access `node.source` for the source override. The matched variable `node` refers to the full dataclass instance:

```python
case Exact(field_name=f, value=v):
    nf = node.source if node.source is not None else self.dialect.normalize_identifier(f)
    return f"{q(nf)} = {ph}", [v]
```

However, there is a subtlety: in Python `match/case`, the bound name for the node is the variable being matched. Looking at the existing code, the match is `match node:` — so `node` is available inside each case branch.

### Pattern: Field operator methods pass source=

All 12 operator/method callsites in `fields.py` currently follow this pattern:

```python
def __eq__(self, value: Any) -> Exact:
    name = _check_name(self.name)
    from .filters import Exact as _Exact
    return _Exact(field_name=name, value=value)
```

Must become:

```python
def __eq__(self, value: Any) -> Exact:
    name = _check_name(self.name)
    from .filters import Exact as _Exact
    return _Exact(field_name=name, value=value, source=self.source)
```

The 12 affected methods are:
1. `__eq__` (Exact)
2. `__ne__` (NotEqual)
3. `__lt__` (Lt)
4. `__le__` (Lte)
5. `__gt__` (Gt)
6. `__ge__` (Gte)
7. `between` (Between)
8. `in_` (In)
9. `like` (Like)
10. `ilike` (ILike)
11. `startswith` (StartsWith)
12. `istartswith` (IStartsWith)
13. `endswith` (EndsWith)
14. `iendswith` (IEndsWith)
15. `iexact` (IExact)
16. `isnull` (IsNull)
17. `lookup` (arbitrary Lookup subclass — cannot pass source= here without changing signature)

Note: `lookup()` is an escape hatch that constructs an arbitrary `Lookup` subclass. It should also pass `source`, but the current `lookup_cls(field_name=name, value=value)` call cannot pass `source=` unless `Lookup` has `source` in its constructor. Since `Lookup` will gain `source: str | None = None`, the `lookup()` method can pass it as well.

### Anti-Patterns to Avoid

- **Storing source-resolved names in Lookup IR**: Do not store the SQL column name (e.g., `"revenue_usd"`) directly in `Lookup.field_name`. The IR should always store the Python field name for debuggability. `source` is a separate override field.
- **Calling `_resolve_col_name` from `_compile_predicate`**: `_resolve_col_name` takes a `Field` object. `_compile_predicate` only has a `Predicate` node — it does not have access to the model class or Field objects. Pass `source` through the IR instead.
- **Normalizing `source` values**: The `source=` value is used verbatim — never apply `normalize_identifier` to it. This is consistent with `_resolve_col_name`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Column name resolution | Custom lookup table mapping Python name to SQL name | `Lookup.source` field propagated from `Field.source` | Simpler, no additional state, no model reference needed |
| Model introspection at compile time | Pass model class to `_compile_predicate` to look up Field objects | `source` field on `Lookup` IR | IR is self-contained; no model class dependency |

## Common Pitfalls

### Pitfall 1: source field ordering in Lookup dataclass

**What goes wrong:** Adding `source: str | None = None` before `value: T` causes `TypeError: non-default argument 'value' follows default argument`.

**Why it happens:** Python dataclass fields with defaults must come after fields without defaults.

**How to avoid:** Add `source` AFTER `value`. The order is: `field_name: str`, `value: T`, `source: str | None = None`.

**Warning signs:** `dataclasses.dataclass` raises `TypeError` at class definition time.

### Pitfall 2: match/case variable access for source

**What goes wrong:** Inside `case Exact(field_name=f, value=v):`, trying to access `node.source` fails because `node` was not captured. In the current code, the match variable is `node`.

**Why it happens:** Python `match/case` — pattern match captures sub-fields as local variables but the original node is accessible by its original name (`node`) from the `match node:` statement.

**How to avoid:** Access `node.source` directly. The match statement is `match node:` so `node` is the full Predicate instance in every `case` branch.

**Confirmation:** The current `_compile_predicate` code at line 573 uses `type(cast("object", node)).__name__` inside the catch-all branch, confirming that `node` is accessible throughout all `case` branches.

### Pitfall 3: lookup() escape hatch

**What goes wrong:** `lookup()` constructs an arbitrary `Lookup` subclass via `lookup_cls(field_name=name, value=value)`. If the subclass does not accept `source=`, this fails.

**Why it happens:** `Lookup` is the base class; all subclasses inherit its fields. After adding `source: str | None = None` to `Lookup`, all subclasses automatically gain it. The call `lookup_cls(field_name=name, value=value, source=self.source)` is valid.

**How to avoid:** Update `lookup()` to pass `source=self.source`.

### Pitfall 4: Existing test assertions for predicate repr

**What goes wrong:** Changing `Lookup` dataclass schema may change `repr()` output (frozen dataclasses auto-generate `__repr__` including all fields). Existing test assertions like `assert repr(pred) == "Exact(field_name='country', value='US')"` will fail if `source=None` appears in repr.

**Why it happens:** `dataclasses` auto-repr includes all fields by default, including `source=None`.

**How to avoid:** Either: (a) check whether tests assert on `repr(Lookup(...))` output and update them, OR (b) add `repr=False` to the `source` field definition via `dataclasses.field(default=None, repr=False)` to exclude it from repr when None.

**Recommendation:** Use `dataclasses.field(default=None, repr=False)` to preserve existing repr output. This matches the project's existing pattern of `_model: type | None = field(default=None, init=False, repr=False)` in `_Query`. Source is metadata about the SQL binding, not the logical identity of the predicate.

Check existing repr assertions:

```bash
grep -r "repr.*Exact\|Exact.*repr\|assert.*Lookup\|assert.*Exact\|assert.*Gt\|assert.*Gte" tests/
```

## Code Examples

### Lookup dataclass change

```python
# filters.py
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")

@dataclass(frozen=True)
class Lookup(Predicate, Generic[T]):
    """
    Typed leaf node for field comparisons.

    Every lookup has a ``field_name`` (the Python attribute name),
    a ``value`` (the comparison operand), and an optional ``source``
    (the explicit SQL column name override from Field.source=).
    """

    field_name: str
    value: T
    source: str | None = field(default=None, repr=False)
```

### Field operator update (example: __eq__)

```python
# fields.py
def __eq__(self, value: Any) -> Exact:
    name = _check_name(self.name)
    from .filters import Exact as _Exact
    return _Exact(field_name=name, value=value, source=self.source)
```

### _compile_predicate fix (example: Exact case)

```python
# engines/sql.py — inside _compile_predicate
case Exact(field_name=f, value=v):
    nf = node.source if node.source is not None else self.dialect.normalize_identifier(f)
    return f"{q(nf)} = {ph}", [v]
```

### Regression test shape (failing first, then passing)

```python
# tests/unit/test_sql.py — new TestClass

class TestWhereClauseSourceOverride:
    """Regression tests: source= override propagates through WHERE clause compiler."""

    def test_metric_with_source_uses_source_in_where(self):
        """Metric(source='revenue_usd') WHERE emits 'revenue_usd', not normalized name."""
        from cubano import Metric, SemanticView

        class MyView(SemanticView, view="my_view"):
            revenue_usd_field = Metric[int](source="revenue_usd")

        query = MyView.query().metrics(MyView.revenue_usd_field).where(
            MyView.revenue_usd_field > 100
        )
        sql = query.to_sql()
        assert '"revenue_usd"' in sql   # source= value used verbatim
        assert '"revenue_usd_field"' not in sql  # Python name NOT used
        assert '"REVENUE_USD_FIELD"' not in sql  # Snowflake-normalized Python name NOT used

    def test_select_and_where_column_names_match_when_source_set(self):
        """SELECT and WHERE use identical column names for fields with source=."""
        ...

    def test_field_without_source_where_still_normalized(self):
        """Field without source= still gets dialect normalization in WHERE."""
        ...
```

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|-----------------|-------|
| `_compile_predicate` uses `normalize_identifier(field_name)` | After fix: uses `source if source is not None else normalize_identifier(field_name)` | Mirrors `_resolve_col_name` exactly |

**Gap introduced in:** Phase 20.1 (when `source=` parameter was added to `Field` and `_resolve_col_name` was added for SELECT/ORDER BY — but `_compile_predicate` was not updated to match)

**The relevant Phase 20.1 decision to update:**
> [Phase 20.1]: WHERE predicates store Python field_name strings; normalize_identifier applied at compile time in _compile_predicate (not stored in predicate IR)

After this fix, this should become:
> WHERE predicates store Python field_name strings AND optional source= override; column resolution in _compile_predicate mirrors _resolve_col_name (source if set, else normalize_identifier)

## Open Questions

1. **repr= on source field**
   - What we know: Python dataclasses auto-include all fields in repr by default
   - What's unclear: Whether any existing test assertions check `repr(Lookup(...))` output that would break
   - Recommendation: Use `field(default=None, repr=False)` proactively to exclude `source=None` from repr. If tests assert on repr output, they will remain green. Check with grep before deciding.

2. **lookup() escape hatch behavior**
   - What we know: `lookup()` currently constructs `lookup_cls(field_name=name, value=value)` without `source=`
   - What's unclear: Whether users who have subclassed `Lookup` with positional-only constructors would be affected
   - Recommendation: Since `Lookup.source` has a default of `None`, existing `lookup_cls(field_name=name, value=value)` calls still work. Updating `lookup()` to also pass `source=self.source` is the correct improvement.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml |
| Quick run command | `uv run --extra dev pytest tests/unit/test_sql.py tests/unit/test_fields.py -x` |
| Full suite command | `uv run --extra dev pytest` |
| Estimated runtime | ~0.1 seconds (unit), ~5 seconds (full suite) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SC-1 | `Metric[int](source="revenue_usd")` WHERE emits `revenue_usd` | unit | `pytest tests/unit/test_sql.py::TestWhereClauseSourceOverride -x` | ❌ Wave 0 gap |
| SC-2 | SELECT and WHERE column names identical when source= set | unit | `pytest tests/unit/test_sql.py::TestWhereClauseSourceOverride -x` | ❌ Wave 0 gap |
| SC-3 | Regression test for field-with-source= + WHERE | unit | `pytest tests/unit/test_sql.py::TestWhereClauseSourceOverride -x` | ❌ Wave 0 gap |

### Nyquist Sampling Rate
- **Minimum sample interval:** After each committed task → run: `uv run --extra dev pytest tests/unit/test_sql.py tests/unit/test_fields.py -x`
- **Full suite trigger:** Before final commit of the plan
- **Phase-complete gate:** Full suite green before verification
- **Estimated feedback latency per task:** ~0.1 seconds

### Wave 0 Gaps (must be created before implementation)
- [ ] `tests/unit/test_sql.py::TestWhereClauseSourceOverride` — new test class covering SC-1, SC-2, SC-3 (add to existing file)

*(Existing test infrastructure and file exist — only new test methods needed, no new files)*

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `/Users/paul/Documents/Dev/Personal/cubano/src/cubano/engines/sql.py` — `_compile_predicate` and `_resolve_col_name` methods, confirmed behavior
- Direct code inspection of `/Users/paul/Documents/Dev/Personal/cubano/src/cubano/filters.py` — `Lookup` dataclass schema confirmed
- Direct code inspection of `/Users/paul/Documents/Dev/Personal/cubano/src/cubano/fields.py` — all 17 operator/method callsites inspected
- Direct code inspection of `/Users/paul/Documents/Dev/Personal/cubano/tests/unit/test_sql.py` — confirmed `TestWhereClauseNormalization` tests call `_compile_predicate` directly with raw strings (not Field objects), test pattern confirmed
- `.planning/STATE.md` decision: `[Phase 20.1]: WHERE predicates store Python field_name strings; normalize_identifier applied at compile time in _compile_predicate (not stored in predicate IR)` — confirms the design intent and identifies when the gap was introduced
- Python dataclasses docs (stdlib) — field ordering rules for defaults confirmed

### Secondary (MEDIUM confidence)
- Python `match/case` semantics — `node` in `match node:` is accessible in all case branches, confirmed by existing code at line 573 using `type(cast("object", node)).__name__`

## Metadata

**Confidence breakdown:**
- Bug identification: HIGH — confirmed by direct code reading
- Fix approach: HIGH — mirrors existing `_resolve_col_name` pattern exactly
- Implementation scope: HIGH — 3 files affected (filters.py, fields.py, engines/sql.py), all changes are additive/surgical
- Test strategy: HIGH — TDD with failing test first, then fix

**Research date:** 2026-02-25
**Valid until:** Until Phase 21 is implemented (no external dependencies, pure internal code change)
