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
    Mock backend engine for testing queries with fixture data.

    MockEngine validates query structure and returns configurable test data,
    enabling unit testing of query logic without a real warehouse connection.
    SQL generation uses MockDialect (Snowflake-compatible syntax) for
    consistency.

    Attributes:
        fixtures: Dict mapping view_name -> list of row dicts for test data
        dialect: MockDialect instance for SQL generation

    Example:
        from cubano import Query, SemanticView, Metric, Dimension
        from cubano.engines import MockEngine

        class Sales(SemanticView, view='sales_view'):
            revenue = Metric()
            country = Dimension()

        fixtures = {
            'sales_view': [
                {'revenue': 1000, 'country': 'US'},
                {'revenue': 500, 'country': 'CA'},
            ]
        }

        engine = MockEngine(fixtures=fixtures)
        query = Query().metrics(Sales.revenue).dimensions(Sales.country)

        # Generate SQL
        sql = engine.to_sql(query)
        # SELECT AGG("revenue"), "country"
        # FROM "sales_view"
        # GROUP BY ALL

        # Execute query
        results = engine.execute(query)
        # Returns: [{'revenue': 1000, 'country': 'US'}, ...]
    """

    def __init__(self, fixtures: dict[str, list[dict[str, Any]]] | None = None) -> None:
        """
        Initialize MockEngine with optional fixture data.

        Args:
            fixtures: Optional dict mapping view_name (str) to list of row
                dicts. Each row dict maps field names to values.
                Example: {'sales_view': [{'revenue': 1000, 'country': 'US'}]}
                If None, defaults to empty dict (no fixtures).
        """
        self.fixtures = fixtures or {}
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
        Execute a query and return fixture data.

        Validates the query, extracts the view name from the first field's
        owner model, and returns the corresponding fixture data. If the
        view has no fixtures, returns an empty list.

        Phase 3 behavior: Returns raw fixture data without filtering or
        aggregation. Full filtering/aggregation logic happens in Phase 4-6
        with real backend execution.

        Args:
            query: Query object to execute

        Returns:
            List of row dicts from fixtures (or empty list if view not found)

        Raises:
            ValueError: If query is invalid (missing metrics and dimensions)

        Example:
            results = engine.execute(query)
            # Returns: [{'revenue': 1000, 'country': 'US'}, ...]
        """
        # Validate query
        query._validate_for_execution()

        # Extract view name from first metric or dimension's owner
        view_name: str | None = None

        if query._metrics:
            view_name = query._metrics[0].owner._view_name
        elif query._dimensions:
            view_name = query._dimensions[0].owner._view_name

        # Return fixture data for this view (or empty list if not found)
        if view_name and view_name in self.fixtures:
            return self.fixtures[view_name]
        else:
            return []
