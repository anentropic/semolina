"""
The sync/async naming rule, enforced.

The rule (documented in ``how-to/connection-pools.rst``): an async-only class names its
methods like its sync counterpart, because the class already says the calls are awaited
(``await engine.dispose()``, ``await cursor.fetchall()``). The ``a`` prefix is kept for the
two places where a name would otherwise be ambiguous or where Python names the method:

- ``aexecute`` starts async work from a :class:`~semolina.query.Query`, which also has a
  synchronous ``execute``, and ``AsyncEngine.aexecute`` is the method it calls.
- ``aclose`` is the async-closing protocol ``contextlib.aclosing`` calls.

So there is no ``adispose`` or ``aconnect``: those would be twins of methods that do not
exist on the same object.
"""

from __future__ import annotations

import inspect

import pytest

from semolina.acursor import AsyncSemolinaCursor
from semolina.cursor import SemolinaCursor
from semolina.engines.abase import AsyncEngine
from semolina.engines.base import Engine
from semolina.query import Query

PREFIXED = {
    (AsyncEngine, "aexecute"): "the target of Query.aexecute",
    (AsyncSemolinaCursor, "aclose"): "the contextlib.aclosing protocol",
}
"""The ``a``-prefixed public methods the rule allows, each with its reason."""

PAIRS = [(AsyncEngine, Engine), (AsyncSemolinaCursor, SemolinaCursor)]


def _public_coroutines(cls: type) -> set[str]:
    """Return the public coroutine methods a class defines or inherits."""
    return {
        name
        for name, _ in inspect.getmembers(cls, inspect.iscoroutinefunction)
        if not name.startswith("_")
    }


@pytest.mark.parametrize(("async_cls", "sync_cls"), PAIRS, ids=lambda c: c.__name__)
def test_async_only_classes_name_methods_like_their_sync_counterpart(
    async_cls: type, sync_cls: type
) -> None:
    """Each coroutine method has a sync namesake, unless it is one of the allowed prefixes."""
    unmatched = {
        name
        for name in _public_coroutines(async_cls)
        if (async_cls, name) not in PREFIXED and not hasattr(sync_cls, name)
    }
    assert not unmatched, f"{async_cls.__name__} methods with no sync namesake: {unmatched}"


@pytest.mark.parametrize(("async_cls", "sync_cls"), PAIRS, ids=lambda c: c.__name__)
def test_no_unlisted_a_prefix(async_cls: type, sync_cls: type) -> None:
    """An ``a``-prefixed coroutine name whose unprefixed form exists on the sync class is new."""
    prefixed = {
        name
        for name in _public_coroutines(async_cls)
        if name.startswith("a") and hasattr(sync_cls, name[1:])
    }
    allowed = {name for (cls, name) in PREFIXED if cls is async_cls}
    assert prefixed <= allowed, f"unlisted a-prefixed methods: {prefixed - allowed}"


def test_query_offers_both_forms() -> None:
    """``Query`` is the one object with both, so its async form carries the prefix."""
    assert not inspect.iscoroutinefunction(Query.execute)
    assert inspect.iscoroutinefunction(Query.aexecute)
