"""
Measure a semantic-view field's type along three independent routes and render the comparison.

This module is deliberately **not** a test module: its name matches none of pytest's
``python_files`` patterns, so pytest imports it for doctest collection only (the same way it
imports ``tests/models.py``). It is driven by ``just type-fidelity``
(``uv run python tests/type_fidelity_probe.py --write``) and read by the guards in
``tests/unit/test_type_fidelity_table.py``.

The module is split into two regions that must never be allowed to converge:

* the **metadata half** — :func:`measure_duckdb`'s use of ``Engine.introspect`` and the raw
  ``DESCRIBE SELECT * FROM semantic_view(...)`` statement. Its mapped-annotation column is
  produced by ``semolina.codegen.type_map``, which is exactly the thing being measured;
* the **result half** — :func:`probe_schema`. It must never import
  ``semolina.codegen.type_map`` or any symbol from it. Its values come from the driver's own
  Arrow schema and from ``pyarrow``'s conversion of that schema to Python objects.

Two columns sourced from one place would make the comparison circular, and a comparison that
cannot produce a mismatch is not measuring anything. That is the failure this probe exists to
rule out; ``tests/unit/test_type_fidelity_table.py`` enforces it.

Record/replay contract: the DuckDB probe runs **live, in-process**, against an in-memory
DuckDB. It records nothing and must never be routed through pytest-adbc-replay cassette
interception — ``adbc_auto_patch`` lists ``adbc_driver_manager.dbapi``, which DuckDB also
routes through, so a cassette marker would silently divert it into replay *and* normalise its
SQL as the Databricks dialect.
"""

from __future__ import annotations

import argparse
import difflib
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from semolina import Dimension, Metric, SemanticView

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pyarrow

    from semolina.engines.base import Engine


# -- Fixture -----------------------------------------------------------------------------

PROBE_VIEW_NAME = "type_fidelity_view"
"""Name of the semantic view the probe measures."""

PROBE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS type_fidelity_orders (
    id INTEGER,
    order_total DECIMAL(10, 2),
    order_count INTEGER,
    region VARCHAR
)
"""
"""
Base table for the probe fixture.

``order_total DECIMAL(10, 2)`` is the phase's headline column: it is the only shape in this
repo where decimal precision widening under ``SUM`` is demonstrable end to end.
"""

PROBE_SEED_DML = """
INSERT INTO type_fidelity_orders VALUES
    (1, 30.75, 3, 'US'),
    (2, 12.50, 1, 'US'),
    (3, 100.00, 7, 'MX'),
    (4, NULL, NULL, 'CA')
"""
"""
Seed rows for the probe fixture.

Row 4 exists so that a group can have a non-NULL dimension key and all-NULL metric inputs,
which is the shape :func:`measure_empty_group_values` measures for metric nullability. It is
the only seed row whose metric inputs are NULL, so :data:`EMPTY_GROUP_REGION` names the group
it creates rather than any group that happens to be empty.
"""

PROBE_VIEW_DDL = """
CREATE OR REPLACE SEMANTIC VIEW type_fidelity_view AS
TABLES (
    o AS type_fidelity_orders PRIMARY KEY (id)
)
DIMENSIONS (
    o.region AS region
)
METRICS (
    o.total_order_value AS SUM(o.order_total),
    o.max_order_value AS MAX(o.order_total),
    o.total_order_count AS SUM(o.order_count),
    o.avg_order_count AS AVG(o.order_count),
    o.min_order_count AS MIN(o.order_count),
    o.n_order_totals AS COUNT(o.order_total)
)
"""
"""
Semantic view over :data:`PROBE_TABLE_DDL`.

The six metrics here and :data:`DUCKDB_PROBE_METRICS` must stay in step — a metric declared
here and not emitted is a gap nothing else would make visible. Metric names deliberately
differ from the underlying column names: the ``semantic_views`` extension rejects a metric
that collides with a dimension or column name.
"""


class TypeFidelityView(SemanticView, view="type_fidelity_view"):
    """
    Model of :data:`PROBE_VIEW_DDL`, used to build probe SQL through Semolina's own builder.

    Every field of the view is declared. The SQL is built rather than pasted so the probe
    measures the statement users' queries actually produce.
    """

    total_order_value = Metric()
    max_order_value = Metric()
    total_order_count = Metric()
    avg_order_count = Metric()
    min_order_count = Metric()
    n_order_totals = Metric()
    region = Dimension()


def setup_probe_view(dbapi_conn: Any, _connection_record: Any) -> None:
    """
    Create the probe table, seed it, and create the semantic view on each new connection.

    Everything happens in this ``connect`` listener rather than after the pool is built:
    adbc-poolhouse clones an independent in-memory DuckDB per physical connection
    (``source.adbc_clone``), so data inserted later would vanish on the next checkout.

    Args:
        dbapi_conn: The freshly opened ADBC DBAPI connection.
        _connection_record: SQLAlchemy pool bookkeeping object; unused.
    """
    cur = dbapi_conn.cursor()
    cur.execute(PROBE_TABLE_DDL)
    cur.execute("DELETE FROM type_fidelity_orders")
    cur.execute(PROBE_SEED_DML)
    cur.execute(PROBE_VIEW_DDL)
    cur.close()
    dbapi_conn.commit()


def make_probe_engine() -> Engine:
    """
    Build an in-memory DuckDB engine carrying the probe fixture.

    ``create_engine`` attaches the ``_load_semantic_views`` connect listener, which installs
    the community extension on first use; :func:`setup_probe_view` is attached to the same
    pool afterwards so the extension is loaded before the view DDL runs. ``pool_size=1`` is
    the mitigation for the per-connection-clone trap described in :func:`setup_probe_view`.

    Returns:
        A DuckDB :class:`~semolina.engines.base.Engine` whose every physical connection
        carries ``type_fidelity_view``. The caller owns it and must call ``dispose()``.
    """
    from adbc_poolhouse import DuckDBConfig
    from sqlalchemy import event

    from semolina.config import create_engine

    engine = create_engine(DuckDBConfig(database=":memory:", pool_size=1))
    event.listen(engine._pool, "connect", setup_probe_view)
    return engine


# -- Result half: schema probing. Must not import semolina.codegen.type_map ---------------

ROUTE_EXECUTE_SCHEMA = "execute-schema"
"""Probe route: the driver answered ``adbc_execute_schema`` directly."""

ROUTE_ZERO_ROW = "zero-row"
"""Probe route: the driver refused ``ExecuteSchema``, so a ``WHERE 1=0`` execution was used."""


def _resolve_not_implemented_errors() -> tuple[type[Exception], ...]:
    """
    Read the installed driver manager's exception classes for a refused ``ExecuteSchema``.

    Resolved from the installed package rather than assumed. In ``adbc_driver_manager``
    1.10.0 the DBAPI hierarchy is ``Error(Exception)`` ->
    ``DatabaseError`` -> ``{NotSupportedError, ProgrammingError, OperationalError, ...}``.
    ``NotSupportedError`` is the documented DBAPI mapping for ``StatusNotImplemented``, but
    it was never exercised against a refusing driver, so ``ProgrammingError`` and
    ``OperationalError`` are included: they are the two classes the manager also uses for
    driver-side status codes, and catching all three makes the fallback fire regardless of
    which one a given driver's status is mapped onto.

    Returns:
        The exception classes that mean "this driver will not answer ``ExecuteSchema``".
    """
    import adbc_driver_manager

    return (
        adbc_driver_manager.NotSupportedError,
        adbc_driver_manager.ProgrammingError,
        adbc_driver_manager.OperationalError,
    )


NOT_IMPLEMENTED_ERRORS: tuple[type[Exception], ...] = _resolve_not_implemented_errors()
"""
Exception classes that mean the driver refused ``ExecuteSchema``.

See :func:`_resolve_not_implemented_errors` for the resolved hierarchy and the installed
version it was read from.
"""


@dataclass(frozen=True)
class ProbeResult:
    """
    A probed result schema plus the route that produced it.

    Attributes:
        schema: The query's result schema, as the driver resolved it.
        route: :data:`ROUTE_EXECUTE_SCHEMA` or :data:`ROUTE_ZERO_ROW`. Recorded so the
            artifact's provenance cell is measured rather than assumed.
    """

    schema: pyarrow.Schema
    route: str


def probe_schema(cursor: Any, sql: str, params: list[Any]) -> ProbeResult:
    """
    Return a query's result schema without depending on Semolina's type map.

    Prefers ADBC ``ExecuteSchema``; falls back to a zero-row execution for drivers that
    answer ``NOT_IMPLEMENTED`` (Databricks) or that reject bound parameters (Snowflake).

    Args:
        cursor: An ADBC DBAPI cursor.
        sql: The query whose result schema is wanted.
        params: Bind parameters for that query. Pass ``[]`` rather than ``None`` — under
            cassette replay the parameter list is part of the lookup key.

    Returns:
        The resolved schema and the route that produced it.
    """
    try:
        schema = cursor.adbc_execute_schema(sql, params)
    except NOT_IMPLEMENTED_ERRORS:
        cursor.execute(f"SELECT * FROM ({sql}) WHERE 1=0", params or None)
        reader = cursor.fetch_record_batch()
        try:
            fallback_schema = reader.schema
        finally:
            reader.close()
        return ProbeResult(schema=fallback_schema, route=ROUTE_ZERO_ROW)
    return ProbeResult(schema=schema, route=ROUTE_EXECUTE_SCHEMA)


def python_value_type_name(value: object) -> str:
    """
    Name the Python type a warehouse value actually arrived as.

    Builtins are named bare (``int``); anything else is qualified by module so the artifact
    reads ``decimal.Decimal`` rather than an ambiguous ``Decimal``.

    Args:
        value: A single value taken from ``RecordBatch.to_pylist()``.

    Returns:
        The type's name, module-qualified unless it is a builtin.
    """
    cls = type(value)
    if cls.__module__ == "builtins":
        return cls.__qualname__
    return f"{cls.__module__}.{cls.__qualname__}"


def probe_value_types(cursor: Any, sql: str, params: list[Any]) -> dict[str, str]:
    """
    Execute a query once and report the Python type every one of its columns arrives as.

    This is the user-visible consequence of the result schema: ``pyarrow`` converts the Arrow
    buffer, and Semolina's row path calls ``to_pylist()`` on exactly this data. NULLs are
    skipped per column — a group with no non-NULL inputs says nothing about the value type.

    One execution covers every column, so the seven measured fields cannot end up describing
    seven separately-planned queries.

    Args:
        cursor: An ADBC DBAPI cursor.
        sql: The query to execute.
        params: Bind parameters for that query.

    Returns:
        Result column name -> the name of the Python type its first non-NULL value has, or
        ``"NoneType"`` when every value in that column is NULL.
    """
    cursor.execute(sql, params or None)
    table = cursor.fetch_arrow_table()
    rows: list[dict[str, object]] = table.to_pylist()
    column_names: list[str] = list(table.column_names)

    value_types: dict[str, str] = {}
    for name in column_names:
        value_types[name] = "NoneType"
        for row in rows:
            value = row.get(name)
            if value is not None:
                value_types[name] = python_value_type_name(value)
                break
    return value_types


def probe_value_type(cursor: Any, sql: str, params: list[Any], field_name: str) -> str:
    """
    Execute a query and report the Python type one column's values arrive as.

    A single-column view of :func:`probe_value_types`.

    Args:
        cursor: An ADBC DBAPI cursor.
        sql: The query to execute.
        params: Bind parameters for that query.
        field_name: The result column to read.

    Returns:
        The name of the Python type the field's first non-NULL value has, or ``"NoneType"``
        when every value is NULL.
    """
    return probe_value_types(cursor, sql, params)[field_name]


# -- Metadata half: introspection and the raw warehouse type ------------------------------

TODO_PREFIX = "TODO: "
"""Prefix ``IntrospectedField.data_type`` carries when the type map produced no annotation."""

VERDICT_MATCH = "match"
"""The mapped annotation names the Python type the values actually arrive as."""

VERDICT_MISMATCH = "mismatch"
"""The mapped annotation does not name the Python type the values actually arrive as."""


def classify_verdict(mapped_annotation: str, value_type: str) -> str:
    """
    Compare the annotation codegen would emit against the type the values actually have.

    A ``TODO: `` annotation is classified as a mismatch rather than as a third
    "mapping-gap" verdict: the renderer turns it into ``Any``, so it names no Python type at
    all, which is the strongest form of disagreement rather than a separate kind. Keeping the
    vocabulary to two values also keeps the canary honest — if a future refactor ever sourced
    both columns from one place, this would read ``match`` and the canary test would go red.

    Args:
        mapped_annotation: ``IntrospectedField.data_type`` for the field.
        value_type: The name produced by :func:`python_value_type_name`.

    Returns:
        :data:`VERDICT_MATCH` or :data:`VERDICT_MISMATCH`.
    """
    if mapped_annotation.startswith(TODO_PREFIX):
        return VERDICT_MISMATCH
    return VERDICT_MATCH if mapped_annotation == value_type else VERDICT_MISMATCH


def describe_raw_types(
    cursor: Any, view_name: str, dimensions: list[str], metrics: list[str]
) -> dict[str, str]:
    """
    Read the raw warehouse type of each field, before any Semolina mapping is applied.

    Re-runs the same ``DESCRIBE SELECT * FROM semantic_view(...)`` statement
    ``DuckDBEngine.introspect`` runs, and keeps column 1 verbatim. The raw type is captured
    here rather than parsed back out of the ``TODO: `` prefix, because that prefix only
    survives for types the map has no entry for — raw and mapped are two separate values.

    Args:
        cursor: An ADBC DBAPI cursor.
        view_name: Unqualified semantic view name.
        dimensions: Dimension field names to include in the ``semantic_view()`` call.
        metrics: Metric field names to include in the ``semantic_view()`` call.

    Returns:
        Field name -> raw SQL type string, e.g. ``{"total_order_value": "DECIMAL(38,2)"}``.
    """
    from semolina.engines.duckdb import _sql_str_literal

    parts: list[str] = []
    if dimensions:
        dim_list = ", ".join(_sql_str_literal(name) for name in dimensions)
        parts.append(f"dimensions := [{dim_list}]")
    if metrics:
        metric_list = ", ".join(_sql_str_literal(name) for name in metrics)
        parts.append(f"metrics := [{metric_list}]")

    view_literal = _sql_str_literal(view_name)
    cursor.execute(f"DESCRIBE SELECT * FROM semantic_view({view_literal}, {', '.join(parts)})")
    return {str(row[0]): str(row[1]) for row in cursor.fetchall()}


# -- Row model and rendering --------------------------------------------------------------


@dataclass(frozen=True)
class FidelityRow:
    """
    One measured ``(backend, field)`` comparison.

    There is deliberately no sample-value field. The artifact is committed and public, so it
    records types only; a value column would give warehouse row data a path into git.

    Attributes:
        backend: ``duckdb``, ``snowflake``, or ``databricks``.
        field_name: The semantic view field measured.
        role: ``metric``, ``dimension``, or ``fact``.
        metadata_raw_type: The warehouse's own type name, before Semolina maps it.
        metadata_provenance: How ``metadata_raw_type`` and ``mapped_annotation`` were obtained.
        mapped_annotation: The Python annotation string codegen would emit for this field.
        result_arrow_type: The Arrow type the driver resolves for the query result.
        result_provenance: How ``result_arrow_type`` was obtained, including the probe route.
        python_value_type: The Python type the field's values actually arrive as.
        verdict: :data:`VERDICT_MATCH` or :data:`VERDICT_MISMATCH`.
    """

    backend: str
    field_name: str
    role: str
    metadata_raw_type: str
    metadata_provenance: str
    mapped_annotation: str
    result_arrow_type: str
    result_provenance: str
    python_value_type: str
    verdict: str

    def as_cells(self) -> tuple[str, ...]:
        """
        Return this row's values in :data:`ARTIFACT_HEADERS` order.

        Returns:
            One string per artifact column.
        """
        return (
            self.backend,
            self.field_name,
            self.role,
            self.metadata_raw_type,
            self.metadata_provenance,
            self.mapped_annotation,
            self.result_arrow_type,
            self.result_provenance,
            self.python_value_type,
            self.verdict,
        )


ARTIFACT_HEADERS: tuple[str, ...] = (
    "Backend",
    "Field",
    "Role",
    "Warehouse type",
    "Metadata provenance",
    "Mapped annotation",
    "Result Arrow type",
    "Result provenance",
    "Python value type",
    "Verdict",
)
"""Column headers of the artifact's comparison table, in :meth:`FidelityRow.as_cells` order."""

BACKEND_ORDER: tuple[str, ...] = ("duckdb", "snowflake", "databricks")
"""
Fixed backend order for the artifact's rows.

Row order is ``(BACKEND_ORDER index, field_name)``. Determinism is load-bearing: the drift
guard compares bytes, so ordering must never be a source of diff.
"""

ARTIFACT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".planning"
    / "phases"
    / "47-type-fidelity-probe-decision-doc"
    / "47-TYPE-FIDELITY.md"
)
"""The committed artifact this module generates."""


def sort_rows(rows: Sequence[FidelityRow]) -> list[FidelityRow]:
    """
    Order rows deterministically by backend then field name.

    Args:
        rows: Measured rows in collection order.

    Returns:
        A new list ordered by ``(BACKEND_ORDER index, field_name)``.
    """
    return sorted(rows, key=lambda row: (BACKEND_ORDER.index(row.backend), row.field_name))


def render_artifact(rows: Sequence[FidelityRow], sections: Sequence[str] = ()) -> str:
    """
    Render the committed comparison artifact.

    Emits no timestamp and no other value that changes between runs — the drift guard in
    ``tests/unit/test_type_fidelity_table.py`` compares bytes.

    Args:
        rows: Measured rows, in any order.
        sections: Pre-rendered markdown sections appended after the comparison table, in
            order. Each must begin with its own ``##`` heading. Defaults to none, so a caller
            holding only rows still renders a valid table-only document.

    Returns:
        The full markdown document, newline-terminated.

    Raises:
        ValueError: If a row does not carry exactly one cell per artifact column.
    """
    lines: list[str] = [
        "# Phase 47: warehouse type fidelity, measured",
        "",
        "Generated by `just type-fidelity`. Do not edit by hand — edits are overwritten on",
        "regeneration and `tests/unit/test_type_fidelity_table.py` fails while the committed",
        "file and the generator disagree.",
        "",
        "Every cell below was measured. Nothing here is asserted from Semolina's own type map,",
        "except the `Mapped annotation` column, which *is* the type map and is the thing under",
        "measurement.",
        "",
        "## Provenance legend",
        "",
        "- `live` — measured in this process against a real driver connection.",
        "- `cassette-file` — read from a committed pytest-adbc-replay cassette. Real warehouse",
        "  evidence about result types; no evidence about what the live driver implements.",
        "- `derived-from-code` — produced by reading Semolina's own source rather than a",
        "  warehouse. Any `derived-from-code` in a result column would be circular evidence.",
        "- `driver-source` — read from the ADBC driver's published source at a pinned version.",
        "",
        "A result-provenance cell names the probe route in parentheses: `execute-schema` when",
        "the driver answered `adbc_execute_schema`, `zero-row` when it refused and the",
        "`SELECT * FROM (...) WHERE 1=0` fallback was used instead.",
        "",
        "## Field type comparison",
        "",
        "| " + " | ".join(ARTIFACT_HEADERS) + " |",
        "|" + "---|" * len(ARTIFACT_HEADERS),
    ]
    for row in sort_rows(rows):
        cells = row.as_cells()
        if len(cells) != len(ARTIFACT_HEADERS):
            msg = (
                f"FidelityRow emitted {len(cells)} cells but the table has "
                f"{len(ARTIFACT_HEADERS)} columns."
            )
            raise ValueError(msg)
        lines.append("| " + " | ".join(cells) + " |")
    for section in sections:
        lines.append("")
        lines.extend(section.splitlines())
    lines.append("")
    return "\n".join(lines)


# -- Collection ---------------------------------------------------------------------------

DUCKDB_PROBE_METRICS: tuple[str, ...] = (
    "total_order_value",
    "max_order_value",
    "total_order_count",
    "avg_order_count",
    "min_order_count",
    "n_order_totals",
)
"""
The six metrics of :data:`PROBE_VIEW_DDL`, in DDL declaration order.

They are the measurement surface for TYPE-01, chosen so each named disagreement has both a
positive case and a contrast case: ``total_order_value``/``max_order_value`` for decimal
widening, ``avg_order_count``/``total_order_count`` for ``AVG``, and
``n_order_totals``/``min_order_count`` for ``COUNT``. This tuple and the ``METRICS`` block of
:data:`PROBE_VIEW_DDL` must stay in step — a metric declared in the DDL and missing here is a
gap nothing else would make visible.
"""

DUCKDB_PROBE_DIMENSIONS: tuple[str, ...] = ("region",)
"""The dimensions of :data:`PROBE_VIEW_DDL`, grouped by in the probe query."""

DUCKDB_PROBE_FIELDS: tuple[str, ...] = DUCKDB_PROBE_METRICS + DUCKDB_PROBE_DIMENSIONS
"""Every field the DuckDB half emits a row for."""

EMPTY_GROUP_REGION = "CA"
"""
The seed group whose dimension key is non-NULL and whose every metric input is NULL.

Row 4 of :data:`PROBE_SEED_DML` is ``(4, NULL, NULL, 'CA')``, so the ``CA`` group exists but
has nothing to aggregate. This is the shape that separates NULL-able aggregates from ``COUNT``.
"""

UNMATCHED_FILTER_REGION = "ZZ-NO-SUCH-REGION"
"""
A dimension value no seed row carries, used to measure the *other* empty shape.

Filtering on it produces a ``GROUP BY`` that matches nothing, which is a different observation
from :data:`EMPTY_GROUP_REGION` and yields a different answer.
"""


def probe_sql_for(field_name: str) -> tuple[str, list[Any]]:
    """
    Build the probe SQL for one metric through Semolina's own DuckDB builder.

    Built rather than pasted so the probe measures the statement a user's query produces.
    Probing through ``semantic_view(...)`` matters: a hand-written ``SELECT SUM(...)`` over
    the base table reports types the extension casts away before users ever see them.

    This is the *minimal* query for a single metric, quoted in the artifact's named
    disagreements. :func:`probe_sql_all` is what the comparison table is measured through.

    Args:
        field_name: A metric declared on :class:`TypeFidelityView`.

    Returns:
        The SQL template and its bind parameters.
    """
    from semolina.engines.sql import DuckDBDialect

    builder = DuckDBDialect().create_builder()
    query = TypeFidelityView.query().metrics(getattr(TypeFidelityView, field_name))
    return builder.build_select_with_params(query)


def probe_sql_all() -> tuple[str, list[Any]]:
    """
    Build the probe SQL selecting every metric, grouped by every dimension.

    One query rather than seven: every measured field then comes out of a single planned
    statement, so the comparison table cannot describe seven differently-planned queries that
    happen to share a view name.

    Returns:
        The SQL template and its bind parameters.
    """
    from semolina.engines.sql import DuckDBDialect

    builder = DuckDBDialect().create_builder()
    query = (
        TypeFidelityView.query()
        .metrics(*(getattr(TypeFidelityView, name) for name in DUCKDB_PROBE_METRICS))
        .dimensions(*(getattr(TypeFidelityView, name) for name in DUCKDB_PROBE_DIMENSIONS))
    )
    return builder.build_select_with_params(query)


def measure_empty_group_values(engine: Engine) -> dict[str, object]:
    """
    Observe what each metric returns for a group whose inputs are all NULL.

    The Arrow ``nullable`` flag cannot answer this — it reads ``True`` for every field on
    every backend measured, ``COUNT`` included. The answer comes from observed values on the
    :data:`EMPTY_GROUP_REGION` group instead.

    Args:
        engine: A DuckDB engine carrying the probe fixture.

    Returns:
        Metric name -> the Python value observed for that metric on the all-NULL group.

    Raises:
        LookupError: If the seed group is absent, which would mean the measurement silently
            described a different group than the one it names.
    """
    sql, params = probe_sql_all()
    with engine.connect() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params or None)
            rows: list[dict[str, object]] = cursor.fetch_arrow_table().to_pylist()
        finally:
            cursor.close()

    for row in rows:
        if row.get("region") == EMPTY_GROUP_REGION:
            return {name: row[name] for name in DUCKDB_PROBE_METRICS}

    msg = (
        f"No {EMPTY_GROUP_REGION!r} group in the probe result; the all-NULL seed row is "
        "missing, so nothing here would be measuring empty-group nullability."
    )
    raise LookupError(msg)


def measure_unmatched_filter_rows(engine: Engine) -> int:
    """
    Count the rows a ``GROUP BY`` returns when its filter matches nothing.

    A separate observation from :func:`measure_empty_group_values`, and it answers
    differently. The success criterion's phrase "metric nullability on empty groups" reads as
    though an unmatched filter yields a row of NULLs; it does not, and the artifact has to say
    which of the two shapes it measured.

    Args:
        engine: A DuckDB engine carrying the probe fixture.

    Returns:
        The number of result rows, which is expected to be zero.
    """
    from semolina.engines.duckdb import _sql_str_literal

    sql, params = probe_sql_all()
    literal = _sql_str_literal(UNMATCHED_FILTER_REGION)
    with engine.connect() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT * FROM ({sql}) WHERE region = {literal}", params or None)
            rows: list[dict[str, object]] = cursor.fetch_arrow_table().to_pylist()
        finally:
            cursor.close()
    return len(rows)


def measure_versions(engine: Engine) -> tuple[str, str]:
    """
    Read the DuckDB and ``semantic_views`` versions the measurement actually ran against.

    Read rather than quoted from ``pyproject.toml``: a measurement is only reproducible if the
    artifact names the versions that produced it, and a hand-written version string is one
    more claim nobody checked.

    Args:
        engine: A DuckDB engine carrying the probe fixture.

    Returns:
        The DuckDB version and the ``semantic_views`` extension version.
    """
    with engine.connect() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT version()")
            duckdb_version = str(cursor.fetchall()[0][0])
            cursor.execute(
                "SELECT extension_version FROM duckdb_extensions() "
                "WHERE extension_name = 'semantic_views'"
            )
            extension_rows = cursor.fetchall()
        finally:
            cursor.close()
    extension_version = str(extension_rows[0][0]) if extension_rows else "unknown"
    return duckdb_version, extension_version


@dataclass(frozen=True)
class ProbeEvidence:
    """
    The measured facts the artifact states outside the comparison table.

    Grouped rather than passed loose because they are read off one probe run, and a renderer
    holding only some of them would state the rest unmeasured.

    Attributes:
        empty_group_values: Metric name -> value observed on the all-NULL group.
        nullable_flags: Field name -> the Arrow schema's ``nullable`` flag for that field.
        unmatched_filter_row_count: Rows returned when the filter matches nothing.
        duckdb_version: The DuckDB version the measurement ran against.
        extension_version: The ``semantic_views`` extension version it ran against.
    """

    empty_group_values: dict[str, object]
    nullable_flags: dict[str, bool]
    unmatched_filter_row_count: int
    duckdb_version: str
    extension_version: str


@dataclass(frozen=True)
class DuckDBMeasurement:
    """
    Everything the DuckDB half measures in one probe run.

    Attributes:
        rows: One :class:`FidelityRow` per entry in :data:`DUCKDB_PROBE_FIELDS`.
        evidence: The observations that are not table columns.
    """

    rows: list[FidelityRow]
    evidence: ProbeEvidence


def measure_duckdb() -> DuckDBMeasurement:
    """
    Measure the DuckDB half of the comparison, live and in-process.

    Reaches every field by two independent routes: ``Engine.introspect`` plus a raw
    ``DESCRIBE`` for the metadata half, and :func:`probe_schema` plus ``to_pylist()`` for the
    result half. One ``semantic_view(...)`` query covers all seven fields.

    Returns:
        The measured rows plus the nullability evidence.
    """
    engine = make_probe_engine()
    try:
        view = engine.introspect(PROBE_VIEW_NAME)
        by_name = {field.name: field for field in view.fields}
        dimensions = sorted(f.name for f in view.fields if f.field_type == "dimension")
        metrics = sorted(f.name for f in view.fields if f.field_type == "metric")

        sql, params = probe_sql_all()
        rows: list[FidelityRow] = []
        with engine.connect() as conn:
            cursor = conn.cursor()
            try:
                raw_types = describe_raw_types(cursor, PROBE_VIEW_NAME, dimensions, metrics)
                probed = probe_schema(cursor, sql, params)
                value_types = probe_value_types(cursor, sql, params)
                nullable_flags = {
                    name: bool(probed.schema.field(name).nullable) for name in DUCKDB_PROBE_FIELDS
                }
                for field_name in DUCKDB_PROBE_FIELDS:
                    introspected = by_name[field_name]
                    mapped = introspected.data_type or ""
                    value_type = value_types[field_name]
                    rows.append(
                        FidelityRow(
                            backend="duckdb",
                            field_name=field_name,
                            role=introspected.field_type,
                            metadata_raw_type=raw_types[field_name],
                            metadata_provenance="live",
                            mapped_annotation=mapped,
                            result_arrow_type=str(probed.schema.field(field_name).type),
                            result_provenance=f"live ({probed.route})",
                            python_value_type=value_type,
                            verdict=classify_verdict(mapped, value_type),
                        )
                    )
            finally:
                cursor.close()

        duckdb_version, extension_version = measure_versions(engine)
        evidence = ProbeEvidence(
            empty_group_values=measure_empty_group_values(engine),
            nullable_flags=nullable_flags,
            unmatched_filter_row_count=measure_unmatched_filter_rows(engine),
            duckdb_version=duckdb_version,
            extension_version=extension_version,
        )
        return DuckDBMeasurement(rows=rows, evidence=evidence)
    finally:
        engine.dispose()


def collect_duckdb_rows() -> list[FidelityRow]:
    """
    Measure the DuckDB half and keep only the comparison rows.

    Returns:
        One :class:`FidelityRow` per entry in :data:`DUCKDB_PROBE_FIELDS`.
    """
    return measure_duckdb().rows


def collect_rows() -> list[FidelityRow]:
    """
    Measure every backend the artifact currently covers.

    Returns:
        All measured rows, unordered; :func:`render_artifact` orders them.
    """
    return collect_duckdb_rows()


# -- Named disagreements ------------------------------------------------------------------

DISAGREEMENT_HEADINGS: tuple[str, ...] = (
    "Decimal precision widening under SUM",
    "`AVG(int)` -> double",
    "`COUNT` -> int64",
    "Metric nullability on empty groups",
)
"""
The four disagreements ROADMAP success criterion 2 requires to be named individually.

Criterion 2 explicitly rejects a pass/fail summary, so each of these gets its own subsection
carrying the minimal query that produced it, the measured Arrow type, and a contrast case that
makes it a finding rather than a coincidence.
"""


def _minimal_query_block(field_name: str) -> list[str]:
    """
    Render the minimal ``semantic_view(...)`` query for one metric as a fenced code block.

    Built through :func:`probe_sql_for` rather than pasted, so the quoted query cannot drift
    away from the statement the probe actually issues.

    Args:
        field_name: A metric declared on :class:`TypeFidelityView`.

    Returns:
        Markdown lines, ready to extend into a document.
    """
    sql, _params = probe_sql_for(field_name)
    return ["```sql", *sql.splitlines(), "```"]


def _render_observed_value(value: object) -> str:
    """
    Render an empty-group observation without giving warehouse row data a path into the file.

    Only ``None`` and ``0`` are printed verbatim — they are the two answers the nullability
    question turns on and neither is data. Anything else is reduced to its type name, so a
    future re-seed against a real dataset cannot leak a value into a committed artifact
    (threat T-47-01).

    Args:
        value: A single observed metric value.

    Returns:
        A markdown fragment naming the observation.
    """
    if value is None:
        return "`None`"
    if isinstance(value, int) and not isinstance(value, bool) and value == 0:
        return "`0`"
    return f"non-NULL (`{python_value_type_name(value)}`)"


PROSE_WIDTH = 92
"""
Wrap width for generated prose paragraphs.

Interpolated Arrow types vary in length, so paragraphs are assembled as single strings and
wrapped here rather than hand-broken. Wrapping is a pure function of the text, which keeps
regeneration byte-stable for the drift guard.
"""


def _paragraph(text: str) -> list[str]:
    """
    Wrap one prose paragraph to :data:`PROSE_WIDTH`, followed by a blank line.

    Args:
        text: The paragraph, with any incidental newlines and runs of spaces.

    Returns:
        Wrapped markdown lines plus a trailing blank line.
    """
    collapsed = " ".join(text.split())
    return [*textwrap.wrap(collapsed, width=PROSE_WIDTH), ""]


def render_disagreements(rows: Sequence[FidelityRow], evidence: ProbeEvidence) -> str:
    """
    Render the ``## Named disagreements`` section.

    Reads its measured types out of the same :class:`FidelityRow` list the comparison table
    renders, so the prose and the table cannot drift apart.

    Args:
        rows: The measured rows.
        evidence: The observations that are not table columns.

    Returns:
        A markdown section beginning with its own ``##`` heading.

    Raises:
        KeyError: If a field named by a subsection was not measured.
    """
    by_field = {row.field_name: row for row in rows if row.backend == "duckdb"}

    def arrow(field_name: str) -> str:
        return f"`{by_field[field_name].result_arrow_type}`"

    def python(field_name: str) -> str:
        return f"`{by_field[field_name].python_value_type}`"

    def warehouse(field_name: str) -> str:
        return f"`{by_field[field_name].metadata_raw_type}`"

    lines: list[str] = ["## Named disagreements", ""]
    lines += _paragraph(
        "Four disagreements between what the catalogue says a field is and what the "
        "warehouse actually returns. Each names the minimal query that produced it, the "
        "measured Arrow type, the Python type the value arrives as, and a contrast case — "
        "without the contrast a single measurement is a coincidence rather than a rule."
    )
    lines += _paragraph(
        f"All four were measured through `semantic_view(...)` against DuckDB "
        f"{evidence.duckdb_version} with `semantic_views` {evidence.extension_version}, both "
        "read from the running database rather than quoted from `pyproject.toml`. Vendor "
        "rules are cited where a vendor publishes one and marked undocumented where none "
        "exists; a rule is never inferred from a measurement."
    )

    lines += [f"### 1. {DISAGREEMENT_HEADINGS[0]}", "", "Minimal query:", ""]
    lines += [*_minimal_query_block("total_order_value"), ""]
    lines += _paragraph(
        f"`total_order_value` is `SUM(o.order_total)` over an `order_total DECIMAL(10, 2)` "
        f"column. The catalogue reports {warehouse('total_order_value')}, the result schema "
        f"resolves to {arrow('total_order_value')}, and the value arrives as "
        f"{python('total_order_value')}. Precision went to 38: an aggregate's result type is "
        "not its input's type."
    )
    lines += _paragraph(
        f"**Contrast:** `max_order_value` is `MAX(o.order_total)` over the *same* column and "
        f"measures {arrow('max_order_value')} — no widening. Two aggregates reading one input "
        "column do not collapse into one result type, and only accumulating aggregates widen."
    )
    lines += _paragraph(
        "**Vendor rules.** Databricks documents `sum(DECIMAL(p, s))` as "
        "`DECIMAL(p + min(10, 31-p), s)`. Snowflake publishes no SUM precision rule at all — "
        'its SUM page says only that values are summed into "an equivalent or larger data '
        'type" — so the Snowflake cell is undocumented and measured only.'
    )

    lines += [f"### 2. {DISAGREEMENT_HEADINGS[1]}", "", "Minimal query:", ""]
    lines += [*_minimal_query_block("avg_order_count"), ""]
    lines += _paragraph(
        f"`avg_order_count` is `AVG(o.order_count)` over an `order_count INTEGER` column. The "
        f"catalogue reports {warehouse('avg_order_count')}, the result schema resolves to "
        f"{arrow('avg_order_count')}, and the value arrives as {python('avg_order_count')}. "
        "Averaging leaves the integer domain entirely."
    )
    lines += _paragraph(
        f"**Contrast:** `total_order_count` is `SUM(o.order_count)` over the same `INTEGER` "
        f"column and measures {arrow('total_order_count')} -> {python('total_order_count')}. "
        "It is the aggregate that decides, not the column."
    )
    lines += _paragraph(
        "**Vendor rules.** Databricks documents `avg(DECIMAL(p, s))` as `DECIMAL(p+4, s+4)` "
        'and DOUBLE "in all other cases", which puts Databricks and DuckDB in disagreement on '
        "`AVG(decimal)` specifically. Snowflake documents no AVG return type at all: "
        "undocumented, and unmeasured here."
    )

    lines += [f"### 3. {DISAGREEMENT_HEADINGS[2]}", "", "Minimal query:", ""]
    lines += [*_minimal_query_block("n_order_totals"), ""]
    lines += _paragraph(
        f"`n_order_totals` is `COUNT(o.order_total)`. The catalogue reports "
        f"{warehouse('n_order_totals')}, the result schema resolves to "
        f"{arrow('n_order_totals')}, and the value arrives as {python('n_order_totals')}."
    )
    lines += _paragraph(
        f"**Contrast:** `min_order_count` is `MIN(o.order_count)` over an `INTEGER` column and "
        f'measures {arrow("min_order_count")}, not {arrow("n_order_totals")}. "Integer '
        'metric" is therefore not one Arrow type, and a type map keyed on the column type '
        "would get one of these two wrong whichever width it picked."
    )
    lines += _paragraph(
        "**The trap this row encodes.** A hand-written "
        "`SELECT SUM(order_count) FROM type_fidelity_orders` over that same column measures "
        "`decimal128(38, 0)` and arrives as `decimal.Decimal`, because plain DuckDB sums an "
        "`INTEGER` into a `HUGEINT`. Through `semantic_view(...)` the extension casts down and "
        f"the user receives {arrow('total_order_count')} -> {python('total_order_count')}. "
        "Probing outside `semantic_view(...)` would record a type nobody ever receives, so "
        "`tests/unit/test_type_fidelity_duckdb.py` asserts both halves and the probe cannot be "
        "moved onto the wrong path unnoticed."
    )

    lines += [f"### 4. {DISAGREEMENT_HEADINGS[3]}", ""]
    lines += _paragraph(
        f"Minimal query — every metric grouped by `region`, where the seed row "
        f"`(4, NULL, NULL, '{EMPTY_GROUP_REGION}')` gives the `{EMPTY_GROUP_REGION}` group a "
        "non-NULL key and all-NULL metric inputs:"
    )
    sql, _params = probe_sql_all()
    lines += ["```sql", *sql.splitlines(), "```", ""]
    lines += [f"Observed on the `{EMPTY_GROUP_REGION}` group:", ""]
    lines += [
        f"- `{name}` -> {_render_observed_value(evidence.empty_group_values[name])}"
        for name in DUCKDB_PROBE_METRICS
    ]
    lines.append("")
    lines += _paragraph(
        "So metric nullability is **not uniform**. `SUM`, `AVG`, `MIN`, and `MAX` all go NULL "
        "on a group with nothing to aggregate, while `COUNT` returns `0`. A blanket "
        "`T | None` over every metric would be wrong for `COUNT`; a blanket `T` would be wrong "
        "for the other four."
    )
    lines += _paragraph(
        "**A GROUP BY that matches nothing returns zero rows, not a row of NULLs.** Filtering "
        f"the same query on a region no seed row carries returned "
        f"{evidence.unmatched_filter_row_count} rows. The NULLs above appear only because the "
        'group exists and has no non-NULL inputs. The phrase "metric nullability on empty '
        'groups" covers those two different shapes and only one of them produces a NULL; both '
        "were measured here."
    )
    lines += _paragraph(
        "**The Arrow `nullable` flag carries no information.** Every field measured reports "
        "`nullable` as True, `n_order_totals` included, even though `COUNT` demonstrably never "
        "returns NULL. Nullability cannot be read off the probe, so no acceptance criterion in "
        "this phase is built on that flag: it is a policy call decided from the aggregate's "
        "semantics. The measured flags, in full:"
    )
    lines += [
        f"- `{name}` -> `nullable={evidence.nullable_flags[name]}`" for name in DUCKDB_PROBE_FIELDS
    ]

    return "\n".join(lines)


# -- Entry point --------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """
    Regenerate or verify the committed comparison artifact.

    Args:
        argv: Command-line arguments, excluding the program name. Defaults to ``sys.argv[1:]``.

    Returns:
        ``0`` on success. ``1`` when ``--check`` finds the committed file out of date; the
        unified diff is written to stderr.
    """
    parser = argparse.ArgumentParser(description=__doc__ and __doc__.strip().splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Regenerate and write the artifact.")
    mode.add_argument("--check", action="store_true", help="Fail if the artifact is stale.")
    args = parser.parse_args(argv)

    measurement = measure_duckdb()
    sections = [render_disagreements(measurement.rows, measurement.evidence)]
    rendered = render_artifact(measurement.rows, sections)

    if args.write:
        ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _ = ARTIFACT_PATH.write_text(rendered, encoding="utf-8")
        return 0

    committed = ARTIFACT_PATH.read_text(encoding="utf-8") if ARTIFACT_PATH.exists() else ""
    if committed == rendered:
        return 0
    diff = difflib.unified_diff(
        committed.splitlines(keepends=True),
        rendered.splitlines(keepends=True),
        fromfile=f"{ARTIFACT_PATH} (committed)",
        tofile=f"{ARTIFACT_PATH} (regenerated)",
    )
    sys.stderr.writelines(diff)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
