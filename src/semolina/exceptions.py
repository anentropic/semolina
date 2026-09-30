"""
Errors raised by Semolina's result-shaping surface, plus the optional-dependency guard.

The errors here are flat :class:`RuntimeError` subclasses with no common base, matching
:class:`~semolina.engines.base.SemolinaViewNotFoundError` and
:class:`~semolina.engines.base.SemolinaConnectionError`. That is deliberate: a
``SemolinaError`` base class would give app backends one ``except`` clause, but it would also
reparent errors this module has no business touching, so the engine errors stay exactly where
and what they are.

:func:`_require` is how every optional dependency is checked. It uses
``importlib.util.find_spec`` rather than a ``try: import``, so an absent package is detected
without importing a present one — the same mechanism
:func:`semolina.codegen.python_renderer.ruff_available` uses for the ``codegen-lint`` extra.
"""

from __future__ import annotations

import importlib.util

__all__ = [
    "SemolinaMissingDependencyError",
    "SemolinaResultConsumedError",
    "SemolinaSchemaMismatchError",
    "_claim_read",
    "_require",
]
"""
The module's interface, ``_require`` and ``_claim_read`` included.

The leading underscore means "internal to Semolina", not "internal to this file": both
cursors import them, and it is deliberately not re-exported from the package root because a
guard helper is not part of the public API. Listing it here says that out loud, and stops a
strict type checker reading a private function used only across module boundaries as dead
code.
"""


class SemolinaMissingDependencyError(RuntimeError):
    """Raised when a method needs an optional package that is not installed."""


class SemolinaSchemaMismatchError(RuntimeError):
    """Raised when a DTO's field annotations do not describe the result schema."""


class SemolinaResultConsumedError(RuntimeError):
    """
    Raised when a cursor's result is read a second way after the first has started.

    A result is one stream. Each way of reading it — the DBAPI fetches, ``for row in cursor``,
    ``fetch_record_batch()``, or one of the whole-result methods — keeps its own place in that
    stream, so a second way would start wherever the first had buffered up to and silently
    miss the rows in between. The message names both calls. To read a result twice, run the
    query twice.
    """


def _require(package: str, extra: str) -> None:
    """
    Raise unless ``package`` is importable, naming the extra that installs it.

    The check is ``importlib.util.find_spec``, so a package that *is* installed is never
    imported as a side effect of asking about it — the caller does its own function-local
    import afterwards.

    Two properties of this function are load-bearing and must survive any refactor: this
    module imports ``importlib.util`` (not ``from importlib.util import find_spec``), and the
    call is spelled ``importlib.util.find_spec(...)`` inside the body with no caching. That is
    exactly what lets a test reach it with ``patch("importlib.util.find_spec", ...)``. Hoisting
    the lookup or memoizing the answer would silently stop every one of those tests from
    patching anything, and they would keep passing.

    Args:
        package: The distribution's importable module name, e.g. ``"arrowmodel"``.
        extra: The Semolina extra that installs it, e.g. ``"arrowmodel"``. Rendered into the
            message as ``pip install semolina[{extra}]``.

    Raises:
        SemolinaMissingDependencyError: If ``package`` cannot be found.

    Example:
        .. code-block:: python

            from semolina.exceptions import _require

            _require("polars", "polars")
            # SemolinaMissingDependencyError: polars is required by this method but is
            # not installed. Install it with: pip install semolina[polars]
    """
    if importlib.util.find_spec(package) is None:
        raise SemolinaMissingDependencyError(
            f"{package} is required by this method but is not installed. "
            f"Install it with: pip install semolina[{extra}]"
        )


_DBAPI_FETCHES = "the DBAPI fetches"
"""
The one way of reading shared by ``fetchone``/``fetchmany``/``fetchall`` and their ``_rows``
variants, which all go through the driver's single DBAPI row iterator and so interleave
correctly, as DBAPI specifies.
"""


def _claim_read(
    reading: tuple[str, str] | None, call: str, *, dbapi: bool = False
) -> tuple[str, str]:
    """
    Record ``call`` as a cursor's way of reading its result, or refuse a second way.

    Called by both cursors before a method reads anything, and only once its dependency and
    schema checks have passed, so a call that fails before reading leaves the cursor free.

    Args:
        reading: The cursor's current claim — ``(way, first call)`` — or None before any read.
        call: How the reading method is named in the error, e.g. ``"fetchall_rows()"``.
        dbapi: True for the DBAPI fetches, which share one way of reading between them.

    Returns:
        The claim the cursor stores: unchanged if this is the same way of reading, new if it
        is the first.

    Raises:
        SemolinaResultConsumedError: If the result is already being read a different way.
    """
    way = _DBAPI_FETCHES if dbapi else call
    if reading is None:
        return (way, call)
    if reading[0] != way:
        first = reading[1]
        raise SemolinaResultConsumedError(
            f"{call} cannot read this result: {first} is already reading it. A cursor's result "
            f"is one stream, and a second way of reading it would silently skip the rows the "
            f"first has buffered. Keep to {first}, or run the query again to read it another way."
        )
    return reading
