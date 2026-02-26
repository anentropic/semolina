# Phase 23: API Export Cleanup - Research

**Researched:** 2026-02-25
**Domain:** Python public API surface, pytest xfail markers, requirements traceability
**Confidence:** HIGH

## Summary

Phase 23 is a pure housekeeping phase with four discrete tasks, each independently verifiable. No new functionality is introduced; all changes are corrections to existing code and documentation to reflect the actual implementation state.

The two API export tasks (`CubanoViewNotFoundError`, `CubanoConnectionError`, and `Result`) are simple additions to `src/cubano/__init__.py` — both types exist in the codebase, neither is currently in `__all__`. The xfail removal task is equally mechanical: both test functions in `cubano-jaffle-shop/tests/test_mock_queries.py::TestFiltering` are confirmed XPASS (the MockEngine now evaluates filters correctly as of Phase 13.1). The REQUIREMENTS.md update requires two targeted prose edits: adding CODEGEN-WAREHOUSE to the traceability table (Phase 20 implemented it) and correcting the CODEGEN-REVERSE description to reflect the actual warehouse→Python direction.

No external libraries, new dependencies, or architectural decisions are required. This phase can be executed as a single plan with four tasks running in sequence.

**Primary recommendation:** One plan (`23-01-PLAN.md`), four tasks in order: (1) export exceptions, (2) export Result, (3) remove xfail markers, (4) fix REQUIREMENTS.md traceability. Run full quality gate once at the end.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `__init__.py` | stdlib | Public API surface | Standard Python packaging pattern |
| pytest | >=7 | Test framework | Already in dev deps |

### Supporting

None required — all changes use existing infrastructure.

### Alternatives Considered

None — this is housekeeping, there are no alternatives to evaluate.

## Architecture Patterns

### Public API Export Pattern

The project uses the explicit `__all__` list in `src/cubano/__init__.py` to define the public API. The current file:

```python
# src/cubano/__init__.py (current state)
from .fields import Dimension, Fact, Metric, NullsOrdering, OrderTerm
from .filters import Predicate
from .models import SemanticView
from .registry import get_engine, register, unregister
from .results import Row

__all__ = [
    "__version__",
    "SemanticView",
    "Metric",
    "Dimension",
    "Fact",
    "Predicate",
    "OrderTerm",
    "NullsOrdering",
    "register",
    "get_engine",
    "unregister",
    "Row",
]
```

Three types are missing:
- `CubanoViewNotFoundError` — lives in `src/cubano/engines/base.py`
- `CubanoConnectionError` — lives in `src/cubano/engines/base.py`
- `Result` — lives in `src/cubano/results.py`

The fix is two lines: add an import from `cubano.engines.base` and extend the `from .results import` line, then add all three names to `__all__`.

### Import Verification Pattern

After adding to `__init__.py`, the planner should verify imports work at the Python REPL level:

```bash
uv run python -c "from cubano import CubanoViewNotFoundError, CubanoConnectionError, Result; print('ok')"
```

### xfail Removal Pattern

The `@pytest.mark.xfail` decorator is on two test methods in `cubano-jaffle-shop/tests/test_mock_queries.py`. Both are in class `TestFiltering`:

- `test_filter_boolean` (line 125)
- `test_filter_comparison` (line 146)

Both tests are **confirmed XPASS** — they currently pass despite being marked as expected failures. This happened because Phase 13.1 implemented the WHERE clause compiler, which made `MockEngine` evaluate filters correctly.

The fix removes the `@pytest.mark.xfail(reason="...")` decorator from each method and updates the docstring to remove the "Marked xfail to document this limitation" language. The test body itself is already correct and will pass without the decorator.

Verification command:
```bash
cd cubano-jaffle-shop && uv run pytest tests/test_mock_queries.py::TestFiltering -v
```

Expected after fix: 2 PASSED (not 2 XPASS).

### REQUIREMENTS.md Traceability Pattern

The traceability table currently has this row:

```
| CODEGEN-REVERSE | Phase 20 | Complete |
```

Two issues:
1. `CODEGEN-WAREHOUSE` ("Generate models from warehouse introspection") is missing from the traceability table entirely — Phase 20 implemented it but it was listed as v1+ deferred.
2. `CODEGEN-REVERSE` in the v1+ section is described as "Reverse codegen (Cubano models → dbt semantic YAML)" — this is directionally wrong. Phase 20 actually implemented warehouse→Python (introspect warehouse view, generate Python model class), not Python→dbt YAML.

The fix requires:
1. Update the v1+ description for `CODEGEN-WAREHOUSE` to note it was implemented in Phase 20 (or move it to the completed section — the simpler fix is just adding a traceability row).
2. Update the v1+ description for `CODEGEN-REVERSE` to accurately say "Generate Cubano Python model class from warehouse introspection (warehouse→Python direction)" and note Phase 20 implemented this.
3. Add `CODEGEN-WAREHOUSE` row to the traceability table pointing at Phase 20.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Public API verification | Custom import checker script | Direct `python -c "from cubano import X"` | One-liner is sufficient for 3 names |
| xfail detection | Grep/parse test files | Run `pytest` and observe XPASS output | pytest already reports this |

## Common Pitfalls

### Pitfall 1: Circular Import When Adding Engine Exceptions to `__init__`

**What goes wrong:** `cubano/engines/base.py` imports from `cubano.codegen.introspector` (via `TYPE_CHECKING`), and `__init__.py` importing from `engines.base` could in theory create a circular import if the import graph is traversed at module load time.

**Why it happens:** The engines subpackage has internal imports. However, `TYPE_CHECKING` guards in `base.py` prevent runtime circular imports.

**How to avoid:** The import in `engines/base.py` is already guarded with `if TYPE_CHECKING:` (verified in the source). Adding `from .engines.base import CubanoViewNotFoundError, CubanoConnectionError` to `__init__.py` will not cause runtime circular imports.

**Warning signs:** If import fails with `ImportError: cannot import name` or `circular import` error, check `engines/base.py` `TYPE_CHECKING` guard.

**Verification:** Run `uv run python -c "import cubano"` — if it succeeds without error, the import graph is clean.

### Pitfall 2: xfail Removal Breaks Test Docstrings

**What goes wrong:** The docstrings on the xfail tests still say "Marked xfail to document this limitation" and reference "Plan 08-04". These become misleading after the decorator is removed.

**How to avoid:** Update docstrings to remove the xfail explanation prose when removing the decorator.

### Pitfall 3: REQUIREMENTS.md Description vs. Traceability Mismatch

**What goes wrong:** The v1+ section says `CODEGEN-REVERSE = "Reverse codegen (Cubano models → dbt semantic YAML)"` but the traceability table has `CODEGEN-REVERSE | Phase 20 | Complete`. These descriptions conflict — Phase 20 was warehouse→Python, not Cubano→YAML.

**How to avoid:** Update the v1+ section description for `CODEGEN-REVERSE` to accurately describe what Phase 20 delivered (warehouse→Python), and either add a new `CODEGEN-WAREHOUSE` entry for the same behavior, or note that Phase 20 implemented what was tracked as `CODEGEN-WAREHOUSE` (the live schema scanning).

**Recommended resolution:**
- In v1+ section: Update `CODEGEN-REVERSE` description to "Generate Cubano Python model class from warehouse introspection (warehouse→Python direction; implemented in Phase 20)"
- In traceability table: Rename `CODEGEN-REVERSE` row to `CODEGEN-WAREHOUSE` (or add a `CODEGEN-WAREHOUSE` row) pointing to Phase 20
- The old `CODEGEN-REVERSE` concept (Cubano→dbt YAML) was never implemented and remains deferred

## Code Examples

### Adding to `__init__.py`

```python
# Add to imports section:
from .engines.base import CubanoConnectionError, CubanoViewNotFoundError
from .results import Result, Row  # extend existing import

# Add to __all__:
"CubanoViewNotFoundError",
"CubanoConnectionError",
"Result",
```

Full updated `__init__.py`:

```python
from .engines.base import CubanoConnectionError, CubanoViewNotFoundError
from .fields import Dimension, Fact, Metric, NullsOrdering, OrderTerm
from .filters import Predicate
from .models import SemanticView
from .registry import get_engine, register, unregister
from .results import Result, Row

__all__ = [
    "__version__",
    "SemanticView",
    "Metric",
    "Dimension",
    "Fact",
    "Predicate",
    "OrderTerm",
    "NullsOrdering",
    "register",
    "get_engine",
    "unregister",
    "Row",
    "Result",
    "CubanoViewNotFoundError",
    "CubanoConnectionError",
]
```

Note: ruff isort will alphabetize imports; the executor should run `uv run ruff format` and `uv run ruff check --fix` after editing.

### Removing xfail Marker

Before (lines 125-144 in `test_mock_queries.py`):

```python
@pytest.mark.xfail(reason="MockEngine doesn't evaluate filters yet")
def test_filter_boolean(self, orders_engine) -> None:
    """
    ...
    Marked xfail to document this limitation. Real filter evaluation
    requires warehouse connection (Plan 08-04).
    """
```

After:

```python
def test_filter_boolean(self, orders_engine) -> None:
    """
    Query with boolean filter should validate query construction.

    MockEngine evaluates filters via the WHERE clause compiler (Phase 13.1).
    """
```

### REQUIREMENTS.md Traceability Update

Add new row to traceability table:

```markdown
| CODEGEN-WAREHOUSE | Phase 20 | Complete |
```

Update existing `CODEGEN-REVERSE` row description in v1+ section to clarify the warehouse→Python direction (not Cubano→YAML).

## State of the Art

All technology in this phase is stable and well-understood. No library upgrades, new dependencies, or architectural patterns are involved.

| Item | Current State | After Phase 23 |
|------|--------------|----------------|
| `from cubano import CubanoViewNotFoundError` | ImportError | Works |
| `from cubano import Result` | ImportError | Works |
| `test_filter_boolean` | XPASS | PASSED |
| `test_filter_comparison` | XPASS | PASSED |
| CODEGEN-WAREHOUSE in traceability | Missing | Present (Phase 20) |
| CODEGEN-REVERSE description | Wrong direction | Accurate |

## Open Questions

None. All four success criteria are fully understood and all necessary code locations are identified.

## Sources

### Primary (HIGH confidence)

- Direct code inspection: `src/cubano/__init__.py` — current exports confirmed
- Direct code inspection: `src/cubano/engines/base.py` — exception classes confirmed at lines 19-23
- Direct code inspection: `src/cubano/results.py` — `Result` class confirmed at line 172
- Direct code inspection: `cubano-jaffle-shop/tests/test_mock_queries.py` — xfail markers at lines 125, 146
- Live pytest run: `cd cubano-jaffle-shop && uv run pytest tests/test_mock_queries.py::TestFiltering -v` — both tests confirmed XPASS
- Live import test: `uv run python -c "from cubano import CubanoViewNotFoundError"` — confirmed ImportError
- Live import test: `uv run python -c "from cubano import Result"` — confirmed ImportError
- Direct code inspection: `.planning/REQUIREMENTS.md` lines 69-70, 130 — CODEGEN-WAREHOUSE/REVERSE state confirmed

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no external dependencies involved; pure Python stdlib patterns
- Architecture: HIGH — all code locations identified by direct inspection and live testing
- Pitfalls: HIGH — all pitfalls verified by reading actual source code

**Research date:** 2026-02-25
**Valid until:** Stable indefinitely (housekeeping only; no external dependencies)
