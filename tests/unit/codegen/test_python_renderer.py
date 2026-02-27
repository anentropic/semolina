"""
Tests for Python code renderer.

Converts IntrospectedView objects into formatted, importable Python source.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from semolina.codegen.introspector import IntrospectedField, IntrospectedView


class TestRenderViews:
    """Tests for render_views() function."""

    def test_single_view_metric_field(self) -> None:
        """Single view with one metric field renders Metric[int]() assignment."""
        from semolina.codegen.python_renderer import render_views

        view = IntrospectedView(
            view_name="sales_view",
            class_name="SalesView",
            fields=[
                IntrospectedField(name="revenue", field_type="metric", data_type="int"),
            ],
        )
        source = render_views([view])
        assert "revenue = Metric[int]()" in source
        assert "from semolina import SemanticView, Metric, Dimension, Fact" in source

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
        assert "revenue = Metric[int]()" in source
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
        assert source.count("from semolina import SemanticView, Metric, Dimension, Fact") == 1
        # Both class definitions present
        assert "class SalesView(SemanticView" in source
        assert "class OrdersView(SemanticView" in source
        # Fields use typed subscripts
        assert "revenue = Metric[int]()" in source
        assert "order_count = Metric[int]()" in source

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
        assert "from semolina import SemanticView, Metric, Dimension, Fact" in source

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
        assert "revenue = Metric[int]()" in result

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
        assert "revenue = Metric[int]()" in result
