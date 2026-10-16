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

Since D9 (2026-10-15) names resolve through :mod:`semolina.codegen.static_reader`, which
uses griffe and still imports nothing. Three things follow. Each annotation is also recorded
in codegen's spelling with its names resolved, so ``Optional[Decimal]`` after
``from decimal import Decimal`` compares equal to ``decimal.Decimal | None``. A field
inherited from a base class the user added is read as the subclass's own. And a hand-edit
to ``validation_alias=pydantic.AliasChoices(...)`` is read: the field binds each of its
choices, and the check accepts it when one of them is the column.

**No field-like statement is skipped silently** (GEN-12). In a class the reader recognises,
a ``ClassVar`` or an underscored name is skipped, because pydantic makes neither a field.
Anything else that is not read -- a field with a default, an alias the reader cannot
interpret, a field declared inside an ``if`` block, a base class it cannot find -- becomes a
warning naming the class and the statement, which the CLI prints beside the report.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Iterator

    import griffe

    from semolina.codegen.static_reader import ClassSource, StaticModule

ALIAS_KEYWORD = "validation_alias"
"""
The ``pydantic.Field`` keyword the renderer writes a result-column name into.

The renderer writes one plain-string alias per field, never the multi-alias form -- see
:mod:`semolina.codegen.dto_renderer` for why. The reader also reads a hand-edited
``AliasChoices`` of strings; any other value is warned about and the field is not read.
"""


DOCSTRING_PREFIX = "Result DTO for "
"""
How every class docstring the renderer writes begins, and how this reader knows its own.

The renderer builds its class docstrings from this constant rather than from a copy, so the
two cannot drift apart.
"""


def has_provenance(docstring: str | None, origin: str) -> bool:
    """
    Decide whether a class docstring is the provenance line codegen writes for ``origin``.

    A DTO class renamed by hand keeps the docstring the renderer wrote, which names the
    query it was generated from. That is what lets ``codegen-dto --check`` match it to the
    class codegen would generate today (case D4).

    Args:
        docstring: A cleaned class docstring, or None.
        origin: Where the query comes from, as the renderer records it.

    Returns:
        True when the docstring is the renderer's provenance line for exactly that origin.
    """
    return docstring is not None and docstring.startswith(f"{DOCSTRING_PREFIX}{origin} (")


_FIELD_QUALNAMES = frozenset({"pydantic.Field", "pydantic.fields.Field"})
"""Every qualified name ``pydantic.Field`` can be reached by."""

_ALIAS_CHOICES_QUALNAMES = frozenset({"pydantic.AliasChoices", "pydantic.aliases.AliasChoices"})
"""Every qualified name ``pydantic.AliasChoices`` can be reached by."""


@dataclass(frozen=True)
class CommittedDtoField:
    """
    One field declaration read out of a committed DTO class.

    Attributes:
        name: The Python attribute name.
        annotation: The annotation exactly as written, e.g. ``'Optional[Decimal]'``. Shown
            in the report, so a drifted row reads as the file does.
        alias: The result column the field binds to: its ``validation_alias`` string, the
            first of its ``AliasChoices``, its ``alias`` string, or the field's own name for
            a bare annotation.
        resolved_annotation: The annotation with its names resolved, in codegen's spelling
            (``'decimal.Decimal | None'``), which is what the check compares. None when it
            uses a name or syntax the comparison cannot resolve, and the text as written is
            compared instead.
        alias_choices: Every column the field binds when its ``validation_alias`` is an
            ``AliasChoices``, in order. Empty for a field with a single alias.
    """

    name: str
    annotation: str
    alias: str
    resolved_annotation: str | None = None
    alias_choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class CommittedDto:
    """
    One generated DTO class read out of a committed module.

    Attributes:
        class_name: The Python class name, which is what a check matches against the
            class codegen would generate for a given query.
        fields: Field name -> declaration: inherited fields first, then the class's own,
            each in source order.
        docstring: The class docstring, cleaned, or None. A class renamed by hand is still
            matched to its query through the provenance line it starts with.
    """

    class_name: str
    fields: dict[str, CommittedDtoField]
    docstring: str | None = None


@dataclass(frozen=True)
class CommittedDtoFile:
    """
    Everything read out of a committed DTO module.

    Attributes:
        dtos: One entry per recognized DTO class, in source order.
        warnings: One line per statement in a recognized class that might declare a field
            and was not read, or per base class that was not followed. Printed by the CLI,
            never dropped.
    """

    dtos: list[CommittedDto]
    warnings: list[str]


def _alias_of(call: ast.Call) -> str | None:
    """
    Read a field's ``validation_alias="..."`` argument, when it is a string literal.

    Args:
        call: The ``pydantic.Field(...)`` call.

    Returns:
        The alias, or None when the call carries no plain-string ``validation_alias``.
        This is the shape :func:`_is_generated` keys on: the renderer writes a literal and
        nothing else.
    """
    for keyword in call.keywords:
        if (
            keyword.arg == ALIAS_KEYWORD
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        ):
            return keyword.value.value
    return None


def _field_names(tree: ast.Module) -> frozenset[str]:
    """
    Collect the names ``pydantic.Field`` goes by in a module, by its import statements.

    The textual fallback for a ``Field`` that griffe cannot resolve, e.g. one reached
    through ``from pydantic import *``.

    Args:
        tree: The parsed module.

    Returns:
        ``Field`` plus every name it is imported as (``from pydantic import Field as F``).
    """
    names = {"Field"}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("pydantic"):
            names.update(
                alias.asname for alias in node.names if alias.name == "Field" and alias.asname
            )
    return frozenset(names)


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
    # Cleaned, so a formatter that moves the summary to its own line still matches.
    docstring = ast.get_docstring(node)
    if docstring is not None and docstring.startswith(DOCSTRING_PREFIX):
        return True
    return any(
        isinstance(statement, ast.AnnAssign)
        and isinstance(statement.value, ast.Call)
        and _alias_of(statement.value) is not None
        for statement in node.body
    )


class _NotRead(Exception):
    """A field-like statement that cannot be read; the message says why."""


def _walk_statement(statement: ast.stmt) -> Iterator[ast.AST]:
    """
    Walk a statement without descending into a ``def`` or ``class`` nested inside it.

    Args:
        statement: A statement from a class body.

    Yields:
        Each node of the statement, outside any nested function or class body.
    """
    pending: list[ast.AST] = [statement]
    while pending:
        node = pending.pop()
        yield node
        pending.extend(
            child
            for child in ast.iter_child_nodes(node)
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        )


class _DtoClassReader:
    """Reads one DTO class body's fields, recording what it cannot read."""

    def __init__(
        self,
        static: StaticModule,
        source: ClassSource,
        field_names: frozenset[str],
        warnings: list[str],
    ) -> None:
        self.static = static
        self.source = source
        self.scope: griffe.Object | griffe.Alias = source.scope
        self.field_names = field_names
        self.warnings = warnings

    def warn(self, statement: ast.stmt, reason: str) -> None:
        """
        Record a statement that was not read.

        Args:
            statement: The statement.
            reason: Why it was not read.
        """
        text = ast.unparse(statement).splitlines()[0]
        self.warnings.append(f"{self.source.label} (line {statement.lineno}): {text!r} {reason}")

    def is_field_call(self, node: ast.expr) -> bool:
        """
        Decide whether an expression is a call to ``pydantic.Field``.

        Args:
            node: The expression.

        Returns:
            True when it calls ``Field`` by any name it is imported or reached as.
        """
        if not isinstance(node, ast.Call):
            return False
        qualname = self.static.qualname(node.func, self.scope)
        if qualname in _FIELD_QUALNAMES:
            return True
        callee = node.func
        name = callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", None)
        return name in self.field_names

    def annotated_call(self, annotation: ast.expr) -> ast.Call | None:
        """
        Find the ``Field(...)`` call in an ``Annotated[T, ...]`` annotation.

        Args:
            annotation: The field's annotation.

        Returns:
            The first ``Field`` call among the metadata, or None when the annotation is not
            ``Annotated`` (bare or ``typing.``-qualified) or carries none.
        """
        if not isinstance(annotation, ast.Subscript) or not isinstance(annotation.slice, ast.Tuple):
            return None
        base = annotation.value
        base_name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", None)
        if base_name != "Annotated":
            return None
        for item in annotation.slice.elts[1:]:
            if isinstance(item, ast.Call) and self.is_field_call(item):
                return item
        return None

    def validation_alias(self, value: ast.expr) -> tuple[str, tuple[str, ...]]:
        """
        Read a ``validation_alias=`` value: a string, or an ``AliasChoices`` of strings.

        Args:
            value: The keyword's value.

        Returns:
            The primary column and, for ``AliasChoices``, every choice in order.

        Raises:
            _NotRead: For any other value, e.g. an ``AliasPath``.
        """
        alias = self.static.string_constant(value, self.scope)
        if alias is not None:
            return alias, ()
        if isinstance(value, ast.Call):
            qualname = self.static.qualname(value.func, self.scope)
            callee = value.func
            name = callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", None)
            if qualname in _ALIAS_CHOICES_QUALNAMES or (
                qualname is None and name == "AliasChoices"
            ):
                choices = [self.static.string_constant(arg, self.scope) for arg in value.args]
                strings = tuple(choice for choice in choices if choice is not None)
                if strings and len(strings) == len(value.args) and not value.keywords:
                    return strings[0], strings
        raise _NotRead(
            "was not read: its validation_alias is not a string or an AliasChoices of strings"
        )

    def bound_name(self, call: ast.Call, name: str) -> tuple[str, tuple[str, ...]]:
        """
        Read the result column a field declared with a call binds.

        Args:
            call: The call assigned to the field, or found inside ``Annotated``.
            name: The field's name.

        Returns:
            The column, and every choice when the alias is an ``AliasChoices``.

        Raises:
            _NotRead: When the call gives the field a default and no ``validation_alias``
                (codegen never emits that, so it is a hand-added field with no result column
                behind it), or carries an alias the reader cannot interpret.
        """
        for keyword in call.keywords:
            if keyword.arg == ALIAS_KEYWORD:
                return self.validation_alias(keyword.value)
        # Any other call (list(), datetime.now()) builds a default, so only Field keeps it bound.
        if not self.is_field_call(call):
            raise _NotRead("was not read: it has a default, so it binds no result column")
        # A positional Ellipsis is pydantic's "required" marker, not a default.
        positional_default = any(
            not (isinstance(arg, ast.Constant) and arg.value is Ellipsis) for arg in call.args
        )
        if positional_default or any(
            keyword.arg in ("default", "default_factory") for keyword in call.keywords
        ):
            raise _NotRead("was not read: it has a default, so it binds no result column")
        for keyword in call.keywords:
            if keyword.arg == "alias":
                alias = self.static.string_constant(keyword.value, self.scope)
                if alias is None:
                    raise _NotRead("was not read: its alias is not a string")
                return alias, ()
        return name, ()

    def read_statement(self, statement: ast.stmt) -> CommittedDtoField | None:
        """
        Read one field declaration out of a DTO class body.

        Recognizes the two shapes the renderer emits: ``name: annotation``, which binds the
        field's own name, and ``name: annotation = pydantic.Field(validation_alias="COLUMN")``.
        A ``validation_alias`` call is matched by its *keyword* rather than by the callee's
        spelling, so ``pydantic.Field``, ``Field`` and any other import alias all read the
        same. A user's edit that keeps the field bound is still read: a
        ``Field(description=...)`` added to a bare field binds its own name,
        ``Field(alias="COLUMN")`` binds the alias, ``Field`` imported under another name
        counts as ``Field``, ``AliasChoices`` binds each of its choices, and a ``Field``
        call inside ``Annotated[T, ...]`` is read as if it were assigned.

        Args:
            statement: A statement from the class body.

        Returns:
            The field, or None when the statement declares none: a docstring, a
            ``model_config``, a ``ClassVar`` or underscored name, or a statement that was
            warned about.
        """
        if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
            self.read_other(statement)
            return None
        name = statement.target.id
        # Pydantic makes neither a class variable nor an underscored name a field.
        if name.startswith("_") or _is_class_var(statement.annotation):
            return None
        value = statement.value
        call = self.annotated_call(statement.annotation) if value is None else value
        try:
            if call is None:
                alias, choices = name, ()
            elif isinstance(call, ast.Call):
                alias, choices = self.bound_name(call, name)
            else:
                raise _NotRead("was not read: it has a default, so it binds no result column")
        except _NotRead as e:
            self.warn(statement, str(e))
            return None
        return CommittedDtoField(
            name=name,
            annotation=ast.unparse(statement.annotation),
            alias=alias,
            resolved_annotation=self.resolved(statement.annotation),
            alias_choices=choices,
        )

    def resolved(self, annotation: ast.expr) -> str | None:
        """
        Write an annotation in codegen's spelling, with its names resolved.

        Args:
            annotation: The annotation.

        Returns:
            The canonical spelling, or None when it cannot be resolved.
        """
        from semolina.codegen.type_compare import canonical_annotation

        return canonical_annotation(annotation, self.static.resolver(self.scope))

    def read_other(self, statement: ast.stmt) -> None:
        """
        Warn about a statement that is not an annotated assignment but declares a field.

        Args:
            statement: A statement from the class body: an ``if`` block, an unannotated
                ``x = Field(...)``, and so on.
        """
        # A method's locals and a nested class's attributes are not this class's fields.
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        declares = any(
            isinstance(node, ast.AnnAssign)
            or (isinstance(node, ast.Call) and self.is_field_call(node))
            for node in _walk_statement(statement)
        )
        if declares:
            names = [
                ast.unparse(node.target)
                for node in _walk_statement(statement)
                if isinstance(node, ast.AnnAssign)
            ]
            what = f"declares {', '.join(names)} " if names else "declares a field "
            self.warn(
                statement,
                f"{what}in a statement the reader does not read; declare each field as "
                "`name: T` directly in the class body",
            )

    def read(self) -> dict[str, CommittedDtoField]:
        """
        Read every field the class body declares.

        Returns:
            Field name -> declaration, in source order.
        """
        fields: dict[str, CommittedDtoField] = {}
        for statement in self.source.node.body:
            field = self.read_statement(statement)
            if field is not None:
                fields[field.name] = field
        return fields


def read_committed_dto_file(path: pathlib.Path) -> CommittedDtoFile:
    """
    Read the generated DTO classes in a committed module, and everything that was not read.

    Args:
        path: Path to the committed DTO file.

    Returns:
        The recognized DTO classes in source order, and a warning for each field-like
        statement or base class in them that was not read. The class list is empty when the
        file parses but declares none, which the caller reports rather than treating as a
        match -- an empty answer and a matching answer are not the same thing.

    Raises:
        ValueError: If the file cannot be read, or does not parse. The message names the
            path (and, for a syntax error, the line) and nothing else, so the CLI can print
            it instead of a traceback.

    Example:
        .. code-block:: python

            import pathlib

            from semolina.codegen.dto_reader import read_committed_dto_file

            read = read_committed_dto_file(pathlib.Path("myapp/dtos.py"))
            read.dtos[0].fields["revenue"].alias
            # 'revenue' -- a bare field binds its own name
            read.warnings
            # []
    """
    from semolina.codegen.static_reader import ClassSource, StaticModule

    try:
        source = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Cannot read DTO file {path}: {e.strerror or e}") from e

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        raise ValueError(f"Cannot parse DTO file {path} at line {e.lineno}: {e.msg}") from e

    static = StaticModule.load(path, source, tree)
    field_names = _field_names(tree)
    dtos: list[CommittedDto] = []
    warnings: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or not _is_generated(node):
            continue
        class_warnings: list[str] = []
        top = ClassSource(node=node, scope=static.class_scope(node), label=node.name)
        fields: dict[str, CommittedDtoField] = {}
        # Bases first, so a subclass's declaration replaces its base's, as pydantic's would.
        for cls in reversed(static.inheritance_chain(top, class_warnings)):
            fields.update(_DtoClassReader(static, cls, field_names, class_warnings).read())
        if fields:
            dtos.append(
                CommittedDto(class_name=node.name, fields=fields, docstring=ast.get_docstring(node))
            )
        # Whatever `fields` holds: a class with nothing readable is exactly the one whose
        # warnings say why it reads as missing.
        warnings.extend(class_warnings)
    return CommittedDtoFile(dtos=dtos, warnings=list(dict.fromkeys(warnings)))


def read_committed_dtos(path: pathlib.Path) -> list[CommittedDto]:
    """
    Read the generated DTO classes declared in a committed module.

    The classes half of :func:`read_committed_dto_file`, for a caller that reports its
    warnings some other way or has none to report. The CLI uses
    :func:`read_committed_dto_file`, so nothing it reads is dropped without a word.

    Args:
        path: Path to the committed DTO file.

    Returns:
        One entry per recognized DTO class, in source order.

    Raises:
        ValueError: If the file cannot be read, or does not parse.

    Example:
        .. code-block:: python

            import pathlib

            from semolina.codegen.dto_reader import read_committed_dtos

            dtos = read_committed_dtos(pathlib.Path("myapp/dtos.py"))
            dtos[0].fields["revenue"].alias
            # 'revenue' -- a bare field binds its own name
    """
    return read_committed_dto_file(path).dtos
