"""
``Query`` has a public, read-only view of its own state (ARCH-3).

``Query`` is public, and the type ``Model.query()`` returns, but before 0.7.0 the only way to
ask a query what it selects was through its underscore attributes, which its own docstrings
taught. A cache key, an audit log or a middleware that inspects a query needs a surface it
can rely on.
"""

from __future__ import annotations

import dataclasses

import pytest

from semolina import Dimension, Fact, Metric, Query, SemanticView


class Sales(SemanticView, view="sales"):
    """A view to build queries against."""

    revenue = Metric()
    cost = Metric()
    country = Dimension()
    unit_price = Fact()


def _full_query() -> Query:
    return (
        Sales.query()
        .metrics(Sales.revenue, Sales.cost)
        .dimensions(Sales.country, Sales.unit_price)
        .where(Sales.country == "US")
        .order_by(Sales.revenue.desc(), Sales.country)
        .limit(10)
        .using("warehouse")
    )


def test_a_query_reports_what_it_selects() -> None:
    """The selected fields come back in the order they were added, as tuples."""
    query = _full_query()
    assert query.selected_metrics == (Sales.revenue, Sales.cost)
    assert query.selected_dimensions == (Sales.country, Sales.unit_price)


def test_a_query_reports_its_filter_ordering_limit_engine_and_model() -> None:
    """Each builder call is readable back from the query it returned."""
    query = _full_query()
    assert query.filters == (Sales.country == "US")
    assert len(query.ordering) == 2
    assert query.ordering[1] is Sales.country
    assert query.limit_value == 10
    assert query.engine_name == "warehouse"
    assert query.model is Sales


def test_an_empty_query_reports_empty_state() -> None:
    """A query with nothing added reports nothing, rather than raising."""
    query = Sales.query()
    assert query.selected_metrics == ()
    assert query.selected_dimensions == ()
    assert query.filters is None
    assert query.ordering == ()
    assert query.limit_value is None
    assert query.engine_name is None
    assert query.model is Sales


@pytest.mark.parametrize(
    "name",
    [
        "selected_metrics",
        "selected_dimensions",
        "filters",
        "ordering",
        "limit_value",
        "engine_name",
        "model",
    ],
)
def test_the_read_surface_is_read_only(name: str) -> None:
    """Assigning to a reported attribute fails, as the query is immutable."""
    query = _full_query()
    before = getattr(query, name)
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        setattr(query, name, None)
    assert getattr(query, name) == before
