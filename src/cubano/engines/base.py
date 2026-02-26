"""
Abstract base class for backend engines.

Defines the interface for all SQL generation and query execution backends,
including Snowflake, Databricks, and MockEngine. Each backend provides
dialect-specific SQL generation and execution semantics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cubano.codegen.introspector import IntrospectedView
    from cubano.query import _Query


class CubanoViewNotFoundError(RuntimeError):
    """Raised when the requested semantic view does not exist in the warehouse."""


class CubanoConnectionError(RuntimeError):
    """Raised when the engine cannot connect to or authenticate with the warehouse."""


class Engine(ABC):
    """
    Abstract base class for query execution backends.

    Establishes the interface for backend-agnostic query building with
    dialect-specific SQL generation and execution. Subclasses implement
    concrete backends like Snowflake, Databricks, and MockEngine.

    Each Engine:
    - Generates SQL using dialect-specific quoting and metric wrapping
    - Executes queries and returns results in a consistent format
    - Handles validation and optimization specific to the backend

    Example:
        engine = MockEngine()
        sql = engine.to_sql(query)  # AGG() wrapping, double quotes
        results = engine.execute(query)  # Returns list of dicts

    See Also:
        - cubano.engines.sql.Dialect: Backend-specific SQL generation rules
        - cubano.engines.sql.SnowflakeDialect: Snowflake-specific dialect
        - cubano.engines.sql.DatabricksDialect: Databricks-specific dialect
        - cubano.engines.sql.MockDialect: Mock backend dialect
    """

    @abstractmethod
    def to_sql(self, query: _Query) -> str:
        """
        Generate SQL for a query using backend-specific dialect.

        Converts a _Query object to a SQL string using dialect-specific
        identifier quoting, metric wrapping (AGG vs MEASURE), and SQL
        keywords. SQL generation is dialect-specific; the same query
        produces different SQL depending on the backend.

        Args:
            query: _Query object to convert to SQL. Must be valid for
                execution (has metrics and/or dimensions).

        Returns:
            SQL string formatted for this backend. Identifiers are quoted
            using backend-specific quoting (double quotes for Snowflake/Mock,
            backticks for Databricks). Metrics are wrapped with AGG() or
            MEASURE() depending on dialect.

        Raises:
            ValueError: If query is invalid for execution (missing metrics
                and dimensions, circular dependencies, etc.)
            NotImplementedError: Raised by implementations for unsupported
                query features.

        Example:
            sql = engine.to_sql(query)
            # For Snowflake: SELECT "revenue", "country" FROM "sales" ...
            # For Databricks: SELECT `revenue`, `country` FROM `sales` ...
        """
        pass

    @abstractmethod
    def execute(self, query: _Query) -> list[Any]:
        """
        Execute a query and return results.

        Runs the query against the backend (real or mock) and returns a
        list of result rows. Actual execution depends on backend
        implementation; MockEngine returns fixtures, real backends execute
        against warehouse or database.

        Args:
            query: _Query object to execute. Must be valid for execution
                (has metrics and/or dimensions).

        Returns:
            List of Row objects representing query results. Each Row is a
            dict-like object with field names as keys and values as results.
            Empty list if query returns no results.

            Note: Row is a Phase 4 feature for standardized result object
            representation. Currently, subclasses may return dicts, Row-like
            objects, or other sequence types. See Phase 4 planning for the
            final Row class implementation that will provide consistent
            attribute and dict-style access across all backends.

        Raises:
            ValueError: If query is invalid for execution.
            RuntimeError: For backend-specific execution errors (connection
                failures, SQL errors, quota exceeded, etc.). Subclasses may
                raise backend-specific exceptions like SnowflakeError or
                DatabricksError.
            NotImplementedError: For unsupported query features in backend.

        Example:
            results = engine.execute(query)
            for row in results:
                print(row['country'], row['revenue'])
        """
        pass

    @abstractmethod
    def introspect(self, view_name: str) -> IntrospectedView:
        """
        Introspect a semantic view and return its intermediate representation.

        Queries the warehouse metadata API to discover the fields (metrics,
        dimensions, facts) defined on the named semantic view. The returned
        ``IntrospectedView`` is consumed by the Python code renderer to generate
        a SemanticView subclass.

        Args:
            view_name: Warehouse identifier for the semantic view to introspect
                (e.g., ``'sales_view'``). Must exist in the warehouse.

        Returns:
            ``IntrospectedView`` containing the view name, derived class name,
            and all discovered fields with their types and descriptions.

        Raises:
            NotImplementedError: If the engine does not support introspection.
            RuntimeError: For backend-specific errors (connection failures,
                view not found, insufficient permissions, etc.).

        Example:
            view = engine.introspect('sales_view')
            # IntrospectedView(view_name='sales_view', class_name='Sales', ...)
        """
        pass
