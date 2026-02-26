"""
Tests for Engine ABC and MockEngine implementation.

Tests cover:
- ENG-01: MockEngine works without warehouse credentials
- ENG-02: MockEngine validates query structure before execution
- Engine ABC abstract interface
- MockEngine SQL generation
- MockEngine query execution with fixtures
"""

from typing import Any

import pytest
from models import Sales

from cubano.engines.base import Engine
from cubano.engines.mock import MockEngine
from cubano.query import _Query

# Type alias for fixtures used in tests
FixturesDict = dict[str, list[dict[str, Any]]]


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

        with pytest.raises(TypeError):
            IncompleteEngine()  # type: ignore[abstract]

    def test_engine_execute_is_abstract(self):
        """Engine.execute() is abstract and must be implemented."""

        class IncompleteEngine(Engine):
            def to_sql(self, query):  # type: ignore[no-untyped-def]
                pass

        with pytest.raises(TypeError):
            IncompleteEngine()  # type: ignore[abstract]


class TestMockEngineInit:
    """Test MockEngine initialization."""

    def test_mock_engine_with_no_fixtures(self):
        """Should initialize without parameters (no fixtures in constructor)."""
        engine = MockEngine()
        assert engine is not None

    def test_mock_engine_has_dialect(self):
        """Should have MockDialect instance."""
        engine = MockEngine()
        assert engine.dialect is not None
        from cubano.engines.sql import MockDialect

        assert isinstance(engine.dialect, MockDialect)


class TestMockEngineToSQL:
    """Test MockEngine.to_sql() method."""

    def test_to_sql_validates_empty_query(self):
        """Should raise ValueError for empty query."""
        engine = MockEngine()
        query = _Query()
        with pytest.raises(ValueError):
            engine.to_sql(query)

    def test_to_sql_returns_sql_string(self):
        """Should return SQL string for valid query."""
        engine = MockEngine()
        query = _Query().metrics(Sales.revenue)
        sql = engine.to_sql(query)
        assert isinstance(sql, str)
        assert "SELECT" in sql

    def test_to_sql_includes_agg_wrapping(self):
        """Should include AGG() wrapping for metrics."""
        engine = MockEngine()
        query = _Query().metrics(Sales.revenue)
        sql = engine.to_sql(query)
        assert 'AGG("revenue")' in sql

    def test_to_sql_includes_group_by_all(self):
        """Should include GROUP BY ALL for queries with dimensions."""
        engine = MockEngine()
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        sql = engine.to_sql(query)
        assert "GROUP BY ALL" in sql

    def test_to_sql_includes_limit(self):
        """Should include LIMIT clause when set."""
        engine = MockEngine()
        query = _Query().metrics(Sales.revenue).limit(100)
        sql = engine.to_sql(query)
        assert "LIMIT 100" in sql

    def test_to_sql_includes_order_by(self):
        """Should include ORDER BY clause when set."""
        engine = MockEngine()
        query = _Query().metrics(Sales.revenue).order_by(Sales.revenue.desc())
        sql = engine.to_sql(query)
        assert 'ORDER BY AGG("revenue") DESC' in sql

    def test_to_sql_with_dimensions_only(self):
        """Should work with dimensions only (no metrics)."""
        engine = MockEngine()
        query = _Query().dimensions(Sales.country)
        sql = engine.to_sql(query)
        assert 'SELECT "country"' in sql

    def test_to_sql_uses_mock_dialect_syntax(self):
        """Should use MockDialect syntax (Snowflake-like)."""
        engine = MockEngine()
        query = _Query().metrics(Sales.revenue, Sales.cost)
        sql = engine.to_sql(query)
        # Double quotes (Snowflake-like), not backticks
        assert '"revenue"' in sql
        assert '"cost"' in sql
        assert "`revenue`" not in sql


class TestMockEngineExecute:
    """Test MockEngine.execute() method."""

    def test_execute_empty_fixtures_returns_empty_list(self) -> None:
        """Should return empty list when no fixtures loaded."""
        engine = MockEngine()
        query = _Query().metrics(Sales.revenue)
        results = engine.execute(query)
        assert results == []

    def test_execute_returns_loaded_fixtures(self) -> None:
        """Should return fixture data from load()."""
        engine = MockEngine()
        fixture_data = [{"revenue": 1000, "country": "US"}]
        engine.load("sales_view", fixture_data)
        query = _Query().metrics(Sales.revenue)
        results = engine.execute(query)
        assert results == fixture_data

    def test_execute_validates_query(self) -> None:
        """Should validate query before execution."""
        engine = MockEngine()
        query = _Query()  # Empty query - no metrics or dimensions
        with pytest.raises(ValueError, match="must select at least one metric or dimension"):
            engine.execute(query)


class TestMockEngineIntegration:
    """Test full MockEngine workflow."""

    def test_to_sql_generation(self) -> None:
        """Should generate SQL for queries."""
        engine = MockEngine()
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country).limit(50)

        # Generate SQL
        sql = engine.to_sql(query)
        assert isinstance(sql, str)
        assert "SELECT" in sql

    def test_multiple_metrics_and_dimensions(self) -> None:
        """Should handle complex queries."""
        engine = MockEngine()
        query = (
            _Query()
            .metrics(Sales.revenue, Sales.cost)
            .dimensions(Sales.country, Sales.region)
            .order_by(Sales.revenue.desc())
            .limit(100)
        )

        # Generate SQL
        sql = engine.to_sql(query)
        assert 'AGG("revenue")' in sql
        assert 'AGG("cost")' in sql
        assert '"country"' in sql
        assert '"region"' in sql

    def test_validation_happens_before_sql_generation(self) -> None:
        """Should validate query before SQL generation and execution."""
        engine = MockEngine()
        query = _Query()

        # Should raise during validation for to_sql
        with pytest.raises(ValueError, match="must select at least one metric or dimension"):
            engine.to_sql(query)

        # Should raise during validation for execute
        with pytest.raises(ValueError, match="must select at least one metric or dimension"):
            engine.execute(query)


class TestENG01_MockEngineWithoutWarehouse:
    """Test ENG-01: MockEngine works without warehouse credentials."""

    def test_mock_engine_no_credentials_needed(self):
        """Should initialize and work with no credentials."""
        # No environment variables, no connection strings, no auth tokens
        engine = MockEngine()
        assert engine is not None
        assert isinstance(engine, Engine)

    def test_mock_engine_no_connection_attempts(self):
        """Should not attempt any network connection."""
        # If initialization tried to connect, this would hang or fail
        engine = MockEngine()

        # Immediate success - no connection attempted
        assert engine is not None

    def test_mock_engine_to_sql_no_warehouse_needed(self):
        """to_sql() works without warehouse."""
        engine = MockEngine()
        query = _Query().metrics(Sales.revenue)
        sql = engine.to_sql(query)
        assert isinstance(sql, str)


class TestENG02_MockEngineValidation:
    """Test ENG-02: MockEngine validates query structure before execution."""

    def test_empty_query_fails_validation(self):
        """Query with no metrics or dimensions should fail validation."""
        engine = MockEngine()
        query = _Query()
        with pytest.raises(ValueError) as exc_info:
            engine.to_sql(query)
        assert "metric or dimension" in str(exc_info.value)

    def test_valid_query_with_metrics_passes(self):
        """Query with metrics should pass validation."""
        engine = MockEngine()
        query = _Query().metrics(Sales.revenue)
        # Should not raise
        sql = engine.to_sql(query)
        assert sql is not None

    def test_valid_query_with_dimensions_passes(self):
        """Query with dimensions should pass validation."""
        engine = MockEngine()
        query = _Query().dimensions(Sales.country)
        # Should not raise
        sql = engine.to_sql(query)
        assert sql is not None

    def test_validation_message_helpful(self):
        """Validation error message should be helpful."""
        engine = MockEngine()
        query = _Query()
        with pytest.raises(ValueError) as exc_info:
            engine.to_sql(query)
        error_msg = str(exc_info.value)
        # Should mention what's needed
        assert "metric" in error_msg or "dimension" in error_msg

    def test_validation_runs_before_sql_generation(self):
        """Validation should prevent SQL generation for invalid queries."""
        engine = MockEngine()
        query = _Query()

        # Query is invalid, so to_sql should fail at validation
        with pytest.raises(ValueError):
            engine.to_sql(query)


class TestMockEngineSQL:
    """Test MockEngine SQL generation capabilities."""

    def test_to_sql_with_complex_query(self) -> None:
        """Should generate SQL for complex queries."""
        engine = MockEngine()
        query = (
            _Query()
            .metrics(Sales.revenue, Sales.cost)
            .dimensions(Sales.country, Sales.region)
            .order_by(Sales.revenue.desc())
            .limit(100)
        )
        sql = engine.to_sql(query)

        assert 'AGG("revenue")' in sql
        assert 'AGG("cost")' in sql
        assert '"country"' in sql
        assert '"region"' in sql
        assert "GROUP BY ALL" in sql
        assert 'ORDER BY AGG("revenue") DESC' in sql
        assert "LIMIT 100" in sql

    def test_to_sql_with_simple_query(self) -> None:
        """Should generate SQL for simple queries."""
        engine = MockEngine()
        query = _Query().metrics(Sales.revenue)
        sql = engine.to_sql(query)

        assert 'SELECT AGG("revenue")' in sql
        assert 'FROM "sales_view"' in sql
        assert "GROUP BY" not in sql  # No dimensions, no GROUP BY


class TestMockEngineFiltering:
    """
    Test MockEngine.execute() in-memory predicate evaluation.

    Verifies that WHERE predicates applied via .where() are correctly
    evaluated against fixture rows, returning only matching rows.
    """

    _fixture_data: list[dict[str, object]] = [
        {"revenue": 100, "cost": 40, "country": "US", "region": "East"},
        {"revenue": 800, "cost": 200, "country": "US", "region": "West"},
        {"revenue": 300, "cost": 90, "country": "CA", "region": "North"},
    ]

    def _engine_with_fixtures(self) -> MockEngine:
        engine = MockEngine()
        engine.load("sales_view", self._fixture_data)
        return engine

    def test_filter_exact_reduces_results(self) -> None:
        """Exact filter on country='US' should return 2 rows, not 3."""
        engine = self._engine_with_fixtures()
        query = _Query().dimensions(Sales.country).where(Sales.country == "US")
        results = engine.execute(query)

        assert len(results) == 2
        assert all(r["country"] == "US" for r in results)

    def test_filter_exact_all_rows_match(self) -> None:
        """Exact filter matching all rows returns all fixture rows."""
        # Use a fixture where all rows share the same country value
        all_us_engine = MockEngine()
        all_us_data: list[dict[str, object]] = [
            {"revenue": 100, "country": "US"},
            {"revenue": 200, "country": "US"},
        ]
        all_us_engine.load("sales_view", all_us_data)
        query = _Query().dimensions(Sales.country).where(Sales.country == "US")
        results = all_us_engine.execute(query)

        assert len(results) == 2
        assert all(r["country"] == "US" for r in results)

    def test_filter_comparison_gt(self) -> None:
        """Gt filter on revenue > 500 should return only 1 row (revenue=800)."""
        engine = self._engine_with_fixtures()
        query = _Query().metrics(Sales.revenue).where(Sales.revenue > 500)
        results = engine.execute(query)

        assert len(results) == 1
        assert all(r["revenue"] > 500 for r in results)

    def test_filter_no_match_returns_empty(self) -> None:
        """Filter matching no rows returns empty list."""
        engine = self._engine_with_fixtures()
        query = _Query().dimensions(Sales.country).where(Sales.country == "MX")
        results = engine.execute(query)

        assert len(results) == 0

    def test_filter_and_composition(self) -> None:
        """AND filter: revenue > 500 AND country == 'US' returns 1 row."""
        engine = self._engine_with_fixtures()
        query = (
            _Query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .where((Sales.revenue > 500) & (Sales.country == "US"))
        )
        results = engine.execute(query)

        assert len(results) == 1
        assert results[0]["revenue"] == 800
        assert results[0]["country"] == "US"

    def test_filter_none_returns_all_rows(self) -> None:
        """Query with no .where() returns all fixture rows unchanged."""
        engine = self._engine_with_fixtures()
        query = _Query().metrics(Sales.revenue)
        results = engine.execute(query)

        assert len(results) == 3
