"""
DuckDB backend engine for semantic view introspection.

Provides the DuckDBEngine class. Query execution runs through the
:class:`~semolina.engines.base.Engine` ADBC pool path; this subclass adds
DuckDB-specific ``introspect()`` (DESCRIBE SEMANTIC VIEW + DESCRIBE SELECT) run
over the engine's owned ADBC pool. The ``semantic_views`` community extension is
loaded by the pool's ``connect`` event listener (wired in ``create_engine``).
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING, cast

from semolina.engines.base import Engine, SemolinaConnectionError, SemolinaViewNotFoundError

# The single escaper for a `semantic_view()` string literal, shared with `DuckDBSQLBuilder`.
# Introspection and query building interpolate the same catalogue-sourced names into the
# same grammar, so they must not carry two copies of the rule.
from semolina.engines.sql import DuckDBDialect
from semolina.engines.sql import sql_str_literal as _sql_str_literal
from semolina.exceptions import SemolinaIntrospectionError

if TYPE_CHECKING:
    from typing import Literal

    from semolina.codegen.introspector import IntrospectedView

__all__ = [
    "DuckDBEngine",
]


_MISSING_VIEW = re.compile(
    r"semantic view '.*' (?:does not exist|not found)"
    r"|semantic_views: '.*' names database '.*', but semantic views are single-catalog",
    re.IGNORECASE,
)
"""
How the ``semantic_views`` extension words a missing view, measured on v0.12.1.

``DESCRIBE SEMANTIC VIEW`` says ``semantic view 'x' does not exist`` (a missing schema
included) and ``semantic_view()`` says ``Semantic view 'x' not found``. A catalog part that
is not the extension's catalog gets ``'x' names database 'y', but semantic views are
single-catalog``: no view by that name can exist there, so it counts as missing too.
"""


def _to_pascal_case(view_name: str) -> str:
    """
    Convert a warehouse view identifier to a PascalCase Python class name.

    Args:
        view_name: Warehouse view identifier, e.g. ``"sales_view"``.

    Returns:
        PascalCase class name; see :func:`~semolina.codegen.introspector.class_name_for`.
    """
    from semolina.codegen.introspector import class_name_for

    return class_name_for(view_name)


def _unquote_identifier(name: str) -> str:
    """
    Strip the double quotes the extension keeps on a field name that was declared quoted.

    ``DESCRIBE SEMANTIC VIEW`` reports ``o."Order Date" AS ...`` as ``"Order Date"``, quotes
    included, while the result columns of ``semantic_view()`` (and so the type lookup and
    every query) use the bare ``Order Date``. A name that is not wrapped in quotes is
    returned unchanged.

    Args:
        name: A field name as ``DESCRIBE SEMANTIC VIEW`` reports it.

    Returns:
        The name without its quotes, with any doubled quote inside it undoubled.
    """
    if len(name) >= 2 and name.startswith('"') and name.endswith('"'):
        return name[1:-1].replace('""', '"')
    return name


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
            view_name: DuckDB semantic view identifier to introspect. A
                schema-qualified name (``"analytics.orders"``) describes that
                schema's view; each segment is quoted, and a pre-quoted segment
                (``'"Order Book"'``) keeps its case.

        Returns:
            Intermediate representation of the view, ready for code rendering.

        Raises:
            SemolinaViewNotFoundError: If the semantic view does not exist
                (wraps an ADBC :class:`~adbc_driver_manager.Error` worded as the
                extension words a missing view).
            SemolinaConnectionError: If the connection fails: an ``OperationalError``
                or ``InterfaceError``, whatever its message.
            SemolinaIntrospectionError: If DuckDB cannot describe the view, for example
                because its definition no longer binds (any other ADBC
                :class:`~adbc_driver_manager.Error`).
            ValueError: If a quoted part of ``view_name`` contains a ``.`` or leaves a
                quote unbalanced.

        Example:
            .. code-block:: python

                from adbc_poolhouse import DuckDBConfig

                from semolina.config import create_engine

                engine = create_engine(DuckDBConfig(database="/path/to/analytics.db"))
                view = engine.introspect("orders")
                for field in view.fields:
                    print(f"{field.name}: {field.field_type} ({field.data_type})")
        """
        from adbc_driver_manager import (
            Error,
            InterfaceError,
            OperationalError,
        )

        from semolina.codegen.introspector import (
            IntrospectedField,
            IntrospectedView,
            with_python_field_names,
        )
        from semolina.codegen.type_map import duckdb_type_to_python

        # DESCRIBE takes an identifier, quoted per segment so a schema prefix selects that
        # schema's view and a name with a space parses. semantic_view() takes the name as a
        # string literal, which the extension resolves the same way, schema and all.
        described = DuckDBDialect().quote_table_name(view_name)

        try:
            with self.connect() as conn:
                cur = conn.cursor()
                # Step 1: Get field structure from DESCRIBE SEMANTIC VIEW
                cur.execute(f"DESCRIBE SEMANTIC VIEW {described}")
                raw_rows = cur.fetchall()
                parsed = _parse_describe_semantic_view(raw_rows)

                # Categorize fields and exclude PRIVATE
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

                view_literal = _sql_str_literal(view_name)

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
                columns: list[str] = []
                for described_name, props in parsed.items():
                    # Skip PRIVATE fields
                    if props.get("access_modifier") == "PRIVATE":
                        continue

                    # DuckDB matches identifiers case-insensitively, so the name keeps its
                    # case and needs no source_name unless python_field_names changes it.
                    field_name = _unquote_identifier(described_name)
                    columns.append(field_name)
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
                    fields=with_python_field_names(fields, columns),
                )

        except (OperationalError, InterfaceError) as e:
            # The driver's type decides first: a connection-level failure is one whatever
            # its message says ("database file not found" is not a missing view).
            msg = f"DuckDB introspection failed: {e}"
            raise SemolinaConnectionError(msg) from e
        except Error as e:
            # DuckDB's ADBC driver reports a missing semantic view as InternalError, the same
            # type as a parse error, with no SQLSTATE. Its message is the only signal, so
            # only the extension's own two wordings count as a missing view.
            message = str(e)
            if _MISSING_VIEW.search(message):
                msg = f"DuckDB semantic view not found: {message}"
                raise SemolinaViewNotFoundError(msg) from e
            msg = f"DuckDB introspection failed: {message}"
            raise SemolinaIntrospectionError(msg) from e
