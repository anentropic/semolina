"""
The annotation contract, proved by measurement rather than by inspection.

Every annotation Phase 48 writes into the type map is a claim about what a user's ``Row``
actually holds. This module executes that claim: for each mapped type it obtains a real
value — live from DuckDB, or from a committed cassette for Snowflake and Databricks — and
asserts ``isinstance(value, annotated_type)``.

``isinstance`` rather than a type-name comparison is deliberate. It lets a sound
over-approximation pass (a ``TIMESTAMP_NS`` value is a ``pandas.Timestamp``, which subclasses
``datetime.datetime``) while still failing an annotation that names a type the value simply is
not. A string comparison would reject the first and is the reason a "does the annotation match
the value?" check had previously to be argued rather than run.

Record/replay contract: the DuckDB half runs **live, in-process** against an in-memory DuckDB
and must never carry ``pytest.mark.adbc_cassette`` — see the module docstring of
``tests/unit/test_type_fidelity_duckdb.py`` for why a marker here would silently divert the
probe into replay. The Snowflake and Databricks halves read committed cassette *files*
directly with ``pyarrow.ipc.open_file``; they drive no driver and need no marker either.

What this module cannot cover is recorded in ``## Evidence limitations`` of
``47-TYPE-FIDELITY.md`` and in ``.planning/WINDOWS.md``: there is no Databricks decimal column
and no interval column of any kind in any recording in this repo.
"""

from __future__ import annotations

import builtins
import importlib
import json
from typing import TYPE_CHECKING, Any

import pyarrow
import pytest
from type_fidelity_probe import (
    DATABRICKS_FIELD_SOURCES,
    DATABRICKS_INTROSPECT_CASSETTE,
    DATABRICKS_PROBE_CASSETTE,
    SNOWFLAKE_DERIVED_METADATA,
    SNOWFLAKE_PROBE_CASSETTE,
    make_probe_engine,
    probe_values,
)

from semolina.codegen.type_map import (
    databricks_type_to_python,
    duckdb_type_to_python,
    snowflake_json_type_to_python,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from semolina.engines.base import Engine

pytest.importorskip("adbc_driver_duckdb")

CONTRACT_TABLE = "annotation_contract"
"""Table carrying one column per type in the Phase 48 annotation contract."""

CONTRACT_TABLE_DDL = f"""
CREATE TABLE {CONTRACT_TABLE} (
    c_decimal DECIMAL(10, 2),
    c_hugeint HUGEINT,
    c_uuid UUID,
    c_json JSON,
    c_enum mood,
    c_timestamp TIMESTAMP,
    c_timestamp_s TIMESTAMP_S,
    c_timestamp_ms TIMESTAMP_MS,
    c_timestamp_ns TIMESTAMP_NS,
    c_timestamptz TIMESTAMPTZ,
    c_interval INTERVAL
)
"""
"""
One column per contract row, declared with the DDL spelling a user would write.

``c_enum`` uses a named ENUM type created separately, because DuckDB has no inline ENUM
column syntax.
"""

CONTRACT_ENUM_DDL = "CREATE TYPE mood AS ENUM ('sad', 'ok', 'happy')"
"""The named ENUM the contract table's ``c_enum`` column is declared with."""

CONTRACT_SEED_DML = f"""
INSERT INTO {CONTRACT_TABLE} VALUES (
    123.45,
    170141183460469231731687303715884105727,
    '550e8400-e29b-41d4-a716-446655440000',
    '{{"a": 1}}',
    'ok',
    TIMESTAMP '2024-01-01 12:00:00',
    TIMESTAMP '2024-01-01 12:00:00',
    TIMESTAMP '2024-01-01 12:00:00',
    TIMESTAMP '2024-01-01 12:00:00',
    TIMESTAMPTZ '2024-01-01 12:00:00+00',
    INTERVAL 1 DAY
)
"""
"""
A single all-non-NULL row.

``c_hugeint`` carries HUGEINT's maximum so the value cannot be mistaken for something an
``int`` annotation would have described adequately by accident. Every timestamp is a whole
second: a ``TIMESTAMP_NS`` value carrying sub-microsecond precision raises ``ValueError`` in
``pyarrow`` when pandas is absent (24.0.0, ``scalar.pxi:706-725``), and this module asserts an
annotation, not that anyone has pandas installed.
"""

INTERVAL_XFAIL_REASON = (
    "D-06 / WINDOWS.md entry 6: _DUCKDB_TYPE_MAP['INTERVAL'] is 'datetime.timedelta' and the "
    "measured value is a pyarrow.MonthDayNano. Known wrong and deliberately unfixed — no "
    "stdlib type describes MonthDayNano. strict=True so that fixing the map turns this into a "
    "failure and forces the row to be updated rather than leaving a stale expectation."
)
"""Why the INTERVAL row is an expected failure rather than an excluded one."""


def resolve_annotation(annotation: str) -> type:
    """
    Resolve an annotation string produced by the type map to the class it names.

    Handles the two shapes the maps emit: a builtin (``'str'``) and a module-qualified name
    (``'decimal.Decimal'``). Nothing here consults the type map, so a wrong annotation cannot
    resolve to the type of the value that would excuse it.

    Args:
        annotation: An annotation string, exactly as a type map returned it.

    Returns:
        The class the annotation names.

    Raises:
        AssertionError: If the annotation names nothing importable, which would mean the map
            emits an annotation a generated module could not resolve either.
    """
    module_name, _, attribute = annotation.rpartition(".")
    module = importlib.import_module(module_name) if module_name else builtins

    resolved: object = getattr(module, attribute, None)
    assert isinstance(resolved, type), (
        f"Annotation {annotation!r} does not name an importable type; a generated model "
        f"carrying it would raise NameError."
    )
    return resolved


def read_cassette_values(cassette_dir: Any) -> dict[str, object]:
    """
    Read a committed cassette's recorded values, one per column.

    Mirrors :func:`type_fidelity_probe.probe_values` over recorded data rather than a live
    cursor, so a recorded field and a live one are read the same way. Cassettes are Arrow IPC
    *file* format, so ``open_file`` is correct.

    Args:
        cassette_dir: A cassette directory holding ``000_result.arrow``.

    Returns:
        Field name -> its first non-NULL recorded value, or ``None`` when every value is NULL.
    """
    with pyarrow.ipc.open_file(cassette_dir / "000_result.arrow") as reader:
        table = reader.read_all()

    rows: list[dict[str, Any]] = table.to_pylist()
    values: dict[str, object] = {}
    for name in table.column_names:
        values[str(name)] = None
        for row in rows:
            value = row.get(name)
            if value is not None:
                values[str(name)] = value
                break
    return values


@pytest.fixture(scope="module")
def contract_engine() -> Generator[Engine, None, None]:
    """
    Yield an in-memory DuckDB engine carrying the contract table.

    Built through ``type_fidelity_probe.make_probe_engine`` rather than a second engine
    builder: that function already owns the ``pool_size=1`` mitigation for adbc-poolhouse's
    per-connection database clone, which a fresh in-memory DuckDB per checkout would
    otherwise make this fixture's table vanish from.
    """
    from adbc_poolhouse import close_pool

    engine = make_probe_engine()
    yield engine
    close_pool(engine._pool)


@pytest.fixture(scope="module")
def duckdb_contract(contract_engine: Engine) -> dict[str, tuple[str, object]]:
    """
    Measure every contract column: the raw DuckDB type, and the value it arrives as.

    Both halves come from one connection and one row, so the type string a column is mapped
    by and the value that mapping is judged against cannot describe different data.

    Args:
        contract_engine: The in-memory DuckDB engine.

    Returns:
        Column name -> (the ``DESCRIBE`` type string, the value ``to_pylist()`` produced).
    """
    with contract_engine.connect() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(CONTRACT_ENUM_DDL)
            cursor.execute(CONTRACT_TABLE_DDL)
            cursor.execute(CONTRACT_SEED_DML)

            # The DESCRIBE string is what duckdb_type_to_python actually receives from
            # DuckDBEngine.introspect — read it rather than restating the DDL, so a
            # divergence between the two spellings shows up here instead of in a user's model.
            cursor.execute(f"DESCRIBE SELECT * FROM {CONTRACT_TABLE}")
            raw_types = {str(row[0]): str(row[1]) for row in cursor.fetchall()}

            values = probe_values(cursor, f"SELECT * FROM {CONTRACT_TABLE}", [])
        finally:
            cursor.close()

    return {name: (raw_types[name], values[name]) for name in raw_types}


DUCKDB_CONTRACT_COLUMNS = [
    "c_decimal",
    "c_hugeint",
    "c_uuid",
    "c_json",
    "c_enum",
    "c_timestamp",
    "c_timestamp_s",
    "c_timestamp_ms",
    "c_timestamp_ns",
    "c_timestamptz",
    pytest.param("c_interval", marks=pytest.mark.xfail(strict=True, reason=INTERVAL_XFAIL_REASON)),
]
"""
Every contract column, INTERVAL included.

INTERVAL is an ``xfail``, never an exclusion. Excluding a row is how it stayed wrong through
two phases without anything going red.
"""


@pytest.mark.parametrize("column", DUCKDB_CONTRACT_COLUMNS)
def test_duckdb_annotation_describes_the_measured_value(
    column: str, duckdb_contract: dict[str, tuple[str, object]]
) -> None:
    """The DuckDB annotation names a type the live measured value is an instance of."""
    raw_type, value = duckdb_contract[column]
    annotation = duckdb_type_to_python(raw_type)

    assert annotation is not None, (
        f"{column} ({raw_type}) is part of the Phase 48 contract but the type map still "
        f"returns None for it, so a generated model would carry a TODO."
    )
    assert value is not None, f"{column} measured as NULL, which says nothing about its type"

    assert isinstance(value, resolve_annotation(annotation)), (
        f"{column}: DuckDB reports {raw_type!r}, the type map annotates it {annotation!r}, "
        f"but the measured value is a {type(value).__module__}.{type(value).__qualname__}."
    )


def test_duckdb_contract_covers_every_measured_column(
    duckdb_contract: dict[str, tuple[str, object]],
) -> None:
    """
    Every column of the contract table is parametrized — none was quietly dropped.

    The guard against fixing a red row by deleting it from
    :data:`DUCKDB_CONTRACT_COLUMNS` while leaving the column in the table.
    """
    parametrized = {
        column if isinstance(column, str) else str(column.values[0])
        for column in DUCKDB_CONTRACT_COLUMNS
    }

    assert parametrized == set(duckdb_contract), (
        f"Contract table columns {sorted(set(duckdb_contract) - parametrized)} are measured "
        f"but not asserted on."
    )


def test_duckdb_contract_runs_live_not_replayed(contract_engine: Engine) -> None:
    """The contract measurement uses a real driver cursor, not a cassette stand-in."""
    with contract_engine.connect() as conn:
        cursor = conn.cursor()
        module = type(cursor).__module__
        cursor.close()

    assert not module.startswith("pytest_adbc_replay"), (
        f"The annotation contract is being served by cassette replay (cursor from {module}). "
        "Remove the adbc_cassette marker from this module."
    )


@pytest.mark.parametrize("field_name", sorted(SNOWFLAKE_DERIVED_METADATA))
def test_snowflake_annotation_describes_the_recorded_value(field_name: str) -> None:
    """
    The Snowflake annotation names a type the recorded value is an instance of.

    Asymmetric evidence, and the asymmetry is stated rather than hidden: the value comes from
    a committed recording, while the ``FIXED``/``TEXT`` descriptor it is mapped from is
    derived from the recording fixture's DDL, because no Snowflake introspection cassette
    exists anywhere in this repo. The hand-fed mock in ``tests/unit/test_snowflake_engine.py``
    is deliberately not used here — Phase 47 labelled it non-evidence, since it asserts the
    answer the type map already produces.
    """
    _role, descriptor = SNOWFLAKE_DERIVED_METADATA[field_name]
    annotation = snowflake_json_type_to_python(descriptor)
    value = read_cassette_values(SNOWFLAKE_PROBE_CASSETTE)[field_name]

    assert annotation is not None, f"{field_name} maps to no annotation"
    assert value is not None, f"{field_name} recorded as NULL, which says nothing about its type"

    assert isinstance(value, resolve_annotation(annotation)), (
        f"{field_name}: Snowflake reports {descriptor!r}, the type map annotates it "
        f"{annotation!r}, but the recorded value is a "
        f"{type(value).__module__}.{type(value).__qualname__}."
    )


@pytest.mark.parametrize("field_name", sorted(DATABRICKS_FIELD_SOURCES))
def test_databricks_annotation_describes_the_recorded_value(field_name: str) -> None:
    """
    The Databricks annotation names a type the recorded value is an instance of.

    Databricks is the one backend whose metadata *and* value both come from real recordings:
    the introspection cassette supplies the column's type object and the query cassette
    supplies the value. What it has no recording of is a decimal column or an interval column
    of any kind — see this module's docstring.
    """
    with pyarrow.ipc.open_file(DATABRICKS_INTROSPECT_CASSETTE / "000_result.arrow") as reader:
        rows: list[dict[str, Any]] = reader.read_all().to_pylist()
    payload: dict[str, Any] = json.loads(str(rows[0]["json_metadata"]))
    columns = {str(column["name"]): column for column in payload["columns"]}

    type_obj: dict[str, object] = columns[DATABRICKS_FIELD_SOURCES[field_name]]["type"]
    annotation = databricks_type_to_python(type_obj)
    value = read_cassette_values(DATABRICKS_PROBE_CASSETTE)[field_name]

    assert annotation is not None, f"{field_name} maps to no annotation"
    assert value is not None, f"{field_name} recorded as NULL, which says nothing about its type"

    assert isinstance(value, resolve_annotation(annotation)), (
        f"{field_name}: Databricks reports {type_obj!r}, the type map annotates it "
        f"{annotation!r}, but the recorded value is a "
        f"{type(value).__module__}.{type(value).__qualname__}."
    )
