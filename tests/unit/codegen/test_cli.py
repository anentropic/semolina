"""
Tests for the reverse codegen CLI command.

Uses CliRunner to invoke the full Typer app with a MockEngine injected via
unittest.mock.patch, avoiding any warehouse connections.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import typer
from typer.testing import CliRunner

from cubano.cli import app
from cubano.codegen.introspector import IntrospectedField, IntrospectedView
from cubano.engines.base import CubanoConnectionError, CubanoViewNotFoundError

runner = CliRunner()

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")


def plain(text: str) -> str:
    """Strip ANSI escape codes for version-independent string assertions."""
    return _ANSI_ESCAPE.sub("", text)


def make_mock_engine(views: list[IntrospectedView]) -> MagicMock:
    """
    Build a MagicMock engine whose introspect() returns views by view_name.

    Args:
        views: IntrospectedView objects to serve via introspect().

    Returns:
        MagicMock with introspect configured as a side_effect lookup.
    """
    engine = MagicMock()
    engine.introspect.side_effect = lambda view_name: next(
        v for v in views if v.view_name == view_name
    )
    return engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SALES_VIEW = IntrospectedView(
    view_name="my_schema.my_sales_view",
    class_name="MySalesView",
    fields=[
        IntrospectedField(name="revenue", field_type="metric", data_type="int"),
        IntrospectedField(name="country", field_type="dimension", data_type="str"),
        IntrospectedField(name="unit_price", field_type="fact", data_type="float"),
    ],
)

DESCRIBED_VIEW = IntrospectedView(
    view_name="my_schema.orders",
    class_name="Orders",
    fields=[
        IntrospectedField(
            name="revenue",
            field_type="metric",
            data_type="int",
            description="Total revenue",
        ),
        IntrospectedField(name="country", field_type="dimension", data_type="str", description=""),
    ],
)

TODO_VIEW = IntrospectedView(
    view_name="my_schema.geo",
    class_name="Geo",
    fields=[
        IntrospectedField(name="location", field_type="dimension", data_type="TODO: GEOGRAPHY"),
    ],
)

SECOND_VIEW = IntrospectedView(
    view_name="my_schema.customers",
    class_name="Customers",
    fields=[
        IntrospectedField(name="customer_id", field_type="dimension", data_type="int"),
    ],
)


# ---------------------------------------------------------------------------
# TestCLIBasicBehavior
# ---------------------------------------------------------------------------


class TestCLIBasicBehavior:
    """Basic CLI plumbing: help, missing args, version flag."""

    def test_help_shows_usage(self) -> None:
        """Help output includes --backend option and positional views argument."""
        result = runner.invoke(app, ["codegen", "--help"])
        assert result.exit_code == 0
        output = plain(result.output)
        assert "--backend" in output
        # Typer uses the parameter name as metavar; 'views' appears in Usage line
        assert "views" in output.lower()

    def test_missing_backend_exits_error(self) -> None:
        """Omitting --backend causes a non-zero exit."""
        result = runner.invoke(app, ["codegen", "my_schema.my_view"])
        assert result.exit_code != 0

    def test_missing_view_exits_error(self) -> None:
        """Omitting view_names causes a non-zero exit."""
        result = runner.invoke(app, ["codegen", "--backend", "snowflake"])
        assert result.exit_code != 0

    def test_version_flag(self) -> None:
        """--version prints cubano and exits 0."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "cubano" in result.output


# ---------------------------------------------------------------------------
# TestReverseCodegenOutput
# ---------------------------------------------------------------------------


class TestReverseCodegenOutput:
    """Core: introspect view -> emit Python class."""

    def test_generates_python_class_for_view(self) -> None:
        """Output contains a SemanticView subclass for the introspected view."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0, result.output
        assert "class MySalesView(SemanticView" in result.output

    def test_view_parameter_uses_full_qualified_name(self) -> None:
        """Generated class contains the schema-qualified view name in view=."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0
        assert 'view="my_schema.my_sales_view"' in result.output

    def test_metric_field_emitted_correctly(self) -> None:
        """Metric field appears as `revenue = Metric[int]()` in output."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0
        assert "revenue = Metric[int]()" in result.output

    def test_dimension_field_emitted_correctly(self) -> None:
        """Dimension field appears as `country = Dimension[str]()` in output."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0
        assert "country = Dimension[str]()" in result.output

    def test_fact_field_emitted_correctly(self) -> None:
        """Fact field appears as `unit_price = Fact[float]()` in output."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0
        assert "unit_price = Fact[float]()" in result.output

    def test_imports_at_top(self) -> None:
        """Output starts with the standard cubano import line."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0
        assert "from cubano import Dimension, Fact, Metric, SemanticView" in result.output

    def test_field_with_description_emits_docstring(self) -> None:
        """Field with a description produces an inline docstring in the output."""
        mock_engine = make_mock_engine([DESCRIBED_VIEW])
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(app, ["codegen", "my_schema.orders", "--backend", "snowflake"])
        assert result.exit_code == 0
        assert '"""Total revenue"""' in result.output

    def test_field_without_description_no_docstring(self) -> None:
        """Field with an empty description does not emit a docstring."""
        mock_engine = make_mock_engine([DESCRIBED_VIEW])
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(app, ["codegen", "my_schema.orders", "--backend", "snowflake"])
        assert result.exit_code == 0
        # country has no description; the only triple-quotes should be for revenue
        lines = result.output.splitlines()
        country_idx = next(
            i for i, line in enumerate(lines) if "country = Dimension[str]()" in line
        )
        # The line after country assignment must NOT be a docstring
        next_line = lines[country_idx + 1].strip() if country_idx + 1 < len(lines) else ""
        assert not next_line.startswith('"""')

    def test_todo_comment_for_unresolved_type(self) -> None:
        """Field with data_type starting 'TODO:' emits a # TODO: comment."""
        mock_engine = make_mock_engine([TODO_VIEW])
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(app, ["codegen", "my_schema.geo", "--backend", "snowflake"])
        assert result.exit_code == 0
        assert "# TODO:" in result.output

    def test_output_to_stdout(self) -> None:
        """Python source goes to result.output (stdout); exit code is 0."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0
        assert len(result.output) > 0


# ---------------------------------------------------------------------------
# TestMultipleViews
# ---------------------------------------------------------------------------


class TestMultipleViews:
    """Multiple view names produce multiple class definitions."""

    def test_two_views_generate_two_classes(self) -> None:
        """Passing two view names emits two Python class definitions."""
        mock_engine = make_mock_engine([SALES_VIEW, SECOND_VIEW])
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app,
                [
                    "codegen",
                    "my_schema.my_sales_view",
                    "my_schema.customers",
                    "--backend",
                    "snowflake",
                ],
            )
        assert result.exit_code == 0, result.output
        assert "class MySalesView(SemanticView" in result.output
        assert "class Customers(SemanticView" in result.output

    def test_single_imports_section_for_multiple_views(self) -> None:
        """Only one cubano import line appears even when rendering two views."""
        mock_engine = make_mock_engine([SALES_VIEW, SECOND_VIEW])
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app,
                [
                    "codegen",
                    "my_schema.my_sales_view",
                    "my_schema.customers",
                    "--backend",
                    "snowflake",
                ],
            )
        assert result.exit_code == 0
        assert result.output.count("from cubano import") == 1


# ---------------------------------------------------------------------------
# TestBackendResolution
# ---------------------------------------------------------------------------


class TestBackendResolution:
    """Backend specifier parsing and validation."""

    def test_invalid_dotted_backend_exits_2(self) -> None:
        """A dotted path that cannot be imported causes exit code 2."""
        result = runner.invoke(app, ["codegen", "s.v", "--backend", "nonexistent.module.Class"])
        assert result.exit_code == 2

    def test_unknown_simple_backend_exits_2(self) -> None:
        """A simple name with no dot (not snowflake/databricks) causes exit code 2."""
        result = runner.invoke(app, ["codegen", "s.v", "--backend", "mysql"])
        assert result.exit_code == 2

    def test_bad_parameter_via_mock_exits_2(self) -> None:
        """_resolve_backend raising BadParameter produces exit code 2."""
        with patch(
            "cubano.cli.codegen._resolve_backend",
            side_effect=typer.BadParameter("bad backend"),
        ):
            result = runner.invoke(app, ["codegen", "s.v", "--backend", "bad"])
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# TestErrorHandling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Runtime errors from introspection are surfaced cleanly."""

    def test_introspect_runtime_error_exits_1(self) -> None:
        """RuntimeError from engine.introspect() causes exit code 1."""
        mock_engine = MagicMock()
        mock_engine.introspect.side_effect = RuntimeError("Unexpected error")
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "bad_schema.missing_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 1

    def test_view_not_found_exits_3(self) -> None:
        """CubanoViewNotFoundError from engine.introspect() causes exit code 3."""
        mock_engine = MagicMock()
        mock_engine.introspect.side_effect = CubanoViewNotFoundError("View not found")
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "bad_schema.missing_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 3

    def test_connection_error_exits_4(self) -> None:
        """CubanoConnectionError from engine.introspect() causes exit code 4."""
        mock_engine = MagicMock()
        mock_engine.introspect.side_effect = CubanoConnectionError("Connection refused")
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(app, ["codegen", "my_schema.my_view", "--backend", "snowflake"])
        assert result.exit_code == 4

    def test_databricks_view_not_found_exits_3(self) -> None:
        """CubanoViewNotFoundError from a Databricks engine path causes exit code 3."""
        mock_engine = MagicMock()
        mock_engine.introspect.side_effect = CubanoViewNotFoundError(
            "Databricks view not found or inaccessible: <DatabaseError>"
        )
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "main.analytics.missing_view", "--backend", "databricks"]
            )
        assert result.exit_code == 3

    def test_databricks_connection_error_exits_4(self) -> None:
        """CubanoConnectionError from a Databricks engine path causes exit code 4."""
        mock_engine = MagicMock()
        mock_engine.introspect.side_effect = CubanoConnectionError(
            "Databricks connection failed: <OperationalError>"
        )
        with patch("cubano.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "main.analytics.my_view", "--backend", "databricks"]
            )
        assert result.exit_code == 4
