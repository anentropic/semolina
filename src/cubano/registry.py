"""Engine registry for named engine registration and lazy lookup."""

from typing import Any, Final

_engines: dict[str, Any] = {}
_default_name: Final[str] = "default"


def register(name: str, engine: Any) -> None:
    """
    Register an engine by name.

    Raises ValueError if the name is already registered.

    Example:
        >>> from cubano.engines.mock import MockEngine
        >>> engine = MockEngine()
        >>> register("test_reg", engine)
        >>> get_engine("test_reg") is engine
        True
        >>> unregister("test_reg")
    """
    if name in _engines:
        raise ValueError(f"Engine '{name}' is already registered")
    _engines[name] = engine


def get_engine(name: str | None = None) -> Any:
    """
    Get an engine by name, or the default engine if no name specified.

    Raises ValueError if the requested engine is not registered.
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
                "Use cubano.register(name, engine) to register an engine."
            )
    return _engines[lookup_name]


def unregister(name: str) -> None:
    """
    Unregister an engine by name.

    Does not raise an error if the name is not registered (silent no-op).
    """
    _engines.pop(name, None)


def reset() -> None:
    """Clear all registered engines (for testing only)."""
    _engines.clear()
