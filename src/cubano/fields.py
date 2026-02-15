"""
Field descriptors for Cubano semantic models.

Descriptor classes for defining typed fields in semantic view models.
Fields use the descriptor protocol for class-level access and validation.
"""

from __future__ import annotations

import keyword
from dataclasses import dataclass
from enum import Enum
from typing import Any


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


class Field:
    """
    Base descriptor for semantic view fields.

    Fields are descriptors that:
    - Validate field names at class creation time (__set_name__)
    - Return themselves for class-level access (Sales.revenue)
    - Prevent instance-level access, modification, and deletion
    """

    def __init__(self) -> None:
        """Initialize field descriptor."""
        self.name: str | None = None
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

        # Check reserved names that would conflict with dict methods
        reserved = {"keys", "values", "items", "get", "pop", "update", "clear"}
        if name in reserved:
            raise ValueError(f"Field name '{name}' is reserved and cannot be used")

        self.name = name
        self.owner = owner

    def __get__(self, instance: Any, owner: type) -> Field:
        """
        Return field descriptor for class-level access.

        Args:
            instance: The instance accessing the field (None for class access)
            owner: The class that owns this field

        Returns:
            The field descriptor itself

        Raises:
            AttributeError: If accessed from an instance rather than class
        """
        if instance is not None:
            raise AttributeError(
                f"Field '{self.name}' cannot be accessed from instances. "
                f"Use {owner.__name__}.{self.name} instead."
            )
        return self

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

    def asc(self, nulls: NullsOrdering | None = None) -> OrderTerm:
        """
        Return ascending OrderTerm for use in order_by().

        Args:
            nulls: How to position NULL values (NullsOrdering.FIRST, NullsOrdering.LAST,
                   or None for default)

        Returns:
            OrderTerm with descending=False

        Example:
            Query().order_by(Sales.revenue.asc())
            Query().order_by(Sales.revenue.asc(NullsOrdering.LAST))
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
            Query().order_by(Sales.revenue.desc())
            Query().order_by(Sales.revenue.desc(NullsOrdering.FIRST))
        """
        nulls_handling = nulls if nulls is not None else NullsOrdering.DEFAULT
        return OrderTerm(field=self, descending=True, nulls=nulls_handling)


class Metric(Field):
    """
    Descriptor for metric fields (aggregatable measures).

    Metrics represent quantitative measurements that can be aggregated,
    such as SUM(revenue), AVG(price), COUNT(*).
    """

    pass


class Dimension(Field):
    """
    Descriptor for dimension fields (groupable attributes).

    Dimensions represent categorical or descriptive attributes used for
    grouping and filtering, such as country, product_category, date.
    """

    pass


class Fact(Field):
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
        Sales.revenue.desc()  # Descending order
        Sales.revenue.desc(NullsOrdering.FIRST)  # Descending with NULLS FIRST
        Sales.revenue.asc(NullsOrdering.LAST)  # Ascending with NULLS LAST
    """

    field: Field
    descending: bool = False
    nulls: NullsOrdering = NullsOrdering.DEFAULT

    def __repr__(self) -> str:
        """Return readable representation."""
        direction = "DESC" if self.descending else "ASC"
        nulls_str = f", {repr(self.nulls)}" if self.nulls != NullsOrdering.DEFAULT else ""
        return f"OrderTerm({self.field.name}, {direction}{nulls_str})"
