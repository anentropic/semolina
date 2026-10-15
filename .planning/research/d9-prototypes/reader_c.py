"""
Alternative C, parent side: run ``c_child.py`` in a subprocess with no credentials in its
environment, and rebuild the reader's records from its JSON. Throwaway.

The child's environment is an allowlist (``SAFE_ENV``), not a denylist: nothing the parent
holds reaches it unless it is named here. Whether that keeps credentials away from the
user's module is measured separately, by ``c_isolation.py``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SAFE_ENV = ("PATH", "LANG", "LC_ALL", "SYSTEMROOT", "TMPDIR")


def child_env() -> dict[str, str]:
    return {k: os.environ[k] for k in SAFE_ENV if k in os.environ}


def run_child(kind: str, path: Path) -> list[dict[str, Any]]:
    result = subprocess.run(
        [sys.executable, str(HERE / "c_child.py"), kind, str(Path(path).resolve())],
        stdin=subprocess.DEVNULL,
        env=child_env(),
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"Cannot import {path}: {result.stderr.strip().splitlines()[-1:]}")
    return json.loads(result.stdout)


def read_committed_model(path: Path) -> list[Any]:
    from semolina.codegen.model_reader import CommittedField, CommittedModel

    return [
        CommittedModel(
            class_name=m["class_name"],
            view_name=m["view_name"],
            fields={n: CommittedField(name=n, **f) for n, f in m["fields"].items()},
        )
        for m in run_child("models", path)
    ]


def install_dto() -> None:
    import semolina.codegen.dto_check as dc
    import semolina.codegen.dto_reader as dr

    def read_committed_dtos(path: Path) -> list[Any]:
        out = []
        for d in run_child("dtos", path):
            # Only classes the renderer wrote: the same provenance rule as the text reader.
            if not d["doc"].startswith(dr.DOCSTRING_PREFIX):
                continue
            fields = {}
            for n, f in d["fields"].items():
                alias = f["alias"]
                fields[n] = dr.CommittedDtoField(
                    name=n, annotation=f["annotation"], alias="\x00".join(alias) if isinstance(alias, list) else alias
                )
            out.append(dr.CommittedDto(class_name=d["class_name"], fields=fields))
        return out

    dr.read_committed_dtos = read_committed_dtos

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
