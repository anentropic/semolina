"""
Intermediate representation dataclasses for reverse codegen introspection.

Defines the frozen dataclasses that form the contract between warehouse
introspection engines and the Python code renderer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


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
    """

    name: str
    field_type: Literal["metric", "dimension", "fact"]
    data_type: str | None
    description: str = ""
    source_name: str | None = None


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
