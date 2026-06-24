"""
Abstract base class for backend engines.

Defines the SQLAlchemy-style ``Engine`` that owns one adbc-poolhouse
connection pool plus its derived dialect, for all backends (Snowflake,
Databricks, DuckDB). ``connect()`` checks an ADBC connection out of the
owned pool; ``execute()`` runs the builder + cursor path through it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from semolina.codegen.introspector import IntrospectedView
    from semolina.cursor import SemolinaCursor
    from semolina.engines.sql import Dialect
    from semolina.query import _Query


class SemolinaViewNotFoundError(RuntimeError):
    """Raised when the requested semantic view does not exist in the warehouse."""


class SemolinaConnectionError(RuntimeError):
    """Raised when the engine cannot connect to or authenticate with the warehouse."""


class Engine(ABC):
    """
    SQLAlchemy-style engine owning one ADBC pool plus its derived dialect.

    An ``Engine`` is the single handle used for both query execution and
    semantic-view introspection (codegen). It owns exactly one adbc-poolhouse
    pool and the :class:`~semolina.engines.sql.Dialect` derived from the
    config type. ``connect()`` checks an ADBC connection out of the owned pool
    (the SQLAlchemy ``Engine.connect()`` parallel); ``execute()`` builds the
    dialect-specific SQL and runs it through a pooled connection, returning a
    :class:`~semolina.cursor.SemolinaCursor`.

    Engines are constructed via :func:`semolina.config.create_engine`, which
    selects the right subclass and supplies the pool and dialect. Subclasses
    implement only backend-specific :meth:`introspect`.

    Each Engine:
    - Owns one ADBC connection pool and its dialect
    - Executes queries through the owned pool via ``SemolinaCursor``
    - Introspects semantic views into an intermediate representation

    Example:
        .. code-block:: python

            from adbc_poolhouse import SnowflakeConfig

            from semolina.config import create_engine

            engine = create_engine(SnowflakeConfig(account="xy12345", user="u"))
            view = engine.introspect("my_schema.sales_view")

    See Also:
        - semolina.config.create_engine: Builds an Engine from a config or name
        - semolina.engines.sql.Dialect: Backend-specific SQL generation rules
        - semolina.engines.sql.SnowflakeDialect: Snowflake-specific dialect
        - semolina.engines.sql.DatabricksDialect: Databricks-specific dialect
        - semolina.engines.sql.DuckDBDialect: DuckDB-specific dialect
    """

    def __init__(self, *, pool: Any, dialect: Dialect, config: Any = None) -> None:
        """
        Store the owned ADBC pool, its derived dialect, and the source config.

        Args:
            pool: The adbc-poolhouse connection pool this engine owns. Typed as
                ``Any`` because the poolhouse/SQLAlchemy pool surface is untyped.
            dialect: Concrete :class:`~semolina.engines.sql.Dialect` selected
                from the config type by :func:`semolina.config.create_engine`.
            config: The adbc-poolhouse warehouse config the pool was built from
                (``SnowflakeConfig`` etc.). Held so introspectors can read
                connection metadata (e.g. the Snowflake database for view-name
                qualification) without re-reading the TOML. Typed as ``Any``
                because the union of poolhouse config classes is untyped here.
        """
        self._pool = pool
        self.dialect = dialect
        self._config = config

    def connect(self) -> Any:
        """
        Check an ADBC connection out of the owned pool.

        The SQLAlchemy ``Engine.connect()`` parallel: returns a pooled
        connection (a context manager) that is returned to the pool on close.

        Returns:
            An ADBC DBAPI connection checked out of the owned pool. Typed as
            ``Any`` because the poolhouse/ADBC connection surface is untyped.
        """
        return self._pool.connect()

    def execute(self, query: _Query) -> SemolinaCursor:
        """
        Execute a query through the owned pool and return a cursor.

        Builds dialect-specific parameterised SQL, checks an ADBC connection
        out of the owned pool, executes the statement, and wraps the resulting
        cursor in a :class:`~semolina.cursor.SemolinaCursor` (passing the live
        connection and owning pool so Arrow allocators are released on checkin).

        Args:
            query: ``_Query`` object to execute. Must be valid for execution
                (has metrics and/or dimensions).

        Returns:
            A :class:`~semolina.cursor.SemolinaCursor` wrapping the post-execute
            ADBC cursor. Use ``fetchall_rows()`` for Row objects or
            ``fetchall()`` for raw tuples.

        Raises:
            ValueError: If query is invalid for execution.
            Exception: For backend execution errors (connection failures, SQL
                errors) surfaced by the underlying ADBC driver.

        Example:
            .. code-block:: python

                with engine.execute(query) as cursor:
                    for row in cursor.fetchall_rows():
                        print(row["country"], row["revenue"])
        """
        from semolina.cursor import SemolinaCursor

        builder = self.dialect.create_builder()
        sql, params = builder.build_select_with_params(query)

        conn = self.connect()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
        except BaseException:
            # Return the checked-out connection to the pool before propagating.
            # Otherwise (cursor()/execute() failures, or cancellation) the slot
            # is leaked, since checkin normally happens only via
            # SemolinaCursor.close() on the success path. Mirrors
            # SemolinaCursor.close()'s ``self._conn.close()``.
            conn.close()
            raise

        return SemolinaCursor(cur, conn, self._pool)

    @abstractmethod
    def introspect(self, view_name: str) -> IntrospectedView:
        """
        Introspect a semantic view and return its intermediate representation.

        Queries the warehouse metadata API to discover the fields (metrics,
        dimensions, facts) defined on the named semantic view. The returned
        ``IntrospectedView`` is consumed by the Python code renderer to generate
        a SemanticView subclass.

        Args:
            view_name: Warehouse identifier for the semantic view to introspect
                (e.g., ``'sales_view'``). Must exist in the warehouse.

        Returns:
            ``IntrospectedView`` containing the view name, derived class name,
            and all discovered fields with their types and descriptions.

        Raises:
            NotImplementedError: If the engine does not support introspection.
            RuntimeError: For backend-specific errors (connection failures,
                view not found, insufficient permissions, etc.).

        Example:
            .. code-block:: python

                view = engine.introspect("sales_view")
                # IntrospectedView(view_name='sales_view', class_name='Sales', ...)
        """
        pass
