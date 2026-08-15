"""
DTO codegen subcommand: generate Pydantic result DTOs from importable query objects.

A sibling command rather than a flag on ``semolina codegen`` (O-02, decided 2026-08-15).
The two commands share every option they have in common — ``--backend``, ``--database``,
the diagnostics idiom and the exit-code vocabulary — and they are reused from
:mod:`semolina.cli.codegen` rather than copied. What they do not share is the *positional*
argument: ``codegen`` takes schema-qualified warehouse view names, this one takes dotted
Python import paths. A different noun in the same slot is the ambiguity
``_resolve_check_model`` was written to avoid, not one to repeat, and a separate command
also keeps ``EXIT_PROBE_FAILED`` out of a table where it can never fire.

(A literal rather than a ``:data:`` cross-reference: a module docstring is rendered by
sphinx-autoapi before the module's own data objects are registered, so the role resolves to
nothing and ``just docs-build`` fails on it. The roles inside the functions below are past
that point and do resolve.)

The cost of the split is a second exit-code table. ``docs/src/how-to/dto-codegen.rst``
duplicates the epilog registered for this command in :mod:`semolina.cli`, and the two must
agree — the same standing obligation the ``codegen`` epilog already carries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

# Imported rather than re-implemented, private names included. `_resolve_backend` is the
# published `--backend` contract (shorthand aliases plus `dotted.path.ClassName`) and
# `_labelled` is the one place this CLI's "never hand rich a bare string" rule lives; a
# second copy of either would drift from the command users already have.
from semolina.cli.codegen import (
    EXIT_CONNECTION_ERROR,
    EXIT_INVALID_BACKEND,
    EXIT_VIEW_NOT_FOUND,
    _adbc_connection_errors,
    _labelled,
    _resolve_backend,
    _stderr,
)

if TYPE_CHECKING:
    from semolina.codegen.dto_renderer import ProbedQuery
    from semolina.engines.base import Engine
    from semolina.query import _Query

# A probe failure, or a projected field the probed result carries no column for.
#
# 6 rather than 5: 5 is `EXIT_ANNOTATION_DRIFT` and means "your committed model is stale",
# which is the caller's to fix by regenerating. This one means the warehouse could not
# describe the query at all, and no file was written. A CI job that cannot tell those apart
# has to treat both the same — the same reasoning that gave drift its own code in the first
# place.
EXIT_PROBE_FAILED = 6


def _resolve_class_names(dotted_paths: list[str], *, name: str | None) -> list[str]:
    """
    Validate the ``--name`` pairing and name the class each dotted path becomes.

    ``--name`` renames one class, so it is only meaningful when exactly one query was
    given — the same coupled-flag validation ``semolina.cli.codegen._resolve_check_model``
    performs for ``--check`` / ``--model``, and raised the same way so the command funnels
    it to :data:`~semolina.cli.codegen.EXIT_INVALID_BACKEND`.

    Every name is also checked to be a usable Python identifier, whether it came from
    ``--name`` or from :func:`~semolina.codegen.query_resolver.class_name_for`. The generated
    file declares ``class <name>(pydantic.BaseModel):`` with the name written in as a bare
    token, so it is the one value on this path that no escaper can make safe — a ``--name``
    carrying a newline and a statement produces a *valid* module that runs that statement
    when the user imports it (threat T-50-01). ``class_name_for`` sanitises nothing on its
    own either: it capitalises the parts of the attribute name it was given, so a path whose
    attribute part is empty or does not start an identifier reaches the same token.
    :func:`~semolina.codegen.query_resolver.is_valid_class_name` is the check; refusing here
    is what stands in for the quoting that every other interpolated value gets.

    Duplicate names are refused as well. Several queries render into one module (O-03), and
    two classes with the same name in one file is not an error Python reports: the second
    definition silently replaces the first, so the user would get a file that imports
    cleanly and is missing a DTO. Two queries whose *attribute* names collide across
    modules is the ordinary way to reach that.

    Args:
        dotted_paths: The positional dotted paths, in the order they were given.
        name: The ``--name`` override, if any.

    Returns:
        One class name per dotted path, in the same order.

    Raises:
        typer.BadParameter: If ``--name`` was passed alongside more than one query, if any
            name is not a valid Python class name, or if two paths would produce the same
            class name.
    """
    from semolina.codegen.query_resolver import class_name_for, is_valid_class_name

    if name is not None:
        if len(dotted_paths) != 1:
            msg = (
                f"--name renames a single generated class, but {len(dotted_paths)} query "
                "paths were given. Pass one path, or drop --name and let each class be "
                "named after its query attribute."
            )
            raise typer.BadParameter(msg)
        if not is_valid_class_name(name):
            msg = (
                f"--name {name!r} is not a valid Python class name. The value becomes the "
                "generated class's own name, written into the file as a bare token rather "
                "than as a string, so it has to be a single Python identifier and not a "
                "keyword -- RevenueByRegion, say."
            )
            raise typer.BadParameter(msg)
        return [name]

    class_names = [class_name_for(path.rpartition(".")[2]) for path in dotted_paths]
    seen: dict[str, str] = {}
    for path, class_name in zip(dotted_paths, class_names, strict=True):
        if not is_valid_class_name(class_name):
            msg = (
                f"{path!r} would generate a class named {class_name!r}, which is not a valid "
                "Python identifier. Rename the query attribute, or pass --name to name the "
                "generated class yourself."
            )
            raise typer.BadParameter(msg)
        if class_name in seen:
            msg = (
                f"{path!r} and {seen[class_name]!r} both generate a class named "
                f"{class_name!r}, and one file cannot carry two. Generate them separately, "
                "using --name to rename one."
            )
            raise typer.BadParameter(msg)
        seen[class_name] = path
    return class_names


def _resolve_queries(dotted_paths: list[str]) -> list[_Query]:
    """
    Import every dotted path and return the query objects they name.

    :func:`semolina.codegen.query_resolver.resolve_query` reports every failure as a
    ``ValueError`` whose message already names the path, the module or the type it found
    instead; this converts that into the CLI's own vocabulary so an unresolvable path exits
    2 with a message rather than a traceback.

    Args:
        dotted_paths: The positional dotted paths.

    Returns:
        The resolved queries, in the same order.

    Raises:
        typer.BadParameter: If any path carries no module part, names a module that cannot
            be imported, names no such attribute, or names something that is not a query.
    """
    from semolina.codegen.query_resolver import resolve_query

    queries: list[_Query] = []
    for path in dotted_paths:
        try:
            queries.append(resolve_query(path))
        except ValueError as e:
            raise typer.BadParameter(str(e)) from e
    return queries


def _backend_label(backend_spec: str, engine: Engine) -> str:
    """
    Name the backend the generated file's provenance header will claim.

    The header is the generated DTO's evidence about where its aliases and annotations came
    from, and :func:`semolina.codegen.dto_renderer.render_dtos` refuses a label that
    contradicts the dialect that answered. Passing ``--backend`` through verbatim would
    satisfy that for the three shorthand aliases and break it for
    ``--backend mypackage.backends.CustomEngine``: a custom engine built on
    ``DuckDBDialect`` answers ``duckdb``, so the raw spec string would be refused for
    disagreeing with a dialect it does not contradict in any way a reader cares about.

    The dialect's own answer is therefore preferred where this repo has one, and the spec
    string is the fallback for a dialect from outside it — which is the only case where the
    caller's word is the only name there is.

    Args:
        backend_spec: The ``--backend`` value as given.
        engine: The resolved engine.

    Returns:
        The backend label to put in the header.
    """
    from semolina.codegen.dto_renderer import _known_backend_label

    known = _known_backend_label(engine.dialect)
    return known if known is not None else backend_spec


def _probe_all(
    engine: Engine,
    dotted_paths: list[str],
    queries: list[_Query],
    class_names: list[str],
) -> list[ProbedQuery]:
    """
    Probe every query's result schema, mapping each failure onto its exit code.

    There is deliberately no ``except Exception`` here, and none anywhere else on this path.
    ``annotation_check._probe_view`` can afford one because a failed probe there degrades to
    warehouse metadata and says so; DTO codegen has no metadata route, so degrading would
    mean writing a file whose annotations came from nowhere. Every class caught below is
    named, and anything unnamed reaches typer as an unhandled error rather than becoming a
    generated file.

    Args:
        engine: The resolved engine.
        dotted_paths: The dotted paths, for the provenance header.
        queries: The resolved queries, in the same order.
        class_names: The class names, in the same order.

    Returns:
        One probed query per input, in the same order.

    Raises:
        typer.Exit: :data:`~semolina.cli.codegen.EXIT_VIEW_NOT_FOUND` (3),
            :data:`~semolina.cli.codegen.EXIT_CONNECTION_ERROR` (4),
            :data:`EXIT_PROBE_FAILED` (6) or 1, depending on what failed.
    """
    import adbc_driver_manager

    from semolina.codegen.dto_renderer import probe_query
    from semolina.engines.base import SemolinaConnectionError, SemolinaViewNotFoundError

    probed: list[ProbedQuery] = []
    for path, query, class_name in zip(dotted_paths, queries, class_names, strict=True):
        try:
            probed.append(probe_query(engine, query, class_name=class_name, dotted_path=path))
        # Semolina's own two RuntimeError subclasses, before the bare RuntimeError arm.
        # Neither is raised by anything DTO codegen calls today: they come from
        # `Engine.introspect`, and DTO codegen calls no `introspect()` (D-08). They are
        # handled because `--backend dotted.path.ClassName` accepts a user's own `Engine`,
        # whose `connect()` may raise either, and because a code that means "view not
        # found" must not mean something else on a sibling command.
        except SemolinaViewNotFoundError as e:
            _stderr.print(_labelled("Error:", "bold red", f" {e}"))
            raise typer.Exit(code=EXIT_VIEW_NOT_FOUND) from e
        except SemolinaConnectionError as e:
            _stderr.print(_labelled("Error:", "bold red", f" {e}"))
            raise typer.Exit(code=EXIT_CONNECTION_ERROR) from e
        # The driver's own hierarchy: `adbc_driver_manager.Error` is the DBAPI base, and
        # `probe.NOT_IMPLEMENTED_ERRORS` are three of its subclasses. A refused
        # `ExecuteSchema` never arrives here — `probe_schema` catches that and takes the
        # zero-row route — so what reaches this arm is a probe that failed on both routes.
        except adbc_driver_manager.Error as e:
            _stderr.print(
                _labelled(
                    "Error:",
                    "bold red",
                    f" could not probe the result schema for {path}: {type(e).__name__}: {e}",
                )
            )
            raise typer.Exit(code=EXIT_PROBE_FAILED) from e
        except RuntimeError as e:
            _stderr.print(_labelled("Error:", "bold red", f" {e}"))
            raise typer.Exit(code=1) from e
    return probed


def codegen_dto(
    queries: Annotated[
        list[str],
        typer.Argument(
            metavar="QUERY_PATHS...",
            help=(
                "Dotted paths to module-level query objects, e.g. "
                "myapp.queries.revenue_by_region. Resolving one imports and runs that "
                "module. Several are emitted into one output block."
            ),
        ),
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
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            help=(
                "Override the generated class name, which otherwise comes from the query "
                "attribute (revenue_by_region -> RevenueByRegion). One query path only."
            ),
        ),
    ] = None,
) -> None:
    """
    Generate Pydantic result DTOs from importable query objects.

    Each QUERY_PATH names a module-level query, e.g.
    myapp.queries.revenue_by_region. The query's filter, ordering and
    limit are ignored -- the DTO describes the projection and nothing
    else -- and the annotations come from the result schema the
    warehouse resolves for it, not from declared model field types.

    Generated source goes to stdout and every diagnostic goes to
    stderr, so redirecting stdout yields a file you can import.

    Resolving a QUERY_PATH IMPORTS the module it names, which runs that
    module top to bottom: connections open, environment variables are
    read, decorators fire. That is inherent to generating code from an
    importable object, and it is what --backend dotted.path.ClassName
    has always done. Point this at code you trust.

    The working directory is APPENDED to sys.path, never prepended, so
    a project-root package resolves without being installed while a
    file in the working directory cannot shadow an installed
    distribution of the same name.

    A generated DTO is pinned to the backend it was probed against: its
    aliases are that warehouse's result-column spellings and its
    annotations reflect that warehouse's aggregation result typing. The
    file says so in its own header, and another warehouse needs a
    regenerated class.
    """
    # The lines above are kept short on purpose. Typer renders help text through rich with
    # single line breaks preserved, so a docstring wrapped at this file's 100-character
    # limit renders as alternating long and orphaned lines in an 80-column terminal.
    # `queries` is the positional dotted paths; the resolved query objects are separate.
    dotted_paths = queries

    try:
        # Ordered cheapest-and-least-consequential first. The --name pairing is pure
        # argument validation; resolving the paths executes the user's modules; resolving
        # the backend opens a pool. A typo in a path should not have opened a warehouse
        # connection, and a bad flag pairing should not have imported anything.
        class_names = _resolve_class_names(dotted_paths, name=name)
        resolved = _resolve_queries(dotted_paths)
        engine = _resolve_backend(backend, database=database)
    except typer.BadParameter as e:
        _stderr.print(_labelled("Error:", "bold red", f" {e}"))
        raise typer.Exit(code=EXIT_INVALID_BACKEND) from e
    except _adbc_connection_errors() as e:
        # `_resolve_backend` does not merely name a backend: `create_engine` builds the
        # adbc-poolhouse pool, and poolhouse opens a connection while doing it. So the
        # driver's own failure to reach the database surfaces HERE, before `_probe_all` and
        # its `adbc_driver_manager.Error` arm exist to catch it. Left unhandled it exited 1
        # with a raw traceback and an empty stderr, while the epilog documented 4 for
        # exactly this (UAT test 7, measured 2026-08-16).
        _stderr.print(_labelled("Error:", "bold red", f" could not connect to the warehouse: {e}"))
        raise typer.Exit(code=EXIT_CONNECTION_ERROR) from e

    probed = _probe_all(engine, dotted_paths, resolved, class_names)

    from semolina.codegen.dto_renderer import render_and_format_dtos
    from semolina.codegen.python_renderer import ruff_available

    try:
        source = render_and_format_dtos(probed, backend_label=_backend_label(backend, engine))
    except ValueError as e:
        # `_alias_for` raising: a projected field matches no result column, or matches more
        # than one. The message already names the field, every candidate tried and every
        # column the result carried, which is the whole remedy — a DTO whose alias never
        # binds is otherwise accepted, committed, and reports `missing` at `.into()` time in
        # a service with nothing pointing back at the generated file.
        _stderr.print(_labelled("Error:", "bold red", f" {e}"))
        raise typer.Exit(code=EXIT_PROBE_FAILED) from e

    typer.echo(source)
    if not ruff_available():
        _stderr.print(
            _labelled(
                "Note:",
                "yellow",
                " ruff is not installed; generated output is unformatted. Install "
                "semolina[codegen-lint] for formatted output.",
            )
        )
