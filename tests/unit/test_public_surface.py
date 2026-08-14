"""
Tests for Semolina's public export surface.

Every name here is one users import by name, so a rename or a missed ``__all__`` entry is a
breaking change rather than a refactor. These tests assert the import path, the ``__all__``
membership, and — for a type alias — that the name is usable in the position it exists for.
"""

from __future__ import annotations

import semolina


class TestJsonValue:
    """TYPE-06: ``semolina.JsonValue``, the annotation codegen writes for a VARIANT column."""

    def test_importable_from_the_package_root(self) -> None:
        """``from semolina import JsonValue`` succeeds."""
        from semolina import JsonValue

        assert JsonValue is not None

    def test_is_exported_in_all(self) -> None:
        """``JsonValue`` is in ``semolina.__all__``, so it is a supported public name."""
        assert "JsonValue" in semolina.__all__

    def test_subscripts_a_field_descriptor(self) -> None:
        """
        ``Dimension[JsonValue]()`` constructs, which is the position the alias exists for.

        At runtime the alias is a string, so this produces a ``ForwardRef`` subscript rather
        than a resolved type. That is expected: the alias is recursive, and Python's floor
        here (3.11) predates PEP 695 ``type`` statements, so the string form is the only one
        a typechecker accepts. Generated models are read textually, never by importing them.
        """
        from semolina import Dimension, JsonValue

        field = Dimension[JsonValue]()

        assert field is not None

    def test_names_every_json_scalar(self) -> None:
        """
        The alias covers the JSON value domain: scalars, null, arrays, and objects.

        Asserted on the alias text because at runtime the alias *is* its text. This is what
        makes the annotation sound whether a VARIANT arrives as raw JSON text or as a parsed
        structure — see the evidence limitation in ``.planning/WINDOWS.md``.
        """
        from semolina import JsonValue

        for member in ("str", "int", "float", "bool", "None", "list[", "dict[str, "):
            assert member in JsonValue, f"{member} missing from the JsonValue union"


class TestSemolinaMissingDependencyError:
    """DTO-05: the error every optional-dependency guard raises when the extra is absent."""

    def test_importable_from_the_package_root(self) -> None:
        """``from semolina import SemolinaMissingDependencyError`` succeeds."""
        from semolina import SemolinaMissingDependencyError

        assert SemolinaMissingDependencyError is not None

    def test_is_exported_in_all(self) -> None:
        """
        The name is in ``semolina.__all__``, so users may catch it by name.

        This is the error a user meets first when they call ``fetch_polars()`` on a base
        install, so ``except SemolinaMissingDependencyError`` has to be a supported
        spelling rather than an internal one.
        """
        assert "SemolinaMissingDependencyError" in semolina.__all__


class TestSemolinaSchemaMismatchError:
    """DTO-01: the error ``.into(DTO)`` raises when the result schema cannot fill the DTO."""

    def test_importable_from_the_package_root(self) -> None:
        """``from semolina import SemolinaSchemaMismatchError`` succeeds."""
        from semolina import SemolinaSchemaMismatchError

        assert SemolinaSchemaMismatchError is not None

    def test_is_exported_in_all(self) -> None:
        """The name is in ``semolina.__all__``, so it is a supported public name."""
        assert "SemolinaSchemaMismatchError" in semolina.__all__
