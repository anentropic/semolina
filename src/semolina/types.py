"""
Public type aliases used in generated models and in hand-written ones.

Currently one: :data:`JsonValue`, the annotation ``semolina codegen`` writes for a
semi-structured column — a Snowflake ``VARIANT`` or a Databricks ``variant``. Phase 49's
DTO side mirrors it against ``pydantic.JsonValue``, which Semolina core cannot simply
re-export: core carries no pydantic dependency, and acquiring one to name a type would be a
steep price for an alias.

This module is deliberately separate from ``fields.py`` and ``models.py``, which are both
class-definition modules. Note that it does not shadow the stdlib ``types`` module for code
inside the package — Python 3 resolves ``import types`` absolutely.
"""

from __future__ import annotations

from typing import TypeAlias

JsonValue: TypeAlias = "str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]"
"""
Any value expressible in JSON, whether a scalar, null, an array, or an object.

The recursive members are what make it a description rather than a synonym for ``object``:
a nested array of objects of arrays typechecks, and a ``datetime`` does not.

Written as a string because the alias refers to itself. Semolina's floor is Python 3.11,
which predates PEP 695 ``type`` statements, and the quoted form is the one a typechecker
accepts at that version.

One consequence worth knowing: at runtime this alias *is* a ``str``, so ``Dimension[JsonValue]()``
produces a ``ForwardRef`` subscript rather than a resolved type. Nothing in Semolina resolves
it — generated models are read as text — but code introspecting ``__orig_class__`` on such a
field will find the ``ForwardRef``, not a union.

Example:
    .. code-block:: python

        from semolina import Dimension, JsonValue, SemanticView


        class EventsView(SemanticView, view="events_view"):
            payload = Dimension[JsonValue]()
"""
