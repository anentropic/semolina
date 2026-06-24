"""
Engine registry for named registration and lazy lookup.

Stores a name→:class:`~semolina.engines.base.Engine` map (each Engine carries
its own ADBC pool and dialect), retrievable by name via :func:`get_engine`.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from .engines.base import Engine

_engines: dict[str, Engine] = {}
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
    """
    if name in _engines:
        raise ValueError(f"Engine '{name}' is already registered")
    _engines[name] = engine


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


def unregister(name: str) -> None:
    """
    Unregister an engine by name.

    Does not raise an error if the name is not registered (silent no-op).
    """
    _engines.pop(name, None)


def reset() -> None:
    """
    Clear all registered engines (for testing only).

    Disposes each engine via its public :meth:`~semolina.engines.base.Engine.dispose`
    (which selects ``close_pool()`` vs ``pool.close()``), then drops the registry.
    The registry is always cleared even if a teardown raises, so one bad engine
    cannot wedge subsequent tests.
    """
    for engine in _engines.values():
        # Test-only teardown: pool close can surface driver/OS shutdown errors
        # (OSError) or poolhouse teardown failures (RuntimeError); swallow only
        # those so a flaky close does not break test isolation, while genuine
        # programming errors (e.g. AttributeError) still propagate.
        with contextlib.suppress(OSError, RuntimeError):
            engine.dispose()
    _engines.clear()
