"""
Tests for AsyncEngine query execution over a real in-memory DuckDB async pool.

Tests cover:
- ASYNC-01: ``await engine.aexecute(query)`` returns the same result surface as
  ``.execute()``, with awaited fetches and ``async for`` row streaming.

Every test in this module runs twice, once under asyncio and once under Trio,
via the module-local parametrized ``anyio_backend`` fixture. The fixture is
module-local rather than a repository-wide ini option because ``testpaths``
includes ``src`` under ``--doctest-modules``, so a repo-wide setting would have
a blast radius this does not need.

Test classes:
- TestAsyncExecute: end-to-end execution and connection checkin (ASYNC-01)
"""
# Test-only: the async tests reach the owned async pool's inner sync pool via
# engine._pool._pool to assert checkin. Scope-disable the private-access rule
# (intentionally not a `# type: ignore`).
# pyright: reportPrivateUsage=false

from __future__ import annotations

from typing import Any

import pytest

from semolina import Metric, SemanticView
from semolina.acursor import AsyncSemolinaCursor
from semolina.query import _Query
from semolina.results import Row

pytestmark = pytest.mark.anyio


class MissingSales(SemanticView, view="no_such_view"):
    """A view the DuckDB fixture does not define, so its query fails in the driver."""

    total = Metric()


@pytest.fixture(params=["asyncio", "trio"])
def anyio_backend(request: pytest.FixtureRequest) -> str:
    """Run every test in this module under both asyncio and Trio."""
    backend: str = request.param
    return backend


class TestAsyncExecute:
    """Test AsyncEngine.aexecute() end to end against real DuckDB (ASYNC-01)."""

    async def test_aexecute_streams_rows_and_returns_connection(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """Executing a query yields Row objects and checks the connection back in."""
        rows: list[Row] = []
        cursor = await async_duckdb_engine.aexecute(sales_query)
        assert isinstance(cursor, AsyncSemolinaCursor)
        async with cursor as cur:
            async for row in cur:
                rows.append(row)

        assert len(rows) == 2
        assert all(isinstance(row, Row) for row in rows)
        assert all(set(row.keys()) == {"revenue", "country"} for row in rows)
        by_country = {row["country"]: row["revenue"] for row in rows}
        assert by_country == {"US": 1500, "CA": 2000}

        # The checked-out slot is returned to the pool by the cursor's close.
        assert async_duckdb_engine._pool._pool.checkedout() == 0

    async def test_failed_execute_returns_the_slot(self, async_duckdb_engine: Any) -> None:
        """
        A statement the driver rejects still checks its connection back in.

        On the success path the check-in belongs to the cursor's ``aclose()``,
        and a failed ``execute()`` never produces a cursor — so ``aexecute``'s
        own error handler is the only thing that can return the slot. Nothing
        else in the suite drives that handler deterministically: the
        cancellation tests either cancel before a connection is checked out or
        depend on a multi-second measured query.
        """
        inner_pool = async_duckdb_engine._pool._pool

        with pytest.raises(Exception, match="no_such_view"):
            await async_duckdb_engine.aexecute(_Query().metrics(MissingSales.total))

        assert inner_pool.checkedout() == 0
        assert inner_pool.checkedin() == 1


class TestAsyncConcurrency:
    """
    Test that the event loop stays free and two queries run at once (ASYNC-01).

    These tests import anyio directly. The TID251 Posture A ban scopes to
    ``src/semolina/`` only, and the Trio half of the matrix needs it.
    """

    async def test_concurrency_loop_stays_free_during_query(
        self, sales_query: _Query, async_duckdb_file_engine: Any
    ) -> None:
        """
        A sibling task scheduled while a query is in flight runs at least once.

        The assertion is on a scheduling counter, not on elapsed time: a timing
        threshold would be a flaky proxy for the real claim. The sibling parks
        on ``started`` until the query task is about to enter ``aexecute``, so
        it can only count if the query yields the loop. Were Semolina running
        the warehouse call on the loop thread, the coroutine body would run
        straight through with no scheduling point between the call's start and
        its completion, and the counter would be 0.
        """
        import anyio

        started = anyio.Event()
        done = anyio.Event()
        spins = 0
        rows: list[Row] = []

        async def run_query() -> None:
            try:
                started.set()
                async with await async_duckdb_file_engine.aexecute(sales_query) as cur:
                    async for row in cur:
                        rows.append(row)
            finally:
                done.set()

        async def spin() -> None:
            nonlocal spins
            await started.wait()
            while not done.is_set():
                spins += 1
                await anyio.sleep(0)

        async with anyio.create_task_group() as tg:
            tg.start_soon(spin)
            tg.start_soon(run_query)

        assert rows, "the query must actually have returned rows"
        assert spins >= 1

    async def test_concurrency_two_queries_share_the_pool(
        self, sales_query: _Query, async_duckdb_file_engine: Any
    ) -> None:
        """
        Two aexecute calls in one task group both return rows, and every slot returns.

        The pool-size assertion is what makes the two-connection claim
        meaningful rather than two serialized checkouts of a single slot.
        """
        import anyio

        inner_pool = async_duckdb_file_engine._pool._pool
        assert inner_pool.size() > 1

        results: list[list[Row]] = []

        async def run_query() -> None:
            async with await async_duckdb_file_engine.aexecute(sales_query) as cur:
                results.append([row async for row in cur])

        async with anyio.create_task_group() as tg:
            tg.start_soon(run_query)
            tg.start_soon(run_query)

        assert len(results) == 2
        for rows in results:
            assert {row["country"]: row["revenue"] for row in rows} == {"US": 1000, "CA": 2000}

        assert inner_pool.checkedout() == 0
