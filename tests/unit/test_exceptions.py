"""
Tests for Semolina's exception hierarchy.

Every error Semolina defines derives from :class:`semolina.SemolinaError`, so a backend can
catch "anything Semolina raised on purpose" in one clause. The original bases stay, so every
``except RuntimeError`` or ``except ValueError`` written against 0.6.0 still matches.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from typing import TYPE_CHECKING

import pytest

import semolina
from semolina import exceptions
from semolina.registry import get_async_engine, get_engine, reset

if TYPE_CHECKING:
    from collections.abc import Callable


def _defined_exception_classes() -> list[tuple[str, type[BaseException]]]:
    """
    Find every public exception class a Semolina module defines itself.

    Read from source rather than from module attributes, so a re-export is counted once, at
    its definition, and a class added later is found without anyone updating a list.

    Returns:
        ``(dotted name, class)`` pairs, sorted by name.
    """
    found: dict[str, type[BaseException]] = {}
    modules = ["semolina"] + [
        info.name
        for info in pkgutil.walk_packages(semolina.__path__, "semolina.")
        if not info.name.rsplit(".", 1)[1].startswith("_") and not info.name.endswith("conftest")
    ]
    for name in modules:
        module = importlib.import_module(name)
        assert module.__file__ is not None
        with open(module.__file__, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node.name.startswith("_"):
                continue
            cls = getattr(module, node.name)
            if isinstance(cls, type) and issubclass(cls, BaseException):
                found[f"{name}.{node.name}"] = cls
    return sorted(found.items())


EXCEPTION_CLASSES = _defined_exception_classes()


def test_the_scan_finds_the_known_errors() -> None:
    """The source scan is not vacuous: it finds the errors users already catch."""
    names = {cls.__name__ for _, cls in EXCEPTION_CLASSES}
    assert {
        "SemolinaViewNotFoundError",
        "SemolinaConnectionError",
        "SemolinaMissingDependencyError",
        "SemolinaSchemaMismatchError",
        "SemolinaResultConsumedError",
    } <= names


def test_semolina_error_is_exported() -> None:
    """``SemolinaError`` is importable from the package root and is an ``Exception``."""
    assert "SemolinaError" in semolina.__all__
    assert issubclass(semolina.SemolinaError, Exception)


@pytest.mark.parametrize(
    "cls", [cls for _, cls in EXCEPTION_CLASSES], ids=[name for name, _ in EXCEPTION_CLASSES]
)
def test_every_error_derives_from_semolina_error(cls: type[BaseException]) -> None:
    """Each public exception class Semolina defines is a ``SemolinaError``."""
    assert issubclass(cls, semolina.SemolinaError)


@pytest.mark.parametrize(
    "name",
    [
        "SemolinaViewNotFoundError",
        "SemolinaConnectionError",
        "SemolinaMissingDependencyError",
        "SemolinaSchemaMismatchError",
        "SemolinaResultConsumedError",
    ],
)
def test_existing_errors_keep_runtime_error(name: str) -> None:
    """The 0.6.0 errors are still ``RuntimeError``, so existing ``except`` clauses match."""
    assert issubclass(getattr(semolina, name), RuntimeError)


@pytest.mark.parametrize("name", ["SemolinaViewNotFoundError", "SemolinaConnectionError"])
def test_engine_errors_live_in_exceptions_and_stay_importable_from_engines(name: str) -> None:
    """The engine errors are defined in ``semolina.exceptions``; ``engines.base`` re-exports."""
    from semolina.engines import base

    defined = getattr(exceptions, name)
    assert defined.__module__ == "semolina.exceptions"
    assert getattr(base, name) is defined
    assert name in base.__all__


@pytest.fixture
def empty_registry():
    """Start and finish with no engines registered."""
    reset()
    yield
    reset()


@pytest.mark.usefixtures("empty_registry")
@pytest.mark.parametrize("lookup", [get_engine, get_async_engine])
def test_an_unregistered_engine_raises_a_dedicated_error(
    lookup: Callable[[str], object],
) -> None:
    """
    ``get_engine`` and ``get_async_engine`` raise ``SemolinaEngineNotRegisteredError``.

    It is a ``SemolinaError`` and still a ``ValueError``, so 0.6.0 handlers keep matching.
    """
    with pytest.raises(semolina.SemolinaEngineNotRegisteredError, match="registered") as info:
        lookup("missing")
    assert isinstance(info.value, ValueError)
    assert isinstance(info.value, semolina.SemolinaError)
