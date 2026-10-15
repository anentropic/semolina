"""
Alternative G with astroid: read committed models without importing them. Throwaway.

astroid builds a tree for the file and for any module it needs to follow (found on
``sys.path``; the working directory is appended for the duration of a read, never
prepended, like ``codegen-dto``). Base classes come from ``ClassDef.mro()``, ``view=`` from
inference, and annotation names from scope lookup, then B's canonical form.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

import astroid
import common
from astroid import nodes
from semolina.codegen.model_reader import CommittedField, CommittedModel

WARNINGS: list[str] = []


def warn(message: str) -> None:
    WARNINGS.append(message)
    print(f"Warning: {message}", file=sys.stderr)


def _resolver(scope: Any) -> common.Resolver:
    def resolve(name: str) -> str | None:
        if name == "None":
            return "None"
        frame, assignments = scope.lookup(name)
        if not assignments:
            return None
        node = assignments[0]
        if isinstance(node, nodes.ImportFrom):
            return f"{node.modname}.{node.real_name(name)}"
        if isinstance(node, nodes.Import):
            return node.real_name(name)
        if frame.qname() == "builtins":
            return f"builtins.{name}"
        return f"{frame.qname()}.{name}"

    return resolve


def _field(cls: Any, statement: Any) -> CommittedField | None:
    if isinstance(statement, nodes.Assign) and len(statement.targets) == 1:
        target, value = statement.targets[0], statement.value
    elif isinstance(statement, nodes.AnnAssign) and statement.value is not None:
        target, value = statement.target, statement.value
    else:
        return None
    if not isinstance(target, nodes.AssignName) or not isinstance(value, nodes.Call):
        return None
    tree = ast.parse(value.as_string(), mode="eval").body
    assert isinstance(tree, ast.Call)
    func = tree.func
    callee, slice_ = (func.value, func.slice) if isinstance(func, ast.Subscript) else (func, None)
    resolve = _resolver(cls)
    qual = common.qualname(callee, resolve)
    field_class = common.FIELD_QUALNAMES.get(qual or "")
    if field_class is None:
        if isinstance(func, ast.Subscript):
            warn(f"{cls.name}.{target.name}: {value.as_string()} looks like a field and was not read")
        return None
    annotation = "Any" if slice_ is None else common.normalise(ast.unparse(slice_), resolve)
    source = next(
        (
            k.value.value
            for k in tree.keywords
            if k.arg == "source" and isinstance(k.value, ast.Constant) and isinstance(k.value.value, str)
        ),
        None,
    )
    return CommittedField(name=target.name, field_class=field_class, annotation=annotation, source_name=source)


def read_committed_model(path: Path) -> list[CommittedModel]:
    path = Path(path).resolve()
    cwd = str(Path.cwd())
    name = common.module_name_for(path, Path.cwd()) or path.stem
    added = cwd not in sys.path
    if added:
        sys.path.append(cwd)
    try:
        astroid.MANAGER.clear_cache()
        module = astroid.MANAGER.ast_from_file(str(path), modname=name, source=True)
        models: list[CommittedModel] = []
        for cls in module.body:
            if not isinstance(cls, nodes.ClassDef):
                continue
            view_kw = next((k for k in (cls.keywords or []) if k.arg == "view"), None)
            if view_kw is None:
                continue
            try:
                inferred = next(view_kw.value.infer())
                view = inferred.value if isinstance(inferred, nodes.Const) else None
            except astroid.InferenceError:
                view = None
            if not isinstance(view, str):
                warn(f"{cls.name}: view={view_kw.value.as_string()} could not be read; class skipped")
                continue
            try:
                mro = cls.mro()
            except Exception as e:
                warn(f"{cls.name}: base classes not resolved ({e}); inherited fields read as absent")
                mro = [cls]
            fields: dict[str, CommittedField] = {}
            for klass in reversed(mro):
                if klass.root().name.startswith(("semolina", "builtins")):
                    continue
                for statement in klass.body:
                    f = _field(klass, statement)
                    if f is not None:
                        fields[f.name] = f
            models.append(CommittedModel(class_name=cls.name, view_name=view, fields=fields))
        return models
    except astroid.AstroidSyntaxError as e:
        raise ValueError(f"Cannot parse model file {path}: {e}") from e
    finally:
        if added:
            sys.path.remove(cwd)
