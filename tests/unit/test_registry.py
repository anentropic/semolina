"""Tests for the pool registry module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from semolina import registry
from semolina.dialect import Dialect
from semolina.engines.sql import DuckDBDialect, SnowflakeDialect


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset registry after each test to prevent state leaking."""
    yield
    registry.reset()


def test_unregister_nonexistent():
    """Unregistering a nonexistent pool does not raise an error."""
    registry.unregister("nonexistent")  # Should not raise


# ---------------------------------------------------------------------------
# Pool registry tests (pool+dialect path)
# ---------------------------------------------------------------------------


class TestPoolRegistry:
    """Tests for the new pool+dialect registry path."""

    def test_register_with_dialect_string(self):
        """Register with dialect string stores pool and get_pool retrieves it."""
        pool = object()
        registry.register("default", pool, dialect="snowflake")
        result_pool, result_dialect = registry.get_pool("default")
        assert result_pool is pool
        assert isinstance(result_dialect, SnowflakeDialect)

    def test_register_with_dialect_enum(self):
        """Register with Dialect enum stores pool and get_pool retrieves correct type."""
        pool = object()
        registry.register("default", pool, dialect=Dialect.DUCKDB)
        result_pool, result_dialect = registry.get_pool("default")
        assert result_pool is pool
        assert isinstance(result_dialect, DuckDBDialect)

    def test_get_pool_none_returns_default(self):
        """get_pool(None) returns the default pool."""
        pool = object()
        registry.register("default", pool, dialect="snowflake")
        result_pool, result_dialect = registry.get_pool(None)
        assert result_pool is pool
        assert isinstance(result_dialect, SnowflakeDialect)

    def test_get_pool_no_arg_returns_default(self):
        """get_pool() with no argument returns the default pool."""
        pool = object()
        registry.register("default", pool, dialect="snowflake")
        result_pool, _ = registry.get_pool()
        assert result_pool is pool

    def test_get_pool_nonexistent_raises(self):
        """get_pool for nonexistent name raises ValueError."""
        with pytest.raises(ValueError, match="No pool registered"):
            registry.get_pool("nonexistent")

    def test_get_pool_nonexistent_with_available(self):
        """get_pool error message lists available pools when some exist."""
        pool = object()
        registry.register("prod", pool, dialect="snowflake")
        with pytest.raises(ValueError, match="Available pools"):
            registry.get_pool("nonexistent")

    def test_duplicate_pool_name_raises(self):
        """Registering duplicate pool name raises ValueError."""
        p1 = object()
        p2 = object()
        registry.register("default", p1, dialect="snowflake")
        with pytest.raises(ValueError, match="already registered"):
            registry.register("default", p2, dialect="databricks")

    def test_reset_clears_pools(self):
        """reset() clears the pool registry."""
        pool = object()
        registry.register("default", pool, dialect="snowflake")
        registry.reset()
        with pytest.raises(ValueError):
            registry.get_pool("default")

    def test_reset_calls_close_on_pools(self):
        """reset() calls .close() on each pool that has a close method."""

        class FakePool:
            closed = False

            def close(self):
                self.closed = True

        pool = FakePool()
        registry.register("default", pool, dialect="duckdb")
        registry.reset()
        assert pool.closed is True

    def test_reset_uses_close_pool_for_adbc_pools(self):
        """reset() calls close_pool() for pools with _adbc_source attribute."""
        pool = MagicMock()
        pool._adbc_source = MagicMock()  # Mark as ADBC pool
        registry.register("default", pool, dialect="snowflake")

        with patch("adbc_poolhouse.close_pool") as mock_close_pool:
            registry.reset()
            mock_close_pool.assert_called_once_with(pool)
            pool.close.assert_not_called()

    def test_unregister_removes_pool(self):
        """unregister() removes from the pool registry."""
        pool = object()
        registry.register("default", pool, dialect="snowflake")
        registry.unregister("default")
        with pytest.raises(ValueError):
            registry.get_pool("default")

    def test_register_with_duckdb_dialect(self):
        """Register with dialect='duckdb' stores pool with DuckDBDialect (DUCK-02)."""
        pool = object()
        registry.register("db", pool, dialect="duckdb")
        result_pool, result_dialect = registry.get_pool("db")
        assert result_pool is pool
        assert isinstance(result_dialect, DuckDBDialect)

    def test_multiple_pools(self):
        """Register multiple pools and retrieve them independently."""
        p1 = object()
        p2 = object()
        registry.register("prod", p1, dialect="snowflake")
        registry.register("dev", p2, dialect="duckdb")
        prod_pool, prod_dialect = registry.get_pool("prod")
        dev_pool, dev_dialect = registry.get_pool("dev")
        assert prod_pool is p1
        assert isinstance(prod_dialect, SnowflakeDialect)
        assert dev_pool is p2
        assert isinstance(dev_dialect, DuckDBDialect)

    def test_register_with_empty_name(self):
        """Registering a pool with an empty string name works."""
        pool = object()
        registry.register("", pool, dialect="snowflake")
        result_pool, result_dialect = registry.get_pool("")
        assert result_pool is pool
        assert isinstance(result_dialect, SnowflakeDialect)
