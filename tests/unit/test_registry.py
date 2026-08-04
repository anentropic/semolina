"""
Tests for the engine registry module.

Expresses the Phase 44 contract: ``register("name", engine)`` stores a
name→Engine mapping and ``get_engine(name)`` returns the single ``Engine``
(which carries its own dialect and pool), replacing the old 3-arg tuple API.

Also covers the Phase 46 async registry (ASYNC-02, D-05): a **second, separate**
store for ``AsyncEngine`` values, so a lookup can never hand back an engine of
the wrong kind, plus the synchronous ``reset()`` that has to tear async pools
down inline because it cannot await.

RED until Plan 02 lands ``get_engine`` and the ``_engines`` map. The
``get_engine`` import below fails loudly (ImportError) against current
``main`` so the missing implementation is visible, not silently skipped.

Test classes:
- TestEngineRegistry: the name→Engine registry path (Phase 44)
- TestAsyncEngineRegistry: the separate name→AsyncEngine store (ASYNC-02)
- TestResetTearsDownBothStores: reset() across both kinds (ASYNC-02)
"""
# RED-first (Phase 44 Wave 0): get_engine and the 2-arg register() land in
# Plan 02. Until then basedpyright strict cannot see them, so scope-disable the
# two rules the not-yet-built API triggers. Plan 02 REMOVES this pragma when the
# tests go GREEN (it is intentionally not a `# type: ignore`).
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from semolina import registry
from semolina.engines.sql import DuckDBDialect, SnowflakeDialect
from semolina.registry import get_async_engine, get_engine


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset registry after each test to prevent state leaking."""
    yield
    registry.reset()


def _fake_engine(dialect: Any, pool: Any = None) -> Any:
    """
    Build a lightweight stand-in Engine for registry-bookkeeping tests.

    The registry only stores and returns the Engine, so a stand-in carrying
    ``dialect``, ``_pool``, and the real ``Engine.dispose`` teardown is
    sufficient to exercise registration, lookup, duplicate-name guarding,
    reset, and unregister without spinning up a real ADBC pool. ``dispose`` is
    wired to the real implementation (bound to the mock) so reset() teardown
    dispatch (close_pool vs pool.close) stays under test.
    """
    from semolina.engines.base import Engine

    if pool is None:
        # A non-ADBC stub pool (no _adbc_source) so dispose() takes the plain
        # pool.close() branch harmlessly for bookkeeping-only tests.
        pool = SimpleNamespace(close=lambda: None)

    engine = MagicMock(name="Engine")
    engine.dialect = dialect
    engine._pool = pool
    engine.dispose = lambda: Engine.dispose(engine)
    return engine


def _fake_async_engine(dialect: Any, inner_pool: Any = None) -> Any:
    """
    Build a lightweight stand-in AsyncEngine for registry-bookkeeping tests.

    The registry only stores and returns the engine, and tears it down through
    the *inner* synchronous pool that poolhouse's ``AsyncPool`` wraps, so a
    stand-in carrying ``dialect`` and a nested ``_pool._pool`` is enough to
    exercise registration, lookup, duplicate-name guarding, reset, and
    unregister without constructing a real async pool. ``_pool.close`` is a
    mock so tests can assert reset() never calls it — on a real ``AsyncPool``
    that returns an un-awaited coroutine and closes nothing.
    """
    if inner_pool is None:
        inner_pool = MagicMock(name="InnerSyncPool")
    engine = MagicMock(name="AsyncEngine")
    engine.dialect = dialect
    engine._pool = SimpleNamespace(_pool=inner_pool, close=MagicMock(name="AsyncPool.close"))
    return engine


def test_unregister_nonexistent():
    """Unregistering a nonexistent engine does not raise an error."""
    registry.unregister("nonexistent")  # Should not raise


# ---------------------------------------------------------------------------
# Engine registry tests (name -> Engine path)
# ---------------------------------------------------------------------------


class TestEngineRegistry:
    """Tests for the name→Engine registry path (register(engine) / get_engine)."""

    def test_register_stores_engine(self):
        """register("name", engine) stores the engine; get_engine retrieves it."""
        engine = _fake_engine(SnowflakeDialect())
        registry.register("default", engine)
        result = get_engine("default")
        assert result is engine
        assert isinstance(result.dialect, SnowflakeDialect)

    def test_register_duckdb_engine(self):
        """A DuckDB engine round-trips through register/get_engine with its dialect."""
        engine = _fake_engine(DuckDBDialect())
        registry.register("default", engine)
        result = get_engine("default")
        assert result is engine
        assert isinstance(result.dialect, DuckDBDialect)

    def test_get_engine_none_returns_default(self):
        """get_engine(None) returns the default engine."""
        engine = _fake_engine(SnowflakeDialect())
        registry.register("default", engine)
        result = get_engine(None)
        assert result is engine
        assert isinstance(result.dialect, SnowflakeDialect)

    def test_get_engine_no_arg_returns_default(self):
        """get_engine() with no argument returns the default engine."""
        engine = _fake_engine(SnowflakeDialect())
        registry.register("default", engine)
        result = get_engine()
        assert result is engine

    def test_get_engine_nonexistent_raises(self):
        """get_engine for nonexistent name raises ValueError."""
        with pytest.raises(ValueError, match="No engine registered"):
            get_engine("nonexistent")

    def test_get_engine_nonexistent_with_available(self):
        """get_engine error message lists available engines when some exist."""
        registry.register("prod", _fake_engine(SnowflakeDialect()))
        with pytest.raises(ValueError, match="Available engines"):
            get_engine("nonexistent")

    def test_duplicate_engine_name_raises(self):
        """Registering a duplicate engine name raises ValueError."""
        registry.register("default", _fake_engine(SnowflakeDialect()))
        with pytest.raises(ValueError, match="already registered"):
            registry.register("default", _fake_engine(DuckDBDialect()))

    def test_reset_clears_engines(self):
        """reset() clears the engine registry."""
        registry.register("default", _fake_engine(SnowflakeDialect()))
        registry.reset()
        with pytest.raises(ValueError):
            get_engine("default")

    def test_reset_uses_close_pool_for_adbc_pools(self):
        """reset() calls close_pool() for the engine's pool when it is an ADBC pool."""
        pool = MagicMock()
        pool._adbc_source = MagicMock()  # Mark as ADBC pool
        engine = _fake_engine(SnowflakeDialect(), pool=pool)
        registry.register("default", engine)

        with patch("adbc_poolhouse.close_pool") as mock_close_pool:
            registry.reset()
            mock_close_pool.assert_called_once_with(pool)
            pool.close.assert_not_called()

    def test_unregister_removes_engine(self):
        """unregister() removes the engine from the registry."""
        registry.register("default", _fake_engine(SnowflakeDialect()))
        registry.unregister("default")
        with pytest.raises(ValueError):
            get_engine("default")

    def test_multiple_engines(self):
        """Register multiple engines and retrieve them independently."""
        prod = _fake_engine(SnowflakeDialect())
        dev = _fake_engine(DuckDBDialect())
        registry.register("prod", prod)
        registry.register("dev", dev)
        prod_result = get_engine("prod")
        dev_result = get_engine("dev")
        assert prod_result is prod
        assert isinstance(prod_result.dialect, SnowflakeDialect)
        assert dev_result is dev
        assert isinstance(dev_result.dialect, DuckDBDialect)

    def test_register_with_empty_name(self):
        """Registering an engine with an empty string name works."""
        engine = _fake_engine(SnowflakeDialect())
        registry.register("", engine)
        result = get_engine("")
        assert result is engine
        assert isinstance(result.dialect, SnowflakeDialect)


# ---------------------------------------------------------------------------
# Async engine registry tests (name -> AsyncEngine path, ASYNC-02 / D-05)
# ---------------------------------------------------------------------------


class TestAsyncEngineRegistry:
    """Tests for the separate name→AsyncEngine store (ASYNC-02, D-05)."""

    def test_register_async_stores_engine(self):
        """register_async_engine("name", engine) stores it; get_async_engine retrieves it."""
        engine = _fake_async_engine(DuckDBDialect())
        registry.register_async_engine("default", engine)
        result = get_async_engine("default")
        assert result is engine
        assert isinstance(result.dialect, DuckDBDialect)

    def test_get_async_engine_none_returns_default(self):
        """get_async_engine(None) returns the default async engine."""
        engine = _fake_async_engine(SnowflakeDialect())
        registry.register_async_engine("default", engine)
        assert get_async_engine(None) is engine

    def test_get_async_engine_no_arg_returns_default(self):
        """get_async_engine() with no argument returns the default async engine."""
        engine = _fake_async_engine(SnowflakeDialect())
        registry.register_async_engine("default", engine)
        assert get_async_engine() is engine

    def test_duplicate_async_engine_name_raises(self):
        """Registering a duplicate async engine name raises ValueError naming the name."""
        registry.register_async_engine("reports", _fake_async_engine(SnowflakeDialect()))
        with pytest.raises(ValueError, match="'reports' is already registered"):
            registry.register_async_engine("reports", _fake_async_engine(DuckDBDialect()))

    def test_same_name_may_hold_both_kinds(self):
        """One name may hold a sync and an async engine; each lookup returns its own kind."""
        sync_engine = _fake_engine(SnowflakeDialect())
        async_engine = _fake_async_engine(DuckDBDialect())
        registry.register("reports", sync_engine)
        registry.register_async_engine("reports", async_engine)

        assert get_engine("reports") is sync_engine
        assert get_async_engine("reports") is async_engine

    def test_get_async_engine_never_falls_back_to_sync_store(self):
        """A name registered only as a sync engine is not visible to get_async_engine."""
        registry.register("reports", _fake_engine(SnowflakeDialect()))
        with pytest.raises(ValueError, match="No async engine registered"):
            get_async_engine("reports")

    def test_get_async_engine_nonexistent_lists_available_sorted(self):
        """The miss message lists the registered async engine names, sorted."""
        registry.register_async_engine("prod", _fake_async_engine(SnowflakeDialect()))
        registry.register_async_engine("dev", _fake_async_engine(DuckDBDialect()))
        with pytest.raises(ValueError) as excinfo:
            get_async_engine("nonexistent")
        assert "Available async engines: 'dev', 'prod'" in str(excinfo.value)

    def test_get_async_engine_empty_registry_hint_names_async_register(self):
        """With no async engines registered the hint points at register_async_engine."""
        with pytest.raises(ValueError) as excinfo:
            get_async_engine("nonexistent")
        message = str(excinfo.value)
        assert "register_async_engine" in message
        assert "create_async_engine" in message

    def test_unregister_async_nonexistent_is_silent(self):
        """Unregistering an absent async engine is a silent no-op."""
        registry.unregister_async_engine("nonexistent")  # Should not raise

    def test_unregister_async_removes_engine(self):
        """unregister_async_engine() removes the engine from the async store."""
        registry.register_async_engine("default", _fake_async_engine(DuckDBDialect()))
        registry.unregister_async_engine("default")
        with pytest.raises(ValueError):
            get_async_engine("default")

    def test_unregister_async_leaves_sync_registration(self):
        """Unregistering the async engine under a name leaves the sync one registered."""
        sync_engine = _fake_engine(SnowflakeDialect())
        registry.register("reports", sync_engine)
        registry.register_async_engine("reports", _fake_async_engine(DuckDBDialect()))

        registry.unregister_async_engine("reports")

        assert get_engine("reports") is sync_engine
        with pytest.raises(ValueError):
            get_async_engine("reports")

    def test_registration_functions_are_not_coroutines(self):
        """All three async-registry functions are plain defs, not coroutines."""
        import inspect

        for func in (
            registry.register_async_engine,
            registry.get_async_engine,
            registry.unregister_async_engine,
            registry.reset,
        ):
            assert not inspect.iscoroutinefunction(func), func.__name__

    def test_stores_are_distinct_objects(self):
        """The sync and async stores are two dicts, not one dict holding a union."""
        assert registry._async_engines is not registry._engines
        assert isinstance(registry._async_engines, dict)


class TestResetTearsDownBothStores:
    """Tests for the synchronous reset() across both engine kinds (ASYNC-02)."""

    def test_reset_clears_both_registries(self):
        """reset() empties the sync store and the async store."""
        registry.register("default", _fake_engine(SnowflakeDialect()))
        registry.register_async_engine("default", _fake_async_engine(DuckDBDialect()))

        registry.reset()

        with pytest.raises(ValueError):
            get_engine("default")
        with pytest.raises(ValueError):
            get_async_engine("default")

    def test_reset_closes_inner_sync_pool_not_the_async_pool(self):
        """reset() disposes an async engine via close_pool on the inner sync pool."""
        engine = _fake_async_engine(DuckDBDialect())
        registry.register_async_engine("default", engine)

        with patch("adbc_poolhouse.close_pool") as mock_close_pool:
            registry.reset()

        mock_close_pool.assert_called_once_with(engine._pool._pool)
        # AsyncPool.close() is a coroutine: calling it here would return an
        # un-awaited coroutine object and close nothing.
        engine._pool.close.assert_not_called()

    def test_reset_clears_both_stores_when_async_teardown_raises(self):
        """A failing async teardown does not stop reset() from clearing either store."""
        engine = _fake_async_engine(DuckDBDialect())
        registry.register("default", _fake_engine(SnowflakeDialect()))
        registry.register_async_engine("default", engine)

        with patch("adbc_poolhouse.close_pool", side_effect=OSError("driver shutdown")):
            registry.reset()

        assert registry._async_engines == {}
        assert registry._engines == {}

    def test_reset_reports_a_missing_inner_pool(self):
        """
        A poolhouse release without ``AsyncPool._pool`` raises a message naming the cause.

        The inner sync pool is how a synchronous ``reset()`` tears an async pool
        down without awaiting, and it is reached through an attribute
        ``AsyncPool`` does not publish. The guard is deliberately placed
        *outside* the narrow ``(OSError, RuntimeError)`` suppression: a package
        contract break is not the flaky driver shutdown that suppression exists
        to tolerate, and swallowing it would leave every async pool in the
        process unclosed and unmentioned.
        """
        engine = MagicMock(name="AsyncEngine")
        engine.dialect = DuckDBDialect()
        # Only connect() and close(): the 1.6.2 public AsyncPool surface, minus
        # the private attribute reset() currently depends on.
        engine._pool = SimpleNamespace(connect=lambda: None, close=lambda: None)
        registry.register_async_engine("default", engine)

        try:
            with pytest.raises(RuntimeError, match="adbc-poolhouse"):
                registry.reset()
        finally:
            registry._async_engines.clear()

    def test_reset_actually_tears_down_a_real_async_pool(self, async_duckdb_engine: Any):
        """reset() empties a real async engine's pooled connections, not just the dict."""
        inner_pool = async_duckdb_engine._pool._pool
        # Prime the pool so there is observable state to tear down: check a
        # connection out through the inner sync pool and return it.
        conn = inner_pool.connect()
        conn.close()
        assert inner_pool.checkedin() == 1

        registry.register_async_engine("default", async_duckdb_engine)
        registry.reset()

        assert inner_pool.checkedin() == 0
