"""
Tests for Semolina's public export surface.

Every name here is one users import by name, so a rename or a missed ``__all__`` entry is a
breaking change rather than a refactor.
"""

from __future__ import annotations

import pytest

import semolina


@pytest.mark.parametrize("name", semolina.__all__)
def test_every_exported_name_resolves(name: str) -> None:
    """
    Each name in ``__all__`` exists on the package.

    A stale entry breaks ``from semolina import *`` with an ``AttributeError`` at the user's
    import line, naming nothing they wrote.
    """
    assert hasattr(semolina, name)


@pytest.mark.parametrize(
    "name",
    [
        # The annotation codegen writes for a VARIANT column.
        "JsonValue",
        # Raised by every optional-dependency guard, so `except` must be able to name it.
        "SemolinaMissingDependencyError",
        # Raised by `.into(DTO)` when the result schema cannot fill the DTO.
        "SemolinaSchemaMismatchError",
        # Raised when a cursor's result is read a second way.
        "SemolinaResultConsumedError",
    ],
)
def test_is_exported_in_all(name: str) -> None:
    """Names users are documented to import are in ``__all__``, so they are supported."""
    assert name in semolina.__all__


def test_jsonvalue_subscripts_a_field_descriptor() -> None:
    """
    ``Dimension[JsonValue]()`` constructs, which is the position the alias exists for.

    At runtime the alias is a string, so this produces a ``ForwardRef`` subscript rather
    than a resolved type. That is expected: the alias is recursive, and Python's floor here
    (3.11) predates PEP 695 ``type`` statements, so the string form is the only one a
    typechecker accepts.
    """
    from semolina import Dimension, JsonValue

    class Events(semolina.SemanticView, view="events"):
        payload = Dimension[JsonValue]()

    assert Events.payload.name == "payload"


@pytest.mark.parametrize(
    "name",
    ["Query", "Field", "Engine", "AsyncEngine", "And", "Or", "Not", "Lookup"],
)
def test_names_users_annotate_with_are_exported(name: str) -> None:
    """
    The types a backend annotates its own code with are importable from ``semolina``.

    A service that builds a query in one function and executes it in another needs
    ``Query`` for the annotation, and code composing filters needs the predicate classes.
    """
    assert name in semolina.__all__
    assert hasattr(semolina, name)


def test_query_is_public_and_the_old_name_still_works() -> None:
    """``Query`` is the builder's public name; ``_Query`` stays an alias for one release."""
    from semolina.query import Query, _Query

    assert _Query is Query
    assert Query.__name__ == "Query"


@pytest.mark.parametrize(
    "name",
    ["AsyncEngine", "SemolinaViewNotFoundError", "SemolinaConnectionError"],
)
def test_engines_package_exports_the_async_engine_and_its_errors(name: str) -> None:
    """``semolina.engines`` exports the async engine and the errors an engine raises."""
    import semolina.engines

    assert name in semolina.engines.__all__
    assert hasattr(semolina.engines, name)


def _public_modules() -> list[str]:
    """
    List every importable module under ``semolina`` whose name has no leading underscore.

    ``__main__`` runs the CLI on import, and ``conftest`` is pytest's, so neither is a
    module a user imports names from.

    Returns:
        Dotted module names, sorted.
    """
    import pkgutil

    names = ["semolina"]
    for info in pkgutil.walk_packages(semolina.__path__, "semolina."):
        leaf = info.name.rsplit(".", 1)[1]
        if leaf.startswith("_") or leaf == "conftest":
            continue
        names.append(info.name)
    return sorted(names)


def _defined_public_names(module_name: str) -> set[str]:
    """
    Return the public classes and functions a module defines itself, read from its source.

    Imported names are left out: a module re-exporting another's class is a choice that
    module's ``__all__`` makes, not something it must do.

    Args:
        module_name: A dotted module name.

    Returns:
        Top-level ``def`` and ``class`` names with no leading underscore.
    """
    import ast
    import importlib

    module = importlib.import_module(module_name)
    assert module.__file__ is not None
    with open(module.__file__, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and not node.name.startswith("_")
    }


@pytest.mark.parametrize("module_name", _public_modules())
def test_every_public_module_declares_all(module_name: str) -> None:
    """
    Each public module has an ``__all__`` whose names resolve and that lists what it defines.

    Without ``__all__`` a type checker treats every imported name as re-exported, so
    ``from semolina.query import Dialect`` would type-check and quietly become API.
    """
    import importlib

    module = importlib.import_module(module_name)
    exported = getattr(module, "__all__", None)
    assert exported is not None, f"{module_name} has no __all__"
    assert len(set(exported)) == len(exported), f"{module_name}.__all__ repeats a name"
    missing = [name for name in exported if not hasattr(module, name)]
    assert not missing, f"{module_name}.__all__ names {missing}, which do not exist"
    unlisted = _defined_public_names(module_name) - set(exported)
    assert not unlisted, f"{module_name} defines {sorted(unlisted)} but leaves them out of __all__"
