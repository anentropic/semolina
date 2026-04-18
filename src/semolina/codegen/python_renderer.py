"""
Python code renderer for reverse codegen.

Converts IntrospectedView objects into formatted, importable Python source code
suitable for use as Semolina SemanticView model classes.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader

if TYPE_CHECKING:
    from semolina.codegen.introspector import IntrospectedView

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DATETIME_TYPES = frozenset({"datetime.date", "datetime.datetime", "datetime.time"})


@dataclass
class _FieldContext:
    """
    Intermediate rendering context for a single field.

    Attributes:
        name: Python attribute name for the field.
        field_class: Semolina class name: 'Metric', 'Fact', or 'Dimension'.
        docstring: Field description text (empty string if none).
        todo_comment: TODO comment text (empty string if not a TODO type).
        data_type: Python type string for the Generic subscript (e.g., 'int',
            'str', 'datetime.date', 'Any'). Never empty.
        source_name: Original warehouse column name when it differs from the
            Pythonic field name. Set to emit ``source="..."`` in the generated
            field constructor. None when not needed.
    """

    name: str
    field_class: str
    docstring: str
    todo_comment: str
    data_type: str
    source_name: str | None


@dataclass
class _ModelContext:
    """
    Intermediate rendering context for a single view.

    Attributes:
        class_name: PascalCase Python class name.
        view_name: Original schema-qualified warehouse view name.
        fields: Ordered list of field rendering contexts.
    """

    class_name: str
    view_name: str
    fields: list[_FieldContext]


def _field_class_for(field_type: str) -> str:
    """
    Return the Semolina class name for a given field type string.

    Args:
        field_type: One of 'metric', 'fact', or 'dimension'.

    Returns:
        Semolina class name: 'Metric', 'Fact', or 'Dimension'.
    """
    if field_type == "metric":
        return "Metric"
    if field_type == "fact":
        return "Fact"
    return "Dimension"


def _build_model_context(view: IntrospectedView) -> _ModelContext:
    """
    Convert an IntrospectedView into a _ModelContext ready for Jinja2 rendering.

    Args:
        view: Warehouse introspection result.

    Returns:
        Rendering context with resolved field classes, docstrings, TODO comments,
        data_type strings, and source_name values.
    """
    fields: list[_FieldContext] = []
    for f in view.fields:
        todo_comment = ""
        if f.data_type is not None and f.data_type.startswith("TODO:"):
            todo_comment = f.data_type

        # Map IntrospectedField.data_type to Python type string for Generic subscript.
        # None data_type (unmapped warehouse type) → "Any" so generated code is valid.
        if f.data_type is None or f.data_type.startswith("TODO:"):
            data_type_str = "Any"
        else:
            data_type_str = f.data_type

        fields.append(
            _FieldContext(
                name=f.name,
                field_class=_field_class_for(f.field_type),
                docstring=f.description,
                todo_comment=todo_comment,
                data_type=data_type_str,
                source_name=f.source_name,
            )
        )
    return _ModelContext(
        class_name=view.class_name,
        view_name=view.view_name,
        fields=fields,
    )


def render_views(views: list[IntrospectedView]) -> str:
    """
    Render a list of IntrospectedView objects into a single Python source string.

    Emits a shared imports section at the top, followed by one class definition
    per view. If any field across all views uses a datetime type (datetime.date,
    datetime.datetime, or datetime.time), an ``import datetime`` line is included
    after the semolina import.

    The returned source string is *not* passed through ruff. Call
    :func:`render_and_format` if you want automatic formatting.

    Args:
        views: List of views to render into Python classes.

    Returns:
        Raw Python source string (not yet formatted by ruff).

    Example:
        .. code-block:: python

            from semolina.codegen.introspector import (
                IntrospectedField,
                IntrospectedView,
            )
            from semolina.codegen.python_renderer import render_views

            view = IntrospectedView(
                view_name="sales_view",
                class_name="SalesView",
                fields=[
                    IntrospectedField(
                        name="revenue",
                        field_type="metric",
                        data_type="int",
                    )
                ],
            )
            source = render_views([view])
            # 'from semolina import SemanticView, Metric, Dimension, Fact' in source
    """
    # Determine whether any field requires datetime or Any imports
    needs_datetime = any(f.data_type in _DATETIME_TYPES for view in views for f in view.fields)
    # needs_any: True when any field has no clean Python type mapping (data_type is None
    # or starts with "TODO:" — both map to "Any" in the template)
    needs_any = any(
        f.data_type is None or f.data_type.startswith("TODO:")
        for view in views
        for f in view.fields
    )

    models = [_build_model_context(v) for v in views]

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,
    )
    template = env.get_template("python_model.py.jinja2")
    return template.render(  # type: ignore[no-any-return]
        models=models,
        needs_datetime=needs_datetime,
        needs_any=needs_any,
    )


def format_with_ruff(source: str) -> str:
    """
    Format Python source using ruff via uv.

    Runs ``uv run ruff format`` followed by ``uv run ruff check --fix --select I``.
    Falls back gracefully: format failure returns original source; isort failure
    returns formatted-but-unsorted source.

    Args:
        source: Python source string to format.

    Returns:
        Formatted and import-sorted Python source if both passes succeed.
        Falls back to formatted source if isort pass fails, or original source
        if format pass fails.
    """
    try:
        format_result = subprocess.run(
            ["uv", "run", "ruff", "format", "--stdin-filename", "models.py", "-"],
            input=source,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return source

    if format_result.returncode != 0:
        return source

    formatted = format_result.stdout

    try:
        isort_result = subprocess.run(
            [
                "uv",
                "run",
                "ruff",
                "check",
                "--fix",
                "--select",
                "I",
                "--stdin-filename",
                "models.py",
                "-",
            ],
            input=formatted,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return formatted

    if isort_result.returncode != 0:
        return formatted

    return isort_result.stdout


def render_and_format(views: list[IntrospectedView]) -> str:
    """
    Render views to Python source and format with ruff.

    Convenience wrapper that calls :func:`render_views` followed by
    :func:`format_with_ruff`. This is what the CLI calls.

    Args:
        views: List of views to render into Python classes.

    Returns:
        Formatted Python source string. Falls back to unformatted source if
        ruff is unavailable or exits non-zero.

    Example:
        .. code-block:: python

            from semolina.codegen.introspector import (
                IntrospectedField,
                IntrospectedView,
            )
            from semolina.codegen.python_renderer import (
                render_and_format,
            )

            view = IntrospectedView(
                view_name="sales_view",
                class_name="SalesView",
                fields=[
                    IntrospectedField(
                        name="revenue",
                        field_type="metric",
                        data_type="int",
                    )
                ],
            )
            source = render_and_format([view])
    """
    return format_with_ruff(render_views(views))
