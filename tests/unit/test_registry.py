"""
Tests for the engine registry module.

Expresses the Phase 44 contract: ``register("name", engine)`` stores a
name→Engine mapping and ``get_engine(name)`` returns the single ``Engine``
(which carries its own dialect and pool), replacing the old 3-arg tuple API.

RED until Plan 02 lands ``get_engine`` and the ``_engines`` map. The
``get_engine`` import below fails loudly (ImportError) against current
``main`` so the missing implementation is visible, not silently skipped.
"""
# RED-first (Phase 44 Wave 0): get_engine and the 2-arg register() land in
# Plan 02. Until then basedpyright strict cannot see them, so scope-disable the
# two rules the not-yet-built API triggers. Plan 02 REMOVES this pragma when the
# tests go GREEN (it is intentionally not a `# type: ignore`).
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from semolina import registry
from semolina.engines.sql import DuckDBDialect, SnowflakeDialect
from semolina.registry import get_engine


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset registry after each test to prevent state leaking."""
    yield
    registry.reset()


def _fake_engine(dialect: Any, pool: Any = None) -> Any:
    """
    Build a lightweight stand-in Engine for registry-bookkeeping tests.

    The registry only stores and returns the Engine, so a stand-in carrying
    ``dialect`` and ``_pool`` is sufficient to exercise registration, lookup,
    duplicate-name guarding, reset, and unregister without spinning up a real
    ADBC pool.
    """
    engine = MagicMock(name="Engine")
    engine.dialect = dialect
    engine._pool = pool
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
