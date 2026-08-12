"""
Snowflake backend engine for semantic view introspection.

Provides the SnowflakeEngine class. Query execution runs through the
:class:`~semolina.engines.base.Engine` ADBC pool path; this subclass adds
Snowflake-specific ``introspect()``, which runs ``SHOW COLUMNS IN VIEW`` over
the engine's owned ADBC pool.
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
    Snowflake backend engine for semantic view queries and introspection.

    Built by :func:`semolina.config.create_engine` from a ``SnowflakeConfig``;
    it owns one ADBC connection pool (via adbc-poolhouse) plus the Snowflake
    dialect. Query execution runs through the
    :class:`~semolina.engines.base.Engine` pool path (``execute()``); this
    subclass adds Snowflake-specific :meth:`introspect`, which runs
    ``SHOW COLUMNS IN VIEW`` over a pooled ADBC connection.

    Connection Lifecycle:
        - One ADBC pool is owned by the Engine for its lifetime
        - ``connect()`` checks a connection out of the pool per call
        - The pool returns the connection on context-manager exit

    Error Handling (introspect):
        - ADBC ``ProgrammingError`` (invalid view, SQL syntax) ->
          ``SemolinaViewNotFoundError``
        - ADBC ``OperationalError`` (connection, permissions) ->
          ``SemolinaConnectionError``

    SQL Generation:
        - Delegates to SQLBuilder with SnowflakeDialect
        - Generates AGG() wrapping for metrics
        - Uses double-quoted identifiers for case preservation
        - GROUP BY ALL for automatic dimension derivation

    Example:
        .. code-block:: python

            from adbc_poolhouse import SnowflakeConfig

            import semolina
            from semolina import Dimension, Metric, SemanticView
            from semolina.config import create_engine


            class Sales(SemanticView, view="sales_view"):
                revenue = Metric()
                country = Dimension()


            engine = create_engine(
                SnowflakeConfig(account="xy12345.us-east-1", user="username")
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
        - semolina.engines.sql.SnowflakeDialect: SQL generation rules
        - semolina.engines.sql.SQLBuilder: Query to SQL converter
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
                accessible (wraps an ADBC :class:`~adbc_driver_manager.ProgrammingError`).
            SemolinaConnectionError: If the connection or authentication fails
                (wraps an ADBC :class:`~adbc_driver_manager.OperationalError` /
                :class:`~adbc_driver_manager.DatabaseError`).

        Example:
            .. code-block:: python

                from adbc_poolhouse import SnowflakeConfig

                from semolina.config import create_engine

                engine = create_engine(
                    SnowflakeConfig(account="xy12345.us-east-1", user="myuser")
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
        from semolina.codegen.type_map import snowflake_json_type_to_python

        # SHOW COLUMNS IN VIEW requires a fully-qualified database.schema.view
        # identifier. Auto-prepend the connection database when the caller
        # supplies fewer than three dot-separated parts. The database lives on
        # the poolhouse config the Engine holds (set by create_engine).
        parts = view_name.split(".")
        config_database = getattr(self._config, "database", None)
        if len(parts) < 3 and config_database:
            qualified_name = f"{config_database}.{view_name}"
        else:
            qualified_name = view_name

        try:
            with self.connect() as conn:
                cur = conn.cursor()
                cur.execute(f"SHOW COLUMNS IN VIEW {qualified_name}")

                # Build column name list from cursor description (lowercase for safe access)
                columns = [desc[0].lower() for desc in cur.description]

                fields: list[IntrospectedField] = []
                for row in cur.fetchall():
                    d: dict[str, Any] = dict(zip(columns, row, strict=True))
                    field_type = cast(
                        "Literal['metric', 'dimension', 'fact']", str(d["kind"]).lower()
                    )
                    type_json: dict[str, object] = json.loads(d["data_type"])
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
                            field_type=field_type,
                            data_type=data_type,
                            description=description,
                            raw_type=str(d["data_type"]),
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

        except OperationalError as e:
            # Connection failures, authentication, permissions
            msg = f"Snowflake connection failed: {e}"
            raise SemolinaConnectionError(msg) from e
