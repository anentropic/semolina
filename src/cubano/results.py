"""Query result objects with attribute and dict-style access."""

from collections.abc import ItemsView, Iterator, KeysView, ValuesView
from typing import Any


class Row:
    """
    Immutable result row with attribute and dict-style access.

    Supports both `row.revenue` and `row['revenue']` access patterns.
    Implements dict protocol methods (keys, values, items).

    Example:
        >>> row = Row({"revenue": 1000, "country": "US"})
        >>> row.revenue
        1000
        >>> row["country"]
        'US'
        >>> len(row)
        2
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
                f"Row has no field {name!r}. Available fields: {list(self._data.keys())}"
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


class Result:
    """
    Typed result wrapper for query execution.

    Result wraps a list of Row objects and provides helper methods for
    data access and transformation. Supports iteration, indexing, and
    attribute/dict-style row access.

    Future helper methods: to_pandas(), summary(), pivot()
    These are intentionally deferred to Phase 10.2

    Example:
        >>> result = Sales.query().metrics(Sales.revenue).execute()
        >>> len(result)
        3
        >>> for row in result:
        ...     print(row.revenue)  # doctest: +SKIP
        1000
        2000
        500
        >>> result[0].revenue
        1000
    """

    def __init__(self, rows: list[Row]) -> None:
        """
        Initialize Result with row data.

        Args:
            rows: List of Row objects from query execution
        """
        self.rows: list[Row] = rows

    def __len__(self) -> int:
        """Return number of rows in result."""
        return len(self.rows)

    def __iter__(self) -> Iterator[Row]:
        """Iterate over Row objects."""
        return iter(self.rows)

    def __getitem__(self, index: int) -> Row:
        """
        Get row by index.

        Args:
            index: Row index (0-based)

        Returns:
            Row object

        Raises:
            IndexError: If index out of range
        """
        return self.rows[index]

    def __repr__(self) -> str:
        """Return string representation with column names when rows exist."""
        if self.rows:
            cols = list(self.rows[0].keys())
            return f"Result({len(self.rows)} rows, columns={cols})"
        return "Result(0 rows)"

    def __bool__(self) -> bool:
        """Return True if result has any rows."""
        return len(self.rows) > 0
