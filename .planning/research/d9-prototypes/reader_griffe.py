"""
Alternative G with griffe: read committed models without importing them. Throwaway prototype.

griffe parses the file (and any module it imports from the search paths) and resolves
names, base classes and inherited members statically. ``allow_inspection=False`` keeps it
from ever falling back to importing a module. Annotations are then reduced with B's
canonical form, resolving each name through griffe's scope rather than our own table.
"""

from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path
from typing import Any

import common
import griffe
from semolina.codegen.model_reader import CommittedField, CommittedModel

WARNINGS: list[str] = []


def warn(message: str) -> None:
    WARNINGS.append(message)
    print(f"Warning: {message}", file=sys.stderr)


def _load(path: Path) -> tuple[Any, Any]:
    """Load a file as a griffe module. Search paths: the working directory, then its folder."""
    path = path.resolve()
    cwd = Path.cwd()
    name = common.module_name_for(path, cwd)
    search = [cwd, path.parent] if name else [path.parent, cwd]
    loader = griffe.GriffeLoader(search_paths=search, allow_inspection=False)
    module = loader.load(name or path.stem)
    loader.resolve_aliases(implicit=False, external=None)
    return loader, module


def _resolver(scope: Any) -> common.Resolver:
    def resolve(name: str) -> str | None:
        try:
            return scope.resolve(name)
        except Exception:  # NameResolutionError
            if name == "None":
                return "None"
            return f"builtins.{name}" if hasattr(builtins, name) else None

    return resolve


def _literal(loader: Any, expr: Any) -> str | None:
    """A ``view=`` value: a string literal, or a name griffe resolves to a string constant."""
    if isinstance(expr, str):
        try:
            value = ast.literal_eval(expr)
        except (ValueError, SyntaxError):
            return None
        return value if isinstance(value, str) else None
    path = getattr(expr, "canonical_path", None)
    if path is None:
        return None
    try:
        target = loader.modules_collection.get_member(path)
    except Exception:
        return None
    value = getattr(target, "value", None)
    return _literal(loader, value) if isinstance(value, str) else None


def _field(name: str, member: Any) -> CommittedField | None:
    target = member.final_target if member.is_alias else member
    value = getattr(target, "value", None)
    if not isinstance(value, griffe.ExprCall):
        return None
    func = value.function
    callee, slice_ = (func.left, func.slice) if isinstance(func, griffe.ExprSubscript) else (func, None)
    qual = getattr(callee, "canonical_path", None)
    field_class = common.FIELD_QUALNAMES.get(qual or "")
    if field_class is None:
        if isinstance(func, griffe.ExprSubscript):
            warn(f"{name}: {value} looks like a field and was not read")
        return None
    annotation = "Any"
    if slice_ is not None:
        annotation = common.normalise(str(slice_), _resolver(target.parent))
    source = None
    for argument in value.arguments:
        if isinstance(argument, griffe.ExprKeyword) and argument.name == "source":
            source = _literal(None, argument.value) if isinstance(argument.value, str) else None
    return CommittedField(name=name, field_class=field_class, annotation=annotation, source_name=source)


def read_committed_model(path: Path) -> list[CommittedModel]:
    try:
        loader, module = _load(Path(path))
    except Exception as e:
        raise ValueError(f"Cannot read model file {path}: {e}") from e
    models: list[CommittedModel] = []
    for cls in module.classes.values():
        view_expr = cls.keywords.get("view")
        if view_expr is None:
            continue
        view = _literal(loader, view_expr)
        if view is None:
            warn(f"{cls.name}: view={view_expr} could not be read; class skipped")
            continue
        try:
            cls.resolved_bases  # noqa: B018 - raises when a base cannot be found
        except Exception as e:
            warn(f"{cls.name}: a base class was not found ({e}); its fields read as absent")
        fields: dict[str, CommittedField] = {}
        for name, member in cls.all_members.items():
            try:
                f = _field(name, member)
            except Exception as e:  # an alias griffe could not resolve
                warn(f"{cls.name}.{name}: not read ({type(e).__name__}: {e})")
                continue
            if f is not None:
                fields[name] = f
        models.append(CommittedModel(class_name=cls.name, view_name=view, fields=fields))
    return models
