"""
SQL type to Python annotation mapping for Snowflake, Databricks, and DuckDB.

Converts the type metadata returned by warehouse introspection APIs into
Python annotation strings suitable for use in generated SemanticView code.
Types without clean Python equivalents (GEOGRAPHY, VARIANT, ARRAY, etc.)
return None, which signals the renderer to emit a TODO comment instead.
"""

from __future__ import annotations

# Snowflake SQL type names → Python annotation strings.
# Keys are uppercase as returned by the Snowflake metadata API.
_SNOWFLAKE_TYPE_MAP: dict[str, str] = {
    # Decision 1 (47-DECISIONS.md): the whole FIXED family annotates decimal.Decimal,
    # scale 0 included. The Snowflake driver returns Decimal128 for every FIXED column
    # while use_high_precision is enabled — its default, which adbc-poolhouse never
    # changes — so a NUMBER(38,0) arrives as a decimal.Decimal, not an int. The scale
    # key is therefore never read.
    "FIXED": "decimal.Decimal",
    "TEXT": "str",
    "REAL": "float",
    "BOOLEAN": "bool",
    "DATE": "datetime.date",
    "TIMESTAMP_LTZ": "datetime.datetime",
    "TIMESTAMP_NTZ": "datetime.datetime",
    "TIMESTAMP_TZ": "datetime.datetime",
    "TIME": "datetime.time",
    "BINARY": "bytes",
}

# Databricks type names → Python annotation strings.
# Keys are lowercase as returned by the Databricks metadata API.
_DATABRICKS_TYPE_MAP: dict[str, str] = {
    "string": "str",
    "bigint": "int",
    "int": "int",
    "smallint": "int",
    "tinyint": "int",
    "long": "int",
    "double": "float",
    "float": "float",
    # Decision 1 (47-DECISIONS.md): a decimal column annotates decimal.Decimal on all
    # three backends. No branch is needed — precision and scale do not change the answer
    # under this policy, so the type object's `name` alone decides it.
    "decimal": "decimal.Decimal",
    "boolean": "bool",
    "date": "datetime.date",
    "timestamp": "datetime.datetime",
    "timestamp_ntz": "datetime.datetime",
    "binary": "bytes",
}


def snowflake_json_type_to_python(type_json: dict[str, object]) -> str | None:
    """
    Map a Snowflake JSON type descriptor to a Python annotation string.

    Snowflake's metadata API returns type information as JSON objects with at
    minimum a ``type`` key. FIXED (integer/decimal) types also carry a ``scale``
    key, which this function ignores: every FIXED column arrives as a
    ``decimal.Decimal``, so the declared scale does not change the annotation.

    Args:
        type_json: Type descriptor dict from the Snowflake metadata API.
            Must contain a ``type`` key. Any other key it carries — including
            ``scale`` — is not read.

    Returns:
        Python annotation string (e.g., ``'int'``, ``'str'``,
        ``'datetime.datetime'``), or ``None`` if the type has no clean
        Python equivalent (ARRAY, OBJECT, VARIANT, GEOGRAPHY, GEOMETRY,
        or any unknown type name). ``None`` signals the renderer to emit a
        TODO comment in the generated output.

    Example:
        .. code-block:: python

            from semolina.codegen.type_map import (
                snowflake_json_type_to_python,
            )

            snowflake_json_type_to_python({"type": "TEXT"})
            # 'str'
            snowflake_json_type_to_python({"type": "FIXED", "scale": 0})
            # 'decimal.Decimal'
            snowflake_json_type_to_python({"type": "FIXED", "scale": 2})
            # 'decimal.Decimal'
            snowflake_json_type_to_python({"type": "ARRAY"})
            # None
    """
    raw_type = type_json.get("type")
    if not isinstance(raw_type, str):
        return None

    type_name = raw_type.upper()
    return _SNOWFLAKE_TYPE_MAP.get(type_name)


def databricks_type_to_python(type_obj: dict[str, object]) -> str | None:
    """
    Map a Databricks type descriptor to a Python annotation string.

    Databricks' metadata API returns type information as objects with a ``name``
    key containing the type name in lowercase.

    Args:
        type_obj: Type descriptor dict from the Databricks metadata API.
            Must contain a ``name`` key with the lowercase type name.

    Returns:
        Python annotation string (e.g., ``'int'``, ``'str'``,
        ``'datetime.datetime'``), or ``None`` if the type has no clean
        Python equivalent (array, map, struct, variant, or any unknown
        type name). ``None`` signals the renderer to emit a TODO comment
        in the generated output.

    Example:
        .. code-block:: python

            from semolina.codegen.type_map import (
                databricks_type_to_python,
            )

            databricks_type_to_python({"name": "string"})
            # 'str'
            databricks_type_to_python({"name": "bigint"})
            # 'int'
            databricks_type_to_python({"name": "array"})
            # None
    """
    raw_name = type_obj.get("name")
    if not isinstance(raw_name, str):
        return None

    type_name = raw_name.lower()
    return _DATABRICKS_TYPE_MAP.get(type_name)


# DuckDB SQL type names → Python annotation strings.
# Keys are uppercase. DuckDB returns uppercase type names from DESCRIBE SELECT.
_DUCKDB_TYPE_MAP: dict[str, str] = {
    "VARCHAR": "str",
    "INTEGER": "int",
    "BIGINT": "int",
    "SMALLINT": "int",
    "TINYINT": "int",
    "HUGEINT": "int",
    "UBIGINT": "int",
    "UINTEGER": "int",
    "USMALLINT": "int",
    "UTINYINT": "int",
    "DOUBLE": "float",
    "FLOAT": "float",
    "BOOLEAN": "bool",
    "DATE": "datetime.date",
    "TIMESTAMP": "datetime.datetime",
    "TIMESTAMP WITH TIME ZONE": "datetime.datetime",
    "TIME": "datetime.time",
    "TIME WITH TIME ZONE": "datetime.time",
    "BLOB": "bytes",
    "INTERVAL": "datetime.timedelta",
    # Decision 1 (47-DECISIONS.md): warehouse decimals annotate as decimal.Decimal on
    # all three backends. The key is the bare base name because the lookup below strips
    # parenthesized parameters, so DECIMAL(10,2) and DECIMAL(38,2) both arrive here as
    # "DECIMAL". This is an annotation change only: pyarrow already converts decimal128
    # to decimal.Decimal, and no value on the read path is coerced.
    "DECIMAL": "decimal.Decimal",
}


def duckdb_type_to_python(type_name: str) -> str | None:
    """
    Map a DuckDB SQL type name to a Python annotation string.

    DuckDB's ``DESCRIBE SELECT`` output returns type names as plain strings
    (e.g., ``'VARCHAR'``, ``'BIGINT'``, ``'TIMESTAMP WITH TIME ZONE'``).
    Parameterized types like ``'DECIMAL(10,2)'`` or ``'VARCHAR(255)'`` have
    their parenthesized suffix stripped before lookup, so ``'VARCHAR(255)'``
    correctly maps to ``'str'``.

    Args:
        type_name: Raw SQL type name from DuckDB ``DESCRIBE SELECT`` output.

    Returns:
        Python annotation string (e.g., ``'int'``, ``'str'``,
        ``'datetime.datetime'``, ``'decimal.Decimal'``), or ``None`` if the
        type has no clean Python equivalent (STRUCT, MAP, LIST, UNION, ARRAY,
        or any unknown type name). ``None`` signals the renderer to emit a
        TODO comment in the generated output.

    Example:
        .. code-block:: python

            from semolina.codegen.type_map import duckdb_type_to_python

            duckdb_type_to_python("VARCHAR")
            # 'str'
            duckdb_type_to_python("BIGINT")
            # 'int'
            duckdb_type_to_python("DECIMAL(10,2)")
            # 'decimal.Decimal'
            duckdb_type_to_python("STRUCT(a INTEGER)")
            # None
    """
    normalized = type_name.strip().upper()

    # DuckDB spells a list type by suffixing its element type with "[]", so a
    # `list(o.order_total)` metric describes as "DECIMAL(10,2)[]". Refuse container
    # types before the parameter strip below: stripping first would leave "DECIMAL"
    # and annotate a list of decimals as a scalar decimal.Decimal, which is exactly
    # the annotation-vs-value defect the Decimal policy exists to end.
    if normalized.endswith("]"):
        return None

    # Strip parenthesized type parameters: "DECIMAL(10,2)" -> "DECIMAL",
    # "VARCHAR(255)" -> "VARCHAR". Space-separated qualifiers like
    # "TIMESTAMP WITH TIME ZONE" are preserved since they contain no parens.
    base = normalized.split("(")[0].strip()
    return _DUCKDB_TYPE_MAP.get(base)
