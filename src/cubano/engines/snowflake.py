"""
Snowflake backend engine for query execution.

Provides SnowflakeEngine class for executing queries against Snowflake semantic
views using the snowflake-connector-python driver. Supports lazy driver import,
context-managed connection lifecycle, and comprehensive error handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cubano.engines.base import Engine
from cubano.engines.sql import SnowflakeDialect, SQLBuilder

if TYPE_CHECKING:
    from cubano.query import Query


class SnowflakeEngine(Engine):
    """
    Snowflake backend engine for semantic view queries.

    Executes queries against Snowflake semantic views using AGG() syntax for
    metrics and proper connection lifecycle management via context managers.
    The snowflake-connector-python driver is lazily imported only when the
    engine is instantiated, preventing ImportError for users without Snowflake
    credentials installed.

    Connection Lifecycle:
        - Connection parameters are stored at initialization but not connected
        - Connections are created per execute() call using context managers
        - Automatic cleanup guaranteed by with statement even on exceptions
        - No connection pooling (connections handled by Snowflake internally)

    Error Handling:
        - ProgrammingError (SQL syntax, invalid objects) translated to RuntimeError
        - DatabaseError (connection, permissions) translated to RuntimeError
        - Error messages include Snowflake error code, SQL state, and message

    SQL Generation:
        - Delegates to SQLBuilder with SnowflakeDialect (from Phase 3)
        - Generates AGG() wrapping for metrics
        - Uses double-quoted identifiers for case preservation
        - GROUP BY ALL for automatic dimension derivation

    Example:
        from cubano.engines import SnowflakeEngine
        from cubano import Query, SemanticView, Metric, Dimension

        class Sales(SemanticView, view='sales_view'):
            revenue = Metric()
            country = Dimension()

        # Connection parameters (from environment or config)
        connection_params = {
            "account": "xy12345.us-east-1",  # Include region suffix
            "user": "username",
            "password": "password",
            "warehouse": "compute_wh",  # Optional
            "database": "analytics",    # Optional
            "schema": "public",         # Optional
        }

        engine = SnowflakeEngine(**connection_params)
        query = Query().metrics(Sales.revenue).dimensions(Sales.country)
        results = engine.execute(query)
        # Returns: [{"revenue": 1000, "country": "US"}, ...]

    See Also:
        - cubano.engines.sql.SnowflakeDialect: SQL generation rules
        - cubano.engines.sql.SQLBuilder: Query to SQL converter
        - snowflake.connector: Snowflake Python driver documentation
    """

    def __init__(self, **connection_params: Any) -> None:
        """
        Initialize SnowflakeEngine with connection parameters.

        Connection is NOT established at initialization time. Parameters are
        stored and used to create connections during execute() calls. This
        defers expensive connection setup and allows the engine to be
        instantiated without network access.

        Args:
            **connection_params: Snowflake connection parameters passed to
                snowflake.connector.connect(). Common parameters:
                - account (str): Account identifier with region suffix
                  (e.g., "xy12345.us-east-1")
                - user (str): Snowflake username
                - password (str): Snowflake password
                - warehouse (str, optional): Warehouse name
                - database (str, optional): Database name
                - schema (str, optional): Schema name
                - authenticator (str, optional): Authentication method
                  (default: username/password)

        Raises:
            ImportError: If snowflake-connector-python is not installed.
                Install with: pip install cubano[snowflake]

        Example:
            engine = SnowflakeEngine(
                account="xy12345.us-east-1",
                user="myuser",
                password="mypassword",
                warehouse="compute_wh",
            )
        """
        # Lazy import: only load snowflake.connector when SnowflakeEngine instantiated
        try:
            import snowflake.connector as _  # noqa: F401
        except ImportError as e:
            msg = (
                "snowflake-connector-python is required for SnowflakeEngine. "
                "Install with: pip install cubano[snowflake]"
            )
            raise ImportError(msg) from e

        self._connection_params = connection_params
        self.dialect = SnowflakeDialect()

    def to_sql(self, query: Query) -> str:
        """
        Generate Snowflake SQL for a query.

        Delegates to SQLBuilder with SnowflakeDialect to produce SQL with
        AGG() wrapping for metrics, double-quoted identifiers, and GROUP BY ALL.
        This reuses the SQL generation implementation from Phase 3.

        Args:
            query: Query object to convert to SQL. Must be valid for execution
                (has metrics and/or dimensions).

        Returns:
            SQL string formatted for Snowflake. Example:
                SELECT AGG("revenue"), "country"
                FROM "sales_view"
                GROUP BY ALL

        Raises:
            ValueError: If query is invalid for execution (missing metrics
                and dimensions, circular dependencies, etc.)

        Example:
            sql = engine.to_sql(query)
            print(sql)
            # SELECT AGG("revenue"), "country"
            # FROM "sales_view"
            # GROUP BY ALL
        """
        builder = SQLBuilder(self.dialect)
        return builder.build_select(query)

    def execute(self, query: Query) -> list[dict[str, Any]]:
        """
        Execute a query against Snowflake and return results.

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
            RuntimeError: For Snowflake execution errors. Includes original
                error code, SQL state, and message. Common causes:
                - Invalid SQL syntax (ProgrammingError)
                - Object does not exist (ProgrammingError)
                - Connection failure (DatabaseError)
                - Authentication failure (DatabaseError)
                - Permission denied (DatabaseError)
            ValueError: If query is invalid for execution.

        Example:
            results = engine.execute(query)
            for row in results:
                print(row["country"], row["revenue"])
        """
        import snowflake.connector  # type: ignore[reportUnusedImport]
        from snowflake.connector.errors import DatabaseError, ProgrammingError

        try:
            # Generate SQL using dialect-specific builder
            sql = self.to_sql(query)

            # Execute using context managers for guaranteed cleanup
            with (
                snowflake.connector.connect(**self._connection_params) as conn,  # type: ignore[reportUnknownMemberType]
                conn.cursor() as cur,
            ):
                cur.execute(sql)

                # Extract column names from cursor metadata
                columns = [desc[0] for desc in cur.description]

                # Fetch all rows and convert tuples to dicts
                rows = cur.fetchall()
                return [dict(zip(columns, row, strict=True)) for row in rows]

        except ProgrammingError as e:
            # SQL syntax errors, invalid objects, semantic view issues
            msg = f"Snowflake query failed: {e.msg} (Error {e.errno}, SQL State {e.sqlstate})"
            raise RuntimeError(msg) from e

        except DatabaseError as e:
            # Connection failures, authentication, permissions
            msg = f"Snowflake database error: {e.msg}"
            raise RuntimeError(msg) from e
