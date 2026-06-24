"""
Databricks backend engine for metric view introspection.

Provides the DatabricksEngine class. Query execution runs through the
:class:`~semolina.engines.base.Engine` ADBC pool path; this subclass adds
Databricks-specific ``introspect()``.

.. note::
    Databricks ADBC *introspection* is currently UNVALIDATED and ships as a
    marked :class:`NotImplementedError` fallback (Phase 44 / 44-04). The
    Foundry-distributed Databricks ADBC driver (``adbc_driver_databricks``) is
    not on PyPI / not installed, and the Databricks recording hangs on
    warehouse cold-start, so the ``DESCRIBE TABLE EXTENDED ... AS JSON`` path
    has never been run over ADBC. Run
    ``scripts/spike_databricks_adbc_introspect.py`` against a live warehouse
    (with the Foundry driver installed) to validate, then implement the real
    ADBC ``introspect()`` in a follow-up. Query *execution* is unaffected: it
    runs through the inherited :meth:`~semolina.engines.base.Engine.execute`
    ADBC-pool path like the other backends.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from semolina.engines.base import Engine

if TYPE_CHECKING:
    from semolina.codegen.introspector import IntrospectedView


class DatabricksEngine(Engine):
    """
    Databricks backend engine for semantic view queries.

    Built by :func:`semolina.config.create_engine` from a ``DatabricksConfig``;
    it owns one ADBC connection pool (via adbc-poolhouse) plus the Databricks
    dialect, exactly like the Snowflake and DuckDB engines. Query execution runs
    through the :class:`~semolina.engines.base.Engine` pool path
    (:meth:`~semolina.engines.base.Engine.execute`).

    Introspection status:
        :meth:`introspect` is a marked :class:`NotImplementedError` fallback
        (Phase 44 / 44-04). The Foundry-distributed Databricks ADBC driver is
        not installed and the introspection path is unvalidated. See
        ``scripts/spike_databricks_adbc_introspect.py`` to validate the
        ``DESCRIBE TABLE EXTENDED ... AS JSON`` path over ADBC before wiring the
        real implementation.

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
        Introspect a Databricks metric view -- NOT YET IMPLEMENTED over ADBC.

        Databricks introspection runs ``DESCRIBE TABLE EXTENDED {view} AS JSON``
        and is "just SQL", so it very likely works over the engine's owned ADBC
        pool. But it has never actually been run that way: the
        Foundry-distributed Databricks ADBC driver (``adbc_driver_databricks``)
        is not on PyPI / not installed, and the Databricks recording hangs on
        warehouse cold-start (Phase 44 / 44-RESEARCH.md). Rather than ship an
        unvalidated path, this raises :class:`NotImplementedError`.

        To validate and enable: install the Foundry Databricks ADBC driver,
        start a SQL Warehouse with a metric view, and run
        ``scripts/spike_databricks_adbc_introspect.py <schema.metric_view>``.
        Once it reports the ADBC and native results are structurally identical,
        implement the real ADBC path here (mirroring
        :meth:`semolina.engines.snowflake.SnowflakeEngine.introspect`).

        Args:
            view_name: Databricks metric view identifier to introspect.
                Accepts schema-qualified (``schema.view``) and Unity Catalog
                three-part (``catalog.schema.view``) names.

        Returns:
            Never returns -- always raises.

        Raises:
            NotImplementedError: Always. Databricks ADBC introspection is
                pending the Foundry ADBC driver and a live validation spike
                (Phase 44).
        """
        # TODO(Phase 44): Wire Databricks introspect() onto self.connect() once
        # the Foundry Databricks ADBC driver is installed and
        # scripts/spike_databricks_adbc_introspect.py confirms DESCRIBE TABLE
        # EXTENDED ... AS JSON is structurally identical over ADBC vs native.
        # Mirror SnowflakeEngine.introspect: with self.connect() as conn: ...
        # and translate adbc_driver_manager.{ProgrammingError,OperationalError}.
        msg = (
            "Databricks ADBC introspection is not yet implemented: the "
            "Foundry-distributed Databricks ADBC driver is not installed and "
            "the introspection path is unvalidated (Phase 44 / 44-RESEARCH.md). "
            "Run scripts/spike_databricks_adbc_introspect.py against a live "
            "warehouse with the Foundry driver installed to validate "
            f"DESCRIBE TABLE EXTENDED {view_name} AS JSON over ADBC, then "
            "implement the real path."
        )
        raise NotImplementedError(msg)
