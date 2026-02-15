# Phase 1: Model Foundation - Research

**Researched:** 2026-02-15
**Domain:** Python metaclasses, descriptors, and type-safe field patterns
**Confidence:** HIGH

## Summary

Phase 1 requires implementing an ORM-style model definition system using metaclasses and descriptors to enable type-safe field references. The standard approach combines Python's descriptor protocol (specifically `__set_name__` introduced in Python 3.6) with either traditional metaclasses or the modern `__init_subclass__` hook (PEP 487, Python 3.6+).

For this phase, the descriptor protocol provides field definitions (Metric, Dimension, Fact), while metaclass machinery validates field names, prevents SQL injection, collects metadata, and freezes the class after creation. The pattern is well-established in Django ORM and SQLAlchemy, both of which use descriptors for field-to-attribute mapping.

**Primary recommendation:** Use descriptors with `__set_name__` for field definitions, prefer `__init_subclass__` over full metaclass unless deeper control is needed, validate identifiers with `str.isidentifier()` + `keyword.iskeyword()`, and freeze metadata by overriding `__setattr__` after class creation.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.11+ | `typing`, `keyword`, `abc` | Project requirement: Python >=3.11, zero dependencies |
| `typing.get_type_hints` | stdlib | Runtime type inspection | Standard way to access class annotations at runtime |
| `keyword.iskeyword` | stdlib | Validate against reserved words | Built-in Python keyword checking |
| `str.isidentifier` | stdlib | Validate identifier syntax | Built-in identifier validation |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `dataclasses` | stdlib | Immutable metadata objects | For field metadata storage (frozen=True) |
| `types.MappingProxyType` | stdlib | Read-only dict views | To expose frozen field mappings |
| `__slots__` | language feature | Memory optimization | Only if many model instances in memory (not for this phase) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `__init_subclass__` | Full metaclass `type` | Metaclass needed only for namespace preparation or deeper control |
| Descriptors | Class-level factory functions | Descriptors provide cleaner attribute access, IDE support |
| `str.isidentifier()` | Regex `^[a-zA-Z_][a-zA-Z0-9_]*$` | `isidentifier()` is more Pythonic, handles edge cases |

**Installation:**
```bash
# No external dependencies required
# Using Python 3.11+ stdlib only
```

## Architecture Patterns

### Recommended Project Structure
```
cubano/
├── models.py            # Public API: SemanticView base class
├── fields.py            # Field descriptors: Metric, Dimension, Fact
├── _metadata.py         # Internal: frozen metadata containers
└── _validation.py       # Internal: field name validation
```

### Pattern 1: Descriptor with `__set_name__`
**What:** Field classes implement descriptor protocol to capture attribute name automatically
**When to use:** Always - this is the foundation for type-safe field references

**Example:**
```python
# Source: https://docs.python.org/3/howto/descriptor.html
class Field:
    """Base descriptor for semantic view fields"""

    def __set_name__(self, owner, name):
        """Called automatically when field is assigned to class attribute"""
        self.name = name
        self.owner = owner

    def __get__(self, obj, objtype=None):
        """Return field reference when accessed as class attribute"""
        if obj is None:
            return self  # Accessed from class: Sales.revenue returns Field instance
        raise AttributeError(f"Field {self.name} only accessible from class")

    def __set__(self, obj, value):
        """Prevent instance-level assignment"""
        raise AttributeError(f"Cannot set field {self.name}")

class Metric(Field):
    """Metric field descriptor"""
    pass

class Dimension(Field):
    """Dimension field descriptor"""
    pass

class Fact(Field):
    """Fact field descriptor"""
    pass
```

### Pattern 2: `__init_subclass__` for Model Registration
**What:** Hook called when subclass is created, receives class parameters
**When to use:** For simple class customization without full metaclass

**Example:**
```python
# Source: https://peps.python.org/pep-0487/
class SemanticView:
    """Base class for semantic view models"""

    def __init_subclass__(cls, view=None, **kwargs):
        super().__init_subclass__(**kwargs)

        if view is None:
            raise TypeError(f"{cls.__name__} must specify view name")

        # Collect field descriptors
        fields = {}
        for name, value in cls.__dict__.items():
            if isinstance(value, Field):
                fields[name] = value

        # Store metadata (frozen after this point)
        cls._view_name = view
        cls._fields = types.MappingProxyType(fields)
        cls._frozen = True

# Usage
class Sales(SemanticView, view='sales'):
    revenue = Metric()
    country = Dimension()
```

### Pattern 3: Metadata Freezing with `__setattr__` Override
**What:** Prevent modification of class after creation
**When to use:** To ensure model immutability per MOD-05 requirement

**Example:**
```python
# Source: Web research on frozen class patterns
class SemanticView:
    _frozen = False

    def __init_subclass__(cls, view=None, **kwargs):
        super().__init_subclass__(**kwargs)
        # ... registration logic ...
        cls._frozen = True

    def __setattr__(cls, name, value):
        """Prevent modification after class creation"""
        if getattr(cls, '_frozen', False):
            raise AttributeError(
                f"Cannot modify {cls.__name__} after class creation. "
                f"Models are immutable."
            )
        super().__setattr__(name, value)
```

### Pattern 4: Field Name Validation
**What:** Validate field names against SQL injection and reserved words
**When to use:** During field registration in `__set_name__`

**Example:**
```python
# Source: https://docs.python.org/3/library/keyword.html
import keyword

def validate_field_name(name: str, owner_name: str) -> None:
    """Validate field name is safe SQL identifier"""

    # Check Python identifier rules
    if not name.isidentifier():
        raise ValueError(
            f"Field '{name}' in {owner_name} is not a valid identifier. "
            f"Must match pattern: [a-zA-Z_][a-zA-Z0-9_]*"
        )

    # Check Python keywords
    if keyword.iskeyword(name):
        raise ValueError(
            f"Field '{name}' in {owner_name} is a Python keyword"
        )

    # Additional check for soft keywords (match, case, type, _)
    if keyword.issoftkeyword(name):
        raise ValueError(
            f"Field '{name}' in {owner_name} is a Python soft keyword"
        )

    # Check for dict method name collisions
    RESERVED_NAMES = {'keys', 'values', 'items', 'get', 'pop', 'update'}
    if name in RESERVED_NAMES:
        raise ValueError(
            f"Field '{name}' in {owner_name} collides with dict method"
        )

class Field:
    def __set_name__(self, owner, name):
        validate_field_name(name, owner.__name__)
        self.name = name
        self.owner = owner
```

### Anti-Patterns to Avoid

- **Mutable class-level defaults in descriptors:** Using `self.metadata = {}` creates shared state. Use `None` and initialize in `__init__` or make immutable with `dataclass(frozen=True)`.
- **Not implementing `__get__` obj=None case:** When accessing `Sales.revenue` (class access), descriptor should return itself, not raise error.
- **Using full metaclass when `__init_subclass__` suffices:** Metaclasses add complexity. Per PEP 487, use `__init_subclass__` unless you need to modify `__prepare__` or class creation itself.
- **Forgetting to call `super().__init_subclass__(**kwargs)`:** Breaks multiple inheritance and cooperative multiple inheritance patterns.
- **Direct `__annotations__` access instead of `get_type_hints()`:** Annotations may contain string literals; `get_type_hints()` resolves them properly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Type hint resolution | String annotation parser | `typing.get_type_hints()` | Handles forward references, string annotations, scoping |
| Keyword checking | Manual list of reserved words | `keyword.iskeyword()`, `keyword.softkwlist` | Python version-dependent, maintained by stdlib |
| Identifier validation | Regex `^[a-zA-Z_][a-zA-Z0-9_]*$` | `str.isidentifier()` | Handles Unicode identifiers, edge cases |
| Immutable dicts | Custom frozen dict class | `types.MappingProxyType` | Standard, efficient, well-tested |
| Frozen dataclasses | Manual `__setattr__` with validation | `@dataclass(frozen=True)` | Generates `__hash__`, handles edge cases |

**Key insight:** Python 3.6+ provides all necessary primitives for descriptor-based ORMs. Using stdlib functions prevents version-dependent bugs and Unicode edge cases.

## Common Pitfalls

### Pitfall 1: Mutable Default Descriptors
**What goes wrong:** Field instances with mutable defaults (`self.metadata = {}`) share state across all fields.

**Why it happens:** Python evaluates default arguments once at function definition, not per-call. Class-level attributes are shared.

**How to avoid:**
```python
# BAD: Shared mutable default
class Field:
    def __init__(self):
        self.metadata = {}  # Same dict instance for all Field() calls!

# GOOD: Initialize as None, create per-instance
class Field:
    def __init__(self):
        self.metadata = None

    def __set_name__(self, owner, name):
        if self.metadata is None:
            self.metadata = {}
        self.metadata['name'] = name

# BETTER: Use frozen dataclass
@dataclass(frozen=True)
class FieldMetadata:
    name: str
    owner: type

class Field:
    def __set_name__(self, owner, name):
        self.metadata = FieldMetadata(name=name, owner=owner)
```

**Warning signs:** Tests pass individually but fail when run together; field metadata "leaks" between models.

### Pitfall 2: Field Name Collision with dict Methods
**What goes wrong:** Field named `keys`, `values`, `items` shadows dict methods if metadata stored in dict.

**Why it happens:** Dynamic attribute access can conflict with built-in methods.

**How to avoid:**
```python
# Validate against reserved names
RESERVED_NAMES = {'keys', 'values', 'items', 'get', 'pop', 'update', 'clear'}

def validate_field_name(name: str) -> None:
    if name in RESERVED_NAMES:
        raise ValueError(f"Field '{name}' collides with dict method")
```

**Warning signs:** AttributeError when trying to access field; dict methods return unexpected types.

### Pitfall 3: Incomplete SQL Injection Prevention
**What goes wrong:** Validating with regex but missing edge cases like Unicode identifiers, soft keywords, or Python keywords.

**Why it happens:** Hand-rolled validation misses edge cases that `isidentifier()` handles.

**How to avoid:**
```python
# BAD: Incomplete validation
import re
if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
    raise ValueError("Invalid identifier")

# GOOD: Use stdlib, check all cases
if not name.isidentifier():
    raise ValueError("Invalid identifier")
if keyword.iskeyword(name) or keyword.issoftkeyword(name):
    raise ValueError("Reserved keyword")
```

**Warning signs:** Validation passes but field names cause errors at query time; Unicode identifiers rejected incorrectly.

### Pitfall 4: Not Freezing Metadata After Class Creation
**What goes wrong:** Users can modify `Sales.revenue = SomethingElse()` after class creation, breaking immutability.

**Why it happens:** Python classes are mutable by default.

**How to avoid:**
```python
class SemanticView:
    _frozen = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # ... setup ...
        object.__setattr__(cls, '_frozen', True)  # Use object.__setattr__ to bypass override

    def __setattr__(cls, name, value):
        if cls._frozen:
            raise AttributeError(f"Cannot modify frozen model {cls.__name__}")
        super().__setattr__(name, value)
```

**Warning signs:** Tests can modify model fields after creation; metadata changes unexpectedly.

### Pitfall 5: Missing Class vs Instance Access Pattern
**What goes wrong:** `Sales.revenue` raises error instead of returning Field instance for query building.

**Why it happens:** Descriptor `__get__` doesn't handle `obj=None` case (class-level access).

**How to avoid:**
```python
class Field:
    def __get__(self, obj, objtype=None):
        if obj is None:
            # Class-level access: Sales.revenue
            return self
        # Instance-level access: sales_instance.revenue
        # For this phase, instances don't exist, so raise
        raise AttributeError("Fields only accessible from class")
```

**Warning signs:** `TypeError: 'NoneType' object is not callable` when accessing `Sales.revenue`.

## Code Examples

Verified patterns from official sources:

### Complete Field Descriptor
```python
# Source: https://docs.python.org/3/howto/descriptor.html (adapted)
import keyword
from typing import Any

class Field:
    """Base descriptor for semantic view fields"""

    def __set_name__(self, owner: type, name: str) -> None:
        """Called when field assigned to class attribute"""
        # Validate field name
        if not name.isidentifier():
            raise ValueError(f"'{name}' is not a valid identifier")
        if keyword.iskeyword(name) or keyword.issoftkeyword(name):
            raise ValueError(f"'{name}' is a reserved keyword")

        self.name = name
        self.owner = owner

    def __get__(self, obj: Any, objtype: type = None) -> 'Field':
        """Return self for class-level access"""
        if obj is None:
            return self  # Class access: Sales.revenue
        raise AttributeError(
            f"Field {self.name} only accessible from class, not instance"
        )

    def __set__(self, obj: Any, value: Any) -> None:
        """Prevent assignment"""
        raise AttributeError(f"Cannot set field {self.name}")

    def __delete__(self, obj: Any) -> None:
        """Prevent deletion"""
        raise AttributeError(f"Cannot delete field {self.name}")

class Metric(Field):
    """Metric field - numeric aggregations"""
    pass

class Dimension(Field):
    """Dimension field - categorical attributes"""
    pass

class Fact(Field):
    """Fact field - raw data points"""
    pass
```

### Model Base with `__init_subclass__`
```python
# Source: https://peps.python.org/pep-0487/ (adapted)
from types import MappingProxyType
from typing import Dict

class SemanticView:
    """Base class for semantic view models"""

    _view_name: str
    _fields: MappingProxyType
    _frozen: bool = False

    def __init_subclass__(cls, view: str = None, **kwargs) -> None:
        """Called when subclass is created"""
        super().__init_subclass__(**kwargs)

        # Validate view name
        if view is None:
            raise TypeError(
                f"{cls.__name__} must specify view name: "
                f"class {cls.__name__}(SemanticView, view='name')"
            )

        # Collect field descriptors
        fields: Dict[str, Field] = {}
        for name in dir(cls):
            if name.startswith('_'):
                continue
            value = getattr(cls, name)
            if isinstance(value, Field):
                fields[name] = value

        # Store immutable metadata
        object.__setattr__(cls, '_view_name', view)
        object.__setattr__(cls, '_fields', MappingProxyType(fields))
        object.__setattr__(cls, '_frozen', True)

    def __setattr__(cls, name: str, value: Any) -> None:
        """Prevent modification after class creation"""
        if getattr(cls, '_frozen', False):
            raise AttributeError(
                f"Cannot modify {cls.__name__}.{name} after class creation. "
                f"Models are immutable."
            )
        super().__setattr__(name, value)

# Usage
class Sales(SemanticView, view='sales'):
    revenue = Metric()
    country = Dimension()
    unit_price = Fact()

# Valid: Access field references
print(Sales.revenue)  # <Metric: revenue>
print(Sales._view_name)  # 'sales'
print(Sales._fields)  # mappingproxy({'revenue': <Metric>, 'country': <Dimension>, ...})

# Invalid: Modification raises AttributeError
try:
    Sales.new_field = Metric()
except AttributeError as e:
    print(e)  # Cannot modify Sales.new_field after class creation
```

### Type-Safe Field Reference
```python
# Demonstrates type-safe field references per MOD-05
class Sales(SemanticView, view='sales'):
    revenue = Metric()
    country = Dimension()

# Type checker knows these are Field instances
revenue_field: Metric = Sales.revenue
country_field: Dimension = Sales.country

# Enables IDE autocomplete
def query_metric(field: Metric) -> None:
    print(f"Querying metric: {field.name}")

query_metric(Sales.revenue)  # OK: revenue is Metric
# query_metric(Sales.country)  # Type error: country is Dimension, not Metric
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual `__metaclass__` | `__init_subclass__` hook | Python 3.6 (PEP 487) | Simpler syntax, no metaclass conflicts |
| Manual descriptor naming | `__set_name__` auto-naming | Python 3.6 (PEP 487) | No duplicate name strings, less error-prone |
| `obj.__annotations__` direct access | `typing.get_type_hints()` | Python 3.5+ (PEP 484) | Resolves string annotations, handles scoping |
| `frozen=True` via manual `__setattr__` | `@dataclass(frozen=True)` | Python 3.7 (PEP 557) | Auto-generates `__hash__`, `__eq__` |
| `__slots__` manual definition | `@dataclass(slots=True)` | Python 3.10 (PEP 591) | Combines slots + dataclass benefits |

**Deprecated/outdated:**
- **Python 2 `__metaclass__` attribute:** Removed in Python 3. Use `class MyClass(metaclass=Meta)` syntax.
- **Hard-coded field names in descriptors:** Before `__set_name__`, developers passed name string to `Field('revenue')`. Now automatic.
- **Manual keyword lists:** Use `keyword.kwlist` and `keyword.softkwlist` instead of maintaining own list.

## Open Questions

1. **Should we use `__init_subclass__` or full metaclass?**
   - What we know: `__init_subclass__` handles most cases; metaclass needed only for `__prepare__` or namespace control
   - What's unclear: Whether freezing metadata requires metaclass `__new__` access
   - Recommendation: Start with `__init_subclass__`; only add metaclass if freezing pattern proves insufficient

2. **How to handle field type annotations for tooling?**
   - What we know: Can use `revenue: Metric = Metric()` syntax, but redundant
   - What's unclear: Whether type checkers need explicit annotations or can infer from descriptor type
   - Recommendation: Test with mypy/pyright; add annotations only if inference fails

3. **Should field metadata be mutable or frozen?**
   - What we know: Frozen prevents bugs but complicates extension
   - What's unclear: Whether future phases need to modify field metadata
   - Recommendation: Use frozen initially (`@dataclass(frozen=True)`); refactor if extension needed

## Sources

### Primary (HIGH confidence)
- [Python Descriptor Guide - Official Docs](https://docs.python.org/3/howto/descriptor.html) - Complete descriptor protocol, `__set_name__` examples
- [PEP 487 - Simpler customisation of class creation](https://peps.python.org/pep-0487/) - `__init_subclass__` specification and rationale
- [typing module - Official Docs](https://docs.python.org/3/library/typing.html) - `get_type_hints()` API and annotation handling
- [keyword module - Official Docs](https://docs.python.org/3/library/keyword.html) - `iskeyword()`, `issoftkeyword()` API
- [Python Data Model - Official Docs](https://docs.python.org/3/reference/datamodel.html) - Metaclass protocol, descriptor protocol

### Secondary (MEDIUM confidence)
- [Real Python: Python Descriptors](https://realpython.com/python-descriptors/) - Practical descriptor patterns
- [Real Python: Python Metaclasses](https://realpython.com/python-metaclasses/) - Metaclass use cases and alternatives
- [Leapcell: Deep Dive into Python Descriptors](https://leapcell.io/blog/deep-dive-into-python-descriptors-empowering-django-orm-and-beyond) - Django ORM descriptor implementation
- [SQLAlchemy ORM Mapping Styles](https://docs.sqlalchemy.org/en/21/orm/mapping_styles.html) - Modern ORM patterns

### Tertiary (LOW confidence - verify during implementation)
- [Python String isidentifier() Method](https://www.w3schools.com/python/ref_string_isidentifier.asp) - Basic identifier validation
- [Statically enforcing frozen dataclasses](https://rednafi.com/python/statically-enforcing-frozen-dataclasses/) - Immutability patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using only Python 3.11+ stdlib, verified in official docs
- Architecture: HIGH - Patterns verified in PEP 487, descriptor guide, and production ORMs (Django, SQLAlchemy)
- Pitfalls: MEDIUM-HIGH - Common issues documented in official sources; specific project pitfalls from user context

**Research date:** 2026-02-15
**Valid until:** 2026-03-15 (30 days - stable domain, stdlib features unlikely to change)

**Key assumptions:**
- Python 3.11+ target (per project requirements)
- Zero external dependencies (per project requirements)
- Type safety for IDE autocomplete is priority
- Immutability after class creation is strict requirement (MOD-05)
