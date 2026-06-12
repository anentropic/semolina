"""
Pool registry for named registration and lazy lookup.

Stores ``(pool, dialect)`` tuples for the pool-based API, retrievable by
name via :func:`get_pool`.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Final

from .dialect import Dialect, resolve_dialect

if TYPE_CHECKING:
    from .engines.sql import Dialect as DialectABC

_pools: dict[str, tuple[Any, DialectABC]] = {}
_default_name: Final[str] = "default"


def register(
    name: str,
    pool: Any,
    *,
    dialect: str | Dialect,
) -> None:
    """
    Register a connection pool and its dialect by name.

    The ``(pool, dialect)`` pair is retrievable via :func:`get_pool` and used
    by :meth:`SemanticView.query` execution.

    Args:
        name: Unique name for the registration (e.g. ``"default"``).
        pool: Connection pool instance to register.
        dialect: Dialect string or :class:`Dialect` enum value selecting the
            SQL generation backend.

    Raises:
        ValueError: If a pool is already registered under ``name``.

    Example:
        .. code-block:: python

            import semolina

            semolina.register("default", pool, dialect=semolina.Dialect.SNOWFLAKE)
            pool, dialect_instance = semolina.get_pool("default")
    """
    if name in _pools:
        raise ValueError(f"Pool '{name}' is already registered")
    resolved = resolve_dialect(dialect)
    _pools[name] = (pool, resolved)


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


def unregister(name: str) -> None:
    """
    Unregister a pool by name.

    Does not raise an error if the name is not registered (silent no-op).
    """
    _pools.pop(name, None)


def reset() -> None:
    """
    Clear all registered pools (for testing only).

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
