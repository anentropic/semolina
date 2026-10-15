"""
Tests for the reverse codegen CLI command.

Uses CliRunner to invoke the full Typer app with a mocked engine injected via
unittest.mock.patch, avoiding any warehouse connections.
"""

from __future__ import annotations

import io
import subprocess
import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
import typer
from rich.console import Console
from typer.testing import CliRunner

from semolina.cli import app
from semolina.cli.codegen import (
    EXIT_ANNOTATION_DRIFT,
    EXIT_CONNECTION_ERROR,
    EXIT_INVALID_BACKEND,
    EXIT_VIEW_NOT_FOUND,
    _render_check_report,
)
from semolina.codegen.annotation_check import (
    ABSENT,
    ROUTE_METADATA,
    STATUS_DRIFT,
    STATUS_MATCH,
    FieldCheckRow,
    ViewCheckReport,
)
from semolina.codegen.introspector import IntrospectedField, IntrospectedView
from semolina.codegen.probe import ROUTE_EXECUTE_SCHEMA
from semolina.engines.base import SemolinaConnectionError, SemolinaViewNotFoundError

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import Result

runner = CliRunner()


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
        assert "--backend" in result.output
        # Typer uses the parameter name as metavar; 'views' appears in Usage line
        assert "views" in result.output.lower()

    def test_missing_backend_exits_error(self) -> None:
        """Omitting --backend causes a non-zero exit."""
        result = runner.invoke(app, ["codegen", "my_schema.my_view"])
        assert result.exit_code != 0

    def test_missing_view_exits_error(self) -> None:
        """Omitting view_names causes a non-zero exit."""
        result = runner.invoke(app, ["codegen", "--backend", "snowflake"])
        assert result.exit_code != 0

    def test_version_flag(self) -> None:
        """--version prints semolina and exits 0."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "semolina" in result.output


# ---------------------------------------------------------------------------
# TestReverseCodegenOutput
# ---------------------------------------------------------------------------


class TestReverseCodegenOutput:
    """Core: introspect view -> emit Python class."""

    def test_generates_python_class_for_view(self) -> None:
        """Output contains a SemanticView subclass for the introspected view."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0, result.output
        assert "class MySalesView(SemanticView" in result.output

    def test_view_parameter_uses_full_qualified_name(self) -> None:
        """Generated class contains the schema-qualified view name in view=."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0
        assert 'view="my_schema.my_sales_view"' in result.output

    def test_metric_field_emitted_correctly(self) -> None:
        """Metric field appears as `revenue = Metric[int | None]()` in output."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0
        assert "revenue = Metric[int | None]()" in result.output

    def test_dimension_field_emitted_correctly(self) -> None:
        """Dimension field appears as `country = Dimension[str]()` in output."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0
        assert "country = Dimension[str]()" in result.output

    def test_fact_field_emitted_correctly(self) -> None:
        """Fact field appears as `unit_price = Fact[float]()` in output."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0
        assert "unit_price = Fact[float]()" in result.output

    def test_imports_at_top(self) -> None:
        """Output starts with the standard semolina import line."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0
        assert "from semolina import Dimension, Fact, Metric, SemanticView" in result.output

    def test_field_with_description_emits_docstring(self) -> None:
        """Field with a description produces an inline docstring in the output."""
        mock_engine = make_mock_engine([DESCRIBED_VIEW])
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(app, ["codegen", "my_schema.orders", "--backend", "snowflake"])
        assert result.exit_code == 0
        assert '"""Total revenue"""' in result.output

    def test_field_without_description_no_docstring(self) -> None:
        """Field with an empty description does not emit a docstring."""
        mock_engine = make_mock_engine([DESCRIBED_VIEW])
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
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
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(app, ["codegen", "my_schema.geo", "--backend", "snowflake"])
        assert result.exit_code == 0
        assert "# TODO:" in result.output

    def test_output_to_stdout(self) -> None:
        """Python source goes to result.output (stdout); exit code is 0."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
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
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
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
        """Only one semolina import line appears even when rendering two views."""
        mock_engine = make_mock_engine([SALES_VIEW, SECOND_VIEW])
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
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
        assert result.output.count("from semolina import") == 1


# ---------------------------------------------------------------------------
# TestValidityGate
# ---------------------------------------------------------------------------


def _diagnostics(result: Result) -> str:
    """
    Read stderr back as one unwrapped line, so a test asserts what a message says.

    Rich hard-wraps to the console width; collapsing whitespace makes the assertion
    independent of where the wrap fell.

    Args:
        result: The ``CliRunner`` result.

    Returns:
        Stderr with every run of whitespace collapsed to a single space.
    """
    return " ".join(result.stderr.split())


UNUSABLE_CLASS_NAMES = [
    pytest.param("2024Sales", id="leading-digit"),
    pytest.param("class", id="keyword"),
    pytest.param("Sales:\n    pass\n\nimport os\nclass X", id="statement-injection"),
]
"""
Class names an engine may hand back that no ``class`` statement can carry.

The built-in engines all derive the name with ``introspector.class_name_for``, which never
produces one of these. A ``--backend dotted.path.ClassName`` engine builds its own
``IntrospectedView``, though, and its ``class_name`` is written into the generated file as a
bare token -- the one value no escaper can make safe.
"""


class TestValidityGate:
    """
    ``codegen`` refuses a class name it cannot emit, and never emits source that won't parse.

    The DTO command has had these guards since it shipped; the model command had none, and
    exited 0 having written a module that fails on import (A24).
    """

    @pytest.mark.parametrize("class_name", UNUSABLE_CLASS_NAMES)
    def test_a_view_whose_class_name_is_unusable_exits_2_naming_it(self, class_name: str) -> None:
        """The view and the class name are both named, and nothing reaches stdout."""
        view = IntrospectedView(
            view_name="analytics.2024_sales",
            class_name=class_name,
            fields=[IntrospectedField(name="revenue", field_type="metric", data_type="int")],
        )
        mock_engine = make_mock_engine([view])
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "analytics.2024_sales", "--backend", "custom.Engine"]
            )
        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert result.stdout == "", result.stdout
        assert "analytics.2024_sales" in _diagnostics(result), result.stderr
        assert "not a valid Python class name" in _diagnostics(result), result.stderr

    def test_two_views_folding_to_one_class_name_exit_2_naming_both(self) -> None:
        """
        ``a.sales`` and ``b.sales`` both become ``Sales``, and one module cannot carry two.

        Python does not report it: the second ``class Sales`` silently replaces the first, so
        the file imports cleanly and is missing a model. Both views are named so the user
        knows which pair to split.
        """
        from semolina.codegen.introspector import class_name_for

        views = [
            IntrospectedView(
                view_name=name,
                class_name=class_name_for(name),
                fields=[IntrospectedField(name="revenue", field_type="metric", data_type="int")],
            )
            for name in ("emea.sales", "apac.sales")
        ]
        mock_engine = make_mock_engine(views)
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "emea.sales", "apac.sales", "--backend", "snowflake"]
            )
        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert result.stdout == "", result.stdout
        diagnostics = _diagnostics(result)
        assert "emea.sales" in diagnostics, result.stderr
        assert "apac.sales" in diagnostics, result.stderr
        assert "'Sales'" in diagnostics, result.stderr

    def test_source_that_does_not_parse_exits_1_and_emits_nothing(self) -> None:
        """
        The rendered module is ``ast.parse``d before it is emitted.

        The renderer is patched to produce a broken module, standing in for any template or
        escaping defect the name checks did not anticipate. ruff is switched off so the parse
        check is what has to notice, not the formatter.
        """
        mock_engine = make_mock_engine([SALES_VIEW])
        with (
            patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine),
            patch(
                "semolina.codegen.python_renderer.render_views",
                return_value="class MySalesView(:\n    pass\n",
            ),
            patch("semolina.codegen.python_renderer.ruff_available", return_value=False),
        ):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 1, result.output
        assert result.stdout == "", result.stdout
        assert "does not parse" in _diagnostics(result), result.stderr
        assert result.exception is None or isinstance(result.exception, SystemExit)

    def test_a_ruff_failure_exits_1_with_ruffs_message(self) -> None:
        """
        Ruff installed but exiting non-zero is reported, not swallowed (GEN-02).

        Before, the formatter's failure returned the unformatted source with exit 0, so the
        one tool that might have noticed a broken module stayed silent.
        """
        failed = MagicMock(returncode=2, stdout="", stderr="error: Failed to parse models.py")
        mock_engine = make_mock_engine([SALES_VIEW])
        with (
            patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine),
            patch("semolina.codegen.python_renderer.ruff_available", return_value=True),
            patch("semolina.codegen.python_renderer.subprocess.run", return_value=failed),
        ):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 1, result.output
        assert result.stdout == "", result.stdout
        assert "Failed to parse models.py" in _diagnostics(result), result.stderr
        assert result.exception is None or isinstance(result.exception, SystemExit)


# ---------------------------------------------------------------------------
# TestCredentialsNeverReachStderr / TestTheSharedExitTable
# ---------------------------------------------------------------------------

# The two commands reach `_resolve_backend` through different arguments. `codegen-dto --view`
# builds its query from names alone, so it gets to the backend without importing anything or
# touching a warehouse -- the same point `codegen` reaches with a view name.
COMMAND_PREFIXES = [
    pytest.param(["codegen", "analytics.sales"], id="codegen"),
    pytest.param(
        ["codegen-dto", "--view", "analytics.sales", "--metrics", "revenue"], id="codegen-dto"
    ),
]

SECRET = "hunter2-do-not-print"


def _isolate_snowflake_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Run from an empty directory with no ``SNOWFLAKE_*`` variable inherited.

    Args:
        tmp_path: The directory to run from.
        monkeypatch: pytest's monkeypatch fixture.
    """
    import os

    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith("SNOWFLAKE_") or key == "SEMOLINA_ENV_FILE":
            monkeypatch.delenv(key)


class TestCredentialsNeverReachStderr:
    """
    A config ``ValidationError`` names fields, never their values (GEN-03, A25).

    pydantic's own message carries ``input_value={'user': ..., 'password': ...}`` -- the
    whole dict the settings were built from -- and the command printed it verbatim. A CI log
    is the last place a warehouse password should land.
    """

    @pytest.mark.parametrize("prefix", COMMAND_PREFIXES)
    def test_a_password_from_the_environment_is_not_printed(
        self, prefix: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``account`` is missing; the error names it and leaves the password out."""
        _isolate_snowflake_config(tmp_path, monkeypatch)
        monkeypatch.setenv("SNOWFLAKE_USER", "bob")
        monkeypatch.setenv("SNOWFLAKE_PASSWORD", SECRET)

        result = runner.invoke(app, [*prefix, "--backend", "snowflake"])

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert SECRET not in result.output
        assert SECRET not in result.stderr
        assert "account" in _diagnostics(result), result.stderr

    @pytest.mark.parametrize("prefix", COMMAND_PREFIXES)
    def test_a_password_from_semolina_toml_is_not_printed(
        self, prefix: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The same, with the password committed to ``.semolina.toml``."""
        _isolate_snowflake_config(tmp_path, monkeypatch)
        (tmp_path / ".semolina.toml").write_text(
            f'[connections.snowflake]\nuser = "bob"\npassword = "{SECRET}"\n'
        )

        result = runner.invoke(app, [*prefix, "--backend", "snowflake"])

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert SECRET not in result.output
        assert SECRET not in result.stderr
        assert "account" in _diagnostics(result), result.stderr


class TestTheSharedExitTable:
    """
    Expected failures map to documented exit codes on both commands (GEN-04, A26).

    Each of these escaped ``codegen`` as a raw traceback with exit 1: a backend whose driver
    extra is missing, a ``--backend dotted.path.ClassName`` that cannot be built with no
    arguments, and a driver error ``Engine.introspect`` did not translate.
    """

    @pytest.mark.parametrize("prefix", COMMAND_PREFIXES)
    def test_a_missing_driver_extra_exits_2_naming_the_extra(
        self, prefix: list[str], tmp_path: Path
    ) -> None:
        """
        The ``ImportError`` adbc-poolhouse raises for an absent driver is an option error.

        Raised from ``create_engine`` because that is where it comes from in practice: the
        pool is built, and poolhouse loads the driver while doing it.
        """
        missing = ImportError(
            "ADBC driver 'adbc_driver_duckdb' not found. See: https://docs.adbc-drivers.org/"
        )
        with patch("semolina.config.create_engine", side_effect=missing):
            result = runner.invoke(
                app, [*prefix, "--backend", "duckdb", "--database", str(tmp_path / "x.db")]
            )

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "adbc_driver_duckdb" in _diagnostics(result), result.stderr
        assert "semolina[duckdb]" in _diagnostics(result), result.stderr
        assert result.exception is None or isinstance(result.exception, SystemExit)

    @pytest.mark.parametrize(
        "backend",
        [
            pytest.param("codegen.fixtures.backends.NeedsArguments", id="needs-arguments"),
            pytest.param("codegen.fixtures.backends.RaisesInInit", id="raises-in-init"),
        ],
    )
    @pytest.mark.parametrize("prefix", COMMAND_PREFIXES)
    def test_a_dotted_backend_that_cannot_be_built_exits_2(
        self, prefix: list[str], backend: str
    ) -> None:
        """The class is named, with what its constructor said, and no traceback."""
        result = runner.invoke(app, [*prefix, "--backend", backend])

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert backend in _diagnostics(result), result.stderr
        assert result.exception is None or isinstance(result.exception, SystemExit)

    def test_an_untranslated_driver_error_while_introspecting_exits_6(self) -> None:
        """
        A raw ``adbc_driver_manager.Error`` from ``introspect()`` exits 6, as on codegen-dto.

        The built-in engines translate every driver error they raise; a ``--backend
        dotted.path.ClassName`` engine need not. ``codegen-dto`` maps the same exception at
        the same stage -- the warehouse describing what was asked for -- to 6, and one table
        means one answer.
        """
        import adbc_driver_manager  # pyright: ignore[reportMissingImports]

        from semolina.cli.dto_codegen import EXIT_PROBE_FAILED

        error = adbc_driver_manager.ProgrammingError(
            "relation does not exist",
            status_code=adbc_driver_manager.AdbcStatusCode.INVALID_ARGUMENT,
        )
        engine = MagicMock()
        engine.introspect.side_effect = error
        with patch("semolina.cli.codegen._resolve_backend", return_value=engine):
            result = runner.invoke(app, ["codegen", "analytics.sales", "--backend", "custom.E"])

        assert result.exit_code == EXIT_PROBE_FAILED, result.output
        assert "relation does not exist" in _diagnostics(result), result.stderr
        assert "analytics.sales" in _diagnostics(result), result.stderr
        assert result.exception is None or isinstance(result.exception, SystemExit)

    def test_an_untranslated_driver_error_under_check_exits_6(self, tmp_path: Path) -> None:
        """``--check`` goes through the same table as generation."""
        import adbc_driver_manager  # pyright: ignore[reportMissingImports]

        from semolina.cli.dto_codegen import EXIT_PROBE_FAILED

        model = tmp_path / "models.py"
        model.write_text(
            "from semolina import Metric, SemanticView\n\n\n"
            'class Sales(SemanticView, view="analytics.sales"):\n'
            "    revenue = Metric[int | None]()\n"
        )
        error = adbc_driver_manager.OperationalError(
            "warehouse suspended",
            status_code=adbc_driver_manager.AdbcStatusCode.IO,
        )
        with (
            patch("semolina.cli.codegen._resolve_backend", return_value=MagicMock()),
            patch("semolina.codegen.annotation_check.check_view", side_effect=error),
        ):
            result = runner.invoke(
                app,
                [
                    "codegen",
                    "analytics.sales",
                    "--backend",
                    "custom.E",
                    "--check",
                    "--model",
                    str(model),
                ],
            )

        assert result.exit_code == EXIT_PROBE_FAILED, result.output
        assert "warehouse suspended" in _diagnostics(result), result.stderr
        assert result.exception is None or isinstance(result.exception, SystemExit)

    @pytest.mark.parametrize(
        ("make_error", "stage", "code"),
        [
            pytest.param(lambda: typer.BadParameter("x"), "setup", 2, id="bad-parameter"),
            pytest.param(lambda: ImportError("no driver"), "setup", 2, id="missing-extra"),
            pytest.param(
                lambda: SemolinaConnectionError("refused"), "setup", 4, id="setup-connection"
            ),
            pytest.param(
                lambda: SemolinaViewNotFoundError("gone"), "warehouse", 3, id="view-not-found"
            ),
            pytest.param(
                lambda: SemolinaConnectionError("refused"), "warehouse", 4, id="connection"
            ),
            pytest.param(lambda: RuntimeError("odd"), "warehouse", 1, id="runtime-error"),
            pytest.param(lambda: ValueError("unquotable"), "warehouse", 1, id="value-error"),
            pytest.param(lambda: KeyError("bug"), "warehouse", None, id="unlisted-propagates"),
        ],
    )
    def test_the_table(self, make_error: Any, stage: str, code: int | None) -> None:
        """
        One function answers for both commands; anything it does not list propagates.

        A row missing here would be an exception one command reports and the other lets
        out as a traceback, which is the divergence GEN-04 removes. ``None`` is the table's
        "not mine" answer: a bug should still surface as one, not as a tidy exit 1.
        """
        from semolina.cli.codegen import exit_code_for

        assert exit_code_for(make_error(), stage=stage) == code

    @pytest.mark.parametrize("stage", ["setup", "warehouse"])
    def test_the_table_maps_driver_errors_by_stage(self, stage: str) -> None:
        """A driver error is a connection failure at setup and a failed description after."""
        import adbc_driver_manager  # pyright: ignore[reportMissingImports]

        from semolina.cli.codegen import exit_code_for

        error = adbc_driver_manager.InternalError(
            "x", status_code=adbc_driver_manager.AdbcStatusCode.INTERNAL
        )
        assert exit_code_for(error, stage=stage) == (4 if stage == "setup" else 6)


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
            "semolina.cli.codegen._resolve_backend",
            side_effect=typer.BadParameter("bad backend"),
        ):
            result = runner.invoke(app, ["codegen", "s.v", "--backend", "bad"])
        assert result.exit_code == 2

    def test_malformed_toml_exits_2(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A malformed .semolina.toml surfaces as a clean error (exit 2), not a raw traceback."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".semolina.toml").write_text("this is = = not valid toml\n")
        result = runner.invoke(app, ["codegen", "s.v", "--backend", "snowflake"])
        assert result.exit_code == 2

    def test_resolve_backend_malformed_toml_raises_bad_parameter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_resolve_backend wraps a TOML parse error in typer.BadParameter."""
        from semolina.cli.codegen import _resolve_backend

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".semolina.toml").write_text("this is = = not valid toml\n")
        with pytest.raises(typer.BadParameter, match="semolina.toml"):
            _resolve_backend("snowflake")


# ---------------------------------------------------------------------------
# TestErrorHandling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Runtime errors from introspection are surfaced cleanly."""

    def test_introspect_runtime_error_exits_1(self) -> None:
        """RuntimeError from engine.introspect() causes exit code 1."""
        mock_engine = MagicMock()
        mock_engine.introspect.side_effect = RuntimeError("Unexpected error")
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "bad_schema.missing_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 1

    def test_view_not_found_exits_3(self) -> None:
        """SemolinaViewNotFoundError from engine.introspect() causes exit code 3."""
        mock_engine = MagicMock()
        mock_engine.introspect.side_effect = SemolinaViewNotFoundError("View not found")
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "bad_schema.missing_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 3

    def test_connection_error_exits_4(self) -> None:
        """SemolinaConnectionError from engine.introspect() causes exit code 4."""
        mock_engine = MagicMock()
        mock_engine.introspect.side_effect = SemolinaConnectionError("Connection refused")
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(app, ["codegen", "my_schema.my_view", "--backend", "snowflake"])
        assert result.exit_code == 4

    def test_databricks_view_not_found_exits_3(self) -> None:
        """SemolinaViewNotFoundError from a Databricks engine path causes exit code 3."""
        mock_engine = MagicMock()
        mock_engine.introspect.side_effect = SemolinaViewNotFoundError(
            "Databricks view not found or inaccessible: <DatabaseError>"
        )
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "main.analytics.missing_view", "--backend", "databricks"]
            )
        assert result.exit_code == 3

    def test_databricks_connection_error_exits_4(self) -> None:
        """SemolinaConnectionError from a Databricks engine path causes exit code 4."""
        mock_engine = MagicMock()
        mock_engine.introspect.side_effect = SemolinaConnectionError(
            "Databricks connection failed: <OperationalError>"
        )
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "main.analytics.my_view", "--backend", "databricks"]
            )
        assert result.exit_code == 4


# ---------------------------------------------------------------------------
# TestDuckDBBackend
# ---------------------------------------------------------------------------


class TestDuckDBBackend:
    """DuckDB backend resolution and --database option."""

    def test_duckdb_backend_with_database_option(self) -> None:
        """--backend duckdb --database test.db resolves DuckDBEngine."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app,
                [
                    "codegen",
                    "my_schema.my_sales_view",
                    "--backend",
                    "duckdb",
                    "--database",
                    "test.db",
                ],
            )
        assert result.exit_code == 0, result.output
        assert "class MySalesView(SemanticView" in result.output

    def test_duckdb_backend_database_env_var(self) -> None:
        """--backend duckdb uses DUCKDB_DATABASE env var when --database not given."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app,
                ["codegen", "my_schema.my_sales_view", "--backend", "duckdb"],
                env={"DUCKDB_DATABASE": "/tmp/test.db"},
            )
        assert result.exit_code == 0, result.output

    def test_duckdb_backend_no_database_exits_error(self) -> None:
        """--backend duckdb without --database or env var exits with error."""
        result = runner.invoke(
            app,
            ["codegen", "my_schema.my_sales_view", "--backend", "duckdb"],
        )
        assert result.exit_code == EXIT_INVALID_BACKEND

    def test_duckdb_resolve_creates_engine_with_database(self) -> None:
        """_resolve_backend('duckdb', database='test.db') builds via create_engine."""
        with patch("semolina.config.create_engine") as mock_create_engine:
            mock_create_engine.return_value = MagicMock()
            from pathlib import Path

            from semolina.cli.codegen import _resolve_backend

            _resolve_backend("duckdb", database="test.db")
            expected = str(Path("test.db").expanduser().resolve(strict=False))
            mock_create_engine.assert_called_once()
            (config,) = mock_create_engine.call_args[0]
            assert config.database == expected

    def test_duckdb_view_not_found_exits_3(self) -> None:
        """SemolinaViewNotFoundError from DuckDB introspect exits 3."""
        mock_engine = MagicMock()
        mock_engine.introspect.side_effect = SemolinaViewNotFoundError("View not found")
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app,
                ["codegen", "missing_view", "--backend", "duckdb", "--database", "test.db"],
            )
        assert result.exit_code == EXIT_VIEW_NOT_FOUND

    def test_an_invalid_view_name_is_an_error_message_not_a_traceback(self) -> None:
        """quote_table_name's ValueError on a malformed name reaches the user as an error line."""
        mock_engine = MagicMock()
        mock_engine.introspect.side_effect = ValueError("View name '\"x' has an unbalanced quote")
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app,
                ["codegen", '"x', "--backend", "duckdb", "--database", "test.db"],
            )
        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        assert "unbalanced quote" in result.output

    def test_duckdb_connection_error_exits_4(self) -> None:
        """SemolinaConnectionError from DuckDB exits 4."""
        mock_engine = MagicMock()
        mock_engine.introspect.side_effect = SemolinaConnectionError("Cannot open file")
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app,
                ["codegen", "orders", "--backend", "duckdb", "--database", "bad.db"],
            )
        assert result.exit_code == EXIT_CONNECTION_ERROR


# ---------------------------------------------------------------------------
# TestPathNormalization
# ---------------------------------------------------------------------------


class TestPathNormalization:
    """
    Tests for the ``_normalize_database_path`` helper in ``cli/codegen.py``.

    Pinned by CONTEXT.md decision D-LockedPathHandling: ``:memory:`` MUST pass
    through unchanged; empty strings MUST pass through unchanged (so DuckDB
    raises the consistent error); non-sentinel values MUST be expanded with
    ``expanduser`` and resolved with ``strict=False``. The same treatment
    applies whether the value arrives via ``--database`` or ``DUCKDB_DATABASE``.
    """

    def test_memory_sentinel_preserved(self) -> None:
        """``:memory:`` sentinel must pass through unchanged (CONTEXT.md guard)."""
        from semolina.cli.codegen import _normalize_database_path

        assert _normalize_database_path(":memory:") == ":memory:"

    def test_empty_string_passthrough(self) -> None:
        """
        Empty strings must pass through unchanged.

        The CONTEXT.md guard ``if database and database != ":memory:":``
        short-circuits on falsy input. Without this, ``Path("").resolve()``
        silently expands to the current working directory — masking a bug
        and producing an inconsistent error path. Leaving ``""`` unchanged
        lets DuckDB raise the same error it would for any invalid path.
        """
        from semolina.cli.codegen import _normalize_database_path

        assert _normalize_database_path("") == ""

    def test_tilde_expanded(self) -> None:
        """Leading ``~`` must expand to the user home directory."""
        from pathlib import Path

        from semolina.cli.codegen import _normalize_database_path

        result = _normalize_database_path("~/sales.duckdb")
        assert "~" not in result
        assert result.startswith(str(Path.home()))

    def test_relative_resolved_to_absolute(self) -> None:
        """Relative paths must resolve to absolute paths (non-strict)."""
        from pathlib import Path

        from semolina.cli.codegen import _normalize_database_path

        result = _normalize_database_path("./does_not_exist/sales.duckdb")
        assert Path(result).is_absolute()
        # strict=False: should NOT raise FileNotFoundError when target is missing

    def test_envvar_path_normalized(self) -> None:
        """
        Paths supplied via ``DUCKDB_DATABASE`` env-var must also be normalized.

        CONTEXT.md (Path Handling, locked): "Apply ``expanduser()`` +
        ``resolve(strict=False)`` to the ``--database`` value AND to the value
        of the ``DUCKDB_DATABASE`` env-var fallback. Same treatment for both
        sources." This test invokes the CLI with the env-var set and no
        ``--database`` flag, then asserts the expanded path is what reached
        the engine layer.
        """
        from pathlib import Path

        captured: dict[str, str] = {}

        def _fake_create_engine(config: object) -> MagicMock:
            captured["database"] = config.database  # type: ignore[attr-defined]
            engine = MagicMock()
            engine.introspect.side_effect = SystemExit(0)  # short-circuit codegen
            return engine

        # Patch the factory invoked inside _resolve_backend's duckdb branch.
        with patch("semolina.config.create_engine", _fake_create_engine):
            runner.invoke(
                app,
                ["codegen", "sales_view", "--backend", "duckdb"],
                env={"DUCKDB_DATABASE": "~/foo.duckdb"},
            )

        assert "database" in captured, (
            "create_engine was never called; env-var path did not reach _resolve_backend"
        )
        assert "~" not in captured["database"], (
            f"DUCKDB_DATABASE was not normalized: {captured['database']!r}"
        )
        assert captured["database"].startswith(str(Path.home())), (
            f"Expected expanded home path, got {captured['database']!r}"
        )


class TestRuffNotInstalledHint:
    """When ruff is absent, codegen still emits source plus a stderr hint."""

    def test_hint_printed_when_ruff_missing(self) -> None:
        """Source still goes to stdout; the codegen-lint hint goes to the stderr console."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with (
            patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine),
            patch("semolina.codegen.python_renderer.ruff_available", return_value=False),
            patch("semolina.cli.codegen._stderr") as mock_stderr,
        ):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0, result.output
        # Generated source still reaches stdout, unformatted.
        assert "class MySalesView(SemanticView" in result.output
        # The hint goes to the stderr console — never to stdout, so piping stays clean.
        assert "codegen-lint" not in result.output
        mock_stderr.print.assert_called_once()
        hint = mock_stderr.print.call_args[0][0]
        assert "codegen-lint" in hint

    def test_no_hint_when_ruff_available(self) -> None:
        """When ruff is installed, codegen prints no hint."""
        mock_engine = make_mock_engine([SALES_VIEW])
        with (
            patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine),
            patch("semolina.codegen.python_renderer.ruff_available", return_value=True),
            patch("semolina.cli.codegen._stderr") as mock_stderr,
        ):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0, result.output
        assert "class MySalesView(SemanticView" in result.output
        mock_stderr.print.assert_not_called()


# ---------------------------------------------------------------------------
# TestAnnotationCheck
# ---------------------------------------------------------------------------


def _generate_model(db_path: Path, target: Path) -> str:
    """
    Generate a model for ``sales_view`` through the real CLI and write it to ``target``.

    Generating the fixture rather than hand-writing it proves the round trip and keeps the
    fixture from going stale the next time the renderer changes.

    Args:
        db_path: The file-backed DuckDB database.
        target: Where to write the generated source.

    Returns:
        The generated source.
    """
    result = runner.invoke(
        app, ["codegen", "sales_view", "--backend", "duckdb", "--database", str(db_path)]
    )
    assert result.exit_code == 0, result.output
    target.write_text(result.stdout, encoding="utf-8")
    return result.stdout


def _ruff_format_check(path: Path) -> subprocess.CompletedProcess[str]:
    """
    Run ``ruff format --check --isolated`` on a file, as a CI job would.

    ``--isolated`` because the generated module is formatted that way (GEN-07): with this
    repository's own ``pyproject.toml`` in play, the check would measure the repo's ruff
    settings rather than the generated file.

    Args:
        path: The file to check.

    Returns:
        The completed process; ``returncode`` 0 means ruff would change nothing.
    """
    return subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", "--isolated", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


class TestCodegenWritesToAFile:
    """
    ``--output`` on ``codegen``: the module ``> models.py`` produces, written safely.

    The shell redirect truncates ``models.py`` before codegen has done anything, so a run
    that fails leaves an empty file where a committed model was (A29). ``--output`` writes
    only after every view rendered, and atomically, so a failed run leaves it alone.
    """

    def test_stdout_passes_ruff_format_check(self, tmp_path: Path) -> None:
        """
        ``> models.py`` yields a file ``ruff format --check`` accepts (GEN-05, A27).

        ``typer.echo`` appended a newline to source that already ended in one, so the
        documented workflow produced a file the formatter wanted to change.
        """
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app, ["codegen", "my_schema.my_sales_view", "--backend", "snowflake"]
            )
        assert result.exit_code == 0, result.output
        redirected = tmp_path / "models.py"
        redirected.write_text(result.stdout, encoding="utf-8")
        check = _ruff_format_check(redirected)
        assert check.returncode == 0, check.stdout + check.stderr

    def test_output_writes_the_module_and_nothing_to_stdout(self, tmp_path: Path) -> None:
        """The file holds the module; stdout is empty; stderr says where it went."""
        target = tmp_path / "models.py"
        mock_engine = make_mock_engine([SALES_VIEW])
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            result = runner.invoke(
                app,
                [
                    "codegen",
                    "my_schema.my_sales_view",
                    "--backend",
                    "snowflake",
                    "--output",
                    str(target),
                ],
            )
        assert result.exit_code == 0, result.output
        assert result.stdout == "", result.stdout
        assert "class MySalesView(SemanticView" in target.read_text()
        assert "Wrote:" in _diagnostics(result), result.stderr

    def test_stdout_and_output_are_byte_identical_and_ruff_clean(self, tmp_path: Path) -> None:
        """
        The two documented ways to land the module produce the same bytes (GEN-05).

        Bytes, not text: a trailing-newline difference is exactly what this pins, and a
        ``read_text`` comparison would hide a line-ending one as well.
        """
        target = tmp_path / "models.py"
        mock_engine = make_mock_engine([SALES_VIEW, SECOND_VIEW])
        views = ["my_schema.my_sales_view", "my_schema.customers"]
        with patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine):
            to_stdout = runner.invoke(app, ["codegen", *views, "--backend", "snowflake"])
            to_file = runner.invoke(
                app, ["codegen", *views, "--backend", "snowflake", "--output", str(target)]
            )
        assert to_stdout.exit_code == 0, to_stdout.output
        assert to_file.exit_code == 0, to_file.output
        assert target.read_bytes() == to_stdout.stdout_bytes
        check = _ruff_format_check(target)
        assert check.returncode == 0, check.stdout + check.stderr

    def test_a_failure_on_a_later_view_leaves_the_file_untouched(self, tmp_path: Path) -> None:
        """
        Nothing is written until every view has been introspected and rendered.

        The second view fails, after the first succeeded -- the point at which an
        implementation writing per view would already have replaced the committed file.
        """
        target = tmp_path / "models.py"
        target.write_text("# committed\n", encoding="utf-8")
        engine = MagicMock()
        engine.introspect.side_effect = [SALES_VIEW, SemolinaViewNotFoundError("customers")]
        with patch("semolina.cli.codegen._resolve_backend", return_value=engine):
            result = runner.invoke(
                app,
                [
                    "codegen",
                    "my_schema.my_sales_view",
                    "my_schema.customers",
                    "--backend",
                    "snowflake",
                    "--output",
                    str(target),
                ],
            )
        assert result.exit_code == EXIT_VIEW_NOT_FOUND, result.output
        assert target.read_text() == "# committed\n"

    def test_the_write_is_atomic(self, tmp_path: Path) -> None:
        """
        The module is written beside the target and renamed over it, never written in place.

        Driven by failing the rename. An in-place write would already have replaced the
        committed file by then; an atomic one leaves it, and leaves no temporary file behind.
        """
        target = tmp_path / "models.py"
        target.write_text("# committed\n", encoding="utf-8")
        mock_engine = make_mock_engine([SALES_VIEW])
        with (
            patch("semolina.cli.codegen._resolve_backend", return_value=mock_engine),
            patch("os.replace", side_effect=OSError("disk full")),
        ):
            result = runner.invoke(
                app,
                [
                    "codegen",
                    "my_schema.my_sales_view",
                    "--backend",
                    "snowflake",
                    "--output",
                    str(target),
                ],
            )
        assert result.exit_code == 1, result.output
        assert target.read_text() == "# committed\n"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["models.py"]
        assert "disk full" in _diagnostics(result), result.stderr

    def test_a_directory_that_does_not_exist_exits_2_before_connecting(
        self, tmp_path: Path
    ) -> None:
        """A mistyped destination is caught before the backend is resolved."""
        with patch("semolina.cli.codegen._resolve_backend") as resolve:
            result = runner.invoke(
                app,
                [
                    "codegen",
                    "my_schema.my_sales_view",
                    "--backend",
                    "snowflake",
                    "--output",
                    str(tmp_path / "nope" / "models.py"),
                ],
            )
        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "does not exist" in _diagnostics(result), result.stderr
        resolve.assert_not_called()

    def test_check_reads_the_file_output_names(
        self, duckdb_file_backed_db: Path, tmp_path: Path
    ) -> None:
        """
        ``--check --output PATH`` checks the file ``--output PATH`` writes (GEN-06).

        The same pairing ``codegen-dto`` has: one option names the file both ways, so CI
        checks exactly the file generation would write. ``--model`` is no longer needed.
        """
        model = tmp_path / "models.py"
        _generate_model(duckdb_file_backed_db, model)

        result = runner.invoke(
            app,
            [
                "codegen",
                "sales_view",
                "--check",
                "--output",
                str(model),
                "--backend",
                "duckdb",
                "--database",
                str(duckdb_file_backed_db),
            ],
        )

        assert result.exit_code == 0, result.stderr
        assert result.stdout == ""
        assert ROUTE_EXECUTE_SCHEMA in result.stderr

    def test_check_with_both_model_and_output_exits_2(self, tmp_path: Path) -> None:
        """Two options naming the file to check is one too many; neither silently wins."""
        result = runner.invoke(
            app,
            [
                "codegen",
                "sales_view",
                "--check",
                "--output",
                str(tmp_path / "a.py"),
                "--model",
                str(tmp_path / "b.py"),
                "--backend",
                "duckdb",
                "--database",
                "x.db",
            ],
        )
        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "--model" in _diagnostics(result), result.stderr


class TestAnnotationCheckOptionValidation:
    """``--check`` and ``--model`` are only meaningful together."""

    def test_check_without_model_exits_invalid_backend(self) -> None:
        result = runner.invoke(
            app, ["codegen", "sales_view", "--check", "--backend", "duckdb", "--database", "x.db"]
        )

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "--model" in result.stderr

    def test_model_without_check_exits_invalid_backend(self) -> None:
        result = runner.invoke(
            app,
            [
                "codegen",
                "sales_view",
                "--model",
                "models.py",
                "--backend",
                "duckdb",
                "--database",
                "x.db",
            ],
        )

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "--model" in result.stderr

    def test_missing_model_file_exits_1_without_a_traceback(
        self, duckdb_file_backed_db: Path, tmp_path: Path
    ) -> None:
        missing = tmp_path / "nope.py"

        result = runner.invoke(
            app,
            [
                "codegen",
                "sales_view",
                "--check",
                "--model",
                str(missing),
                "--backend",
                "duckdb",
                "--database",
                str(duckdb_file_backed_db),
            ],
        )

        assert result.exit_code == 1, result.output
        assert "nope.py" in result.stderr
        assert "Traceback" not in result.stderr

    def test_help_documents_the_drift_exit_code(self) -> None:
        result = runner.invoke(app, ["codegen", "--help"])

        assert result.exit_code == 0
        drift_lines = [line for line in result.output.splitlines() if "drift" in line]
        assert drift_lines, result.output
        assert any("5" in line for line in drift_lines)


def _render_to_text(report: ViewCheckReport, *, width: int = 200) -> str:
    """
    Render one report through the real ``_render_check_report`` and capture the text.

    The module-level ``_stderr`` console is swapped for a wide, file-backed one so the
    assertions below are about markup handling rather than about where rich chose to wrap.

    Args:
        report: The report to render.
        width: Console width; wide enough that no cell in these fixtures wraps.

    Returns:
        Everything the renderer wrote.
    """
    buffer = io.StringIO()
    console = Console(file=buffer, width=width, force_terminal=False, highlight=False)
    with patch("semolina.cli.codegen._stderr", console):
        _render_check_report(report)
    return buffer.getvalue()


class TestCheckReportIsNotParsedAsMarkup:
    """
    The report's cells are data, not style directives.

    The drift report carries warehouse- and model-supplied strings, and rich renders
    ``str`` cells with ``markup=True``. A report whose whole job is to show a difference
    must not have the difference eaten by a style tag, and a catalogue field name must not
    be able to crash the CLI out of its own exit codes.
    """

    def test_a_subscripted_annotation_survives_the_table(self) -> None:
        """``list[str]`` and ``list[int]`` must not both print as ``list``."""
        report = ViewCheckReport(
            view_name="v",
            rows=[
                FieldCheckRow(
                    name="payload",
                    committed="list[str] | None",
                    probed="list[int] | None",
                    route=ROUTE_EXECUTE_SCHEMA,
                    status=STATUS_DRIFT,
                )
            ],
            has_drift=True,
        )

        output = _render_to_text(report)

        assert "list[str] | None" in output
        assert "list[int] | None" in output

    def test_a_closing_tag_shaped_field_name_does_not_crash(self) -> None:
        """A quoted identifier from the catalogue is data, not a style directive."""
        report = ViewCheckReport(
            view_name="v",
            rows=[
                FieldCheckRow(
                    name="[/red]",
                    committed="str",
                    probed=ABSENT,
                    route=ROUTE_EXECUTE_SCHEMA,
                    status=STATUS_DRIFT,
                )
            ],
            has_drift=True,
        )

        output = _render_to_text(report)

        assert "[/red]" in output

    def test_the_status_cell_is_still_styled(self) -> None:
        """Bypassing markup must not cost the red/green the status column carries."""
        report = ViewCheckReport(
            view_name="v",
            rows=[
                FieldCheckRow(
                    name="ok",
                    committed="str",
                    probed="str",
                    route=ROUTE_EXECUTE_SCHEMA,
                    status=STATUS_MATCH,
                ),
                FieldCheckRow(
                    name="bad",
                    committed="str",
                    probed="int",
                    route=ROUTE_EXECUTE_SCHEMA,
                    status=STATUS_DRIFT,
                ),
            ],
            has_drift=True,
        )

        buffer = io.StringIO()
        # ``tests/conftest.py`` sets NO_COLOR=1 for the whole suite, which rich honours by
        # stripping colour while keeping every other attribute. This one test is about the
        # colour, so it opts back in explicitly rather than asserting on an empty channel.
        console = Console(
            file=buffer,
            width=200,
            force_terminal=True,
            color_system="truecolor",
            no_color=False,
            highlight=False,
        )
        with patch("semolina.cli.codegen._stderr", console):
            _render_check_report(report)
        rendered = buffer.getvalue()

        # The ANSI SGR codes for the two colours, not the literal tag text.
        assert "\x1b[32m" in rendered
        assert "\x1b[31m" in rendered
        assert "[green]" not in rendered
        assert "[red]" not in rendered

    def test_a_driver_error_in_the_fallback_note_is_printed_verbatim(self) -> None:
        """The note interpolates a driver message, which routinely contains brackets."""
        detail = 'Binder Error: Referenced column "x[0]" not found'
        report = ViewCheckReport(
            view_name="v",
            rows=[
                FieldCheckRow(
                    name="x",
                    committed="str",
                    probed="str",
                    route=ROUTE_METADATA,
                    status=STATUS_MATCH,
                )
            ],
            has_drift=False,
            probe_error=detail,
        )

        output = _render_to_text(report)

        assert "x[0]" in output
        assert "Note:" in output

    def test_a_bracketed_view_name_does_not_crash_the_absent_class_note(
        self, duckdb_file_backed_db: Path, tmp_path: Path
    ) -> None:
        """``_run_check``'s ``{view_name!r}`` note goes through the same parser."""
        model = tmp_path / "models.py"
        model.write_text(
            "from semolina import Dimension, SemanticView\n\n\n"
            'class Other(SemanticView, view="other_view"):\n'
            "    country = Dimension[str]()\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "codegen",
                "[/red]missing_view",
                "--check",
                "--model",
                str(model),
                "--backend",
                "duckdb",
                "--database",
                str(duckdb_file_backed_db),
            ],
        )

        # Whatever the outcome, it is one of the CLI's own exit codes rather than a
        # MarkupError traceback, and the note names the view it could not find.
        assert result.exit_code in (EXIT_VIEW_NOT_FOUND, EXIT_ANNOTATION_DRIFT), result.stderr
        assert "MarkupError" not in result.stderr
        assert "[/red]missing_view" in result.stderr


class TestAnnotationCheckAgainstLiveDuckDB:
    """The end-to-end contract, over a real file-backed DuckDB semantic view."""

    @pytest.mark.parametrize("view_name", ['"sales_view', 'main."sales.view"'])
    def test_an_invalid_view_name_is_an_error_message_not_a_traceback(
        self, view_name: str, duckdb_file_backed_db: Path, tmp_path: Path
    ) -> None:
        """``quote_table_name``'s ValueError reaches a ``--check`` user as an error line."""
        model = tmp_path / "models.py"
        _generate_model(duckdb_file_backed_db, model)

        result = runner.invoke(
            app,
            [
                "codegen",
                view_name,
                "--check",
                "--model",
                str(model),
                "--backend",
                "duckdb",
                "--database",
                str(duckdb_file_backed_db),
            ],
        )

        assert result.exit_code == 1, result.stderr
        assert isinstance(result.exception, SystemExit)
        assert "Error:" in result.stderr

    def test_a_freshly_generated_model_exits_0_with_empty_stdout(
        self, duckdb_file_backed_db: Path, tmp_path: Path
    ) -> None:
        model = tmp_path / "models.py"
        _generate_model(duckdb_file_backed_db, model)

        result = runner.invoke(
            app,
            [
                "codegen",
                "sales_view",
                "--check",
                "--model",
                str(model),
                "--backend",
                "duckdb",
                "--database",
                str(duckdb_file_backed_db),
            ],
        )

        assert result.exit_code == 0, result.stderr
        assert result.stdout == ""

    def test_a_check_that_fell_back_to_metadata_exits_6(
        self, duckdb_file_backed_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A probe that failed is a check that was not performed, even with no drift (A33).

        The fallback compares the model with the catalogue -- the source that wrote it -- so
        it reports a match and exited 0, indistinguishable in CI from a probed pass. It now
        exits ``EXIT_PROBE_FAILED``, with the report and the note still printed.
        """
        from semolina.cli.codegen import EXIT_PROBE_FAILED

        model = tmp_path / "models.py"
        _generate_model(duckdb_file_backed_db, model)

        def refuse(cursor: object, sql: str, params: object) -> None:
            raise RuntimeError("probe unavailable in this test")

        monkeypatch.setattr("semolina.codegen.annotation_check.probe_schema", refuse)
        result = runner.invoke(
            app,
            [
                "codegen",
                "sales_view",
                "--check",
                "--output",
                str(model),
                "--backend",
                "duckdb",
                "--database",
                str(duckdb_file_backed_db),
            ],
        )

        assert result.exit_code == EXIT_PROBE_FAILED, result.stderr
        assert ROUTE_METADATA in result.stderr
        assert "probe unavailable" in _diagnostics(result), result.stderr

    def test_the_route_is_reported_on_a_clean_run(
        self, duckdb_file_backed_db: Path, tmp_path: Path
    ) -> None:
        """A green ``--check`` still says what it checked against."""
        model = tmp_path / "models.py"
        _generate_model(duckdb_file_backed_db, model)

        result = runner.invoke(
            app,
            [
                "codegen",
                "sales_view",
                "--check",
                "--model",
                str(model),
                "--backend",
                "duckdb",
                "--database",
                str(duckdb_file_backed_db),
            ],
        )

        assert result.exit_code == 0
        assert ROUTE_EXECUTE_SCHEMA in result.stderr

    def test_an_edited_annotation_exits_with_the_drift_code(
        self, duckdb_file_backed_db: Path, tmp_path: Path
    ) -> None:
        model = tmp_path / "models.py"
        source = _generate_model(duckdb_file_backed_db, model)
        model.write_text(
            source.replace(
                "revenue = Metric[int | None]()", "revenue = Metric[decimal.Decimal | None]()"
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "codegen",
                "sales_view",
                "--check",
                "--model",
                str(model),
                "--backend",
                "duckdb",
                "--database",
                str(duckdb_file_backed_db),
            ],
        )

        assert result.exit_code == EXIT_ANNOTATION_DRIFT, result.stderr
        assert result.stdout == ""
        # The table names the field and marks it. Asserted on short, unwrappable tokens:
        # rich wraps a long cell at the terminal width, so a longer substring is not a
        # stable assertion.
        assert "revenue" in result.stderr
        assert "drift" in result.stderr

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_check_run_fetches_no_data_rows(
        self, duckdb_file_backed_db: Path, tmp_path: Path
    ) -> None:
        """
        ``--check`` runs "without executing a query for rows", at the CLI seam.

        The guard permits catalogue fetches (``DESCRIBE``/``SHOW``), which is what
        introspection is and what the generation path has always done, and refuses a fetch
        from anything else. The model fixture is written before the guard's scope matters
        because generation is inside it too.
        """
        model = tmp_path / "models.py"
        _generate_model(duckdb_file_backed_db, model)

        result = runner.invoke(
            app,
            [
                "codegen",
                "sales_view",
                "--check",
                "--model",
                str(model),
                "--backend",
                "duckdb",
                "--database",
                str(duckdb_file_backed_db),
            ],
        )

        assert result.exit_code == 0, result.stderr

    def test_a_view_with_no_class_in_the_model_is_named(
        self, duckdb_file_backed_db: Path, tmp_path: Path
    ) -> None:
        model = tmp_path / "models.py"
        model.write_text(
            "from semolina import Dimension, SemanticView\n\n\n"
            'class Other(SemanticView, view="other_view"):\n'
            "    country = Dimension[str]()\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "codegen",
                "sales_view",
                "--check",
                "--model",
                str(model),
                "--backend",
                "duckdb",
                "--database",
                str(duckdb_file_backed_db),
            ],
        )

        assert result.exit_code == EXIT_ANNOTATION_DRIFT, result.stderr
        assert "sales_view" in result.stderr

    def test_the_generation_path_is_unchanged(self, duckdb_file_backed_db: Path) -> None:
        """Without ``--check``, model source still goes to stdout and the exit code is 0."""
        result = runner.invoke(
            app,
            [
                "codegen",
                "sales_view",
                "--backend",
                "duckdb",
                "--database",
                str(duckdb_file_backed_db),
            ],
        )

        assert result.exit_code == 0, result.stderr
        assert "class SalesView(SemanticView" in result.stdout
