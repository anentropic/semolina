"""
Arrow type to Python annotation mapping.

Converts a result schema's ``pyarrow.DataType`` into the Python annotation string a generated
SemanticView field should carry. This is the *result-schema* counterpart of
``semolina.codegen.type_map``, which maps the warehouse's own metadata type names; the two
must produce the same annotation for the same logical column.

Types without clean Python equivalents (interval, struct, map, list, union) return None,
which signals the caller to emit a TODO comment instead — the same contract the three SQL
mappers use, so a caller can build its own ``TODO: {dtype}`` string exactly as the three
engines already do.

Classification is by ``pyarrow.types.is_*`` predicate, never by matching ``str(dtype)``. An
Arrow type is parameterised, so it has no stable name to look up: the string forms are
``decimal128(38, 2)``, ``timestamp[us, tz=Europe/London]`` and
``dictionary<values=string, indices=uint8, ordered=0>``, none of which survive naive matching.
"""

from __future__ import annotations

import pyarrow
import pyarrow.types


def arrow_type_to_python(dtype: pyarrow.DataType) -> str | None:
    """
    Map an Arrow data type to a Python annotation string.

    Every answer here names the type a value of that column actually arrives as through
    ``RecordBatch.to_pylist()``, which is the conversion Semolina's row path performs. The
    answers agree with :mod:`semolina.codegen.type_map` for every column measured in
    ``47-TYPE-FIDELITY.md``, with one deliberate exception: an interval returns ``None``
    here while ``_DUCKDB_TYPE_MAP['INTERVAL']`` still reads ``'datetime.timedelta'``. That
    entry is known wrong (D-06, ``.planning/WINDOWS.md`` entry 6) and reproducing it would
    make two maps wrong in step, which reads as agreement rather than as an open question.

    Args:
        dtype: An Arrow type, typically read off a field of a result schema resolved by
            :func:`semolina.codegen.probe.probe_schema`.

    Returns:
        Python annotation string (e.g., ``'int'``, ``'str'``, ``'decimal.Decimal'``,
        ``'datetime.datetime'``), or ``None`` if the type has no clean Python equivalent
        (interval, duration, struct, map, list, union, null, or anything ``pyarrow`` adds
        later). ``None`` signals the caller to emit a TODO comment rather than guess.

    Example:
        .. code-block:: python

            import pyarrow

            from semolina.codegen.arrow_map import arrow_type_to_python

            arrow_type_to_python(pyarrow.decimal128(38, 2))
            # 'decimal.Decimal'
            arrow_type_to_python(pyarrow.timestamp("us", tz="Europe/London"))
            # 'datetime.datetime'
            arrow_type_to_python(pyarrow.struct([("a", pyarrow.int64())]))
            # None
    """
    # `bool` is tested first. It does not currently collide with `is_integer` (measured False
    # for a boolean at pyarrow 24.0.0), but `bool` subclasses `int` in Python and an editor
    # tidying this cascade "numerically" would move the integer test above it; the answer
    # would then silently become 'int' for every boolean column.
    if pyarrow.types.is_boolean(dtype):
        return "bool"
    if pyarrow.types.is_decimal(dtype):
        # Covers decimal128 and decimal256 at every precision and scale. 47-DECISIONS.md
        # Decision 1: a warehouse decimal annotates decimal.Decimal on all three backends,
        # scale 0 included.
        return "decimal.Decimal"
    if pyarrow.types.is_integer(dtype):
        return "int"
    if pyarrow.types.is_floating(dtype):
        return "float"
    if pyarrow.types.is_dictionary(dtype):
        # Resolved through the value type, not through this type. A DuckDB ENUM arrives
        # dictionary-encoded over a `string`, so the answer is 'str' — but a dictionary over
        # an unmapped value type has to stay honest and return None, which recursion gives
        # for free where a hard-coded 'str' would not.
        return arrow_type_to_python(dtype.value_type)
    if (
        pyarrow.types.is_string(dtype)
        or pyarrow.types.is_large_string(dtype)
        or pyarrow.types.is_string_view(dtype)
    ):
        # All three predicates are needed: `is_string` is False for both `large_string` and
        # `string_view` (measured, pyarrow 24.0.0), so a single test would send a plain
        # string column to a TODO.
        return "str"
    if (
        pyarrow.types.is_binary(dtype)
        or pyarrow.types.is_large_binary(dtype)
        or pyarrow.types.is_fixed_size_binary(dtype)
        or pyarrow.types.is_binary_view(dtype)
    ):
        return "bytes"
    if pyarrow.types.is_date(dtype):
        return "datetime.date"
    if pyarrow.types.is_timestamp(dtype):
        # Every unit and both tz-aware and naive. `timestamp[ns]` is a sound
        # over-approximation rather than an exact answer: the value is a `pandas.Timestamp`
        # when pandas is importable and a microsecond-truncated `datetime.datetime` when it
        # is not, and `pandas.Timestamp` subclasses `datetime.datetime` (D-04, broken
        # window 3).
        return "datetime.datetime"
    if pyarrow.types.is_time(dtype):
        return "datetime.time"
    return None
