"""
Tests for results module (Row class).

Row attribute and dict-style access, immutability, dict protocol,
and magic methods.
"""

import copy
import pickle
from collections.abc import Mapping

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


class TestRowCopyingAndPickling:
    """
    CORE-01: a Row survives the round trips a result object is put through.

    `Row` is the primary result object, so anything that caches, forks or ships rows —
    multiprocessing, a task queue, `functools` memoisation — copies or pickles one. Before
    this, all three raised `RecursionError`: `__getattr__` reads `self._data`, and on an
    instance reconstructed without `__init__` (which is exactly what copy, deepcopy and
    `pickle.loads` do before restoring state) that attribute is absent, so the lookup calls
    `__getattr__` again for `_data`, forever. The traceback named recursion rather than the
    missing attribute, so the cause was not obvious from the failure.
    """

    def test_copy_round_trips(self) -> None:
        """A shallow copy is an equal Row, not a RecursionError."""
        row = Row({"revenue": 1000, "country": "US"})

        assert copy.copy(row) == row

    def test_deepcopy_round_trips(self) -> None:
        """A deep copy is an equal Row and does not share the underlying mapping."""
        row = Row({"revenue": 1000, "tags": ["a"]})
        clone = copy.deepcopy(row)

        assert clone == row
        assert clone["tags"] is not row["tags"]

    def test_pickle_round_trips(self) -> None:
        """A Row survives pickle, which is what sends it to another process."""
        row = Row({"revenue": 1000, "country": "US"})

        assert pickle.loads(pickle.dumps(row)) == row

    def test_reconstructed_row_reports_a_missing_field_as_attribute_error(self) -> None:
        """
        The recursion guard does not swallow the ordinary missing-field error.

        `_data` is the one name `__getattr__` must refuse rather than look up, and refusing it
        must still leave every other name reporting the error a caller can act on.
        """
        row = pickle.loads(pickle.dumps(Row({"revenue": 1000})))

        with pytest.raises(AttributeError, match="no field 'missing'"):
            _ = row.missing


class TestRowAsAMapping:
    """CORE-01, CORE-02: the dict-like surface a caller expects of a result row."""

    def test_is_a_mapping(self) -> None:
        """`isinstance(row, Mapping)` holds, so a row satisfies a Mapping annotation."""
        assert isinstance(Row({"a": 1}), Mapping)

    def test_get_returns_the_value(self) -> None:
        """`.get()` exists — its absence was surprising given keys/values/items do."""
        assert Row({"revenue": 1000}).get("revenue") == 1000

    def test_get_returns_the_default_for_a_missing_field(self) -> None:
        """A missing field yields the default rather than raising."""
        assert Row({"revenue": 1000}).get("missing", 0) == 0

    def test_get_defaults_to_none(self) -> None:
        """The default default is None, as on dict."""
        assert Row({"revenue": 1000}).get("missing") is None

    def test_is_hashable_when_its_values_are(self) -> None:
        """
        Defining __eq__ without __hash__ made Row unhashable, so `set(rows)` raised.

        SQLAlchemy's Row and namedtuples are both hashable, and deduplicating results is an
        ordinary thing to want.
        """
        assert len({Row({"a": 1}), Row({"a": 1}), Row({"a": 2})}) == 2

    def test_hash_ignores_key_order(self) -> None:
        """
        Equal rows hash equally even when built in a different key order.

        Row equality compares the underlying mappings, and dict equality ignores order — so a
        hash derived from an ordered view of the items would break the invariant that equal
        objects hash equally, and put two equal rows in a set at once.
        """
        assert hash(Row({"a": 1, "b": 2})) == hash(Row({"b": 2, "a": 1}))

    def test_a_row_holding_an_unhashable_value_is_not_hashable(self) -> None:
        """Hashability follows the values, exactly as it does for a tuple."""
        with pytest.raises(TypeError):
            hash(Row({"tags": ["a"]}))

    def test_a_column_named_like_a_method_is_reachable_by_item_access(self) -> None:
        """
        CORE-02: a warehouse may return a column named `items`, `keys`, `values` or `get`.

        The method wins for attribute access — changing that would break every caller that
        writes `row.items()` — so item access is the documented way to reach such a column,
        and it must work rather than return the method.
        """
        row = Row({"items": 3, "keys": 4, "values": 5, "get": 6})

        assert [row["items"], row["keys"], row["values"], row["get"]] == [3, 4, 5, 6]
        assert callable(row.items)
