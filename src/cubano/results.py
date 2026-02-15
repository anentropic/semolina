"""
Query result objects with attribute and dict-style access.
"""

from collections.abc import ItemsView, Iterator, KeysView, ValuesView
from typing import Any


class Row:
    """
    Immutable result row with attribute and dict-style access.

    Supports both `row.revenue` and `row['revenue']` access patterns.
    Implements dict protocol methods (keys, values, items).
    """

    def __init__(self, data: dict[str, Any]) -> None:
        """
        Initialize Row with field data.

        Args:
            data: Field name to value mapping
        """
        object.__setattr__(self, "_data", dict(data))  # defensive copy

    def __getattr__(self, name: str) -> Any:
        """
        Get field value via attribute access.

        Args:
            name: Field name

        Returns:
            Field value

        Raises:
            AttributeError: Field does not exist
        """
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(
                f"Row has no field {name!r}. "
                f"Available fields: {list(self._data.keys())}"
            ) from None

    def __getitem__(self, key: str) -> Any:
        """
        Get field value via dict-style access.

        Args:
            key: Field name

        Returns:
            Field value

        Raises:
            KeyError: Field does not exist
        """
        return self._data[key]

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Prevent attribute assignment (Row is immutable).

        Args:
            name: Attribute name
            value: Attribute value

        Raises:
            AttributeError: Always - Row objects are immutable
        """
        raise AttributeError(f"Row objects are immutable. Cannot set {name!r}.")

    def __repr__(self) -> str:
        """
        Return human-readable representation.

        Returns:
            String like "Row(revenue=1000, country='US')"
        """
        fields = ", ".join(f"{k}={v!r}" for k, v in self._data.items())
        return f"Row({fields})"

    def __eq__(self, other: object) -> bool:
        """
        Check equality with another Row.

        Args:
            other: Object to compare

        Returns:
            True if other is a Row with same data, False otherwise
        """
        if not isinstance(other, Row):
            return NotImplemented
        return self._data == other._data

    def __len__(self) -> int:
        """
        Return number of fields.

        Returns:
            Field count
        """
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        """
        Check if field exists.

        Args:
            key: Field name to check

        Returns:
            True if field exists, False otherwise
        """
        return key in self._data

    def __bool__(self) -> bool:
        """
        Check if row has any fields.

        Returns:
            True if row has fields, False if empty
        """
        return bool(self._data)

    def __iter__(self) -> Iterator[str]:
        """
        Iterate over field names.

        Returns:
            Iterator over field names
        """
        return iter(self._data)

    def keys(self) -> KeysView[str]:
        """
        Get view of field names.

        Returns:
            Dict keys view
        """
        return self._data.keys()

    def values(self) -> ValuesView[Any]:
        """
        Get view of field values.

        Returns:
            Dict values view
        """
        return self._data.values()

    def items(self) -> ItemsView[str, Any]:
        """
        Get view of (field_name, value) pairs.

        Returns:
            Dict items view
        """
        return self._data.items()
