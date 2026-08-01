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
from models import Sales

from semolina.acursor import AsyncSemolinaCursor
from semolina.query import _Query
from semolina.results import Row

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio", "trio"])
def anyio_backend(request: pytest.FixtureRequest) -> str:
    """Run every test in this module under both asyncio and Trio."""
    backend: str = request.param
    return backend


class TestAsyncExecute:
    """Test AsyncEngine.aexecute() end to end against real DuckDB (ASYNC-01)."""

    async def test_aexecute_streams_rows_and_returns_connection(
        self, async_duckdb_engine: Any
    ) -> None:
        """Executing a query yields Row objects and checks the connection back in."""
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)

        rows: list[Row] = []
        cursor = await async_duckdb_engine.aexecute(query)
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
