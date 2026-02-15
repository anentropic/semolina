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

from cubano import Dimension, Metric, SemanticView
from cubano.engines.base import Engine
from cubano.engines.mock import MockEngine
from cubano.query import Query

# Type alias for fixtures used in tests
FixturesDict = dict[str, list[dict[str, Any]]]


class Sales(SemanticView, view="sales_view"):
    """Test model for engine tests."""

    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()


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
        """Should initialize with empty fixtures dict by default."""
        engine = MockEngine()
        assert engine.fixtures == {}

    def test_mock_engine_with_fixtures(self):
        """Should initialize with provided fixtures."""
        fixtures = {"sales_view": [{"revenue": 1000, "country": "US"}]}
        engine = MockEngine(fixtures=fixtures)
        assert engine.fixtures == fixtures

    def test_mock_engine_has_dialect(self):
        """Should have MockDialect instance."""
        engine = MockEngine()
        assert engine.dialect is not None
        from cubano.engines.sql import MockDialect

        assert isinstance(engine.dialect, MockDialect)

    def test_mock_engine_multiple_fixtures(self):
        """Should support multiple views in fixtures."""
        fixtures = {
            "sales_view": [{"revenue": 1000}],
            "products_view": [{"name": "Widget"}],
        }
        engine = MockEngine(fixtures=fixtures)
        assert len(engine.fixtures) == 2
        assert "sales_view" in engine.fixtures
        assert "products_view" in engine.fixtures


class TestMockEngineToSQL:
    """Test MockEngine.to_sql() method."""

    def test_to_sql_validates_empty_query(self):
        """Should raise ValueError for empty query."""
        engine = MockEngine()
        query = Query()
        with pytest.raises(ValueError):
            engine.to_sql(query)

    def test_to_sql_returns_sql_string(self):
        """Should return SQL string for valid query."""
        engine = MockEngine()
        query = Query().metrics(Sales.revenue)
        sql = engine.to_sql(query)
        assert isinstance(sql, str)
        assert "SELECT" in sql

    def test_to_sql_includes_agg_wrapping(self):
        """Should include AGG() wrapping for metrics."""
        engine = MockEngine()
        query = Query().metrics(Sales.revenue)
        sql = engine.to_sql(query)
        assert 'AGG("revenue")' in sql

    def test_to_sql_includes_group_by_all(self):
        """Should include GROUP BY ALL for queries with dimensions."""
        engine = MockEngine()
        query = Query().metrics(Sales.revenue).dimensions(Sales.country)
        sql = engine.to_sql(query)
        assert "GROUP BY ALL" in sql

    def test_to_sql_includes_limit(self):
        """Should include LIMIT clause when set."""
        engine = MockEngine()
        query = Query().metrics(Sales.revenue).limit(100)
        sql = engine.to_sql(query)
        assert "LIMIT 100" in sql

    def test_to_sql_includes_order_by(self):
        """Should include ORDER BY clause when set."""
        engine = MockEngine()
        query = Query().metrics(Sales.revenue).order_by(Sales.revenue.desc())
        sql = engine.to_sql(query)
        assert 'ORDER BY "revenue" DESC' in sql

    def test_to_sql_with_dimensions_only(self):
        """Should work with dimensions only (no metrics)."""
        engine = MockEngine()
        query = Query().dimensions(Sales.country)
        sql = engine.to_sql(query)
        assert 'SELECT "country"' in sql

    def test_to_sql_uses_mock_dialect_syntax(self):
        """Should use MockDialect syntax (Snowflake-like)."""
        engine = MockEngine()
        query = Query().metrics(Sales.revenue, Sales.cost)
        sql = engine.to_sql(query)
        # Double quotes (Snowflake-like), not backticks
        assert '"revenue"' in sql
        assert '"cost"' in sql
        assert "`revenue`" not in sql


class TestMockEngineExecute:
    """Test MockEngine.execute() method."""

    @pytest.fixture
    def sales_fixtures(self) -> FixturesDict:
        """Fixture data for sales_view."""
        return {
            "sales_view": [
                {"revenue": 1000, "cost": 100, "country": "US", "region": "West"},
                {"revenue": 2000, "cost": 200, "country": "CA", "region": "West"},
                {"revenue": 500, "cost": 50, "country": "US", "region": "East"},
            ]
        }

    def test_execute_validates_empty_query(self, sales_fixtures: FixturesDict) -> None:
        """Should raise ValueError for empty query."""
        engine = MockEngine(fixtures=sales_fixtures)
        query = Query()
        with pytest.raises(ValueError):
            engine.execute(query)

    def test_execute_returns_list(self, sales_fixtures: FixturesDict) -> None:
        """Should return list of result dicts."""
        engine = MockEngine(fixtures=sales_fixtures)
        query = Query().metrics(Sales.revenue)
        results = engine.execute(query)
        assert isinstance(results, list)

    def test_execute_returns_fixture_data(self, sales_fixtures: FixturesDict) -> None:
        """Should return fixture data for queried view."""
        engine = MockEngine(fixtures=sales_fixtures)
        query = Query().metrics(Sales.revenue)
        results = engine.execute(query)
        assert len(results) == 3
        assert results[0]["country"] == "US"
        assert results[1]["country"] == "CA"

    def test_execute_returns_all_rows(self, sales_fixtures: FixturesDict) -> None:
        """Should return all fixture rows (no filtering in Phase 3)."""
        engine = MockEngine(fixtures=sales_fixtures)
        query = Query().metrics(Sales.revenue).dimensions(Sales.country)
        results = engine.execute(query)
        # Phase 3: Returns raw fixture data, no aggregation
        assert len(results) == 3

    def test_execute_returns_empty_for_unknown_view(self):
        """Should return empty list for unknown view."""
        engine = MockEngine()
        query = Query().metrics(Sales.revenue)
        results = engine.execute(query)
        assert results == []

    def test_execute_with_dimensions_only(self, sales_fixtures: FixturesDict) -> None:
        """Should work with dimensions only (no metrics)."""
        engine = MockEngine(fixtures=sales_fixtures)
        query = Query().dimensions(Sales.country)
        results = engine.execute(query)
        assert len(results) == 3

    def test_execute_result_structure(self, sales_fixtures: FixturesDict) -> None:
        """Should return results with correct structure."""
        engine = MockEngine(fixtures=sales_fixtures)
        query = Query().metrics(Sales.revenue, Sales.cost)
        results = engine.execute(query)

        # Check structure
        assert len(results) > 0
        for row in results:
            assert isinstance(row, dict)
            assert "revenue" in row
            assert "cost" in row
            assert isinstance(row["revenue"], int)
            assert isinstance(row["cost"], int)

    def test_execute_with_order_by(self, sales_fixtures: FixturesDict) -> None:
        """Should execute query with ORDER BY (returns fixtures)."""
        engine = MockEngine(fixtures=sales_fixtures)
        query = Query().metrics(Sales.revenue).order_by(Sales.revenue.desc())
        results = engine.execute(query)
        # Still returns all fixture data (no actual sorting in Phase 3)
        assert len(results) == 3

    def test_execute_with_limit(self, sales_fixtures: FixturesDict) -> None:
        """Should execute query with LIMIT (returns fixtures)."""
        engine = MockEngine(fixtures=sales_fixtures)
        query = Query().metrics(Sales.revenue).limit(2)
        results = engine.execute(query)
        # Phase 3: Returns all fixtures regardless of limit
        assert len(results) == 3


class TestMockEngineIntegration:
    """Test full MockEngine workflow."""

    @pytest.fixture
    def sales_fixtures(self) -> FixturesDict:
        """Fixture data for integration tests."""
        return {
            "sales_view": [
                {"revenue": 1000, "cost": 100, "country": "US", "region": "West"},
                {"revenue": 2000, "cost": 200, "country": "CA", "region": "West"},
                {"revenue": 500, "cost": 50, "country": "US", "region": "East"},
            ]
        }

    def test_full_workflow_to_sql_and_execute(self, sales_fixtures: FixturesDict) -> None:
        """Should generate SQL and execute query in sequence."""
        engine = MockEngine(fixtures=sales_fixtures)
        query = Query().metrics(Sales.revenue).dimensions(Sales.country).limit(50)

        # Generate SQL
        sql = engine.to_sql(query)
        assert isinstance(sql, str)
        assert "SELECT" in sql

        # Execute query
        results = engine.execute(query)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_multiple_metrics_and_dimensions(self, sales_fixtures: FixturesDict) -> None:
        """Should handle complex queries."""
        engine = MockEngine(fixtures=sales_fixtures)
        query = (
            Query()
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

        # Execute query
        results = engine.execute(query)
        assert len(results) == 3
        for row in results:
            assert "revenue" in row
            assert "cost" in row
            assert "country" in row
            assert "region" in row

    def test_validation_happens_before_execution(self, sales_fixtures: FixturesDict) -> None:
        """Should validate query before any execution attempt."""
        engine = MockEngine(fixtures=sales_fixtures)
        query = Query()

        # Should raise during validation, not during fixture lookup
        with pytest.raises(ValueError):
            engine.to_sql(query)

        with pytest.raises(ValueError):
            engine.execute(query)

    def test_invalid_query_never_accesses_fixtures(self):
        """Should validate empty query without accessing fixtures."""
        # Empty fixtures
        engine = MockEngine(fixtures={})
        query = Query()

        # Should raise ValueError before trying to access fixtures
        with pytest.raises(ValueError):
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
        fixtures = {"sales_view": [{"revenue": 1000}]}
        engine = MockEngine(fixtures=fixtures)

        # Immediate success - no connection attempted
        assert engine.fixtures == fixtures

    def test_mock_engine_to_sql_no_warehouse_needed(self):
        """to_sql() works without warehouse."""
        engine = MockEngine()
        query = Query().metrics(Sales.revenue)
        sql = engine.to_sql(query)
        assert isinstance(sql, str)

    def test_mock_engine_execute_with_local_data_only(self):
        """execute() uses only provided fixtures, no warehouse query."""
        fixtures = {"sales_view": [{"revenue": 1000, "country": "US"}]}
        engine = MockEngine(fixtures=fixtures)
        query = Query().metrics(Sales.revenue)
        results = engine.execute(query)
        # Returns local fixture data
        assert results == fixtures["sales_view"]


class TestENG02_MockEngineValidation:
    """Test ENG-02: MockEngine validates query structure before execution."""

    def test_empty_query_fails_validation(self):
        """Query with no metrics or dimensions should fail validation."""
        engine = MockEngine()
        query = Query()
        with pytest.raises(ValueError) as exc_info:
            engine.to_sql(query)
        assert "metric or dimension" in str(exc_info.value)

    def test_validation_on_execute(self):
        """execute() should validate before attempting to return fixtures."""
        engine = MockEngine(fixtures={"sales_view": [{"revenue": 1000}]})
        query = Query()
        with pytest.raises(ValueError):
            engine.execute(query)

    def test_valid_query_with_metrics_passes(self):
        """Query with metrics should pass validation."""
        engine = MockEngine()
        query = Query().metrics(Sales.revenue)
        # Should not raise
        sql = engine.to_sql(query)
        assert sql is not None

    def test_valid_query_with_dimensions_passes(self):
        """Query with dimensions should pass validation."""
        engine = MockEngine()
        query = Query().dimensions(Sales.country)
        # Should not raise
        sql = engine.to_sql(query)
        assert sql is not None

    def test_validation_message_helpful(self):
        """Validation error message should be helpful."""
        engine = MockEngine()
        query = Query()
        with pytest.raises(ValueError) as exc_info:
            engine.to_sql(query)
        error_msg = str(exc_info.value)
        # Should mention what's needed
        assert "metric" in error_msg or "dimension" in error_msg

    def test_validation_runs_before_sql_generation(self):
        """Validation should prevent SQL generation for invalid queries."""
        engine = MockEngine()
        query = Query()

        # Query is invalid, so to_sql should fail at validation
        with pytest.raises(ValueError):
            engine.to_sql(query)


class TestMockEngineFixtureFormats:
    """Test MockEngine handles various fixture formats."""

    def test_fixtures_with_multiple_data_types(self):
        """Should handle fixtures with various data types."""
        fixtures = {
            "sales_view": [
                {
                    "revenue": 1000,
                    "cost": 100.5,
                    "country": "US",
                    "active": True,
                    "notes": None,
                }
            ]
        }
        engine = MockEngine(fixtures=fixtures)
        query = Query().metrics(Sales.revenue)
        results = engine.execute(query)

        assert len(results) == 1
        assert results[0]["revenue"] == 1000
        assert results[0]["cost"] == 100.5
        assert results[0]["country"] == "US"
        assert results[0]["active"] is True
        assert results[0]["notes"] is None

    def test_fixtures_with_empty_view(self) -> None:
        """Should handle empty fixture lists."""
        fixtures: FixturesDict = {"sales_view": []}
        engine = MockEngine(fixtures=fixtures)
        query = Query().metrics(Sales.revenue)
        results = engine.execute(query)
        assert results == []

    def test_fixtures_with_many_rows(self) -> None:
        """Should handle large fixture datasets."""
        fixtures: FixturesDict = {
            "sales_view": [{"revenue": i * 100, "country": f"COUNTRY_{i}"} for i in range(1000)]
        }
        engine = MockEngine(fixtures=fixtures)
        query = Query().metrics(Sales.revenue)
        results = engine.execute(query)
        assert len(results) == 1000
