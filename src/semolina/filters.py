"""
Predicate tree IR for Cubano filter expressions.

Defines the typed intermediate representation for all filter conditions:
- Predicate: base class with &, |, ~ composition operators
- And, Or, Not: composite nodes for boolean logic
- Lookup[T]: generic leaf base for field comparisons
- 16 core lookup subclasses: Exact, NotEqual, Gt, Gte, Lt, Lte, In, Between,
  IsNull, Like, ILike, StartsWith, IStartsWith, EndsWith, IEndsWith, IExact
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Predicate:
    """
    Base for all filter predicates.

    Supports boolean composition via operators:
    - & (AND): ``Exact(...) & Gt(...)`` -> ``And(left, right)``
    - | (OR): ``Exact(...) | Exact(...)`` -> ``Or(left, right)``
    - ~ (NOT): ``~Exact(...)`` -> ``Not(inner)``

    Predicate is a plain class (not a dataclass). Composite nodes (And, Or, Not)
    and leaf nodes (Lookup subclasses) are frozen dataclasses.
    """

    def __and__(self, other: Predicate) -> And:
        """Combine with AND: ``a & b`` -> ``And(left=a, right=b)``."""
        return And(left=self, right=other)

    def __or__(self, other: Predicate) -> Or:
        """Combine with OR: ``a | b`` -> ``Or(left=a, right=b)``."""
        return Or(left=self, right=other)

    def __invert__(self) -> Not:
        """Negate with NOT: ``~a`` -> ``Not(inner=a)``."""
        return Not(inner=self)


# -- Composite nodes ----------------------------------------------------------


@dataclass(frozen=True)
class And(Predicate):
    """
    AND composition of two predicates.

    Created by the ``&`` operator: ``left & right``.
    """

    left: Predicate
    right: Predicate


@dataclass(frozen=True)
class Or(Predicate):
    """
    OR composition of two predicates.

    Created by the ``|`` operator: ``left | right``.
    """

    left: Predicate
    right: Predicate


@dataclass(frozen=True)
class Not(Predicate):
    """
    NOT negation of a predicate.

    Created by the ``~`` operator: ``~inner``.
    """

    inner: Predicate


# -- Leaf node base ------------------------------------------------------------


@dataclass(frozen=True)
class Lookup(Predicate, Generic[T]):
    """
    Typed leaf node for field comparisons.

    Every lookup has a ``field_name`` (the Python attribute name), a
    ``value`` (the comparison operand), and an optional ``source``
    (the explicit SQL column name override from ``Field.source=``).

    When ``source`` is set, it is used verbatim in WHERE clause compilation
    instead of applying dialect normalization to ``field_name``. When
    ``source`` is ``None`` (the default), the dialect's
    ``normalize_identifier`` is applied to ``field_name`` at compile time.
    """

    field_name: str
    value: T
    source: str | None = field(default=None, repr=False)


# -- Core lookup subclasses (all backends must compile these) ------------------


class Exact(Lookup[Any]):
    """Equality: ``field = value``."""


class NotEqual(Lookup[Any]):
    """Inequality: ``field != value``."""


class Gt(Lookup[Any]):
    """Greater than: ``field > value``."""


class Gte(Lookup[Any]):
    """Greater than or equal: ``field >= value``."""


class Lt(Lookup[Any]):
    """Less than: ``field < value``."""


class Lte(Lookup[Any]):
    """Less than or equal: ``field <= value``."""


class In(Lookup[Collection[Any]]):
    """Membership: ``field IN (values)``."""


class Between(Lookup[tuple[Any, Any]]):
    """Range: ``field BETWEEN lo AND hi``."""


class IsNull(Lookup[bool]):
    """Null check: ``field IS NULL`` (value=True) or ``field IS NOT NULL`` (value=False)."""


class Like(Lookup[str]):
    """Pattern match (case-sensitive): ``field LIKE pattern``."""


class ILike(Lookup[str]):
    """Pattern match (case-insensitive): ``field ILIKE pattern``."""


class StartsWith(Lookup[str]):
    """Prefix match (case-sensitive): ``field LIKE 'value%'``."""


class IStartsWith(Lookup[str]):
    """Prefix match (case-insensitive): ``field ILIKE 'value%'``."""


class EndsWith(Lookup[str]):
    """Suffix match (case-sensitive): ``field LIKE '%value'``."""


class IEndsWith(Lookup[str]):
    """Suffix match (case-insensitive): ``field ILIKE '%value'``."""


class IExact(Lookup[str]):
    """Case-insensitive equality: ``field ILIKE value`` (no wildcards)."""
