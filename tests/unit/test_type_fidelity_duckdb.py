"""
The DuckDB half of the type-fidelity probe: introspection, result schema and value type agree.

What DuckDB itself does with each aggregate (``SUM`` widening a decimal, ``AVG`` returning a
double) was measured in Phase 47 and is recorded in its artifact; it is not re-asserted here,
because those tests failed on a DuckDB upgrade whether or not Semolina was affected.

Record/replay contract: this module runs **live, in-process**, against an in-memory DuckDB.
It records nothing and replays nothing, and it must never carry
``pytest.mark.adbc_cassette``. ``adbc_auto_patch`` in ``pyproject.toml`` lists
``adbc_driver_manager.dbapi``, which DuckDB also routes through, and ``adbc_dialect`` maps
that same module to the ``databricks`` sqlglot dialect — so a marked DuckDB test would be
diverted into cassette replay *and* have its SQL normalized as Databricks.
:func:`test_probe_runs_live_not_replayed` is the runtime guard against that happening by
accident; it reads the cursor class at runtime rather than grepping for a marker, because a
textual check breaks the moment a docstring explains the rule.

The canary here is asserted **by value**, not by "the two differ". A comparison that cannot
produce a mismatch is not measuring anything, so if a future refactor ever routes the
introspection column and the result column through one source, these literals stop agreeing
with reality and the test goes red.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from type_fidelity_probe import (
    PROBE_VIEW_NAME,
    make_probe_engine,
    probe_sql_for,
    probe_value_type,
)

# Imported from the shipped module, not through ``type_fidelity_probe``'s re-export. These
# two canaries assert what a released `semolina codegen --check` will run; reaching them
# through the generator would leave the shipped probe untested by name, and a future
# re-definition in the test tree would pass here while the shipped code rotted.
from semolina.codegen.probe import probe_schema

if TYPE_CHECKING:
    from collections.abc import Generator

    from semolina.engines.base import Engine

pytest.importorskip("adbc_driver_duckdb")

PROBE_FIELD = "total_order_value"
"""The decimal metric whose three columns Phase 48 brought into agreement."""

UNMAPPED_PROBE_FIELD = "region_list"
"""
A metric whose warehouse type the type map still has no entry for.

Phase 48 gave `_DUCKDB_TYPE_MAP` a `DECIMAL` key, which is the success condition for that
phase and which makes :data:`PROBE_FIELD`'s three columns agree. The circularity guard needs
a field where they still do not, or it degenerates into asserting that two columns sourced
from one place are equal — which is what
:func:`test_an_unmapped_type_still_disagrees_by_value` exists to rule out. `region_list` is
a `list(o.region)` aggregate, described as `VARCHAR[]`, and no plan in Phase 48 maps a
container type. Its positive twin, :func:`test_decimal_metric_agrees_by_value`, keeps the
other half of the story committed.
"""


@pytest.fixture
def probe_engine() -> Generator[Engine, None, None]:
    """
    Yield the probe's own in-memory DuckDB engine, closing its pool on teardown.

    Mirrors the register/unregister/close symmetry of ``tests/conftest.py``'s
    ``duckdb_pool``, minus the registry step: the probe never resolves an engine by name.
    """
    from adbc_poolhouse import close_pool

    engine = make_probe_engine()
    yield engine
    close_pool(engine._pool)


@pytest.fixture
def probe_cursor(probe_engine: Engine) -> Generator[Any, None, None]:
    """Yield a live ADBC cursor on the probe engine's pool."""
    with probe_engine.connect() as conn:
        cursor = conn.cursor()
        yield cursor
        cursor.close()


def test_an_unmapped_type_still_disagrees_by_value(probe_engine: Engine, probe_cursor: Any) -> None:
    """Introspection, the result schema, and the value type disagree by named literals."""
    view = probe_engine.introspect(PROBE_VIEW_NAME)
    by_name = {field.name: field for field in view.fields}

    # Metadata half: the type map has no VARCHAR[] entry, so codegen emits a TODO annotation.
    assert by_name[UNMAPPED_PROBE_FIELD].data_type == "TODO: VARCHAR[]"

    # Result half: the warehouse resolves list(VARCHAR) to an Arrow list of strings.
    sql, params = probe_sql_for(UNMAPPED_PROBE_FIELD)
    probed = probe_schema(probe_cursor, sql, params)
    assert str(probed.schema.field(UNMAPPED_PROBE_FIELD).type) == "list<l: string>"

    # What the user actually receives, via the same to_pylist() call semolina.cursor makes.
    assert probe_value_type(probe_cursor, sql, params, UNMAPPED_PROBE_FIELD) == "list"


def test_decimal_metric_agrees_by_value(probe_engine: Engine, probe_cursor: Any) -> None:
    """Introspection, the result schema, and the value type now agree for the decimal metric."""
    view = probe_engine.introspect(PROBE_VIEW_NAME)
    by_name = {field.name: field for field in view.fields}

    # Metadata half: Decision 1 gave the type map a DECIMAL entry, so the TODO is gone.
    assert by_name[PROBE_FIELD].data_type == "decimal.Decimal"

    # Result half: the warehouse resolves SUM(DECIMAL(10,2)) to a widened decimal128.
    sql, params = probe_sql_for(PROBE_FIELD)
    probed = probe_schema(probe_cursor, sql, params)
    assert str(probed.schema.field(PROBE_FIELD).type) == "decimal128(38, 2)"

    # What the user actually receives, via the same to_pylist() call semolina.cursor makes.
    assert probe_value_type(probe_cursor, sql, params, PROBE_FIELD) == "decimal.Decimal"


def test_probe_runs_live_not_replayed(probe_cursor: Any) -> None:
    """The probe's cursor is a real driver cursor, not a pytest-adbc-replay stand-in."""
    module = type(probe_cursor).__module__

    assert not module.startswith("pytest_adbc_replay"), (
        f"The DuckDB probe is being served by cassette replay (cursor from {module}). "
        "Remove the adbc_cassette marker from this module."
    )


def test_zero_row_fallback_matches_execute_schema(probe_cursor: Any) -> None:
    """
    Both probe routes resolve the same schema for the same query.

    A canary for a Semolina decision, not a test of Semolina code: ``probe_schema`` falls
    back to a zero-row execution when a driver refuses ``ExecuteSchema`` (Databricks always
    does), and reports either route's answer as the result schema. That is only sound while
    the two agree, and DuckDB is the one driver here that answers both ways.
    """
    sql, params = probe_sql_for(PROBE_FIELD)

    direct = probe_cursor.adbc_execute_schema(sql, params)

    probe_cursor.execute(f"SELECT * FROM ({sql}) WHERE 1=0", params or None)
    reader = probe_cursor.fetch_record_batch()
    try:
        fallback = reader.schema
    finally:
        reader.close()

    assert direct.equals(fallback), (
        f"adbc_execute_schema gave {direct} but the zero-row route gave {fallback}"
    )


# -- The four named disagreements, each asserted on its exact measured literal -------------
