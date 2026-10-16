"""
Tests for Semolina's exception hierarchy.

Every error Semolina defines derives from :class:`semolina.SemolinaError`, so a backend can
catch "anything Semolina raised on purpose" in one clause. The original bases stay, so every
``except RuntimeError`` or ``except ValueError`` written against 0.6.0 still matches.
"""

# Test-only: one test calls the private column check the cursors share, the narrowest way to
# reach the duplicate-column error without a custom engine.
# pyright: reportPrivateUsage=false

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
    "name",
    [
        "SemolinaViewNotFoundError",
        "SemolinaConnectionError",
        "SemolinaExtensionLoadError",
        "SemolinaIntrospectionError",
        "SemolinaEngineNotRegisteredError",
        "SemolinaMissingDependencyError",
        "SemolinaSchemaMismatchError",
        "SemolinaResultConsumedError",
        "SemolinaDuplicateColumnsError",
    ],
)
def test_errors_the_query_path_raises_are_exported(name: str) -> None:
    """Every error a query, engine or cursor can raise is importable from ``semolina``."""
    assert name in semolina.__all__
    assert getattr(semolina, name) is getattr(exceptions, name)


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


def test_every_error_class_is_defined_in_the_exceptions_module() -> None:
    """
    Every public exception class lives in ``semolina.exceptions``, listed in ``__all__`` (ARCH-7).

    The module says it holds "Semolina's errors"; a class defined anywhere else is one a
    reader of that module never learns about. Other modules may keep an alias, which the
    source scan does not count.
    """
    stray = [name for name, _ in EXCEPTION_CLASSES if not name.startswith("semolina.exceptions.")]
    assert stray == []
    defined = {cls.__name__ for _, cls in EXCEPTION_CLASSES}
    assert defined <= set(exceptions.__all__)


@pytest.mark.parametrize(
    ("module", "name"),
    [
        ("semolina.codegen.python_renderer", "GeneratedSourceError"),
        ("semolina.codegen.type_compare", "Unresolvable"),
    ],
)
def test_moved_codegen_errors_stay_importable_from_their_old_module(module: str, name: str) -> None:
    """The codegen errors keep their old import path as an alias of the class in exceptions."""
    cls = getattr(importlib.import_module(module), name)
    assert cls.__module__ == "semolina.exceptions"
    assert issubclass(cls, semolina.SemolinaError)


def test_a_result_with_duplicate_column_names_raises_a_semolina_error() -> None:
    """
    A result Rows cannot hold is a warehouse-result condition, so it is a ``SemolinaError``.

    It stays a ``ValueError`` too, so 0.6 ``except ValueError`` clauses still match.
    """
    from semolina.results import _distinct_columns

    with pytest.raises(semolina.SemolinaError) as raised:
        _distinct_columns(["x", "x"])
    assert isinstance(raised.value, ValueError)
