"""
Shared pieces for the D9 prototypes. Throwaway code: not part of semolina.

- ``import_table``: map each module-level name to the qualified name it was imported as
  (alternative A's name resolution).
- ``canonical``: alternative B. Reduce an annotation AST to a canonical form without
  executing anything: only Name, Attribute, Subscript, BinOp(|), Tuple and Constant are
  walked, and every name must resolve inside an allowlist of modules. Unions are flattened
  into a set, so ``Optional[int]``, ``int | None`` and ``None | int`` all come out equal.
- ``render``: write a canonical form back in codegen's spelling (``decimal.Decimal | None``),
  so the unchanged string comparison in ``annotation_check`` can be reused.
"""

from __future__ import annotations

import ast
import builtins
from collections.abc import Callable
from pathlib import Path

ALLOWED_MODULES = ("builtins", "typing", "decimal", "datetime", "uuid", "semolina.types", "pydantic")
"""Names must resolve inside one of these, or the annotation is not evaluated (B)."""

FIELD_QUALNAMES = {
    f"{module}.{name}": name
    for module in ("semolina", "semolina.fields")
    for name in ("Metric", "Dimension", "Fact")
}
"""Every qualified name a field class can be reached by."""

VIEW_BASE_QUALNAMES = {"semolina.SemanticView", "semolina.models.SemanticView"}

# B alone has no import table, so it can only resolve names that need none.
B_ONLY_NAMES = {
    **{n: f"builtins.{n}" for n in ("int", "str", "float", "bool", "bytes", "list", "dict")},
    **{n: f"typing.{n}" for n in ("Optional", "Union", "Any")},
    **{m: m for m in ("typing", "decimal", "datetime", "uuid", "pydantic")},
    "None": "None",
}

Resolver = Callable[[str], "str | None"]


def import_table(tree: ast.Module, module_name: str | None = None) -> dict[str, str]:
    """Map each name a module imports to its qualified name. Relative imports use module_name."""
    table: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    table[alias.asname] = alias.name
                else:
                    head = alias.name.split(".")[0]
                    table[head] = head
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level and module_name:
                parts = module_name.split(".")[: -node.level]
                base = ".".join([*parts, base] if base else parts)
            for alias in node.names:
                table[alias.asname or alias.name] = f"{base}.{alias.name}"
    return table


def table_resolver(table: dict[str, str]) -> Resolver:
    """Resolve a bare name through an import table, then builtins."""

    def resolve(name: str) -> str | None:
        if name in table:
            return table[name]
        if name == "None":
            return "None"
        if hasattr(builtins, name):
            return f"builtins.{name}"
        return None

    return resolve


def b_only_resolver(name: str) -> str | None:
    """Resolve a bare name with no import table: B on its own."""
    return B_ONLY_NAMES.get(name)


def qualname(node: ast.expr, resolve: Resolver) -> str | None:
    """Qualified name of a Name or a dotted Attribute chain, or None."""
    if isinstance(node, ast.Name):
        return resolve(node.id)
    if isinstance(node, ast.Attribute):
        head = qualname(node.value, resolve)
        return None if head is None else f"{head}.{node.attr}"
    return None


class Unresolvable(Exception):
    """The annotation uses something outside B's grammar or allowlist."""


Canon = "str | frozenset[str] | tuple[str, tuple[object, ...]]"


def _allowed(q: str) -> bool:
    return q == "None" or any(q == m or q.startswith(m + ".") for m in ALLOWED_MODULES)


def _union(parts: list[object]) -> object:
    flat: set[object] = set()
    for part in parts:
        if isinstance(part, frozenset):
            flat |= part
        else:
            flat.add(part)
    return next(iter(flat)) if len(flat) == 1 else frozenset(flat)


def canonical(node: ast.expr, resolve: Resolver) -> object:
    """Reduce an annotation to a canonical form. Raises Unresolvable outside the allowlist."""
    if isinstance(node, ast.Constant):
        if node.value is None:
            return "None"
        if isinstance(node.value, str):
            return canonical(ast.parse(node.value, mode="eval").body, resolve)
        raise Unresolvable(repr(node.value))
    if isinstance(node, (ast.Name, ast.Attribute)):
        q = qualname(node, resolve)
        if q is None or not _allowed(q):
            raise Unresolvable(ast.unparse(node))
        return q.removeprefix("builtins.")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _union([canonical(node.left, resolve), canonical(node.right, resolve)])
    if isinstance(node, ast.Subscript):
        base = qualname(node.value, resolve)
        if base is None or not _allowed(base):
            raise Unresolvable(ast.unparse(node))
        elts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        args = [canonical(e, resolve) for e in elts]
        if base == "typing.Optional":
            return _union([args[0], "None"])
        if base == "typing.Union":
            return _union(args)
        return (base.removeprefix("builtins."), tuple(args))
    raise Unresolvable(ast.unparse(node))


def render(form: object) -> str:
    """Write a canonical form in codegen's spelling: members sorted, ``None`` last."""
    if isinstance(form, str):
        return form.removeprefix("typing.")
    if isinstance(form, frozenset):
        members = sorted((m for m in form if m != "None"), key=render)
        tail = ["None"] if "None" in form else []
        return " | ".join([render(m) for m in members] + tail)
    base, args = form  # type: ignore[misc]
    return f"{render(base)}[{', '.join(render(a) for a in args)}]"


def normalise(text: str, resolve: Resolver) -> str:
    """Canonical spelling of an annotation string, or the string itself when B cannot reach it."""
    try:
        return render(canonical(ast.parse(text, mode="eval").body, resolve))
    except (Unresolvable, SyntaxError):
        return text


def module_name_for(path: Path, root: Path) -> str | None:
    """Dotted module name for a file under root, or None."""
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return ".".join(rel.with_suffix("").parts)


def find_module(dotted: str, roots: list[Path]) -> Path | None:
    """Locate a module's source file by text under the given roots (no import)."""
    rel = Path(*dotted.split("."))
    for root in roots:
        for candidate in (root / rel.with_suffix(".py"), root / rel / "__init__.py"):
            if candidate.is_file():
                return candidate
    return None
