"""
Alternative A: an import-aware text reader. Throwaway prototype.

Still ``ast.parse`` only, nothing imported. Over today's reader it adds:

- names resolved through the file's own import statements (``semolina.Metric``,
  ``from semolina import Metric as M``);
- annotated assignments (``x: Dimension[str] = Dimension[str]()``);
- ``view=`` read from a module-level string constant;
- base classes followed when they are defined in the same file;
- with ``follow_imports=True`` (call it A+), ``view=`` constants and base classes imported
  from another module are found by locating that module's source under the working
  directory and parsing it, still as text;
- a warning on stderr for every field-like statement or base it could not read, instead of
  skipping it silently;
- with ``normalise=True`` (A+B), each annotation is rewritten through B's canonical form.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

import common
from semolina.codegen.model_reader import CommittedField, CommittedModel

WARNINGS: list[str] = []


def warn(message: str) -> None:
    WARNINGS.append(message)
    print(f"Warning: {message}", file=sys.stderr)


@dataclass
class ModuleInfo:
    path: Path
    name: str | None
    table: dict[str, str]
    constants: dict[str, str]
    classes: dict[str, ast.ClassDef] = field(default_factory=dict)


class Reader:
    def __init__(self, *, follow_imports: bool, normalise: bool) -> None:
        self.follow_imports = follow_imports
        self.normalise = normalise
        self.roots = [Path.cwd()]
        self.cache: dict[Path, ModuleInfo] = {}

    def load(self, path: Path) -> ModuleInfo:
        path = path.resolve()
        if path in self.cache:
            return self.cache[path]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        name = common.module_name_for(path, self.roots[0])
        info = ModuleInfo(path=path, name=name, table=common.import_table(tree, name), constants={})
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                info.classes[node.name] = node
            elif (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                info.constants[node.targets[0].id] = node.value.value
        self.cache[path] = info
        return info

    def _other_module(self, qual: str) -> tuple[ModuleInfo, str] | None:
        """Split ``pkg.mod.NAME`` and load ``pkg.mod`` by text, when following imports."""
        if not self.follow_imports or "." not in qual:
            return None
        module, _, name = qual.rpartition(".")
        path = common.find_module(module, self.roots)
        if path is None:
            return None
        return self.load(path), name

    def resolve_constant(self, info: ModuleInfo, node: ast.expr) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in info.constants:
                return info.constants[node.id]
            qual = info.table.get(node.id)
            if qual is not None:
                found = self._other_module(qual)
                if found is not None:
                    other, name = found
                    return other.constants.get(name)
        return None

    def resolve_class(self, info: ModuleInfo, node: ast.expr) -> tuple[ModuleInfo, ast.ClassDef] | None:
        if isinstance(node, ast.Name) and node.id in info.classes:
            return info, info.classes[node.id]
        qual = common.qualname(node, common.table_resolver(info.table))
        if qual is None:
            return None
        found = self._other_module(qual)
        if found is None:
            return None
        other, name = found
        if name in other.classes:
            return other, other.classes[name]
        return None

    def field_of(self, info: ModuleInfo, statement: ast.stmt, cls: str) -> CommittedField | None:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target, value = statement.targets[0], statement.value
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            target, value = statement.target, statement.value
        else:
            return None
        if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
            return None
        func = value.func
        callee, slice_ = (func.value, func.slice) if isinstance(func, ast.Subscript) else (func, None)
        resolve = common.table_resolver(info.table)
        qual = common.qualname(callee, resolve)
        field_class = common.FIELD_QUALNAMES.get(qual or "")
        if field_class is None and isinstance(callee, ast.Name) and callee.id in ("Metric", "Dimension", "Fact"):
            field_class = callee.id  # today's rule, kept for files that star-import
        if field_class is None:
            if isinstance(func, ast.Subscript) or qual is None:
                warn(f"{cls}.{target.id}: {ast.unparse(value)} looks like a field and was not read")
            return None
        annotation = "Any" if slice_ is None else ast.unparse(slice_)
        if self.normalise and slice_ is not None:
            annotation = common.normalise(annotation, resolve)
        source = next(
            (
                k.value.value
                for k in value.keywords
                if k.arg == "source" and isinstance(k.value, ast.Constant) and isinstance(k.value.value, str)
            ),
            None,
        )
        return CommittedField(name=target.id, field_class=field_class, annotation=annotation, source_name=source)

    def fields_of(self, info: ModuleInfo, node: ast.ClassDef, depth: int = 0) -> dict[str, CommittedField]:
        fields: dict[str, CommittedField] = {}
        resolve = common.table_resolver(info.table)
        # Later bases first, so the first base wins, as in a simple MRO.
        for base in reversed(node.bases):
            qual = common.qualname(base, resolve)
            if qual in common.VIEW_BASE_QUALNAMES or (isinstance(base, ast.Name) and base.id == "SemanticView"):
                continue
            found = self.resolve_class(info, base) if depth < 20 else None
            if found is None:
                warn(f"{node.name}: base {ast.unparse(base)} was not followed; its fields read as absent")
                continue
            fields.update(self.fields_of(*found, depth=depth + 1))
        for statement in node.body:
            f = self.field_of(info, statement, node.name)
            if f is not None:
                fields[f.name] = f
        return fields

    def read(self, path: Path) -> list[CommittedModel]:
        try:
            info = self.load(path)
        except OSError as e:
            raise ValueError(f"Cannot read model file {path}: {e.strerror or e}") from e
        except SyntaxError as e:
            raise ValueError(f"Cannot parse model file {path} at line {e.lineno}: {e.msg}") from e
        models: list[CommittedModel] = []
        for node in info.classes.values():
            view_kw = next((k for k in node.keywords if k.arg == "view"), None)
            if view_kw is None:
                continue
            view = self.resolve_constant(info, view_kw.value)
            if view is None:
                warn(f"{node.name}: view={ast.unparse(view_kw.value)} could not be read; class skipped")
                continue
            models.append(CommittedModel(class_name=node.name, view_name=view, fields=self.fields_of(info, node)))
        return models


def make_reader(*, follow_imports: bool, normalise: bool):
    def read_committed_model(path: Path) -> list[CommittedModel]:
        return Reader(follow_imports=follow_imports, normalise=normalise).read(path)

    return read_committed_model
