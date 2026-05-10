"""
Pool and engine registry for named registration and lazy lookup.

Stores (pool, dialect) tuples for the v0.3 pool-based API, and retains
backward-compatible engine storage for the v0.2 API (with deprecation
warnings).
"""

from __future__ import annotations

import contextlib
import warnings
from typing import TYPE_CHECKING, Any, Final

from .dialect import Dialect, resolve_dialect

if TYPE_CHECKING:
    from .engines.sql import Dialect as DialectABC

_pools: dict[str, tuple[Any, DialectABC]] = {}
_engines: dict[str, Any] = {}
_default_name: Final[str] = "default"


def register(
    name: str,
    pool_or_engine: Any,
    *,
    dialect: str | Dialect | None = None,
) -> None:
    """
    Register a pool (with dialect) or engine (deprecated) by name.

    When ``dialect`` is provided, registers a pool+dialect pair retrievable
    via ``get_pool()``. When ``dialect`` is omitted, falls back to the
    legacy engine registry (emits ``DeprecationWarning``).

    Args:
        name: Unique name for the registration (e.g. ``"default"``).
        pool_or_engine: Pool or engine instance to register.
        dialect: Dialect string or ``Dialect`` enum value. Required for
            pool registration. Omit for backward-compatible engine
            registration (deprecated).

    Raises:
        ValueError: If the name is already registered in the target registry.

    Example:
        .. code-block:: python

            import semolina

            semolina.register("default", pool, dialect="snowflake")
            pool, dialect_instance = semolina.get_pool("default")
    """
    if dialect is not None:
        if name in _pools:
            raise ValueError(f"Pool '{name}' is already registered")
        resolved = resolve_dialect(dialect)
        _pools[name] = (pool_or_engine, resolved)
    else:
        warnings.warn(
            "register(name, engine) without dialect= is deprecated. "
            "Use register(name, pool, dialect='snowflake') instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if name in _engines:
            raise ValueError(f"Engine '{name}' is already registered")
        _engines[name] = pool_or_engine


def get_pool(name: str | None = None) -> tuple[Any, DialectABC]:
    """
    Get a pool and its dialect by name, or the default pool.

    Args:
        name: Pool name to look up. Defaults to ``"default"`` when ``None``.

    Returns:
        Tuple of ``(pool, dialect_instance)``.

    Raises:
        ValueError: If no pool is registered with the given name.

    Example:
        .. code-block:: python

            pool, dialect = semolina.get_pool("default")
    """
    lookup = name if name is not None else _default_name
    if lookup in _pools:
        return _pools[lookup]
    available = list(_pools.keys())
    if available:
        available_str = ", ".join(f"'{k}'" for k in sorted(available))
        raise ValueError(
            f"No pool registered with name '{lookup}'. Available pools: {available_str}"
        )
    raise ValueError(
        f"No pool registered with name '{lookup}'. "
        "Use semolina.register(name, pool, dialect='snowflake') to register a pool."
    )


def get_engine(name: str | None = None) -> Any:
    """
    Get an engine by name, or the default engine if no name specified.

    .. deprecated::
        Use ``get_pool()`` for the new pool+dialect API.

    Raises:
        ValueError: If the requested engine is not registered.
    """
    lookup_name = name if name is not None else _default_name
    if lookup_name not in _engines:
        available = list(_engines.keys())
        if available:
            available_str = ", ".join(f"'{k}'" for k in sorted(available))
            raise ValueError(
                f"No engine registered with name '{lookup_name}'. "
                f"Available engines: {available_str}"
            )
        else:
            raise ValueError(
                f"No engine registered with name '{lookup_name}'. "
                "Use semolina.register(name, engine) to register an engine."
            )
    return _engines[lookup_name]


def unregister(name: str) -> None:
    """
    Unregister a pool or engine by name.

    Removes from both pool and engine registries. Does not raise an error
    if the name is not registered (silent no-op).
    """
    _pools.pop(name, None)
    _engines.pop(name, None)


def reset() -> None:
    """
    Clear all registered pools and engines (for testing only).

    Uses ``close_pool()`` from adbc-poolhouse for proper ADBC resource
    cleanup. Falls back to ``pool.close()`` for pools without an ADBC
    source connection.
    """
    for pool, _dialect in _pools.values():
        with contextlib.suppress(Exception):
            if hasattr(pool, "_adbc_source"):
                from adbc_poolhouse import close_pool

                close_pool(pool)
            else:
                pool.close()
    _pools.clear()
    _engines.clear()
