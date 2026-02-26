"""Tests for the engine registry module."""

import pytest

from cubano import registry
from cubano.engines import MockEngine


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset registry after each test to prevent state leaking."""
    yield
    registry.reset()


def test_register_and_retrieve():
    """Register a default engine and retrieve it."""
    engine = MockEngine()
    registry.register("default", engine)
    assert registry.get_engine() is engine


def test_register_named_engine():
    """Register a named engine and retrieve it by name."""
    engine = MockEngine()
    registry.register("warehouse", engine)
    assert registry.get_engine("warehouse") is engine


def test_multiple_engines():
    """Register multiple engines and retrieve them independently."""
    default_engine = MockEngine()
    warehouse_engine = MockEngine()
    registry.register("default", default_engine)
    registry.register("warehouse", warehouse_engine)
    assert registry.get_engine() is default_engine
    assert registry.get_engine("warehouse") is warehouse_engine


def test_duplicate_name_raises():
    """Registering a duplicate name raises ValueError."""
    e1 = MockEngine()
    e2 = MockEngine()
    registry.register("default", e1)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("default", e2)


def test_get_unregistered_raises():
    """Getting an unregistered engine raises ValueError with available engines."""
    with pytest.raises(ValueError, match="No engine registered"):
        registry.get_engine("nonexistent")


def test_get_default_when_none_registered():
    """Getting default engine when none registered raises ValueError with helpful message."""
    with pytest.raises(ValueError, match="No engine registered"):
        registry.get_engine()


def test_unregister():
    """Unregistering an engine removes it from the registry."""
    engine = MockEngine()
    registry.register("default", engine)
    registry.unregister("default")
    with pytest.raises(ValueError):
        registry.get_engine()


def test_unregister_nonexistent():
    """Unregistering a nonexistent engine does not raise an error."""
    registry.unregister("nonexistent")  # Should not raise


def test_reset_clears_all():
    """Reset clears all registered engines."""
    e1 = MockEngine()
    e2 = MockEngine()
    registry.register("default", e1)
    registry.register("warehouse", e2)
    registry.reset()
    with pytest.raises(ValueError):
        registry.get_engine()
    with pytest.raises(ValueError):
        registry.get_engine("warehouse")


def test_get_engine_with_none_returns_default():
    """get_engine(None) is equivalent to get_engine()."""
    engine = MockEngine()
    registry.register("default", engine)
    assert registry.get_engine(None) is engine


def test_register_with_empty_name():
    """Registering with an empty string name works."""
    engine = MockEngine()
    registry.register("", engine)
    assert registry.get_engine("") is engine
