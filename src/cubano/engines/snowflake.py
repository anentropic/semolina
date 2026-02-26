"""
Snowflake backend engine for query execution.

Provides SnowflakeEngine class for executing queries against Snowflake semantic
views using the snowflake-connector-python driver. Supports lazy driver import,
context-managed connection lifecycle, and comprehensive error handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cubano.engines.base import CubanoConnectionError, CubanoViewNotFoundError, Engine
from cubano.engines.sql import SnowflakeDialect, SQLBuilder

if TYPE_CHECKING:
    from cubano.codegen.introspector import IntrospectedView
    from cubano.query import _Query


def _to_pascal_case(view_name: str) -> str:
    """
    Convert a warehouse view identifier to a PascalCase Python class name.

    Extracts the last segment after the final "." (handles schema-qualified and
    catalog-qualified names), then splits by "_" and capitalises each word.

    Args:
        view_name: Warehouse view identifier, e.g. ``"sales_view"`` or
            ``"my_db.my_schema.sales_revenue_view"``.

    Returns:
        PascalCase string, e.g. ``"SalesView"`` or ``"SalesRevenueView"``.
    """
    segment = view_name.rsplit(".", 1)[-1]
    return "".join(word.capitalize() for word in segment.split("_"))


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
        ```python
        from cubano.engines import SnowflakeEngine
        from cubano import SemanticView, Metric, Dimension


        class Sales(SemanticView, view="sales_view"):
            revenue = Metric()
            country = Dimension()


        # Connection parameters (from environment or config)
        connection_params = {
            "account": "xy12345.us-east-1",  # Include region suffix
            "user": "username",
            "password": "password",
            "warehouse": "compute_wh",  # Optional
            "database": "analytics",  # Optional
            "schema": "public",  # Optional
        }

        engine = SnowflakeEngine(**connection_params)
        cubano.register("default", engine)
        results = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .execute()
        )
        # Returns: [{"revenue": 1000, "country": "US"}, ...]
        ```

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
            ```python
            engine = SnowflakeEngine(
                account="xy12345.us-east-1",
                user="myuser",
                password="mypassword",
                warehouse="compute_wh",
            )
            ```
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

    def to_sql(self, query: _Query) -> str:
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
            ```python
            sql = engine.to_sql(query)
            print(sql)
            # SELECT AGG("revenue"), "country"
            # FROM "sales_view"
            # GROUP BY ALL
            ```
        """
        builder = SQLBuilder(self.dialect)
        return builder.build_select(query)

    def execute(self, query: _Query) -> list[dict[str, Any]]:
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
            ```python
            [
                {"revenue": 1000, "country": "US"},
                {"revenue": 500, "country": "UK"},
            ]
            ```

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
            ```python
            results = engine.execute(query)
            for row in results:
                print(row["country"], row["revenue"])
            ```
        """
        import snowflake.connector  # type: ignore[reportUnusedImport]
        from snowflake.connector.errors import DatabaseError, ProgrammingError

        try:
            # Generate parameterized SQL using dialect-specific builder
            builder = SQLBuilder(self.dialect)
            sql, params = builder.build_select_with_params(query)

            # Execute using context managers for guaranteed cleanup
            with (
                snowflake.connector.connect(**self._connection_params) as conn,  # type: ignore[reportUnknownMemberType]
                conn.cursor() as cur,
            ):
                cur.execute(sql, params)

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

    def introspect(self, view_name: str) -> IntrospectedView:
        """
        Introspect a Snowflake semantic view and return its intermediate representation.

        Executes ``SHOW COLUMNS IN VIEW {view_name}`` against Snowflake
        and parses the result rows into an :class:`~cubano.codegen.introspector.IntrospectedView`.
        Column ``kind`` values (``METRIC``, ``DIMENSION``, ``FACT``) are
        lowercased before use. The ``data_type`` JSON column is parsed and mapped
        to a Python annotation string; types without a clean mapping produce a
        ``"TODO: ..."`` placeholder so generated code remains syntactically valid.

        Args:
            view_name: Snowflake semantic view identifier to introspect.
                Accepts schema-qualified (``schema.view``) and
                catalog-qualified (``catalog.schema.view``) names.

        Returns:
            Intermediate representation of the view, ready for code rendering.

        Raises:
            CubanoViewNotFoundError: If the view does not exist or is not
                accessible (wraps :class:`~snowflake.connector.errors.ProgrammingError`).
            CubanoConnectionError: If the connection or authentication fails
                (wraps :class:`~snowflake.connector.errors.DatabaseError`).

        Example:
            ```python
            from cubano.engines import SnowflakeEngine

            engine = SnowflakeEngine(
                account="xy12345.us-east-1",
                user="myuser",
                password="mypassword",
            )
            view = engine.introspect("analytics.sales_view")
            print(view.class_name)
            # SalesView
            ```
        """
        import json

        import snowflake.connector  # type: ignore[reportUnusedImport]
        from snowflake.connector.errors import DatabaseError, ProgrammingError

        from cubano.codegen.introspector import IntrospectedField, IntrospectedView
        from cubano.codegen.type_map import snowflake_json_type_to_python

        # SHOW COLUMNS IN VIEW requires a fully-qualified database.schema.view
        # identifier. Auto-prepend the connection database when the caller
        # supplies fewer than three dot-separated parts.
        parts = view_name.split(".")
        if len(parts) < 3 and "database" in self._connection_params:
            qualified_name = f"{self._connection_params['database']}.{view_name}"
        else:
            qualified_name = view_name

        try:
            with (
                snowflake.connector.connect(**self._connection_params) as conn,  # type: ignore[reportUnknownMemberType]
                conn.cursor() as cur,
            ):
                cur.execute(f"SHOW COLUMNS IN VIEW {qualified_name}")

                # Build column name list from cursor description (lowercase for safe access)
                columns = [desc[0].lower() for desc in cur.description]

                fields: list[IntrospectedField] = []
                for row in cur.fetchall():
                    d = dict(zip(columns, row, strict=True))
                    field_type = d["kind"].lower()  # type: ignore[union-attr]
                    type_json: dict[str, object] = json.loads(d["data_type"])  # type: ignore[arg-type]
                    py_type = snowflake_json_type_to_python(type_json)
                    data_type = f"TODO: {d['data_type']}" if py_type is None else py_type
                    description = str(d.get("comment") or "")

                    # Lowercase the column name to produce a Pythonic field name.
                    # For standard Snowflake UPPERCASE columns (e.g., ORDER_ID),
                    # the Python name is 'order_id' and normalize_identifier
                    # round-trips it back to 'ORDER_ID' — no source_name needed.
                    # For quoted-lowercase columns (e.g., "order_id" stored as-is),
                    # upper() != original, so source_name is set to preserve the
                    # exact warehouse column name for SQL generation.
                    original_col_name = str(d["column_name"])
                    python_name = original_col_name.lower()
                    normalized_back = python_name.upper()  # SnowflakeDialect behavior
                    source_name = (
                        original_col_name if normalized_back != original_col_name else None
                    )

                    fields.append(
                        IntrospectedField(
                            name=python_name,
                            field_type=field_type,  # type: ignore[arg-type]
                            data_type=data_type,
                            description=description,
                            source_name=source_name,
                        )
                    )

                return IntrospectedView(
                    view_name=view_name,
                    class_name=_to_pascal_case(view_name),
                    fields=fields,
                )

        except ProgrammingError as e:
            # SQL errors, invalid view name, view does not exist
            msg = f"Snowflake view not found or inaccessible: {e}"
            raise CubanoViewNotFoundError(msg) from e

        except DatabaseError as e:
            # Connection failures, authentication, permissions
            msg = f"Snowflake connection failed: {e}"
            raise CubanoConnectionError(msg) from e
