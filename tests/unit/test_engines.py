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
