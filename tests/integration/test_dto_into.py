"""
ALIAS-02: a DTO written with plain field names converts on Snowflake and Databricks.

Everything here replays (incl. CI): no credentials, no warehouse, no network. Nothing here
runs live and nothing here is ever recorded. Both cassettes were **copied** byte for byte
from the ``test_queries`` recordings of ``test_metric_with_dimension``, for the reason
``test_type_fidelity.py`` gives: cassette directories are derived from the pytest node id,
so a new test cannot read an existing test's recording. Re-record the *sources*, never this
module, then copy them over these again::

    pytest --adbc-record=all tests/integration/test_queries.py

Before phase 53 neither DTO below could load a warehouse result: Snowflake named the
columns ``AGG("REVENUE")`` and ``COUNTRY``, Databricks named the metric
``measure(revenue)``, and a DTO had to carry each backend's spelling as a
``validation_alias``. Every builder now aliases each selected column to its field name, so
the same plain class serves both backends. DuckDB's half of ALIAS-02 lives in
``tests/unit/test_dto_duckdb.py``, which runs live.

The ``adbc_cassette`` marker is applied per test rather than module-wide, as in
``test_type_fidelity.py``, so a DuckDB test added here could not be diverted into replay.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pydantic
import pytest

from semolina import Dimension, Metric, SemanticView


class Sales(SemanticView, view="sales_view"):
    """
    Synthetic SemanticView, field for field the ``Sales`` of ``test_queries.py``.

    That is load-bearing: the cassette key is the sqlglot-normalized SQL, so the generated
    statement has to normalize to what was recorded or the copied cassette misses.
    """

    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()


class RevenueByCountry(pydantic.BaseModel):
    """A DTO as a user writes it: plain field names, no alias, no ``populate_by_name``."""

    revenue: Decimal
    country: str


class SnowflakeRevenueByCountry(pydantic.BaseModel):
    """The same DTO with the exact type Snowflake returns for the metric, ``decimal128``."""

    revenue: Decimal
    country: str


class DatabricksRevenueByCountry(pydantic.BaseModel):
    """The same DTO with the exact type Databricks returns for the metric, ``int64``."""

    revenue: int
    country: str


EXPECTED = [("CA", 2800), ("MX", 1500), ("US", 1500)]
"""``(country, revenue)`` as ``test_queries.test_metric_with_dimension`` records it."""


def _into(model: type[pydantic.BaseModel], *, validate: bool) -> list[Any]:
    """
    Run the recorded query and convert its result into ``model``.

    The query is ``test_queries.test_metric_with_dimension``'s, which is the test whose
    cassette was copied.

    Args:
        model: The DTO class.
        validate: Passed through to :meth:`~semolina.cursor.SemolinaCursor.into`.

    Returns:
        One ``model`` instance per result row.
    """
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue)
        .dimensions(Sales.country)
        .order_by(Sales.country)
        .execute()
    )
    try:
        return cursor.into(model, validate=validate)
    finally:
        cursor.close()


def _pairs(rows: list[Any]) -> list[tuple[str, int]]:
    """
    Reduce converted rows to ``(country, revenue)`` pairs comparable across backends.

    Args:
        rows: DTO instances carrying ``country`` and ``revenue``.

    Returns:
        The pairs, with ``revenue`` as an ``int`` so a ``Decimal`` and an ``int`` compare.
    """
    return [(row.country, int(row.revenue)) for row in rows]


@pytest.mark.adbc_cassette
def test_snowflake_plain_dto_converts_copied_cassette(snowflake_engine: Any) -> None:  # noqa: ARG001
    """
    Snowflake's result loads into a plain DTO, on the fast path and the validating one.

    ``validate=False`` builds instances without converting anything, so the annotation must
    match ``decimal128`` exactly; ``validate=True`` runs pydantic. Both fail before phase 53
    with every field missing, because no column was named ``revenue`` or ``country``.
    """
    fast = _into(SnowflakeRevenueByCountry, validate=False)
    validated = _into(RevenueByCountry, validate=True)

    assert _pairs(fast) == EXPECTED
    assert _pairs(validated) == EXPECTED
    assert all(isinstance(row.revenue, Decimal) for row in fast)


@pytest.mark.adbc_cassette
def test_databricks_plain_dto_converts_copied_cassette(databricks_engine: Any) -> None:  # noqa: ARG001
    """
    Databricks' result loads into a plain DTO, and into the same class Snowflake's does.

    ``RevenueByCountry`` is shared with the Snowflake test on purpose: one class, two
    backends, no alias. Before phase 53 its ``revenue`` field would have found only
    ``measure(revenue)`` here.
    """
    fast = _into(DatabricksRevenueByCountry, validate=False)
    validated = _into(RevenueByCountry, validate=True)

    assert _pairs(fast) == EXPECTED
    assert _pairs(validated) == EXPECTED
    assert all(isinstance(row.revenue, Decimal) for row in validated)
