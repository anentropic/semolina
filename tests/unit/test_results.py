"""
Tests for results module (Row and Result classes).

Phase 10.1 tests:
- Result class for eager execution
- Result iteration, indexing, and bool conversion
- Row access patterns through Result
"""

import pytest

from cubano.results import Result, Row


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


class TestResultBasics:
    """Test Phase 10.1 Result class for query execution results."""

    def test_result_initialization(self) -> None:
        """Result should initialize with list of Row objects."""
        rows = [Row({"a": 1}), Row({"b": 2})]
        result = Result(rows)
        assert result.rows == rows

    def test_result_length(self) -> None:
        """len(Result) should return number of rows."""
        rows = [Row({"a": 1}), Row({"b": 2}), Row({"c": 3})]
        result = Result(rows)
        assert len(result) == 3

    def test_result_empty_length(self) -> None:
        """len(Result) should work for empty result."""
        result = Result([])
        assert len(result) == 0


class TestResultIteration:
    """Test iteration over Result objects."""

    def test_result_iteration(self) -> None:
        """Result should be iterable over Row objects."""
        rows = [Row({"a": 1}), Row({"b": 2})]
        result = Result(rows)
        collected = list(result)
        assert collected == rows

    def test_result_for_loop(self) -> None:
        """Result should work in for loops."""
        rows = [Row({"revenue": 1000}), Row({"revenue": 2000})]
        result = Result(rows)

        revenues: list[int] = []
        for row in result:
            revenues.append(row.revenue)

        assert revenues == [1000, 2000]


class TestResultIndexing:
    """Test indexing into Result objects."""

    def test_result_single_index(self) -> None:
        """Result[i] should return Row at index i."""
        rows = [Row({"a": 1}), Row({"b": 2}), Row({"c": 3})]
        result = Result(rows)

        assert result[0].a == 1
        assert result[1].b == 2
        assert result[2].c == 3

    def test_result_negative_index(self) -> None:
        """Result[-1] should return last row."""
        rows = [Row({"a": 1}), Row({"b": 2}), Row({"c": 3})]
        result = Result(rows)
        assert result[-1].c == 3

    def test_result_index_out_of_range(self) -> None:
        """Result[i] should raise IndexError for out of range."""
        result = Result([Row({"a": 1})])
        with pytest.raises(IndexError):
            _ = result[10]


class TestResultBool:
    """Test bool conversion of Result objects."""

    def test_result_bool_non_empty(self) -> None:
        """bool(Result) should be True for non-empty."""
        result = Result([Row({"a": 1})])
        assert bool(result) is True

    def test_result_bool_empty(self) -> None:
        """bool(Result) should be False for empty."""
        result = Result([])
        assert bool(result) is False

    def test_result_in_if_statement_non_empty(self) -> None:
        """Result can be used in if statement (non-empty)."""
        result = Result([Row({"a": 1})])
        passed = bool(result)
        assert passed

    def test_result_in_if_statement_empty(self) -> None:
        """Result can be used in if statement (empty)."""
        result = Result([])
        passed = not result
        assert passed


class TestResultRowAccess:
    """Test accessing row data through Result."""

    def test_result_row_attribute_access(self) -> None:
        """Result rows should support attribute access."""
        rows = [Row({"revenue": 1000, "country": "US"})]
        result = Result(rows)
        assert result[0].revenue == 1000
        assert result[0].country == "US"

    def test_result_row_dict_access(self) -> None:
        """Result rows should support dict-style access."""
        rows = [Row({"revenue": 1000, "country": "US"})]
        result = Result(rows)
        assert result[0]["revenue"] == 1000
        assert result[0]["country"] == "US"

    def test_result_all_rows_iterable(self) -> None:
        """All rows in Result should be iterable."""
        rows = [
            Row({"id": 1, "value": "a"}),
            Row({"id": 2, "value": "b"}),
            Row({"id": 3, "value": "c"}),
        ]
        result = Result(rows)

        ids = [row.id for row in result]
        assert ids == [1, 2, 3]

        values = [row["value"] for row in result]
        assert values == ["a", "b", "c"]


class TestResultRepr:
    """Test Result string representation."""

    def test_result_repr_non_empty(self) -> None:
        """Result repr should show row count."""
        result = Result([Row({"a": 1}), Row({"b": 2})])
        repr_str = repr(result)
        assert "Result" in repr_str
        assert "2 rows" in repr_str

    def test_result_repr_empty(self) -> None:
        """Result repr should show 0 rows."""
        result = Result([])
        repr_str = repr(result)
        assert "Result" in repr_str
        assert "0 rows" in repr_str

    def test_result_repr_shows_columns(self) -> None:
        """Result repr should show column names when rows exist."""
        result = Result([Row({"revenue": 1000, "country": "US"})])
        repr_str = repr(result)
        assert "columns=" in repr_str
        assert "'revenue'" in repr_str
        assert "'country'" in repr_str
