"""
Intermediate representation dataclasses for reverse codegen introspection.

Defines the frozen dataclasses that form the contract between warehouse
introspection engines and the Python code renderer.
"""

from __future__ import annotations

import functools
import keyword
import re
import unicodedata
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

PLACEHOLDER_FIELD_NAME = "column"
"""The field name given to a column whose name holds no letter or digit, such as ``?``."""


def class_name_for(view_name: str) -> str:
    """
    Derive a PascalCase Python class name from a warehouse view name.

    Takes the last segment of a qualified name, drops any identifier quotes, and joins the
    runs of letters and digits (any script, so ``café_sales`` is ``CaféSales``), each
    capitalized. A name that would start with a digit, has no letters or digits at all, or is
    a Python keyword (``none`` capitalizes to ``None``) is prefixed with ``View``.

    Args:
        view_name: The view name as given to ``introspect()``, e.g. ``"sales_view"``,
            ``"analytics.sales_view"`` or ``'"Order Book"'``.

    Returns:
        A valid Python identifier, e.g. ``"SalesView"`` or ``"OrderBook"``.
    """
    segment = view_name.rsplit(".", 1)[-1].strip('"`')
    name = "".join(word.capitalize() for word in re.split(r"[\W_]+", segment))
    # \w admits a few characters no identifier may hold (superscript digits, say).
    name = "".join(char for char in name if f"A{char}".isidentifier())
    if not name[:1].isalpha() or keyword.iskeyword(name):
        return f"View{name}"
    return name


@functools.cache
def _unusable_field_names() -> frozenset[str]:
    """
    Return the valid identifiers a generated field still may not take.

    These are the names the query builder reserves and every attribute the model base class
    defines or declares, so a generated field can neither be refused by
    :class:`~semolina.models.SemanticView` nor shadow one of its methods. Built lazily
    because :mod:`semolina.models` imports far more than this module needs at import time.

    Returns:
        The reserved builder names plus the base class's own attribute names.
    """
    from semolina.fields import RESERVED_FIELD_NAMES
    from semolina.models import SemanticView

    return RESERVED_FIELD_NAMES | set(dir(SemanticView)) | set(SemanticView.__annotations__)


def _python_identifier(name: str) -> str:
    """
    Apply the per-name half of :func:`python_field_names`, without collision handling.

    Args:
        name: One column name, already folded the way its engine folds it.

    Returns:
        A valid, usable field name; not necessarily unique within its view.
    """
    # Python reads identifiers in NFKC form, so `ﬁeld` would be declared as `field`.
    # Normalizing first keeps the name we compute and the name Python binds the same.
    text = unicodedata.normalize("NFKC", name)
    text = "".join(char if f"_{char}".isidentifier() else "_" for char in text)
    if not text.strip("_"):
        return PLACEHOLDER_FIELD_NAME
    # Two leading underscores would be name-mangled inside the class body (or name a dunder).
    if text.startswith("__"):
        text = "_" + text.lstrip("_")
    # Only a character that cannot start an identifier is left to fix: a digit, usually.
    if not text.isidentifier():
        text = f"_{text}"
    if keyword.iskeyword(text) or keyword.issoftkeyword(text) or text in _unusable_field_names():
        text = f"{text}_"
    return text


def python_field_names(names: Sequence[str]) -> list[str]:
    """
    Turn a view's column names into valid, unique Python field names.

    This is the one rule every backend's introspection uses to name generated fields.
    Names are not lower-cased here: each engine folds its own column names first, the way
    its warehouse folds unquoted identifiers, and passes the folded names in.

    The rule, applied to each name:

    1. The name is NFKC-normalized (Python reads identifiers in that form), then every
       character that cannot appear in a Python identifier becomes ``_``:
       ``order date`` is ``order_date`` and ``what?`` is ``what_``.
    2. A name left with no letter or digit (``?``, ``_`` or the empty string) becomes
       ``column``. A lone ``_`` is not used: it is a soft keyword, which a field may not be.
    3. Two or more leading underscores shrink to one, so the name is not mangled inside the
       class body: ``__secret`` is ``_secret``.
    4. A name that would start with a character an identifier cannot start with, a digit
       usually, takes a leading ``_``: ``1st`` is ``_1st``.
    5. A keyword, a soft keyword (``match``, ``case``, ``type``), a name the query builder
       reserves (``query``, ``keys``) or an attribute of
       :class:`~semolina.models.SemanticView` (``_fields``) takes a trailing ``_``:
       ``class`` is ``class_``.

    Then collisions are settled. A name that the rule above leaves unchanged keeps it. Every
    other name, in column order, takes the first of ``base``, ``base_2``, ``base_3``, ...
    that no other field holds, where a trailing ``_`` from step 5 is dropped before the
    number is added (``class_`` then ``class_2``). The same input always gives the same
    output.

    The caller is responsible for keeping the original column reachable: a field whose
    name changed needs ``source=`` set to the exact column name, which
    :func:`with_python_field_names` does.

    Args:
        names: Column names in the order the warehouse reports them, each already folded
            by its engine.

    Returns:
        One field name per input name, in the same order.

    Example:
        .. code-block:: python

            from semolina.codegen.introspector import python_field_names

            python_field_names(["what?", "order date", "class", "1st", "?", "a b", "a_b"])
            # ['what_', 'order_date', 'class_', '_1st', 'column', 'a_b_2', 'a_b']
    """
    bases = [_python_identifier(name) for name in names]
    result: list[str | None] = [None] * len(names)
    taken: set[str] = set()

    # A name that is already valid keeps it, so a renamed column never displaces it.
    for index, (name, base) in enumerate(zip(names, bases, strict=True)):
        if base == name and base not in taken:
            result[index] = base
            taken.add(base)

    for index, base in enumerate(bases):
        if result[index] is not None:
            continue
        candidate = base
        stem = base.rstrip("_")
        number = 2
        while candidate in taken:
            candidate = f"{stem}_{number}"
            number += 1
        result[index] = candidate
        taken.add(candidate)

    return [name for name in result if name is not None]


@dataclass(frozen=True)
class IntrospectedField:
    """
    Intermediate representation of a single field from an introspected semantic view.

    Produced by warehouse introspection engines and consumed by the Python code
    renderer to generate Metric, Dimension, or Fact field declarations.

    Attributes:
        name: Python attribute name for the field (e.g., 'revenue', 'country'): the
            column name folded by its engine (lower-cased for Snowflake and Databricks),
            then made a valid, unique identifier by :func:`python_field_names`.
        field_type: Semantic role of the field: 'metric', 'dimension', or 'fact'.
        data_type: Python annotation string (e.g., 'int', 'str', 'datetime.date'),
            or None if the SQL type has no clean Python equivalent (triggers a
            TODO comment in the generated output).
        description: Human-readable description of the field. Defaults to empty
            string if the warehouse provides no description metadata.
        source_name: Original warehouse column name when ``name`` does not lead back
            to it. Set when the column was created with a quoted identifier (e.g.,
            ``"order_id"`` in Snowflake, stored as lowercase), and whenever
            :func:`python_field_names` had to change the name (``what?`` becomes
            ``what_``). None for standard columns that round-trip correctly through
            normalize_identifier.
        raw_type: The warehouse's own spelling of the column type (e.g.
            ``'DECIMAL(38,2)'``, ``'{"type": "FIXED", "scale": 2}'``), carried
            so the renderer can preserve it as a comment for annotations that
            do not name it. None means the engine supplied no raw type, and the
            renderer then emits no comment rather than guessing one.
    """

    name: str
    field_type: Literal["metric", "dimension", "fact"]
    data_type: str | None
    description: str = ""
    source_name: str | None = None
    raw_type: str | None = None


@dataclass(frozen=True)
class IntrospectedView:
    """
    Intermediate representation of a semantic view returned by engine introspection.

    Produced by Engine.introspect() and consumed by the Python code renderer to
    generate a complete SemanticView subclass.

    Attributes:
        view_name: Warehouse identifier for the view (e.g., 'sales_view'). Used
            as the ``view=`` parameter in the generated SemanticView subclass.
        class_name: Python class name to use in the generated code (e.g., 'Sales').
            Derived from view_name by the introspection layer (snake_case → PascalCase).
        fields: All fields discovered in the view, in the order returned by the
            warehouse API. Includes metrics, dimensions, and facts.
    """

    view_name: str
    class_name: str
    fields: list[IntrospectedField] = field(default_factory=list)


def with_python_field_names(
    fields: Sequence[IntrospectedField], columns: Sequence[str]
) -> list[IntrospectedField]:
    """
    Rename fields by :func:`python_field_names`, keeping each renamed field's column.

    Every engine's ``introspect()`` passes its fields through here before building the
    :class:`IntrospectedView`, so ``semolina codegen`` and ``semolina codegen --check`` see
    the same names whatever the backend. A field whose name is unchanged is returned as it
    came, ``source_name`` included. A renamed one gets ``source_name`` set to its exact
    column, so the generated ``source=`` makes queries hit that column.

    Args:
        fields: The view's fields, named by their folded column names.
        columns: Each field's column exactly as the warehouse spells it, in the same order.

    Returns:
        The fields, with valid and unique names.

    Raises:
        ValueError: If ``fields`` and ``columns`` differ in length.
    """
    if len(fields) != len(columns):
        raise ValueError(f"Got {len(fields)} fields but {len(columns)} column names.")
    names = python_field_names([f.name for f in fields])
    return [
        f if name == f.name else replace(f, name=name, source_name=column)
        for f, name, column in zip(fields, names, columns, strict=True)
    ]
