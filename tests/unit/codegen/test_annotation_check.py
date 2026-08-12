"""
Tests for the annotation-drift comparison core.

Record/replay contract: the DuckDB half of this module runs **live, in-process**, against
in-memory and file-backed DuckDB, and must never carry ``pytest.mark.adbc_cassette`` — the
same rule ``tests/unit/test_type_fidelity_duckdb.py``'s module docstring states and for the
same reason (``adbc_auto_patch`` lists ``adbc_driver_manager.dbapi``, which DuckDB routes
through, and ``adbc_dialect`` maps that module to the Databricks sqlglot dialect).

The Snowflake half reads the **committed recording** with ``pyarrow.ipc.open_file`` and feeds
its real Arrow schema through the comparison core. That is a deliberate narrowing of D-09's
"Snowflake (cassette)": this repo has no Snowflake *introspection* cassette
(``tests/type_fidelity_probe.py`` says so verbatim), so a replayed end-to-end CLI ``--check``
on Snowflake is not runnable. The recording carries the result-schema half, which is exactly
what the comparison core consumes.

There is deliberately **no Databricks test** (D-09): the driver has no ``ExecuteSchema`` and
its zero-row wrapper has never been run against a live metric view (broken window 2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from semolina.codegen.annotation_check import (
    ABSENT,
    ROUTE_METADATA,
    STATUS_DRIFT,
    STATUS_MATCH,
    check_view,
)
from semolina.codegen.introspector import IntrospectedField, IntrospectedView
from semolina.codegen.model_reader import CommittedField, CommittedModel
from semolina.codegen.probe import ROUTE_EXECUTE_SCHEMA
from semolina.engines.base import Engine

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    import pyarrow

pytest.importorskip("adbc_driver_duckdb")

PROBE_VIEW = "type_fidelity_view"
"""The in-memory probe view: seven metrics, one dimension, no facts."""

DECIMAL_METRIC = "total_order_value"
"""``SUM(DECIMAL(10,2))``: the field whose probed type is ``decimal128(38, 2)``."""


@pytest.fixture
def probe_engine() -> Generator[Engine]:
    """
    Yield the type-fidelity probe's in-memory DuckDB engine, disposing it on teardown.

    Mirrors the fixture of the same name in ``tests/unit/test_type_fidelity_duckdb.py``,
    which owns the record/replay contract this module inherits.
    """
    from type_fidelity_probe import make_probe_engine

    engine = make_probe_engine()
    yield engine
    engine.dispose()


@pytest.fixture
def sales_engine(duckdb_file_backed_db: Path) -> Generator[Engine]:
    """
    Yield an engine on the file-backed ``sales_view``, which carries facts AND metrics.

    That combination is what ``DuckDBSQLBuilder.build_select_with_params`` refuses in one
    query, so this fixture is the one that exercises the two-probe merge.
    """
    from adbc_poolhouse import DuckDBConfig

    from semolina.config import create_engine

    engine = create_engine(DuckDBConfig(database=str(duckdb_file_backed_db), read_only=True))
    yield engine
    engine.dispose()


def committed_from_warehouse(engine: Engine, view_name: str) -> CommittedModel:
    """
    Build the committed model the generation path would write for a view, right now.

    Renders the view through the real generation path and reads the result back with the
    real parser, so the fixture cannot go stale by hand and the round trip is proven.

    Args:
        engine: A live engine.
        view_name: The view to generate for.

    Returns:
        The parsed committed model.
    """
    import tempfile
    from pathlib import Path as _Path

    from semolina.codegen.model_reader import read_committed_model
    from semolina.codegen.python_renderer import render_and_format

    source = render_and_format([engine.introspect(view_name)])
    with tempfile.TemporaryDirectory() as tmp:
        path = _Path(tmp) / "models.py"
        path.write_text(source, encoding="utf-8")
        return read_committed_model(path)[0]


def replace_annotation(model: CommittedModel, name: str, annotation: str) -> CommittedModel:
    """
    Return a copy of ``model`` with one field's annotation replaced.

    Args:
        model: The parsed committed model.
        name: The field to edit.
        annotation: The annotation to write in its place.

    Returns:
        A new model carrying the edited field.
    """
    fields = dict(model.fields)
    fields[name] = CommittedField(
        name=name,
        field_class=fields[name].field_class,
        annotation=annotation,
        source_name=fields[name].source_name,
    )
    return CommittedModel(class_name=model.class_name, view_name=model.view_name, fields=fields)


def row_named(report: Any, name: str) -> Any:
    """
    Return the report row for a field, failing the test if it is absent.

    Args:
        report: A ``ViewCheckReport``.
        name: The field name.

    Returns:
        The matching ``FieldCheckRow``.
    """
    for row in report.rows:
        if row.name == name:
            return row
    pytest.fail(f"No row for {name!r}; rows were {[r.name for r in report.rows]}")


# ---------------------------------------------------------------------------
# Live DuckDB
# ---------------------------------------------------------------------------


class TestLiveDuckDB:
    """The end-to-end comparison, against a real in-memory DuckDB semantic view."""

    def test_a_freshly_generated_model_reports_no_drift(self, probe_engine: Engine) -> None:
        """
        The D-02 worked example: generate, then check, on the same view.

        For this view the metadata route and the probe route agree on every field, so
        nothing drifts. That is a measurement, not an assumption — see
        :meth:`TestMetadataProbeDivergence.test_an_interval_column_drifts` for a live view
        where they do not.
        """
        committed = committed_from_warehouse(probe_engine, PROBE_VIEW)

        report = check_view(probe_engine, PROBE_VIEW, committed)

        assert report.has_drift is False, [
            (r.name, r.committed, r.probed) for r in report.rows if r.status == STATUS_DRIFT
        ]
        assert {r.status for r in report.rows} == {STATUS_MATCH}

    def test_every_row_carries_the_route_that_produced_it(self, probe_engine: Engine) -> None:
        committed = committed_from_warehouse(probe_engine, PROBE_VIEW)

        report = check_view(probe_engine, PROBE_VIEW, committed)

        assert {r.route for r in report.rows} == {ROUTE_EXECUTE_SCHEMA}

    def test_a_drifted_annotation_is_reported(self, probe_engine: Engine) -> None:
        committed = replace_annotation(
            committed_from_warehouse(probe_engine, PROBE_VIEW), DECIMAL_METRIC, "int | None"
        )

        report = check_view(probe_engine, PROBE_VIEW, committed)

        row = row_named(report, DECIMAL_METRIC)
        assert report.has_drift is True
        assert row.committed == "int | None"
        assert row.probed == "decimal.Decimal | None"
        assert row.status == STATUS_DRIFT

    def test_a_metric_gets_nullability_and_a_dimension_does_not(self, probe_engine: Engine) -> None:
        committed = committed_from_warehouse(probe_engine, PROBE_VIEW)

        report = check_view(probe_engine, PROBE_VIEW, committed)

        assert row_named(report, DECIMAL_METRIC).probed == "decimal.Decimal | None"
        assert row_named(report, "region").probed == "str"

    def test_a_field_missing_from_the_committed_model_is_drift(self, probe_engine: Engine) -> None:
        committed = committed_from_warehouse(probe_engine, PROBE_VIEW)
        fields = dict(committed.fields)
        del fields["region"]
        trimmed = CommittedModel(
            class_name=committed.class_name, view_name=committed.view_name, fields=fields
        )

        report = check_view(probe_engine, PROBE_VIEW, trimmed)

        row = row_named(report, "region")
        assert row.committed == ABSENT
        assert row.probed == "str"
        assert row.status == STATUS_DRIFT
        assert report.has_drift is True

    def test_a_field_absent_from_the_warehouse_is_drift(self, probe_engine: Engine) -> None:
        committed = committed_from_warehouse(probe_engine, PROBE_VIEW)
        fields = dict(committed.fields)
        fields["ghost"] = CommittedField(
            name="ghost", field_class="Metric", annotation="int | None", source_name=None
        )
        widened = CommittedModel(
            class_name=committed.class_name, view_name=committed.view_name, fields=fields
        )

        report = check_view(probe_engine, PROBE_VIEW, widened)

        row = row_named(report, "ghost")
        assert row.committed == "int | None"
        assert row.probed == ABSENT
        assert row.status == STATUS_DRIFT
        assert report.has_drift is True

    def test_an_unmapped_type_compares_as_any(self, probe_engine: Engine) -> None:
        """``region_list`` is ``list(o.region)``; neither map has an answer, so both say Any."""
        committed = committed_from_warehouse(probe_engine, PROBE_VIEW)

        report = check_view(probe_engine, PROBE_VIEW, committed)

        row = row_named(report, "region_list")
        assert row.committed == "Any | None"
        assert row.probed == "Any | None"
        assert row.status == STATUS_MATCH


class TestFactsAndMetricsAreTwoProbes:
    """``sales_view`` carries a fact and two metrics, which one query cannot select."""

    def test_the_builder_still_refuses_the_combined_query(self, sales_engine: Engine) -> None:
        """
        The reason two probes exist, asserted rather than assumed.

        If this ever stops raising, the two-probe split becomes dead weight and should be
        revisited — so the guard fails loudly instead of silently over-engineering.
        """
        from semolina.codegen.annotation_check import (
            _canonical_model,  # pyright: ignore[reportPrivateUsage]
        )

        view = sales_engine.introspect("sales_view")
        model = _canonical_model(view)
        builder = sales_engine.dialect.create_builder()
        query = (
            model.query()
            .metrics(*(getattr(model, f.name) for f in view.fields if f.field_type == "metric"))
            .dimensions(*(getattr(model, f.name) for f in view.fields if f.field_type != "metric"))
        )

        with pytest.raises(ValueError, match="facts and metrics"):
            builder.build_select_with_params(query)

    def test_check_view_completes_and_probes_both_groups(self, sales_engine: Engine) -> None:
        committed = committed_from_warehouse(sales_engine, "sales_view")

        report = check_view(sales_engine, "sales_view", committed)

        assert report.has_drift is False, [
            (r.name, r.committed, r.probed) for r in report.rows if r.status == STATUS_DRIFT
        ]
        # The fact comes from the second probe, the metrics from the first.
        assert row_named(report, "unit_price").probed == "int"
        assert row_named(report, "revenue").probed == "int | None"
        assert {r.route for r in report.rows} == {ROUTE_EXECUTE_SCHEMA}


class TestMetadataProbeDivergence:
    """D-02: where the two routes disagree, ``--check`` surfaces it rather than hiding it."""

    @pytest.fixture
    def interval_engine(self, tmp_path_factory: pytest.TempPathFactory) -> Generator[Engine]:
        """
        Yield an engine on a semantic view carrying an ``INTERVAL`` fact.

        ``_DUCKDB_TYPE_MAP['INTERVAL']`` still says ``datetime.timedelta`` and is known wrong
        (D-06, ``.planning/WINDOWS.md`` entry 6); the Arrow map answers ``None`` for
        ``month_day_nano_interval`` deliberately rather than reproduce it. This view is where
        that disagreement becomes a live, runnable ``--check`` result.
        """
        import duckdb  # pyright: ignore[reportMissingImports]
        from adbc_poolhouse import DuckDBConfig

        from semolina.config import create_engine

        db_path = tmp_path_factory.mktemp("interval_fixture") / "interval.db"
        conn = duckdb.connect(database=str(db_path))
        try:
            conn.execute("INSTALL semantic_views FROM community")
            conn.execute("LOAD semantic_views")
            conn.execute("CREATE TABLE spans (id INTEGER, span INTERVAL, region VARCHAR)")
            conn.execute("INSERT INTO spans VALUES (1, INTERVAL 3 DAY, 'US')")
            conn.execute(
                "CREATE SEMANTIC VIEW span_view AS "
                "TABLES (t AS spans PRIMARY KEY (id)) "
                "FACTS (t.span AS span) "
                "DIMENSIONS (t.region AS region)"
            )
        finally:
            conn.close()

        engine = create_engine(DuckDBConfig(database=str(db_path), read_only=True))
        yield engine
        engine.dispose()

    def test_an_interval_column_drifts(self, interval_engine: Engine) -> None:
        committed = committed_from_warehouse(interval_engine, "span_view")

        report = check_view(interval_engine, "span_view", committed)

        row = row_named(report, "span")
        assert row.committed == "datetime.timedelta"
        assert row.probed == "Any"
        assert row.status == STATUS_DRIFT
        assert report.has_drift is True


class TestMetadataFallback:
    """A ``--check`` that could not probe must say so, not quietly pass."""

    def test_metadata_fallback_is_labelled_on_every_row(
        self, probe_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _refuse(cursor: Any, sql: str, params: list[Any]) -> Any:
            raise RuntimeError("probe unavailable in this test")

        monkeypatch.setattr("semolina.codegen.annotation_check.probe_schema", _refuse)
        committed = committed_from_warehouse(probe_engine, PROBE_VIEW)

        report = check_view(probe_engine, PROBE_VIEW, committed)

        assert {r.route for r in report.rows} == {ROUTE_METADATA}
        assert report.probe_error is not None
        assert "probe unavailable" in report.probe_error

    def test_metadata_fallback_still_compares(
        self, probe_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falling back is not the same as giving up: the comparison still runs."""

        def _refuse(cursor: Any, sql: str, params: list[Any]) -> Any:
            raise RuntimeError("probe unavailable in this test")

        monkeypatch.setattr("semolina.codegen.annotation_check.probe_schema", _refuse)
        committed = replace_annotation(
            committed_from_warehouse(probe_engine, PROBE_VIEW), DECIMAL_METRIC, "int | None"
        )

        report = check_view(probe_engine, PROBE_VIEW, committed)

        assert report.has_drift is True
        assert row_named(report, DECIMAL_METRIC).probed == "decimal.Decimal | None"


class TestTheReportCarriesNoRowValues:
    """T-48-22: a ``--check`` report is likely to land in a CI log."""

    def test_no_report_field_holds_anything_but_names_types_and_routes(
        self, probe_engine: Engine
    ) -> None:
        committed = committed_from_warehouse(probe_engine, PROBE_VIEW)
        annotations = {r.committed for r in check_view(probe_engine, PROBE_VIEW, committed).rows}

        # Every seeded value in the probe fixture, none of which may appear anywhere in the
        # report. `30.75`, `100.00` and `US`/`MX`/`CA` are the rows of PROBE_SEED_DML.
        report = check_view(probe_engine, PROBE_VIEW, committed)
        rendered = " ".join(
            f"{r.name} {r.committed} {r.probed} {r.route} {r.status}" for r in report.rows
        )
        for value in ("30.75", "12.50", "100.00", "'US'", "'MX'"):
            assert value not in rendered
        assert annotations  # the report is non-empty, so the assertion above is not vacuous

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_check_view_fetches_no_data_rows(self, probe_engine: Engine) -> None:
        """
        With every fetch of a non-catalogue statement poisoned, ``check_view`` completes.

        TYPE-07's "without executing a query for rows", made runnable — and scoped to what
        it can mean. ``check_view`` calls ``engine.introspect()``, which fetches *catalogue*
        rows from ``DESCRIBE SEMANTIC VIEW`` exactly as ``semolina codegen`` already does.
        The guarantee is about the view's **data**: nothing ever fetches from the
        ``semantic_view(...)`` SELECT the probe resolves a schema for.
        """
        committed = committed_from_warehouse(probe_engine, PROBE_VIEW)

        assert check_view(probe_engine, PROBE_VIEW, committed).has_drift is False

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_the_fetch_guard_is_not_vacuous(self, probe_engine: Engine) -> None:
        """Fetching from the probe's own query under the guard must fail."""
        from type_fidelity_probe import probe_sql_all

        sql, params = probe_sql_all()

        with probe_engine.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params or None)
            with pytest.raises(AssertionError, match="fetched data rows"):
                cursor.fetch_arrow_table()


# ---------------------------------------------------------------------------
# Snowflake, from the committed recording
# ---------------------------------------------------------------------------

SNOWFLAKE_PROBE_CASSETTE = (
    "tests/integration/cassettes/integration/test_type_fidelity/test_snowflake_probe/"
    "adbc_driver_snowflake.dbapi"
)
"""The recorded ``sales_view`` query whose result schema this half reads."""

SNOWFLAKE_VIEW = IntrospectedView(
    view_name="sales_view",
    class_name="SalesView",
    fields=[
        IntrospectedField(
            name="revenue",
            field_type="metric",
            data_type="decimal.Decimal",
            raw_type='{"type": "FIXED", "scale": 0}',
        ),
        IntrospectedField(name="country", field_type="dimension", data_type="str"),
    ],
)
"""
The introspection half, derived from the DDL the cassette was recorded against.

``tests/integration/conftest.py`` creates ``revenue NUMBER, country VARCHAR``; a bare
``NUMBER`` is ``NUMBER(38,0)``, which Snowflake reports as ``{"type": "FIXED", "scale": 0}``
and 48-03 maps to ``decimal.Decimal``. Derived rather than read from a warehouse because
**no Snowflake introspection cassette exists** — the narrowing this module's docstring records.
"""


def _recorded_schema() -> pyarrow.Schema:
    """
    Read the Snowflake recording's real result schema.

    Returns:
        The recorded Arrow schema: ``AGG("REVENUE")`` as ``decimal128(38, 0)`` and
        ``COUNTRY`` as ``string``.
    """
    import pathlib

    import pyarrow.ipc

    path = pathlib.Path(SNOWFLAKE_PROBE_CASSETTE) / "000_result.arrow"
    with pyarrow.ipc.open_file(path) as reader:
        return reader.read_all().schema


class _RecordedCursor:
    """A cursor that answers ``adbc_execute_schema`` from the committed recording."""

    def __init__(self, schema: pyarrow.Schema) -> None:
        self._schema = schema

    def adbc_execute_schema(self, sql: str, params: list[Any]) -> pyarrow.Schema:
        return self._schema

    def close(self) -> None:
        return None


class _RecordedConnection:
    """A one-shot connection handing out :class:`_RecordedCursor`."""

    def __init__(self, schema: pyarrow.Schema) -> None:
        self._schema = schema

    def cursor(self) -> _RecordedCursor:
        return _RecordedCursor(self._schema)

    def __enter__(self) -> _RecordedConnection:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _RecordedEngine(Engine):
    """
    A real :class:`~semolina.engines.base.Engine` whose connection replays the recording.

    Subclasses ``Engine`` rather than duck-typing it, which keeps the comparison core honest:
    it may only use the public engine surface. The dialect is a real ``SnowflakeDialect``, so
    the SQL that gets built and the result-column names that get resolved (``AGG("REVENUE")``)
    come from the shipped dialect rather than from this test. There is no pool — nothing here
    opens a connection to anything.
    """

    def __init__(self, view: IntrospectedView, schema: pyarrow.Schema) -> None:
        from semolina.engines.sql import SnowflakeDialect

        super().__init__(pool=None, dialect=SnowflakeDialect())
        self._view = view
        self._schema = schema

    def introspect(self, view_name: str) -> IntrospectedView:
        return self._view

    def connect(self) -> _RecordedConnection:
        return _RecordedConnection(self._schema)


def _snowflake_committed(revenue_annotation: str) -> CommittedModel:
    """
    Build a hand-written committed model for the recorded Snowflake view.

    Args:
        revenue_annotation: The annotation to commit for the metric.

    Returns:
        The committed model.
    """
    return CommittedModel(
        class_name="SalesView",
        view_name="sales_view",
        fields={
            "revenue": CommittedField(
                name="revenue",
                field_class="Metric",
                annotation=revenue_annotation,
                source_name=None,
            ),
            "country": CommittedField(
                name="country", field_class="Dimension", annotation="str", source_name=None
            ),
        },
    )


class TestSnowflakeFromTheCommittedRecording:
    """The comparison core over Snowflake's real recorded Arrow types."""

    def test_the_recording_carries_the_types_this_test_relies_on(self) -> None:
        """Guard the fixture: if the recording changes, this says so first."""
        schema = _recorded_schema()

        assert str(schema.field('AGG("REVENUE")').type) == "decimal128(38, 0)"
        assert str(schema.field("COUNTRY").type) == "string"

    def test_a_matching_annotation_reports_no_drift(self) -> None:
        engine = _RecordedEngine(SNOWFLAKE_VIEW, _recorded_schema())

        report = check_view(engine, "sales_view", _snowflake_committed("decimal.Decimal | None"))

        assert report.has_drift is False, [
            (r.name, r.committed, r.probed) for r in report.rows if r.status == STATUS_DRIFT
        ]
        assert row_named(report, "revenue").probed == "decimal.Decimal | None"
        assert row_named(report, "country").probed == "str"
        assert {r.route for r in report.rows} == {ROUTE_EXECUTE_SCHEMA}

    def test_a_drifted_annotation_is_reported(self) -> None:
        engine = _RecordedEngine(SNOWFLAKE_VIEW, _recorded_schema())

        report = check_view(engine, "sales_view", _snowflake_committed("int | None"))

        assert report.has_drift is True
        row = row_named(report, "revenue")
        assert row.committed == "int | None"
        assert row.probed == "decimal.Decimal | None"
