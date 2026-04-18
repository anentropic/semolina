"""
Field descriptors for Semolina semantic models.

Descriptor classes for defining typed fields in semantic view models.
Fields use the descriptor protocol for class-level access and validation.
"""

from __future__ import annotations

import keyword
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, Self, TypeVar, overload

T = TypeVar("T")

# Names that would conflict with query builder methods or dict-like interface
RESERVED_FIELD_NAMES = frozenset(
    {
        "query",  # entry point
        "metrics",  # field selection
        "dimensions",  # field selection
        "where",  # filtering
        "filter",  # internal filtering
        "order_by",  # ordering
        "limit",  # limiting
        "execute",  # eager execution
        "to_sql",  # SQL generation
        "using",  # engine selection
        "keys",
        "values",
        "items",
        "get",
        "pop",
        "update",
        "clear",  # dict methods
    }
)

if TYPE_CHECKING:
    from .filters import (
        Between,
        EndsWith,
        Exact,
        Gt,
        Gte,
        IEndsWith,
        IExact,
        ILike,
        In,
        IsNull,
        IStartsWith,
        Like,
        Lookup,
        Lt,
        Lte,
        NotEqual,
        StartsWith,
    )


class NullsOrdering(Enum):
    """
    How to position NULL values in ORDER BY clause.

    Attributes:
        FIRST: NULLS FIRST - NULL values appear before non-NULL values
        LAST: NULLS LAST - NULL values appear after non-NULL values
        DEFAULT: No NULLS clause - let backend decide
    """

    FIRST = "FIRST"
    LAST = "LAST"
    DEFAULT = None

    def __repr__(self) -> str:
        """Return readable representation."""
        if self.value is None:
            return "DEFAULT"
        return f"NULLS {self.value}"


def _check_name(name: str | None) -> str:
    """
    Validate that field name has been set via __set_name__.

    Args:
        name: The field name to check.

    Returns:
        The validated field name.

    Raises:
        RuntimeError: If name is None (field used before __set_name__ called).
    """
    if name is None:
        raise RuntimeError("Field operator used before __set_name__ called")
    return name


class Field(Generic[T]):
    """
    Base descriptor for semantic view fields.

    Fields are descriptors that:
    - Validate field names at class creation time (__set_name__)
    - Return themselves for class-level access (Sales.revenue)
    - Prevent instance-level access, modification, and deletion
    - Support Python comparison operators to create Predicate filters

    Operators:
        Field descriptors support Python comparison operators that return
        typed Predicate nodes::

            Users.country == 'US'      # -> Exact(field_name='country', value='US')
            Users.country != 'CA'      # -> NotEqual(field_name='country', value='CA')
            Users.revenue > 1000       # -> Gt(field_name='revenue', value=1000)
            Users.revenue >= 1000      # -> Gte(...)
            Users.revenue < 100        # -> Lt(...)
            Users.revenue <= 100       # -> Lte(...)

        Combine with & (AND) and | (OR)::

            (Users.country == 'US') | (Users.country == 'CA')  # -> Or(...)
            (Users.revenue > 1000) & (Users.country == 'US')   # -> And(...)

    Named filter methods:
        Additional filter methods for common SQL operations::

            Users.country.in_(['US', 'CA'])      # -> In(...)
            Users.revenue.between(100, 1000)     # -> Between(...)
            Users.name.like('%Smith%')            # -> Like(...)
            Users.name.ilike('%smith%')           # -> ILike(...)
            Users.name.startswith('A')            # -> StartsWith(...)
            Users.name.endswith('son')            # -> EndsWith(...)
            Users.country.iexact('united states') # -> IExact(...)
            Users.country.isnull()                # -> IsNull(...)
    """

    def __init__(self, source: str | None = None) -> None:
        """
        Initialize field descriptor.

        Args:
            source: Optional explicit SQL column name. When set, the SQL builder uses this
                string verbatim (after quoting) instead of deriving the column name from the
                Python field name via dialect normalization. Use this when the warehouse column
                name cannot be recovered by normalizing the Python attribute name — for example,
                a Snowflake column created with a quoted lowercase identifier::

                    # Snowflake column "order_id" (quoted lowercase, case-preserved)
                    order_id = Metric(source="order_id")

                When source is None (the default), the SQL builder applies
                ``dialect.normalize_identifier(field.name)`` to derive the column name.
        """
        self.name: str | None = None
        self.source: str | None = source
        self.owner: type | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        """
        Called when field is assigned to a class attribute.

        Validates the field name to ensure it's a valid identifier and
        doesn't conflict with Python keywords or reserved names.

        Args:
            owner: The class that owns this field
            name: The name of the attribute

        Raises:
            ValueError: If name is not a valid identifier, is a Python keyword,
                       or is a reserved name that would conflict with dict methods
        """
        # Check valid identifier syntax
        if not name.isidentifier():
            raise ValueError(f"Field name '{name}' is not a valid Python identifier")

        # Check Python keywords
        if keyword.iskeyword(name):
            raise ValueError(f"Field name '{name}' is a Python keyword and cannot be used")

        # Check soft keywords (e.g., match, case in Python 3.10+)
        if keyword.issoftkeyword(name):
            raise ValueError(f"Field name '{name}' is a Python soft keyword and cannot be used")

        self.name = name
        self.owner = owner

    @overload
    def __get__(self, obj: None, cls: type) -> Self: ...

    @overload
    def __get__(self, obj: object, cls: type) -> T: ...

    def __get__(self, obj: object | None, cls: type) -> Self | T:
        """
        Return field descriptor for class-level access.

        Args:
            obj: The instance accessing the field (None for class access)
            cls: The class that owns this field

        Returns:
            The field descriptor itself when accessed from the class (obj is None).

        Raises:
            AttributeError: If accessed from an instance rather than class
        """
        if obj is None:
            return self
        raise AttributeError(
            f"Field '{self.name}' cannot be accessed from instances. "
            f"Use {cls.__name__}.{self.name} instead."
        )

    def __set__(self, instance: Any, value: Any) -> None:
        """
        Prevent field assignment.

        Raises:
            AttributeError: Always, as fields are immutable
        """
        raise AttributeError(f"Field '{self.name}' cannot be modified. Fields are immutable.")

    def __delete__(self, instance: Any) -> None:
        """
        Prevent field deletion.

        Raises:
            AttributeError: Always, as fields cannot be deleted
        """
        raise AttributeError(f"Field '{self.name}' cannot be deleted. Fields are immutable.")

    def __repr__(self) -> str:
        """
        Return informative repr showing field type and name.

        Shows ``TypeName('field_name')`` for bound fields,
        ``TypeName('field_name', source='SOURCE')`` when a source is set, or
        ``TypeName(unbound)`` for fields not yet attached to a model.
        """
        cls_name = type(self).__name__
        if self.name is None:
            return f"{cls_name}(unbound)"
        if self.source is not None:
            return f"{cls_name}('{self.name}', source='{self.source}')"
        return f"{cls_name}('{self.name}')"

    # -- Comparison operators returning Predicate nodes -----------------------

    def __eq__(self, value: Any) -> Exact:
        """
        Create equality predicate: ``field == value``.

        Returns an Exact predicate node for this field.

        Args:
            value: The value to compare against.

        Returns:
            Exact predicate with this field's name and the given value.

        Example:
            .. code-block:: pycon

                >>> Users.country == 'US'  # doctest: +SKIP
                Exact(field_name='country', value='US')
        """
        name = _check_name(self.name)
        from .filters import Exact as _Exact

        return _Exact(field_name=name, value=value, source=self.source)

    def __ne__(self, value: Any) -> NotEqual:
        """
        Create inequality predicate: ``field != value``.

        Returns NotEqual(...) predicate node.

        Args:
            value: The value to compare against.

        Returns:
            NotEqual predicate with this field's name and the given value.

        Example:
            .. code-block:: pycon

                >>> Users.country != 'US'  # doctest: +SKIP
                NotEqual(field_name='country', value='US')
        """
        name = _check_name(self.name)
        from .filters import NotEqual as _NotEqual

        return _NotEqual(field_name=name, value=value, source=self.source)

    def __lt__(self, value: Any) -> Lt:
        """
        Create less-than predicate: ``field < value``.

        Args:
            value: The value to compare against.

        Returns:
            Lt predicate node.

        Example:
            .. code-block:: pycon

                >>> Users.age < 30  # doctest: +SKIP
                Lt(field_name='age', value=30)
        """
        name = _check_name(self.name)
        from .filters import Lt as _Lt

        return _Lt(field_name=name, value=value, source=self.source)

    def __le__(self, value: Any) -> Lte:
        """
        Create less-than-or-equal predicate: ``field <= value``.

        Args:
            value: The value to compare against.

        Returns:
            Lte predicate node.

        Example:
            .. code-block:: pycon

                >>> Users.age <= 30  # doctest: +SKIP
                Lte(field_name='age', value=30)
        """
        name = _check_name(self.name)
        from .filters import Lte as _Lte

        return _Lte(field_name=name, value=value, source=self.source)

    def __gt__(self, value: Any) -> Gt:
        """
        Create greater-than predicate: ``field > value``.

        Args:
            value: The value to compare against.

        Returns:
            Gt predicate node.

        Example:
            .. code-block:: pycon

                >>> Users.revenue > 1000  # doctest: +SKIP
                Gt(field_name='revenue', value=1000)
        """
        name = _check_name(self.name)
        from .filters import Gt as _Gt

        return _Gt(field_name=name, value=value, source=self.source)

    def __ge__(self, value: Any) -> Gte:
        """
        Create greater-than-or-equal predicate: ``field >= value``.

        Args:
            value: The value to compare against.

        Returns:
            Gte predicate node.

        Example:
            .. code-block:: pycon

                >>> Users.revenue >= 1000  # doctest: +SKIP
                Gte(field_name='revenue', value=1000)
        """
        name = _check_name(self.name)
        from .filters import Gte as _Gte

        return _Gte(field_name=name, value=value, source=self.source)

    # Preserve identity-based hashing even with __eq__ defined
    # (Python sets __hash__ = None when __eq__ is defined without explicit __hash__)
    __hash__ = object.__hash__

    # -- Named filter methods -------------------------------------------------

    def between(self, lo: Any, hi: Any) -> Between:
        """
        Create range predicate: ``field BETWEEN lo AND hi``.

        Args:
            lo: Lower bound (inclusive).
            hi: Upper bound (inclusive).

        Returns:
            Between predicate with value as (lo, hi) tuple.

        Example:
            .. code-block:: pycon

                >>> Sales.revenue.between(100, 1000)  # doctest: +SKIP
                Between(field_name='revenue', value=(100, 1000))
        """
        name = _check_name(self.name)
        from .filters import Between as _Between

        return _Between(field_name=name, value=(lo, hi), source=self.source)

    def in_(self, values: Any) -> In:
        """
        Create membership predicate: ``field IN (values)``.

        Args:
            values: Collection of values to check membership against.

        Returns:
            In predicate with the given values.

        Example:
            .. code-block:: pycon

                >>> Sales.country.in_(['US', 'CA', 'UK'])  # doctest: +SKIP
                In(field_name='country', value=['US', 'CA', 'UK'])
        """
        name = _check_name(self.name)
        from .filters import In as _In

        return _In(field_name=name, value=values, source=self.source)

    def like(self, pattern: str) -> Like:
        """
        Create case-sensitive pattern match: ``field LIKE pattern``.

        Args:
            pattern: SQL LIKE pattern (use % and _ wildcards).

        Returns:
            Like predicate with the given pattern.

        Example:
            .. code-block:: pycon

                >>> Users.name.like('%Smith%')  # doctest: +SKIP
                Like(field_name='name', value='%Smith%')
        """
        name = _check_name(self.name)
        from .filters import Like as _Like

        return _Like(field_name=name, value=pattern, source=self.source)

    def ilike(self, pattern: str) -> ILike:
        """
        Create case-insensitive pattern match: ``field ILIKE pattern``.

        Args:
            pattern: SQL ILIKE pattern (use % and _ wildcards).

        Returns:
            ILike predicate with the given pattern.

        Example:
            .. code-block:: pycon

                >>> Users.name.ilike('%smith%')  # doctest: +SKIP
                ILike(field_name='name', value='%smith%')
        """
        name = _check_name(self.name)
        from .filters import ILike as _ILike

        return _ILike(field_name=name, value=pattern, source=self.source)

    def startswith(self, prefix: str) -> StartsWith:
        """
        Create case-sensitive prefix match: ``field LIKE 'prefix%'``.

        Args:
            prefix: The prefix string to match.

        Returns:
            StartsWith predicate with the given prefix.

        Example:
            .. code-block:: pycon

                >>> Users.name.startswith('A')  # doctest: +SKIP
                StartsWith(field_name='name', value='A')
        """
        name = _check_name(self.name)
        from .filters import StartsWith as _StartsWith

        return _StartsWith(field_name=name, value=prefix, source=self.source)

    def istartswith(self, prefix: str) -> IStartsWith:
        """
        Create case-insensitive prefix match: ``field ILIKE 'prefix%'``.

        Args:
            prefix: The prefix string to match (case-insensitive).

        Returns:
            IStartsWith predicate with the given prefix.

        Example:
            .. code-block:: pycon

                >>> Users.name.istartswith('a')  # doctest: +SKIP
                IStartsWith(field_name='name', value='a')
        """
        name = _check_name(self.name)
        from .filters import IStartsWith as _IStartsWith

        return _IStartsWith(field_name=name, value=prefix, source=self.source)

    def endswith(self, suffix: str) -> EndsWith:
        """
        Create case-sensitive suffix match: ``field LIKE '%suffix'``.

        Args:
            suffix: The suffix string to match.

        Returns:
            EndsWith predicate with the given suffix.

        Example:
            .. code-block:: pycon

                >>> Users.name.endswith('son')  # doctest: +SKIP
                EndsWith(field_name='name', value='son')
        """
        name = _check_name(self.name)
        from .filters import EndsWith as _EndsWith

        return _EndsWith(field_name=name, value=suffix, source=self.source)

    def iendswith(self, suffix: str) -> IEndsWith:
        """
        Create case-insensitive suffix match: ``field ILIKE '%suffix'``.

        Args:
            suffix: The suffix string to match (case-insensitive).

        Returns:
            IEndsWith predicate with the given suffix.

        Example:
            .. code-block:: pycon

                >>> Users.name.iendswith('SON')  # doctest: +SKIP
                IEndsWith(field_name='name', value='SON')
        """
        name = _check_name(self.name)
        from .filters import IEndsWith as _IEndsWith

        return _IEndsWith(field_name=name, value=suffix, source=self.source)

    def iexact(self, value: str) -> IExact:
        """
        Create case-insensitive equality: ``field ILIKE value`` (no wildcards).

        Args:
            value: The value to compare (case-insensitive).

        Returns:
            IExact predicate with the given value.

        Example:
            .. code-block:: pycon

                >>> Users.country.iexact('united states')  # doctest: +SKIP
                IExact(field_name='country', value='united states')
        """
        name = _check_name(self.name)
        from .filters import IExact as _IExact

        return _IExact(field_name=name, value=value, source=self.source)

    def isnull(self) -> IsNull:
        """
        Create null check predicate: ``field IS NULL``.

        Returns:
            IsNull predicate with value=True.

        Example:
            .. code-block:: pycon

                >>> Users.country.isnull()  # doctest: +SKIP
                IsNull(field_name='country', value=True)
        """
        name = _check_name(self.name)
        from .filters import IsNull as _IsNull

        return _IsNull(field_name=name, value=True, source=self.source)

    # -- Escape hatch ---------------------------------------------------------

    def lookup(self, lookup_cls: type[Lookup[Any]], value: Any) -> Lookup[Any]:
        """
        Create an arbitrary lookup predicate (escape hatch).

        Use this when none of the built-in operators or named methods fit.
        Accepts any Lookup subclass and constructs it with this field's name.

        Args:
            lookup_cls: A Lookup subclass to instantiate.
            value: The value for the lookup.

        Returns:
            Instance of lookup_cls with this field's name and the given value.

        Example:
            .. code-block:: pycon

                >>> from semolina.filters import Exact
                >>> Users.country.lookup(Exact, 'US')  # doctest: +SKIP
                Exact(field_name='country', value='US')
        """
        name = _check_name(self.name)
        return lookup_cls(field_name=name, value=value, source=self.source)

    # -- Ordering methods -----------------------------------------------------

    def asc(self, nulls: NullsOrdering | None = None) -> OrderTerm:
        """
        Return ascending OrderTerm for use in order_by().

        Args:
            nulls: How to position NULL values (NullsOrdering.FIRST, NullsOrdering.LAST,
                   or None for default)

        Returns:
            OrderTerm with descending=False

        Example:
            .. code-block:: pycon

                >>> term = Sales.revenue.asc()
                >>> term.descending
                False
        """
        nulls_handling = nulls if nulls is not None else NullsOrdering.DEFAULT
        return OrderTerm(field=self, descending=False, nulls=nulls_handling)

    def desc(self, nulls: NullsOrdering | None = None) -> OrderTerm:
        """
        Return descending OrderTerm for use in order_by().

        Args:
            nulls: How to position NULL values (NullsOrdering.FIRST, NullsOrdering.LAST,
                   or None for default)

        Returns:
            OrderTerm with descending=True

        Example:
            .. code-block:: pycon

                >>> term = Sales.revenue.desc()
                >>> term.descending
                True
        """
        nulls_handling = nulls if nulls is not None else NullsOrdering.DEFAULT
        return OrderTerm(field=self, descending=True, nulls=nulls_handling)


class Metric(Field[T]):
    """
    Descriptor for metric fields (aggregatable measures).

    Metrics represent quantitative measurements that can be aggregated,
    such as SUM(revenue), AVG(price), COUNT(*).
    """

    pass


class Dimension(Field[T]):
    """
    Descriptor for dimension fields (groupable attributes).

    Dimensions represent categorical or descriptive attributes used for
    grouping and filtering, such as country, product_category, date.
    """

    pass


class Fact(Field[T]):
    """
    Descriptor for fact fields (raw numeric values).

    Facts represent raw numeric values in fact tables that may be used
    in calculations but aren't pre-aggregated, such as unit_price, quantity.
    """

    pass


@dataclass(frozen=True)
class OrderTerm:
    """
    Wrapper specifying sort direction and NULL handling for a field in order_by().

    Created via Field.asc() or Field.desc() methods.

    Attributes:
        field: The Field to sort by
        descending: If True, sort descending (DESC). If False, sort ascending (ASC).
        nulls: How to position NULL values (NullsOrdering.FIRST, NullsOrdering.LAST,
               or NullsOrdering.DEFAULT)

    Example:
        .. code-block:: python

            >>> term = Sales.revenue.desc()
            >>> term.descending
            True
            >>> term_nulls = Sales.revenue.desc(NullsOrdering.FIRST)
            >>> term_nulls.nulls
            NULLS FIRST
    """

    field: Field[Any]
    descending: bool = False
    nulls: NullsOrdering = NullsOrdering.DEFAULT

    def __repr__(self) -> str:
        """Return readable representation."""
        direction = "DESC" if self.descending else "ASC"
        nulls_str = f", {repr(self.nulls)}" if self.nulls != NullsOrdering.DEFAULT else ""
        return f"OrderTerm({self.field.name}, {direction}{nulls_str})"
