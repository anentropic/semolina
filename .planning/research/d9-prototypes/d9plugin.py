"""
Pytest plugin that swaps one D9 alternative into ``--check``. Throwaway prototype.

Loaded with ``-p d9plugin`` and configured by the ``D9_ALT`` environment variable, a
``+``-separated list of parts:

- ``A``: import-aware text reader, same file only (models), ``AliasChoices`` read (DTOs)
- ``A+``: as A, also following imports into other modules under the working directory
- ``B``: compare canonical types (allowlist evaluator) instead of strings; with A or A+ the
  committed side resolves names through the file's imports, alone it uses a fixed table
- ``G``: griffe reads the committed model and resolves its names (implies B's comparison)
- ``GA``: astroid instead of griffe
- ``C``: import the committed file in a credential-free subprocess (implies B's comparison
  on the generated side)
- ``R``: matching rules: view names matched DuckDB-style, every class for a view checked,
  fields matched by resolved column, DTO classes matched by provenance docstring
- ``E``: DTO ``validate`` mode judged by what ``validate=True`` would accept (narrowing)

The patches are installed in ``pytest_configure``, before the corpus module is imported,
so its ``from ... import check_dto`` picks up the patched names too.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any

import common

PARTS = set(filter(None, os.environ.get("D9_ALT", "").split(",")))


def _install_model_compare(committed_resolver_from_file: bool) -> None:
    """B on the model side: a drifted row whose two annotations are the same type matches."""
    import semolina.codegen.annotation_check as ac

    original = ac.check_view

    def check_view(engine: Any, view_name: str, committed: Any) -> Any:
        report = original(engine, view_name, committed)
        rows = []
        for row in report.rows:
            if (
                row.status == ac.STATUS_DRIFT
                and ac.ABSENT not in (row.committed, row.probed)
                and not row.detail
            ):
                committed_text = row.committed
                if not committed_resolver_from_file:
                    committed_text = common.normalise(committed_text, common.b_only_resolver)
                if committed_text == common.normalise(row.probed, common.b_only_resolver):
                    row = ac.FieldCheckRow(**{**row.__dict__, "status": ac.STATUS_MATCH})
            rows.append(row)
        return ac.ViewCheckReport(
            view_name=report.view_name,
            rows=rows,
            has_drift=any(r.status == ac.STATUS_DRIFT for r in rows),
            probe_error=report.probe_error,
        )

    ac.check_view = check_view


def _install_dto_compare() -> None:
    """B on the DTO side: compare canonical forms inside ``_annotations_agree``."""
    import semolina.codegen.dto_check as dc

    original = dc._annotations_agree

    def agree(committed: str, generated: str) -> tuple[bool, str]:
        return original(
            common.normalise(committed, common.b_only_resolver),
            common.normalise(generated, common.b_only_resolver),
        )

    dc._annotations_agree = agree


def _install_dto_reader(*, alias_choices: bool, normalise: bool) -> None:
    """A on the DTO side: read ``AliasChoices``; with B, resolve names through imports."""
    import semolina.codegen.dto_check as dc
    import semolina.codegen.dto_reader as dr

    if alias_choices:
        original_alias_of = dr._alias_of

        def alias_of(call: ast.Call) -> str | None:
            for keyword in call.keywords:
                if keyword.arg == dr.ALIAS_KEYWORD and isinstance(keyword.value, ast.Call):
                    choices = [
                        a.value
                        for a in keyword.value.args
                        if isinstance(a, ast.Constant) and isinstance(a.value, str)
                    ]
                    if choices and len(choices) == len(keyword.value.args):
                        return "\x00".join(choices)
            return original_alias_of(call)

        dr._alias_of = alias_of

        original_check = dc.check_dto

        def check_dto(probed: Any, committed: Any, **kwargs: Any) -> Any:
            if committed is not None:
                generated = {f.name: f.alias for f in dc._build_dto_context(probed).fields}
                fields = {}
                for name, f in committed.fields.items():
                    if "\x00" in f.alias and generated.get(name) in f.alias.split("\x00"):
                        f = dr.CommittedDtoField(name=f.name, annotation=f.annotation, alias=generated[name])
                    fields[name] = f
                committed = dr.CommittedDto(class_name=committed.class_name, fields=fields)
            return original_check(probed, committed, **kwargs)

        dc.check_dto = check_dto

    if normalise:
        original_read = dr.read_committed_dtos

        def read_committed_dtos(path: Path) -> Any:
            dtos = original_read(path)
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
            resolve = common.table_resolver(common.import_table(tree))
            return [
                dr.CommittedDto(
                    class_name=d.class_name,
                    fields={
                        n: dr.CommittedDtoField(
                            name=f.name, annotation=common.normalise(f.annotation, resolve), alias=f.alias
                        )
                        for n, f in d.fields.items()
                    },
                )
                for d in dtos
            ]

        dr.read_committed_dtos = read_committed_dtos


def _install_model_reader(reader: Any) -> None:
    import semolina.codegen.model_reader as mr

    mr.read_committed_model = reader


def pytest_configure(config: Any) -> None:  # noqa: ARG001
    model_names_resolved = False
    if "A" in PARTS or "A+" in PARTS:
        import reader_a

        _install_model_reader(
            reader_a.make_reader(follow_imports="A+" in PARTS, normalise="B" in PARTS)
        )
        _install_dto_reader(alias_choices=True, normalise="B" in PARTS)
        model_names_resolved = "B" in PARTS
    if "G" in PARTS:
        import reader_griffe

        _install_model_reader(reader_griffe.read_committed_model)
        _install_dto_reader(alias_choices=False, normalise=True)
        model_names_resolved = True
    if "GA" in PARTS:
        import reader_astroid

        _install_model_reader(reader_astroid.read_committed_model)
        _install_dto_reader(alias_choices=False, normalise=True)
        model_names_resolved = True
    if "C" in PARTS:
        import reader_c

        _install_model_reader(reader_c.read_committed_model)
        reader_c.install_dto()
        model_names_resolved = True
    if "B" in PARTS or model_names_resolved:
        _install_model_compare(committed_resolver_from_file=model_names_resolved)
        _install_dto_compare()
    if "R" in PARTS:
        import matching

        matching.install()
    if "E" in PARTS:
        import validate_mode

        validate_mode.install()
