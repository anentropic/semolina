"""
A dialect knows which backend it is, and ``to_sql()`` takes one (ARCH-5).

Before 0.7.0 an ``SQLDialect`` carried no identity: code that needed the backend's name
scanned its class hierarchy for a class *name*, and four hand-kept tables mapped the same
three backends. ``to_sql()`` took only a dialect name, so a custom dialect's SQL could be
previewed only by registering an engine for it.
"""

from __future__ import annotations

import pytest

from semolina import Dimension, Metric, SemanticView
from semolina.dialect import Dialect, resolve_dialect
from semolina.engines.sql import (
    DatabricksDialect,
    DuckDBDialect,
    SnowflakeDialect,
    SQLDialect,
)


class Sales(SemanticView, view="sales"):
    """A view to preview SQL for."""

    revenue = Metric()
    country = Dimension()


@pytest.mark.parametrize(
    ("cls", "kind"),
    [
        (SnowflakeDialect, Dialect.SNOWFLAKE),
        (DatabricksDialect, Dialect.DATABRICKS),
        (DuckDBDialect, Dialect.DUCKDB),
    ],
)
def test_each_built_in_dialect_names_its_backend(cls: type[SQLDialect], kind: Dialect) -> None:
    """``kind`` is the :class:`Dialect` member the dialect renders for."""
    assert cls.kind is kind
    assert cls().kind is kind


@pytest.mark.parametrize("kind", list(Dialect))
def test_resolve_dialect_returns_a_dialect_of_that_kind(kind: Dialect) -> None:
    """Every Dialect member resolves, and the result names the member back."""
    assert resolve_dialect(kind).kind is kind


def test_a_subclass_keeps_its_parents_kind() -> None:
    """A user's subclass of a built-in dialect is still that backend."""

    class TunedDuckDB(DuckDBDialect):
        pass

    assert TunedDuckDB().kind is Dialect.DUCKDB


def test_a_dialect_outside_the_built_ins_has_no_kind() -> None:
    """The base class names no backend, so a fully custom dialect answers ``None``."""
    assert SQLDialect.kind is None


@pytest.mark.parametrize(
    "instance",
    [SnowflakeDialect(), DatabricksDialect(), DuckDBDialect()],
    ids=["snowflake", "databricks", "duckdb"],
)
def test_to_sql_takes_a_dialect_instance(instance: SQLDialect) -> None:
    """Passing a dialect object previews the same SQL as passing its name."""
    query = Sales.query().metrics(Sales.revenue).dimensions(Sales.country)
    assert instance.kind is not None
    assert query.to_sql(instance) == query.to_sql(instance.kind)


def test_to_sql_renders_a_custom_dialect_instance() -> None:
    """A subclass's own rendering shows in the preview, with no engine registered."""

    class TaggedMetrics(SnowflakeDialect):
        def wrap_metric(self, field_name: str) -> str:
            return f"TAGGED({field_name})"

    query = Sales.query().metrics(Sales.revenue)
    assert "TAGGED(REVENUE)" in query.to_sql(TaggedMetrics())
