"""
SQL type to Python annotation mapping for Snowflake and Databricks.

Converts the type metadata returned by warehouse introspection APIs into
Python annotation strings suitable for use in generated SemanticView code.
Types without clean Python equivalents (GEOGRAPHY, VARIANT, ARRAY, etc.)
return None, which signals the renderer to emit a TODO comment instead.
"""

from __future__ import annotations

# Snowflake SQL type names → Python annotation strings.
# FIXED is handled separately (scale=0 → int, scale>0 → float).
# Keys are uppercase as returned by the Snowflake metadata API.
_SNOWFLAKE_TYPE_MAP: dict[str, str] = {
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
    "decimal": "float",
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
    key that determines whether the value maps to ``int`` (scale=0) or ``float``
    (scale>0).

    Args:
        type_json: Type descriptor dict from the Snowflake metadata API.
            Must contain a ``type`` key. FIXED types should also contain
            a ``scale`` key (defaults to 0 if absent).

    Returns:
        Python annotation string (e.g., ``'int'``, ``'str'``,
        ``'datetime.datetime'``), or ``None`` if the type has no clean
        Python equivalent (ARRAY, OBJECT, VARIANT, GEOGRAPHY, GEOMETRY,
        or any unknown type name). ``None`` signals the renderer to emit a
        TODO comment in the generated output.

    Example:
        ```python
        from cubano.codegen.type_map import (
            snowflake_json_type_to_python,
        )

        snowflake_json_type_to_python({"type": "TEXT"})
        # 'str'
        snowflake_json_type_to_python({"type": "FIXED", "scale": 0})
        # 'int'
        snowflake_json_type_to_python({"type": "FIXED", "scale": 2})
        # 'float'
        snowflake_json_type_to_python({"type": "ARRAY"})
        # None
        ```
    """
    raw_type = type_json.get("type")
    if not isinstance(raw_type, str):
        return None

    type_name = raw_type.upper()

    if type_name == "FIXED":
        scale = type_json.get("scale", 0)
        return "int" if scale == 0 else "float"

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
        ```python
        from cubano.codegen.type_map import (
            databricks_type_to_python,
        )

        databricks_type_to_python({"name": "string"})
        # 'str'
        databricks_type_to_python({"name": "bigint"})
        # 'int'
        databricks_type_to_python({"name": "array"})
        # None
        ```
    """
    raw_name = type_obj.get("name")
    if not isinstance(raw_name, str):
        return None

    type_name = raw_name.lower()
    return _DATABRICKS_TYPE_MAP.get(type_name)
