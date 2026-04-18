# Phase 28: Query Shorthand - Research

**Researched:** 2026-03-17
**Domain:** Python API design, frozen dataclass mutation, type annotations
**Confidence:** HIGH

## Summary

Phase 28 adds keyword arguments `metrics=` and `dimensions=` to `SemanticView.query()` so users can write concise one-liner queries like `Sales.query(metrics=[Sales.revenue], dimensions=[Sales.region])`. The existing builder methods (`.metrics()`, `.dimensions()`) must remain additive -- calling `.metrics(Sales.cost)` after `query(metrics=[Sales.revenue])` selects both.

This is a small, well-contained change touching exactly two files (`models.py` and `query.py`) plus their corresponding test files. The implementation leverages the existing immutable `_Query` dataclass and tuple-concatenation pattern already used by `.metrics()` and `.dimensions()`.

**Primary recommendation:** Accept optional `metrics` and `dimensions` keyword args in `SemanticView.query()`, pass them to `_Query` constructor as initial tuple values. The existing `.metrics()` / `.dimensions()` methods already concatenate tuples, so additivity is automatic with zero changes to those methods.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| QAPI-01 | `query(metrics=[...], dimensions=[...])` shorthand accepted as keyword args | Modify `SemanticView.query()` signature and `_Query` constructor to accept initial metrics/dimensions tuples |
| QAPI-02 | Builder methods (`.metrics()`, `.dimensions()`) are additive with args passed to `query()` | Already works -- `.metrics()` uses `self._metrics + fields` tuple concatenation; if `_metrics` starts non-empty from `query()`, additivity is automatic |
</phase_requirements>

## Standard Stack

No new dependencies required. This phase modifies existing code only.

### Core (already in project)
| Library | Version | Purpose | Relevance |
|---------|---------|---------|-----------|
| basedpyright | (project tool) | Strict type checking | Must type-annotate new kwargs correctly |
| ruff | (project tool) | Lint + format | Must pass check + format |
| pytest | (project dev dep) | Tests | New test class for shorthand behavior |

## Architecture Patterns

### Current Architecture (key files)

```
src/semolina/
  models.py      # SemanticView.query() classmethod -- entry point
  query.py       # _Query frozen dataclass -- builder pattern
  fields.py      # Metric, Dimension, Fact field descriptors
```

### Pattern: Frozen Dataclass with Initial Values

The `_Query` dataclass is `frozen=True`. Its fields default to empty tuples:

```python
@dataclass(frozen=True, repr=False)
class _Query:
    _metrics: tuple[Metric[Any], ...] = field(default_factory=tuple)
    _dimensions: tuple[Dimension[Any] | Fact[Any], ...] = field(default_factory=tuple)
    # ... other fields ...
```

`SemanticView.query()` currently creates a `_Query` and sets `_model` via `object.__setattr__`:

```python
@classmethod
def query(cls, using: str | None = None) -> "_Query":
    from .query import _Query as QueryImpl
    q = QueryImpl(_using=using)
    object.__setattr__(q, "_model", cls)
    return q
```

### Recommended Implementation Pattern

**Approach: Pass initial values to `_Query` constructor**

Since `_Query` is a frozen dataclass, its `__init__` already accepts `_metrics` and `_dimensions` as constructor args. The change is to:

1. Add `metrics` and `dimensions` kwargs to `SemanticView.query()`
2. Validate them (type check each element)
3. Pass as `_metrics=tuple(metrics)` and `_dimensions=tuple(dimensions)` to `_Query()`

```python
# models.py
@classmethod
def query(
    cls,
    *,
    metrics: list[Metric[Any]] | None = None,
    dimensions: list[Dimension[Any] | Fact[Any]] | None = None,
    using: str | None = None,
) -> "_Query":
    from .query import _Query as QueryImpl

    # Validate and convert
    m: tuple[Metric[Any], ...] = ()
    if metrics is not None:
        for f in metrics:
            if not isinstance(f, Metric):
                raise TypeError(
                    f"metrics requires Metric fields, got {type(f).__name__}. "
                    f"Did you mean dimensions=?"
                )
            if f.owner != cls:
                raise TypeError(
                    f"Cannot mix fields from different models. "
                    f"Expected fields from {cls.__name__}, "
                    f"got field '{f.name}' from {f.owner.__name__ if f.owner else 'unknown'}"
                )
        m = tuple(metrics)

    d: tuple[Dimension[Any] | Fact[Any], ...] = ()
    if dimensions is not None:
        for f in dimensions:
            if not isinstance(f, (Dimension, Fact)):
                raise TypeError(
                    f"dimensions requires Dimension or Fact fields, "
                    f"got {type(f).__name__}. Did you mean metrics=?"
                )
            if f.owner != cls:
                raise TypeError(
                    f"Cannot mix fields from different models. "
                    f"Expected fields from {cls.__name__}, "
                    f"got field '{f.name}' from {f.owner.__name__ if f.owner else 'unknown'}"
                )
        d = tuple(dimensions)

    q = QueryImpl(_metrics=m, _dimensions=d, _using=using)
    object.__setattr__(q, "_model", cls)
    return q
```

**Why this approach:**
- No changes needed to `_Query.metrics()` or `_Query.dimensions()` -- they already concatenate tuples
- Validation happens at the `query()` call site, consistent with how `.metrics()` validates
- `_model` is set, so field ownership validation works
- Additivity is automatic: `query(metrics=[Sales.revenue]).metrics(Sales.cost)` produces `_metrics = (Sales.revenue,) + (Sales.cost,) = (Sales.revenue, Sales.cost)`

### Design Decision: Keyword-Only Args

Make `metrics` and `dimensions` keyword-only (after `*`). This is important because:
- Prevents positional arg confusion: `Sales.query([Sales.revenue])` is unclear
- Matches the success criteria syntax: `Sales.query(metrics=[...], dimensions=[...])`
- `using` should also become keyword-only for consistency (it already was positional-or-keyword)

**Note on `using` position change:** Currently `using` is the only positional arg (`query(using=None)`). Making it keyword-only is technically a breaking change if anyone calls `Sales.query("warehouse")`. However, the documented examples all use `query(using="warehouse")`, and this is an internal API detail. The planner should decide whether to keep backward compat or enforce keyword-only.

### Anti-Patterns to Avoid

- **Don't accept `Sequence[Metric]` type hint:** Use `list[Metric[Any]]` to match user expectation. Internally convert to tuple.
- **Don't validate inside `_Query.__init__`:** Validation belongs in `SemanticView.query()` where we have `cls` context for field ownership checks. `_Query` is an internal class that trusts its inputs.
- **Don't duplicate validation logic:** Extract shared validation into a helper function or reuse the existing `.metrics()` / `.dimensions()` methods by chaining.

### Alternative: Chain Builder Methods Instead

An alternative to passing constructor args is to chain:

```python
q = QueryImpl(_using=using)
object.__setattr__(q, "_model", cls)
if metrics:
    q = q.metrics(*metrics)
if dimensions:
    q = q.dimensions(*dimensions)
return q
```

**Tradeoff:** Simpler (reuses existing validation), but creates 1-2 extra intermediate `_Query` objects. Since queries are lightweight frozen dataclasses, the overhead is negligible. This approach has the advantage of zero validation duplication.

**Recommendation:** Use the chaining approach. It reuses existing validation code in `.metrics()` and `.dimensions()`, preventing logic duplication. The immutable dataclass copies are cheap.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Type validation of metrics/dimensions args | Custom isinstance checks in query() | Chain `.metrics()` / `.dimensions()` builder methods | They already validate types and field ownership |
| Tuple conversion from list | Manual tuple() calls | Let builder methods handle it | They already accept varargs and produce tuples |

## Common Pitfalls

### Pitfall 1: Forgetting `_model` Must Be Set Before Validation
**What goes wrong:** If you chain `.metrics()` before setting `_model`, field ownership validation fails silently (it skips when `_model is None`).
**Why it happens:** `_model` has `init=False` on the dataclass, so it starts as `None`.
**How to avoid:** Set `_model` via `object.__setattr__` BEFORE chaining `.metrics()` / `.dimensions()`.
**Warning signs:** Tests pass but field ownership validation doesn't trigger.

### Pitfall 2: Breaking `using` Positional Compatibility
**What goes wrong:** Existing code calling `Sales.query("warehouse")` breaks if `using` becomes keyword-only.
**Why it happens:** Adding `*` before `using` forces keyword-only.
**How to avoid:** Keep `using` as positional-or-keyword OR accept the break (if no public usage exists). Check existing tests and docs.
**Warning signs:** `TypeError: query() takes 1 positional argument` in tests.

### Pitfall 3: Empty List vs None Semantics
**What goes wrong:** `query(metrics=[])` could raise `ValueError` from `.metrics()` ("At least one metric must be provided").
**Why it happens:** Builder methods validate non-empty input.
**How to avoid:** Treat `metrics=[]` same as `metrics=None` (no-op). Only chain if the list is non-empty.
**Warning signs:** `ValueError: At least one metric must be provided` when user passes empty list.

### Pitfall 4: Accepting Sequences vs Lists in Type Signature
**What goes wrong:** User passes tuple or generator; type checker rejects it.
**Why it happens:** Type hint is too narrow.
**How to avoid:** Use `Sequence[Metric[Any]]` for the type hint. Accept any iterable-like input.
**Warning signs:** basedpyright errors when user passes a tuple of metrics.

## Code Examples

### Basic Shorthand Query (QAPI-01)
```python
# Before (verbose)
cursor = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.region)
    .execute()
)

# After (shorthand)
cursor = Sales.query(
    metrics=[Sales.revenue],
    dimensions=[Sales.region],
).execute()
```

### Additive Builder Methods (QAPI-02)
```python
# Start with shorthand, add more via builder
cursor = (
    Sales.query(metrics=[Sales.revenue])
    .metrics(Sales.cost)        # additive: now has revenue AND cost
    .dimensions(Sales.region)
    .execute()
)
# query._metrics == (Sales.revenue, Sales.cost)
```

### Shorthand with Filters and Ordering
```python
cursor = (
    Sales.query(
        metrics=[Sales.revenue, Sales.cost],
        dimensions=[Sales.region],
    )
    .where(Sales.region == "US")
    .order_by(Sales.revenue.desc())
    .limit(10)
    .execute()
)
```

### Shorthand with using=
```python
cursor = Sales.query(
    metrics=[Sales.revenue],
    dimensions=[Sales.region],
    using="warehouse",
).execute()
```

## State of the Art

This is a standard Python API design pattern. No external library research needed.

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Sales.query().metrics(Sales.revenue).dimensions(Sales.region)` | Both verbose and shorthand supported | Phase 28 | Shorthand is syntactic sugar; builder chain still works |

## Open Questions

1. **Should `using` become keyword-only?**
   - What we know: Currently `using` is positional-or-keyword in `SemanticView.query(cls, using=None)`
   - What's unclear: Whether any code calls `Sales.query("warehouse")` positionally
   - Recommendation: Make keyword-only. All documented examples use `query(using=...)`. The existing test `test_query_with_using_parameter` uses `Sales.query(using="warehouse")`.

2. **Should `metrics` and `dimensions` accept `Sequence` or `list`?**
   - What we know: The success criteria shows `metrics=[Sales.revenue]` (list literal)
   - Recommendation: Use `Sequence[Metric[Any]]` in type hint for flexibility, but document with list examples. This lets users pass tuples too.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (project dev dependency) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run --extra dev pytest tests/unit/test_query.py -x` |
| Full suite command | `uv run --extra dev pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QAPI-01 | `query(metrics=..., dimensions=...)` shorthand accepted | unit | `uv run --extra dev pytest tests/unit/test_query.py -k "shorthand" -x` | No -- Wave 0 |
| QAPI-01 | Shorthand produces identical query to builder chain | unit | `uv run --extra dev pytest tests/unit/test_query.py -k "shorthand_equivalent" -x` | No -- Wave 0 |
| QAPI-01 | Type validation on shorthand args (wrong field type) | unit | `uv run --extra dev pytest tests/unit/test_query.py -k "shorthand_type" -x` | No -- Wave 0 |
| QAPI-01 | Cross-model field ownership validation on shorthand | unit | `uv run --extra dev pytest tests/unit/test_query.py -k "shorthand_ownership" -x` | No -- Wave 0 |
| QAPI-01 | Empty list treated as no-op | unit | `uv run --extra dev pytest tests/unit/test_query.py -k "shorthand_empty" -x` | No -- Wave 0 |
| QAPI-02 | Builder `.metrics()` additive with shorthand metrics | unit | `uv run --extra dev pytest tests/unit/test_query.py -k "additive" -x` | No -- Wave 0 |
| QAPI-02 | Builder `.dimensions()` additive with shorthand dimensions | unit | `uv run --extra dev pytest tests/unit/test_query.py -k "additive" -x` | No -- Wave 0 |
| QAPI-02 | Shorthand + builder produces correct SQL | unit | `uv run --extra dev pytest tests/unit/test_query.py -k "shorthand_sql" -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run --extra dev pytest tests/unit/test_query.py tests/unit/test_models.py -x`
- **Per wave merge:** `uv run --extra dev pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] New test class `TestQueryShorthand` in `tests/unit/test_query.py` -- covers QAPI-01
- [ ] New test class `TestQueryShorthandAdditivity` in `tests/unit/test_query.py` -- covers QAPI-02

## Sources

### Primary (HIGH confidence)
- Project source code: `src/semolina/query.py` -- current `_Query` frozen dataclass implementation
- Project source code: `src/semolina/models.py` -- current `SemanticView.query()` classmethod
- Project source code: `src/semolina/fields.py` -- `Metric`, `Dimension`, `Fact` field types
- Project tests: `tests/unit/test_query.py` -- existing query builder tests
- Project tests: `tests/unit/test_models.py` -- existing model tests including `query()` usage

### Secondary (MEDIUM confidence)
- None needed -- this is internal API design, no external libraries involved

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies, pure internal refactoring
- Architecture: HIGH - direct inspection of existing code, clear implementation path
- Pitfalls: HIGH - identified from code inspection (empty list edge case, _model ordering, using positional compat)

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (30 days -- stable internal API)
