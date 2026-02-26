"""Codegen subcommand: introspect warehouse semantic views and generate Python model classes."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console

if TYPE_CHECKING:
    from cubano.codegen.introspector import IntrospectedView
    from cubano.engines.base import Engine

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


def _resolve_backend(backend_spec: str) -> Engine:
    """
    Resolve a backend specifier string to an Engine instance.

    Recognises the shorthand aliases ``'snowflake'`` and ``'databricks'``, and
    also accepts any fully-qualified ``dotted.path.ClassName`` string which is
    dynamically imported and instantiated with no arguments.

    Args:
        backend_spec: One of ``'snowflake'``, ``'databricks'``, or a dotted
            import path such as ``'mypackage.backends.CustomEngine'``.

    Returns:
        Engine: An instantiated engine ready for introspection calls.

    Raises:
        typer.BadParameter: If the specifier is not recognised or cannot be
            imported.
    """
    if backend_spec == "snowflake":
        from cubano.engines.snowflake import SnowflakeEngine
        from cubano.testing.credentials import SnowflakeCredentials

        creds = SnowflakeCredentials.load()
        params = creds.model_dump(by_alias=True)
        params["password"] = creds.password.get_secret_value()
        return SnowflakeEngine(**params)
    elif backend_spec == "databricks":
        from cubano.engines.databricks import DatabricksEngine
        from cubano.testing.credentials import DatabricksCredentials

        creds = DatabricksCredentials.load()
        params = creds.model_dump(by_alias=True)
        params["access_token"] = creds.access_token.get_secret_value()
        return DatabricksEngine(**params)
    else:
        import importlib

        module_path, _, class_name = backend_spec.rpartition(".")
        if not module_path:
            raise typer.BadParameter(
                f"Unknown backend {backend_spec!r}. "
                "Use 'snowflake', 'databricks', or a dotted import path."
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
            "--backend", "-b", help="Backend: snowflake, databricks, or dotted.path.ClassName"
        ),
    ],
) -> None:
    """Introspect warehouse semantic views and generate Cubano model classes."""
    from cubano.engines.base import CubanoConnectionError, CubanoViewNotFoundError

    try:
        engine = _resolve_backend(backend)
    except typer.BadParameter as e:
        _stderr.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=EXIT_INVALID_BACKEND) from e

    introspected_views: list[IntrospectedView] = []
    for view_name in views:
        try:
            introspected = engine.introspect(view_name)
            introspected_views.append(introspected)
        except CubanoViewNotFoundError as e:
            _stderr.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=EXIT_VIEW_NOT_FOUND) from e
        except CubanoConnectionError as e:
            _stderr.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=EXIT_CONNECTION_ERROR) from e
        except RuntimeError as e:
            _stderr.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=1) from e

    from cubano.codegen.python_renderer import render_and_format

    source = render_and_format(introspected_views)
    typer.echo(source)
