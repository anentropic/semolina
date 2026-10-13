"""
Intermediate representation dataclasses for reverse codegen introspection.

Defines the frozen dataclasses that form the contract between warehouse
introspection engines and the Python code renderer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


def class_name_for(view_name: str) -> str:
    """
    Derive a PascalCase Python class name from a warehouse view name.

    Takes the last segment of a qualified name, drops any identifier quotes, and joins the
    runs of letters and digits, each capitalized. A name that would start with a digit, or
    has no letters or digits at all, is prefixed with ``View``.

    Args:
        view_name: The view name as given to ``introspect()``, e.g. ``"sales_view"``,
            ``"analytics.sales_view"`` or ``'"Order Book"'``.

    Returns:
        A valid Python identifier, e.g. ``"SalesView"`` or ``"OrderBook"``.
    """
    segment = view_name.rsplit(".", 1)[-1].strip('"`')
    name = "".join(word.capitalize() for word in re.split(r"[^0-9A-Za-z]+", segment))
    return name if name[:1].isalpha() else f"View{name}"


@dataclass(frozen=True)
class IntrospectedField:
    """
    Intermediate representation of a single field from an introspected semantic view.

    Produced by warehouse introspection engines and consumed by the Python code
    renderer to generate Metric, Dimension, or Fact field declarations.

    Attributes:
        name: Python attribute name for the field (e.g., 'revenue', 'country').
            Always lowercase (Pythonic). For Snowflake views, this is the
            warehouse column name lowercased.
        field_type: Semantic role of the field: 'metric', 'dimension', or 'fact'.
        data_type: Python annotation string (e.g., 'int', 'str', 'datetime.date'),
            or None if the SQL type has no clean Python equivalent (triggers a
            TODO comment in the generated output).
        description: Human-readable description of the field. Defaults to empty
            string if the warehouse provides no description metadata.
        source_name: Original warehouse column name when it differs from what
            ``normalize_identifier`` would produce. Set only when the column
            was created with a quoted identifier (e.g., ``"order_id"`` in
            Snowflake, stored as lowercase). None for standard columns that
            round-trip correctly through normalize_identifier.
        raw_type: The warehouse's own spelling of the column type (e.g.
            ``'DECIMAL(38,2)'``, ``'{"type": "FIXED", "scale": 2}'``), carried
            so the renderer can preserve it as a comment for annotations that
            do not name it. None means the engine supplied no raw type, and the
            renderer then emits no comment rather than guessing one.
    """

    name: str
    field_type: Literal["metric", "dimension", "fact"]
    data_type: str | None
    description: str = ""
    source_name: str | None = None
    raw_type: str | None = None


@dataclass(frozen=True)
class IntrospectedView:
    """
    Intermediate representation of a semantic view returned by engine introspection.

    Produced by Engine.introspect() and consumed by the Python code renderer to
    generate a complete SemanticView subclass.

    Attributes:
        view_name: Warehouse identifier for the view (e.g., 'sales_view'). Used
            as the ``view=`` parameter in the generated SemanticView subclass.
        class_name: Python class name to use in the generated code (e.g., 'Sales').
            Derived from view_name by the introspection layer (snake_case → PascalCase).
        fields: All fields discovered in the view, in the order returned by the
            warehouse API. Includes metrics, dimensions, and facts.
    """

    view_name: str
    class_name: str
    fields: list[IntrospectedField] = field(default_factory=list)
