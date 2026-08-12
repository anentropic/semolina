"""
Tests for Python code renderer.

Converts IntrospectedView objects into formatted, importable Python source.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from semolina.codegen.introspector import IntrospectedField, IntrospectedView


def test_field_class_for_unrecognized_role_raises() -> None:
    """Unrecognized role string raises rather than defaulting to Dimension."""
    from semolina.codegen.python_renderer import _field_class_for

    with pytest.raises(ValueError, match="Unrecognized field role"):
        _field_class_for("widget")


class TestRenderViews:
    """Tests for render_views() function."""

    def test_single_view_metric_field(self) -> None:
        """Single view with one metric field renders Metric[int | None]() assignment."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="revenue", field_type="metric", data_type="int"),
            ],
        )
        source = render_views([view])
        assert "revenue = Metric[int | None]()" in source
        assert "from semolina import Dimension, Fact, Metric, SemanticView" in source

    def test_single_view_dimension_field(self) -> None:
        """Single view with one dimension field renders Dimension[str]() assignment."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="country", field_type="dimension", data_type="str"),
            ],
        )
        source = render_views([view])
        assert "country = Dimension[str]()" in source

    def test_single_view_fact_field(self) -> None:
        """Single view with one fact field renders Fact[float]() assignment."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="unit_price", field_type="fact", data_type="float"),
            ],
        )
        source = render_views([view])
        assert "unit_price = Fact[float]()" in source

    def test_field_with_description_emits_docstring(self) -> None:
        """Field with description emits a docstring below the assignment."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(
                    name="revenue",
                    field_type="metric",
                    data_type="int",
                    description="Total revenue",
                ),
            ],
        )
        source = render_views([view])
        assert "revenue = Metric[int | None]()" in source
        assert '"""Total revenue"""' in source

    def test_field_without_description_no_docstring(self) -> None:
        """Field without description emits no docstring."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="revenue", field_type="metric", data_type="int"),
            ],
        )
        source = render_views([view])
        assert '"""' not in source

    def test_field_todo_data_type_emits_comment(self) -> None:
        """Field with data_type starting 'TODO:' emits a # comment and Dimension[Any]()."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(
                    name="geo",
                    field_type="dimension",
                    data_type='TODO: {"type": "GEOGRAPHY"}',
                ),
            ],
        )
        source = render_views([view])
        assert "# TODO:" in source
        assert "geo = Dimension[Any]()" in source
        # Comment must appear before the field assignment
        todo_idx = source.index("# TODO:")
        field_idx = source.index("geo = Dimension[Any]()")
        assert todo_idx < field_idx

    def test_field_todo_comment_with_newline_stays_single_line(self) -> None:
        """
        A TODO type containing a newline must not break the comment across lines.

        Warehouse type descriptors can be pretty-printed (e.g. a multi-line STRUCT
        definition). The renderer interpolates the descriptor into a ``# ...`` comment,
        so an embedded newline would push the rest onto a non-comment physical line and
        produce a SyntaxError. The comment must collapse to a single line.
        """
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(
                    name="geo",
                    field_type="dimension",
                    data_type='TODO: {\n  "type": "STRUCT"\n}',
                ),
            ],
        )
        source = render_views([view])
        # The interpolated comment must not contain a raw newline that would escape it.
        comment_line = next(line for line in source.splitlines() if line.lstrip().startswith("#"))
        assert "STRUCT" in comment_line
        # Every physical line after the imports must be a comment, an assignment,
        # a docstring, a class/decl, or blank — never an orphaned type-descriptor fragment.
        for line in source.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            assert not stripped.startswith('"type"'), f"comment leaked onto its own line: {line!r}"

    def test_none_data_type_emits_any_type(self) -> None:
        """Field with data_type=None emits FieldClass[Any]() and 'from typing import Any'."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="geo", field_type="dimension", data_type=None),
            ],
        )
        source = render_views([view])
        assert "geo = Dimension[Any]()" in source
        assert "from typing import Any" in source

    def test_source_name_set_emits_source_kwarg(self) -> None:
        """Field with source_name emits FieldClass[T](source='...')."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="orders_view",
            class_name="OrdersView",
            fields=[
                IntrospectedField(
                    name="order_id",
                    field_type="dimension",
                    data_type="str",
                    source_name="order_id",
                ),
            ],
        )
        source = render_views([view])
        assert 'order_id = Dimension[str](source="order_id")' in source

    def test_source_name_none_no_source_kwarg(self) -> None:
        """Field without source_name emits FieldClass[T]() without source= kwarg."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="orders_view",
            class_name="OrdersView",
            fields=[
                IntrospectedField(
                    name="order_id",
                    field_type="dimension",
                    data_type="str",
                    source_name=None,
                ),
            ],
        )
        source = render_views([view])
        assert "order_id = Dimension[str]()" in source
        assert "source=" not in source

    def test_datetime_date_type_imports_datetime(self) -> None:
        """Field with datetime.date data_type causes 'import datetime' to be emitted."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(
                    name="order_date", field_type="dimension", data_type="datetime.date"
                ),
            ],
        )
        source = render_views([view])
        assert "import datetime" in source

    def test_datetime_datetime_type_imports_datetime(self) -> None:
        """Field with datetime.datetime data_type causes 'import datetime' to be emitted."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(
                    name="created_at",
                    field_type="dimension",
                    data_type="datetime.datetime",
                ),
            ],
        )
        source = render_views([view])
        assert "import datetime" in source

    def test_no_datetime_fields_no_datetime_import(self) -> None:
        """No datetime fields → no 'import datetime' in output."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="revenue", field_type="metric", data_type="int"),
                IntrospectedField(name="country", field_type="dimension", data_type="str"),
            ],
        )
        source = render_views([view])
        assert "import datetime" not in source
        assert "from typing import Any" not in source

    def test_multiple_views_single_imports_section(self) -> None:
        """Multiple views produce a single shared imports section at the top."""
        from semolina.codegen.python_renderer import render_views

        views = [
            IntrospectedView(
                view_name="sales_view",
                class_name="SalesView",
                fields=[
                    IntrospectedField(name="revenue", field_type="metric", data_type="int"),
                ],
            ),
            IntrospectedView(
                view_name="orders_view",
                class_name="OrdersView",
                fields=[
                    IntrospectedField(name="order_count", field_type="metric", data_type="int"),
                ],
            ),
        ]
        source = render_views(views)
        # Only one imports line
        assert source.count("from semolina import Dimension, Fact, Metric, SemanticView") == 1
        # Both class definitions present
        assert "class SalesView(SemanticView" in source
        assert "class OrdersView(SemanticView" in source
        # Fields use typed subscripts
        assert "revenue = Metric[int | None]()" in source
        assert "order_count = Metric[int | None]()" in source

    def test_class_declaration_uses_full_view_name(self) -> None:
        """Class view= parameter uses the full original schema-qualified name."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="my_schema.sales_view",
            class_name="SalesView",
            fields=[],
        )
        source = render_views([view])
        assert 'view="my_schema.sales_view"' in source

    def test_class_declaration_format(self) -> None:
        """Class declaration uses correct SemanticView inheritance syntax."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="revenue", field_type="metric", data_type="int"),
            ],
        )
        source = render_views([view])
        assert 'class SalesView(SemanticView, view="sales_view"):' in source

    def test_imports_appear_before_classes(self) -> None:
        """The semolina import line appears before any class definition."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="revenue", field_type="metric", data_type="int"),
            ],
        )
        source = render_views([view])
        import_idx = source.index("from semolina import")
        class_idx = source.index("class SalesView")
        assert import_idx < class_idx

    def test_datetime_import_before_semolina_import(self) -> None:
        """'import datetime' appears before the semolina import line (stdlib before third-party)."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(
                    name="order_date", field_type="dimension", data_type="datetime.date"
                ),
            ],
        )
        source = render_views([view])
        semolina_idx = source.index("from semolina import")
        datetime_idx = source.index("import datetime")
        assert datetime_idx < semolina_idx

    def test_returns_string(self) -> None:
        """render_views() returns a str."""
        from semolina.codegen.python_renderer import render_views

        source = render_views([])
        assert isinstance(source, str)

    def test_empty_views_list(self) -> None:
        """Empty views list returns a string with just the imports."""
        from semolina.codegen.python_renderer import render_views

        source = render_views([])
        assert "from semolina import Dimension, Fact, Metric, SemanticView" in source

    def test_datetime_across_multiple_views(self) -> None:
        """Datetime import triggered by field in any view across all views."""
        from semolina.codegen.python_renderer import render_views

        views = [
            IntrospectedView(
                view_name="sales_view",
                class_name="SalesView",
                fields=[
                    IntrospectedField(name="revenue", field_type="metric", data_type="int"),
                ],
            ),
            IntrospectedView(
                view_name="orders_view",
                class_name="OrdersView",
                fields=[
                    IntrospectedField(
                        name="order_date",
                        field_type="dimension",
                        data_type="datetime.date",
                    ),
                ],
            ),
        ]
        source = render_views(views)
        assert "import datetime" in source
        # Only one import datetime line
        assert source.count("import datetime") == 1


class TestMetricNullability:
    """
    Decision 2 (47-DECISIONS.md): metric annotations are uniformly ``T | None``.

    The decoration is applied in ``_build_model_context`` and nowhere else. Applying it in
    a type map or an engine would put ``| None`` into ``IntrospectedField.data_type``,
    which the artifact generator and ``--check`` both read as the mapped annotation.
    """

    def test_metric_annotation_gains_none(self) -> None:
        """A metric field renders ``Metric[T | None]()``."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="revenue", field_type="metric", data_type="int"),
            ],
        )
        source = render_views([view])
        assert "revenue = Metric[int | None]()" in source, source

    def test_dimension_annotation_gains_no_none(self) -> None:
        """A dimension field is untouched — Decision 2 defers dimension nullability."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="country", field_type="dimension", data_type="str"),
            ],
        )
        source = render_views([view])
        assert "country = Dimension[str]()" in source, source
        assert "| None" not in source, source

    def test_fact_annotation_gains_no_none(self) -> None:
        """A fact field is untouched by the metric nullability stance."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="unit_price", field_type="fact", data_type="float"),
            ],
        )
        source = render_views([view])
        assert "unit_price = Fact[float]()" in source, source
        assert "| None" not in source, source

    def test_unmapped_metric_is_any_or_none(self) -> None:
        """An unmapped metric renders ``Metric[Any | None]()`` and still imports Any."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="blob", field_type="metric", data_type=None),
                IntrospectedField(name="geo", field_type="dimension", data_type=None),
            ],
        )
        source = render_views([view])
        assert "blob = Metric[Any | None]()" in source, source
        assert "geo = Dimension[Any]()" in source, source
        assert "from typing import Any" in source, source

    def test_source_kwarg_survives_nullability(self) -> None:
        """A nullable metric with a source= kwarg keeps both."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="orders_view",
            class_name="OrdersView",
            fields=[
                IntrospectedField(
                    name="revenue",
                    field_type="metric",
                    data_type="int",
                    source_name="Revenue",
                ),
            ],
        )
        source = render_views([view])
        assert 'revenue = Metric[int | None](source="Revenue")' in source, source


class TestImportEmission:
    """
    Imports are derived from the *resolved* annotations, not from the raw introspected type.

    The predecessor computed ``needs_datetime`` by exact membership of
    ``IntrospectedField.data_type`` in a frozenset of three literal strings, evaluated
    before ``_build_model_context`` ran. Appending ``| None`` to a metric annotation would
    have silently stopped that test matching, dropping ``import datetime`` from generated
    modules for datetime-typed metrics only — a NameError at import time in the user's
    model, with most of the suite still green.
    """

    def test_nullable_datetime_metric_still_imports_datetime(self) -> None:
        """A ``datetime.datetime`` metric emits ``import datetime`` despite the ``| None``."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(
                    name="last_seen",
                    field_type="metric",
                    data_type="datetime.datetime",
                ),
            ],
        )
        source = render_views([view])
        assert "import datetime" in source, source
        assert "last_seen = Metric[datetime.datetime | None]()" in source, source

    def test_decimal_annotation_imports_decimal(self) -> None:
        """A ``decimal.Decimal`` annotation emits ``import decimal``."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(
                    name="revenue",
                    field_type="metric",
                    data_type="decimal.Decimal",
                ),
            ],
        )
        source = render_views([view])
        assert "import decimal" in source, source
        assert "revenue = Metric[decimal.Decimal | None]()" in source, source

    def test_no_decimal_fields_no_decimal_import(self) -> None:
        """No decimal-annotated field means no ``import decimal``."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="revenue", field_type="metric", data_type="int"),
            ],
        )
        source = render_views([view])
        assert "import decimal" not in source, source

    def test_stdlib_imports_are_sorted(self) -> None:
        """``import datetime`` precedes ``import decimal`` regardless of field order."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="revenue", field_type="metric", data_type="decimal.Decimal"),
                IntrospectedField(
                    name="last_seen", field_type="metric", data_type="datetime.datetime"
                ),
            ],
        )
        source = render_views([view])
        assert source.index("import datetime") < source.index("import decimal"), source

    def test_semolina_import_emitted_once_and_sorted(self) -> None:
        """Exactly one ``from semolina import`` line is emitted, with sorted names."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="revenue", field_type="metric", data_type="int"),
            ],
        )
        source = render_views([view])
        assert source.count("from semolina import") == 1, source
        assert "from semolina import Dimension, Fact, Metric, SemanticView" in source, source

    def test_render_views_is_deterministic(self) -> None:
        """Two renders of the same input return byte-identical source."""
        from semolina.codegen.python_renderer import render_views

        views = [
            IntrospectedView(
                view_name="sales_view",
                class_name="SalesView",
                fields=[
                    IntrospectedField(
                        name="revenue", field_type="metric", data_type="decimal.Decimal"
                    ),
                    IntrospectedField(
                        name="last_seen", field_type="metric", data_type="datetime.datetime"
                    ),
                    IntrospectedField(name="geo", field_type="dimension", data_type=None),
                ],
            ),
        ]
        assert render_views(views) == render_views(views)


class TestRawTypeComment:
    """
    D-03: the raw warehouse type survives into generated source once a type stops being a TODO.

    Before Phase 48 the ``TODO:`` comment was the only channel carrying a warehouse type
    into emitted code, and it is skipped for mapped types — so annotating a DuckDB
    ``DECIMAL(38,2)`` as ``decimal.Decimal`` would have thrown away the precision and scale
    the user needs in order to reason about the column. ``IntrospectedField.raw_type``
    carries it instead, and the renderer emits it for any annotation that does not name the
    warehouse type it came from.
    """

    def test_lossy_annotation_emits_raw_type_comment(self) -> None:
        """A decimal.Decimal annotation keeps its DECIMAL(38,2) origin as a comment."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(
                    name="revenue",
                    field_type="metric",
                    data_type="decimal.Decimal",
                    raw_type="DECIMAL(38,2)",
                ),
            ],
        )
        source = render_views([view])
        assert "# DECIMAL(38,2)" in source, source
        comment_idx = source.index("# DECIMAL(38,2)")
        field_idx = source.index("revenue = Metric[decimal.Decimal | None]()")
        assert comment_idx < field_idx, source

    def test_faithful_annotation_emits_no_comment(self) -> None:
        """A str annotation for a VARCHAR column already names its origin, so no comment."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(
                    name="country",
                    field_type="dimension",
                    data_type="str",
                    raw_type="VARCHAR",
                ),
            ],
        )
        source = render_views([view])
        assert "#" not in source, source

    def test_todo_comment_is_unchanged(self) -> None:
        """An unmapped field still emits the existing ``# TODO: <raw>`` text verbatim."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(
                    name="geo",
                    field_type="dimension",
                    data_type='TODO: {"type": "GEOGRAPHY"}',
                    raw_type='{"type": "GEOGRAPHY"}',
                ),
            ],
        )
        source = render_views([view])
        assert '# TODO: {"type": "GEOGRAPHY"}' in source, source
        assert source.count("#") == 1, source

    def test_raw_type_with_newline_stays_single_line(self) -> None:
        """
        A pretty-printed warehouse descriptor collapses to one physical comment line.

        Snowflake's ``data_type`` is a JSON blob and can arrive pretty-printed. A comment
        interpolating a raw newline would push the remainder onto a non-comment line and
        make the generated module a SyntaxError — or, worse, let a crafted catalogue entry
        put arbitrary text onto a fresh line of a file the user then executes (T-48-01).
        """
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(
                    name="revenue",
                    field_type="metric",
                    data_type="decimal.Decimal",
                    raw_type='{\n  "type": "FIXED",\n  "scale": 2\n}',
                ),
            ],
        )
        source = render_views([view])
        comment_lines = [line for line in source.splitlines() if line.strip().startswith("#")]
        assert len(comment_lines) == 1, source
        assert "FIXED" in comment_lines[0], source

    def test_raw_type_is_optional(self) -> None:
        """IntrospectedField still constructs with no raw_type argument."""
        field = IntrospectedField(name="revenue", field_type="metric", data_type="int")
        assert field.raw_type is None

    def test_lossy_annotation_without_raw_type_emits_no_comment(self) -> None:
        """An engine that supplies no raw_type produces no comment rather than a broken one."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(
                    name="revenue",
                    field_type="metric",
                    data_type="decimal.Decimal",
                ),
            ],
        )
        source = render_views([view])
        assert "#" not in source, source

    def test_lossy_base_type_emits_comment_for_faithful_looking_annotation(self) -> None:
        """
        A ``str``-annotated UUID column earns a comment: the annotation hides the type.

        D-03 annotates the measured value, so a DuckDB ``UUID`` is ``str``. That is
        correct and lossy at the same time, which is exactly the case the raw-type comment
        exists for.
        """
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(
                    name="order_id",
                    field_type="dimension",
                    data_type="str",
                    raw_type="UUID",
                ),
            ],
        )
        source = render_views([view])
        assert "# UUID" in source, source


class TestFormatWithRuff:
    """Tests for format_with_ruff() function."""

    def test_returns_string(self) -> None:
        """format_with_ruff() returns a string."""
        from semolina.codegen.python_renderer import format_with_ruff

        result = format_with_ruff("x = 1\n")
        assert isinstance(result, str)

    def test_valid_python_formatted(self) -> None:
        """format_with_ruff() returns formatted source for valid Python."""
        from semolina.codegen.python_renderer import format_with_ruff

        source = "x=1\n"
        result = format_with_ruff(source)
        # Either formatted or unchanged (if ruff unavailable) — both are str
        assert isinstance(result, str)

    def test_fallback_on_file_not_found(self) -> None:
        """format_with_ruff() returns source unchanged when uv/ruff is unavailable."""
        from semolina.codegen.python_renderer import format_with_ruff

        source = "x = 1\n"
        with patch("subprocess.run", side_effect=FileNotFoundError("uv not found")):
            result = format_with_ruff(source)
        assert result == source

    def test_fallback_on_nonzero_returncode(self) -> None:
        """format_with_ruff() returns source unchanged when ruff format exits non-zero."""
        from semolina.codegen.python_renderer import format_with_ruff

        source = "x = 1\n"
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", side_effect=[mock_result]):
            result = format_with_ruff(source)
        assert result == source

    def test_returns_stdout_on_success(self) -> None:
        """format_with_ruff() returns isort stdout when both passes succeed."""
        from semolina.codegen.python_renderer import format_with_ruff

        source = "x=1\n"
        formatted = "x = 1\n"
        sorted_output = "x = 1\n"
        mock_format = MagicMock()
        mock_format.returncode = 0
        mock_format.stdout = formatted
        mock_isort = MagicMock()
        mock_isort.returncode = 0
        mock_isort.stdout = sorted_output
        with patch("subprocess.run", side_effect=[mock_format, mock_isort]):
            result = format_with_ruff(source)
        assert result == sorted_output

    def test_isort_pass_applied_after_format(self) -> None:
        """format_with_ruff() calls subprocess.run twice: ruff format then ruff check --fix."""

        from semolina.codegen.python_renderer import format_with_ruff

        source = "from semolina import X\nimport datetime\n"
        formatted = "from semolina import X\nimport datetime\n"
        sorted_output = "import datetime\n\nfrom semolina import X\n"
        mock_format = MagicMock()
        mock_format.returncode = 0
        mock_format.stdout = formatted
        mock_isort = MagicMock()
        mock_isort.returncode = 0
        mock_isort.stdout = sorted_output
        with patch("subprocess.run", side_effect=[mock_format, mock_isort]) as mock_run:
            result = format_with_ruff(source)

        assert mock_run.call_count == 2
        first_cmd = mock_run.call_args_list[0][0][0]
        second_cmd = mock_run.call_args_list[1][0][0]
        # ruff is invoked via the current interpreter, not `uv run` — no uv dependency.
        assert first_cmd[:3] == [sys.executable, "-m", "ruff"]
        assert second_cmd[:3] == [sys.executable, "-m", "ruff"]
        assert "uv" not in first_cmd
        assert "format" in first_cmd
        assert "check" in second_cmd
        assert "--fix" in second_cmd
        assert "--select" in second_cmd
        assert "I" in second_cmd
        assert result == sorted_output

    def test_isort_fallback_returns_formatted_on_failure(self) -> None:
        """format_with_ruff() returns formatted source when isort pass exits non-zero."""
        from semolina.codegen.python_renderer import format_with_ruff

        source = "x=1\n"
        formatted = "x = 1\n"
        mock_format = MagicMock()
        mock_format.returncode = 0
        mock_format.stdout = formatted
        mock_isort = MagicMock()
        mock_isort.returncode = 1
        mock_isort.stdout = ""
        with patch("subprocess.run", side_effect=[mock_format, mock_isort]):
            result = format_with_ruff(source)
        assert result == formatted

    def test_short_circuits_when_ruff_unavailable(self) -> None:
        """format_with_ruff() returns source and spawns no subprocess when ruff is absent."""
        from semolina.codegen import python_renderer

        source = "x=1\n"
        with (
            patch.object(python_renderer, "ruff_available", return_value=False),
            patch("subprocess.run") as mock_run,
        ):
            result = python_renderer.format_with_ruff(source)
        assert result == source
        mock_run.assert_not_called()


class TestRuffAvailable:
    """Tests for ruff_available() helper."""

    def test_true_when_installed(self) -> None:
        """ruff_available() is True when importlib finds the ruff package."""
        from semolina.codegen.python_renderer import ruff_available

        with patch("importlib.util.find_spec", return_value=object()):
            assert ruff_available() is True

    def test_false_when_not_installed(self) -> None:
        """ruff_available() is False when the ruff package cannot be found."""
        from semolina.codegen.python_renderer import ruff_available

        with patch("importlib.util.find_spec", return_value=None):
            assert ruff_available() is False


class TestRenderAndFormat:
    """Tests for render_and_format() convenience wrapper."""

    def test_returns_string(self) -> None:
        """render_and_format() returns a string."""
        from semolina.codegen.python_renderer import render_and_format

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="revenue", field_type="metric", data_type="int"),
            ],
        )
        result = render_and_format([view])
        assert isinstance(result, str)

    def test_integration_ruff_available(self) -> None:
        """render_and_format() calls render_views then format_with_ruff."""
        from semolina.codegen.python_renderer import render_and_format

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="revenue", field_type="metric", data_type="int"),
            ],
        )
        # If ruff is available it formats; if not, source returned unchanged — both are valid
        result = render_and_format([view])
        assert "SalesView" in result
        assert "revenue = Metric[int | None]()" in result

    def test_fallback_when_ruff_unavailable(self) -> None:
        """render_and_format() returns unformatted source if ruff unavailable."""
        from semolina.codegen.python_renderer import render_and_format

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="revenue", field_type="metric", data_type="int"),
            ],
        )
        with patch("subprocess.run", side_effect=FileNotFoundError("uv not found")):
            result = render_and_format([view])
        assert "SalesView" in result
        assert "revenue = Metric[int | None]()" in result
