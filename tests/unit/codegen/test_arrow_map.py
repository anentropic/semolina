"""
Tests for Arrow type -> Python annotation mapping.

Covers every Arrow type the three backends are known to produce, the parameterized shapes
whose ``str()`` form defeats naive matching (``decimal128(38, 2)``,
``timestamp[us, tz=Europe/London]``, ``dictionary<values=string, indices=uint8, ordered=0>``),
and the types that return None to trigger TODO comment generation.

The predicate ordering is asserted, not assumed: ``bool`` must not resolve to ``int``, and a
dictionary-encoded column must resolve through its value type rather than through its own
name.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pyarrow as pa
import pytest

from semolina.codegen.arrow_map import (
    _ANNOTATION_TO_TYPE,
    arrow_type_to_python,
    arrow_type_to_runtime_type,
)


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

    def test_run_end_encoded_resolves_through_its_value_type(self) -> None:
        """
        The other pure-encoding Arrow type resolves the same way ``dictionary`` does.

        Measured, not assumed: ``pc.run_end_encode(pa.array(["a", "a", "b"]))`` in a
        ``RecordBatch`` produces ``[{'x': 'a'}, {'x': 'a'}, {'x': 'b'}]`` through
        ``to_pylist()`` on pyarrow 24.0.0 — plain ``str`` values, exactly as a dictionary
        column does. Returning None here would have sent an ordinary string column to a
        TODO comment on the strength of how it was encoded.
        """
        assert arrow_type_to_python(pa.run_end_encoded(pa.int32(), pa.string())) == "str"

    def test_run_end_encoded_of_an_unmapped_value_type_returns_none(self) -> None:
        """Recursion rather than a hard-coded 'str', for the same reason as dictionary."""
        assert arrow_type_to_python(pa.run_end_encoded(pa.int32(), pa.list_(pa.int64()))) is None

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


class TestArrowTypeToRuntimeType:
    """Tests for the runtime-type sibling used by the .into() schema pre-check."""

    def test_every_reachable_annotation_has_a_runtime_type(self) -> None:
        """
        No string ``arrow_type_to_python`` can return is missing from ``_ANNOTATION_TO_TYPE``.

        This is the most important test in the class, and it is a coverage test rather than a
        conversion test. ``arrow_type_to_runtime_type`` subscripts the map directly, so a
        future branch added to the cascade with a new annotation string would raise
        :exc:`KeyError` at a user's ``.into()`` call. Reading the reachable strings out of the
        function's own AST means adding that branch fails here instead — and fails whether or
        not anyone remembers to add a case to the parametrized list below.
        """
        tree = ast.parse(textwrap.dedent(inspect.getsource(arrow_type_to_python)))

        returned = {
            node.value.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Return)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        }

        assert returned, (
            "Found no string return in arrow_type_to_python's source. The cascade was "
            "restructured and this guard silently stopped guarding anything."
        )
        assert returned <= set(_ANNOTATION_TO_TYPE), (
            f"arrow_type_to_python can return {sorted(returned - set(_ANNOTATION_TO_TYPE))}, "
            "which has no entry in _ANNOTATION_TO_TYPE. Add it there in the same commit, or "
            "arrow_type_to_runtime_type raises KeyError at a user's .into() call."
        )

    def test_map_has_no_unreachable_entries(self) -> None:
        """Every key in the map is a string the cascade can actually produce."""
        tree = ast.parse(textwrap.dedent(inspect.getsource(arrow_type_to_python)))

        returned = {
            node.value.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Return)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        }

        assert set(_ANNOTATION_TO_TYPE) == returned, (
            f"_ANNOTATION_TO_TYPE has entries the cascade never returns: "
            f"{sorted(set(_ANNOTATION_TO_TYPE) - returned)}. Two mappings that disagree about "
            "their own domain are the drift this module exists to prevent."
        )

    def test_decimal_returns_the_decimal_class(self) -> None:
        """The headline case: a decimal128 resolves to the class, not to the string."""
        import decimal

        assert arrow_type_to_runtime_type(pa.decimal128(38, 2)) is decimal.Decimal

    def test_timestamp_returns_the_datetime_class(self) -> None:
        """A timestamp resolves to ``datetime.datetime``, tz-awareness notwithstanding."""
        import datetime

        assert arrow_type_to_runtime_type(pa.timestamp("us", tz="Europe/London")) is (
            datetime.datetime
        )

    def test_dictionary_encoded_string_returns_str(self) -> None:
        """The adapter inherits the cascade's recursion, so a DuckDB ENUM resolves to str."""
        assert arrow_type_to_runtime_type(pa.dictionary(pa.uint8(), pa.string())) is str

    def test_boolean_returns_bool_not_int(self) -> None:
        """The adapter inherits the cascade's ordering guard too."""
        assert arrow_type_to_runtime_type(pa.bool_()) is bool

    def test_struct_returns_none(self) -> None:
        """
        An unmapped Arrow type answers None rather than guessing.

        The pre-check reads this as "no opinion" and skips the field. arrowmodel converts an
        Arrow struct into a nested BaseModel correctly, so a verdict here would break a
        conversion that works.
        """
        assert arrow_type_to_runtime_type(pa.struct([("a", pa.int64())])) is None

    def test_list_returns_none(self) -> None:
        """A list answers None, for the same reason: arrowmodel handles ``list[str]`` fine."""
        assert arrow_type_to_runtime_type(pa.list_(pa.int64())) is None

    def test_agrees_with_the_string_sibling_across_the_cascade(self) -> None:
        """
        The two functions never disagree about whether a type is mapped at all.

        One cascade, two renderings. If a refactor ever gave the runtime sibling its own
        predicate chain, this is where the divergence would surface.
        """
        for dtype in (
            pa.bool_(),
            pa.decimal128(10, 2),
            pa.int32(),
            pa.float64(),
            pa.string(),
            pa.binary(),
            pa.date32(),
            pa.timestamp("us"),
            pa.time64("us"),
            pa.struct([("a", pa.int64())]),
            pa.list_(pa.int64()),
            pa.null(),
            pa.month_day_nano_interval(),
        ):
            annotation = arrow_type_to_python(dtype)
            runtime = arrow_type_to_runtime_type(dtype)
            assert (annotation is None) == (runtime is None), (
                f"{dtype} is mapped by one sibling and not the other: {annotation!r} vs {runtime!r}"
            )
