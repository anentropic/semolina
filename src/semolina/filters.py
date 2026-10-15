"""
Predicate tree IR for Semolina filter expressions.

Defines the typed intermediate representation for all filter conditions:
- Predicate: base class with &, |, ~ composition operators
- And, Or, Not: composite nodes for boolean logic
- Lookup[T]: generic leaf base for field comparisons
- 16 core lookup subclasses: Exact, NotEqual, Gt, Gte, Lt, Lte, In, Between,
  IsNull, Like, ILike, StartsWith, IStartsWith, EndsWith, IEndsWith, IExact
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, ClassVar, Generic, TypeVar

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

    accepts_none: ClassVar[bool] = False
    """Whether ``None`` is a meaningful value: only for ``==`` and ``!=``."""

    def __post_init__(self) -> None:
        """
        Refuse ``None`` where the SQL would compare with ``NULL``.

        A comparison with ``NULL`` is never true, so the filter would match no row and say
        nothing about it (D3). ``==`` and ``!=`` are the exception: the compiler turns them
        into ``IS NULL`` and ``IS NOT NULL``.

        Raises:
            TypeError: If ``value`` is ``None`` and this lookup does not accept it.
        """
        if self.value is None and not self.accepts_none:
            raise TypeError(_none_message(f"{type(self).__name__}({self.field_name!r})"))


def _none_message(what: str) -> str:
    """
    Say why a comparison with ``None`` is refused, and what to write instead.

    Args:
        what: The filter that was given ``None``, as the message names it.

    Returns:
        The ``TypeError`` message.
    """
    return (
        f"{what} got None, and a SQL comparison with NULL matches no row. To match missing "
        f"values use .isnull(), or == None / != None, which compile to IS NULL / IS NOT NULL."
    )


# -- Core lookup subclasses (all backends must compile these) ------------------


class Exact(Lookup[Any]):
    """Equality: ``field = value``, or ``field IS NULL`` when ``value`` is ``None``."""

    accepts_none = True


class NotEqual(Lookup[Any]):
    """Inequality: ``field != value``, or ``field IS NOT NULL`` when ``value`` is ``None``."""

    accepts_none = True


class Gt(Lookup[Any]):
    """Greater than: ``field > value``."""


class Gte(Lookup[Any]):
    """Greater than or equal: ``field >= value``."""


class Lt(Lookup[Any]):
    """Less than: ``field < value``."""


class Lte(Lookup[Any]):
    """Less than or equal: ``field <= value``."""


@dataclass(frozen=True)
class In(Lookup[Iterable[Any]]):
    """
    Membership: ``field IN (values)``.

    The values are copied into a tuple when the predicate is built. The predicate then owns
    them: a later change to the caller's list cannot reach a query built earlier, and a
    generator is read once, here, rather than once per placeholder at compile time.

    Raises:
        TypeError: If ``value`` is a ``str`` or ``bytes``, which would otherwise be read as a
            collection of characters, is not iterable at all, or holds ``None``, which ``IN``
            never matches.
    """

    def __post_init__(self) -> None:
        """Copy the values into a tuple, refusing a string, a non-iterable and ``None``."""
        super().__post_init__()
        values = self.value
        if isinstance(values, str | bytes | bytearray):
            hint = f" To match one value, use in_([{values!r}])." if isinstance(values, str) else ""
            raise TypeError(
                f"in_() takes a collection of values, got {type(values).__name__}.{hint}"
            )
        try:
            iterator = iter(values)
        except TypeError:
            raise TypeError(
                f"in_() takes a collection of values, got {type(values).__name__}."
            ) from None
        copied = tuple(iterator)
        if any(value is None for value in copied):
            raise TypeError(
                _none_message(f"in_() on {self.field_name!r}")
                + " To include them, OR the in_() with .isnull()."
            )
        object.__setattr__(self, "value", copied)


class Between(Lookup[tuple[Any, Any]]):
    """
    Range: ``field BETWEEN lo AND hi``.

    Raises:
        TypeError: If either bound is ``None``. An open-ended range is ``>=`` or ``<=``.
    """

    def __post_init__(self) -> None:
        """Refuse a ``None`` bound, which would make the range match no row."""
        super().__post_init__()
        if any(bound is None for bound in self.value):
            raise TypeError(
                _none_message(f"between() on {self.field_name!r}")
                + " For an open-ended range use >= or <=."
            )


class IsNull(Lookup[bool]):
    """Null check: ``field IS NULL`` (value=True) or ``field IS NOT NULL`` (value=False)."""


class Like(Lookup[str]):
    """Pattern match (case-sensitive): ``field LIKE pattern``, wildcards passed through."""


class ILike(Lookup[str]):
    """Pattern match (case-insensitive): ``field ILIKE pattern``, wildcards passed through."""


class StartsWith(Lookup[str]):
    """Prefix match (case-sensitive): ``field LIKE 'value%' ESCAPE '!'``, value escaped."""


class IStartsWith(Lookup[str]):
    """Prefix match (case-insensitive): ``field ILIKE 'value%' ESCAPE '!'``, value escaped."""


class EndsWith(Lookup[str]):
    """Suffix match (case-sensitive): ``field LIKE '%value' ESCAPE '!'``, value escaped."""


class IEndsWith(Lookup[str]):
    """Suffix match (case-insensitive): ``field ILIKE '%value' ESCAPE '!'``, value escaped."""


class IExact(Lookup[str]):
    """Case-insensitive equality: ``field ILIKE value ESCAPE '!'``, value escaped."""
