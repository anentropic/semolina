"""Codegen subcommand: introspect warehouse semantic views and generate Python model classes."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console

if TYPE_CHECKING:
    from semolina.codegen.annotation_check import ViewCheckReport
    from semolina.codegen.introspector import IntrospectedView
    from semolina.engines.base import Engine

# Diagnostics-only console: writes to stderr
# NOTE: _stderr is module-level for error messages outside the command function.
# Python source output uses typer.echo() so CliRunner captures it correctly.
#
# `stderr=True` with no `file=`: rich then resolves `sys.stderr` at *write* time. Passing
# `file=sys.stderr` pinned the stream captured at import, so anything that replaces
# `sys.stderr` afterwards — a test runner, an embedding process — silently lost every
# diagnostic this CLI emits. The destination is identical in normal use.
_stderr = Console(stderr=True)

# Exit code constants for scripted callers.
# Note: Typer also uses exit code 2 for missing required arguments (fires earlier).
# EXIT_INVALID_BACKEND=2 fires when --backend value is provided but unrecognized.
EXIT_INVALID_BACKEND = 2
EXIT_VIEW_NOT_FOUND = 3
EXIT_CONNECTION_ERROR = 4
# --check found annotation drift. Distinct from 1 ("the tool broke") on purpose: a CI job
# that cannot tell "your model is stale" from "codegen crashed" has to treat both the same,
# which means either failing builds on a crash or shipping stale models on a real drift.
EXIT_ANNOTATION_DRIFT = 5

# Canonical display names for built-in backends. ``str.capitalize()`` would
# mangle proper-noun casing (e.g. "Duckdb"), so map explicitly for user-facing
# error messages.
_BACKEND_LABELS = {"snowflake": "Snowflake", "databricks": "Databricks", "duckdb": "DuckDB"}


def _normalize_database_path(database: str) -> str:
    """
    Normalize a DuckDB database path, preserving the ``:memory:`` sentinel.

    Applies ``expanduser()`` + ``resolve(strict=False)`` to real paths so
    relative paths, absolute paths, and ``~`` expansion all work uniformly.
    The ``:memory:`` sentinel and empty strings pass through unchanged.

    The empty-string passthrough is intentional: ``Path("").resolve()`` would
    silently expand to the current working directory, masking a bug and
    producing an inconsistent error path. Leaving ``""`` unchanged lets
    DuckDB raise the same error it raises for any other invalid path.

    Args:
        database: A DuckDB database path or the ``":memory:"`` sentinel.

    Returns:
        Normalized absolute path, or the input unchanged for ``":memory:"``
        and empty strings.

    Example:
        .. code-block:: python

            from semolina.cli.codegen import _normalize_database_path

            _normalize_database_path(":memory:")
            # ':memory:'

            _normalize_database_path("~/analytics.db")
            # '/Users/you/analytics.db'
    """
    if database and database != ":memory:":
        database = str(Path(database).expanduser().resolve(strict=False))
    return database


def _resolve_backend(backend_spec: str, *, database: str | None = None) -> Engine:
    """
    Resolve a backend specifier string to an Engine instance.

    Recognises the shorthand aliases ``'snowflake'``, ``'databricks'``, and
    ``'duckdb'``, and also accepts any fully-qualified ``dotted.path.ClassName``
    string which is dynamically imported and instantiated with no arguments.

    Args:
        backend_spec: One of ``'snowflake'``, ``'databricks'``, ``'duckdb'``,
            or a dotted import path such as ``'mypackage.backends.CustomEngine'``.
        database: DuckDB database file path. Required when ``backend_spec``
            is ``'duckdb'``; ignored for other backends.

    Returns:
        Engine: An instantiated engine ready for introspection calls.

    Raises:
        typer.BadParameter: If the specifier is not recognised or cannot be
            imported, or if ``'duckdb'`` is requested without a database path.
    """
    if backend_spec in ("snowflake", "databricks", "duckdb"):
        from pydantic import ValidationError

        from semolina.config import create_engine, warehouse_config

        if backend_spec == "duckdb":
            if database is None:
                raise typer.BadParameter(
                    "DuckDB backend requires a database path. "
                    "Use --database or set DUCKDB_DATABASE environment variable."
                )
            from adbc_poolhouse import DuckDBConfig

            config = DuckDBConfig(database=_normalize_database_path(database), read_only=True)
            return create_engine(config)

        try:
            config = warehouse_config(backend_spec)
        except tomllib.TOMLDecodeError as e:
            raise typer.BadParameter(f"Invalid .semolina.toml: {e}") from e
        except ValidationError as e:
            label = _BACKEND_LABELS.get(backend_spec, backend_spec.capitalize())
            section = backend_spec
            env_prefix = backend_spec.upper()
            raise typer.BadParameter(
                f"{label} connection config missing or invalid. Set [connections.{section}] in "
                f".semolina.toml or {env_prefix}_* environment variables.\n{e}"
            ) from e
        return create_engine(config)
    else:
        import importlib

        module_path, _, class_name = backend_spec.rpartition(".")
        if not module_path:
            raise typer.BadParameter(
                f"Unknown backend {backend_spec!r}. "
                "Use 'snowflake', 'databricks', 'duckdb', or a dotted import path."
            )
        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            return cls()  # type: ignore[no-any-return]
        except (ImportError, AttributeError) as e:
            raise typer.BadParameter(f"Cannot import backend {backend_spec!r}: {e}") from e


def _resolve_check_model(*, check: bool, model: Path | None) -> Path | None:
    """
    Validate the ``--check`` / ``--model`` pairing and return the model path to check.

    ``--model`` is a separate option rather than an overload of the positional ``views``
    argument, which would be ambiguous — so the two have to be validated against each other.

    Args:
        check: Whether ``--check`` was passed.
        model: The ``--model`` path, if any.

    Returns:
        The model path when a check was requested, None when it was not.

    Raises:
        typer.BadParameter: If exactly one of the two was passed. Converted to
            ``EXIT_INVALID_BACKEND`` (2) by the caller, matching the file's existing idiom.
    """
    if check and model is None:
        raise typer.BadParameter(
            "--check requires --model PATH: the committed model file to check against the "
            "warehouse's current result schema."
        )
    if model is not None and not check:
        raise typer.BadParameter("--model is only meaningful with --check.")
    return model if check else None


def _render_check_report(report: ViewCheckReport) -> None:
    """
    Write one view's per-field verdict to stderr.

    Everything here goes to **stderr**: the module's convention is source to stdout and
    diagnostics to stderr, and a ``--check`` run emits no source at all. The table carries
    field names, annotation strings and routes — never a row value (threat T-48-22).

    The Route column is always present, drift or no drift. A green ``--check`` that fell back
    to warehouse metadata must not look identical to a probed one (threat T-48-24).

    Args:
        report: A ``ViewCheckReport``.
    """
    from rich.table import Table

    from semolina.codegen.annotation_check import ROUTE_METADATA, STATUS_DRIFT

    table = Table(title=f"semolina codegen --check: {report.view_name}", title_justify="left")
    table.add_column("Field")
    table.add_column("Committed")
    table.add_column("Probed (result schema)")
    table.add_column("Route")
    table.add_column("Status")
    for row in report.rows:
        style = "red" if row.status == STATUS_DRIFT else "green"
        table.add_row(
            row.name, row.committed, row.probed, row.route, f"[{style}]{row.status}[/{style}]"
        )
    _stderr.print(table)

    if any(row.route == ROUTE_METADATA for row in report.rows):
        detail = f" ({report.probe_error})" if report.probe_error else ""
        _stderr.print(
            f"[yellow]Note:[/yellow] the result-schema probe was unavailable{detail}; the "
            "annotations above were compared against warehouse metadata instead, which is "
            "not the same thing."
        )


def _run_check(engine: Engine, views: list[str], model: Path) -> None:
    """
    Run ``--check`` over every requested view and exit with the right code.

    Args:
        engine: The resolved engine.
        views: Requested view names.
        model: Path to the committed model file.

    Raises:
        typer.Exit: Always — 0 when every annotation matches, ``EXIT_ANNOTATION_DRIFT`` when
            any drifted, and the file's existing codes for a bad file or a warehouse error.
    """
    from semolina.codegen.annotation_check import check_view
    from semolina.codegen.model_reader import read_committed_model
    from semolina.engines.base import SemolinaConnectionError, SemolinaViewNotFoundError

    try:
        committed_models = read_committed_model(model)
    except ValueError as e:
        # A missing or malformed --model file is the user's, and deserves the message rather
        # than a traceback. read_committed_model's ValueError names the path and nothing else.
        _stderr.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    by_view = {m.view_name: m for m in committed_models}

    drift = False
    for view_name in views:
        committed = by_view.get(view_name)
        if committed is None:
            _stderr.print(
                f"[yellow]Note:[/yellow] {model} declares no model class for view "
                f"{view_name!r}; every field of it reports as absent."
            )
        try:
            report = check_view(engine, view_name, committed)
        except SemolinaViewNotFoundError as e:
            _stderr.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=EXIT_VIEW_NOT_FOUND) from e
        except SemolinaConnectionError as e:
            _stderr.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=EXIT_CONNECTION_ERROR) from e
        except RuntimeError as e:
            _stderr.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=1) from e

        _render_check_report(report)
        drift = drift or report.has_drift

    if drift:
        raise typer.Exit(code=EXIT_ANNOTATION_DRIFT)


def codegen(
    views: Annotated[
        list[str],
        typer.Argument(help="Schema-qualified view names (e.g. my_schema.my_view)"),
    ],
    backend: Annotated[
        str,
        typer.Option(
            "--backend",
            "-b",
            help="Backend: snowflake, databricks, duckdb, or dotted.path.ClassName",
        ),
    ],
    database: Annotated[
        str | None,
        typer.Option(
            "--database",
            "-d",
            help="DuckDB database file path (or set DUCKDB_DATABASE env var)",
            envvar="DUCKDB_DATABASE",
        ),
    ] = None,
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help=(
                "Report whether a committed model's annotations still match the warehouse's "
                "current result schema. Writes nothing to stdout; exits 5 on drift. "
                "Requires --model."
            ),
        ),
    ] = False,
    model: Annotated[
        Path | None,
        typer.Option("--model", help="Path to the committed model file to check"),
    ] = None,
) -> None:
    """Introspect warehouse semantic views and generate Semolina model classes."""
    from semolina.engines.base import SemolinaConnectionError, SemolinaViewNotFoundError

    try:
        check_model = _resolve_check_model(check=check, model=model)
        engine = _resolve_backend(backend, database=database)
    except typer.BadParameter as e:
        _stderr.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=EXIT_INVALID_BACKEND) from e

    if check_model is not None:
        # A --check run emits no model source, so it branches before render_and_format.
        _run_check(engine, views, check_model)
        return

    introspected_views: list[IntrospectedView] = []
    for view_name in views:
        try:
            introspected = engine.introspect(view_name)
            introspected_views.append(introspected)
        except SemolinaViewNotFoundError as e:
            _stderr.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=EXIT_VIEW_NOT_FOUND) from e
        except SemolinaConnectionError as e:
            _stderr.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=EXIT_CONNECTION_ERROR) from e
        except RuntimeError as e:
            _stderr.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=1) from e

    from semolina.codegen.python_renderer import render_and_format, ruff_available

    source = render_and_format(introspected_views)
    typer.echo(source)
    if not ruff_available():
        _stderr.print(
            r"[yellow]Note:[/yellow] ruff is not installed; generated output is "
            r"unformatted. Install [bold]semolina\[codegen-lint][/bold] for formatted "
            r"output."
        )
