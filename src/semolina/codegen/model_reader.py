"""
Read a committed generated model's declared annotations from its source text.

``semolina codegen --check`` needs one half of its comparison from a file the user points
at: the annotations a model *currently* carries. This module recovers them with
:func:`ast.parse`, which interprets the file structurally and **executes nothing**.

Importing the module would work — ``__orig_class__`` survives at runtime, so
``Metric[decimal.Decimal | None]()`` is introspectable — and it is still the wrong route.
Importing runs whatever the file's module level contains, which in CI means running code
out of a repo checkout because someone passed ``--model`` (threat T-48-19). It also
requires the file to be an importable package member, and returns a ``ForwardRef`` rather
than the source text for a ``JsonValue``-annotated field. Annotations here are recovered as
**text, exactly as written**: ``--check`` compares annotation strings, so resolving names
would only add a way to be wrong.

A miss means a field silently drops out of the drift report. The parser therefore skips only
shapes it can positively identify as *not* a generated field — a class with no ``view=``
keyword, an assignment whose call target is not one of the three field classes — and never
guesses at a shape it half-recognizes.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib

_FIELD_CLASSES = frozenset({"Metric", "Dimension", "Fact"})
"""The three field descriptors a generated model can declare."""

_UNTYPED_ANNOTATION = "Any"
"""
Annotation recorded for the documented ``Metric()`` shorthand.

``Metric()`` is legal and means ``Metric[Any]()``. Recording it as ``Any`` rather than
dropping the field keeps it in the drift report as the untyped fallback it is — which is also
exactly what the renderer emits for a warehouse type the map has no entry for.
"""


@dataclass(frozen=True)
class CommittedField:
    """
    One field declaration read out of a committed model.

    Attributes:
        name: The Python attribute name the field is assigned to.
        field_class: ``'Metric'``, ``'Dimension'`` or ``'Fact'``.
        annotation: The subscript exactly as written, e.g. ``'decimal.Decimal | None'``.
            Never resolved: an alias such as ``JsonValue`` stays the name in the source.
        source_name: The ``source="..."`` override when the declaration carries one,
            otherwise None.
    """

    name: str
    field_class: str
    annotation: str
    source_name: str | None


@dataclass(frozen=True)
class CommittedModel:
    """
    One ``SemanticView`` subclass read out of a committed model file.

    Attributes:
        class_name: The Python class name.
        view_name: The ``view=`` keyword's value — the warehouse identifier.
        fields: Field name -> declaration, in source order.
    """

    class_name: str
    view_name: str
    fields: dict[str, CommittedField]


def _view_name_of(node: ast.ClassDef) -> str | None:
    """
    Read a class's ``view=`` keyword value.

    Args:
        node: A class definition node.

    Returns:
        The view identifier, or None when the class declares no ``view=`` string — which
        means it is not a generated model and the caller should skip it.
    """
    for keyword in node.keywords:
        if (
            keyword.arg == "view"
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        ):
            return keyword.value.value
    return None


def _source_name_of(call: ast.Call) -> str | None:
    """
    Read a field declaration's ``source="..."`` override.

    Args:
        call: The field constructor call.

    Returns:
        The override, or None when the call carries no string ``source=`` keyword.
    """
    for keyword in call.keywords:
        if (
            keyword.arg == "source"
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        ):
            return keyword.value.value
    return None


def _field_of(statement: ast.stmt) -> CommittedField | None:
    """
    Read one field declaration out of a class-body statement.

    Recognizes the two shapes the renderer emits — ``x = Metric[T]()`` and
    ``x = Dimension[T](source="X")`` — plus the documented untyped shorthand ``x = Metric()``.

    Args:
        statement: A statement from a model class's body.

    Returns:
        The field, or None when the statement is not a field declaration.
    """
    if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
        return None
    target = statement.targets[0]
    if not isinstance(target, ast.Name):
        return None
    call = statement.value
    if not isinstance(call, ast.Call):
        return None

    func = call.func
    if isinstance(func, ast.Subscript) and isinstance(func.value, ast.Name):
        field_class = func.value.id
        annotation = ast.unparse(func.slice)
    elif isinstance(func, ast.Name):
        # The untyped shorthand. Legal, and it has no annotation to compare.
        field_class = func.id
        annotation = _UNTYPED_ANNOTATION
    else:
        return None

    if field_class not in _FIELD_CLASSES:
        return None

    return CommittedField(
        name=target.id,
        field_class=field_class,
        annotation=annotation,
        source_name=_source_name_of(call),
    )


def read_committed_model(path: pathlib.Path) -> list[CommittedModel]:
    """
    Read the model classes declared in a committed generated model file.

    The file is parsed, never imported: no code in it runs, and it need not be an importable
    module. Classes with no ``view=`` keyword are skipped, as are class-body statements that
    are not field declarations.

    Args:
        path: Path to the committed model file.

    Returns:
        One entry per ``SemanticView`` subclass, in source order.

    Raises:
        ValueError: If the file cannot be read, or does not parse. The message names the
            path (and, for a syntax error, the line) and nothing else, so the CLI can print
            it instead of a traceback.

    Example:
        .. code-block:: python

            import pathlib

            from semolina.codegen.model_reader import read_committed_model

            models = read_committed_model(pathlib.Path("models.py"))
            models[0].fields["revenue"].annotation
            # 'decimal.Decimal | None'
    """
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Cannot read model file {path}: {e.strerror or e}") from e

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        raise ValueError(f"Cannot parse model file {path} at line {e.lineno}: {e.msg}") from e

    models: list[CommittedModel] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        view_name = _view_name_of(node)
        if view_name is None:
            continue
        fields: dict[str, CommittedField] = {}
        for statement in node.body:
            field = _field_of(statement)
            if field is not None:
                fields[field.name] = field
        models.append(CommittedModel(class_name=node.name, view_name=view_name, fields=fields))
    return models
