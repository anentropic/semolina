"""
Tests for the Engine ABC's abstract surface.

Real engine execution and SQL generation are exercised by the DuckDB-backed tests; this
module only pins which methods a backend must implement.
"""

from typing import Any

from semolina.engines.base import Engine
from semolina.engines.sql import DuckDBDialect


class TestEngineABC:
    """A backend implements ``introspect`` and inherits everything else."""

    def test_introspect_is_the_only_abstract_method(self) -> None:
        """
        ``introspect`` is abstract; ``execute``, ``connect`` and ``dispose`` are inherited.

        Asserted on the set itself so the test fails in both directions: a method that stops
        being abstract, and one that starts being abstract and would break every backend.
        """
        assert Engine.__abstractmethods__ == frozenset({"introspect"})

    def test_a_subclass_implementing_introspect_can_be_constructed(self) -> None:
        """Implementing the abstract set is enough; the constructor asks for nothing else."""

        class MinimalEngine(Engine):
            def introspect(self, view_name: str) -> Any:
                return view_name

        engine = MinimalEngine(pool=object(), dialect=DuckDBDialect())

        assert engine.introspect("sales_view") == "sales_view"


class TestEngineSiblings:
    """``Engine`` and ``AsyncEngine`` share their state through a base, not through each other."""

    def test_neither_engine_is_a_subclass_of_the_other(self) -> None:
        """An ``isinstance(x, Engine)`` check must not admit an async engine, nor the reverse."""
        from semolina.engines.abase import AsyncEngine

        assert not issubclass(AsyncEngine, Engine)
        assert not issubclass(Engine, AsyncEngine)

    def test_both_keep_the_shared_state_on_one_base(self) -> None:
        """Both constructors store the same four attributes, so code can read either alike."""
        from semolina.engines.abase import AsyncEngine
        from semolina.engines.base import _EngineBase

        class MinimalEngine(Engine):
            def introspect(self, view_name: str) -> Any:
                return view_name

        dialect = DuckDBDialect()
        for engine in (
            MinimalEngine(pool="p", dialect=dialect, config="c"),
            AsyncEngine(pool="p", dialect=dialect, config="c"),
        ):
            assert isinstance(engine, _EngineBase)
            assert (engine._pool, engine.dialect, engine._config, engine._registered_as) == (
                "p",
                dialect,
                "c",
                None,
            )
