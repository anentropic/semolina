# Coding Conventions

**Analysis Date:** 2026-02-17

## Naming Patterns

**Files:**
- `snake_case.py` for all modules: `fields.py`, `filters.py`, `query.py`, `results.py`
- `snake_case/` for subpackages: `engines/`, `codegen/`, `cli/`, `testing/`
- Test files prefix with `test_`: `test_query.py`, `test_fields.py`
- Fixture files use descriptive names: `simple_models.py`, `multi_models.py`

**Classes:**
- `PascalCase` for all classes: `SemanticView`, `MockEngine`, `SnowflakeDialect`, `SQLBuilder`
- Metaclasses suffix with `Meta`: `SemanticViewMeta`
- Abstract base classes use plain names (no `Abstract` prefix): `Engine`, `Dialect`
- Errors/exceptions use descriptive names: `CodegenError`, `CredentialError`

**Functions and Methods:**
- `snake_case` for all functions and methods: `build_select`, `extract_models_from_module`
- Private helpers prefix with `_`: `_build_select_clause`, `_validate_for_execution`, `_combine`
- Private module-level state prefix with `_`: `_engines`, `_PROGRESS_THRESHOLD`
- Constants in `SCREAMING_SNAKE_CASE`: `_PROGRESS_THRESHOLD`, `_default_name`

**Variables:**
- `snake_case`: `view_name`, `field_spec`, `select_items`
- Type alias use `PascalCase`: `FixturesDict = dict[str, list[dict[str, Any]]]`

**Private Attributes on Instances:**
- Query dataclass fields are private: `_metrics`, `_dimensions`, `_filters`, `_order_by_fields`, `_limit_value`, `_using`
- Engine state is private: `_fixtures`, `_connection_params`
- `reportPrivateUsage = false` in pyproject.toml allows tests to access these

## Code Style

**Formatting:**
- Tool: `ruff format`
- Line length: 100 characters
- Target version: Python 3.11

**Linting:**
- Tool: `ruff check`
- Rules enabled: `E, F, W, I, UP, B, SIM, TCH, D`
- `D1` ignored (docstrings not required everywhere)
- `D213` enforced (summary on second line after opening `"""`)
- `D203` ignored in favor of `D211` (no blank line before class docstring)
- `D212` ignored in favor of `D213`
- `D401` ignored (imperative mood not required for dunder methods)
- `TCH` rules: imports used only for type checking go in `TYPE_CHECKING` blocks

**Type Checking:**
- Tool: `basedpyright` in strict mode
- Python version target: 3.11
- `# type: ignore` comments used sparingly, only when the type system cannot express intent (e.g., accessing private members in SQL builder, `type: ignore[abstract]` in tests)
- Prefer pyproject.toml-level exemptions over inline ignores

## Import Organization

**Order (ruff isort):**
1. `__future__` annotations (always first when present)
2. Standard library (`abc`, `dataclasses`, `typing`, `pathlib`)
3. Third-party (`pytest`, `typer`, `rich`)
4. Local / first-party (`cubano.*`, relative imports)

**Relative vs Absolute:**
- Within `src/cubano/`: use relative imports (`.fields`, `.filters`, `..engines`)
- In tests: use absolute imports (`from cubano import ...`, `from cubano.engines.mock import MockEngine`)
- `from __future__ import annotations` used in files with forward references

**TYPE_CHECKING Guard:**
- Use `TYPE_CHECKING` block for imports only needed at type-check time:
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from cubano.query import Query
  ```
- `# noqa: TC003` / `# noqa: TC002` on imports that belong in TYPE_CHECKING but are legitimately runtime

**`__all__` in `__init__.py`:**
- Explicitly list all public exports in `src/cubano/__init__.py`
- Only the public API surfaces: `SemanticView`, `Metric`, `Dimension`, `Fact`, `Query`, `Q`, `OrderTerm`, `NullsOrdering`, `register`, `get_engine`, `unregister`, `Row`

## Docstring Style

**Module-level docstrings:**
- Every module has a module-level docstring
- Multi-line: opening `"""` on its own line, summary on the second line, closing `"""` on its own line
- Example from `src/cubano/models.py`:
  ```python
  """
  Semantic view model base class for Cubano.

  This module provides the SemanticView base class that enables ORM-style
  model definitions with typed fields and immutable metadata.
  """
  ```

**Class docstrings:**
- Opening `"""` immediately after `class ...:`, summary on second line
- Include `Attributes:` section for dataclasses/classes with notable state
- Include `Example:` section for public-facing classes
- `See Also:` section for cross-references

**Method docstrings:**
- `Args:` section for all non-trivial parameters
- `Returns:` section describing the return value
- `Raises:` section listing exceptions with conditions
- `Example:` section with executable doctest when the method is part of public API

**Doctest integration:**
- Public API methods include doctest examples:
  ```python
  Example:
      >>> query = Query().metrics(Sales.revenue).limit(100)
      >>> query._limit_value
      100
  ```
- Doctests run via `--doctest-modules` in pytest
- Doctest namespace injected via `src/cubano/conftest.py` (provides `Sales`, `Query`, `Q`, etc.)

**One-liner docstrings:**
- Used for simple dunder methods and small helpers: `"""Return readable representation."""`
- Opening and closing `"""` on the same line for single-line docstrings

## Error Handling

**Pattern: Raise early, raise specific:**
- Validate inputs at the start of methods before doing any work
- Raise `TypeError` for wrong types: `"filter() requires Q object, got {type(condition).__name__}"`
- Raise `ValueError` for invalid values: `"limit() requires positive integer, got {n}"`
- Raise `AttributeError` for descriptor/protocol violations: `"Field '{name}' cannot be modified"`

**Error messages are helpful and actionable:**
- Include the actual received type/value: `got {type(f).__name__}`
- Suggest the correct alternative: `"Did you mean .dimensions()?"`
- Provide example usage when relevant: `"Use cubano.register('name', engine) to register an engine."`

**No bare `except`:**
- Always catch specific exception types
- Use `except KeyError: raise AttributeError(...) from None` pattern to translate exceptions while preserving clarity

**`assert` for internal invariants:**
- `assert` used for conditions that should never be False in correct code: `assert metric.name is not None`
- Not used for user-facing validation (use `raise ValueError` instead)

## Function Design

**Size:** Methods stay focused on one task. SQL builder has one method per clause: `_build_select_clause`, `_build_from_clause`, etc.

**Parameters:**
- `*args` for variadic field lists: `def metrics(self, *fields: Any) -> Query`
- `**kwargs` for filter conditions: `def __init__(self, **kwargs: Any) -> None`
- Keyword-only parameters for options: `def __init_subclass__(cls, view: str | None = None, **kwargs: Any)`

**Return types:**
- Always annotated with explicit return types
- Fluent methods return `Self`-type (written as the class name): `-> Query`
- Abstract methods return concrete types

**Immutability via `dataclasses.replace`:**
- Frozen dataclasses use `replace(self, field=new_value)` for "mutations":
  ```python
  return replace(self, _metrics=self._metrics + fields)
  ```

## Module Design

**Exports:**
- Public API exported from `src/cubano/__init__.py` with explicit `__all__`
- Sub-modules expose their own public API; consumers import from specific paths when needed: `from cubano.engines.mock import MockEngine`

**Subpackage `__init__.py`:**
- `src/cubano/engines/__init__.py` exists but may be empty or minimal
- `src/cubano/codegen/__init__.py` similarly minimal
- CLI entry at `src/cubano/cli/__init__.py`

**Zero runtime dependencies (core):**
- `src/cubano/` core has zero external runtime dependencies
- Optional dependencies (`databricks`, `snowflake`) imported lazily inside engine `__init__` with helpful `ImportError` messages
- CLI requires `typer` and `rich` (declared in `dependencies` in `pyproject.toml`)

## Immutability Patterns

**Frozen dataclasses** for value objects:
- `Query` is `@dataclass(frozen=True)` with private fields prefixed `_`
- `OrderTerm` is `@dataclass(frozen=True)`
- `FieldData`, `ModelData` in codegen are `@dataclass(frozen=True)`

**`MappingProxyType`** for read-only dicts:
- `SemanticView._fields: ClassVar[types.MappingProxyType[str, Field]]` prevents modification after class creation

**Metaclass freezing:**
- `SemanticViewMeta.__setattr__` raises `AttributeError` when `_frozen = True`

## Type Annotations

**All public signatures are fully annotated:**
- Parameters and return types on all methods and functions
- `ClassVar` for class-level attributes: `_view_name: ClassVar[str]`
- `Final` for module-level constants: `_default_name: Final[str] = "default"`

**Use `Any` sparingly, document why:**
- `query: Any` in SQL builder methods because `Query` would cause circular import
- `# type: ignore[...]` with specific error code when unavoidable

**Union types use `|` syntax (Python 3.10+):**
- `str | None`, `Dimension | Fact`, `Field | OrderTerm`
- `from __future__ import annotations` enables this in Python 3.11 files

---

*Convention analysis: 2026-02-17*
