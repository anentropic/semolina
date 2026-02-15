# Code Conventions

**Purpose:** Document typing conventions, import patterns, and code style preferences for the Cubano project to ensure consistency across all code contributions.

**Audience:** Future contributors (both human and Claude Code)

**Last updated:** 2026-02-15

---

## Typing Conventions

### Future Annotations

**Don't use `from __future__ import annotations` unless necessary.**

Python 3.11+ has native support for postponed evaluation of annotations via PEP 563. The codebase targets Python >=3.11, so future imports are only needed in specific cases:

- When circular imports require TYPE_CHECKING blocks (see Import Patterns below)
- When using string annotations for forward references is insufficient

**Current exceptions in codebase:**
- `src/cubano/query.py` - uses future annotations for Query self-references in return types
- `src/cubano/fields.py` - uses future annotations for OrderTerm self-references
- `src/cubano/engines/base.py` - uses future annotations with TYPE_CHECKING for Query imports

**Rationale:** Minimize import overhead and keep code simple. Use only when needed for circular dependencies or complex type scenarios.

### Constants

**Mark all module-level constants with `Final` type.**

```python
from typing import Final

DEFAULT_TIMEOUT: Final[int] = 30
MAX_RETRIES: Final[int] = 3
API_VERSION: Final[str] = "v1"
```

**Rationale:**
- Makes intent explicit (this value should never change)
- Type checkers can enforce immutability
- Helps readers identify configuration values vs mutable state

**Current status:** Not yet implemented in codebase. Apply to module-level constants as they're added.

**Examples of what should be marked Final:**
- `registry._default_name` (currently `str`, should be `Final[str]`)
- Future constants like SQL keywords, default values, magic strings

### Class Attributes

**Mark all class attributes with `ClassVar` where not modified by instances.**

```python
from typing import ClassVar

class MyClass:
    shared_counter: ClassVar[int] = 0  # Shared across all instances
    instance_value: int  # Instance-specific
```

**Rationale:**
- Clarifies which attributes are class-level vs instance-level
- Prevents accidental instance shadowing of class attributes
- Type checkers can enforce proper usage

**Current status:** Not yet implemented in codebase. Apply to class-level attributes as they're added.

**Examples in models.py:**
- `SemanticView._view_name` - should be `ClassVar[str]` (set once per subclass)
- `SemanticView._fields` - should be `ClassVar[types.MappingProxyType[str, Field]]`
- `SemanticView._frozen` - should be `ClassVar[bool]`

**Note:** Dataclass fields (`@dataclass`) and descriptor protocol fields don't need ClassVar - they have their own semantics.

### Function Type Annotations

**Parameters: Permissive types (accept broad input)**

Use abstract types (collections.abc) that accept the widest range of compatible inputs:

```python
from collections.abc import Iterable, Mapping, Sequence

def process_items(items: Iterable[str]) -> list[str]:  # Accept any iterable
    return [item.upper() for item in items]

def merge_configs(base: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    # Accept any mapping (dict, MappingProxy, etc.)
    return {**base, **overrides}
```

**Rationale:**
- Flexibility for callers (can pass list, tuple, generator, etc.)
- Follows Liskov Substitution Principle
- Matches Python's duck-typing philosophy

**Returns: Precise types (communicate exact output)**

Use concrete types that tell callers exactly what they're getting:

```python
def get_users() -> list[User]:  # Not Iterable[User] or Sequence[User]
    return [User(...), User(...)]

def get_config() -> dict[str, str]:  # Not Mapping[str, str]
    return {"key": "value"}
```

**Rationale:**
- Callers know they can use list/dict-specific methods (.append(), .pop(), etc.)
- Type checkers can verify caller usage
- No ambiguity about mutability or indexing support

### Avoid Any

**Prefer specific type annotations over `Any` where possible.**

Use `Any` only when:
- Duck typing is genuinely required (like Query fields in SQLBuilder to avoid circular imports)
- Type is truly dynamic and cannot be constrained
- Protocol or TypeVar would be over-engineering

```python
# Good - specific type
def format_number(value: int | float) -> str:
    return f"{value:.2f}"

# Acceptable - duck typing for circular import avoidance
def build_sql(query: Any) -> str:  # query is Query, but importing creates circular dependency
    return f"SELECT {query._metrics}"

# Bad - lazy typing
def process_data(data: Any) -> Any:  # What is data? What does this return?
    return data.transform()
```

**Current exceptions in codebase:**
- `query.py` - uses `Any` for method parameters to allow runtime validation via isinstance checks
- `engines/sql.py` - uses `Any` for Query parameters to prevent circular imports
- `models.py` - uses `Any` in metaclass methods for flexibility

**Rationale:**
- Better IDE autocomplete and type checking
- Self-documenting code
- Catches type errors at development time

---

## Import Patterns

### TYPE_CHECKING for Type-Only Dependencies

**Use TYPE_CHECKING imports to avoid circular import errors.**

When you need a type annotation but importing it would create a circular dependency:

```python
from __future__ import annotations  # Enable string annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cubano.query import Query  # Only imported for type checking

def process_query(query: Query) -> str:  # String annotation resolved at type-check time
    ...
```

**Current examples:**
- `engines/base.py` imports Query only under TYPE_CHECKING
- `query.py` uses future annotations for self-references

**Rationale:**
- Prevents runtime circular import errors
- Maintains type safety for static analysis
- Keeps runtime imports minimal

### Import Sorting

**All imports are sorted alphabetically using ruff's isort rules.**

Configuration in `pyproject.toml`:
```toml
[tool.ruff.lint]
select = [..., "I", ...]  # I = isort rules
```

Standard library → third-party → local imports, each section sorted alphabetically:

```python
import keyword
import types
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .fields import Field  # Local imports last
from .filters import Q
```

**Rationale:**
- Consistent ordering across all files
- Easy to find imports
- Automated via `uv run ruff check --fix`

---

## Code Style

### Line Length

**Maximum 100 characters per line.**

Configured in `pyproject.toml`:
```toml
[tool.ruff]
line-length = 100
```

Enforced by ruff formatter. Use line breaks for readability:

```python
# Good
result = some_function(
    first_parameter,
    second_parameter,
    third_parameter,
)

# Good - fits within 100 chars
short_result = some_function(param1, param2)

# Bad - exceeds 100 chars
really_long_line_that_should_be_broken_up = some_function(param1, param2, param3, param4, param5)
```

### Docstrings

**Multi-line docstrings: opening and closing `"""` on own lines**

**Summary line on second line after opening quotes (D213)**

```python
def my_function(x: int) -> str:
    """
    Convert integer to string with formatting.

    Additional details about the function behavior,
    edge cases, and examples go here.

    Args:
        x: The integer to convert

    Returns:
        Formatted string representation
    """
    return f"Value: {x}"
```

**Current configuration in pyproject.toml:**
```toml
[tool.ruff.lint]
select = [..., "D", ...]  # D = pydocstyle rules
ignore = [
    "D1",    # don't require docstrings everywhere
    "D212",  # conflicts with D213 (multiline summary on second line)
    ...
]
```

**Rationale:**
- D213 (summary on second line) is more readable for multi-line docstrings
- Consistent formatting across all docstrings
- Matches Google/NumPy docstring conventions

### Type Ignore Comments

**Minimize `# type: ignore` in code. Prefer pyproject.toml-level exemptions.**

When type checkers report false positives, configure pyproject.toml instead of inline comments:

```toml
[tool.basedpyright]
# Project-wide type checking exemptions
reportUnusedVariable = false
```

**Only use inline `# type: ignore` when:**
- Issue is specific to a single line/statement
- Project-wide exemption would be too broad
- You're working around a known type checker bug

```python
# Acceptable - specific workaround
result = some_dynamic_code()  # type: ignore[attr-defined]

# Better - fix in pyproject.toml if possible
```

**Rationale:**
- Keeps code clean and readable
- Centralizes type checking configuration
- Makes exemptions more visible and reviewable

---

## Quality Gates

**All code must pass these checks before committing:**

### Typecheck

```bash
uv run basedpyright
```

**Configuration:** Strict mode enabled in pyproject.toml

```toml
[tool.basedpyright]
pythonVersion = "3.11"
typeCheckingMode = "strict"
include = ["src"]
```

**Rationale:** Catch type errors early, enforce type annotation consistency.

### Lint

```bash
uv run ruff check
```

**Auto-fix:** Many issues can be fixed automatically:

```bash
uv run ruff check --fix
```

**Rationale:** Enforce code style, catch common bugs (unused imports, undefined names, etc.).

### Format

```bash
uv run ruff format --check
```

**Apply formatting:**

```bash
uv run ruff format
```

**Rationale:** Consistent code formatting (line length, indentation, quotes, etc.).

### Tests

```bash
uv run --extra dev pytest
```

**Rationale:** Verify all functionality works as expected. All tests must pass before merge.

---

## Examples from Codebase

### TYPE_CHECKING Pattern

From `src/cubano/engines/base.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cubano.query import Query  # Avoid circular import


class Engine(ABC):
    @abstractmethod
    def to_sql(self, query: Query) -> str:  # Query type available for type checking
        pass
```

**Key points:**
- `from __future__ import annotations` enables string annotation resolution
- TYPE_CHECKING block imports Query only during type checking
- No circular import at runtime

### Permissive Parameters, Precise Returns

From `src/cubano/query.py`:

```python
def metrics(self, *fields: Any) -> Query:  # Accepts any input (validated at runtime)
    """Select metrics for aggregation."""
    if not fields:
        raise ValueError("At least one metric must be provided")

    for f in fields:
        if not isinstance(f, Metric):
            raise TypeError(f"metrics() requires Metric fields, got {type(f).__name__}")

    return replace(self, _metrics=self._metrics + fields)
```

**Key points:**
- Parameter type is `Any` (permissive) - runtime validation via isinstance
- Return type is `Query` (precise) - callers know exactly what they get
- Runtime checks provide safety despite loose parameter types

### Docstring Format (D213)

From `src/cubano/results.py`:

```python
def __init__(self, data: dict[str, Any]) -> None:
    """
    Initialize Row with field data.

    Args:
        data: Dictionary mapping field names to values

    Raises:
        TypeError: If data is not a dict
    """
    # Implementation...
```

**Key points:**
- Opening `"""` on its own line
- Summary on second line (D213)
- Closing `"""` on its own line
- Args/Raises sections clearly formatted

---

## Checklist for New Code

- [ ] No unnecessary `from __future__ import annotations` (only if needed for circular imports)
- [ ] Module-level constants marked with `Final[T]`
- [ ] Class-level attributes marked with `ClassVar[T]` where appropriate
- [ ] Function parameters use permissive types (Iterable, Mapping, etc.)
- [ ] Function returns use precise types (list, dict, etc.)
- [ ] Avoid `Any` unless genuinely needed (duck typing, circular imports)
- [ ] TYPE_CHECKING used for type-only imports to prevent circular dependencies
- [ ] Multi-line docstrings follow D213 format (summary on second line)
- [ ] Minimal `# type: ignore` comments (prefer pyproject.toml configuration)
- [ ] Passes `uv run basedpyright` (strict mode)
- [ ] Passes `uv run ruff check`
- [ ] Passes `uv run ruff format --check`
- [ ] All tests pass: `uv run --extra dev pytest`

---

## Future Work

**To apply these conventions to existing code:**

1. Add `Final` annotations to constants in `registry.py` (_default_name)
2. Add `ClassVar` annotations to class attributes in `models.py` (_view_name, _fields, _frozen)
3. Review `Any` usage in `query.py` and consider Protocol types where appropriate
4. Audit `# type: ignore` comments and move to pyproject.toml where possible

**Note:** These are quality-of-life improvements, not breaking changes. Apply incrementally as code is modified.
