"""
Semolina command-line interface.

Entry point for the `semolina` CLI command. Registers subcommands
for code generation and future tooling.
"""

import typer

from .codegen import codegen

app = typer.Typer(
    name="semolina",
    help="Semolina — warehouse-native semantic view tooling.",
    no_args_is_help=True,
    add_completion=False,
)

app.command(
    "codegen",
    epilog=(
        "[bold]Exit codes[/bold]\n\n"
        "  [green]0[/green]  Success\n\n"
        "  [yellow]1[/yellow]  Unexpected error\n\n"
        "  [yellow]2[/yellow]  Invalid [bold]--backend[/bold] value (or omitted)\n\n"
        "  [red]3[/red]  View not found in the warehouse\n\n"
        "  [red]4[/red]  Connection or authentication failure"
    ),
)(codegen)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        from semolina import __version__

        typer.echo(f"semolina {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Semolina — warehouse-native semantic view tooling."""
