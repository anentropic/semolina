"""
Engine registry for named engine registration and lazy lookup.
"""

from typing import Any

_engines: dict[str, Any] = {}
_default_name: str = "default"


def register(name: str, engine: Any) -> None:
    """
    Register an engine by name.
    """
    pass


def get_engine(name: str | None = None) -> Any:
    """
    Get an engine by name, or the default engine if no name specified.
    """
    pass


def unregister(name: str) -> None:
    """
    Unregister an engine by name.
    """
    pass


def reset() -> None:
    """
    Clear all registered engines (for testing only).
    """
    pass
