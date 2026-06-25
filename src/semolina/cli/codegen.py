"""Codegen subcommand: introspect warehouse semantic views and generate Python model classes."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console

if TYPE_CHECKING:
    from semolina.codegen.introspector import IntrospectedView
    from semolina.engines.base import Engine

# Diagnostics-only console: writes to stderr
# NOTE: _stderr is module-level for error messages outside the command function.
# Python source output uses typer.echo() so CliRunner captures it correctly.
_stderr = Console(file=sys.stderr, stderr=True)

# Exit code constants for scripted callers.
# Note: Typer also uses exit code 2 for missing required arguments (fires earlier).
# EXIT_INVALID_BACKEND=2 fires when --backend value is provided but unrecognized.
EXIT_INVALID_BACKEND = 2
EXIT_VIEW_NOT_FOUND = 3
EXIT_CONNECTION_ERROR = 4

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
        except ValidationError as e:
            label = _BACKEND_LABELS.get(backend_spec, backend_spec.capitalize())
            section = backend_spec
            env_prefix = backend_spec.upper()
            raise typer.BadParameter(
                f"{label} connection config not found. Set [connections.{section}] in "
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
) -> None:
    """Introspect warehouse semantic views and generate Semolina model classes."""
    from semolina.engines.base import SemolinaConnectionError, SemolinaViewNotFoundError

    try:
        engine = _resolve_backend(backend, database=database)
    except typer.BadParameter as e:
        _stderr.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=EXIT_INVALID_BACKEND) from e

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
