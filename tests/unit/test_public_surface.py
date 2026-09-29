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
