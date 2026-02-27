# Semolina Filter / Query API — Design Decisions

Research and design session output (2026-02-20). Revised 2026-02-22 after Phase 13.1 discussion.

## Phase 13.1 Pre-Planning Clarifications (2026-02-22)

### Architecture: Typed Predicate Tree (replaces Q objects)

Q objects are removed. The filter IR is a typed predicate tree where every leaf node is a
`Lookup[T]` subclass — core lookups and custom/extension lookups use the same mechanism.

**Why:** The operator-overloading API means users never write `Q(field__lookup=value)` directly.
Q objects were an untyped string-keyed IR (`dict[str, Any]`) sitting between typed Field methods
and the typed compiler output. Removing them eliminates string parsing, makes the IR type-safe,
and collapses the "escape hatch" into the same mechanism as core lookups.

**Consequences:**
- The `__gte`/`__lte` vs `__ge`/`__le` naming debate is moot — no string lookup names exist
- The `__exact` suffix question is moot — `Field.__eq__` returns `Exact(...)` directly
- Lookup validation is structural — the compiler dispatches on node type, not string parsing
- The escape hatch IS the core mechanism — define a new `Lookup[T]` subclass, same as built-ins
- `filters.py` rewritten: Q class removed, replaced with predicate node types
- No separate `semolina/lookups.py` needed — everything lives in `filters.py`

### Predicate Tree Structure

```python
# filters.py — the complete IR

T = TypeVar("T")

# ── Composite nodes ──────────────────────────────────


class Predicate:
    """Base for all filter predicates. Supports &, |, ~ composition."""

    def __and__(self, other: Predicate) -> And: ...
    def __or__(self, other: Predicate) -> Or: ...
    def __invert__(self) -> Not: ...


@dataclass
class And(Predicate):
    left: Predicate
    right: Predicate


@dataclass
class Or(Predicate):
    left: Predicate
    right: Predicate


@dataclass
class Not(Predicate):
    inner: Predicate


# ── Leaf node base ───────────────────────────────────


@dataclass
class Lookup(Predicate, Generic[T]):
    """Typed leaf node. Subclass for each operation."""

    field_name: str
    value: T


# ── Core lookups (all backends must compile these) ───


class Exact(Lookup[Any]): ...


class Gt(Lookup[Any]): ...


class Gte(Lookup[Any]): ...


class Lt(Lookup[Any]): ...


class Lte(Lookup[Any]): ...


class In(
    Lookup[Any]
): ...  # value: list[T] enforced by Field.in_() signature


class Between(
    Lookup[Any]
): ...  # value: tuple[T, T] enforced by Field.between() signature


class IsNull(
    Lookup[bool]
): ...  # value=True means IS NULL; Not(IsNull) for IS NOT NULL


class Like(Lookup[str]): ...


class ILike(Lookup[str]): ...


class StartsWith(Lookup[str]): ...


class IStartsWith(Lookup[str]): ...


class EndsWith(Lookup[str]): ...


class IEndsWith(Lookup[str]): ...


class IExact(Lookup[str]): ...


# ── Extension lookups (same mechanism, backend-specific) ──

# Third-party example — NOT shipped in semolina core:
# class RLike(Lookup[str]): ...
# class ArrayContains(Lookup[list[str]]): ...
```

### Field Methods → Predicate Nodes

```python
# fields.py — operator overloads return typed predicates


def __eq__(self, value: Any) -> Exact:
    return Exact(field_name=self.name, value=value)


def __ne__(self, value: Any) -> Not:
    return Not(Exact(field_name=self.name, value=value))


def __ge__(self, value: Any) -> Gte:
    return Gte(field_name=self.name, value=value)


def between(self, lo: Any, hi: Any) -> Between:
    return Between(field_name=self.name, value=(lo, hi))


def in_(self, values: list[Any]) -> In:
    return In(field_name=self.name, value=values)


def isnull(self) -> IsNull:
    return IsNull(field_name=self.name, value=True)


# Escape hatch — same pattern:
def lookup(
    self, lookup_cls: type[Lookup[T]], value: T
) -> Lookup[T]:
    return lookup_cls(field_name=self.name, value=value)
```

### WHERE Compiler

```python
# engines/sql.py — pattern matching on node types


def _compile_predicate(self, node: Predicate) -> str:
    match node:
        case Exact(field_name=f, value=v):
            return f"{quote(f)} = {param(v)}"
        case Gte(field_name=f, value=v):
            return f"{quote(f)} >= {param(v)}"
        case Like(field_name=f, value=v):
            return f"{quote(f)} LIKE {param(v)}"
        case And(left=l, right=r):
            return f"({self._compile(l)} AND {self._compile(r)})"
        case Or(left=l, right=r):
            return f"({self._compile(l)} OR {self._compile(r)})"
        case Not(inner=i):
            return f"NOT ({self._compile(i)})"
        case Lookup():
            raise NotImplementedError(f"...")
```

### Decisions Summary

| Question | Decision |
|----------|----------|
| Filter IR | **Typed predicate tree** — replaces Q objects entirely |
| Leaf node type | **Unified `Lookup[T]`** — core and extension use the same base class |
| Escape hatch | **Just subclass `Lookup[T]`** — same mechanism as built-in lookups |
| Naming convention | **Moot** — no string lookup names; class names (`Gte`, `Lte`) are the identity |
| `__eq__` format | **Returns `Exact(...)`** — typed node, no string suffix |
| `__ne__` format | **Returns `Not(Exact(...))`** — composition, not a separate node type |
| Field methods to add | **Full set**: `between`, `in_`, `like`, `ilike`, `startswith`, `istartswith`, `endswith`, `iendswith`, `iexact`, `isnull` |
| WHERE compiler | **Pattern matching** on predicate node types — replaces `WHERE 1=1` placeholder |
| Lookup validation | **Structural** — compiler dispatches on type; unknown Lookup subclass → `NotImplementedError` |
| Separate lookups.py | **No** — `Lookup[T]` lives in `filters.py` alongside `Predicate`, `And`, `Or`, `Not` |

---

## Context

The WHERE clause in `src/semolina/engines/sql.py:438` is a placeholder returning `"WHERE 1=1"`.
The Q-object tree composition API (`src/semolina/filters.py`) exists and is fully designed —
nothing translates it to SQL yet. This was the right moment to settle the architecture before
the compiler gets built.

---

## Key Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Filter API style | **Field-method** — `D.date.between(start, end)` | Typed, discoverable, consistent with existing `>`, `>=`, `==` operators |
| Verbosity | **`D = DashboardMart` alias** | One line, zero magic, pyright happy |
| Static typing | **Non-negotiable** | No `__getattr__` proxy, no `Any`-typed shortcuts |
| SQLAlchemy | **No** | Zero-dep goal; dbt-sl has no SQL interface; filter set is small enough to hand-roll |
| Scope boundary | **Literal values on dimension columns only** | No F-objects, no expression trees, no cross-field references |
| F-objects | **Never** | Semantic views are aggregation targets — RHS is always a literal |
| Escape hatch | **Typed `Lookup[T]` subclasses** (unified with core lookups) | Pyright infers T; same mechanism for core and extension |
| RLIKE/regex | **Escape hatch only** | Three different regex engines (POSIX/Java/RE2); absent from Cube.dev |

---

## The API in Practice

```python
from datetime import date

D = DashboardMart  # one-line alias, fully typed

result = (
    D.query()
    .metrics(D.inspections_count, D.completion_rate)
    .dimensions(D.reporting_date, D.dealer_id)
    .where(
        D.reporting_date.between(
            date(2025, 1, 1), date(2025, 12, 31)
        )
        & D.dealer_id.in_(["D001", "D002"])
        & (D.currency == "USD")
    )
    .execute()
)

# Composition still works:
us_or_ca = (D.country == "US") | (D.country == "CA")
high_value = D.revenue > 10_000
result = (
    D.query()
    .metrics(D.revenue)
    .where(us_or_ca & high_value)
    .execute()
)

# NOT variant:
result = D.query().where(~D.region.isnull()).execute()

# Extension lookup — same pattern as core:
result = (
    D.query()
    .where(D.name.lookup(RLike, "^widget"))
    .execute()
)
```

---

## Settled Core Lookup Set

Cross-referenced: Snowflake, Databricks, DuckDB, Cube.dev, Django 6.0.
All implementable on every planned backend.

| Field method | Predicate node | SQL (Snowflake / Databricks / DuckDB) | Cube.dev API |
|-------------|---------------|--------------------------------------|--------------|
| `== value` | `Exact` | `= value` | `equals` |
| `!= value` | `Not(Exact)` | `<> value` | `notEquals` |
| `< value` | `Lt` | `< value` | `lt` |
| `> value` | `Gt` | `> value` | `gt` |
| `<= value` | `Lte` | `<= value` | `lte` |
| `>= value` | `Gte` | `>= value` | `gte` |
| `.between(lo, hi)` | `Between` | `BETWEEN lo AND hi` | `inDateRange` (time) / `gte`+`lte` (numeric) |
| `.in_([a, b, c])` | `In` | `IN (a, b, c)` | `equals` (multi-value) |
| `.isnull()` | `IsNull` | `IS NULL` | `notSet` |
| `.like("pat")` | `Like` | `LIKE '%pat%'` | `contains` |
| `.ilike("pat")` | `ILike` | `ILIKE '%pat%'` | `contains` (Cube is case-insensitive by default) |
| `.startswith("x")` | `StartsWith` | `LIKE 'x%'` | `startsWith` |
| `.istartswith("x")` | `IStartsWith` | `ILIKE 'x%'` | `startsWith` |
| `.endswith("x")` | `EndsWith` | `LIKE '%x'` | `endsWith` |
| `.iendswith("x")` | `IEndsWith` | `ILIKE '%x'` | `endsWith` |
| `.iexact("x")` | `IExact` | `ILIKE 'x'` (no wildcards) | `equals` |

NOT variants via `~predicate` (wraps in `Not(...)`) throughout.

**Out of core (extension Lookup subclasses):** RLIKE/REGEXP, ARRAY_CONTAINS, SEARCH,
NULL-safe equality, LIKE ANY/ALL — backend-specific or absent from Cube.dev.

**Out of scope entirely:** Django-style datetime extract transforms (`__year`, `__month`, etc.)
— semantic layers filter by date ranges, not extracted components.

---

## Architecture Note: Predicate Tree as Backend-Agnostic IR

The predicate tree is an intermediate representation — each engine compiles it independently:

- **SQL engines** (Snowflake, Databricks, DuckDB): `_compile_predicate()` pattern-matches on
  node types, emits SQL WHERE clause with dialect-specific identifier quoting and operator syntax.
- **Cube.dev engine** (future): `_compile_predicate()` pattern-matches on node types, emits
  Cube.dev JSON filter array with `{ member, operator, values }` objects.
- **Future engines**: implement their own compiler; predicate tree is the contract.
- **Extension lookups**: compiler hits `case Lookup()` catch-all → `NotImplementedError` unless
  the engine explicitly handles the subclass type.

This is why SQLAlchemy Core doesn't help — you'd need a separate compilation path for Cube.dev
regardless, and the filter set is small enough (~16 core lookups) that a hand-rolled SQL compiler
is ~100–150 lines.

---

## What Was Ruled Out

- **Q objects (string-keyed IR)**: Replaced by typed predicate tree. Q objects stored conditions
  as `dict[str, Any]` with string keys like `"revenue__gte"` — untyped, required string parsing,
  silently accepted invalid lookups. The typed tree makes all of this structural.
- **SQLModel**: SQLModel's query API is SQLAlchemy Core, not Pydantic-native. Has known
  pyright/mypy issues. Couples to two major library release cycles.
- **FilterSet (Pydantic model per view)**: Cannot express OR logic; requires per-view boilerplate
  class; the metadata-from-annotation problem needs its own infrastructure.
- **F-objects / expression trees**: Out of scope by design. Semantic views are aggregation
  targets; RHS of filters is always a literal.
- **Datetime extract transforms** (`__year`, `__month`): Out of scope. Use `.between()` on
  a date dimension instead.
- **RLIKE in core set**: Three different regex engines across backends; absent from Cube.dev.
- **Separate Comparison vs Lookup distinction**: Collapsed into unified `Lookup[T]` hierarchy.
  Core and extension lookups use the same base class, same mechanism. "Escape hatch" is just
  defining a new subclass.
