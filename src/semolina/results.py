"""Row class with attribute and dict-style field access."""

from collections.abc import ItemsView, Iterator, KeysView, Mapping, ValuesView
from typing import Any


class Row(Mapping[str, Any]):
    """
    Immutable result row with attribute and dict-style access.

    Supports both `row.revenue` and `row['revenue']` access patterns.
    Implements dict protocol methods (keys, values, items, get).

    A read-only :class:`collections.abc.Mapping`, so a Row satisfies a Mapping annotation and
    ``dict(row)`` works. Subclassed rather than registered so that static type checkers see it
    too; every mixin Mapping would supply is defined explicitly below, including ``__hash__``,
    which Mapping otherwise sets to None. Note that ``json.dumps(row)`` still does not work:
    json tests ``isinstance(o, dict)`` against the concrete type rather than the ABC, so pass
    ``dict(row)``.

    A column whose name collides with one of these methods — a warehouse may return ``items``
    or ``keys`` — is reached with ``row["items"]``; attribute access returns the method.

    Example:
        .. code-block:: pycon

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
        # `_data` is refused outright rather than looked up. __getattr__ runs only when normal
        # attribute lookup has already failed, so reaching it for `_data` means the instance
        # has none — which is the state copy, deepcopy and pickle.loads leave a Row in between
        # constructing it and restoring its state. Looking it up here would call __getattr__
        # again for the same name, and all three round trips died with a RecursionError that
        # named the recursion instead of the missing attribute.
        if name == "_data":
            raise AttributeError(name)
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

    def __getstate__(self) -> dict[str, Any]:
        """
        Return the field mapping, for copy, deepcopy and pickle.

        Defined alongside :meth:`__setstate__` because ``__setattr__`` raises: without an
        explicit pair, the copy protocol's default restore path assigns to the instance
        ``__dict__`` and a Row would refuse its own reconstruction.

        Returns:
            The field data.
        """
        return self._data

    def __setstate__(self, state: dict[str, Any]) -> None:
        """
        Restore the field mapping, bypassing the immutability guard.

        Args:
            state: The field data, as returned by :meth:`__getstate__`.
        """
        object.__setattr__(self, "_data", dict(state))

    def __hash__(self) -> int:
        """
        Hash the row by its fields, so equal rows hash equally.

        Python sets ``__hash__`` to None on any class defining ``__eq__``, which left Row
        unhashable and ``set(rows)`` raising — unlike SQLAlchemy's Row or a namedtuple.

        Hashed over a ``frozenset`` of the items rather than a tuple of them: equality
        compares the underlying mappings and dict equality ignores order, so an order-sensitive
        hash would give two equal rows different hashes and admit both to one set.

        Returns:
            The hash of this row's fields.

        Raises:
            TypeError: If any value is unhashable, exactly as for a tuple holding one.
        """
        return hash(frozenset(self._data.items()))

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

    def get(self, key: str, default: Any = None) -> Any:
        """
        Return a field value, or ``default`` when the field is absent.

        Args:
            key: Field name.
            default: Returned when the field is absent. Defaults to None.

        Returns:
            The field value, or ``default``.
        """
        return self._data.get(key, default)

    def items(self) -> ItemsView[str, Any]:
        """
        Get view of (field_name, value) pairs.

        Returns:
            Dict items view
        """
        return self._data.items()
