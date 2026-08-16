"""
DTO codegen subcommand: generate Pydantic result DTOs from the queries a project runs.

A sibling command rather than a flag on ``semolina codegen`` (O-02, decided 2026-08-15).
The two commands share every option they have in common — ``--backend``, ``--database``,
the diagnostics idiom and the exit-code vocabulary — and they are reused from
:mod:`semolina.cli.codegen` rather than copied. What they do not share is the *positional*
argument: ``codegen`` takes schema-qualified warehouse view names, this one takes dotted
Python import paths. A different noun in the same slot is the ambiguity
``_resolve_check_model`` was written to avoid, not one to repeat, and a separate command
also keeps ``EXIT_PROBE_FAILED`` out of a table where it can never fire.

Both commands now carry a ``--check``, and the two mean the same thing: compare a committed
generated file against what the warehouse says today, write nothing, exit 5 on drift. They
differ in what names the file. ``codegen`` needs a ``--model PATH`` because it has no
``--output`` and emits to stdout; here the destination is already named by ``--output``, and
in config mode it already has a value, so ``semolina codegen-dto --check`` on its own
verifies exactly the file ``semolina codegen-dto`` on its own would write.

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

The cost of the split is a second exit-code table. ``docs/src/how-to/dto-codegen.rst``
duplicates the epilog registered for this command in :mod:`semolina.cli`, and the two must
agree — the same standing obligation the ``codegen`` epilog already carries.
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
    EXIT_CONNECTION_ERROR,
    EXIT_INVALID_BACKEND,
    EXIT_VIEW_NOT_FOUND,
    _adbc_connection_errors,
    _labelled,
    _resolve_backend,
    _stderr,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from semolina.codegen.dto_check import DtoCheckReport
    from semolina.codegen.dto_config import DtoConfig, DtoEntry
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


@dataclass(frozen=True)
class _Inputs:
    """
    What the three routes reduce to, before anything is imported or connected to.

    Attributes:
        entries: The DTOs to generate, in emission order.
        backend: The resolved ``--backend`` value.
        database: The resolved DuckDB database path, or ``None``.
        output: The file to write, or ``None`` for stdout.
    """

    entries: tuple[DtoEntry, ...]
    backend: str
    database: str | None
    output: Path | None


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
    view's last dotted segment by the same rule — ``analytics.daily_sales`` ->
    ``DailySales``. Both are overridable, by ``--name`` or by an entry's ``name`` key.

    Args:
        entry: A declared DTO with no ``name``.

    Returns:
        The derived class name, which the caller still has to validate: the rule
        capitalises what it is given and invents nothing, so a warehouse identifier that is
        not a Python identifier survives it unchanged.
    """
    from semolina.codegen.query_resolver import class_name_for

    source = entry.query if entry.query is not None else (entry.view or "")
    return class_name_for(source.rpartition(".")[2])


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
    imports it (threat T-50-01). The derived route sanitises nothing on its own either: it
    capitalises the parts of the name it was given, so a source whose last segment is empty
    or does not start an identifier reaches the same token.
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
            name is not a valid Python class name, or if two entries would produce the same
            class name.
    """
    from semolina.codegen.query_resolver import is_valid_class_name

    if name is not None and len(entries) != 1:
        msg = (
            f"--name renames a single generated class, but {len(entries)} DTOs were "
            "requested. Ask for one, or drop --name and let each class be named after its "
            "query attribute or view."
        )
        raise typer.BadParameter(msg)

    pairs: list[tuple[DtoEntry, str]] = []
    seen: dict[str, str] = {}
    for entry in entries:
        class_name = name if name is not None else (entry.class_name or _derived_class_name(entry))
        origin = _entry_origin(entry)
        if not is_valid_class_name(class_name):
            msg = (
                f"{origin} would generate a class named {class_name!r}, which is not a valid "
                "Python class name. The value becomes the generated class's own name, "
                "written into the file as a bare token rather than as a string, so it has to "
                "be a single Python identifier and not a keyword -- RevenueByRegion, say. "
                "Pass --name, or set the entry's name key."
            )
            raise typer.BadParameter(msg)
        if class_name in seen:
            msg = (
                f"{origin} and {seen[class_name]} both generate a class named "
                f"{class_name!r}, and one file cannot carry two. Rename one with --name or "
                "with its name key, or generate them separately."
            )
            raise typer.BadParameter(msg)
        seen[class_name] = origin
        pairs.append((entry, class_name))
    return pairs


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
    )


def _resolve_check_target(output: Path | None, *, check: bool) -> Path | None:
    """
    Name the committed file a ``--check`` run compares against.

    ``--check`` reads the same path ``--output`` writes, rather than taking a second option.
    The sibling command needs its own ``--model`` because ``semolina codegen`` has no
    ``--output`` and emits to stdout; here the destination already has a name, and in config
    mode it already has a *value*, so a bare ``semolina codegen-dto --check`` verifies
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


def _check_output(output: Path | None) -> None:
    """
    Refuse an output path whose directory does not exist, before anything is probed.

    Checked here rather than at the write, which happens after every query has been
    imported and the warehouse has typed all of them. A mistyped ``--output`` is worth
    catching before that work, not after it.

    The directory is not created. A generated DTO is imported by the code that uses it, so
    its directory is a package that already exists; creating one would turn a typo into a
    stray directory and a module nothing imports.

    Args:
        output: The resolved output path, or ``None`` for stdout.

    Raises:
        typer.BadParameter: If the path's parent directory does not exist, or if the path
            names an existing directory.
    """
    if output is None:
        return
    if output.is_dir():
        msg = f"--output {output} is a directory. Name the file to write."
        raise typer.BadParameter(msg)
    parent = output.parent
    if not parent.is_dir():
        msg = f"--output {output} names a directory that does not exist: {parent}."
        raise typer.BadParameter(msg)


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
            :data:`EXIT_PROBE_FAILED` (6) or 1, depending on what failed.
    """
    import adbc_driver_manager

    from semolina.codegen.dto_renderer import probe_query
    from semolina.engines.base import SemolinaConnectionError, SemolinaViewNotFoundError

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
        #
        # A view that does not exist reaches here too, on all three built-in backends: the
        # probe is the first statement the command sends, so the driver reports the missing
        # relation rather than `introspect()` raising `SemolinaViewNotFoundError`. Which
        # makes this the arm an `--view` typo lands in, and why the message carries the
        # origin — the view name and its fields — rather than only the driver's text.
        except adbc_driver_manager.Error as e:
            _stderr.print(
                _labelled(
                    "Error:",
                    "bold red",
                    f" could not probe the result schema for {request.origin}: "
                    f"{type(e).__name__}: {e}",
                )
            )
            raise typer.Exit(code=EXIT_PROBE_FAILED) from e
        except RuntimeError as e:
            _stderr.print(_labelled("Error:", "bold red", f" {e}"))
            raise typer.Exit(code=1) from e
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
        typer.Exit: 0 when every class matches, :data:`~semolina.cli.codegen.EXIT_ANNOTATION_DRIFT`
            (5) when any drifted, :data:`EXIT_PROBE_FAILED` (6) when a field's alias could not
            be resolved against the probed schema, or 1 for a file that cannot be read.
    """
    from semolina.cli.codegen import EXIT_ANNOTATION_DRIFT
    from semolina.codegen.dto_check import check_dto
    from semolina.codegen.dto_reader import read_committed_dtos

    try:
        committed = read_committed_dtos(target)
    except ValueError as e:
        # An unreadable or unparseable committed file is the user's, and deserves the
        # message rather than a traceback. Exit 1, not 5: nothing was compared, so calling
        # it drift would report a verdict no check reached.
        _stderr.print(_labelled("Error:", "bold red", f" {e}"))
        raise typer.Exit(code=1) from e

    by_name = {dto.class_name: dto for dto in committed}
    drift = False
    for p in probed:
        try:
            report = check_dto(p, by_name.get(p.class_name))
        except ValueError as e:
            # `_alias_for` raising, the same failure a generation run reports as 6. A check
            # cannot answer here either: the field binds to no column, so there is no
            # generated annotation to compare a committed one against.
            _stderr.print(_labelled("Error:", "bold red", f" {e}"))
            raise typer.Exit(code=EXIT_PROBE_FAILED) from e
        _render_check_report(report)
        drift = drift or report.has_drift

    generated_names = {p.class_name for p in probed}
    for name in sorted(set(by_name) - generated_names):
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


def _emit(source: str, output: Path | None, *, count: int) -> None:
    """
    Write the generated source to its destination.

    Written in one call after every class has rendered, never incrementally. A run that
    fails partway leaves the previous file untouched rather than half-replaced, which is
    what makes a committed DTO module safe to regenerate in place.

    Args:
        source: The rendered module.
        output: The file to write, or ``None`` for stdout.
        count: How many classes it carries, for the confirmation line.
    """
    if output is None:
        typer.echo(source)
        return
    output.write_text(source, encoding="utf-8")
    classes = "class" if count == 1 else "classes"
    _stderr.print(_labelled("Wrote:", "bold green", f" {output} ({count} {classes})"))


def codegen_dto(
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

    A generated DTO is pinned to the backend it was probed against: its
    aliases are that warehouse's result-column spellings and its
    annotations reflect that warehouse's aggregation result typing. The
    file says so in its own header, and another warehouse needs a
    regenerated class.
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
        check_target = _resolve_check_target(inputs.output, check=check)
        if check_target is None:
            _check_output(inputs.output)
        requests = _resolve(_named(inputs.entries, name=name))
        engine = _resolve_backend(inputs.backend, database=inputs.database)
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

    probed = _probe_all(engine, requests)

    if check_target is not None:
        # A --check run emits no source, so it branches before the renderer. It still had to
        # probe: the whole comparison is against what the warehouse says today.
        _run_check(probed, check_target)
        return

    from semolina.codegen.dto_renderer import render_and_format_dtos
    from semolina.codegen.python_renderer import ruff_available

    try:
        source = render_and_format_dtos(
            probed, backend_label=_backend_label(inputs.backend, engine)
        )
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

    _emit(source, inputs.output, count=len(probed))
    if not ruff_available():
        _stderr.print(
            _labelled(
                "Note:",
                "yellow",
                " ruff is not installed; generated output is unformatted. Install "
                "semolina[codegen-lint] for formatted output.",
            )
        )
