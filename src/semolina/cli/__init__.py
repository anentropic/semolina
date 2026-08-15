"""
Semolina command-line interface.

Entry point for the `semolina` CLI command. Registers subcommands
for code generation and future tooling.
"""

import typer

from .codegen import codegen
from .dto_codegen import codegen_dto

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
        # Not "invalid backend": --check and --model without each other also exit 2, and a
        # message naming only the backend sends you looking in the wrong place.
        "  [yellow]2[/yellow]  Invalid option -- an unrecognised or omitted "
        "[bold]--backend[/bold], or [bold]--check[/bold] and [bold]--model[/bold] "
        "passed without each other\n\n"
        "  [red]3[/red]  View not found in the warehouse\n\n"
        "  [red]4[/red]  Connection or authentication failure\n\n"
        # Yellow, not red: the colour convention here is green for success, yellow for a
        # caller-actionable outcome, red for a warehouse-side failure. Drift is the caller's
        # to fix. This table is duplicated in docs/src/how-to/codegen.rst; the two must agree.
        "  [yellow]5[/yellow]  Annotation drift -- a committed model no longer matches the "
        "result schema"
    ),
)(codegen)

app.command(
    "codegen-dto",
    epilog=(
        "[bold]Exit codes[/bold]\n\n"
        "  [green]0[/green]  Success\n\n"
        "  [yellow]1[/yellow]  Unexpected error\n\n"
        # Same wording as the codegen table's 2 for the shared half, plus this command's own
        # two pairings. A message naming only the backend would send you looking in the
        # wrong place when it was really the query path.
        "  [yellow]2[/yellow]  Invalid option -- an unrecognised or omitted "
        "[bold]--backend[/bold], a [bold]QUERY_PATH[/bold] that does not resolve to a query, "
        "or [bold]--name[/bold] passed with more than one query\n\n"
        "  [red]3[/red]  View not found in the warehouse\n\n"
        "  [red]4[/red]  Connection or authentication failure\n\n"
        # 5 is deliberately absent: it is `--check`'s annotation drift and this command has
        # no --check. Red, not yellow: the colour convention is green for success, yellow
        # for a caller-actionable outcome, red for a warehouse-side failure, and a probe
        # that fails is the warehouse declining to describe the query. This table is
        # duplicated in docs/src/how-to/dto-codegen.rst; the two must agree.
        "  [red]6[/red]  Probe failed, or a projected field matched no result column -- no "
        "DTO was written"
    ),
)(codegen_dto)


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
