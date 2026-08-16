"""
Databricks backend engine for metric view introspection.

Provides the DatabricksEngine class. Query execution runs through the
:class:`~semolina.engines.base.Engine` ADBC pool path; this subclass adds
Databricks-specific ``introspect()``, which runs
``DESCRIBE TABLE EXTENDED {view} AS JSON`` over the engine's owned ADBC pool.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from semolina.engines.base import Engine, SemolinaConnectionError, SemolinaViewNotFoundError

if TYPE_CHECKING:
    from typing import Literal

    from semolina.codegen.introspector import IntrospectedView


def _to_pascal_case(view_name: str) -> str:
    """
    Convert a warehouse view identifier to a PascalCase Python class name.

    Extracts the last segment after the final "." (handles schema-qualified and
    Unity Catalog three-part names), then splits by "_" and capitalizes each
    word.

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

    Built by :func:`semolina.config.create_engine` from a ``DatabricksConfig``;
    it owns one ADBC connection pool (via adbc-poolhouse) plus the Databricks
    dialect, exactly like the Snowflake and DuckDB engines. Query execution runs
    through the :class:`~semolina.engines.base.Engine` pool path
    (:meth:`~semolina.engines.base.Engine.execute`).

    Error Handling (introspect):
        - ADBC ``ProgrammingError`` (invalid view, SQL syntax) ->
          ``SemolinaViewNotFoundError``
        - ADBC ``OperationalError`` (connection, permissions) ->
          ``SemolinaConnectionError``

    Connection Lifecycle:
        - One ADBC pool is owned by the Engine for its lifetime
        - ``connect()`` checks a connection out of the pool per call
        - The pool returns the connection on context-manager exit

    SQL Generation:
        - Delegates to SQLBuilder with DatabricksDialect
        - Generates MEASURE() wrapping for metrics
        - Uses backtick-quoted identifiers for case preservation
        - GROUP BY ALL for automatic dimension derivation

    Unity Catalog:
        - Three-part names (catalog.schema.view) work transparently
        - Each part quoted separately with backticks

    Example:
        .. code-block:: python

            from adbc_poolhouse import DatabricksConfig

            import semolina
            from semolina import Dimension, Metric, SemanticView
            from semolina.config import create_engine


            class Sales(SemanticView, view="main.analytics.sales_view"):
                revenue = Metric()
                country = Dimension()


            engine = create_engine(
                DatabricksConfig(
                    host="workspace.cloud.databricks.com",
                    http_path="/sql/1.0/warehouses/abc123",
                    token="dapi...",
                )
            )
            semolina.register("default", engine)
            results = (
                Sales.query()
                .metrics(Sales.revenue)
                .dimensions(Sales.country)
                .execute()
            )
            # Returns: [{"revenue": 1000, "country": "US"}, ...]

    See Also:
        - semolina.config.create_engine: Builds an Engine from a config or name
        - semolina.engines.sql.DatabricksDialect: SQL generation rules
        - semolina.engines.sql.SQLBuilder: Query to SQL converter
    """

    def introspect(self, view_name: str) -> IntrospectedView:
        """
        Introspect a Databricks metric view and return its intermediate representation.

        Executes ``DESCRIBE TABLE EXTENDED {view_name} AS JSON`` over the
        engine's owned ADBC pool and parses the single-cell JSON payload into an
        :class:`~semolina.codegen.introspector.IntrospectedView`. Each entry in
        the payload's ``columns`` array becomes one field: columns flagged
        ``is_measure`` map to ``metric``, all others to ``dimension`` (Databricks
        metric views expose only dimensions and measures). The ``type.name`` is
        mapped to a Python annotation string; types without a clean mapping
        produce a ``"TODO: ..."`` placeholder so generated code stays valid.

        Args:
            view_name: Databricks metric view identifier to introspect.
                Accepts schema-qualified (``schema.view``) and Unity Catalog
                three-part (``catalog.schema.view``) names. Unqualified names
                resolve against the connection's default catalog/schema.

        Returns:
            Intermediate representation of the view, ready for code rendering.

        Raises:
            SemolinaViewNotFoundError: If the view does not exist or is not
                accessible (wraps an ADBC
                :class:`~adbc_driver_manager.ProgrammingError`).
            SemolinaConnectionError: If the connection or authentication fails
                (wraps an ADBC :class:`~adbc_driver_manager.OperationalError`).

        Example:
            .. code-block:: python

                from adbc_poolhouse import DatabricksConfig

                from semolina.config import create_engine

                engine = create_engine(
                    DatabricksConfig(
                        host="workspace.cloud.databricks.com",
                        http_path="/sql/1.0/warehouses/abc123",
                        token="dapi...",
                    )
                )
                view = engine.introspect("analytics.sales_view")
                print(view.class_name)
                # SalesView
        """
        import json

        from adbc_driver_manager import (  # pyright: ignore[reportMissingImports]
            OperationalError,
            ProgrammingError,
        )

        from semolina.codegen.introspector import IntrospectedField, IntrospectedView
        from semolina.codegen.type_map import databricks_type_to_python

        try:
            with self.connect() as conn:
                cur = conn.cursor()
                cur.execute(f"DESCRIBE TABLE EXTENDED {view_name} AS JSON")
                row: Any = cur.fetchone()
                payload: dict[str, Any] = json.loads(row[0])

                fields: list[IntrospectedField] = []
                for col in payload.get("columns", []):
                    original_col_name = str(col["name"])
                    # Databricks metric views expose only dimensions and
                    # measures; ``is_measure`` marks a metric, everything else is
                    # a dimension (there is no Databricks "fact" concept).
                    field_type = cast(
                        "Literal['metric', 'dimension', 'fact']",
                        "metric" if col.get("is_measure") else "dimension",
                    )
                    type_obj: Any = col.get("type") or {}
                    py_type = databricks_type_to_python(
                        type_obj if isinstance(type_obj, dict) else {}
                    )
                    raw_type_name = (
                        type_obj.get("name") if isinstance(type_obj, dict) else str(type_obj)
                    )
                    data_type = py_type if py_type is not None else f"TODO: {raw_type_name}"
                    description = str(col.get("comment") or "")

                    # Databricks folds unquoted identifiers to lowercase (see
                    # DatabricksDialect.normalize_identifier). Set source_name
                    # only when the lowercased Python name would not round-trip
                    # back to the exact warehouse column name.
                    python_name = original_col_name.lower()
                    source_name = original_col_name if python_name != original_col_name else None

                    fields.append(
                        IntrospectedField(
                            name=python_name,
                            field_type=field_type,
                            data_type=data_type,
                            description=description,
                            raw_type=raw_type_name,
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
            msg = f"Databricks view not found or inaccessible: {e}"
            raise SemolinaViewNotFoundError(msg) from e

        except OperationalError as e:
            # Connection failures, authentication, permissions
            msg = f"Databricks connection failed: {e}"
            raise SemolinaConnectionError(msg) from e
