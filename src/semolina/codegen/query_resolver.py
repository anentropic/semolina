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
import sys
from pathlib import Path
from typing import Any, Literal

from semolina.codegen.introspector import IntrospectedField
from semolina.fields import Fact, Field, _check_name
from semolina.query import _Query


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
