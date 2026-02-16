"""
Databricks backend engine for query execution.

Provides DatabricksEngine class for executing queries against Databricks semantic
views using the databricks-sql-connector driver. Supports lazy driver import,
context-managed connection lifecycle, and comprehensive error handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cubano.engines.base import Engine
from cubano.engines.sql import DatabricksDialect, SQLBuilder

if TYPE_CHECKING:
    from cubano.query import Query


class DatabricksEngine(Engine):
    """
    Databricks backend engine for semantic view queries.

    Executes queries against Databricks semantic views using MEASURE() syntax for
    metrics and proper connection lifecycle management via context managers.
    The databricks-sql-connector driver is lazily imported only when the
    engine is instantiated, preventing ImportError for users without Databricks
    credentials installed.

    Connection Lifecycle:
        - Connection parameters are stored at initialization but not connected
        - Connections are created per execute() call using context managers
        - Automatic cleanup guaranteed by with statement even on exceptions
        - No connection pooling (connections handled by Databricks internally)

    Error Handling:
        - DatabaseError (SQL syntax, invalid objects) translated to RuntimeError
        - OperationalError (connection, permissions) translated to RuntimeError
        - Error messages include original exception details

    SQL Generation:
        - Delegates to SQLBuilder with DatabricksDialect (from Phase 3)
        - Generates MEASURE() wrapping for metrics
        - Uses backtick-quoted identifiers for case preservation
        - GROUP BY ALL for automatic dimension derivation

    Unity Catalog:
        - Three-part names (catalog.schema.view) work transparently
        - Each part quoted separately with backticks
        - Enabled through connection parameters

    Example:
        from cubano.engines import DatabricksEngine
        from cubano import Query, SemanticView, Metric, Dimension

        class Sales(SemanticView, view='main.analytics.sales_view'):
            revenue = Metric()
            country = Dimension()

        # Connection parameters (from environment or config)
        connection_params = {
            "server_hostname": "workspace.cloud.databricks.com",
            "http_path": "/sql/1.0/warehouses/warehouse_id",
            "access_token": "dapi...",
        }

        engine = DatabricksEngine(**connection_params)
        query = Query().metrics(Sales.revenue).dimensions(Sales.country)
        results = engine.execute(query)
        # Returns: [{"revenue": 1000, "country": "US"}, ...]

    See Also:
        - cubano.engines.sql.DatabricksDialect: SQL generation rules
        - cubano.engines.sql.SQLBuilder: Query to SQL converter
        - databricks.sql: Databricks SQL connector documentation
    """

    def __init__(self, **connection_params: Any) -> None:
        """
        Initialize DatabricksEngine with connection parameters.

        Connection is NOT established at initialization time. Parameters are
        stored and used to create connections during execute() calls. This
        defers expensive connection setup and allows the engine to be
        instantiated without network access.

        Args:
            **connection_params: Databricks connection parameters passed to
                databricks.sql.connect(). Common parameters:
                - server_hostname (str): Databricks workspace hostname
                  (e.g., "workspace.cloud.databricks.com")
                - http_path (str): SQL warehouse path
                  (e.g., "/sql/1.0/warehouses/{warehouse_id}")
                - access_token (str): Personal access token for authentication
                - catalog (str, optional): Default catalog for Unity Catalog
                - schema (str, optional): Default schema

        Raises:
            ImportError: If databricks-sql-connector is not installed.
                Install with: pip install cubano[databricks]

        Example:
            engine = DatabricksEngine(
                server_hostname="workspace.cloud.databricks.com",
                http_path="/sql/1.0/warehouses/abc123",
                access_token="dapi...",
            )
        """
        # Lazy import: only load databricks.sql when DatabricksEngine instantiated
        try:
            import databricks.sql as _  # noqa: F401
        except ImportError as e:
            msg = (
                "databricks-sql-connector is required for DatabricksEngine. "
                "Install with: pip install cubano[databricks]"
            )
            raise ImportError(msg) from e

        self._connection_params = connection_params
        self.dialect = DatabricksDialect()

    def to_sql(self, query: Query) -> str:
        """
        Generate Databricks SQL for a query.

        Delegates to SQLBuilder with DatabricksDialect to produce SQL with
        MEASURE() wrapping for metrics, backtick-quoted identifiers, and
        GROUP BY ALL. This reuses the SQL generation implementation from Phase 3.

        Args:
            query: Query object to convert to SQL. Must be valid for execution
                (has metrics and/or dimensions).

        Returns:
            SQL string formatted for Databricks. Example:
                SELECT MEASURE(`revenue`), `country`
                FROM `sales_view`
                GROUP BY ALL

        Raises:
            ValueError: If query is invalid for execution (missing metrics
                and dimensions, circular dependencies, etc.)

        Example:
            sql = engine.to_sql(query)
            print(sql)
            # SELECT MEASURE(`revenue`), `country`
            # FROM `sales_view`
            # GROUP BY ALL
        """
        builder = SQLBuilder(self.dialect)
        return builder.build_select(query)

    def execute(self, query: Query) -> list[dict[str, Any]]:
        """
        Execute a query against Databricks and return results.

        Creates a new connection using stored connection parameters, executes
        the query using generated SQL, and returns results as a list of dicts.
        Connection is automatically closed via context manager even on exception.

        Args:
            query: Query object to execute. Must be valid for execution
                (has metrics and/or dimensions).

        Returns:
            List of result rows as dicts. Each dict has field names as keys
            (from cursor.description) and query results as values. Empty list
            if query returns no results.

        Example:
            [
                {"revenue": 1000, "country": "US"},
                {"revenue": 500, "country": "UK"},
            ]

        Raises:
            RuntimeError: For Databricks execution errors. Includes original
                error message for debugging. Common causes:
                - Invalid SQL syntax (DatabaseError)
                - Object does not exist (DatabaseError)
                - Connection failure (OperationalError)
                - Authentication failure (OperationalError)
                - Permission denied (OperationalError)
            ValueError: If query is invalid for execution.

        Example:
            results = engine.execute(query)
            for row in results:
                print(row["country"], row["revenue"])
        """
        import databricks.sql  # type: ignore[reportUnusedImport]
        from databricks.sql.exc import DatabaseError, Error, OperationalError

        try:
            # Generate SQL using dialect-specific builder
            sql = self.to_sql(query)

            # Execute using context managers for guaranteed cleanup
            with (
                databricks.sql.connect(**self._connection_params) as conn,  # type: ignore[reportUnknownMemberType]
                conn.cursor() as cur,  # type: ignore[reportUnknownMemberType]
            ):
                cur.execute(sql)  # type: ignore[reportUnknownMemberType]

                # Extract column names from cursor metadata
                description: Any = cur.description  # type: ignore[reportUnknownMemberType]
                columns: list[str] = [desc[0] for desc in description]

                # Fetch all rows and convert tuples to dicts
                rows: Any = cur.fetchall()  # type: ignore[reportUnknownMemberType]
                return [dict(zip(columns, row, strict=True)) for row in rows]

        except OperationalError as e:
            # Connection failures, authentication, permissions
            # (must be caught before DatabaseError since it may be a subclass)
            msg = f"Databricks operational error: {e}"
            raise RuntimeError(msg) from e

        except DatabaseError as e:
            # SQL syntax errors, invalid objects, semantic view issues
            msg = f"Databricks query failed: {e}"
            raise RuntimeError(msg) from e

        except Error as e:
            # Generic fallback for other Databricks errors
            msg = f"Databricks error: {e}"
            raise RuntimeError(msg) from e
