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
        self._fixtures: dict[str, list[dict[str, Any]]] = {}

    def load(self, view_name: str, data: list[dict[str, Any]]) -> None:
        """
        Load fixture data for a semantic view.

        Args:
            view_name: View name matching SemanticView's view parameter
            data: List of row dicts with field names as keys

        Example:
            engine = MockEngine()
            engine.load('sales_view', [
                {'revenue': 1000, 'country': 'US'},
                {'revenue': 500, 'country': 'CA'},
            ])
        """
        self._fixtures[view_name] = data

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
        Execute a query against loaded fixture data.

        Validates query, extracts view name from query fields, and returns
        fixture data for that view. Returns empty list if no fixtures loaded
        for the view.

        Args:
            query: Query object to execute

        Returns:
            List of row dicts from loaded fixtures

        Raises:
            ValueError: If query is invalid (missing metrics and dimensions)

        Example:
            engine = MockEngine()
            engine.load('sales_view', [{'revenue': 1000, 'country': 'US'}])
            results = engine.execute(query)
        """
        query._validate_for_execution()

        # Extract view name from query fields
        view_name: str | None = None
        if query._metrics:
            owner = query._metrics[0].owner
            if owner is not None:
                view_name = owner._view_name
        elif query._dimensions:
            owner = query._dimensions[0].owner
            if owner is not None:
                view_name = owner._view_name

        if view_name is None:
            return []

        return self._fixtures.get(view_name, [])
