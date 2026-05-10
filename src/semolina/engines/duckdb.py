"""
DuckDB backend engine for semantic view introspection.

Provides DuckDBEngine class for introspecting DuckDB semantic views using
the native duckdb Python driver. Uses a two-step approach: DESCRIBE SEMANTIC
VIEW for field structure, DESCRIBE SELECT for type resolution.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from semolina.engines.base import Engine, SemolinaConnectionError, SemolinaViewNotFoundError

if TYPE_CHECKING:
    from semolina.codegen.introspector import IntrospectedView
    from semolina.query import _Query


def _to_pascal_case(view_name: str) -> str:
    """
    Convert a warehouse view identifier to a PascalCase Python class name.

    Extracts the last segment after the final "." (handles schema-qualified
    names), then splits by "_" and capitalises each word.

    Args:
        view_name: Warehouse view identifier, e.g. ``"sales_view"`` or
            ``"main.sales_revenue_view"``.

    Returns:
        PascalCase string, e.g. ``"SalesView"`` or ``"SalesRevenueView"``.
    """
    segment = view_name.rsplit(".", 1)[-1]
    return "".join(word.capitalize() for word in segment.split("_"))


def _parse_describe_semantic_view(
    rows: list[tuple[str, str, str, str, str]],
) -> dict[str, dict[str, str]]:
    """
    Parse DESCRIBE SEMANTIC VIEW rows into a field-name -> properties dict.

    Only includes DIMENSION, METRIC, FACT rows. Skips TABLE, RELATIONSHIP,
    SEMANTIC_VIEW, MATERIALIZATION, etc.

    Args:
        rows: Raw rows from ``DESCRIBE SEMANTIC VIEW``. Each row is a 5-tuple
            of (object_kind, object_name, parent_entity, property, property_value).

    Returns:
        Dict mapping field name to its properties dict. Each properties dict
        has a ``"kind"`` key (``"dimension"``, ``"metric"``, or ``"fact"``)
        plus any properties from the DESCRIBE output (lowercased keys).
    """
    fields: dict[str, dict[str, str]] = defaultdict(dict)
    for object_kind, object_name, _parent_entity, prop, prop_value in rows:
        if object_kind in ("DIMENSION", "METRIC", "FACT"):
            if "kind" not in fields[object_name]:
                fields[object_name]["kind"] = object_kind.lower()
            fields[object_name][prop.lower()] = prop_value
    return dict(fields)


class DuckDBEngine(Engine):
    """
    DuckDB backend engine for semantic view introspection.

    Introspects DuckDB semantic views using the native ``duckdb`` Python driver
    with a two-step approach:

    1. ``DESCRIBE SEMANTIC VIEW`` for field names, kinds, access modifiers,
       and comments.
    2. ``DESCRIBE SELECT * FROM semantic_view(...)`` for resolved SQL types.

    This engine is introspection-only. Query execution uses the pool path
    (``register()`` with a DuckDB connection pool). Calling ``to_sql()`` or
    ``execute()`` raises ``NotImplementedError``.

    Example:
        .. code-block:: python

            from semolina.engines import DuckDBEngine

            engine = DuckDBEngine(database="/path/to/analytics.db")
            view = engine.introspect("orders")
            print(view.class_name)
            # Orders

    See Also:
        - semolina.codegen.type_map.duckdb_type_to_python: Type mapping
        - semolina.codegen.python_renderer: Code generation from IntrospectedView
    """

    def __init__(self, *, database: str = ":memory:") -> None:
        """
        Initialize DuckDBEngine with a database file path.

        Connection is NOT established at initialization time. The database
        path is stored and used to create connections during introspect() calls.

        Args:
            database: Path to the DuckDB database file, or ``":memory:"`` for
                an in-memory database. Defaults to ``":memory:"``.

        Raises:
            ImportError: If the ``duckdb`` package is not installed.
                Install with: ``pip install semolina[duckdb]``
        """
        try:
            import duckdb as _  # noqa: F401  # pyright: ignore[reportMissingImports]
        except ImportError as e:
            msg = "duckdb is required for DuckDBEngine. Install with: pip install semolina[duckdb]"
            raise ImportError(msg) from e

        self._database = database

    def to_sql(self, query: _Query) -> str:
        """
        Not implemented -- DuckDBEngine is for introspection only.

        Raises:
            NotImplementedError: Always. Use ``register()`` with a DuckDB
                connection pool for query execution.
        """
        raise NotImplementedError(
            "DuckDBEngine is for introspection only. "
            "Use register() with a DuckDB pool for query execution."
        )

    def execute(self, query: _Query) -> list[Any]:
        """
        Not implemented -- DuckDBEngine is for introspection only.

        Raises:
            NotImplementedError: Always. Use ``register()`` with a DuckDB
                connection pool for query execution.
        """
        raise NotImplementedError(
            "DuckDBEngine is for introspection only. "
            "Use register() with a DuckDB pool for query execution."
        )

    def introspect(self, view_name: str) -> IntrospectedView:
        """
        Introspect a DuckDB semantic view and return its intermediate representation.

        Uses a two-step approach:

        1. ``DESCRIBE SEMANTIC VIEW {name}`` to discover field names, kinds
           (DIMENSION/METRIC/FACT), access modifiers (PUBLIC/PRIVATE), and
           comments. Note: DATA_TYPE is always empty in current DuckDB.
        2. ``DESCRIBE SELECT * FROM semantic_view(...)`` to resolve actual
           SQL types for each field. Separate queries are issued for
           dimensions+metrics vs facts.

        PRIVATE metrics and facts are excluded from the output (they cannot
        be queried directly). Dimensions do not have access modifiers and
        are always included.

        Args:
            view_name: DuckDB semantic view identifier to introspect.
                Accepts schema-qualified names (e.g., ``"main.orders"``);
                the schema prefix is stripped for DESCRIBE commands since
                DuckDB only accepts unqualified names.

        Returns:
            Intermediate representation of the view, ready for code rendering.

        Raises:
            SemolinaViewNotFoundError: If the semantic view does not exist
                (wraps ``duckdb.CatalogException``).
            SemolinaConnectionError: If the database file cannot be opened
                (wraps ``duckdb.IOException``).
            RuntimeError: For other unexpected DuckDB errors.

        Example:
            .. code-block:: python

                from semolina.engines import DuckDBEngine

                engine = DuckDBEngine(database="/path/to/analytics.db")
                view = engine.introspect("orders")
                for field in view.fields:
                    print(f"{field.name}: {field.field_type} ({field.data_type})")
        """
        import duckdb  # pyright: ignore[reportMissingImports]

        from semolina.codegen.introspector import IntrospectedField, IntrospectedView
        from semolina.codegen.type_map import duckdb_type_to_python

        # Strip schema prefix -- DESCRIBE SEMANTIC VIEW only accepts unqualified names
        unqualified = view_name.rsplit(".", 1)[-1]

        conn = None
        try:
            conn = duckdb.connect(database=self._database, read_only=True)
            conn.execute("LOAD semantic_views")
            # Step 1: Get field structure from DESCRIBE SEMANTIC VIEW
            result = conn.execute(f"DESCRIBE SEMANTIC VIEW {unqualified}")
            raw_rows = result.fetchall()
            parsed = _parse_describe_semantic_view(raw_rows)

            # Categorise fields and exclude PRIVATE
            dims = [name for name, props in parsed.items() if props["kind"] == "dimension"]
            public_metrics = [
                name
                for name, props in parsed.items()
                if props["kind"] == "metric" and props.get("access_modifier") != "PRIVATE"
            ]
            public_facts = [
                name
                for name, props in parsed.items()
                if props["kind"] == "fact" and props.get("access_modifier") != "PRIVATE"
            ]

            # Step 2: Get types from DESCRIBE SELECT ... FROM semantic_view()
            type_map: dict[str, str] = {}

            if dims or public_metrics:
                parts: list[str] = []
                if dims:
                    dim_list = "[" + ", ".join(f"'{n}'" for n in dims) + "]"
                    parts.append(f"dimensions := {dim_list}")
                if public_metrics:
                    metric_list = "[" + ", ".join(f"'{n}'" for n in public_metrics) + "]"
                    parts.append(f"metrics := {metric_list}")
                sql = f"DESCRIBE SELECT * FROM semantic_view('{unqualified}', {', '.join(parts)})"
                type_result = conn.execute(sql)
                for row in type_result.fetchall():
                    type_map[row[0]] = row[1]

            if public_facts:
                fact_list = "[" + ", ".join(f"'{n}'" for n in public_facts) + "]"
                sql = f"DESCRIBE SELECT * FROM semantic_view('{unqualified}', facts := {fact_list})"
                type_result = conn.execute(sql)
                for row in type_result.fetchall():
                    type_map[row[0]] = row[1]

            # Build IntrospectedField list
            fields: list[IntrospectedField] = []
            for field_name, props in parsed.items():
                # Skip PRIVATE fields
                if props.get("access_modifier") == "PRIVATE":
                    continue

                sql_type = type_map.get(field_name)
                if sql_type:
                    py_type = duckdb_type_to_python(sql_type)
                    data_type = py_type if py_type is not None else f"TODO: {sql_type}"
                else:
                    data_type = None

                description = props.get("comment", "")

                fields.append(
                    IntrospectedField(
                        name=field_name,
                        field_type=props["kind"],  # type: ignore[arg-type]
                        data_type=data_type,
                        description=description,
                    )
                )

            return IntrospectedView(
                view_name=view_name,
                class_name=_to_pascal_case(view_name),
                fields=fields,
            )

        except duckdb.CatalogException as e:
            msg = f"DuckDB semantic view not found: {e}"
            raise SemolinaViewNotFoundError(msg) from e

        except duckdb.IOException as e:
            msg = f"DuckDB connection failed: {e}"
            raise SemolinaConnectionError(msg) from e

        except duckdb.Error as e:
            msg = f"DuckDB introspection failed: {e}"
            raise RuntimeError(msg) from e

        finally:
            if conn is not None:
                conn.close()
