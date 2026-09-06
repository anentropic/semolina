"""
Resolve a user's query object into the inputs DTO codegen needs.

DTO codegen is pointed at an *importable query* — ``myapp.queries.revenue_by_region``, a
module-level ``_Query`` the user already built with ``Model.query().metrics(...)`` (D-01).
This module is the whole of the "get from a dotted path to something the renderer can
probe" step: import it, strip it down to its projection, name the class it will become, and
describe its fields in the shape the shared candidate-name helper already speaks.

Nothing here touches an engine, a warehouse or a schema. That keeps every function testable
without a connection, and it keeps the trust boundary this module owns — executing the
user's module — in one readable place.
"""

from __future__ import annotations

import importlib
import keyword
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from semolina.codegen.introspector import IntrospectedField
from semolina.fields import RESERVED_FIELD_NAMES, Dimension, Fact, Field, Metric, _check_name
from semolina.models import SemanticView
from semolina.query import _Query

if TYPE_CHECKING:
    from collections.abc import Sequence


def resolve_query(dotted_path: str) -> _Query:
    """
    Import a dotted path and return the module-level query object it names.

    The path is split with ``rpartition(".")`` exactly the way
    ``semolina.cli.codegen._resolve_backend`` splits ``--backend
    mypackage.backends.CustomEngine``. Dotted path, never ``module:attr`` — the repo
    already published the first convention and D-01 keeps DTO codegen on it.

    **Importing the user's module executes it, top to bottom.** Module-level code runs:
    connections open, environment variables are read, decorators fire. That is inherent to
    generating code from an importable object rather than from a string, and it is already
    true of ``--backend dotted.path.ClassName``. It is named here (threat T-50-02) rather
    than defended against, because there is no defence that still leaves the feature
    working. Point this at code you trust, the same way you would ``python -c 'import
    myapp.queries'``.

    **The working directory is appended to ``sys.path``, never prepended** (threat T-50-03).
    Appending is what lets ``myapp.queries`` resolve when the CLI runs from a project root
    without an installed package. Prepending would let a file in the working directory
    shadow an installed distribution of the same name — so a stray ``pydantic.py`` beside
    the queries module would be imported in preference to the real one, by anything the
    resolved module then imports. The position is set explicitly rather than inherited from
    however the process happened to be launched.

    Args:
        dotted_path: A dotted path to a module-level ``_Query``, e.g.
            ``'myapp.queries.revenue_by_region'``.

    Returns:
        The query object the path names.

    Raises:
        ValueError: If the path carries no module part, if the module cannot be imported,
            if the module has no such attribute, or if the attribute is not a ``_Query`` —
            the last naming the type actually found, so the message says what went wrong
            rather than that something did.

    Example:
        .. code-block:: python

            from semolina.codegen.query_resolver import resolve_query

            query = resolve_query("myapp.queries.revenue_by_region")
    """
    module_path, _, attribute_name = dotted_path.rpartition(".")
    if not module_path or not attribute_name:
        msg = (
            f"Cannot resolve query {dotted_path!r}: expected a dotted path to a module-level "
            "query object, e.g. 'myapp.queries.revenue_by_region'."
        )
        raise ValueError(msg)

    cwd = str(Path.cwd())
    if cwd not in sys.path:
        # Append, never insert(0, ...). See this function's docstring: prepending would let
        # the working directory shadow an installed distribution.
        sys.path.append(cwd)

    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        msg = f"Cannot import module {module_path!r} for query {dotted_path!r}: {e}"
        raise ValueError(msg) from e

    try:
        obj: object = getattr(module, attribute_name)
    except AttributeError as e:
        msg = f"Module {module_path!r} has no attribute {attribute_name!r}."
        raise ValueError(msg) from e

    if not isinstance(obj, _Query):
        msg = (
            f"{dotted_path!r} resolved to a {type(obj).__name__}, not a query. DTO codegen "
            "takes a module-level query object built with Model.query()."
        )
        raise ValueError(msg)
    return obj


def is_valid_field_name(name: str) -> bool:
    """
    Answer whether a name can be declared as a field on a Semantic View model.

    The three rules :class:`semolina.fields.Field` and
    :class:`semolina.models.SemanticView` already enforce at class-creation time, asked
    ahead of time so the caller can name the option that carried the bad value rather than
    letting a ``ValueError`` surface from a class body the user never wrote.

    Soft keywords are rejected here, unlike in :func:`is_valid_class_name`. That is not an
    inconsistency: ``class match:`` is legal Python but ``match = Dimension()`` is what
    ``Field.__set_name__`` refuses, so this function has to answer for the sink it is
    guarding rather than for the other one.

    Args:
        name: A candidate field name, from ``--metrics`` / ``--dimensions`` or from a
            ``[[tool.semolina.dto.entries]]`` table.

    Returns:
        ``True`` if the name can be declared as a model field.

    Example:
        .. code-block:: python

            from semolina.codegen.query_resolver import is_valid_field_name

            is_valid_field_name("revenue")
            # True
            is_valid_field_name("limit")
            # False
    """
    return (
        name.isidentifier()
        and not keyword.iskeyword(name)
        and not keyword.issoftkeyword(name)
        and name not in RESERVED_FIELD_NAMES
    )


def _check_field_names(names: Sequence[str], *, option: str) -> None:
    """
    Refuse a field name a model could not declare, naming the option it came from.

    Args:
        names: The candidate names.
        option: The option or config key they were read from, for the message.

    Raises:
        ValueError: If any name is not usable as a model field name.
    """
    for name in names:
        if not is_valid_field_name(name):
            msg = (
                f"{option} {name!r} cannot be a field name. It becomes an attribute on the "
                "generated DTO and on the model the probe query is built from, so it has to "
                "be a plain Python identifier, not a keyword, and not one of the names "
                f"reserved by the query builder ({', '.join(sorted(RESERVED_FIELD_NAMES))})."
            )
            raise ValueError(msg)


def _model_name_for(view: str) -> str:
    """
    Name the throwaway model class an ad-hoc query is built on.

    The name never reaches generated source — the DTO's own class name comes from
    :func:`class_name_for` or from ``--name`` — so this only has to be a legal class name
    and a recognizable one in a traceback. A view whose name does not survive the
    PascalCase rule falls back to a fixed label rather than failing: the view name is a
    warehouse identifier and may legally be spelled in ways Python cannot.

    Args:
        view: The semantic view name, schema-qualified or not.

    Returns:
        A valid Python class name.
    """
    derived = class_name_for(view.rpartition(".")[2])
    return derived if is_valid_class_name(derived) else "AdHocSemanticView"


def build_query(
    view: str,
    *,
    metrics: Sequence[str] = (),
    dimensions: Sequence[str] = (),
) -> _Query:
    """
    Build a query for a view from field *names*, with no model class written anywhere.

    The second route into DTO codegen, beside :func:`resolve_query`. It exists because the
    dotted-path route has a bootstrapping cost that is real but not always worth paying: to
    generate a DTO you must first write a model, then write a query, then make both
    importable. When you already know which view and which fields you want, this skips
    straight to the probe.

    A throwaway :class:`~semolina.models.SemanticView` subclass is synthesized rather than
    the SQL being assembled by hand. That is the load-bearing choice here: every downstream
    step — the dialect's ``normalize_identifier``, the ``semantic_view()`` argument lists,
    and above all the candidate result-column names
    :func:`semolina.codegen.annotation_check._result_field_names` derives — reads a real
    field object owned by a real model. A hand-assembled query would be a second
    implementation of the builder, and the first thing it would drift on is the per-backend
    metric spelling that plan 50-01 had to fix once already.

    The names are the *warehouse's* field names, and they are also the generated DTO's
    attribute names. There is no ``source=`` equivalent here: a warehouse field whose name
    is not a Python identifier needs a hand-written model with ``Metric(source=...)``, which
    is the one thing this route deliberately does not try to replace.

    Args:
        view: The semantic view name, schema-qualified as the warehouse wants it. Quoted by
            the dialect on its way into SQL, so any spelling is safe here.
        metrics: Metric field names, in the order they should appear in the DTO.
        dimensions: Dimension field names, appended after the metrics.

    Returns:
        A query over ``view`` projecting exactly those fields, with no filter, ordering or
        limit — already in the shape :func:`projection_only` would reduce it to.

    Raises:
        ValueError: If ``view`` is empty, if no field was named at all, if a name is not
            usable as a model field name, or if one name appears twice. A repeated name is
            refused rather than deduplicated: two fields of one name collapse silently into
            one attribute, so the DTO would quietly be missing a column the caller asked
            for.

    Example:
        .. code-block:: python

            from semolina.codegen.query_resolver import build_query

            query = build_query(
                "analytics.sales",
                metrics=["revenue"],
                dimensions=["region"],
            )
            [f.name for f in query._metrics]
            # ['revenue']
    """
    if not view:
        msg = "A view name is required to build a query from field names."
        raise ValueError(msg)

    _check_field_names(metrics, option="metric")
    _check_field_names(dimensions, option="dimension")

    if not metrics and not dimensions:
        msg = (
            f"No fields were named for view {view!r}. A DTO describes a projection, so at "
            "least one metric or dimension is required."
        )
        raise ValueError(msg)

    seen: set[str] = set()
    for name in [*metrics, *dimensions]:
        if name in seen:
            msg = (
                f"Field {name!r} was named twice for view {view!r}. One field is one "
                "attribute on the generated DTO, and a repeat would silently drop a column "
                "rather than emit it twice."
            )
            raise ValueError(msg)
        seen.add(name)

    metric_fields = {name: Metric[Any]() for name in metrics}
    dimension_fields = {name: Dimension[Any]() for name in dimensions}

    def _body(ns: dict[str, Any]) -> None:
        # Metrics first, then dimensions: the same order `query_fields` emits, and therefore
        # the order the fields appear in the generated class.
        ns.update(metric_fields)
        ns.update(dimension_fields)

    model: type[SemanticView] = types.new_class(
        _model_name_for(view), (SemanticView,), {"view": view}, _body
    )

    # The descriptors above are the bound ones: `__set_name__` mutates each in place during
    # class creation, setting the `name` and `owner` the SQL builder reads. Passing them
    # straight back keeps every field the caller asked for, which a lookup filtered by type
    # would not — that shape can drop a field silently, which is the one failure mode this
    # function's duplicate check exists to rule out.
    return model.query(
        metrics=list(metric_fields.values()),
        dimensions=list(dimension_fields.values()),
    )


def ad_hoc_origin(view: str, *, metrics: Sequence[str], dimensions: Sequence[str]) -> str:
    """
    Describe an ad-hoc query the way the generated file's provenance header will name it.

    The dotted-path route records where the query came from by printing the path, which is
    enough to regenerate the class. This route has no path, so the origin has to carry the
    same information: the view and the fields. The string is deliberately reconstructable
    into the command that produced it.

    Args:
        view: The view name.
        metrics: The metric names.
        dimensions: The dimension names.

    Returns:
        A one-line origin description.

    Example:
        .. code-block:: python

            from semolina.codegen.query_resolver import ad_hoc_origin

            ad_hoc_origin("sales", metrics=["revenue"], dimensions=["region"])
            # "view 'sales' metrics=[revenue] dimensions=[region]"
    """
    parts = [f"view {view!r}"]
    if metrics:
        parts.append(f"metrics=[{', '.join(metrics)}]")
    if dimensions:
        parts.append(f"dimensions=[{', '.join(dimensions)}]")
    return " ".join(parts)


def projection_only(query: _Query) -> _Query:
    """
    Return the query with everything but its projection removed.

    The DTO is derived from the projection and nothing else (D-02), so a filtered, ordered,
    limited query and its unfiltered twin produce the same DTO. A ``WHERE`` clause changes
    which rows come back, not what shape they are.

    All three clauses are stripped rather than only ``_filters``, so the rule is one
    statable sentence instead of an accident of which clauses happen to bind parameters
    today. The parameter-free consequence matters on its own: Snowflake refuses
    ``ExecuteSchema`` for a query carrying a bound parameter, so stripping is what keeps the
    primary probe route reachable on every backend.
    ``tests/unit/codegen/test_dto_renderer.py`` pins both halves.

    ``_Query._replace`` rather than ``dataclasses.replace``: ``_model`` is declared
    ``init=False``, so plain ``replace`` drops it and the rebuilt query would no longer know
    which model it came from.

    Args:
        query: Any query, filtered or not.

    Returns:
        A new query carrying the same metrics and dimensions, with no filter, no ordering
        and no limit.

    Example:
        .. code-block:: python

            from semolina.codegen.query_resolver import projection_only

            stripped = projection_only(query)
            stripped._filters
            # None
    """
    return query._replace(_filters=None, _order_by_fields=(), _limit_value=None)


def class_name_for(attribute_name: str) -> str:
    """
    Derive the generated DTO's class name from the query attribute's name.

    ``revenue_by_region`` becomes ``RevenueByRegion`` (D-05). The dotted path already
    carries the name, so nothing has to be invented and nothing has to be asked for; the
    CLI's ``--name`` override (plan 50-03) replaces the answer rather than the rule.

    This is the same snake-to-Pascal rule the three engines already carry privately as
    ``_to_pascal_case`` — ``semolina.engines.snowflake``, ``semolina.engines.databricks``
    and ``semolina.engines.duckdb`` each have a copy, keyed on a warehouse *view* name
    rather than a Python attribute. They are named here so a future consolidation is
    findable; this phase deliberately does not move them, because a shared helper touching
    all three engines is a change with no test the DTO work needs.

    Args:
        attribute_name: The query object's attribute name, e.g. ``'revenue_by_region'``.

    Returns:
        The PascalCase class name, e.g. ``'RevenueByRegion'``.

    Example:
        .. code-block:: python

            from semolina.codegen.query_resolver import class_name_for

            class_name_for("revenue_by_region")
            # 'RevenueByRegion'
    """
    return "".join(word.capitalize() for word in attribute_name.split("_"))


def is_valid_class_name(name: str) -> bool:
    """
    Answer whether a name can be written into generated source as a class name.

    The generated file declares ``class <name>(pydantic.BaseModel):`` with the name
    interpolated as a bare token, which makes it the one value DTO codegen emits that
    ``python_renderer._python_str_literal`` cannot cover: there is no literal to escape it
    into, because a class name *is* code. This check is what stands in for the escaping, and
    it buys the same property (threat T-50-01) — a value that is not a single Python
    identifier can close the ``class`` statement and open whatever it likes after it, which
    is module-level code execution in a file the documented workflow tells the reader to
    redirect to disk and import.

    ``keyword.iskeyword`` as well as ``str.isidentifier``, because the two disagree exactly
    where it matters: ``'class'``, ``'import'`` and ``'None'`` are all identifiers by
    ``isidentifier()`` and none of them can name a class. Soft keywords are deliberately
    *not* rejected — ``class match:`` is legal Python, so refusing it would narrow the
    contract for nothing.

    Args:
        name: A candidate class name, from the CLI's ``--name`` or from
            :func:`class_name_for`.

    Returns:
        ``True`` if the name can be written into generated source unmodified.

    Example:
        .. code-block:: python

            from semolina.codegen.query_resolver import is_valid_class_name

            is_valid_class_name("RevenueByRegion")
            # True
            is_valid_class_name("class")
            # False
    """
    return name.isidentifier() and not keyword.iskeyword(name)


def _introspected(
    field: Field[Any], field_type: Literal["metric", "dimension", "fact"]
) -> IntrospectedField:
    """
    Adapt one query field object to the ``IntrospectedField`` shape.

    Args:
        field: A bound ``Metric``, ``Dimension`` or ``Fact`` descriptor.
        field_type: ``'metric'``, ``'dimension'`` or ``'fact'``.

    Returns:
        The adapter record. ``data_type`` is always ``None``: DTO codegen resolves every
        annotation from the probed result schema (D-06), so a declared type would be the one
        source DTO-07 forbids.

    Raises:
        RuntimeError: If the field was never bound to a model class, so it has no name.
    """
    return IntrospectedField(
        name=_check_name(field.name),
        field_type=field_type,
        data_type=None,
        source_name=field.source,
    )


def query_fields(query: _Query) -> list[IntrospectedField]:
    """
    Describe a query's projection in the shape the candidate-name helper already speaks.

    ``semolina.codegen.annotation_check._result_field_names`` derives a field's candidate
    result-column names from the dialect that built the SQL, and it takes an
    ``IntrospectedField``. DTO codegen calls no ``introspect()`` (D-08), so the record is
    built from the query's own field objects instead: the projection already separates
    ``_metrics`` from ``_dimensions``, so a field's role is known without asking a
    warehouse.

    Order is metrics then dimensions — the query's own declaration order, and deliberately
    **not** the result-column order. Snowflake and Databricks return metrics before
    dimensions; DuckDB's ``semantic_view()`` returns dimensions before metrics. Binding is
    by name in :func:`semolina.codegen.dto_renderer._alias_for`, never by position, so this
    order is a rendering order and carries no meaning beyond it.

    Args:
        query: The query whose projection to describe. Filters and ordering are ignored, so
            passing a stripped or an unstripped query gives the same answer.

    Returns:
        One record per projected field, metrics first.

    Raises:
        RuntimeError: If a projected field was never bound to a model class.

    Example:
        .. code-block:: python

            from semolina.codegen.query_resolver import query_fields

            [f.field_type for f in query_fields(query)]
            # ['metric', 'dimension']
    """
    fields: list[IntrospectedField] = [_introspected(metric, "metric") for metric in query._metrics]
    fields += [
        _introspected(dimension, "fact" if isinstance(dimension, Fact) else "dimension")
        for dimension in query._dimensions
    ]
    return fields
