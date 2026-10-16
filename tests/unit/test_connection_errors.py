"""
A failure to reach the warehouse raises ``SemolinaConnectionError`` on every path (ARCH-1).

``SemolinaConnectionError`` says the engine could not connect to or authenticate with the
warehouse. Before 0.7.0 only ``introspect()`` raised it: building an engine, or checking a
connection out to run a query, passed the driver's own error through, so an ``except
SemolinaError`` handler around ``execute()`` caught no connection failure at all.

A statement the warehouse rejects (a missing view, say) is not a connection failure. It
still raises the driver's own error, as the web-api how-to documents.
"""

# Test-only: the checkout tests patch the owned pool's ``connect`` to stand in for a
# warehouse that refuses the connection.
# pyright: reportPrivateUsage=false

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from semolina import Metric, SemanticView
from semolina.exceptions import SemolinaConnectionError

if TYPE_CHECKING:
    from pathlib import Path

pytest.importorskip("adbc_driver_duckdb")


class Sales(SemanticView, view="sales_view"):
    """A view the shared DuckDB fixtures define."""

    revenue = Metric()


class Missing(SemanticView, view="no_such_view"):
    """A view nobody defines, so its query fails in the driver after connecting."""

    revenue = Metric()


def _refused() -> Exception:
    """Return the error a driver raises when the warehouse refuses the connection."""
    import adbc_driver_manager

    return adbc_driver_manager.OperationalError(
        "IO Error: could not reach the warehouse",
        status_code=adbc_driver_manager.AdbcStatusCode.IO,
    )


def _unopenable(tmp_path: Path) -> Any:
    """Return a DuckDB config whose database cannot be opened."""
    from adbc_poolhouse import DuckDBConfig

    return DuckDBConfig(database=str(tmp_path / "missing" / "x.db"), read_only=True, pool_size=1)


def test_create_engine_that_cannot_connect_raises_semolina_connection_error(
    tmp_path: Path,
) -> None:
    """``create_engine`` opens the pool's first connection; its failure is a connection error."""
    from semolina.config import create_engine

    with pytest.raises(SemolinaConnectionError) as raised:
        create_engine(_unopenable(tmp_path))

    import adbc_driver_manager

    assert isinstance(raised.value.__cause__, adbc_driver_manager.Error)


def test_create_async_engine_that_cannot_connect_raises_semolina_connection_error(
    tmp_path: Path,
) -> None:
    """The async factory reports the same failure the same way."""
    pytest.importorskip("anyio")
    from semolina.config import create_async_engine

    with pytest.raises(SemolinaConnectionError):
        create_async_engine(_unopenable(tmp_path))


def test_execute_whose_checkout_fails_raises_semolina_connection_error(duckdb_pool: Any) -> None:
    """A refused checkout inside ``execute()`` is a connection error, chained to the driver's."""
    from semolina.registry import get_engine

    engine = get_engine("default")
    error = _refused()
    with (
        patch.object(engine._pool, "connect", side_effect=error),
        pytest.raises(SemolinaConnectionError) as raised,
    ):
        Sales.query().metrics(Sales.revenue).execute()
    assert raised.value.__cause__ is error


def test_a_statement_the_warehouse_rejects_keeps_the_driver_error(duckdb_pool: Any) -> None:
    """A missing view fails after connecting, so it is the driver's error, not a connection one."""
    import adbc_driver_manager

    with pytest.raises(adbc_driver_manager.Error) as raised:
        Missing.query().metrics(Missing.revenue).execute()
    assert not isinstance(raised.value, SemolinaConnectionError)


@pytest.mark.anyio
async def test_aexecute_whose_checkout_fails_raises_semolina_connection_error(
    async_duckdb_engine: Any,
) -> None:
    """The async checkout reports a refused connection the same way."""
    error = _refused()
    with (
        patch.object(async_duckdb_engine._pool, "connect", side_effect=error),
        pytest.raises(SemolinaConnectionError) as raised,
    ):
        await async_duckdb_engine.aexecute(Sales.query().metrics(Sales.revenue))
    assert raised.value.__cause__ is error
