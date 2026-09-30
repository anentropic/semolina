"""
Tests for SQL type -> Python annotation mapping functions.

Tests cover Snowflake JSON type mappings, Databricks type mappings, and DuckDB
type mappings, including all clean-Python-equivalent types and types that return
None to trigger TODO comment generation.
"""

from __future__ import annotations

import pytest

from semolina.codegen.type_map import (
    databricks_type_to_python,
    duckdb_type_to_python,
    snowflake_json_type_to_python,
)


class TestSnowflakeJsonTypeToPython:
    """Tests for snowflake_json_type_to_python function."""

    # Numeric types
    def test_fixed_scale_zero_returns_decimal(self) -> None:
        """
        FIXED with scale=0 returns 'decimal.Decimal'.

        The Decimal policy covers the whole FIXED family including scale 0:
        the Snowflake driver returns Decimal128 for every FIXED column while
        ``use_high_precision`` is enabled, which is its default.
        """
        assert snowflake_json_type_to_python({"type": "FIXED", "scale": 0}) == "decimal.Decimal"

    def test_fixed_scale_positive_returns_decimal(self) -> None:
        """FIXED with scale>0 returns 'decimal.Decimal'."""
        assert snowflake_json_type_to_python({"type": "FIXED", "scale": 2}) == "decimal.Decimal"

    def test_fixed_scale_large_returns_decimal(self) -> None:
        """FIXED with a large scale returns 'decimal.Decimal'."""
        assert snowflake_json_type_to_python({"type": "FIXED", "scale": 10}) == "decimal.Decimal"

    # String types

    # Boolean types

    # Date/time types

    # Binary types

    # Complex types that return None (trigger TODO comment)

    def test_unknown_type_returns_none(self) -> None:
        """Unknown type string returns None."""
        assert snowflake_json_type_to_python({"type": "UNKNOWN_TYPE"}) is None

    def test_missing_type_key_returns_none(self) -> None:
        """Dict missing 'type' key returns None."""
        assert snowflake_json_type_to_python({}) is None

    def test_case_insensitive_lookup(self) -> None:
        """Type names are handled case-insensitively (Snowflake uses uppercase)."""
        # Snowflake API returns uppercase, but handle lowercase too
        assert snowflake_json_type_to_python({"type": "text"}) == "str"

    @pytest.mark.parametrize(
        "type_json,expected",
        [
            ({"type": "FIXED", "scale": 0}, "decimal.Decimal"),
            ({"type": "FIXED", "scale": 5}, "decimal.Decimal"),
            ({"type": "FIXED"}, "decimal.Decimal"),
            ({"type": "TEXT"}, "str"),
            ({"type": "REAL"}, "float"),
            ({"type": "BOOLEAN"}, "bool"),
            ({"type": "DATE"}, "datetime.date"),
            ({"type": "TIMESTAMP_LTZ"}, "datetime.datetime"),
            ({"type": "TIMESTAMP_NTZ"}, "datetime.datetime"),
            ({"type": "TIMESTAMP_TZ"}, "datetime.datetime"),
            ({"type": "TIME"}, "datetime.time"),
            ({"type": "BINARY"}, "bytes"),
            ({"type": "ARRAY"}, None),
            ({"type": "OBJECT"}, None),
            ({"type": "VARIANT"}, "JsonValue"),
            ({"type": "GEOGRAPHY"}, None),
            ({"type": "GEOMETRY"}, None),
        ],
    )
    def test_all_snowflake_type_mappings(
        self, type_json: dict[str, object], expected: str | None
    ) -> None:
        """All Snowflake type mappings return expected Python annotation."""
        assert snowflake_json_type_to_python(type_json) == expected


class TestDatabricksTypeToPython:
    """Tests for databricks_type_to_python function."""

    # String types

    # Integer types

    # Float types

    # Decimal — the Decimal policy's Databricks carve-out, measured 2026-08-16.
    #
    # The policy maps a warehouse decimal to decimal.Decimal on the strength of a stated
    # premise: "a user with a money column already receives a Decimal today", because pyarrow
    # converts decimal128 unconditionally at to_pylist(). That premise holds on DuckDB and
    # Snowflake and is false on Databricks, which the policy never measured. The Foundry ADBC
    # driver returns every decimal as an Arrow string at any precision and scale, scale 0
    # included, on literals as well as columns.
    #
    # So the annotation follows the driver, which is the same standard every other row here is
    # held to.

    def test_decimal_with_precision_and_scale_returns_str(self) -> None:
        """Precision and scale do not change the answer: the driver stringifies them all."""
        assert databricks_type_to_python({"name": "decimal", "precision": 10, "scale": 2}) == "str"

    def test_decimal_scale_zero_returns_str(self) -> None:
        """
        Scale 0 is stringified too, so it does not fall back to an integer annotation.

        Pinned because scale 0 is the case Snowflake's own driver special-cases (returning
        Int64 when high precision is disabled), which makes it the shape most likely to be
        assumed rather than measured. Measured on Databricks: CAST(7 AS DECIMAL(5,0)) arrives
        as the Arrow string '7'.
        """
        assert databricks_type_to_python({"name": "decimal", "precision": 5, "scale": 0}) == "str"

    # Boolean types

    # Date/time types

    # Binary types

    # Complex types that return None (trigger TODO comment)

    def test_unknown_name_returns_none(self) -> None:
        """Unknown type name returns None."""
        assert databricks_type_to_python({"name": "unknown_type"}) is None

    def test_missing_name_key_returns_none(self) -> None:
        """Dict missing 'name' key returns None."""
        assert databricks_type_to_python({}) is None

    def test_case_insensitive_lookup(self) -> None:
        """Type names are handled case-insensitively (Databricks uses lowercase)."""
        # Databricks API returns lowercase, but handle uppercase too
        assert databricks_type_to_python({"name": "STRING"}) == "str"

    @pytest.mark.parametrize(
        "type_obj,expected",
        [
            ({"name": "string"}, "str"),
            ({"name": "bigint"}, "int"),
            ({"name": "int"}, "int"),
            ({"name": "smallint"}, "int"),
            ({"name": "tinyint"}, "int"),
            ({"name": "long"}, "int"),
            ({"name": "double"}, "float"),
            ({"name": "float"}, "float"),
            ({"name": "decimal"}, "str"),
            ({"name": "boolean"}, "bool"),
            ({"name": "date"}, "datetime.date"),
            ({"name": "timestamp"}, "datetime.datetime"),
            ({"name": "timestamp_ntz"}, "datetime.datetime"),
            ({"name": "binary"}, "bytes"),
            ({"name": "array"}, None),
            ({"name": "map"}, None),
            ({"name": "struct"}, None),
            ({"name": "variant"}, "JsonValue"),
            ({"name": "interval"}, "str"),
            ({"name": "interval", "start_unit": "DAY", "end_unit": "SECOND"}, "str"),
            ({"name": "interval", "start_unit": "YEAR", "end_unit": "MONTH"}, "str"),
        ],
    )
    def test_all_databricks_type_mappings(
        self, type_obj: dict[str, object], expected: str | None
    ) -> None:
        """All Databricks type mappings return expected Python annotation."""
        assert databricks_type_to_python(type_obj) == expected


class TestDatabricksIntervalType:
    """
    Tests for Databricks intervals, measured 2026-08-16 against a live workspace.

    Both interval families were first left unmapped for want of evidence: no fixture, cassette,
    or recording in this repo contained an interval column, so nothing could say what one
    arrives as, and a ``datetime.timedelta`` guess was implemented and then reverted rather
    than shipped beside measured neighbours.

    The measurement settles it, and settles both families the same way. An
    ``INTERVAL DAY TO SECOND`` arrives as the Arrow string ``'3 04:05:06.789000000'`` and an
    ``INTERVAL YEAR TO MONTH`` as ``'2-6'``. This is not a driver choice that a better driver
    would make differently: the Databricks Thrift negotiation struct ``TSparkArrowTypes``
    carries ``timestampAsArrow``, ``decimalAsArrow``, ``complexTypesAsArrow`` and
    ``nullTypeAsArrow`` and has **no interval member at all**, and ``databricks-sql-connector``
    returns the same string off the same protocol. Interval-as-string is the wire format.

    So the year-month family, once called unmappable in principle because a month
    has no fixed length, is mappable after all — not because a duration type was found for it,
    but because no duration ever arrives. A string does, and ``str`` describes it exactly.

    See ``verify_databricks_types_live.py`` in this phase's planning directory.
    """

    def test_day_to_second_returns_str(self) -> None:
        """A DAY TO SECOND interval returns 'str' — measured '3 04:05:06.789000000'."""
        type_obj: dict[str, object] = {
            "name": "interval",
            "start_unit": "DAY",
            "end_unit": "SECOND",
        }
        assert databricks_type_to_python(type_obj) == "str"

    def test_year_to_month_returns_str(self) -> None:
        """
        A YEAR TO MONTH interval returns 'str' — measured '2-6'.

        Pinned separately from the day-time family because the two were expected to diverge:
        the earlier reasoning was that a month has no fixed length, so no stdlib duration type
        could describe it. That reasoning was sound and is simply not what the question turned
        on — the driver never offers a duration to describe.
        """
        type_obj: dict[str, object] = {
            "name": "interval",
            "start_unit": "YEAR",
            "end_unit": "MONTH",
        }
        assert databricks_type_to_python(type_obj) == "str"

    def test_bare_interval_returns_str(self) -> None:
        """An interval carrying no units at all returns 'str'."""
        assert databricks_type_to_python({"name": "interval"}) == "str"

    def test_no_unit_value_can_change_the_annotation(self) -> None:
        """
        No ``start_unit`` / ``end_unit`` value can influence the annotation.

        ``start_unit`` and ``end_unit`` are catalogue-controlled strings, and the mapper stays
        a closed-vocabulary lookup on ``name`` alone that never reads them. The threat is a
        unit string reaching generated Python source, which mapping the type does not change:
        the answer is ``'str'`` for every unit value, hostile ones included, because the units
        are never consulted.
        """
        for start_unit in ("DAY", "FORTNIGHT", "str | None", "'); DROP TABLE t; --"):
            type_obj: dict[str, object] = {
                "name": "interval",
                "start_unit": start_unit,
                "end_unit": "SECOND",
            }
            assert databricks_type_to_python(type_obj) == "str"


class TestDuckDBTypeToPython:
    """Tests for duckdb_type_to_python function."""

    # String types

    # Integer types

    def test_hugeint_returns_decimal(self) -> None:
        """
        HUGEINT returns 'decimal.Decimal'.

        The value arrives as a ``decimal.Decimal`` — DuckDB hands a HUGEINT column over
        Arrow as ``decimal128(38, 0)``. Annotating ``int`` would make "the three backends no
        longer disagree about money" false.
        """
        assert duckdb_type_to_python("HUGEINT") == "decimal.Decimal"

    # Unsigned integer types

    # Float types

    # Boolean types

    # Date/time types

    # Binary types

    # Interval type
    def test_interval_returns_datetime_timedelta(self) -> None:
        """
        INTERVAL returns 'datetime.timedelta' — deliberately unchanged.

        This mapping is known to be wrong: the value arrives as a
        ``pyarrow.MonthDayNano``. No stdlib type describes that, so choosing one is a
        design question the type map's specification does not cover. It is left known-wrong
        instead, and this test pins the current answer so a future fix is
        a deliberate change rather than a drift.
        """
        assert duckdb_type_to_python("INTERVAL") == "datetime.timedelta"

    # Measured annotations: the annotation names the value, not the semantic type

    def test_enum_bare_returns_str(self) -> None:
        """A bare ENUM returns 'str' — the dictionary-encoded column arrives as str."""
        assert duckdb_type_to_python("ENUM") == "str"

    def test_timestamp_ns_returns_datetime_datetime(self) -> None:
        """
        TIMESTAMP_NS returns 'datetime.datetime' — a sound over-approximation.

        The value is a ``pandas.Timestamp`` when pandas is importable, and
        ``pandas.Timestamp`` is a ``datetime.datetime`` subclass.
        """
        assert duckdb_type_to_python("TIMESTAMP_NS") == "datetime.datetime"

    # Decimal (the Decimal policy: decimal.Decimal on DuckDB and Snowflake)

    def test_decimal_bare_returns_decimal(self) -> None:
        """A bare DECIMAL with no parameters returns 'decimal.Decimal'."""
        assert duckdb_type_to_python("DECIMAL") == "decimal.Decimal"

    def test_decimal_lowercase_returns_decimal(self) -> None:
        """Type names are normalized before lookup, so lowercase decimal maps too."""
        assert duckdb_type_to_python("decimal(38,2)") == "decimal.Decimal"

    def test_decimal_array_returns_none(self) -> None:
        """
        DECIMAL(10,2)[] is a list of decimals, not a decimal.

        DuckDB spells a list type by suffixing its element type with ``[]``, so the raw
        type of a ``list(o.order_total)`` metric is ``DECIMAL(10,2)[]``. Stripping the
        parenthesized element parameters leaves ``DECIMAL`` and would annotate the field
        ``decimal.Decimal`` while the value arrives as a ``list`` — the annotation-vs-value
        defect the Decimal policy exists to end.
        """
        assert duckdb_type_to_python("DECIMAL(10,2)[]") is None

    # Complex types that return None (trigger TODO comment)
    def test_struct_returns_none(self) -> None:
        """STRUCT(...) returns None (complex type)."""
        assert duckdb_type_to_python("STRUCT(a INTEGER, b VARCHAR)") is None

    def test_array_returns_none(self) -> None:
        """ARRAY returns None (complex type)."""
        assert duckdb_type_to_python("INTEGER[]") is None

    def test_union_returns_none(self) -> None:
        """UNION(...) returns None (complex type)."""
        assert duckdb_type_to_python("UNION(a INTEGER, b VARCHAR)") is None

    # Case insensitivity
    def test_case_insensitive_lookup(self) -> None:
        """Type names are handled case-insensitively."""
        assert duckdb_type_to_python("varchar") == "str"

    # Parameterized types that should still map
    def test_varchar_with_length_returns_str(self) -> None:
        """VARCHAR(255) returns 'str' (params stripped)."""
        assert duckdb_type_to_python("VARCHAR(255)") == "str"

    @pytest.mark.parametrize(
        "type_name,expected",
        [
            ("VARCHAR", "str"),
            ("INTEGER", "int"),
            ("BIGINT", "int"),
            ("SMALLINT", "int"),
            ("TINYINT", "int"),
            ("HUGEINT", "decimal.Decimal"),
            ("UBIGINT", "int"),
            ("UINTEGER", "int"),
            ("USMALLINT", "int"),
            ("UTINYINT", "int"),
            ("DOUBLE", "float"),
            ("FLOAT", "float"),
            ("BOOLEAN", "bool"),
            ("DATE", "datetime.date"),
            ("TIMESTAMP", "datetime.datetime"),
            ("TIMESTAMP WITH TIME ZONE", "datetime.datetime"),
            ("TIMESTAMP_S", "datetime.datetime"),
            ("TIMESTAMP_MS", "datetime.datetime"),
            ("TIMESTAMP_NS", "datetime.datetime"),
            ("TIME", "datetime.time"),
            ("TIME WITH TIME ZONE", "datetime.time"),
            ("BLOB", "bytes"),
            ("INTERVAL", "datetime.timedelta"),
            ("DECIMAL(10,2)", "decimal.Decimal"),
            ("UUID", "str"),
            ("JSON", "str"),
            ("ENUM('sad', 'ok', 'happy')", "str"),
            ("", None),
            ("DECIMAL(10,2)[]", None),
            ("VARCHAR(255)[]", None),
            ("STRUCT(a INTEGER)", None),
            ("MAP(VARCHAR, INTEGER)", None),
            ("LIST(INTEGER)", None),
            ("UNION(a INTEGER)", None),
            ("UNKNOWN_TYPE", None),
        ],
    )
    def test_all_duckdb_type_mappings(self, type_name: str, expected: str | None) -> None:
        """All DuckDB type mappings return expected Python annotation."""
        assert duckdb_type_to_python(type_name) == expected


def test_decimal_annotation_follows_each_driver() -> None:
    """
    Each backend's decimal annotation names the type that backend's driver returns.

    This is the decimal rule restated after the Databricks measurement of 2026-08-16,
    asserted at the mapper level so it runs fully offline: no cassette, no warehouse.

    The rule was written against a real defect — three backends giving three *arbitrary*
    answers for the same shape of column. Before it, Snowflake said ``int`` for scale 0
    and ``float`` otherwise (a copy of a driver configuration Semolina does not use),
    Databricks said ``float``, and DuckDB emitted a ``TODO:``. None of the three described
    what arrived. The Decimal policy replaced that with one rule: annotate what the driver
    returns.

    Two backends land on ``decimal.Decimal`` under that rule, because their drivers deliver
    ``decimal128`` and pyarrow converts it unconditionally. Databricks lands on ``str``,
    because the Foundry ADBC driver delivers an Arrow string — measured, at every precision
    and scale including 0. The rule did not change; one backend's driver answers differently.

    So the invariant worth guarding is not that the three strings are equal. It is that no
    backend annotates a decimal column as something its driver never produces, which is what
    would let a generated model lie to a user. Uniformity was evidence of that invariant
    holding while all three drivers behaved alike; it is not the invariant itself.
    """
    snowflake = snowflake_json_type_to_python({"type": "FIXED", "scale": 0})
    databricks = databricks_type_to_python({"name": "decimal", "precision": 10, "scale": 2})
    duckdb = duckdb_type_to_python("DECIMAL(10,2)")

    # The two backends whose drivers return decimal128 still agree, and must not drift apart:
    # nothing measured in this session touched either of them.
    assert {snowflake, duckdb} == {"decimal.Decimal"}, (snowflake, duckdb)

    # Databricks diverges by measurement, not by oversight. Pinned so that restoring it to
    # decimal.Decimal is a deliberate act — which is exactly what should happen the day the
    # driver ships native decimals (upstream adbc-drivers/databricks#106).
    assert databricks == "str", databricks

    # And the property that actually generalizes: every backend says *something* concrete
    # about a decimal column. A None here would put a `TODO:` back in generated source.
    assert None not in {snowflake, databricks, duckdb}
