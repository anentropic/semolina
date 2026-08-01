"""
Engine registry for named registration and lazy lookup.

Stores a name→:class:`~semolina.engines.base.Engine` map (each Engine carries
its own ADBC pool and dialect), retrievable by name via :func:`get_engine`.

Async engines live in a **second, separate** store keyed the same way and
reached through :func:`get_async_engine`. Keeping the two apart is what stops a
lookup handing back an engine of the wrong kind — a single store holding a union
would let ``.using("reports").aexecute()`` resolve a synchronous engine and then
fail deep inside execution on a method that does not exist. The cost of the
split is that one name may hold both kinds at once, which is deliberate: the
same warehouse is often wanted from both a synchronous script and an async
request handler.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from .engines.abase import AsyncEngine
    from .engines.base import Engine

_engines: dict[str, Engine] = {}
_async_engines: dict[str, AsyncEngine] = {}
_default_name: Final[str] = "default"


def register(name: str, engine: Engine) -> None:
    """
    Register an :class:`~semolina.engines.base.Engine` by name.

    The Engine (which owns its own pool and dialect) is retrievable via
    :func:`get_engine` and used by :meth:`SemanticView.query` execution.

    Args:
        name: Unique name for the registration (e.g. ``"default"``).
        engine: The Engine to register, built via
            :func:`semolina.config.create_engine`.

    Raises:
        ValueError: If an engine is already registered under ``name``.

    Example:
        .. code-block:: python

            from adbc_poolhouse import DuckDBConfig

            import semolina
            from semolina.config import create_engine

            engine = create_engine(DuckDBConfig(database=":memory:"))
            semolina.register("default", engine)
            resolved = semolina.get_engine("default")

    See Also:
        - semolina.registry.register_async_engine: The async sibling, which
          writes to a separate store
    """
    if name in _engines:
        raise ValueError(f"Engine '{name}' is already registered")
    _engines[name] = engine


def register_async_engine(name: str, engine: AsyncEngine) -> None:
    """
    Register an :class:`~semolina.engines.abase.AsyncEngine` by name.

    Async engines are stored separately from synchronous ones, so registering
    here never shadows (or is shadowed by) :func:`register`. A name may
    legitimately hold one of each; :func:`get_async_engine` returns the async
    one and :func:`get_engine` the synchronous one.

    This is a plain function, not a coroutine — registration touches no
    connection and does no I/O.

    Args:
        name: Unique name for the registration (e.g. ``"default"``).
        engine: The AsyncEngine to register, built via
            :func:`semolina.config.create_async_engine`.

    Raises:
        ValueError: If an async engine is already registered under ``name``.

    Example:
        .. code-block:: python

            from adbc_poolhouse import DuckDBConfig

            import semolina
            from semolina.config import create_async_engine

            engine = create_async_engine(DuckDBConfig(database=":memory:"))
            semolina.register_async_engine("default", engine)
            resolved = semolina.get_async_engine("default")

    See Also:
        - semolina.registry.register: The synchronous sibling
        - semolina.registry.get_async_engine: Look an async engine up by name
        - semolina.config.create_async_engine: Builds the AsyncEngine to register
    """
    if name in _async_engines:
        raise ValueError(f"Async engine '{name}' is already registered")
    _async_engines[name] = engine


def get_engine(name: str | None = None) -> Engine:
    """
    Get a registered :class:`~semolina.engines.base.Engine` by name.

    Args:
        name: Engine name to look up. Defaults to ``"default"`` when ``None``.

    Returns:
        The registered Engine (carrying its own pool and dialect).

    Raises:
        ValueError: If no engine is registered with the given name.

    Example:
        .. code-block:: python

            engine = semolina.get_engine("default")

    See Also:
        - semolina.registry.get_async_engine: The async sibling, which reads a
          separate store
    """
    lookup = name if name is not None else _default_name
    if lookup in _engines:
        return _engines[lookup]
    available = list(_engines.keys())
    if available:
        available_str = ", ".join(f"'{k}'" for k in sorted(available))
        raise ValueError(
            f"No engine registered with name '{lookup}'. Available engines: {available_str}"
        )
    raise ValueError(
        f"No engine registered with name '{lookup}'. "
        "Use semolina.register(name, create_engine(config)) to register an engine."
    )


def get_async_engine(name: str | None = None) -> AsyncEngine:
    """
    Get a registered :class:`~semolina.engines.abase.AsyncEngine` by name.

    Reads the async store only. A name registered solely with :func:`register`
    is not visible here, and the lookup never falls back to the synchronous
    store: returning a synchronous engine to an ``aexecute`` call site would
    surface as a missing-attribute failure deep inside execution rather than as
    the registration mistake it is.

    This is a plain function, not a coroutine — lookup does no I/O.

    Args:
        name: Async engine name to look up. Defaults to ``"default"`` when
            ``None``.

    Returns:
        The registered AsyncEngine (carrying its own async pool and dialect).

    Raises:
        ValueError: If no async engine is registered with the given name.

    Example:
        .. code-block:: python

            engine = semolina.get_async_engine("default")

    See Also:
        - semolina.registry.get_engine: The synchronous sibling
        - semolina.registry.register_async_engine: Register an engine here
    """
    lookup = name if name is not None else _default_name
    if lookup in _async_engines:
        return _async_engines[lookup]
    available = list(_async_engines.keys())
    if available:
        available_str = ", ".join(f"'{k}'" for k in sorted(available))
        raise ValueError(
            f"No async engine registered with name '{lookup}'. "
            f"Available async engines: {available_str}"
        )
    raise ValueError(
        f"No async engine registered with name '{lookup}'. "
        "Use semolina.register_async_engine(name, create_async_engine(config)) "
        "to register an async engine."
    )


def unregister(name: str) -> None:
    """
    Unregister an engine by name.

    Does not raise an error if the name is not registered (silent no-op).
    Leaves any async engine registered under the same name untouched.
    """
    _engines.pop(name, None)


def unregister_async_engine(name: str) -> None:
    """
    Unregister an async engine by name.

    Does not raise an error if the name is not registered (silent no-op).
    Leaves any synchronous engine registered under the same name untouched.
    """
    _async_engines.pop(name, None)


def reset() -> None:
    """
    Clear all registered engines, synchronous and async (for testing only).

    Disposes each synchronous engine via its public
    :meth:`~semolina.engines.base.Engine.dispose` (which selects ``close_pool()``
    vs ``pool.close()``), tears each async engine's pool down inline, then drops
    both registries. They are always cleared even if a teardown raises, so one
    bad engine cannot wedge subsequent tests.

    Deliberately a plain function rather than a coroutine: it is autouse-invoked
    from a synchronous pytest fixture after every test, where there is no
    running event loop to await in.
    """
    for engine in _engines.values():
        # Test-only teardown: pool close can surface driver/OS shutdown errors
        # (OSError) or poolhouse teardown failures (RuntimeError); swallow only
        # those so a flaky close does not break test isolation, while genuine
        # programming errors (e.g. AttributeError) still propagate.
        with contextlib.suppress(OSError, RuntimeError):
            engine.dispose()
    _engines.clear()

    if _async_engines:
        # Deferred import so a plain (non-async) install still imports this
        # module; close_pool itself is in the base poolhouse surface.
        from adbc_poolhouse import close_pool

        for async_engine in _async_engines.values():
            # Same narrow suppression, different teardown call. AsyncEngine.dispose()
            # is a coroutine and this function cannot await, so the async pool is
            # closed inline through the inner synchronous pool it wraps —
            # literally the call AsyncPool.close() offloads to a worker thread.
            # Calling the async pool's own close() here would build an un-awaited
            # coroutine and close nothing, leaking a pool per test.
            with contextlib.suppress(OSError, RuntimeError):
                close_pool(async_engine._pool._pool)
    _async_engines.clear()
