"""
Compare two annotations by the type they name, not by how they are spelled.

Both ``--check`` commands compare an annotation a committed file declares with the one
codegen would write today. Compared as strings, ``Optional[decimal.Decimal]``,
``decimal.Decimal | None``, ``None | Decimal`` (after ``from decimal import Decimal``) and
``'decimal.Decimal | None'`` are four different answers, and three of them read as drift
although every one names the same type (cases M1 and D1 in the D9 corpus).

This module reduces an annotation to a canonical form and writes that form back in
codegen's own spelling, so the existing comparison can stay a string comparison:

* every name is replaced by the fully qualified name it refers to, through a resolver the
  caller supplies (the committed file's own imports, read by
  :mod:`semolina.codegen.static_reader`);
* ``Optional[X]``, ``Union[X, Y]`` and ``X | Y`` all become one set of members, so member
  order and spelling stop mattering;
* a string annotation (a forward reference) is parsed and reduced like any other;
* ``Annotated[X, ...]`` reduces to ``X``, since the metadata says nothing about the type.

**Nothing is evaluated.** The reduction walks the annotation's syntax tree and accepts only
names, dotted names, subscripts, ``|`` and constants. Names are resolved only inside
:data:`ALLOWED_MODULES`; anything else, a user's own class for instance, makes the reduction
give up, and the caller then falls back to comparing the text as written. Giving up is
always safe: it is exactly the comparison ``--check`` made before D9.
"""

from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Callable

Resolver: TypeAlias = "Callable[[str], str | None]"
"""Map a bare name to the qualified name it refers to, or None when it cannot be resolved."""

Follower: TypeAlias = "Callable[[str], str]"
"""Map a qualified name to the path it was defined under, following re-exports."""

_Qualifier: TypeAlias = "Callable[[ast.expr], str | None]"
"""Map a name or dotted name to its qualified name, or None when it does not resolve."""

ALLOWED_MODULES = (
    "builtins",
    "typing",
    "typing_extensions",
    "collections.abc",
    "decimal",
    "datetime",
    "uuid",
    "semolina",
    "pydantic",
)
"""
Modules whose names an annotation may use and still be compared by meaning.

Every annotation either codegen command writes uses names from these modules only. A name
from anywhere else is not something codegen would have written, so there is nothing to gain
by resolving it, and comparing its text is the honest answer.
"""

_CANONICAL_NAMES = {
    # One type, several import paths.
    "semolina.JsonValue": "semolina.types.JsonValue",
    "pydantic.main.BaseModel": "pydantic.BaseModel",
    # The typing aliases of builtin generics.
    "typing.List": "builtins.list",
    "typing.Dict": "builtins.dict",
    "typing.Set": "builtins.set",
    "typing.FrozenSet": "builtins.frozenset",
    "typing.Tuple": "builtins.tuple",
    "typing.Type": "builtins.type",
}
"""Qualified names that refer to the same object as another, mapped to one spelling."""

_SPELLINGS = {"typing.Any": "Any", "semolina.types.JsonValue": "JsonValue", "None": "None"}
"""How codegen writes the names it imports bare. Builtins are written bare too."""

_GENERATED_NAMES = {
    "Any": "typing.Any",
    "JsonValue": "semolina.types.JsonValue",
    "decimal": "decimal",
    "datetime": "datetime",
    "uuid": "uuid",
    "pydantic": "pydantic",
}
"""The bare names a generated module imports, and what each refers to."""


class Unresolvable(Exception):
    """An annotation uses syntax or a name this module does not compare by meaning."""


@dataclass(frozen=True)
class _Name:
    """A plain type, by its qualified name (``builtins.int``, ``decimal.Decimal``)."""

    qualname: str


@dataclass(frozen=True)
class _Subscript:
    """A parameterized generic such as ``list[int]``."""

    base: str
    args: tuple[_Type, ...]


@dataclass(frozen=True)
class _Union:
    """A union of two or more members, in no particular order."""

    members: frozenset[_Type]


_Type: TypeAlias = "_Name | _Subscript | _Union"

_NONE = _Name("None")


def _allowed(qualname: str) -> bool:
    """
    Decide whether a qualified name belongs to one of :data:`ALLOWED_MODULES`.

    Args:
        qualname: A fully qualified name.

    Returns:
        True when the name may be compared by meaning.
    """
    return qualname == "None" or any(
        qualname == module or qualname.startswith(f"{module}.") for module in ALLOWED_MODULES
    )


def _canonical_name(qualname: str) -> str:
    """
    Map a qualified name to the one spelling this module compares.

    Args:
        qualname: A fully qualified name inside :data:`ALLOWED_MODULES`.

    Returns:
        The canonical qualified name.
    """
    if qualname.startswith("typing_extensions."):
        qualname = "typing." + qualname.removeprefix("typing_extensions.")
    return _CANONICAL_NAMES.get(qualname, qualname)


def _qualname(node: ast.expr, resolve: Resolver, follow: Follower) -> str | None:
    """
    Resolve a name or a dotted name to its qualified name.

    Args:
        node: The expression.
        resolve: Resolves the leftmost bare name.
        follow: Follows each step of a dotted name through re-exports, so
            ``compat.Decimal`` reads like ``from compat import Decimal`` does.

    Returns:
        The qualified name, or None when the node is not a (dotted) name or its head does
        not resolve.
    """
    if isinstance(node, ast.Name):
        return resolve(node.id)
    if isinstance(node, ast.Attribute):
        head = _qualname(node.value, resolve, follow)
        return None if head is None else follow(f"{head}.{node.attr}")
    return None


def _union(parts: list[_Type]) -> _Type:
    """
    Flatten union members into one union, collapsing a union of one member to that member.

    Args:
        parts: The members, any of which may itself be a union.

    Returns:
        The flattened union, or its only member.
    """
    flat: set[_Type] = set()
    for part in parts:
        if isinstance(part, _Union):
            flat |= part.members
        else:
            flat.add(part)
    if len(flat) == 1:
        return next(iter(flat))
    return _Union(frozenset(flat))


def _reduce(node: ast.expr, qualify: _Qualifier, depth: int = 0) -> _Type:
    """
    Reduce an annotation's syntax tree to its canonical form.

    Args:
        node: The annotation expression.
        qualify: Resolves names and dotted names to qualified names.
        depth: Nesting depth of forward references, bounded so a pathological string cannot
            recurse without end.

    Returns:
        The canonical form.

    Raises:
        Unresolvable: When the annotation uses syntax or a name outside what is compared.
    """
    if isinstance(node, ast.Constant):
        if node.value is None:
            return _NONE
        if isinstance(node.value, str) and depth < 5:
            try:
                parsed = ast.parse(node.value.strip(), mode="eval").body
            except SyntaxError as e:
                raise Unresolvable(node.value) from e
            return _reduce(parsed, qualify, depth + 1)
        raise Unresolvable(repr(node.value))
    if isinstance(node, (ast.Name, ast.Attribute)):
        qualname = qualify(node)
        if qualname is None or not _allowed(qualname):
            raise Unresolvable(ast.unparse(node))
        return _Name(_canonical_name(qualname))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _union([_reduce(node.left, qualify, depth), _reduce(node.right, qualify, depth)])
    if isinstance(node, ast.Subscript):
        qualname = qualify(node.value)
        if qualname is None or not _allowed(qualname):
            raise Unresolvable(ast.unparse(node))
        base = _canonical_name(qualname)
        elements = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        if not elements:
            # `Annotated[()]` and the like name no type at all.
            raise Unresolvable(ast.unparse(node))
        if base == "typing.Annotated":
            # Only the first element is a type; the rest is metadata such as Field(...).
            return _reduce(elements[0], qualify, depth)
        if base == "typing.Literal":
            # Its strings are values, not forward references.
            raise Unresolvable(ast.unparse(node))
        args = [_reduce(element, qualify, depth) for element in elements]
        if base == "typing.Optional" and len(args) == 1:
            return _union([args[0], _NONE])
        if base == "typing.Union":
            return _union(args)
        return _Subscript(base, tuple(args))
    raise Unresolvable(ast.unparse(node))


def _spelling(qualname: str) -> str:
    """
    Write a canonical qualified name the way codegen writes it.

    Args:
        qualname: A canonical qualified name.

    Returns:
        ``int`` for a builtin, ``Any`` and ``JsonValue`` bare as codegen imports them, and
        every other name qualified (``decimal.Decimal``).
    """
    if qualname in _SPELLINGS:
        return _SPELLINGS[qualname]
    return qualname.removeprefix("builtins.")


def _render(form: _Type) -> str:
    """
    Write a canonical form in codegen's spelling.

    Union members are sorted, with ``None`` last, which is where codegen writes it.

    Args:
        form: A canonical form.

    Returns:
        The annotation text.
    """
    if isinstance(form, _Name):
        return _spelling(form.qualname)
    if isinstance(form, _Subscript):
        return f"{_spelling(form.base)}[{', '.join(_render(arg) for arg in form.args)}]"
    members = sorted(_render(m) for m in form.members if m != _NONE)
    if _NONE in form.members:
        members.append("None")
    return " | ".join(members)


def _unchanged(qualname: str) -> str:
    """
    Leave a qualified name as it is, for callers with no re-exports to follow.

    Args:
        qualname: A qualified name.

    Returns:
        ``qualname``.
    """
    return qualname


def canonical_annotation(
    annotation: ast.expr | str, resolve: Resolver, follow: Follower | None = None
) -> str | None:
    """
    Write an annotation in codegen's spelling, resolving its names through ``resolve``.

    Args:
        annotation: The annotation, as a syntax tree or as source text.
        resolve: Resolves each bare name the annotation uses to the qualified name it refers
            to, or None when the name is unknown. Builtins need not be handled: a name it
            cannot resolve is looked up among the builtins before giving up.
        follow: Follows a qualified name through re-exports to where it was defined. Each
            step of a dotted name goes through it. None leaves names as resolved.

    Returns:
        The annotation as codegen would write that type, or None when it uses syntax or a
        name outside what this module compares. None means "compare the text as written".

    Example:
        .. code-block:: python

            from semolina.codegen.type_compare import canonical_annotation

            imports = {"Optional": "typing.Optional", "Decimal": "decimal.Decimal"}
            canonical_annotation("Optional[Decimal]", imports.get)
            # 'decimal.Decimal | None'
    """

    def resolve_or_builtin(name: str) -> str | None:
        resolved = resolve(name)
        if resolved is None and hasattr(builtins, name):
            return f"builtins.{name}"
        return resolved

    try:
        node = (
            ast.parse(annotation.strip(), mode="eval").body
            if isinstance(annotation, str)
            else annotation
        )
        return _render(
            _reduce(node, lambda name: _qualname(name, resolve_or_builtin, follow or _unchanged))
        )
    except (Unresolvable, SyntaxError, RecursionError):
        return None


def generated_annotation(annotation: str) -> str:
    """
    Write an annotation codegen produced in the canonical spelling it is compared in.

    A generated annotation is already in codegen's spelling, so this is normally the
    identity. Passing it through the same reduction as the committed side keeps the
    comparison symmetric, so a change to how codegen orders union members cannot read as
    drift.

    Args:
        annotation: An annotation as codegen writes it, e.g. ``'decimal.Decimal | None'``.

    Returns:
        The canonical spelling, or the annotation unchanged when it cannot be reduced.
    """
    resolved = canonical_annotation(annotation, _GENERATED_NAMES.get)
    return annotation if resolved is None else resolved


class _CommittedAnnotation(Protocol):
    """A committed field as both readers record it: as written, and resolved when possible."""

    @property
    def annotation(self) -> str: ...

    @property
    def resolved_annotation(self) -> str | None: ...


def compared_annotation(field: _CommittedAnnotation) -> str:
    """
    Pick the spelling of a committed annotation that a check compares.

    Shared by ``codegen --check`` and ``codegen-dto --check``, so the two judge the same
    annotation the same way.

    Args:
        field: The committed field, from either reader.

    Returns:
        The annotation with its names resolved, or the text as written when the reader could
        not resolve it, which is the comparison ``--check`` made before D9.
    """
    if field.resolved_annotation is not None:
        return field.resolved_annotation
    return field.annotation
