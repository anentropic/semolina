"""
R: matching rules, orthogonal to how the file is read. Throwaway prototype.

Four cases in the corpus are not about reading at all. They are about pairing what the file
declares with what the warehouse has:

- M4: a view is matched by exact string. Here, DuckDB-style: quotes stripped, case folded,
  the default ``main`` schema dropped. (The real fix would ask the engine to resolve both.)
- M9: two classes for one view. Here, every class for the view is checked.
- M5: fields are matched by attribute name. Here, a committed field whose resolved column
  (``source`` or its folded name) is a warehouse field's column is matched to that field.
- D4: DTO classes are matched by name. Here, a missing class is looked for by the
  provenance docstring the renderer writes (``Result DTO for <origin> ...``).
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Any

import typer


def norm_view(name: str) -> str:
    parts = [p.strip('"').lower() for p in name.split(".")]
    if len(parts) == 2 and parts[0] == "main":
        parts = parts[1:]
    return ".".join(parts)


def install() -> None:
    # `semolina.cli` re-exports the `codegen` command function under the module's name, so
    # `import semolina.cli.codegen as cli` would bind the function. Ask for the module.
    cli = importlib.import_module("semolina.cli.codegen")
    dto_cli = importlib.import_module("semolina.cli.dto_codegen")
    import semolina.codegen.annotation_check as ac
    from semolina.codegen.model_reader import CommittedModel

    original_check_view = ac.check_view

    def check_view(engine: Any, view_name: str, committed: Any) -> Any:
        if committed is not None:
            view = engine.introspect(view_name)
            norm = engine.dialect.normalize_identifier
            by_column = {(f.source_name or norm(f.name)): f.name for f in view.fields}
            names = {f.name for f in view.fields}
            fields = {}
            for key, f in committed.fields.items():
                column = f.source_name or norm(f.name)
                if key not in names and column in by_column and by_column[column] not in committed.fields:
                    key = by_column[column]
                fields[key] = f
            committed = CommittedModel(class_name=committed.class_name, view_name=committed.view_name, fields=fields)
        return original_check_view(engine, view_name, committed)

    ac.check_view = check_view

    def run_check(engine: Any, views: list[str], model: Path) -> None:
        from semolina.codegen.annotation_check import check_view as cv
        from semolina.codegen.model_reader import read_committed_model

        try:
            committed_models = read_committed_model(model)
        except ValueError as e:
            raise typer.Exit(code=1) from e
        by_view: dict[str, list[Any]] = {}
        for m in committed_models:
            by_view.setdefault(norm_view(m.view_name), []).append(m)
        drift = False
        for view_name in views:
            classes = by_view.get(norm_view(view_name)) or [None]
            for committed in classes:
                report = cv(engine, view_name, committed)
                cli._render_check_report(report)
                drift = drift or report.has_drift
        if drift:
            raise typer.Exit(code=cli.EXIT_ANNOTATION_DRIFT)

    cli._run_check = run_check

    original_dto_run_check = dto_cli._run_check

    def dto_run_check(probed: Any, target: Path) -> None:
        import semolina.codegen.dto_reader as dr

        original_read = dr.read_committed_dtos
        tree = ast.parse(Path(target).read_text(encoding="utf-8"))
        docs = {
            n.name: ast.get_docstring(n) or ""
            for n in tree.body
            if isinstance(n, ast.ClassDef)
        }
        wanted = {p.class_name: p.origin for p in probed}

        def read(path: Path) -> list[Any]:
            dtos = original_read(path)
            names = {d.class_name for d in dtos}
            out = []
            for d in dtos:
                if d.class_name not in wanted:
                    for class_name, origin in wanted.items():
                        if class_name not in names and docs.get(d.class_name, "").startswith(
                            f"{dr.DOCSTRING_PREFIX}{origin} "
                        ):
                            d = dr.CommittedDto(class_name=class_name, fields=d.fields)
                            break
                out.append(d)
            return out

        dr.read_committed_dtos = read
        try:
            original_dto_run_check(probed, target)
        finally:
            dr.read_committed_dtos = original_read

    dto_cli._run_check = dto_run_check
