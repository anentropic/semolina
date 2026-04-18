"""
Tests for results module (Row class).

Row attribute and dict-style access, immutability, dict protocol,
and magic methods.
"""

import pytest

from semolina.results import Row


class TestRowAttributeAccess:
    """Test attribute-style access to row fields."""

    def test_single_field_attribute_access(self) -> None:
        """Row attribute access returns field value."""
        row = Row({"revenue": 1000})
        assert row.revenue == 1000

    def test_multiple_fields_attribute_access(self) -> None:
        """Row supports multiple fields via attribute access."""
        row = Row({"revenue": 1000, "country": "US"})
        assert row.revenue == 1000
        assert row.country == "US"

    def test_missing_field_attribute_raises_attribute_error(self) -> None:
        """Accessing missing field via attribute raises AttributeError."""
        row = Row({"revenue": 1000})
        with pytest.raises(AttributeError) as exc_info:
            _ = row.nonexistent

        error_message = str(exc_info.value)
        assert "nonexistent" in error_message
        assert "revenue" in error_message  # Should list available fields


class TestRowDictAccess:
    """Test dict-style access to row fields."""

    def test_single_field_dict_access(self) -> None:
        """Row dict-style access returns field value."""
        row = Row({"revenue": 1000})
        assert row["revenue"] == 1000

    def test_multiple_fields_dict_access(self) -> None:
        """Row supports multiple fields via dict access."""
        row = Row({"revenue": 1000, "country": "US"})
        assert row["revenue"] == 1000
        assert row["country"] == "US"

    def test_missing_field_dict_raises_key_error(self) -> None:
        """Accessing missing field via dict syntax raises KeyError."""
        row = Row({"revenue": 1000})
        with pytest.raises(KeyError):
            _ = row["nonexistent"]


class TestRowImmutability:
    """Test that Row objects are immutable."""

    def test_attribute_assignment_raises_error(self) -> None:
        """Setting attribute on Row raises AttributeError."""
        row = Row({"revenue": 1000})
        with pytest.raises(AttributeError) as exc_info:
            row.revenue = 999

        error_message = str(exc_info.value)
        assert "immutable" in error_message.lower()

    def test_new_attribute_assignment_raises_error(self) -> None:
        """Setting new attribute on Row raises AttributeError."""
        row = Row({"revenue": 1000})
        with pytest.raises(AttributeError) as exc_info:
            row.new_field = 123

        error_message = str(exc_info.value)
        assert "immutable" in error_message.lower()


class TestRowDictProtocol:
    """Test that Row implements dict protocol methods."""

    def test_keys(self) -> None:
        """Row.keys() returns dict_keys view."""
        row = Row({"a": 1, "b": 2})
        keys = row.keys()
        assert set(keys) == {"a", "b"}
        assert type(keys).__name__ == "dict_keys"

    def test_values(self) -> None:
        """Row.values() returns dict_values view."""
        row = Row({"a": 1, "b": 2})
        values = row.values()
        assert set(values) == {1, 2}
        assert type(values).__name__ == "dict_values"

    def test_items(self) -> None:
        """Row.items() returns dict_items view."""
        row = Row({"a": 1, "b": 2})
        items = row.items()
        assert set(items) == {("a", 1), ("b", 2)}
        assert type(items).__name__ == "dict_items"


class TestRowMagicMethods:
    """Test Row magic methods (repr, eq, len, contains, bool, iter)."""

    def test_repr(self) -> None:
        """Row repr is human-readable."""
        row = Row({"revenue": 1000, "country": "US"})
        repr_str = repr(row)
        assert repr_str.startswith("Row(")
        assert "revenue=1000" in repr_str
        assert "country='US'" in repr_str

    def test_equality_equal_rows(self) -> None:
        """Equal Row objects are equal."""
        row1 = Row({"a": 1})
        row2 = Row({"a": 1})
        assert row1 == row2

    def test_equality_different_rows(self) -> None:
        """Different Row objects are not equal."""
        row1 = Row({"a": 1})
        row2 = Row({"a": 2})
        assert row1 != row2

    def test_equality_different_keys(self) -> None:
        """Row objects with different keys are not equal."""
        row1 = Row({"a": 1})
        row2 = Row({"b": 1})
        assert row1 != row2

    def test_len(self) -> None:
        """len(Row) returns number of fields."""
        row = Row({"a": 1, "b": 2})
        assert len(row) == 2

    def test_len_empty(self) -> None:
        """len(Row) works for empty row."""
        row = Row({})
        assert len(row) == 0

    def test_contains_existing_key(self) -> None:
        """'in' operator works for existing keys."""
        row = Row({"revenue": 1000})
        assert "revenue" in row

    def test_contains_missing_key(self) -> None:
        """'in' operator returns False for missing keys."""
        row = Row({"revenue": 1000})
        assert "missing" not in row

    def test_bool_non_empty(self) -> None:
        """bool(Row) is True for non-empty row."""
        row = Row({"a": 1})
        assert bool(row) is True

    def test_bool_empty(self) -> None:
        """bool(Row) is False for empty row."""
        row = Row({})
        assert bool(row) is False

    def test_iter(self) -> None:
        """Iterating Row yields keys like dict iteration."""
        row = Row({"a": 1, "b": 2})
        keys = list(row)
        assert set(keys) == {"a", "b"}
