"""
Snowflake backend engine for semantic view introspection.

Provides the SnowflakeEngine class. Query execution runs through the
:class:`~semolina.engines.base.Engine` ADBC pool path; this subclass adds
Snowflake-specific ``introspect()``.
"""
# Phase 44 (Plan 02): SnowflakeEngine now owns the ADBC pool + dialect via the
# Engine base. ``introspect()`` is rewired onto the pool in Plan 03; until then
# its body still references the pre-Phase-44 native ``_connection_params`` seam,
# so scope-disable the two rules that the deferred native body triggers under
# basedpyright strict. Plan 03 REMOVES this pragma when introspect goes GREEN
# (intentionally not a `# type: ignore`).
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false

from __future__ import annotations

from typing import TYPE_CHECKING

from semolina.engines.base import Engine, SemolinaConnectionError, SemolinaViewNotFoundError

if TYPE_CHECKING:
    from semolina.codegen.introspector import IntrospectedView


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
        .. code-block:: python

            from semolina.engines import SnowflakeEngine
            from semolina import SemanticView, Metric, Dimension


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
            semolina.register("default", engine)
            results = (
                Sales.query()
                .metrics(Sales.revenue)
                .dimensions(Sales.country)
                .execute()
            )
            # Returns: [{"revenue": 1000, "country": "US"}, ...]

    See Also:
        - semolina.engines.sql.SnowflakeDialect: SQL generation rules
        - semolina.engines.sql.SQLBuilder: Query to SQL converter
        - snowflake.connector: Snowflake Python driver documentation
    """

    def introspect(self, view_name: str) -> IntrospectedView:
        """
        Introspect a Snowflake semantic view and return its intermediate representation.

        Executes ``SHOW COLUMNS IN VIEW {view_name}`` against Snowflake
        and parses the result rows into an :class:`~semolina.codegen.introspector.IntrospectedView`.
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
            SemolinaViewNotFoundError: If the view does not exist or is not
                accessible (wraps :class:`~snowflake.connector.errors.ProgrammingError`).
            SemolinaConnectionError: If the connection or authentication fails
                (wraps :class:`~snowflake.connector.errors.DatabaseError`).

        Example:
            .. code-block:: python

                from semolina.engines import SnowflakeEngine

                engine = SnowflakeEngine(
                    account="xy12345.us-east-1",
                    user="myuser",
                    password="mypassword",
                )
                view = engine.introspect("analytics.sales_view")
                print(view.class_name)
                # SalesView
        """
        import json

        import snowflake.connector  # type: ignore[reportUnusedImport]
        from snowflake.connector.errors import (  # pyright: ignore[reportMissingImports]
            DatabaseError,
            ProgrammingError,
        )

        from semolina.codegen.introspector import IntrospectedField, IntrospectedView
        from semolina.codegen.type_map import snowflake_json_type_to_python

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
            raise SemolinaViewNotFoundError(msg) from e

        except DatabaseError as e:
            # Connection failures, authentication, permissions
            msg = f"Snowflake connection failed: {e}"
            raise SemolinaConnectionError(msg) from e
