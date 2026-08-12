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

import decimal
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pyarrow
import pytest
from type_fidelity_probe import probe_schema

from semolina import Dimension, Metric, SemanticView

if TYPE_CHECKING:
    from type_fidelity_probe import ProbeResult

REPO_ROOT = Path(__file__).resolve().parents[2]
"""Repository root, two levels above ``tests/integration/``."""


def _cassette_root() -> Path:
    """
    Resolve the plugin's cassette directory from ``pyproject.toml``.

    Read rather than hard-coded so this module and pytest-adbc-replay cannot end up
    reading two different directories: the plugin resolves the replayed half from
    ``adbc_cassette_dir``, and the raw-Arrow half below has to land on the same tree or
    the comparison compares two unrelated recordings.

    Returns:
        The absolute cassette root.
    """
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        config: dict[str, Any] = tomllib.load(handle)
    configured = config["tool"]["pytest"]["ini_options"]["adbc_cassette_dir"]
    return REPO_ROOT / str(configured)


CASSETTE_ROOT = _cassette_root()
"""The cassette tree both halves of this module read, per ``adbc_cassette_dir``."""

SNOWFLAKE_CASSETTE_NAME = "integration/test_type_fidelity/test_snowflake_probe"
"""
Cassette name for the Snowflake recording, as a positional ``adbc_cassette`` argument.

This is the path ``test_snowflake_probe``'s node id derives, which is why the copy landed
there. The later tests in this module replay the *same* recording, and a positional marker
name replaces node-id derivation entirely — the precedent is
``tests/integration/test_async_queries.py``, where one cassette serves both loop backends.
Without it each additional test would derive a directory of its own and demand a duplicate
copy of a recording that is already committed.
"""

DATABRICKS_CASSETTE_NAME = "integration/test_type_fidelity/test_databricks_probe"
"""Cassette name for the Databricks recording; see :data:`SNOWFLAKE_CASSETTE_NAME`."""

SNOWFLAKE_CASSETTE = CASSETTE_ROOT / SNOWFLAKE_CASSETTE_NAME / "adbc_driver_snowflake.dbapi"
"""The copied Snowflake recording, as a filesystem path for the raw-Arrow read."""

DATABRICKS_CASSETTE = (
    CASSETTE_ROOT / DATABRICKS_CASSETTE_NAME / "adbc_driver_manager.dbapi" / "databricks"
)
"""
The copied Databricks recording, as a filesystem path for the raw-Arrow read.

adbc-poolhouse routes Databricks through ``adbc_driver_manager.dbapi``, so this path
carries an extra ``databricks`` dialect segment the Snowflake path does not have.
"""


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
    ``decimal.Decimal`` (47-DECISIONS.md Decision 1), which the measured
    ``decimal128(38, 0)`` agrees with — the disagreement this row once recorded is what
    Phase 48 closed. Evidence about result types only — see the module docstring.
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


# -- The reviewer's bypass check, promoted from a manual procedure into a test ------------
#
# RESEARCH.md's "How a reviewer validates that the comparison is HONEST" ends with step 4:
# spot-check a row against the raw cassette by opening `000_result.arrow` with
# `pyarrow.ipc.open_file`, which bypasses every line of Semolina code — "if that number
# disagrees with the table, the table is fiction". The three tests below run that step
# automatically, so the artifact's Snowflake and Databricks numbers stay checkable without
# a warehouse and without trusting the replay plugin.


def _recorded_table(cassette: Path) -> pyarrow.Table:
    """
    Read a cassette's recorded result table straight off disk.

    Cassettes are Arrow IPC **file** format, so ``open_file`` is correct and
    ``open_stream`` raises ``ArrowInvalid`` on them. Nothing in this path touches
    Semolina, pytest-adbc-replay, or an ADBC driver.

    Args:
        cassette: A cassette directory holding ``000_result.arrow``.

    Returns:
        The recorded table.
    """
    with pyarrow.ipc.open_file(cassette / "000_result.arrow") as reader:
        return reader.read_all()


def _recorded_field_types(cassette: Path) -> dict[str, str]:
    """
    Reduce a recorded table's schema to a field-name -> Arrow-type-name mapping.

    Args:
        cassette: A cassette directory holding ``000_result.arrow``.

    Returns:
        Result column name -> the string form of its Arrow type.
    """
    schema: Any = _recorded_table(cassette).schema
    return {str(field.name): str(field.type) for field in schema}


@pytest.mark.adbc_cassette(SNOWFLAKE_CASSETTE_NAME)
def test_snowflake_replay_schema_matches_raw_arrow_file(snowflake_engine: Any) -> None:
    """The replayed Snowflake schema equals a raw read of the same recording."""
    assert _field_types(_probe(snowflake_engine)) == _recorded_field_types(SNOWFLAKE_CASSETTE)


@pytest.mark.adbc_cassette(DATABRICKS_CASSETTE_NAME)
def test_databricks_replay_schema_matches_raw_arrow_file(databricks_engine: Any) -> None:
    """The replayed Databricks schema equals a raw read of the same recording."""
    assert _field_types(_probe(databricks_engine)) == _recorded_field_types(DATABRICKS_CASSETTE)


def test_recorded_snowflake_values_are_decimal() -> None:
    """
    Snowflake's ``NUMBER`` metric arrives as ``decimal.Decimal``, measured off the file.

    The user-visible consequence of ``decimal128(38, 0)``, obtained without a warehouse and
    without the replay plugin: this test takes no engine fixture and carries no marker, so
    ``to_pylist()`` is the only conversion between the recorded bytes and the assertion.
    """
    rows: list[dict[str, Any]] = _recorded_table(SNOWFLAKE_CASSETTE).to_pylist()
    values = [row['AGG("REVENUE")'] for row in rows]

    assert values, "The recording holds no rows, so nothing here would be measuring anything"
    assert {type(value).__name__ for value in values} == {decimal.Decimal.__name__}
