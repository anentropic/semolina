"""
Tests for the Engine ABC.

Tests cover:
- Engine ABC abstract interface (cannot instantiate, abstract methods enforced)

Real engine execution and SQL generation are exercised by the DuckDB
integration tests; this module only verifies the abstract interface.
"""

import pytest

from semolina.engines.base import Engine


class TestEngineABC:
    """Test Engine abstract base class."""

    def test_engine_cannot_be_instantiated(self):
        """Engine ABC should not be instantiable directly."""
        with pytest.raises(TypeError):
            Engine()  # type: ignore[abstract]

    def test_engine_to_sql_is_abstract(self):
        """Engine.to_sql() is abstract and must be implemented."""

        class IncompleteEngine(Engine):
            def execute(self, query):  # type: ignore[no-untyped-def]
                pass

            def introspect(self, view_name):  # type: ignore[no-untyped-def]
                pass

        with pytest.raises(TypeError):
            IncompleteEngine()  # type: ignore[abstract]

    def test_engine_execute_is_abstract(self):
        """Engine.execute() is abstract and must be implemented."""

        class IncompleteEngine(Engine):
            def to_sql(self, query):  # type: ignore[no-untyped-def]
                pass

            def introspect(self, view_name):  # type: ignore[no-untyped-def]
                pass

        with pytest.raises(TypeError):
            IncompleteEngine()  # type: ignore[abstract]

    def test_engine_introspect_is_abstract(self):
        """Engine.introspect() is abstract and must be implemented."""

        class IncompleteEngine(Engine):
            def to_sql(self, query):  # type: ignore[no-untyped-def]
                pass

            def execute(self, query):  # type: ignore[no-untyped-def]
                pass

        with pytest.raises(TypeError):
            IncompleteEngine()  # type: ignore[abstract]
