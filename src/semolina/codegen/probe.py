"""
Resolve a query's result schema from the driver, without consulting Semolina's type map.

This is the **result half** of the type-fidelity comparison Phase 47 established, promoted
out of ``tests/type_fidelity_probe.py`` so a shipped ``semolina codegen --check`` can reach
it: a released CLI cannot import from the test tree.

**Must not import** ``semolina.codegen.type_map``, or any symbol from it — the contract this
module carries with it out of the test tree, where it was a banner comment over the same code.
Two columns sourced from one place would make the comparison circular, and a comparison that
cannot produce a mismatch is not measuring anything. The schema returned here comes from the
driver's own answer — ADBC ``ExecuteSchema`` where the driver implements it, a zero-row
execution where it does not — and never from Semolina's own mapping of warehouse types to
Python annotations, which is the thing under measurement.
``tests/unit/test_type_fidelity_table.py::test_promoted_probe_does_not_import_the_type_map``
enforces this by parsing this file, so the contract is executable rather than advisory.

The ``sql`` a caller passes is expected to come from a ``SQLBuilder`` /
``DuckDBSQLBuilder`` ``build_select_with_params`` result, never from user-supplied text:
:func:`probe_schema`'s fallback branch wraps it as ``SELECT * FROM ({sql}) WHERE 1=0``, and
that wrapper adds no token of its own to escape (threat T-48-14).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Annotation-only. ``ProbeResult.schema`` names a ``pyarrow.Schema``, but nothing here
    # ever constructs one — the schema is whatever the driver handed back — and
    # ``from __future__ import annotations`` leaves the dataclass field a string, so
    # ``@dataclass`` never evaluates it. Importing pyarrow at module scope would give the
    # shipped probe a hard dependency on an optional extra for a name it only mentions.
    import pyarrow

ROUTE_EXECUTE_SCHEMA = "execute-schema"
"""Probe route taken when the driver answered ``adbc_execute_schema`` directly."""

ROUTE_ZERO_ROW = "zero-row"
"""Probe route taken when the driver refused ``ExecuteSchema`` and a ``WHERE 1=0`` query ran."""


def _resolve_not_implemented_errors() -> tuple[type[Exception], ...]:
    """
    Read the installed driver manager's exception classes for a refused ``ExecuteSchema``.

    Resolved from the installed package rather than assumed. In ``adbc_driver_manager``
    1.10.0 the DBAPI hierarchy is ``Error(Exception)`` ->
    ``DatabaseError`` -> ``{NotSupportedError, ProgrammingError, OperationalError, ...}``.
    ``NotSupportedError`` is the documented DBAPI mapping for ``StatusNotImplemented``, but
    it was never exercised against a refusing driver, so ``ProgrammingError`` and
    ``OperationalError`` are included: they are the two classes the manager also uses for
    driver-side status codes, and catching all three makes the fallback fire regardless of
    which one a given driver's status is mapped onto.

    Returns:
        The exception classes that mean "this driver will not answer ``ExecuteSchema``".
    """
    import adbc_driver_manager

    return (
        adbc_driver_manager.NotSupportedError,
        adbc_driver_manager.ProgrammingError,
        adbc_driver_manager.OperationalError,
    )


NOT_IMPLEMENTED_ERRORS: tuple[type[Exception], ...] = _resolve_not_implemented_errors()
"""
Exception classes that mean the driver refused ``ExecuteSchema``.

See :func:`_resolve_not_implemented_errors` for the resolved hierarchy and the installed
version it was read from.
"""


@dataclass(frozen=True)
class ProbeResult:
    """
    A probed result schema plus the route that produced it.

    Attributes:
        schema: The query's result schema, as the driver resolved it.
        route: :data:`ROUTE_EXECUTE_SCHEMA` or :data:`ROUTE_ZERO_ROW`. Recorded so the
            artifact's provenance cell is measured rather than assumed.
    """

    schema: pyarrow.Schema
    route: str


def probe_schema(cursor: Any, sql: str, params: list[Any]) -> ProbeResult:
    """
    Return a query's result schema without depending on Semolina's type map.

    Prefers ADBC ``ExecuteSchema``; falls back to a zero-row execution for drivers that
    answer ``NOT_IMPLEMENTED`` (Databricks) or that reject bound parameters (Snowflake).

    Neither branch fetches a row: the primary branch asks only for a schema, and the fallback
    reads ``reader.schema`` off a ``WHERE 1=0`` execution before closing the reader.

    Args:
        cursor: An ADBC DBAPI cursor.
        sql: The query whose result schema is wanted. Expected to be builder output, not
            user text — see this module's docstring.
        params: Bind parameters for that query. Pass ``[]`` rather than ``None`` — under
            cassette replay the parameter list is part of the lookup key.

    Returns:
        The resolved schema and the route that produced it.

    Example:
        .. code-block:: python

            from semolina.codegen.probe import probe_schema

            probed = probe_schema(cursor, sql, [])
            probed.route
            # 'execute-schema'
    """
    try:
        schema = cursor.adbc_execute_schema(sql, params)
    except NOT_IMPLEMENTED_ERRORS:
        cursor.execute(f"SELECT * FROM ({sql}) WHERE 1=0", params or None)
        reader = cursor.fetch_record_batch()
        try:
            fallback_schema = reader.schema
        finally:
            reader.close()
        return ProbeResult(schema=fallback_schema, route=ROUTE_ZERO_ROW)
    return ProbeResult(schema=schema, route=ROUTE_EXECUTE_SCHEMA)
