"""
Alternative C, child side: import a committed file and print what it declares as JSON.

Throwaway. Run by ``reader_c`` in a subprocess with a scrubbed environment. This process
imports the user's file, so the user's module-level code runs here; the parent, which holds
the warehouse connection, never imports it.

Usage: ``python c_child.py models|dtos PATH`` with the project root as working directory.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import types
import typing
from pathlib import Path


def type_text(t: object, namespace: dict[str, object]) -> str:
    """Write a resolved type in codegen's spelling: unions sorted, ``None`` last."""
    if isinstance(t, typing.ForwardRef):
        t = eval(t.__forward_arg__, namespace)  # noqa: S307 - this process already ran the file
    if isinstance(t, str):
        t = eval(t, namespace)  # noqa: S307
    if t is None or t is type(None):
        return "None"
    if t is typing.Any:
        return "Any"
    origin = typing.get_origin(t)
    if origin in (typing.Union, types.UnionType):
        members = sorted({type_text(a, namespace) for a in typing.get_args(t)} - {"None"})
        if type(None) in typing.get_args(t):
            members.append("None")
        return " | ".join(members)
    if origin is not None:
        args = ", ".join(type_text(a, namespace) for a in typing.get_args(t))
        return f"{type_text(origin, namespace)}[{args}]"
    if isinstance(t, type):
        return t.__qualname__ if t.__module__ == "builtins" else f"{t.__module__}.{t.__qualname__}"
    return repr(t)


def load(path: Path) -> types.ModuleType:
    root = Path.cwd().resolve()
    sys.path.append(str(root))  # appended, never prepended, as codegen-dto does
    try:
        dotted = ".".join(path.resolve().relative_to(root).with_suffix("").parts)
        return importlib.import_module(dotted)
    except ValueError:
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        spec.loader.exec_module(module)
        return module


def models(module: types.ModuleType) -> list[dict[str, object]]:
    from semolina import SemanticView

    out = []
    namespace = vars(module)
    for obj in vars(module).values():
        if not (isinstance(obj, type) and issubclass(obj, SemanticView) and obj.__module__ == module.__name__):
            continue
        view = obj.__dict__.get("_view_name")
        if view is None:
            continue
        fields = {}
        for name, field in obj._fields.items():
            orig = getattr(field, "__orig_class__", None)
            annotation = "Any" if orig is None else type_text(typing.get_args(orig)[0], namespace)
            fields[name] = {
                "field_class": type(field).__name__,
                "annotation": annotation,
                "source_name": field.source,
            }
        out.append({"class_name": obj.__name__, "view_name": view, "fields": fields})
    return out


def dtos(module: types.ModuleType) -> list[dict[str, object]]:
    import pydantic

    out = []
    for obj in vars(module).values():
        if not (isinstance(obj, type) and issubclass(obj, pydantic.BaseModel) and obj.__module__ == module.__name__):
            continue
        fields = {}
        for name, info in obj.model_fields.items():
            alias = info.validation_alias
            if isinstance(alias, pydantic.AliasChoices):
                alias = [c for c in alias.choices if isinstance(c, str)]
            fields[name] = {
                "annotation": type_text(info.annotation, vars(module)),
                "alias": alias or info.alias or name,
            }
        out.append({"class_name": obj.__name__, "doc": obj.__doc__ or "", "fields": fields})
    return out


def main() -> None:
    kind, path = sys.argv[1], Path(sys.argv[2])
    module = load(path)
    print(json.dumps(models(module) if kind == "models" else dtos(module)))


if __name__ == "__main__":
    main()
