"""
DTO codegen subcommand: generate Pydantic result DTOs from the queries a project runs.

A sibling command rather than a flag on ``semolina codegen`` (O-02, decided 2026-08-15).
The two commands share every option they have in common — ``--backend``, ``--database``,
the diagnostics idiom and the exit-code vocabulary — and they are reused from
:mod:`semolina.cli.codegen` rather than copied. What they do not share is the *positional*
argument: ``codegen`` takes schema-qualified warehouse view names, this one takes dotted
Python import paths. A different noun in the same slot is the ambiguity
``_resolve_check_model`` was written to avoid, not one to repeat. The exit codes are one
table for both commands (``semolina.cli.codegen.exit_code_for``), so the same exception at
the same stage exits the same way on either.

Both commands now carry a ``--check``, and the two mean the same thing: compare a committed
generated file against what the warehouse says today, write nothing, exit 5 on drift. Both
read the file ``--output`` names (``codegen`` also accepts its older ``--model``), and here
in config mode ``--output`` already has a value, so ``semolina codegen-dto --check`` on its
own verifies exactly the file ``semolina codegen-dto`` on its own would write.

There are three routes to the same generated file, and they differ only in where the list of
DTOs comes from:

* **dotted paths** — the original route. Names module-level query objects, and generating
  from one imports the module that holds it.
* **``--view`` with ``--metrics`` / ``--dimensions``** — names a view and the fields to
  project, with no model class and no query module written anywhere. Imports nothing.
* **``[tool.semolina.dto]`` in ``pyproject.toml``** — the declared form of the other two, so
  a project regenerates every DTO it has with a bare ``semolina codegen-dto``.

The three are mutually exclusive per invocation. They converge on one list of
:class:`~semolina.codegen.dto_config.DtoEntry` before anything is imported or connected to,
which is what keeps the rest of this module — class naming, probing, the exit codes —
written once rather than three times.

(A literal rather than a ``:data:`` cross-reference: a module docstring is rendered by
sphinx-autoapi before the module's own data objects are registered, so the role resolves to
nothing and ``just docs-build`` fails on it. The roles inside the functions below are past
that point and do resolve.)

The cost of the split is a second published copy of that table. The mapping is shared, but
each command documents the cases it can reach in its own epilog, registered in
:mod:`semolina.cli`. ``docs/src/how-to/dto-codegen.rst`` duplicates this command's, and the
two must agree — the same standing obligation the ``codegen`` epilog already carries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

# Imported rather than re-implemented, private names included. `_resolve_backend` is the
# published `--backend` contract (shorthand aliases plus `dotted.path.ClassName`) and
# `_labelled` is the one place this CLI's "never hand rich a bare string" rule lives; a
# second copy of either would drift from the command users already have.
from semolina.cli.codegen import (
    EXIT_PROBE_FAILED,
    STAGE_SETUP,
    STAGE_WAREHOUSE,
    _labelled,
    _resolve_backend,
    _stderr,
    check_output,
    emit_source,
    exit_for,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from semolina.codegen.dto_check import DtoCheckReport
    from semolina.codegen.dto_config import DtoConfig, DtoEntry
    from semolina.codegen.dto_renderer import ProbedQuery
    from semolina.engines.base import Engine
    from semolina.query import _Query

# `EXIT_PROBE_FAILED` (6) -- a probe failure, or a projected field the probed result carries
# no column for -- is imported above. It lives beside the other codes in
# `semolina.cli.codegen` since GEN-04 gave both commands one exception-to-exit table, and
# `codegen` now exits 6 for the same driver failure at the same stage.


@dataclass(frozen=True)
class _Inputs:
    """
    What the three routes reduce to, before anything is imported or connected to.

    Attributes:
        entries: The DTOs to generate, in emission order.
        backend: The resolved ``--backend`` value.
        database: The resolved DuckDB database path, or ``None``.
        output: The file to write, or ``None`` for stdout.
        committed_database: The config section's ``database``, whether or not it won, so an
            override can be announced. ``None`` outside config mode.
    """

    entries: tuple[DtoEntry, ...]
    backend: str
    database: str | None
    output: Path | None
    committed_database: str | None = None


@dataclass(frozen=True)
class _Request:
    """
    One DTO, with its query resolved and its class named.

    Attributes:
        origin: The provenance string the generated file records.
        class_name: The generated class's name.
        query: The query to probe.
    """

    origin: str
    class_name: str
    query: _Query


def _split_names(values: Sequence[str] | None) -> tuple[str, ...]:
    """
    Read a repeated, comma-separable option into a flat list of names.

    ``--metrics revenue --metrics cost`` and ``--metrics revenue,cost`` mean the same thing.
    Both spellings are accepted because both are what people type: the repeated form is what
    a shell loop generates, the comma form is what a person types by hand, and rejecting
    either would be a rule to remember rather than a property to rely on.

    Empty segments are dropped, so a trailing comma is not an error. What that leaves — an
    option that named nothing at all — is caught by
    :func:`semolina.codegen.query_resolver.build_query`, which has to answer for it anyway
    because the same emptiness can arrive from a config file.

    Args:
        values: The option's values, or ``None`` when it was not passed.

    Returns:
        The names, in the order given.
    """
    if not values:
        return ()
    return tuple(part.strip() for value in values for part in value.split(",") if part.strip())


def _entry_origin(entry: DtoEntry) -> str:
    """
    Describe where one entry's query comes from, for the provenance header and for errors.

    Args:
        entry: A declared DTO.

    Returns:
        The dotted path for a query entry, or the view-and-fields description for a view
        entry.
    """
    from semolina.codegen.query_resolver import ad_hoc_origin

    if entry.query is not None:
        return entry.query
    return ad_hoc_origin(entry.view or "", metrics=entry.metrics, dimensions=entry.dimensions)


def _derived_class_name(entry: DtoEntry) -> str:
    """
    Name the class an entry generates when it did not name one itself.

    A query entry is named after its attribute (``revenue_by_region`` ->
    ``RevenueByRegion``, D-05). A view entry has no attribute, so it is named after the
    view the way ``semolina codegen`` names that view's model —
    ``analytics.daily_sales`` -> ``DailySales``, ``analytics."Order Book"`` ->
    ``OrderBook`` — so a view's model and its DTO cannot disagree. Both are overridable,
    by ``--name`` or by an entry's ``name`` key.

    Args:
        entry: A declared DTO with no ``name``.

    Returns:
        The derived class name. A view's is always a valid identifier; a query's is not
        checked here, because its rule only capitalizes the attribute name it is given, so
        the caller still has to validate it.
    """
    from semolina.codegen import introspector, query_resolver

    if entry.query is not None:
        return query_resolver.class_name_for(entry.query.rpartition(".")[2])
    return introspector.class_name_for(entry.view or "")


def _named(entries: Sequence[DtoEntry], *, name: str | None) -> list[tuple[DtoEntry, str]]:
    """
    Pair every entry with the class name it will generate, and refuse an unusable set.

    ``--name`` renames one class, so it is only meaningful when exactly one DTO was asked
    for — the same coupled-flag validation ``semolina.cli.codegen._resolve_check_model``
    performs for ``--check`` / ``--model``, and raised the same way so the command funnels it
    to :data:`~semolina.cli.codegen.EXIT_INVALID_BACKEND`.

    Every name is checked to be a usable Python identifier, whether it came from ``--name``,
    from an entry's ``name`` key, or from :func:`_derived_class_name`. The generated file
    declares ``class <name>(pydantic.BaseModel):`` with the name written in as a bare token,
    so it is the one value on this path that no escaper can make safe — a name carrying a
    newline and a statement produces a *valid* module that runs that statement when the user
    imports it (threat T-50-01). A view's derived name is always an identifier, but a
    query's is not sanitized: its rule capitalizes the attribute name it was given and
    nothing more, so it is checked like the rest.
    :func:`~semolina.codegen.query_resolver.is_valid_class_name` is the check; refusing here
    is what stands in for the quoting that every other interpolated value gets.

    Duplicate names are refused as well. Several queries render into one module (O-03), and
    two classes with the same name in one file is not an error Python reports: the second
    definition silently replaces the first, so the user would get a file that imports
    cleanly and is missing a DTO. Two queries whose *attribute* names collide across
    modules is the ordinary way to reach that, and a config file listing the same view twice
    is the new one.

    Args:
        entries: The declared DTOs, in emission order.
        name: The ``--name`` override, if any.

    Returns:
        One ``(entry, class_name)`` pair per entry, in the same order.

    Raises:
        typer.BadParameter: If ``--name`` was passed alongside more than one DTO, if any
            name is not a valid Python class name or is one the generated module imports
            (:data:`~semolina.codegen.dto_renderer.DTO_MODULE_NAMES`), or if two entries
            would produce the same class name.
    """
    from semolina.codegen.dto_renderer import DTO_MODULE_NAMES
    from semolina.codegen.query_resolver import find_class_name_problem

    if name is not None and len(entries) != 1:
        msg = (
            f"--name renames a single generated class, but {len(entries)} DTOs were "
            "requested. Ask for one, or drop --name and let each class be named after its "
            "query attribute or view."
        )
        raise typer.BadParameter(msg)

    pairs = [
        (entry, name if name is not None else (entry.class_name or _derived_class_name(entry)))
        for entry in entries
    ]
    problem = find_class_name_problem(
        ((_entry_origin(entry), class_name) for entry, class_name in pairs),
        module_names=DTO_MODULE_NAMES,
    )
    if problem is None:
        return pairs
    if problem.shadows_import:
        msg = (
            f"{problem.origin} would generate a class named {problem.class_name!r}, which is "
            "a name the generated module imports or uses in its annotations; the class would "
            "shadow it. Pass --name, or set the entry's name key."
        )
    elif problem.clashes_with is None:
        msg = (
            f"{problem.origin} would generate a class named {problem.class_name!r}, which is "
            "not a valid Python class name. The value becomes the generated class's own name, "
            "written into the file as a bare token rather than as a string, so it has to "
            "be a single Python identifier and not a keyword -- RevenueByRegion, say. "
            "Pass --name, or set the entry's name key."
        )
    else:
        msg = (
            f"{problem.origin} and {problem.clashes_with} both generate a class named "
            f"{problem.class_name!r}, and one file cannot carry two. Rename one with --name "
            "or with its name key, or generate them separately."
        )
    raise typer.BadParameter(msg)


def _resolve(pairs: Sequence[tuple[DtoEntry, str]]) -> list[_Request]:
    """
    Turn named entries into probeable requests, importing or building each query.

    This is the step that executes the user's code, for the entries that name a dotted path.
    Both failure modes report as a ``ValueError`` whose message already names the path, the
    module, the type it found instead, or the field it could not accept; this converts that
    into the CLI's own vocabulary so nothing surfaces as a traceback.

    Args:
        pairs: ``(entry, class_name)`` pairs from :func:`_named`.

    Returns:
        One request per pair, in the same order.

    Raises:
        typer.BadParameter: If a dotted path carries no module part, names a module that
            cannot be imported, names no such attribute, or names something that is not a
            query; or if a view entry names no field, repeats one, or names one a model
            could not declare.
    """
    from semolina.codegen.query_resolver import build_query, resolve_query

    requests: list[_Request] = []
    for entry, class_name in pairs:
        origin = _entry_origin(entry)
        try:
            if entry.query is not None:
                query = resolve_query(entry.query)
            else:
                query = build_query(
                    entry.view or "", metrics=entry.metrics, dimensions=entry.dimensions
                )
        except ValueError as e:
            raise typer.BadParameter(str(e)) from e
        requests.append(_Request(origin=origin, class_name=class_name, query=query))
    return requests


def _load_config(config_option: Path | None) -> DtoConfig | None:
    """
    Read the declared DTOs from ``pyproject.toml``, or from an explicit ``--config`` file.

    An explicit ``--config`` that does not exist is an error; the implicit
    ``pyproject.toml`` merely not being there is not, because that is the state of every
    project that has not opted in. What the implicit case eventually produces is a "nothing
    to generate" message from the caller naming all three routes rather than only this one —
    a user who mistyped a dotted path badly enough for it to vanish should not be told to
    write a config section.

    Args:
        config_option: The ``--config`` value, or ``None``.

    Returns:
        The parsed section, or ``None`` when no config declares anything.

    Raises:
        typer.BadParameter: If an explicit ``--config`` file does not exist or does not
            carry the section, or if the section is malformed.
    """
    from semolina.codegen.dto_config import DEFAULT_CONFIG_FILE, SECTION, load_dto_config

    path = config_option if config_option is not None else Path(DEFAULT_CONFIG_FILE)
    if config_option is not None and not path.is_file():
        msg = f"--config {path} does not exist."
        raise typer.BadParameter(msg)

    try:
        config = load_dto_config(path)
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e

    if config is None and config_option is not None:
        msg = f"--config {path} carries no {SECTION} section."
        raise typer.BadParameter(msg)
    return config


def _resolve_inputs(
    *,
    dotted_paths: Sequence[str],
    view: str | None,
    metrics: tuple[str, ...],
    dimensions: tuple[str, ...],
    backend: str | None,
    database: str | None,
    output: Path | None,
    config_option: Path | None,
) -> _Inputs:
    """
    Pick the route, and settle the options the chosen route and the flags disagree about.

    The three routes are mutually exclusive rather than merged. Merging would have to answer
    what a config file's entries mean alongside a dotted path on the same command line, and
    every answer to that is a rule rather than a property: the config is a declaration of
    what a project generates, and quietly generating a different set than it declares is
    the thing a declaration is supposed to prevent.

    Where a flag and the config both speak — ``--backend``, ``--database``, ``--output`` —
    the flag wins. That is the ordinary precedence for a config file, and it is what makes
    ``--backend duckdb --output tests/dtos.py`` a usable way to regenerate a project's
    declared DTOs against a local database without editing the file.

    Args:
        dotted_paths: The positional arguments.
        view: The ``--view`` value, if any.
        metrics: The ``--metrics`` names, already split.
        dimensions: The ``--dimensions`` names, already split.
        backend: The ``--backend`` value, if any.
        database: The ``--database`` value, if any.
        output: The ``--output`` value, if any.
        config_option: The ``--config`` value, if any.

    Returns:
        The resolved inputs.

    Raises:
        typer.BadParameter: If more than one route was asked for, if ``--metrics`` or
            ``--dimensions`` was passed without ``--view``, if the config is malformed, if
            nothing was asked for at all, or if no backend was named by either the flag or
            the config.
    """
    from semolina.codegen.dto_config import DEFAULT_CONFIG_FILE, SECTION, DtoEntry

    ad_hoc = view is not None or bool(metrics) or bool(dimensions)
    if dotted_paths and ad_hoc:
        msg = (
            "QUERY_PATHS and --view are two ways to say which DTO to generate, so they "
            "cannot be combined. A dotted path already carries its own projection."
        )
        raise typer.BadParameter(msg)
    if config_option is not None and (dotted_paths or ad_hoc):
        msg = (
            "--config generates the DTOs a project declares, so it cannot be combined with "
            "QUERY_PATHS or --view. Run it on its own, or add the query to the config file."
        )
        raise typer.BadParameter(msg)
    if view is None and (metrics or dimensions):
        msg = "--metrics and --dimensions name fields of a view, so they need --view."
        raise typer.BadParameter(msg)

    config: DtoConfig | None = None
    entries: tuple[DtoEntry, ...]
    if dotted_paths:
        entries = tuple(
            DtoEntry(class_name=None, query=path, view=None, metrics=(), dimensions=())
            for path in dotted_paths
        )
    elif view is not None:
        entries = (
            DtoEntry(
                class_name=None, query=None, view=view, metrics=metrics, dimensions=dimensions
            ),
        )
    else:
        config = _load_config(config_option)
        if config is None:
            msg = (
                "Nothing to generate. Name a query by dotted path, or name a view with "
                f"--view and --metrics/--dimensions, or declare a {SECTION} section in "
                f"{DEFAULT_CONFIG_FILE}."
            )
            raise typer.BadParameter(msg)
        entries = config.entries

    resolved_backend = backend if backend is not None else (config.backend if config else None)
    if resolved_backend is None:
        msg = (
            "No backend. Pass --backend snowflake|databricks|duckdb|dotted.path.ClassName, "
            f"or set backend in {SECTION}."
        )
        raise typer.BadParameter(msg)

    return _Inputs(
        entries=entries,
        backend=resolved_backend,
        database=database if database is not None else (config.database if config else None),
        output=output if output is not None else (config.output if config else None),
        committed_database=config.database if config else None,
    )


def _announce_database_override(inputs: _Inputs, *, from_environment: bool) -> None:
    """
    Say so when ``DUCKDB_DATABASE`` replaced the database the config section commits to.

    The override is documented, and it is still what a stray ``export`` does without anyone
    meaning it: the run probes a different database than the committed file names, and the
    generated file says nothing about which (A31). A ``--database`` flag on the command line
    is not announced -- typing it is the announcement.

    Args:
        inputs: The resolved inputs.
        from_environment: Whether ``--database`` was filled from ``DUCKDB_DATABASE``.
    """
    from semolina.cli.codegen import _normalize_database_path
    from semolina.codegen.dto_config import SECTION

    if not from_environment or inputs.committed_database is None or inputs.database is None:
        return
    used = _normalize_database_path(inputs.database)
    committed = _normalize_database_path(inputs.committed_database)
    if used == committed:
        return
    _stderr.print(
        _labelled(
            "Note:",
            "yellow",
            f" DUCKDB_DATABASE ({used}) overrides database in {SECTION} ({committed}); "
            f"probing {used}.",
        )
    )


def _resolve_check_target(output: Path | None, *, check: bool) -> Path | None:
    """
    Name the committed file a ``--check`` run compares against.

    ``--check`` reads the same path ``--output`` writes, rather than taking a second option,
    which is how ``semolina codegen`` pairs them too since GEN-06. Here, in config mode,
    the destination already has a *value*, so a bare ``semolina codegen-dto --check`` verifies
    exactly the file a bare ``semolina codegen-dto`` would write. That is the whole point in
    CI, and a second option naming the same file would be one more thing to keep in step.

    Args:
        output: The resolved output path, from ``--output`` or the config's ``output``.
        check: Whether ``--check`` was passed.

    Returns:
        The file to check, or None when no check was requested.

    Raises:
        typer.BadParameter: If ``--check`` was passed with no destination to read, or the
            destination does not exist. Both are the caller's to fix, and both are worth
            distinguishing from drift: a CI job that cannot tell "your DTO is stale" from
            "you pointed me at nothing" has to treat them the same.
    """
    from semolina.codegen.dto_config import SECTION

    if not check:
        return None
    if output is None:
        msg = (
            "--check compares a committed DTO file against the warehouse, so it needs to "
            f"know which file. Pass --output PATH, or set output in {SECTION}."
        )
        raise typer.BadParameter(msg)
    if not output.is_file():
        msg = f"--check cannot read {output}: no such file. Generate it first."
        raise typer.BadParameter(msg)
    return output


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


def _probe_all(engine: Engine, requests: Sequence[_Request]) -> list[ProbedQuery]:
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
        requests: The resolved requests, in emission order.

    Returns:
        One probed query per request, in the same order.

    Raises:
        typer.Exit: :data:`~semolina.cli.codegen.EXIT_VIEW_NOT_FOUND` (3),
            :data:`~semolina.cli.codegen.EXIT_CONNECTION_ERROR` (4),
            :data:`~semolina.cli.codegen.EXIT_PROBE_FAILED` (6) or 1, depending on what failed.
    """
    from semolina.codegen.dto_renderer import probe_query

    probed: list[ProbedQuery] = []
    for request in requests:
        try:
            probed.append(
                probe_query(
                    engine,
                    request.query,
                    class_name=request.class_name,
                    origin=request.origin,
                )
            )
        # The shared table (`semolina.cli.codegen.exit_code_for`) at the warehouse stage:
        # Semolina's view-not-found and connection errors are 3 and 4 -- a
        # `--backend dotted.path.ClassName` engine's `connect()` may raise either; the
        # driver's own `adbc_driver_manager.Error` is 6, a probe that failed on both routes
        # (a refused `ExecuteSchema` never arrives here, `probe_schema` takes the zero-row
        # route for it); and a RuntimeError or ValueError -- a view name the dialect cannot
        # quote -- is 1. Anything else propagates.
        #
        # A view that does not exist is a driver error too, on all three built-in backends:
        # the probe is the first statement the command sends, so the driver reports the
        # missing relation rather than `introspect()` raising `SemolinaViewNotFoundError`.
        # Which makes 6 the code an `--view` typo lands in, and why the message carries the
        # origin -- the view name and its fields -- rather than only the driver's text.
        except Exception as e:
            exit_for(
                e,
                stage=STAGE_WAREHOUSE,
                driver_failure=f"could not probe the result schema for {request.origin}",
            )
            raise
    return probed


def _render_check_report(report: DtoCheckReport) -> None:
    """
    Write one class's per-field verdict to stderr.

    Everything goes to **stderr**: a ``--check`` run emits no source at all, and the
    module's convention is source to stdout and diagnostics to stderr. The table carries
    field names, annotations and aliases -- never a row value.

    Every cell is wrapped in :class:`~rich.text.Text`, which bypasses rich's markup parser.
    This matters more here than on the sibling's table: an alias column holds strings like
    ``AGG("REVENUE")`` and ``measure(revenue)`` straight from a warehouse, and a bare ``str``
    cell would be parsed for style tags, so ``list[str] | None`` would display as
    ``list | None`` and two cells that differ could print identically on a row marked
    ``drift``.

    Args:
        report: One class's report.
    """
    from rich.table import Table
    from rich.text import Text

    from semolina.codegen.annotation_check import STATUS_DRIFT

    if report.absent:
        _stderr.print(
            _labelled(
                "Missing:",
                "bold red",
                f" {report.class_name} ({report.origin}) is not in the committed file.",
            )
        )
        return

    table = Table(
        title=Text.assemble("semolina codegen-dto --check: ", report.class_name),
        title_justify="left",
        caption=Text(f"{report.origin} (probe route: {report.route})"),
        caption_justify="left",
    )
    # The alias pair is shown only when one of them moved. Six columns do not fit an
    # 80-column terminal -- every cell truncates to an ellipsis, including the two that
    # carry the verdict -- and in the common case both alias columns repeat a value the
    # committed file already shows. When an alias *has* drifted it is the whole story, so
    # then it earns the width.
    show_aliases = any(row.committed_alias != row.generated_alias for row in report.rows)

    table.add_column("Field")
    table.add_column("Committed")
    table.add_column("Generated")
    if show_aliases:
        table.add_column("Committed alias")
        table.add_column("Generated alias")
    table.add_column("Status")
    for row in report.rows:
        style = "red" if row.status == STATUS_DRIFT else "green"
        cells = [
            Text(row.name),
            Text(row.committed_annotation),
            Text(row.generated_annotation),
        ]
        if show_aliases:
            cells += [Text(row.committed_alias), Text(row.generated_alias)]
        cells.append(Text(row.status, style=style))
        table.add_row(*cells)
    _stderr.print(table)

    # Printed under the table rather than as a seventh column, which would push the
    # annotations and aliases into wrapping on a normal terminal for a usually-empty cell.
    for row in report.rows:
        if row.detail:
            _stderr.print(_labelled("Detail:", "yellow", f" {row.name}: {row.detail}"))


def _run_check(probed: Sequence[ProbedQuery], target: Path) -> None:
    """
    Compare every probed query against the committed file and exit with the right code.

    Classes the committed file declares that no query accounts for are reported too. A DTO
    module is generated as a whole, so a leftover class is a query that was removed from the
    config and never from the file -- it still imports, still type-checks, and no longer
    describes anything.

    Args:
        probed: The probed queries, in emission order.
        target: The committed DTO file.

    Raises:
        typer.Exit: 0 when every class matches,
            :data:`~semolina.cli.codegen.EXIT_ANNOTATION_DRIFT` (5) when any drifted,
            :data:`~semolina.cli.codegen.EXIT_PROBE_FAILED` (6) when a field's alias could
            not be resolved against the probed schema, or 1 for a file that cannot be read.
    """
    from semolina.cli.codegen import EXIT_ANNOTATION_DRIFT
    from semolina.codegen.dto_check import check_dto
    from semolina.codegen.dto_reader import has_provenance, read_committed_dto_file

    try:
        read = read_committed_dto_file(target)
    except ValueError as e:
        # An unreadable or unparseable committed file is the user's, and deserves the
        # message rather than a traceback. Exit 1, not 5: nothing was compared, so calling
        # it drift would report a verdict no check reached.
        _stderr.print(_labelled("Error:", "bold red", f" {e}"))
        raise typer.Exit(code=1) from e

    # Everything the reader could not read is said, never dropped (GEN-12).
    for warning in read.warnings:
        _stderr.print(_labelled("Warning:", "yellow", f" {target}: {warning}"))

    by_name = {dto.class_name: dto for dto in read.dtos}
    generated_names = {p.class_name for p in probed}
    # A class renamed by hand is matched by the provenance docstring codegen wrote (D4),
    # but only a class no query claims by name, and only once.
    unclaimed = [dto for dto in read.dtos if dto.class_name not in generated_names]
    matched_names: set[str] = set()
    drift = False
    for p in probed:
        committed = by_name.get(p.class_name)
        if committed is None:
            committed = next(
                (
                    dto
                    for dto in unclaimed
                    if dto.class_name not in matched_names
                    and has_provenance(dto.docstring, p.origin)
                ),
                None,
            )
            if committed is not None:
                _stderr.print(
                    _labelled(
                        "Note:",
                        "yellow",
                        f" {target} declares no {p.class_name}; checking {committed.class_name}, "
                        f"whose docstring says it was generated from {p.origin}.",
                    )
                )
        if committed is not None:
            matched_names.add(committed.class_name)
        try:
            report = check_dto(p, committed)
        except ValueError as e:
            # `_alias_for` raising, the same failure a generation run reports as 6. A check
            # cannot answer here either: the field binds to no column, so there is no
            # generated annotation to compare a committed one against.
            _stderr.print(_labelled("Error:", "bold red", f" {e}"))
            raise typer.Exit(code=EXIT_PROBE_FAILED) from e
        _render_check_report(report)
        drift = drift or report.has_drift

    for name in sorted(set(by_name) - generated_names - matched_names):
        _stderr.print(
            _labelled(
                "Extra:",
                "bold red",
                f" {target} declares {name}, which nothing being generated accounts for.",
            )
        )
        drift = True

    if drift:
        raise typer.Exit(code=EXIT_ANNOTATION_DRIFT)


def codegen_dto(
    ctx: typer.Context,
    queries: Annotated[
        list[str] | None,
        typer.Argument(
            metavar="[QUERY_PATHS]...",
            help=(
                "Dotted paths to module-level query objects, e.g. "
                "myapp.queries.revenue_by_region. Resolving one imports and runs that "
                "module. Several are emitted into one output block. Omit them to use "
                "--view, or to generate what pyproject.toml declares."
            ),
        ),
    ] = None,
    backend: Annotated[
        str | None,
        typer.Option(
            "--backend",
            "-b",
            help=(
                "Backend: snowflake, databricks, duckdb, or dotted.path.ClassName. "
                r"Required unless \[tool.semolina.dto] sets it."
            ),
        ),
    ] = None,
    database: Annotated[
        str | None,
        typer.Option(
            "--database",
            "-d",
            help="DuckDB database file path (or set DUCKDB_DATABASE env var)",
            envvar="DUCKDB_DATABASE",
        ),
    ] = None,
    view: Annotated[
        str | None,
        typer.Option(
            "--view",
            help=(
                "Generate from a view and a field list instead of an importable query. "
                "Needs --metrics and/or --dimensions. Imports nothing."
            ),
        ),
    ] = None,
    metrics: Annotated[
        list[str] | None,
        typer.Option(
            "--metrics",
            help=(
                "Metric field names for --view. Repeatable, and comma-separated values are "
                "accepted."
            ),
        ),
    ] = None,
    dimensions: Annotated[
        list[str] | None,
        typer.Option(
            "--dimensions",
            help=(
                "Dimension field names for --view. Repeatable, and comma-separated values "
                "are accepted."
            ),
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            help=(
                "Override the generated class name, which otherwise comes from the query "
                "attribute or the view name (revenue_by_region -> RevenueByRegion). One "
                "DTO only."
            ),
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help=(
                "Write the generated module to this file instead of stdout. Its directory "
                "must already exist."
            ),
        ),
    ] = None,
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help=(
                "Report whether the committed DTO file still matches the warehouse's "
                "current result schema. Writes nothing to stdout; exits 5 on drift. Reads "
                "the file --output names."
            ),
        ),
    ] = False,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            help=(
                r"Read \[tool.semolina.dto] from this file instead of ./pyproject.toml. "
                "Cannot be combined with QUERY_PATHS or --view."
            ),
        ),
    ] = None,
) -> None:
    r"""
    Generate Pydantic result DTOs from the queries you run.

    Three ways to say which DTO to generate. Each QUERY_PATH names a
    module-level query, e.g. myapp.queries.revenue_by_region. Or name a
    view and its fields directly with --view, --metrics and
    --dimensions, which writes no model and imports nothing. Or declare
    them all in a \[tool.semolina.dto] section of pyproject.toml and run
    the command with no arguments at all.

    However the query arrives, its filter, ordering and limit are
    ignored -- the DTO describes the projection and nothing else -- and
    the annotations come from the result schema the warehouse resolves
    for it, not from declared model field types.

    Generated source goes to stdout unless --output names a file, and
    every diagnostic goes to stderr, so redirecting stdout also yields a
    file you can import.

    Resolving a QUERY_PATH IMPORTS the module it names, which runs that
    module top to bottom: connections open, environment variables are
    read, decorators fire. That is inherent to generating code from an
    importable object, and it is what --backend dotted.path.ClassName
    has always done. Point this at code you trust. --view imports
    nothing.

    The working directory is APPENDED to sys.path, never prepended, so
    a project-root package resolves without being installed while a
    file in the working directory cannot shadow an installed
    distribution of the same name.

    A generated DTO's field names work on every backend: each result
    column carries its field's name, so fields bind with no alias. Its
    annotations reflect the probed warehouse's aggregation result
    typing, which the file's header names; regenerate against another
    warehouse where its driver types differ.
    """
    # The lines above are kept short on purpose. Typer renders help text through rich with
    # single line breaks preserved, so a docstring wrapped at this file's 100-character
    # limit renders as alternating long and orphaned lines in an 80-column terminal.
    try:
        # Ordered cheapest-and-least-consequential first. Route selection and the --name
        # pairing are pure argument validation; resolving a path executes the user's
        # modules; resolving the backend opens a pool. A typo in a path should not have
        # opened a warehouse connection, and a bad flag pairing should not have imported
        # anything.
        inputs = _resolve_inputs(
            dotted_paths=queries or (),
            view=view,
            metrics=_split_names(metrics),
            dimensions=_split_names(dimensions),
            backend=backend,
            database=database,
            output=output,
            config_option=config,
        )
        # Compared by name: typer 0.26 vendors click privately (`typer._click`), so the
        # `ParameterSource` enum has no public import path to compare against by identity.
        source = ctx.get_parameter_source("database")
        _announce_database_override(
            inputs, from_environment=source is not None and source.name == "ENVIRONMENT"
        )
        check_target = _resolve_check_target(inputs.output, check=check)
        if check_target is None:
            check_output(inputs.output)
        requests = _resolve(_named(inputs.entries, name=name))
        engine = _resolve_backend(inputs.backend, database=inputs.database)
    except Exception as e:
        # `_resolve_backend` does not merely name a backend: `create_engine` builds the
        # adbc-poolhouse pool, and poolhouse opens a connection while doing it. So the
        # driver's own failure to reach the database surfaces HERE, before `_probe_all`
        # exists to catch it, and the shared table reports it as 4 (UAT test 7, measured
        # 2026-08-16: it used to exit 1 with a raw traceback).
        exit_for(e, stage=STAGE_SETUP)
        raise

    probed = _probe_all(engine, requests)

    if check_target is not None:
        # A --check run emits no source, so it branches before the renderer. It still had to
        # probe: the whole comparison is against what the warehouse says today.
        _run_check(probed, check_target)
        return

    from semolina.codegen.dto_renderer import render_and_format_dtos
    from semolina.codegen.python_renderer import GeneratedSourceError, ruff_available

    try:
        source = render_and_format_dtos(
            probed, backend_label=_backend_label(inputs.backend, engine)
        )
    except GeneratedSourceError as e:
        # The module does not parse, or ruff is installed and failed on it. Exit 1: neither
        # is the caller's option or the warehouse's answer, and writing the file anyway
        # would hand them a module that fails on import or fails `ruff format --check`.
        _stderr.print(_labelled("Error:", "bold red", f" {e}"))
        raise typer.Exit(code=1) from e
    except ValueError as e:
        # `_alias_for` raising: a projected field matches no result column, or matches more
        # than one. The message already names the field, every candidate tried and every
        # column the result carried, which is the whole remedy — a DTO whose alias never
        # binds is otherwise accepted, committed, and reports `missing` at `.into()` time in
        # a service with nothing pointing back at the generated file.
        #
        # It is also where a --view typo in a *field* name lands: the view types fine and
        # the misspelled field matches nothing, so the message names the columns the result
        # really carried, which is the list the caller needed.
        _stderr.print(_labelled("Error:", "bold red", f" {e}"))
        raise typer.Exit(code=EXIT_PROBE_FAILED) from e

    emit_source(source, inputs.output, count=len(probed))
    if not ruff_available():
        _stderr.print(
            _labelled(
                "Note:",
                "yellow",
                " ruff is not installed; generated output is unformatted. Install "
                "semolina[codegen-lint] for formatted output.",
            )
        )
