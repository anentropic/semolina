"""
Async warehouse query replay tests — the D-16 spike.

This module proves, by execution rather than by inference, that an existing
cassette recorded through the *sync* path replays end to end through the *async*
path, for both warehouse dialects. Two claims ride on a match:

- the async path sends byte-identical SQL, because it reuses
  ``build_select_with_params`` unchanged (D-04) — the plugin matches on the SQL
  the driver received, so a match *is* that assertion;
- cassette interception reaches inside adbc-poolhouse's offload worker thread,
  because the plugin patches ``driver_mod.connect``, a process-global module
  attribute upstream of the whole async stack (D-15).

**Nothing here is recorded.** The four cassettes were copied byte for byte from
the sync tests' recordings (see ``tests/integration/cassettes/async_*``). A miss
is a phase-stopping finding, not a flaky test: it would mean either the async
path generates different SQL or replay cannot intercept the async stack. Do not
re-record, do not add a record mode, do not loosen an assertion to make it pass.

Each test carries a **positional** ``@pytest.mark.adbc_cassette("<name>")``. The
name replaces node-id derivation entirely, which is what lets one cassette serve
both loop backends — without it the ``[asyncio]`` and ``[trio]`` parametrizations
would derive two different cassette paths and each demand its own recording. The
dialect therefore comes from which engine fixture the test requests, not from a
parametrized fixture.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from semolina import Dimension, Metric, SemanticView

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio", "trio"])
def anyio_backend(request: pytest.FixtureRequest) -> str:
    """Run every test in this module under both asyncio and Trio."""
    backend: str = request.param
    return backend


class Sales(SemanticView, view="sales_view"):
    """
    Synthetic SemanticView for async integration query tests.

    View name and field set match ``test_queries.py``'s ``Sales`` exactly. That
    is load-bearing: the generated SQL has to be byte-identical to what was
    recorded or the copied cassette misses.
    """

    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()


def _norm(value: Any) -> Any:
    """
    Normalize a numeric cell so it compares across backends.

    Mirrors ``test_queries._norm``: Snowflake returns ``Decimal`` where
    Databricks returns ``int``/``float``, so integral values collapse to ``int``
    and non-integral ones to ``float`` (never truncated).
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    return value


def _rows(raw: Any) -> list[tuple[Any, ...]]:
    """Normalize an iterable of row tuples for backend-agnostic comparison."""
    return [tuple(_norm(v) for v in row) for row in raw]


def _single_metric_query() -> Any:
    """Build the query ``test_queries.test_single_metric`` builds."""
    return Sales.query().metrics(Sales.revenue).order_by(Sales.revenue)


def _streaming_query() -> Any:
    """Build the query ``test_queries.test_streaming_iteration`` builds."""
    return Sales.query().metrics(Sales.revenue).dimensions(Sales.country).order_by(Sales.country)


async def _revenue_by_country(cursor: Any) -> dict[str, Any]:
    """
    Stream rows and build ``{country: revenue}``.

    Keyed rather than ordered for the reason the sync streaming test gives: each
    row holds one country (str) and one revenue (number), and neither
    ``Row.values()`` order nor the backend-specific metric column name is a
    Semolina contract.
    """
    result: dict[str, Any] = {}
    async for row in cursor:
        values = list(row.values())
        country = next(v for v in values if isinstance(v, str))
        revenue = next(_norm(v) for v in values if not isinstance(v, str))
        result[country] = revenue
    return result


@pytest.mark.adbc_cassette("async_single_metric_snowflake")
async def test_async_single_metric_snowflake(snowflake_async_engine: Any) -> None:
    """SUM(revenue) over the async path replays the Snowflake cassette."""
    async with await snowflake_async_engine.aexecute(_single_metric_query()) as cur:
        rows = _rows(await cur.fetchall())
    assert rows == [(5800,)]


@pytest.mark.adbc_cassette("async_single_metric_databricks")
async def test_async_single_metric_databricks(databricks_async_engine: Any) -> None:
    """SUM(revenue) over the async path replays the Databricks cassette."""
    async with await databricks_async_engine.aexecute(_single_metric_query()) as cur:
        rows = _rows(await cur.fetchall())
    assert rows == [(5800,)]


@pytest.mark.adbc_cassette("async_streaming_iteration_snowflake")
async def test_async_streaming_iteration_snowflake(snowflake_async_engine: Any) -> None:
    """``async for row in cursor`` yields the same Row mapping the sync test asserts."""
    async with await snowflake_async_engine.aexecute(_streaming_query()) as cur:
        result = await _revenue_by_country(cur)
    assert result == {"CA": 2800, "MX": 1500, "US": 1500}


@pytest.mark.adbc_cassette("async_streaming_iteration_databricks")
async def test_async_streaming_iteration_databricks(databricks_async_engine: Any) -> None:
    """``async for row in cursor`` yields the same Row mapping the sync test asserts."""
    async with await databricks_async_engine.aexecute(_streaming_query()) as cur:
        result = await _revenue_by_country(cur)
    assert result == {"CA": 2800, "MX": 1500, "US": 1500}
