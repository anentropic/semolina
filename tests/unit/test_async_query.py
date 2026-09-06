"""
Tests for the query builder's async execution entry point.

Tests cover:
- ASYNC-02: ``await Sales.query().metrics(...).dimensions(...).aexecute()``
  resolves an engine from the async registry, executes it, and returns an open
  ``AsyncSemolinaCursor`` that streams ``Row`` objects.

The plan's load-bearing claims about *where* the engine comes from are tested
directly: ``aexecute`` reads the async store and ``execute`` reads the
synchronous one, so a single name may serve both paths at once and neither can
hand back an engine of the wrong kind.

Every test in this module runs twice, once under asyncio and once under Trio,
via the module-local parametrized ``anyio_backend`` fixture. The fixture is
module-local rather than a repository-wide ini option because ``testpaths``
includes ``src`` under ``--doctest-modules``, so a repo-wide setting would have
a blast radius this does not need.

Test classes:
- TestAsyncQueryExecute: end-to-end execution through the query builder (ASYNC-02)
- TestUsingResolvesPerRegistry: .using() against two separate stores (ASYNC-02)
- TestPublicAsyncExports: the async surface is reachable from ``import semolina``
"""
# Test-only: the tests reach the owned async pool's inner sync pool via
# engine._pool._pool to assert checkout/checkin. Scope-disable the
# private-access rule (intentionally not a `# type: ignore`).
# pyright: reportPrivateUsage=false

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from models import Sales

import semolina
from semolina.acursor import AsyncSemolinaCursor
from semolina.cursor import SemolinaCursor
from semolina.results import Row

if TYPE_CHECKING:
    from semolina.query import _Query

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio", "trio"])
def anyio_backend(request: pytest.FixtureRequest) -> str:
    """Run every test in this module under both asyncio and Trio."""
    backend: str = request.param
    return backend


class TestAsyncQueryExecute:
    """Test _Query.aexecute() end to end against real DuckDB (ASYNC-02)."""

    async def test_aexecute_streams_rows_from_the_query_builder(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """A query built with Sales.query() executes through the async registry."""
        semolina.register_async_engine("default", async_duckdb_engine)

        rows: list[Row] = []
        cursor = await sales_query.aexecute()
        assert isinstance(cursor, AsyncSemolinaCursor)
        async with cursor as cur:
            async for row in cur:
                rows.append(row)

        assert len(rows) == 2
        assert all(isinstance(row, Row) for row in rows)
        assert all(set(row.keys()) == {"revenue", "country"} for row in rows)
        assert {row["country"]: row["revenue"] for row in rows} == {"US": 1500, "CA": 2000}

    async def test_aexecute_returns_the_connection_to_the_pool(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """Closing the cursor checks the connection back in."""
        semolina.register_async_engine("default", async_duckdb_engine)

        async with await sales_query.aexecute() as cur:
            await cur.fetchall_rows()

        assert async_duckdb_engine._pool._pool.checkedout() == 0

    async def test_aexecute_resolves_a_named_engine(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """.using(name) resolves that name in the async registry."""
        semolina.register_async_engine("reports", async_duckdb_engine)

        async with await sales_query.using("reports").aexecute() as cur:
            rows = await cur.fetchall_rows()

        assert len(rows) == 2

    async def test_aexecute_invalid_query_raises_before_any_checkout(
        self, async_duckdb_engine: Any
    ) -> None:
        """
        A query with no metrics and no dimensions fails validation, not execution.

        The pool assertion is what makes this more than a duplicate of the sync
        validation test: nothing was ever checked out, so an invalid query
        cannot consume a pool slot or open a physical connection. A pool that
        had served and reclaimed a connection would report ``checkedin() == 1``.
        """
        semolina.register_async_engine("default", async_duckdb_engine)
        inner_pool = async_duckdb_engine._pool._pool

        with pytest.raises(ValueError, match="metric|dimension"):
            await Sales.query().aexecute()

        assert inner_pool.checkedout() == 0
        assert inner_pool.checkedin() == 0

    async def test_aexecute_matches_the_sync_validation_error(
        self, async_duckdb_engine: Any
    ) -> None:
        """The async path raises the same ValueError text the sync path raises."""
        semolina.register_async_engine("default", async_duckdb_engine)

        with pytest.raises(ValueError) as sync_exc:
            Sales.query()._validate_for_execution()
        with pytest.raises(ValueError) as async_exc:
            await Sales.query().aexecute()

        assert str(async_exc.value) == str(sync_exc.value)

    async def test_aexecute_unknown_name_raises_from_the_async_registry(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """An unregistered name fails the async lookup, not the sync one."""
        semolina.register_async_engine("default", async_duckdb_engine)

        with pytest.raises(ValueError, match="No async engine registered with name 'missing'"):
            await sales_query.using("missing").aexecute()


class TestUsingResolvesPerRegistry:
    """Test that one name may serve the sync and async paths at once (ASYNC-02, D-05)."""

    async def test_same_name_serves_both_paths(
        self, sales_query: _Query, duckdb_pool: Any, async_duckdb_engine: Any
    ) -> None:
        """
        "default" holds a sync engine and an async engine, and each path takes its own.

        ``duckdb_pool`` has already registered a synchronous engine under
        ``"default"``. Registering an async engine under the same name is legal
        precisely because the stores are separate, and the two cursor types
        prove each call site resolved its own kind.
        """
        semolina.register_async_engine("default", async_duckdb_engine)

        with sales_query.execute() as sync_cursor:
            sync_rows = sync_cursor.fetchall_rows()
        async with await sales_query.aexecute() as async_cursor:
            async_rows = await async_cursor.fetchall_rows()

            assert isinstance(async_cursor, AsyncSemolinaCursor)
        assert isinstance(sync_cursor, SemolinaCursor)

        assert {row["country"]: row["revenue"] for row in sync_rows} == {"US": 1500, "CA": 2000}
        assert {row["country"]: row["revenue"] for row in async_rows} == {"US": 1500, "CA": 2000}

    async def test_async_lookup_ignores_a_sync_only_registration(
        self, sales_query: _Query, duckdb_pool: Any
    ) -> None:
        """With only a sync engine registered, aexecute raises rather than using it."""
        with pytest.raises(ValueError, match="No async engine registered"):
            await sales_query.aexecute()


class TestPublicAsyncExports:
    """Test that the async surface is reachable from a plain ``import semolina``."""

    async def test_async_names_are_exported(self) -> None:
        """The five async names resolve on the package and appear in __all__."""
        names = (
            "AsyncSemolinaCursor",
            "create_async_engine",
            "get_async_engine",
            "register_async_engine",
            "unregister_async_engine",
        )
        for name in names:
            assert getattr(semolina, name, None) is not None, name
            assert name in semolina.__all__, name

    async def test_exported_names_are_the_registry_functions(self) -> None:
        """The exported registry functions are the registry module's own objects."""
        from semolina import registry

        assert semolina.get_async_engine is registry.get_async_engine
        assert semolina.register_async_engine is registry.register_async_engine
        assert semolina.unregister_async_engine is registry.unregister_async_engine
