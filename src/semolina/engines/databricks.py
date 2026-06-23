"""
Databricks backend engine for metric view introspection.

Provides the DatabricksEngine class. Query execution runs through the
:class:`~semolina.engines.base.Engine` ADBC pool path; this subclass adds
Databricks-specific ``introspect()``.
"""
# Phase 44 (Plan 02): DatabricksEngine now owns the ADBC pool + dialect via the
# Engine base. ``introspect()`` is rewired onto the pool in Plan 04; until then
# its body still references the pre-Phase-44 native ``_connection_params`` seam,
# so scope-disable the two rules that the deferred native body triggers under
# basedpyright strict. Plan 04 REMOVES this pragma when introspect goes GREEN
# (intentionally not a `# type: ignore`).
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

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
            ``"main.analytics.sales_revenue_view"``.

    Returns:
        PascalCase string, e.g. ``"SalesView"`` or ``"SalesRevenueView"``.
    """
    segment = view_name.rsplit(".", 1)[-1]
    return "".join(word.capitalize() for word in segment.split("_"))


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
        .. code-block:: python

            from semolina.engines import DatabricksEngine
            from semolina import SemanticView, Metric, Dimension


            class Sales(SemanticView, view="main.analytics.sales_view"):
                revenue = Metric()
                country = Dimension()


            # Connection parameters (from environment or config)
            connection_params = {
                "server_hostname": "workspace.cloud.databricks.com",
                "http_path": "/sql/1.0/warehouses/warehouse_id",
                "access_token": "dapi...",
            }

            engine = DatabricksEngine(**connection_params)
            semolina.register("default", engine)
            results = (
                Sales.query()
                .metrics(Sales.revenue)
                .dimensions(Sales.country)
                .execute()
            )
            # Returns: [{"revenue": 1000, "country": "US"}, ...]

    See Also:
        - semolina.engines.sql.DatabricksDialect: SQL generation rules
        - semolina.engines.sql.SQLBuilder: Query to SQL converter
        - databricks.sql: Databricks SQL connector documentation
    """

    def introspect(self, view_name: str) -> IntrospectedView:
        """
        Introspect a Databricks metric view and return its intermediate representation.

        Executes ``DESCRIBE TABLE EXTENDED {view_name} AS JSON`` against Databricks
        and parses the JSON payload into an
        :class:`~semolina.codegen.introspector.IntrospectedView`.
        Columns with ``is_measure=True`` map to ``"metric"``; absent or
        ``False`` values map to ``"dimension"``. Databricks has no separate
        ``"fact"`` concept in its metric view API. Types without a clean Python
        mapping produce a ``"TODO: ..."`` placeholder so generated code remains
        syntactically valid.

        Args:
            view_name: Databricks metric view identifier to introspect.
                Accepts schema-qualified (``schema.view``) and Unity Catalog
                three-part (``catalog.schema.view``) names.

        Returns:
            Intermediate representation of the view, ready for code rendering.

        Raises:
            SemolinaConnectionError: If the connection or authentication fails
                (wraps ``OperationalError`` from the Databricks SQL connector).
            SemolinaViewNotFoundError: If the view does not exist or is not
                accessible (wraps ``DatabaseError`` from the connector).
            RuntimeError: For other unexpected connector errors (wraps ``Error``).

        Example:
            .. code-block:: python

                from semolina.engines import DatabricksEngine

                engine = DatabricksEngine(
                    server_hostname="workspace.cloud.databricks.com",
                    http_path="/sql/1.0/warehouses/abc123",
                    access_token="dapi...",
                )
                view = engine.introspect("main.analytics.sales_view")
                print(view.class_name)
                # SalesView
        """
        import json

        import databricks.sql  # type: ignore[reportUnusedImport]
        from databricks.sql.exc import (  # pyright: ignore[reportMissingImports]
            DatabaseError,
            Error,
            OperationalError,
        )

        from semolina.codegen.introspector import IntrospectedField, IntrospectedView
        from semolina.codegen.type_map import databricks_type_to_python

        try:
            with (
                databricks.sql.connect(**self._connection_params) as conn,  # type: ignore[reportUnknownMemberType]
                conn.cursor() as cur,  # type: ignore[reportUnknownMemberType]
            ):
                cur.execute(f"DESCRIBE TABLE EXTENDED {view_name} AS JSON")  # type: ignore[reportUnknownMemberType]
                row: Any = cur.fetchone()  # type: ignore[reportUnknownMemberType]
                schema: dict[str, Any] = json.loads(row[0])

                fields: list[IntrospectedField] = []
                for col in schema.get("columns", []):
                    is_measure: bool = col.get("is_measure", False)
                    field_type = "metric" if is_measure else "dimension"
                    type_obj: Any = col.get("type", {})
                    type_dict: dict[str, object] = (
                        cast("dict[str, object]", type_obj)
                        if isinstance(type_obj, dict)
                        else {"name": str(type_obj)}
                    )
                    py_type = databricks_type_to_python(type_dict)
                    data_type = f"TODO: {type_obj}" if py_type is None else py_type
                    description = str(col.get("comment") or "")
                    fields.append(
                        IntrospectedField(
                            name=str(col["name"]),
                            field_type=field_type,  # type: ignore[arg-type]
                            data_type=data_type,
                            description=description,
                        )
                    )

                return IntrospectedView(
                    view_name=view_name,
                    class_name=_to_pascal_case(view_name),
                    fields=fields,
                )

        except OperationalError as e:
            # Connection or authentication failure
            msg = f"Databricks connection failed: {e}"
            raise SemolinaConnectionError(msg) from e

        except DatabaseError as e:
            # Treat as view-not-found (DESCRIBE TABLE EXTENDED fails when the view does not exist)
            msg = f"Databricks view not found or inaccessible: {e}"
            raise SemolinaViewNotFoundError(msg) from e

        except Error as e:
            # Unexpected connector error
            msg = f"Databricks introspection failed: {e}"
            raise RuntimeError(msg) from e
