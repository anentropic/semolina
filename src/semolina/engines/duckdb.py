"""
DuckDB backend engine for semantic view introspection.

Provides the DuckDBEngine class. Query execution runs through the
:class:`~semolina.engines.base.Engine` ADBC pool path; this subclass adds
DuckDB-specific ``introspect()`` (DESCRIBE SEMANTIC VIEW + DESCRIBE SELECT) run
over the engine's owned ADBC pool. The ``semantic_views`` community extension is
loaded by the pool's ``connect`` event listener (wired in ``create_engine``).
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, cast

from semolina.engines.base import Engine, SemolinaConnectionError, SemolinaViewNotFoundError

if TYPE_CHECKING:
    from typing import Literal

    from semolina.codegen.introspector import IntrospectedView


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


def _sql_str_literal(value: str) -> str:
    """
    Render a value as a single-quoted SQL string literal, escaping quotes.

    Doubles any embedded single quote (``'`` -> ``''``) so a catalog field or
    view name containing a quote cannot break out of the literal in the
    ``semantic_view('...')`` introspection calls. These values come from the
    warehouse catalog rather than direct user input, so this is defensive
    hardening of an existing interpolation pattern.

    Args:
        value: The raw string to embed (a field or view name).

    Returns:
        The value wrapped in single quotes with internal quotes doubled,
        e.g. ``"o'brien"`` becomes ``"'o''brien'"``.
    """
    return "'" + value.replace("'", "''") + "'"


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

    Built by :func:`semolina.config.create_engine` from a ``DuckDBConfig``; it
    owns one ADBC connection pool (via adbc-poolhouse) whose ``connect`` event
    loads the ``semantic_views`` community extension. Introspection runs over a
    pooled ADBC connection with a two-step approach:

    1. ``DESCRIBE SEMANTIC VIEW`` for field names, kinds, access modifiers,
       and comments.
    2. ``DESCRIBE SELECT * FROM semantic_view(...)`` for resolved SQL types.

    Query execution runs through the :class:`~semolina.engines.base.Engine`
    pool path (``execute()``).

    Example:
        .. code-block:: python

            from adbc_poolhouse import DuckDBConfig

            from semolina.config import create_engine

            engine = create_engine(DuckDBConfig(database="/path/to/analytics.db"))
            view = engine.introspect("orders")
            print(view.class_name)
            # Orders

    See Also:
        - semolina.config.create_engine: Builds an Engine from a config or name
        - semolina.codegen.type_map.duckdb_type_to_python: Type mapping
        - semolina.codegen.python_renderer: Code generation from IntrospectedView
    """

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
                (wraps an ADBC :class:`~adbc_driver_manager.Error` whose message
                indicates a missing catalog object).
            SemolinaConnectionError: If the connection cannot be established
                (wraps any other ADBC :class:`~adbc_driver_manager.Error`).

        Example:
            .. code-block:: python

                from adbc_poolhouse import DuckDBConfig

                from semolina.config import create_engine

                engine = create_engine(DuckDBConfig(database="/path/to/analytics.db"))
                view = engine.introspect("orders")
                for field in view.fields:
                    print(f"{field.name}: {field.field_type} ({field.data_type})")
        """
        from adbc_driver_manager import Error  # pyright: ignore[reportMissingImports]

        from semolina.codegen.introspector import IntrospectedField, IntrospectedView
        from semolina.codegen.type_map import duckdb_type_to_python

        # Strip schema prefix -- DESCRIBE SEMANTIC VIEW only accepts unqualified names
        unqualified = view_name.rsplit(".", 1)[-1]

        try:
            with self.connect() as conn:
                cur = conn.cursor()
                # Step 1: Get field structure from DESCRIBE SEMANTIC VIEW
                cur.execute(f"DESCRIBE SEMANTIC VIEW {unqualified}")
                raw_rows = cur.fetchall()
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

                view_literal = _sql_str_literal(unqualified)

                if dims or public_metrics:
                    parts: list[str] = []
                    if dims:
                        dim_list = "[" + ", ".join(_sql_str_literal(n) for n in dims) + "]"
                        parts.append(f"dimensions := {dim_list}")
                    if public_metrics:
                        metric_list = (
                            "[" + ", ".join(_sql_str_literal(n) for n in public_metrics) + "]"
                        )
                        parts.append(f"metrics := {metric_list}")
                    sql = (
                        f"DESCRIBE SELECT * FROM semantic_view({view_literal}, {', '.join(parts)})"
                    )
                    cur.execute(sql)
                    for row in cur.fetchall():
                        type_map[row[0]] = row[1]

                if public_facts:
                    fact_list = "[" + ", ".join(_sql_str_literal(n) for n in public_facts) + "]"
                    sql = (
                        f"DESCRIBE SELECT * FROM semantic_view({view_literal}, "
                        f"facts := {fact_list})"
                    )
                    cur.execute(sql)
                    for row in cur.fetchall():
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
                            field_type=cast(
                                "Literal['metric', 'dimension', 'fact']", props["kind"]
                            ),
                            data_type=data_type,
                            description=description,
                            raw_type=sql_type,
                        )
                    )

                return IntrospectedView(
                    view_name=view_name,
                    class_name=_to_pascal_case(view_name),
                    fields=fields,
                )

        except Error as e:
            # Over ADBC, DuckDB surfaces a missing semantic view (and other
            # catalog/binder failures) as adbc_driver_manager.Error. Treat a
            # missing-object message as view-not-found; everything else as a
            # connection/operational failure.
            message = str(e)
            lowered = message.lower()
            if (
                "does not exist" in lowered
                or "not found" in lowered
                or "catalog error" in lowered
                or "did you mean" in lowered
            ):
                msg = f"DuckDB semantic view not found: {message}"
                raise SemolinaViewNotFoundError(msg) from e
            msg = f"DuckDB introspection failed: {message}"
            raise SemolinaConnectionError(msg) from e
