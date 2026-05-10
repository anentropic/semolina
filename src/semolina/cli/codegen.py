"""Codegen subcommand: introspect warehouse semantic views and generate Python model classes."""

from __future__ import annotations

import sys
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
    if backend_spec == "snowflake":
        from semolina.engines.snowflake import SnowflakeEngine
        from semolina.testing.credentials import SnowflakeCredentials

        creds = SnowflakeCredentials.load()
        params = creds.model_dump(by_alias=True)
        params["password"] = creds.password.get_secret_value()
        return SnowflakeEngine(**params)
    elif backend_spec == "databricks":
        from semolina.engines.databricks import DatabricksEngine
        from semolina.testing.credentials import DatabricksCredentials

        creds = DatabricksCredentials.load()
        params = creds.model_dump(by_alias=True)
        params["access_token"] = creds.access_token.get_secret_value()
        return DatabricksEngine(**params)
    elif backend_spec == "duckdb":
        if database is None:
            raise typer.BadParameter(
                "DuckDB backend requires a database path. "
                "Use --database or set DUCKDB_DATABASE environment variable."
            )
        from semolina.engines.duckdb import DuckDBEngine

        return DuckDBEngine(database=database)
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

    from semolina.codegen.python_renderer import render_and_format

    source = render_and_format(introspected_views)
    typer.echo(source)
