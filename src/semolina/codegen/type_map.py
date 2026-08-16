"""
SQL type to Python annotation mapping for Snowflake, Databricks, and DuckDB.

Converts the type metadata returned by warehouse introspection APIs into
Python annotation strings suitable for use in generated SemanticView code.
Types without clean Python equivalents (GEOGRAPHY, ARRAY, STRUCT, etc.)
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
    # TYPE-06: a semi-structured column annotates the semolina.JsonValue union rather than
    # an opaque Any. The renderer adds JsonValue to the generated module's
    # `from semolina import ...` line when any field resolves to it.
    "VARIANT": "JsonValue",
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
    # Decision 1 (47-DECISIONS.md) maps a warehouse decimal to decimal.Decimal on all three
    # backends. Databricks is a measured carve-out from it, and the carve-out is the honest
    # reading of Decision 1 rather than a departure from it.
    #
    # Decision 1 rests on a stated premise: "a user with a money column already receives a
    # Decimal today", because pyarrow converts decimal128 to decimal.Decimal unconditionally
    # at to_pylist(). It says so explicitly — "the annotation is being corrected to the value,
    # never the reverse" — and it was written on DuckDB and Snowflake evidence. The Databricks
    # decimal *value* was never measured; that was a recorded evidence limitation.
    #
    # Measured 2026-08-16 against a live workspace: the Foundry ADBC driver returns every
    # decimal as an Arrow string, at any precision and any scale including 0, for literals as
    # well as columns. So the premise is false here, and annotating decimal.Decimal would be
    # the option that "requires changing what arrives" — the thing Decision 1 forbids.
    #
    # This is a driver limitation, not a warehouse one. databricks-sql-connector reads
    # decimal128(38,2) off the same protocol for the same query, and the driver's own docs
    # mark decimal128 unsupported. The Thrift negotiation struct TSparkArrowTypes has a
    # decimalAsArrow member, but the driver hardcodes its answer and exposes no ADBC option to
    # change it; upstream adbc-drivers/databricks#106 is open, and the fix that exists lives on
    # an unmerged branch of a fork with no releases. Nothing here is settable from Semolina.
    #
    # If that changes, this entry is what changes back — see WINDOWS.md.
    "decimal": "str",
    "boolean": "bool",
    "date": "datetime.date",
    "timestamp": "datetime.datetime",
    "timestamp_ntz": "datetime.datetime",
    "binary": "bytes",
    # TYPE-06: see the VARIANT entry in _SNOWFLAKE_TYPE_MAP above. Kept as JsonValue rather
    # than narrowed to str alongside the two entries around it, because the measured value is
    # a *member* of the union rather than a contradiction of it: a VARIANT arrived as the
    # string '{"k":1,...}', and JsonValue admits str. Unlike the decimal annotation, this one
    # was never false — it is wider than what this driver delivers, which is what TYPE-06 asked
    # for, since the union holds whether a VARIANT arrives as raw JSON text or parsed.
    "variant": "JsonValue",
    # Both of Databricks' interval families arrive as strings, measured 2026-08-16 on a live
    # workspace: INTERVAL DAY TO SECOND as '3 04:05:06.789000000', INTERVAL YEAR TO MONTH as
    # '2-6'. Phase 48 left both unmapped for want of exactly this measurement, having reverted
    # a datetime.timedelta guess rather than ship it beside measured neighbours.
    #
    # The year-month family maps too, which Phase 48 expected never to happen: its argument was
    # that a month has no fixed length so no stdlib duration type could describe one. That
    # argument was correct and turned out not to be what the question depended on — no duration
    # ever arrives to be described.
    #
    # Interval-as-string is the wire format, not this driver's choice: TSparkArrowTypes carries
    # timestampAsArrow, decimalAsArrow, complexTypesAsArrow and nullTypeAsArrow and has no
    # interval member at all, and databricks-sql-connector returns the same string.
    #
    # `start_unit` and `end_unit` are never read — the lookup is on `name` alone, so no
    # catalogue-supplied unit string can reach a generated annotation (T-48-10).
    "interval": "str",
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
        Python equivalent (ARRAY, OBJECT, GEOGRAPHY, GEOMETRY, or any
        unknown type name). ``None`` signals the renderer to emit a
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
    key containing the type name in lowercase. Only ``name`` is read: no type this
    function maps needs the descriptor's other keys, so no catalogue-supplied string
    beyond the closed set of names in :data:`_DATABRICKS_TYPE_MAP` can influence the
    answer. That holds for an ``interval``'s ``start_unit``/``end_unit`` and for a
    ``decimal``'s ``precision``/``scale`` alike — both are ignored, and both types
    resolve on ``name`` alone.

    Two entries are Databricks-specific and are annotated from what the Foundry ADBC
    driver actually returns rather than from what the column declares: ``decimal`` and
    ``interval`` both arrive as Arrow strings, measured against a live workspace on
    2026-08-16. The reasoning and its limits are documented at the map itself.

    Args:
        type_obj: Type descriptor dict from the Databricks metadata API.
            Must contain a ``name`` key with the lowercase type name.

    Returns:
        Python annotation string (e.g., ``'int'``, ``'str'``,
        ``'datetime.datetime'``), or ``None`` if the type has no clean
        Python equivalent (array, map, struct, or any unknown type name).
        ``None`` signals the renderer to emit a TODO comment in the
        generated output.

    Example:
        .. code-block:: python

            from semolina.codegen.type_map import (
                databricks_type_to_python,
            )

            databricks_type_to_python({"name": "string"})
            # 'str'
            databricks_type_to_python({"name": "bigint"})
            # 'int'
            databricks_type_to_python({"name": "decimal", "precision": 38, "scale": 2})
            # 'str'
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
    # D-05: a HUGEINT arrives over Arrow as decimal128(38, 0), so the value is a
    # decimal.Decimal. It was annotated "int" until Phase 48; that is the Decimal policy
    # applied inconsistently, not a separate decision.
    "HUGEINT": "decimal.Decimal",
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
    "TIMESTAMP_S": "datetime.datetime",
    "TIMESTAMP_MS": "datetime.datetime",
    # D-04: this row is environment-dependent, and saying so is the point. A TIMESTAMP_NS
    # value arrives as a pandas.Timestamp when pandas is importable, as a
    # microsecond-truncated datetime.datetime when it is not, and pyarrow raises
    # ValueError when pandas is absent AND the value carries sub-microsecond precision
    # (pyarrow 24.0.0, scalar.pxi:706-725). pandas.Timestamp is a datetime.datetime
    # subclass, so datetime.datetime is a sound over-approximation rather than a clean
    # answer. Broken window 3 tracks it; 48-06 documents it for users.
    "TIMESTAMP_NS": "datetime.datetime",
    "TIME": "datetime.time",
    "TIME WITH TIME ZONE": "datetime.time",
    "BLOB": "bytes",
    # D-06: known wrong and deliberately left alone. The value is a
    # pyarrow.MonthDayNano, which no stdlib type describes, so replacing this annotation
    # is a design question Phase 48's specification does not cover. Recorded in
    # .planning/WINDOWS.md rather than silently widened.
    "INTERVAL": "datetime.timedelta",
    # D-03: these three annotate the measured VALUE, not the semantic type. A DuckDB UUID
    # arrives as a str, a JSON column as its raw unparsed text, and an ENUM as a str from
    # a dictionary-encoded column. Annotating uuid.UUID or a parsed JSON type would
    # recreate the annotation-vs-value defect Decision 1 exists to end. The warehouse's
    # own spelling survives into generated source as a comment (python_renderer.py's
    # _RAW_TYPE_COMMENT_BASE_TYPES), so no information is lost.
    "UUID": "str",
    "JSON": "str",
    "ENUM": "str",
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
