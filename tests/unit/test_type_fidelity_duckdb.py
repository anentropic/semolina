"""
Canary tests for the DuckDB half of the type-fidelity probe.

Record/replay contract: this module runs **live, in-process**, against an in-memory DuckDB.
It records nothing and replays nothing, and it must never carry
``pytest.mark.adbc_cassette``. ``adbc_auto_patch`` in ``pyproject.toml`` lists
``adbc_driver_manager.dbapi``, which DuckDB also routes through, and ``adbc_dialect`` maps
that same module to the ``databricks`` sqlglot dialect — so a marked DuckDB test would be
diverted into cassette replay *and* have its SQL normalised as Databricks.
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
    NOT_IMPLEMENTED_ERRORS,
    PROBE_VIEW_NAME,
    make_probe_engine,
    probe_schema,
    probe_sql_for,
    probe_value_type,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from semolina.engines.base import Engine

pytest.importorskip("adbc_driver_duckdb")

PROBE_FIELD = "total_order_value"


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


def test_decimal_metric_disagrees_by_value(probe_engine: Engine, probe_cursor: Any) -> None:
    """Introspection, the result schema, and the value type disagree by named literals."""
    view = probe_engine.introspect(PROBE_VIEW_NAME)
    by_name = {field.name: field for field in view.fields}

    # Metadata half: the type map has no DECIMAL entry, so codegen emits a TODO annotation.
    assert by_name[PROBE_FIELD].data_type == "TODO: DECIMAL(38,2)"

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
    """Both probe routes resolve the same schema for the same query."""
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


def test_not_implemented_errors_are_real_classes() -> None:
    """The fallback's except clause names real exception classes, not an assumed one."""
    assert NOT_IMPLEMENTED_ERRORS, "The fallback would never fire with an empty tuple"
    for candidate in NOT_IMPLEMENTED_ERRORS:
        assert isinstance(candidate, type), f"{candidate!r} is not a class"
        assert issubclass(candidate, Exception), f"{candidate!r} is not an exception class"
