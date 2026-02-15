"""Field descriptors for Cubano semantic models.

This module provides descriptor classes for defining typed fields in semantic view models.
Fields use the descriptor protocol to provide class-level access and validation.
"""

import keyword
from typing import Any


class Field:
    """Base descriptor for semantic view fields.

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
        """Called when field is assigned to a class attribute.

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
            raise ValueError(
                f"Field name '{name}' is not a valid Python identifier"
            )

        # Check Python keywords
        if keyword.iskeyword(name):
            raise ValueError(
                f"Field name '{name}' is a Python keyword and cannot be used"
            )

        # Check soft keywords (e.g., match, case in Python 3.10+)
        if keyword.issoftkeyword(name):
            raise ValueError(
                f"Field name '{name}' is a Python soft keyword and cannot be used"
            )

        # Check reserved names that would conflict with dict methods
        reserved = {'keys', 'values', 'items', 'get', 'pop', 'update', 'clear'}
        if name in reserved:
            raise ValueError(
                f"Field name '{name}' is reserved and cannot be used"
            )

        self.name = name
        self.owner = owner

    def __get__(self, instance: Any, owner: type) -> 'Field':
        """Return field descriptor for class-level access.

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
        """Prevent field assignment.

        Raises:
            AttributeError: Always, as fields are immutable
        """
        raise AttributeError(
            f"Field '{self.name}' cannot be modified. Fields are immutable."
        )

    def __delete__(self, instance: Any) -> None:
        """Prevent field deletion.

        Raises:
            AttributeError: Always, as fields cannot be deleted
        """
        raise AttributeError(
            f"Field '{self.name}' cannot be deleted. Fields are immutable."
        )


class Metric(Field):
    """Descriptor for metric fields (aggregatable measures).

    Metrics represent quantitative measurements that can be aggregated,
    such as SUM(revenue), AVG(price), COUNT(*).
    """
    pass


class Dimension(Field):
    """Descriptor for dimension fields (groupable attributes).

    Dimensions represent categorical or descriptive attributes used for
    grouping and filtering, such as country, product_category, date.
    """
    pass


class Fact(Field):
    """Descriptor for fact fields (raw numeric values).

    Facts represent raw numeric values in fact tables that may be used
    in calculations but aren't pre-aggregated, such as unit_price, quantity.
    """
    pass
