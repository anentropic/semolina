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
    DOWNSTREAM_CONSUMERS,
    DUCKDB_PROBE_FIELDS,
    EMPTY_GROUP_REGION,
    PROBE_VIEW_NAME,
    STATUS_MEASURED,
    STATUS_NOT_MEASURED,
    describe_raw_types,
    make_probe_engine,
    measure_downstream_decimal,
    measure_empty_group_values,
    probe_sql_all,
    probe_sql_for,
    probe_value_type,
    probe_value_types,
)

# Imported from the shipped module, not through ``type_fidelity_probe``'s re-export. These
# two canaries assert what a released `semolina codegen --check` will run; reaching them
# through the generator would leave the shipped probe untested by name, and a future
# re-definition in the test tree would pass here while the shipped code rotted.
from semolina.codegen.probe import NOT_IMPLEMENTED_ERRORS, probe_schema

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

HAND_WRITTEN_SUM = "SELECT SUM(order_count) AS total_order_count FROM type_fidelity_orders"
"""
The contrast query for :func:`test_semantic_view_path_differs_from_hand_written_sum`.

This is the *only* hand-written aggregate in the module. It is the labelled contrast case,
never the measured path.
"""


def _arrow_type(cursor: Any, field_name: str) -> str:
    """
    Probe the Arrow type of one field of the full ``semantic_view(...)`` query.

    Compared against literal strings by every caller. Nothing normalises or rounds the type
    first: ``decimal128(38, 2)`` and ``decimal128(10, 2)`` differing is the measurement, and a
    helper that collapsed them would erase the finding rather than tidy it.

    Args:
        cursor: A live ADBC cursor on the probe engine.
        field_name: A field of ``type_fidelity_view``.

    Returns:
        The Arrow type, rendered exactly as ``pyarrow`` renders it.
    """
    sql, params = probe_sql_all()
    return str(probe_schema(cursor, sql, params).schema.field(field_name).type)


def _value_type(cursor: Any, field_name: str) -> str:
    """
    Probe the Python type one field's values arrive as, through the full query.

    Args:
        cursor: A live ADBC cursor on the probe engine.
        field_name: A field of ``type_fidelity_view``.

    Returns:
        The Python type name, module-qualified unless it is a builtin.
    """
    sql, params = probe_sql_all()
    return probe_value_types(cursor, sql, params)[field_name]


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


class _RecordingCursor:
    """Captures the SQL a helper would run, with no warehouse behind it."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, sql: str) -> None:
        """
        Record a statement instead of running it.

        Args:
            sql: The statement the helper built.
        """
        self.statements.append(sql)

    def fetchall(self) -> list[tuple[str, str]]:
        """
        Return no rows.

        Returns:
            An empty result set.
        """
        return []


def test_semantic_view_needs_at_least_one_field_list(probe_cursor: Any) -> None:
    """
    DuckDB rejects a `semantic_view()` call carrying no field list, by either spelling.

    Measured rather than assumed, because it is the reason
    :func:`describe_raw_types` raises on an empty request instead of tidying the trailing
    comma away. Dropping the comma does not produce a working statement — it only trades a
    parser error for a binder error, several layers from the caller that asked for nothing.
    """
    from adbc_driver_manager import Error as AdbcError

    with pytest.raises(AdbcError, match="syntax error"):
        probe_cursor.execute(f"DESCRIBE SELECT * FROM semantic_view('{PROBE_VIEW_NAME}', )")

    with pytest.raises(AdbcError, match="specify at least"):
        probe_cursor.execute(f"DESCRIBE SELECT * FROM semantic_view('{PROBE_VIEW_NAME}')")


def test_describe_raw_types_refuses_an_empty_field_request() -> None:
    """
    Asking for neither dimensions nor metrics raises here, rather than emitting broken SQL.

    The interpolation used to fall through to `semantic_view('view', )` — a trailing comma
    immediately before the closing paren. Unreachable from ``measure_duckdb``, which always
    passes both lists, but this is a general-purpose helper and the failure would have
    surfaced as a DuckDB parser error naming a paren rather than as the caller's mistake.
    """
    cursor = _RecordingCursor()

    with pytest.raises(ValueError, match="dimensions"):
        _ = describe_raw_types(cursor, PROBE_VIEW_NAME, [], [])

    assert cursor.statements == [], (
        f"describe_raw_types should have run no SQL, it ran {cursor.statements}"
    )


def test_not_implemented_errors_are_real_classes() -> None:
    """The fallback's except clause names real exception classes, not an assumed one."""
    assert NOT_IMPLEMENTED_ERRORS, "The fallback would never fire with an empty tuple"
    for candidate in NOT_IMPLEMENTED_ERRORS:
        assert isinstance(candidate, type), f"{candidate!r} is not a class"
        assert issubclass(candidate, Exception), f"{candidate!r} is not an exception class"


# -- The four named disagreements, each asserted on its exact measured literal -------------


def test_sum_decimal_widens_to_38(probe_cursor: Any) -> None:
    """Disagreement 1: SUM over DECIMAL(10, 2) resolves to a decimal widened to precision 38."""
    assert _arrow_type(probe_cursor, "total_order_value") == "decimal128(38, 2)"
    assert _value_type(probe_cursor, "total_order_value") == "decimal.Decimal"


def test_max_decimal_does_not_widen(probe_cursor: Any) -> None:
    """
    Disagreement 1's contrast: MAX over the same column keeps the source precision.

    Widening is specific to accumulating aggregates. Two aggregates reading one input column
    do not collapse into a single result type, so a type map keyed on the column would get one
    of this pair wrong whichever precision it picked.
    """
    assert _arrow_type(probe_cursor, "max_order_value") == "decimal128(10, 2)"
    assert _value_type(probe_cursor, "max_order_value") == "decimal.Decimal"


def test_avg_int_is_double(probe_cursor: Any) -> None:
    """Disagreement 2: AVG over an INTEGER column leaves the integer domain for a double."""
    assert _arrow_type(probe_cursor, "avg_order_count") == "double"
    assert _value_type(probe_cursor, "avg_order_count") == "float"


def test_count_is_int64_and_never_null(probe_engine: Engine, probe_cursor: Any) -> None:
    """Disagreement 3: COUNT is int64, and returns 0 rather than NULL on an empty group."""
    assert _arrow_type(probe_cursor, "n_order_totals") == "int64"
    assert _value_type(probe_cursor, "n_order_totals") == "int"

    empty_group = measure_empty_group_values(probe_engine)
    assert empty_group["n_order_totals"] == 0
    assert empty_group["n_order_totals"] is not None


def test_min_int_is_int32(probe_cursor: Any) -> None:
    """
    Disagreement 3's contrast: MIN over an INTEGER column is int32, not int64.

    So "integer metric" is not one Arrow type, and the probe has to record the exact width
    rather than a normalised "integer".
    """
    assert _arrow_type(probe_cursor, "min_order_count") == "int32"
    assert _value_type(probe_cursor, "min_order_count") == "int"


def test_empty_group_nullability_is_not_uniform(probe_engine: Engine) -> None:
    """
    Disagreement 4: on an all-NULL group, four aggregates go NULL and COUNT returns 0.

    A blanket ``T | None`` over every metric would be wrong for COUNT; a blanket ``T`` would
    be wrong for the other four. The Arrow ``nullable`` flag cannot distinguish them — see
    :func:`test_arrow_nullable_flag_is_uninformative` — so the answer comes from observed
    values on the ``CA`` group instead.
    """
    empty_group = measure_empty_group_values(probe_engine)

    for name in ("total_order_value", "max_order_value", "avg_order_count", "min_order_count"):
        assert empty_group[name] is None, (
            f"{name} should go NULL on the {EMPTY_GROUP_REGION} group, got {empty_group[name]!r}"
        )

    assert empty_group["n_order_totals"] == 0
    assert empty_group["n_order_totals"] is not None


def test_semantic_view_path_differs_from_hand_written_sum(probe_cursor: Any) -> None:
    """
    The measured path must be ``semantic_view(...)``, never a hand-written aggregate.

    Plain DuckDB sums an ``INTEGER`` column into a ``HUGEINT``, which pyarrow renders as
    ``decimal128(38, 0)`` and converts to ``decimal.Decimal``. The ``semantic_views``
    extension casts that result down to ``int64``, so the user receives an ``int``. Probing
    outside ``semantic_view(...)`` would therefore report a type users never receive, and
    both halves are asserted here so the trap is encoded rather than described.
    """
    assert _arrow_type(probe_cursor, "total_order_count") == "int64"
    assert _value_type(probe_cursor, "total_order_count") == "int"

    hand_written = probe_schema(probe_cursor, HAND_WRITTEN_SUM, [])
    assert str(hand_written.schema.field("total_order_count").type) == "decimal128(38, 0)"
    assert (
        probe_value_type(probe_cursor, HAND_WRITTEN_SUM, [], "total_order_count")
        == "decimal.Decimal"
    )


def test_arrow_nullable_flag_is_uninformative(probe_cursor: Any) -> None:
    """
    Every probed field reports nullable=True, COUNT included, so the flag carries no signal.

    This is why no acceptance criterion in this phase is built on the Arrow ``nullable``
    flag: ``n_order_totals`` demonstrably never returns NULL and still reports True.
    Nullability is a policy call, not a measurement.
    """
    sql, params = probe_sql_all()
    schema = probe_schema(probe_cursor, sql, params).schema

    flags = {name: schema.field(name).nullable for name in DUCKDB_PROBE_FIELDS}

    assert flags["n_order_totals"] is True
    assert all(flags.values()), f"Expected every field nullable, got {flags}"


def test_downstream_decimal_measurements_are_recorded() -> None:
    """
    Every downstream consumer is accounted for, and an unmeasured one says which package.

    Deliberately not gated on ``pytest.importorskip``. The point of the section is that a
    missing package produces an honest artifact row rather than a skipped test and a silent
    gap, so the test has to run in both environments and check the shape of the answer rather
    than assume a package is there.
    """
    observations = measure_downstream_decimal()

    assert set(observations) == set(DOWNSTREAM_CONSUMERS)

    for consumer, row in observations.items():
        assert row.status in {STATUS_MEASURED, STATUS_NOT_MEASURED}, (
            f"{consumer} has status {row.status!r}, which the artifact renders verbatim"
        )
        if row.status == STATUS_NOT_MEASURED:
            assert consumer in row.observed, (
                f"{consumer} is unmeasured but its reason {row.observed!r} does not name it"
            )

    # to_pylist is the one consumer that cannot be absent -- it is pyarrow's own conversion,
    # and it is what semolina.cursor calls, so the Decimal policy turns on it directly.
    assert observations["to_pylist"].status == STATUS_MEASURED
    assert observations["to_pylist"].observed == "`decimal.Decimal`"
