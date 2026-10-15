"""
E: judge a DTO by what ``.into(..., validate=True)`` would accept. Throwaway prototype.

Adds ``validate=True`` to ``check_dto``. In that mode a committed annotation that differs
from the generated one still matches when pydantic would accept a value of the column's
Arrow type for it, which makes deliberate narrowing (D3: ``float`` for a decimal column)
legal. The committed annotation is turned into a type through B's allowlist only, and the
probe value is synthetic: no user code and no warehouse row is involved.
"""

from __future__ import annotations

import ast
import datetime
import decimal
import typing
import uuid
from typing import Any

import pyarrow

SAMPLES = {
    pyarrow.types.is_decimal: decimal.Decimal("1.50"),
    pyarrow.types.is_integer: 1,
    pyarrow.types.is_floating: 1.5,
    pyarrow.types.is_string: "x",
    pyarrow.types.is_boolean: True,
    pyarrow.types.is_date: datetime.date(2026, 1, 1),
}

NAMESPACE = {
    "decimal": decimal,
    "datetime": datetime,
    "uuid": uuid,
    "Any": typing.Any,
    "None": None,
    "int": int,
    "str": str,
    "float": float,
    "bool": bool,
    "bytes": bytes,
}


def _type(annotation: str) -> Any:
    # Every name was already checked by B's allowlist; eval has no builtins to reach.
    ast.parse(annotation, mode="eval")
    return eval(annotation, {"__builtins__": {}}, NAMESPACE)  # noqa: S307


def install() -> None:
    import pydantic

    import semolina.codegen.dto_check as dc

    original = dc.check_dto

    def check_dto(probed: Any, committed: Any, validate: bool = False) -> Any:
        if not validate:
            return original(probed, committed)
        saved = dc._annotations_agree
        # Decide per field with the probed schema in hand.
        context = dc._build_dto_context(probed)
        schema = probed.schema
        accepted: dict[str, str] = {}
        for f in context.fields:
            declared = committed.fields.get(f.name) if committed else None
            if declared is None:
                continue
            column = schema.field(f.alias) if f.alias in schema.names else None
            sample = next((v for test, v in SAMPLES.items() if column is not None and test(column.type)), None)
            if sample is None:
                continue
            try:
                pydantic.TypeAdapter(_type(declared.annotation)).validate_python(sample)
            except Exception:  # noqa: BLE001
                continue
            accepted[declared.annotation] = f.annotation

        def agree_validated(c: str, g: str) -> tuple[bool, str]:
            if accepted.get(c) == g:
                return True, "accepted by validate=True"
            return saved(c, g)

        dc._annotations_agree = agree_validated
        try:
            return original(probed, committed)
        finally:
            dc._annotations_agree = saved

    dc.check_dto = check_dto
