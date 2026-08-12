"""
Type-fidelity probes for Snowflake and Databricks, served from copied cassettes.

Everything here replays (incl. CI): no credentials, no warehouse, no network. Nothing
here runs live and nothing here is ever recorded. Both cassettes were **copied** byte for
byte from the ``test_queries`` recordings of ``test_metric_with_dimension``, mirroring the
justification in ``tests/integration/conftest.py`` for the async fixtures — cassette
directories are derived from the pytest node id, so a new test cannot read an existing
test's recording and the directory has to be copied. Re-record the *sources*, never this
module::

    pytest --adbc-record=once tests/integration/test_queries.py

The ``adbc_cassette`` marker is applied **per test** rather than module-wide.
``adbc_auto_patch`` covers ``adbc_driver_manager.dbapi``, which DuckDB also routes
through, so a module-wide marker would silently divert a DuckDB probe added here into
cassette replay *and* normalise its SQL as the Databricks dialect.

**What a passing test here proves, and what it does not.** pytest-adbc-replay implements
``adbc_execute_schema`` by reading the schema off the recorded result table, so it
succeeds regardless of what the real driver does. These assertions are evidence about
Snowflake's and Databricks' *result types*. They are zero evidence about whether either
driver implements ``ExecuteSchema``; that question is answered from driver source in the
artifact's ``## Driver capability`` table.

See docs/src/how-to/warehouse-testing.rst for the full record/replay workflow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from type_fidelity_probe import probe_schema

from semolina import Dimension, Metric, SemanticView

if TYPE_CHECKING:
    from type_fidelity_probe import ProbeResult


class Sales(SemanticView, view="sales_view"):
    """
    Synthetic SemanticView for the type-fidelity probes.

    View name and field set match ``test_queries.py``'s ``Sales`` exactly. That is
    load-bearing: the cassette key is the sqlglot-normalised SQL, so the generated
    statement has to normalise to what was recorded or the copied cassette misses.
    """

    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()


def _probe(engine: Any) -> ProbeResult:
    """
    Probe the recorded query's result schema through the engine's own SQL builder.

    The SQL is built rather than pasted: cassette keys are sqlglot-normalised, so a
    hand-typed string drifts away from the recording the moment the builder changes. The
    query mirrors ``test_queries.test_metric_with_dimension``, which is the test whose
    cassette was copied.

    Args:
        engine: A replay-backed :class:`~semolina.engines.base.Engine`.

    Returns:
        The probed result schema and the route that produced it.
    """
    query = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue)
        .dimensions(Sales.country)
        .order_by(Sales.country)
    )
    sql, params = engine.dialect.create_builder().build_select_with_params(query)

    # The recorded 000_params.json is `[]`, and params are part of the cassette key, so
    # `[]` is passed explicitly below rather than forwarded — `None` would miss.
    assert params == [], f"Probe query gained bind parameters {params!r}; the recording has none"

    with engine.connect() as conn:
        cursor = conn.cursor()
        try:
            return probe_schema(cursor, sql, [])
        finally:
            cursor.close()


def _field_types(probed: ProbeResult) -> dict[str, str]:
    """
    Reduce a probed schema to a field-name -> Arrow-type-name mapping.

    Compared as a mapping rather than field by field so a failure names the offending
    field and both types instead of printing two opaque ``pyarrow.Schema`` reprs.

    Args:
        probed: A probe result.

    Returns:
        Result column name -> the string form of its Arrow type.
    """
    schema: Any = probed.schema
    return {str(field.name): str(field.type) for field in schema}


@pytest.mark.adbc_cassette
def test_snowflake_probe(snowflake_engine: Any) -> None:
    """
    Snowflake's recorded result types: a NUMBER metric arrives as decimal, not as int.

    ``SnowflakeEngine.introspect`` maps this field's ``FIXED``/``scale=0`` metadata to
    ``int``, so the measured ``decimal128(38, 0)`` is the disagreement the artifact
    records. Evidence about result types only — see the module docstring.
    """
    probed = _probe(snowflake_engine)

    assert _field_types(probed) == {'AGG("REVENUE")': "decimal128(38, 0)", "COUNTRY": "string"}
    # Asserted as a literal rather than through ROUTE_EXECUTE_SCHEMA: the artifact's
    # provenance cell carries this exact string, and renaming the constant must not
    # silently rename what the committed evidence claims.
    assert probed.route == "execute-schema"


@pytest.mark.adbc_cassette
def test_databricks_probe(databricks_engine: Any) -> None:
    """
    Databricks' recorded result types, and the claim this test cannot support.

    pytest-adbc-replay serves ``adbc_execute_schema`` from the recorded result table
    whatever the real driver does, so a pass here is evidence about Databricks' **result
    types** and proves nothing about driver capability. The Databricks ADBC driver does
    not implement ``ExecuteSchema`` at all (Foundry ``go/v0.1.3`` embeds
    ``driverbase.StatementImplBase`` and inherits a ``StatusNotImplemented`` default);
    that answer comes from driver source and lives in the artifact's ``## Driver
    capability`` table, never from this replay.

    The measured field name is ``measure(revenue)``, lower-cased and unquoted — the name
    Databricks returned, not the ``MEASURE("revenue")`` spelling that was sent.
    """
    probed = _probe(databricks_engine)

    assert _field_types(probed) == {"measure(revenue)": "int64", "country": "string"}
    assert probed.route == "execute-schema"
