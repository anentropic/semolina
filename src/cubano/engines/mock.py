"""
MockEngine for testing queries without a real warehouse connection.

MockEngine validates query structure and returns configurable fixture data,
enabling developers to test SQL generation and query logic locally without
connecting to Snowflake, Databricks, or other warehouses.
"""

from __future__ import annotations

from typing import Any

from .base import Engine
from .sql import MockDialect, SQLBuilder


class MockEngine(Engine):
    """
    Mock backend engine for testing queries without a real warehouse connection.

    MockEngine validates query structure and generates SQL for testing purposes.
    SQL generation uses MockDialect (Snowflake-compatible syntax) for consistency.
    For test data injection, use pytest fixtures rather than passing data to the
    constructor.

    Attributes:
        dialect: MockDialect instance for SQL generation

    Example:
        from cubano import Query, SemanticView, Metric, Dimension
        from cubano.engines import MockEngine

        # In conftest.py
        @pytest.fixture
        def sales_fixtures():
            return {
                'sales_view': [
                    {'revenue': 1000, 'country': 'US'},
                    {'revenue': 500, 'country': 'CA'},
                ]
            }

        @pytest.fixture
        def engine(sales_fixtures):
            return MockEngine()

        # In test file
        def test_query(engine):
            query = Query().metrics(Sales.revenue).dimensions(Sales.country)
            sql = engine.to_sql(query)
            # SELECT AGG("revenue"), "country"
            # FROM "sales_view"
            # GROUP BY ALL
    """

    def __init__(self) -> None:
        """
        Initialize MockEngine with MockDialect for SQL generation.

        For testing with data, use pytest fixtures to inject test data
        rather than passing it to the constructor.
        """
        self.dialect = MockDialect()

    def to_sql(self, query: Any) -> str:
        """
        Generate SQL for a query using MockDialect.

        Validates that the query has at least one metric or dimension,
        then uses SQLBuilder to generate SQL with Snowflake-compatible
        syntax (double quotes, AGG() wrapping).

        Args:
            query: Query object to convert to SQL

        Returns:
            SQL string formatted for MockEngine

        Raises:
            ValueError: If query is invalid (missing metrics and dimensions)

        Example:
            sql = engine.to_sql(query)
            # SELECT AGG("revenue"), "country"
            # FROM "sales_view"
            # GROUP BY ALL
        """
        query._validate_for_execution()
        builder = SQLBuilder(self.dialect)
        return builder.build_select(query)

    def execute(self, query: Any) -> list[dict[str, Any]]:
        """
        Execute a query and return results.

        MockEngine.execute() is not available in this phase. Real backend engines
        (SnowflakeEngine, DatabricksEngine) will implement filtering and aggregation
        in Phase 4-6. For testing query logic with mock data, use pytest fixtures
        to inject test data directly into your test assertions.

        Args:
            query: Query object to execute

        Raises:
            NotImplementedError: MockEngine.execute() not available, use pytest
                fixtures for test data injection

        Example:
            # Don't use execute() in tests. Instead:
            @pytest.fixture
            def expected_results():
                return [{'revenue': 1000, 'country': 'US'}]

            def test_query_logic(expected_results):
                # Test your logic with expected_results directly
                assert expected_results[0]['revenue'] == 1000
        """
        raise NotImplementedError(
            "MockEngine.execute() not available in gap closure phase. "
            "Use pytest fixtures for test data injection. "
            "Real execution will be available with SnowflakeEngine/DatabricksEngine in Phase 4+."
        )
