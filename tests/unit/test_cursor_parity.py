"""
The sync and async cursors guard and claim a result the same way, method for method (ARCH-2).

``SemolinaCursor`` and ``AsyncSemolinaCursor`` are separate classes, so a sync-style call on
an async cursor cannot hand back a coroutine. Their bodies are kept in step by hand, and four
shipped defects (A16, A17, A20, A22) were one twin changing without the other.
``test_async_naming.py`` checks only that the method names pair up.

These tests run each read method on both cursors with the dependency guard, the DTO schema
check and the read claim replaced by recorders, stop at the claim, and compare what each
twin did and in what order: which packages it demanded, whether it checked a DTO's schema
first, and how it claimed the result.
"""

# Test-only: the tests set a cursor's private reader to put it in the "already streaming"
# state.
# pyright: reportPrivateUsage=false

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

import semolina.acursor
import semolina.cursor
import semolina.dto
from semolina.acursor import AsyncSemolinaCursor
from semolina.cursor import SemolinaCursor

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine


class _Dto(BaseModel):
    """A DTO for the ``into`` methods; the schema check is recorded, never run."""

    revenue: int


class _Stop(Exception):
    """Raised by the recorded claim, so no method goes on to read from the mock cursor."""


Call = tuple[str, ...]

# (sync method, async method, positional args). Iteration pairs ``__next__`` with
# ``__anext__``; every other pair shares its name.
PAIRS: list[tuple[str, str, tuple[Any, ...]]] = [
    ("fetchall_rows", "fetchall_rows", ()),
    ("fetchone_row", "fetchone_row", ()),
    ("fetchmany_rows", "fetchmany_rows", (2,)),
    ("fetchall", "fetchall", ()),
    ("fetchone", "fetchone", ()),
    ("fetchmany", "fetchmany", (2,)),
    ("fetch_arrow_table", "fetch_arrow_table", ()),
    ("fetch_record_batch", "fetch_record_batch", ()),
    ("fetch_df", "fetch_df", ()),
    ("fetch_polars", "fetch_polars", ()),
    ("into", "into", (_Dto,)),
    ("iter_into", "iter_into", (_Dto,)),
    ("__next__", "__anext__", ()),
]

# Public sync methods that do not read the result, so have nothing to claim.
NOT_READS = {"close"}


def _record(monkeypatch: pytest.MonkeyPatch, module: Any, calls: list[Call]) -> None:
    """Replace ``module``'s guard and claim, and the DTO schema check, with recorders."""

    def require(package: str, extra: str) -> None:
        calls.append(("require", package, extra))

    def claim(_reading: Any, how: str, *, dbapi: bool = False) -> Any:
        # The async cursor names iteration "async for row in cursor"; the claim is the same.
        calls.append(("claim", how.removeprefix("async "), f"dbapi={dbapi}"))
        raise _Stop

    def check_schema(_description: Any, model: type[Any], *, check_types: bool) -> None:
        calls.append(("check_schema", model.__name__, f"check_types={check_types}"))

    monkeypatch.setattr(module, "_require", require)
    monkeypatch.setattr(module, "_claim_read", claim)
    monkeypatch.setattr(semolina.dto, "check_result_schema", check_schema)


def _run_sync(cursor: SemolinaCursor, name: str, args: tuple[Any, ...]) -> None:
    """Call a sync read method up to its claim."""
    method: Callable[..., Any] = getattr(cursor, name)
    with pytest.raises(_Stop):
        method(*args)


def _run_async(cursor: AsyncSemolinaCursor, name: str, args: tuple[Any, ...]) -> None:
    """
    Call an async read method up to its claim.

    The claim comes before any ``await``, so stepping the coroutine once reaches it without
    an event loop. ``iter_into`` is a plain method returning an async iterator, and claims
    when called.
    """
    method: Callable[..., Any] = getattr(cursor, name)
    with pytest.raises(_Stop):
        result = method(*args)
        if inspect.iscoroutine(result):
            coroutine: Coroutine[Any, Any, Any] = result
            try:
                coroutine.send(None)
            finally:
                coroutine.close()


def _cursors(*, streaming: bool) -> tuple[SemolinaCursor, AsyncSemolinaCursor]:
    """Return one cursor of each kind over mocks, with a reader already open if streaming."""
    sync_cursor = SemolinaCursor(MagicMock(), MagicMock())
    async_cursor = AsyncSemolinaCursor(MagicMock(), MagicMock())
    for cursor in (sync_cursor, async_cursor):
        # Nothing was really opened, so neither finalizer has anything to warn about.
        cursor._closed = True
        if streaming:
            cursor._reader = MagicMock()
    return sync_cursor, async_cursor


@pytest.mark.parametrize("streaming", [False, True], ids=["fresh", "streaming"])
@pytest.mark.parametrize(
    ("sync_name", "async_name", "args"), PAIRS, ids=[pair[0] for pair in PAIRS]
)
def test_twins_guard_and_claim_the_same_way(
    monkeypatch: pytest.MonkeyPatch,
    sync_name: str,
    async_name: str,
    args: tuple[Any, ...],
    streaming: bool,
) -> None:
    """Each pair demands the same packages, checks the same schema, then claims identically."""
    sync_calls: list[Call] = []
    async_calls: list[Call] = []
    sync_cursor, async_cursor = _cursors(streaming=streaming)

    _record(monkeypatch, semolina.cursor, sync_calls)
    _run_sync(sync_cursor, sync_name, args)
    _record(monkeypatch, semolina.acursor, async_calls)
    _run_async(async_cursor, async_name, args)

    assert sync_calls[-1][0] == "claim", sync_calls
    assert async_calls == sync_calls


def test_every_sync_read_method_has_a_pair_above() -> None:
    """
    A new read method on the sync cursor must be added to ``PAIRS``.

    Without this, a method added to both cursors would never be compared, which is the drift
    this module exists to catch.
    """
    public = {
        name
        for name, _ in inspect.getmembers(SemolinaCursor, inspect.isfunction)
        if not name.startswith("_")
    }
    paired = {sync_name for sync_name, _, _ in PAIRS}
    assert public - NOT_READS == paired - {"__next__"}
