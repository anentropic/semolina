"""
Read the DTO classes declared in a committed generated DTO module.

The counterpart of :mod:`semolina.codegen.model_reader`, which reads committed
``SemanticView`` subclasses. This one reads the ``pydantic.BaseModel`` subclasses
:mod:`semolina.codegen.dto_renderer` emits, so ``semolina codegen-dto --check`` can compare
a committed file against what the warehouse would produce today.

**The file is parsed, never imported.** That is the same guarantee ``model_reader`` gives
and it matters more here, not less: the committed DTO module is the *output* of codegen,
so a ``--check`` run in CI reads a file that may have been edited, may not import cleanly,
and may sit outside any package. Parsing it costs nothing and runs none of it. It also
means a check needs no ``arrowmodel`` install and no pydantic import.

What counts as a generated DTO class is deliberately narrow: a class whose docstring is the
renderer's provenance line (``Result DTO for ...``), or whose body declares at least one
``name: annotation = pydantic.Field(validation_alias="...")``. A reader that matched on the
base class alone would have to resolve ``pydantic.BaseModel`` through whatever aliasing the
file uses, and a file the user has edited is exactly where that assumption breaks. Keying on
the shapes the renderer emits keeps hand-written Pydantic models that happen to share the
module out of the report.

The docstring became necessary in phase 53. Every backend now names a result column after
its field, so the renderer omits an alias equal to the field name (ALIAS-03) and a freshly
generated class usually carries none -- each field is a bare ``name: annotation``, which
binds its own name. The alias rule stays for classes generated before that, and for any
column still spelled differently from its field.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib

ALIAS_KEYWORD = "validation_alias"
"""
The ``pydantic.Field`` keyword the renderer writes a result-column name into.

One plain-string alias per field, never the multi-alias form -- see
:mod:`semolina.codegen.dto_renderer` for why. A field declared with anything else is not one
this reader recognizes.
"""


DOCSTRING_PREFIX = "Result DTO for "
"""
How every class docstring the renderer writes begins, and how this reader knows its own.

The renderer builds its class docstrings from this constant rather than from a copy, so the
two cannot drift apart.
"""


@dataclass(frozen=True)
class CommittedDtoField:
    """
    One field declaration read out of a committed DTO class.

    Attributes:
        name: The Python attribute name.
        annotation: The annotation exactly as written, e.g. ``'decimal.Decimal | None'``.
            Never resolved: an import alias stays the name in the source, the same rule
            :class:`~semolina.codegen.model_reader.CommittedField` follows.
        alias: The result column the field binds to: its ``validation_alias`` string, or
            the field's own name for a bare annotation.
    """

    name: str
    annotation: str
    alias: str


@dataclass(frozen=True)
class CommittedDto:
    """
    One generated DTO class read out of a committed module.

    Attributes:
        class_name: The Python class name, which is what a check matches against the
            class codegen would generate for a given query.
        fields: Field name -> declaration, in source order.
    """

    class_name: str
    fields: dict[str, CommittedDtoField]


def _alias_of(call: ast.Call) -> str | None:
    """
    Read a field's ``validation_alias="..."`` argument.

    Args:
        call: The ``pydantic.Field(...)`` call.

    Returns:
        The alias, or None when the call carries no plain-string ``validation_alias``.
        ``None`` for the multi-alias form as well, which the renderer never emits and
        Semolina's own ``.into()`` pre-check declines to judge.
    """
    for keyword in call.keywords:
        if (
            keyword.arg == ALIAS_KEYWORD
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        ):
            return keyword.value.value
    return None


def _bound_name_of(call: ast.Call, name: str) -> str | None:
    """
    Read the result column a field declared with a ``pydantic.Field(...)`` call binds.

    Args:
        call: The call assigned to the field.
        name: The field's name.

    Returns:
        The plain-string ``validation_alias``, else a plain-string ``alias``, else the field's
        own name. None when the call gives the field a default (positional other than
        ``...``, ``default=`` or ``default_factory=``) and no ``validation_alias``: codegen
        never emits that, so it is a hand-added field with no result column behind it. None
        for the multi-alias form too.
    """
    if any(keyword.arg == ALIAS_KEYWORD for keyword in call.keywords):
        return _alias_of(call)
    # A positional Ellipsis is pydantic's "required" marker, not a default.
    positional_default = any(
        not (isinstance(arg, ast.Constant) and arg.value is Ellipsis) for arg in call.args
    )
    if positional_default or any(
        keyword.arg in ("default", "default_factory") for keyword in call.keywords
    ):
        return None
    for keyword in call.keywords:
        if (
            keyword.arg == "alias"
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        ):
            return keyword.value.value
    return name


def _is_class_var(annotation: ast.expr) -> bool:
    """
    Decide whether an annotation is ``ClassVar`` (bare, subscripted, or ``typing.``-qualified).

    Args:
        annotation: The annotation expression.

    Returns:
        True for a class variable, which pydantic never makes a field.
    """
    node = annotation.value if isinstance(annotation, ast.Subscript) else annotation
    return (isinstance(node, ast.Name) and node.id == "ClassVar") or (
        isinstance(node, ast.Attribute) and node.attr == "ClassVar"
    )


def _field_of(statement: ast.stmt) -> CommittedDtoField | None:
    """
    Read one field declaration out of a DTO class body.

    Recognizes the two shapes the renderer emits: ``name: annotation``, which binds the
    field's own name, and ``name: annotation = pydantic.Field(validation_alias="COLUMN")``.
    The call is matched by its *keyword* rather than by the callee's spelling, so
    ``pydantic.Field``, ``Field`` and any other import alias all read the same. A user's
    edit that keeps the field bound is still read: a ``Field(description=...)`` added to a
    bare field binds its own name, and ``Field(alias="COLUMN")`` binds the alias.

    Args:
        statement: A statement from a class body.

    Returns:
        The field, or None when the statement is not a recognized field declaration --
        a docstring, a ``model_config``, a ``ClassVar`` or underscored name, or an annotated
        attribute given a default, whether directly or through ``Field(default=...)``.
    """
    if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
        return None
    name = statement.target.id
    # Pydantic makes neither a class variable nor an underscored name a field.
    if name.startswith("_") or _is_class_var(statement.annotation):
        return None
    if statement.value is None:
        alias = name
    elif isinstance(statement.value, ast.Call):
        alias = _bound_name_of(statement.value, name)
        if alias is None:
            return None
    else:
        return None
    return CommittedDtoField(name=name, annotation=ast.unparse(statement.annotation), alias=alias)


def _is_generated(node: ast.ClassDef) -> bool:
    """
    Decide whether a class is one the renderer wrote, from the shapes only it emits.

    Args:
        node: The class definition.

    Returns:
        True when the class carries the renderer's provenance docstring, or declares at
        least one field through a plain-string ``validation_alias`` -- even one equal to
        the field name, which is how every DuckDB field was written before phase 53.
    """
    docstring = ast.get_docstring(node, clean=False)
    if docstring is not None and docstring.startswith(DOCSTRING_PREFIX):
        return True
    return any(
        isinstance(statement, ast.AnnAssign)
        and isinstance(statement.value, ast.Call)
        and _alias_of(statement.value) is not None
        for statement in node.body
    )


def read_committed_dtos(path: pathlib.Path) -> list[CommittedDto]:
    """
    Read the generated DTO classes declared in a committed module.

    Args:
        path: Path to the committed DTO file.

    Returns:
        One entry per recognized DTO class, in source order. Empty when the file parses
        but declares none, which the caller reports rather than treating as a match --
        an empty answer and a matching answer are not the same thing.

    Raises:
        ValueError: If the file cannot be read, or does not parse. The message names the
            path (and, for a syntax error, the line) and nothing else, so the CLI can print
            it instead of a traceback.

    Example:
        .. code-block:: python

            import pathlib

            from semolina.codegen.dto_reader import read_committed_dtos

            dtos = read_committed_dtos(pathlib.Path("myapp/dtos.py"))
            dtos[0].fields["revenue"].alias
            # 'AGG("REVENUE")'
    """
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Cannot read DTO file {path}: {e.strerror or e}") from e

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        raise ValueError(f"Cannot parse DTO file {path} at line {e.lineno}: {e.msg}") from e

    dtos: list[CommittedDto] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        fields: dict[str, CommittedDtoField] = {}
        for statement in node.body:
            field = _field_of(statement)
            if field is not None:
                fields[field.name] = field
        if fields and _is_generated(node):
            dtos.append(CommittedDto(class_name=node.name, fields=fields))
    return dtos
