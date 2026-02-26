# Phase 17: Nice Repr for All Public API Classes - Research

**Researched:** 2026-02-23
**Domain:** Python `__repr__` for ORM-style library classes
**Confidence:** HIGH

## Summary

Phase 17 adds informative `__repr__` methods to all public API classes for REPL/IDE ergonomics. The audit of current source reveals a clear split: some classes already have excellent repr (Row, Result, OrderTerm, NullsOrdering, all frozen dataclass Predicate nodes), while others have no custom repr at all (SemanticView classes, Field/Metric/Dimension/Fact). The _Query dataclass has auto-generated repr but it exposes internal field names with underscores and renders Field objects as raw memory addresses.

The implementation is straightforward Python -- no external libraries needed. The primary technique is adding `__repr__` to the `SemanticViewMeta` metaclass (to control `repr(Sales)` for SemanticView subclasses), adding `__repr__` to `Field` base class (inherited by Metric/Dimension/Fact), and replacing `_Query`'s auto-generated dataclass repr with a custom one that shows human-readable state. Predicate nodes (And, Or, Not, Lookup subclasses) already get acceptable dataclass-generated repr, though a SQL-like repr would be a significant readability improvement for deeply nested trees.

**Primary recommendation:** Add `__repr__` to 4 locations (SemanticViewMeta, Field, _Query custom, and optionally human-readable Predicate formatting), write comprehensive tests, update any docstrings that show expected repr output. No new dependencies.

## Current State Audit

### Classes WITH repr (already good)

| Class | Current repr | Quality |
|-------|-------------|---------|
| `Row` | `Row(revenue=1000, country='US')` | Excellent |
| `Result` | `Result(2 rows)` | Good (could add column preview) |
| `OrderTerm` | `OrderTerm(revenue, DESC, NULLS FIRST)` | Excellent |
| `NullsOrdering` | `NULLS FIRST` / `DEFAULT` | Good |
| Lookup subclasses (Exact, Gt, etc.) | `Exact(field_name='country', value='US')` | Good (dataclass auto-repr) |
| And/Or/Not composites | `And(left=Exact(...), right=Gt(...))` | Functional but verbose for deep trees |

### Classes WITHOUT repr (need work)

| Class | Current repr | Problem |
|-------|-------------|---------|
| SemanticView subclass (e.g. `Sales`) | `<class '__main__.Sales'>` | No view name, no field info |
| `Field` | `<cubano.fields.Field object at 0x...>` | No name, no type info |
| `Metric` | `<cubano.fields.Metric object at 0x...>` | No name, no owner info |
| `Dimension` | `<cubano.fields.Dimension object at 0x...>` | No name, no owner info |
| `Fact` | `<cubano.fields.Fact object at 0x...>` | No name, no owner info |
| `_Query` (dataclass auto) | `_Query(_metrics=(<cubano.fields.Metric object at 0x...>, ...))` | Underscore-prefixed fields, memory addresses for Field objects |

## Architecture Patterns

### Pattern 1: Metaclass `__repr__` for SemanticView Classes

`repr(Sales)` is controlled by `type(Sales).__repr__`, which is `SemanticViewMeta.__repr__`. Adding `__repr__` to the metaclass controls how the **class itself** (not instances) renders.

**Target output:**
```
<SemanticView 'Sales' view='sales_view' metrics=[revenue] dimensions=[country] facts=[unit_price]>
```

**Implementation:**
```python
class SemanticViewMeta(type):
    def __repr__(cls) -> str:
        # Skip base SemanticView class (has no _view_name)
        if not hasattr(cls, "_view_name"):
            return super().__repr__()

        fields = getattr(cls, "_fields", {})
        metrics = [n for n, f in fields.items() if isinstance(f, Metric)]
        dims = [n for n, f in fields.items() if isinstance(f, Dimension)]
        facts = [n for n, f in fields.items() if isinstance(f, Fact)]

        parts = [f"view='{cls._view_name}'"]
        if metrics:
            parts.append(f"metrics={metrics}")
        if dims:
            parts.append(f"dimensions={dims}")
        if facts:
            parts.append(f"facts={facts}")

        return f"<SemanticView '{cls.__name__}' {' '.join(parts)}>"
```

**Key constraint:** Must handle the base `SemanticView` class itself (which has no `_view_name`), and should import Metric/Dimension/Fact carefully to avoid circular imports (they are already imported in models.py).

### Pattern 2: Field `__repr__` on Base Class

Add `__repr__` to `Field` base class. Metric, Dimension, and Fact inherit it automatically.

**Target output:**
```
Metric('revenue')          # after __set_name__
Dimension('country')
Fact('unit_price')
Field(unbound)             # before __set_name__ (edge case)
```

**Implementation:**
```python
class Field:
    def __repr__(self) -> str:
        cls_name = type(self).__name__
        if self.name is None:
            return f"{cls_name}(unbound)"
        return f"{cls_name}('{self.name}')"
```

**Decision point:** Whether to include the owner class name, e.g. `Metric('Sales.revenue')` vs `Metric('revenue')`. The shorter form is cleaner for most REPL uses. The owner is available via `self.owner` if needed.

### Pattern 3: Custom `_Query.__repr__`

Override dataclass auto-repr with a human-readable version. The dataclass currently sets `repr=True` by default on `@dataclass(frozen=True)`, and `_model` has `repr=False`.

**Target output:**
```
<Query Sales metrics=[revenue] dimensions=[country] where=(country = 'US') limit=10>
<Query Sales metrics=[revenue, cost] order_by=[revenue DESC]>
<Query (unbound) metrics=[] dimensions=[]>
```

**Implementation approach:** Add explicit `__repr__` method that overrides the dataclass-generated one. Use `repr=False` on the dataclass or just define `__repr__` (which takes precedence over generated repr in Python dataclasses -- actually, dataclasses with `repr=True` generate a `__repr__` method, but an explicitly defined `__repr__` in the class body takes precedence).

**Important:** Since `_Query` uses `@dataclass(frozen=True)`, defining `__repr__` in the class body works fine -- Python's dataclass decorator only generates `__repr__` if the class doesn't already define one when `repr=True`. Actually, this is **wrong** -- dataclass will overwrite a manually defined `__repr__` if `repr=True`. The fix: either set `repr=False` in the decorator, OR define `__repr__` after class creation with `_Query.__repr__ = ...`. The cleanest approach is `@dataclass(frozen=True, repr=False)` and then define `__repr__` normally.

### Pattern 4: Human-Readable Predicate Repr (Optional Enhancement)

The current dataclass repr for predicates is **functionally correct** but verbose for nested trees:

```
And(left=Exact(field_name='country', value='US'), right=Gt(field_name='revenue', value=1000))
```

A SQL-like repr would be more readable:

```
(country = 'US') AND (revenue > 1000)
```

**Trade-off:** SQL-like repr is more readable in REPL but loses round-trip fidelity (can't distinguish `Exact` from `IExact` visually). The dataclass repr IS the round-trip-faithful version. A `__str__` method could provide the SQL-like version while keeping `__repr__` as-is.

**Recommendation:** Leave the current dataclass `__repr__` for Predicate nodes as-is -- it's already good and consistent. If desired, add `__str__` for SQL-like display as a separate enhancement. The phase success criteria says "show filter expressions readably" which the current dataclass repr already achieves for Lookup subclasses. The And/Or/Not composite nodes are verbose but correct.

### Pattern 5: Enhanced Result Repr (Optional)

Current `Result(2 rows)` is clean. Could optionally add column names:

```
Result(2 rows, columns=[revenue, country])
```

This requires inspecting the first row's keys, which is safe since Row stores `_data`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Truncating long lists in repr | Manual string slicing | Standard `reprlib.repr()` | Handles edge cases (nesting, encoding) correctly |
| Recursive repr protection | Manual seen-set tracking | Not needed here | Cubano's object graph has no cycles |

**Key insight:** This phase is pure Python built-in functionality. No external libraries needed. The implementation is 4-5 `__repr__` methods totaling ~30 lines of actual logic.

## Common Pitfalls

### Pitfall 1: Circular Import in SemanticViewMeta.__repr__
**What goes wrong:** Importing Field subclasses (Metric, Dimension, Fact) in the metaclass repr causes import loops since fields.py imports from models.py (or vice versa).
**Why it happens:** models.py already imports `from .fields import Dimension, Fact, Field, Metric` at top level. This is fine because models.py imports from fields.py, not the reverse. The metaclass repr can safely use these imports.
**How to avoid:** Verify that the import direction is `models.py -> fields.py` (which it is). No issue here.

### Pitfall 2: Dataclass Repr Override
**What goes wrong:** Adding `__repr__` inside a `@dataclass(frozen=True)` class body but the dataclass decorator overwrites it.
**Why it happens:** When `repr=True` (the default), Python's `@dataclass` decorator generates and sets `__repr__`, potentially overwriting a manually defined one.
**How to avoid:** Use `@dataclass(frozen=True, repr=False)` and then define `__repr__` in the class body. This is the standard pattern.
**Warning signs:** The custom repr never runs; you see dataclass-style output instead.

### Pitfall 3: Doctest Breakage
**What goes wrong:** Existing doctests that show repr output break when repr format changes.
**Why it happens:** Doctest compares exact string output.
**How to avoid:** Audit all doctests in affected files. Currently, most operator doctests use `# doctest: +SKIP`. The doctests in `models.py` and `query.py` access properties (like `q._model is Orders`, `query._limit_value`), not repr output. OrderTerm doctest in fields.py shows `term.descending` not repr. **Low risk** but must verify after implementation.

### Pitfall 4: Breaking Existing Unit Tests
**What goes wrong:** Tests in `test_results.py` and `test_fields.py` assert on repr content.
**Why it happens:** Tests use `assert "OrderTerm" in repr_str` style assertions.
**How to avoid:** These tests assert substrings, not exact matches. As long as new reprs include the same key information, they pass. But must verify.

### Pitfall 5: SemanticView Base Class Has No _view_name
**What goes wrong:** `repr(SemanticView)` crashes with `AttributeError` if repr accesses `_view_name` unconditionally.
**Why it happens:** `_view_name` is only set by `__init_subclass__` on concrete subclasses, not the base class.
**How to avoid:** Guard with `hasattr(cls, '_view_name')` or check `cls._frozen`.

### Pitfall 6: `_Query._model` is `None` Before `Model.query()` Sets It
**What goes wrong:** repr crashes or shows wrong info for queries created without `Model.query()`.
**Why it happens:** `_model` has `default=None, init=False` -- it's only set via `object.__setattr__` in `Model.query()`.
**How to avoid:** Handle `_model is None` gracefully in repr (show "unbound" or omit model name).

## Testing Strategy

### What to Test

| Class | Test Assertion Pattern | Notes |
|-------|----------------------|-------|
| SemanticView subclass | `"Sales"` and `"sales_view"` in repr | Test metaclass repr |
| SemanticView base class | Does not crash | Edge case |
| Field (unbound) | `"unbound"` or similar in repr | Before `__set_name__` |
| Metric | `"Metric"` and `"revenue"` in repr | After `__set_name__` |
| Dimension | `"Dimension"` and `"country"` in repr | After `__set_name__` |
| Fact | `"Fact"` and `"unit_price"` in repr | After `__set_name__` |
| _Query (bound) | Model name, metrics, dimensions in repr | Via `Model.query()` |
| _Query (unbound) | Does not crash, shows "unbound" | Direct construction |
| _Query with filters | Filter info appears | Via `.where()` |

### Existing Tests That Assert on Repr

1. `tests/unit/test_fields.py:269` -- `test_order_term_repr`: asserts `"OrderTerm"`, `"revenue"`, `"DESC"`, `"NULLS FIRST"` in repr. **Safe** -- OrderTerm repr is not changing.
2. `tests/unit/test_results.py:111` -- `test_repr`: asserts `"Row("`, `"revenue=1000"`, `"country='US'"`. **Safe** -- Row repr is not changing.
3. `tests/unit/test_results.py:304` -- `test_result_repr_non_empty`: asserts `"Result"`, `"2 rows"`. **Safe** -- Result repr may optionally add columns but will still contain these.
4. `tests/unit/test_results.py:311` -- `test_result_repr_empty`: asserts `"Result"`, `"0 rows"`. **Safe** -- same reasoning.

### Testing Pattern

Use substring assertions (`assert "keyword" in repr_str`) rather than exact string matching. This is the pattern already used in the test suite and is resilient to minor format changes.

## Implementation Scope

### Must Change (Success Criteria 1-5)

| File | Change | Complexity |
|------|--------|-----------|
| `src/cubano/models.py` | Add `__repr__` to `SemanticViewMeta` | Low -- ~10 lines |
| `src/cubano/fields.py` | Add `__repr__` to `Field` base class | Low -- ~4 lines |
| `src/cubano/query.py` | Add `__repr__` to `_Query`, set `repr=False` in decorator | Medium -- ~15 lines |
| `tests/unit/test_models.py` | Add repr tests for SemanticView subclass and base | Low |
| `tests/unit/test_fields.py` | Add repr tests for Metric/Dimension/Fact | Low |
| `tests/unit/test_query.py` | Add repr tests for _Query states | Low |

### May Optionally Change (Success Criteria 6)

| File | Change | Complexity |
|------|--------|-----------|
| `src/cubano/results.py` | Enhance `Result.__repr__` with column names | Low -- ~3 lines |
| `tests/unit/test_results.py` | Update/add repr test for enhanced Result | Low |

### Should NOT Change

| File | Reason |
|------|--------|
| `src/cubano/filters.py` | Dataclass auto-repr is already good for all Predicate nodes |
| `src/cubano/results.py` (Row) | Already has excellent repr |
| `src/cubano/fields.py` (OrderTerm) | Already has excellent custom repr |
| `src/cubano/fields.py` (NullsOrdering) | Already has excellent custom repr |

## Code Examples

### SemanticViewMeta.__repr__

```python
# In models.py - SemanticViewMeta class
def __repr__(cls) -> str:
    """Return informative repr for SemanticView subclasses."""
    if not hasattr(cls, "_view_name"):
        return super().__repr__()

    fields_dict: dict[str, Field] = dict(cls._fields)
    metrics = [n for n, f in fields_dict.items() if isinstance(f, Metric)]
    dims = [n for n, f in fields_dict.items() if isinstance(f, Dimension)]
    facts = [n for n, f in fields_dict.items() if isinstance(f, Fact)]

    parts = [f"view='{cls._view_name}'"]
    if metrics:
        parts.append(f"metrics={metrics}")
    if dims:
        parts.append(f"dimensions={dims}")
    if facts:
        parts.append(f"facts={facts}")

    return f"<SemanticView '{cls.__name__}' {' '.join(parts)}>"
```

**Expected output:**
```
<SemanticView 'Sales' view='sales_view' metrics=['revenue'] dimensions=['country'] facts=['unit_price']>
```

### Field.__repr__

```python
# In fields.py - Field class
def __repr__(self) -> str:
    """Return informative repr showing field type and name."""
    cls_name = type(self).__name__
    if self.name is None:
        return f"{cls_name}(unbound)"
    return f"{cls_name}('{self.name}')"
```

**Expected output:**
```
Metric('revenue')
Dimension('country')
Fact('unit_price')
```

### _Query.__repr__

```python
# In query.py - _Query class, with @dataclass(frozen=True, repr=False)
def __repr__(self) -> str:
    """Return human-readable query state."""
    model_name = self._model.__name__ if self._model else "unbound"

    parts = [f"model={model_name}"]

    if self._metrics:
        names = [f.name for f in self._metrics]
        parts.append(f"metrics={names}")

    if self._dimensions:
        names = [f.name for f in self._dimensions]
        parts.append(f"dimensions={names}")

    if self._filters is not None:
        parts.append(f"where={self._filters!r}")

    if self._order_by_fields:
        order_parts = []
        for f in self._order_by_fields:
            if isinstance(f, OrderTerm):
                order_parts.append(repr(f))
            else:
                order_parts.append(f.name or "?")
        parts.append(f"order_by=[{', '.join(order_parts)}]")

    if self._limit_value is not None:
        parts.append(f"limit={self._limit_value}")

    if self._using is not None:
        parts.append(f"using='{self._using}'")

    return f"<Query {' '.join(parts)}>"
```

**Expected output:**
```
<Query model=Sales metrics=['revenue'] dimensions=['country'] where=Exact(field_name='country', value='US') limit=10>
<Query model=unbound>
```

### Enhanced Result.__repr__ (Optional)

```python
# In results.py - Result class
def __repr__(self) -> str:
    """Return string representation with shape info."""
    if self.rows:
        cols = list(self.rows[0].keys())
        return f"Result({len(self.rows)} rows, columns={cols})"
    return f"Result(0 rows)"
```

**Expected output:**
```
Result(2 rows, columns=['revenue', 'country'])
Result(0 rows)
```

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Default Python `<class 'X'>` for classes | Metaclass `__repr__` for informative class repr | Standard pattern in Django, SQLAlchemy |
| Default `<object at 0x>` for descriptors | Custom `__repr__` on descriptor base class | Standard pattern in all major ORMs |
| Dataclass auto-repr with internal names | Custom `__repr__` with `repr=False` on dataclass | Clean separation of internal structure from display |

Python convention (per `reprlib` docs and PEP 3110 discussions): `__repr__` should be unambiguous and developer-oriented. For library classes, showing the class name and key identifying attributes is the standard.

## Open Questions

1. **SemanticView repr format -- angle brackets vs constructor style?**
   - Options: `<SemanticView 'Sales' view='sales_view' ...>` vs `Sales(view='sales_view', ...)`
   - Recommendation: Angle bracket style (like `<class ...>`) since SemanticView classes are not directly constructible -- they use `class Sales(SemanticView, view=...)` syntax, so constructor-style repr would be misleading.

2. **Should `Field.__repr__` include owner name?**
   - Options: `Metric('revenue')` vs `Metric('Sales.revenue')`
   - Recommendation: Short form `Metric('revenue')` -- the owner is obvious from context in REPL. The owner is still available via `field.owner`.

3. **Predicate repr enhancement -- defer or include?**
   - Current dataclass repr works. SQL-like `__str__` would be nice but is a separate concern.
   - Recommendation: Defer. Current repr satisfies success criterion 4 ("show filter expressions readably"). SQL-like display can be a future enhancement.

4. **Result repr enhancement -- add columns?**
   - Adding columns to `Result(2 rows, columns=[...])` is a small win.
   - Recommendation: Include. Low risk, high value for debugging.

## Sources

### Primary (HIGH confidence)
- Direct source code audit of all files in `src/cubano/` -- verified current repr state
- Python documentation on `__repr__`, metaclass methods, and dataclass `repr` parameter
- Live testing of current repr output via `uv run python -c ...`

### Secondary (MEDIUM confidence)
- [DigitalOcean Python repr guide](https://www.digitalocean.com/community/tutorials/python-str-repr-functions) -- best practices
- [Real Python repr vs str](https://realpython.com/python-repr-vs-str/) -- when to use which
- [Python dataclasses docs](https://docs.python.org/3/library/dataclasses.html) -- repr parameter behavior

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no external libraries needed, pure Python
- Architecture: HIGH -- well-established metaclass `__repr__` and descriptor `__repr__` patterns
- Pitfalls: HIGH -- verified via live code testing, import graph analysis, existing test audit

**Research date:** 2026-02-23
**Valid until:** 2026-06-23 (stable -- pure Python patterns, no dependency concerns)
