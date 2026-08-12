"""
Tests for Arrow type -> Python annotation mapping.

Covers every Arrow type the three backends are known to produce, the parameterised shapes
whose ``str()`` form defeats naive matching (``decimal128(38, 2)``,
``timestamp[us, tz=Europe/London]``, ``dictionary<values=string, indices=uint8, ordered=0>``),
and the types that return None to trigger TODO comment generation.

The predicate ordering is asserted, not assumed: ``bool`` must not resolve to ``int``, and a
dictionary-encoded column must resolve through its value type rather than through its own
name.
"""

from __future__ import annotations

import pyarrow as pa
import pytest

from semolina.codegen.arrow_map import arrow_type_to_python


class TestArrowTypeToPython:
    """Tests for arrow_type_to_python function."""

    # Numeric types
    def test_decimal128_returns_decimal(self) -> None:
        """A decimal128 of any precision and scale returns 'decimal.Decimal'."""
        assert arrow_type_to_python(pa.decimal128(38, 2)) == "decimal.Decimal"

    def test_decimal128_scale_zero_returns_decimal(self) -> None:
        """Scale does not change the answer: a scale-0 decimal is still 'decimal.Decimal'."""
        assert arrow_type_to_python(pa.decimal128(38, 0)) == "decimal.Decimal"

    def test_decimal256_returns_decimal(self) -> None:
        """A decimal256 returns 'decimal.Decimal', like its 128-bit sibling."""
        assert arrow_type_to_python(pa.decimal256(50, 4)) == "decimal.Decimal"

    def test_signed_integer_returns_int(self) -> None:
        """A signed integer of any width returns 'int'."""
        assert arrow_type_to_python(pa.int64()) == "int"

    def test_unsigned_integer_returns_int(self) -> None:
        """An unsigned integer returns 'int' too — Python has one integer type."""
        assert arrow_type_to_python(pa.uint64()) == "int"

    def test_floating_returns_float(self) -> None:
        """A double returns 'float'."""
        assert arrow_type_to_python(pa.float64()) == "float"

    def test_bool_returns_bool_not_int(self) -> None:
        """A boolean returns 'bool', never 'int'."""
        # The ordering guard. `bool` subclasses `int` in Python, so an editor sorting this
        # cascade "numerically" would put the integer test first and silently annotate every
        # boolean column as an int.
        assert arrow_type_to_python(pa.bool_()) == "bool"

    # String types
    def test_string_returns_str(self) -> None:
        """A string returns 'str'."""
        assert arrow_type_to_python(pa.string()) == "str"

    def test_large_string_returns_str(self) -> None:
        """A large_string returns 'str' — pyarrow.types.is_string is False for it."""
        assert arrow_type_to_python(pa.large_string()) == "str"

    def test_dictionary_of_string_returns_str(self) -> None:
        """A dictionary-encoded string column returns 'str', resolved via its value type."""
        # A DuckDB ENUM arrives here. Its str() form is
        # `dictionary<values=string, indices=uint8, ordered=0>`, which no name-based match
        # survives, and its own type is not a string type — only its value type is.
        assert arrow_type_to_python(pa.dictionary(pa.uint8(), pa.string())) == "str"

    def test_dictionary_of_unmapped_value_type_returns_none(self) -> None:
        """A dictionary over an unmapped value type returns None rather than guessing 'str'."""
        assert arrow_type_to_python(pa.dictionary(pa.int32(), pa.list_(pa.int64()))) is None

    def test_dictionary_of_decimal_returns_decimal(self) -> None:
        """The dictionary recursion carries the full cascade, not just the string case."""
        assert (
            arrow_type_to_python(pa.dictionary(pa.int8(), pa.decimal128(10, 2)))
            == "decimal.Decimal"
        )

    # Temporal types
    def test_date32_returns_date(self) -> None:
        """A date32 returns 'datetime.date'."""
        assert arrow_type_to_python(pa.date32()) == "datetime.date"

    def test_date64_returns_date(self) -> None:
        """A date64 returns 'datetime.date'."""
        assert arrow_type_to_python(pa.date64()) == "datetime.date"

    def test_timestamp_returns_datetime(self) -> None:
        """A microsecond timestamp returns 'datetime.datetime'."""
        assert arrow_type_to_python(pa.timestamp("us")) == "datetime.datetime"

    def test_timestamp_nanosecond_returns_datetime(self) -> None:
        """A nanosecond timestamp returns 'datetime.datetime' (D-04 over-approximation)."""
        assert arrow_type_to_python(pa.timestamp("ns")) == "datetime.datetime"

    def test_timestamp_with_timezone_returns_datetime(self) -> None:
        """A tz-aware timestamp returns 'datetime.datetime'; the zone does not change it."""
        assert arrow_type_to_python(pa.timestamp("us", tz="Europe/London")) == "datetime.datetime"

    def test_time64_returns_time(self) -> None:
        """A time64 returns 'datetime.time'."""
        assert arrow_type_to_python(pa.time64("us")) == "datetime.time"

    # Binary types
    def test_binary_returns_bytes(self) -> None:
        """A binary returns 'bytes'."""
        assert arrow_type_to_python(pa.binary()) == "bytes"

    def test_fixed_size_binary_returns_bytes(self) -> None:
        """A fixed-size binary returns 'bytes' — is_binary is False for it."""
        assert arrow_type_to_python(pa.binary(16)) == "bytes"

    # Types with no clean Python equivalent
    def test_month_day_nano_interval_returns_none(self) -> None:
        """An interval returns None: no stdlib type describes a pyarrow.MonthDayNano."""
        # D-06 / WINDOWS.md entry 6. Returning 'datetime.timedelta' here would agree with
        # _DUCKDB_TYPE_MAP's known-wrong INTERVAL row and make two maps wrong in step, which
        # reads as agreement rather than as the open question it is.
        assert arrow_type_to_python(pa.month_day_nano_interval()) is None

    def test_struct_returns_none(self) -> None:
        """A struct returns None, so the caller emits a TODO."""
        assert arrow_type_to_python(pa.struct([("a", pa.int64())])) is None

    def test_list_returns_none(self) -> None:
        """A list returns None rather than annotating its element type as a scalar."""
        assert arrow_type_to_python(pa.list_(pa.int64())) is None

    def test_null_returns_none(self) -> None:
        """An all-NULL column's null type names no Python type, so it returns None."""
        assert arrow_type_to_python(pa.null()) is None

    @pytest.mark.parametrize(
        "dtype,expected",
        [
            (pa.bool_(), "bool"),
            (pa.decimal128(10, 2), "decimal.Decimal"),
            (pa.decimal128(38, 0), "decimal.Decimal"),
            (pa.decimal256(50, 4), "decimal.Decimal"),
            (pa.int8(), "int"),
            (pa.int16(), "int"),
            (pa.int32(), "int"),
            (pa.int64(), "int"),
            (pa.uint8(), "int"),
            (pa.uint16(), "int"),
            (pa.uint32(), "int"),
            (pa.uint64(), "int"),
            (pa.float32(), "float"),
            (pa.float64(), "float"),
            (pa.string(), "str"),
            (pa.large_string(), "str"),
            (pa.string_view(), "str"),
            (pa.dictionary(pa.uint8(), pa.string()), "str"),
            (pa.binary(), "bytes"),
            (pa.large_binary(), "bytes"),
            (pa.binary(16), "bytes"),
            (pa.binary_view(), "bytes"),
            (pa.date32(), "datetime.date"),
            (pa.date64(), "datetime.date"),
            (pa.timestamp("s"), "datetime.datetime"),
            (pa.timestamp("ms"), "datetime.datetime"),
            (pa.timestamp("us"), "datetime.datetime"),
            (pa.timestamp("ns"), "datetime.datetime"),
            (pa.timestamp("us", tz="Europe/London"), "datetime.datetime"),
            (pa.time32("s"), "datetime.time"),
            (pa.time64("us"), "datetime.time"),
            (pa.month_day_nano_interval(), None),
            (pa.duration("us"), None),
            (pa.struct([("a", pa.int64())]), None),
            (pa.map_(pa.string(), pa.int64()), None),
            (pa.list_(pa.int64()), None),
            (pa.large_list(pa.int64()), None),
            (pa.null(), None),
        ],
    )
    def test_all_arrow_type_mappings(self, dtype: pa.DataType, expected: str | None) -> None:
        """All Arrow type mappings return expected Python annotation."""
        assert arrow_type_to_python(dtype) == expected
