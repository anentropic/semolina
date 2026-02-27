"""
Tests for SQL type → Python annotation mapping functions.

Tests cover Snowflake JSON type mappings and Databricks type mappings,
including all clean-Python-equivalent types and types that return None
to trigger TODO comment generation.
"""

from __future__ import annotations

import pytest

from semolina.codegen.type_map import databricks_type_to_python, snowflake_json_type_to_python


class TestSnowflakeJsonTypeToPython:
    """Tests for snowflake_json_type_to_python function."""

    # Numeric types
    def test_fixed_scale_zero_returns_int(self) -> None:
        """FIXED with scale=0 returns 'int'."""
        assert snowflake_json_type_to_python({"type": "FIXED", "scale": 0}) == "int"

    def test_fixed_scale_positive_returns_float(self) -> None:
        """FIXED with scale>0 returns 'float'."""
        assert snowflake_json_type_to_python({"type": "FIXED", "scale": 2}) == "float"

    def test_fixed_scale_large_returns_float(self) -> None:
        """FIXED with large scale returns 'float'."""
        assert snowflake_json_type_to_python({"type": "FIXED", "scale": 10}) == "float"

    def test_real_returns_float(self) -> None:
        """REAL returns 'float'."""
        assert snowflake_json_type_to_python({"type": "REAL"}) == "float"

    # String types
    def test_text_returns_str(self) -> None:
        """TEXT returns 'str'."""
        assert snowflake_json_type_to_python({"type": "TEXT"}) == "str"

    # Boolean types
    def test_boolean_returns_bool(self) -> None:
        """BOOLEAN returns 'bool'."""
        assert snowflake_json_type_to_python({"type": "BOOLEAN"}) == "bool"

    # Date/time types
    def test_date_returns_datetime_date(self) -> None:
        """DATE returns 'datetime.date'."""
        assert snowflake_json_type_to_python({"type": "DATE"}) == "datetime.date"

    def test_timestamp_ltz_returns_datetime_datetime(self) -> None:
        """TIMESTAMP_LTZ returns 'datetime.datetime'."""
        assert snowflake_json_type_to_python({"type": "TIMESTAMP_LTZ"}) == "datetime.datetime"

    def test_timestamp_ntz_returns_datetime_datetime(self) -> None:
        """TIMESTAMP_NTZ returns 'datetime.datetime'."""
        assert snowflake_json_type_to_python({"type": "TIMESTAMP_NTZ"}) == "datetime.datetime"

    def test_timestamp_tz_returns_datetime_datetime(self) -> None:
        """TIMESTAMP_TZ returns 'datetime.datetime'."""
        assert snowflake_json_type_to_python({"type": "TIMESTAMP_TZ"}) == "datetime.datetime"

    def test_time_returns_datetime_time(self) -> None:
        """TIME returns 'datetime.time'."""
        assert snowflake_json_type_to_python({"type": "TIME"}) == "datetime.time"

    # Binary types
    def test_binary_returns_bytes(self) -> None:
        """BINARY returns 'bytes'."""
        assert snowflake_json_type_to_python({"type": "BINARY"}) == "bytes"

    # Complex types that return None (trigger TODO comment)
    def test_array_returns_none(self) -> None:
        """ARRAY returns None (no clean Python equivalent)."""
        assert snowflake_json_type_to_python({"type": "ARRAY"}) is None

    def test_object_returns_none(self) -> None:
        """OBJECT returns None (no clean Python equivalent)."""
        assert snowflake_json_type_to_python({"type": "OBJECT"}) is None

    def test_variant_returns_none(self) -> None:
        """VARIANT returns None (no clean Python equivalent)."""
        assert snowflake_json_type_to_python({"type": "VARIANT"}) is None

    def test_geography_returns_none(self) -> None:
        """GEOGRAPHY returns None (no clean Python equivalent)."""
        assert snowflake_json_type_to_python({"type": "GEOGRAPHY"}) is None

    def test_geometry_returns_none(self) -> None:
        """GEOMETRY returns None (no clean Python equivalent)."""
        assert snowflake_json_type_to_python({"type": "GEOMETRY"}) is None

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
            ({"type": "FIXED", "scale": 0}, "int"),
            ({"type": "FIXED", "scale": 5}, "float"),
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
            ({"type": "VARIANT"}, None),
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
    def test_string_returns_str(self) -> None:
        """String returns 'str'."""
        assert databricks_type_to_python({"name": "string"}) == "str"

    # Integer types
    def test_bigint_returns_int(self) -> None:
        """Bigint returns 'int'."""
        assert databricks_type_to_python({"name": "bigint"}) == "int"

    def test_int_returns_int(self) -> None:
        """Int returns 'int'."""
        assert databricks_type_to_python({"name": "int"}) == "int"

    def test_smallint_returns_int(self) -> None:
        """Smallint returns 'int'."""
        assert databricks_type_to_python({"name": "smallint"}) == "int"

    def test_tinyint_returns_int(self) -> None:
        """Tinyint returns 'int'."""
        assert databricks_type_to_python({"name": "tinyint"}) == "int"

    def test_long_returns_int(self) -> None:
        """Long returns 'int'."""
        assert databricks_type_to_python({"name": "long"}) == "int"

    # Float types
    def test_double_returns_float(self) -> None:
        """Double returns 'float'."""
        assert databricks_type_to_python({"name": "double"}) == "float"

    def test_float_returns_float(self) -> None:
        """Float returns 'float'."""
        assert databricks_type_to_python({"name": "float"}) == "float"

    def test_decimal_returns_float(self) -> None:
        """Decimal returns 'float'."""
        assert databricks_type_to_python({"name": "decimal"}) == "float"

    # Boolean types
    def test_boolean_returns_bool(self) -> None:
        """Boolean returns 'bool'."""
        assert databricks_type_to_python({"name": "boolean"}) == "bool"

    # Date/time types
    def test_date_returns_datetime_date(self) -> None:
        """Date returns 'datetime.date'."""
        assert databricks_type_to_python({"name": "date"}) == "datetime.date"

    def test_timestamp_returns_datetime_datetime(self) -> None:
        """Timestamp returns 'datetime.datetime'."""
        assert databricks_type_to_python({"name": "timestamp"}) == "datetime.datetime"

    def test_timestamp_ntz_returns_datetime_datetime(self) -> None:
        """timestamp_ntz returns 'datetime.datetime'."""
        assert databricks_type_to_python({"name": "timestamp_ntz"}) == "datetime.datetime"

    # Binary types
    def test_binary_returns_bytes(self) -> None:
        """Binary returns 'bytes'."""
        assert databricks_type_to_python({"name": "binary"}) == "bytes"

    # Complex types that return None (trigger TODO comment)
    def test_array_returns_none(self) -> None:
        """Array returns None (no clean Python equivalent)."""
        assert databricks_type_to_python({"name": "array"}) is None

    def test_map_returns_none(self) -> None:
        """Map returns None (no clean Python equivalent)."""
        assert databricks_type_to_python({"name": "map"}) is None

    def test_struct_returns_none(self) -> None:
        """Struct returns None (no clean Python equivalent)."""
        assert databricks_type_to_python({"name": "struct"}) is None

    def test_variant_returns_none(self) -> None:
        """Variant returns None (no clean Python equivalent)."""
        assert databricks_type_to_python({"name": "variant"}) is None

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
            ({"name": "decimal"}, "float"),
            ({"name": "boolean"}, "bool"),
            ({"name": "date"}, "datetime.date"),
            ({"name": "timestamp"}, "datetime.datetime"),
            ({"name": "timestamp_ntz"}, "datetime.datetime"),
            ({"name": "binary"}, "bytes"),
            ({"name": "array"}, None),
            ({"name": "map"}, None),
            ({"name": "struct"}, None),
            ({"name": "variant"}, None),
        ],
    )
    def test_all_databricks_type_mappings(
        self, type_obj: dict[str, object], expected: str | None
    ) -> None:
        """All Databricks type mappings return expected Python annotation."""
        assert databricks_type_to_python(type_obj) == expected
