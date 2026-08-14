"""
End-to-end tests for ``.into(DTO)`` against a live in-memory DuckDB semantic view.

Covers DTO-01 (Pydantic instances matched by column name), DTO-03 (a mismatched DTO raises
rather than producing a silently wrong value), DTO-04 (``Any``-annotated and partially-typed
models), and RESULT-02's guard helper.

Record/replay contract: this module runs **live, in-process**. It records nothing and replays
nothing, and it must never carry ``pytest.mark.adbc_cassette``. ``adbc_auto_patch`` in
``pyproject.toml`` lists ``adbc_driver_manager.dbapi``, which DuckDB also routes through, and
``adbc_dialect`` maps that same module to the ``databricks`` sqlglot dialect — so a marked
DuckDB test would be diverted into cassette replay *and* have its SQL normalised as Databricks.

Everything is asserted **by value, from the real driver path**. The headline claim of this
phase is that a ``DECIMAL(38, 2)`` metric reaches a ``decimal.Decimal``-annotated DTO field as
a real :class:`decimal.Decimal`, and the only way to know that is to run the query and call
:func:`isinstance` on what comes back. A table lookup would prove that Semolina agrees with
itself.

Test classes:

- ``TestIntoDecimalRoundTrip`` — DTO-01's headline: the decimal metric, both directions.
- ``TestIntoSchemaMismatch`` — DTO-03: what the pre-check refuses, and what it lets through.
- ``TestIntoFieldPresence`` — D-07 and D-08: extra columns ignored, defaults honoured.
- ``TestIntoEdgeShapes`` — zero rows, ``Any`` fields, NULL values.
- ``TestRequire`` — the ``find_spec`` guard's two branches.
"""

from __future__ import annotations

import decimal
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pydantic
import pytest
from pydantic import ValidationError
from type_fidelity_probe import (
    PROBE_VIEW_NAME,
    TypeFidelityView,
    make_probe_engine,
)

from semolina.exceptions import SemolinaMissingDependencyError, SemolinaSchemaMismatchError

if TYPE_CHECKING:
    from collections.abc import Generator

    from semolina.cursor import SemolinaCursor
    from semolina.engines.base import Engine

pytest.importorskip("adbc_driver_duckdb")
pytest.importorskip("arrowmodel")

pytestmark = pytest.mark.unit

DECIMAL_FIELD = "total_order_value"
"""The ``SUM(DECIMAL(10, 2))`` metric, which arrives as ``decimal128(38, 2)``."""

UNMATCHED_REGION = "ZZ-NO-SUCH-REGION"
"""A dimension value no seed row carries, used to produce a zero-row result."""


@pytest.fixture
def probe_engine() -> Generator[Engine, None, None]:
    """
    Yield the probe's own in-memory DuckDB engine, closing its pool on teardown.

    Mirrors the register/unregister/close symmetry of ``tests/conftest.py``'s ``duckdb_pool``,
    minus the registry step: these tests execute through ``engine.execute(...)`` and never
    resolve an engine by name.
    """
    from adbc_poolhouse import close_pool

    engine = make_probe_engine()
    yield engine
    close_pool(engine._pool)


def _decimal_cursor(engine: Engine) -> SemolinaCursor:
    """
    Execute the region-by-decimal-metric query and return its open cursor.

    Args:
        engine: The probe engine.

    Returns:
        An open :class:`~semolina.cursor.SemolinaCursor`. The caller closes it.
    """
    query = (
        TypeFidelityView.query()
        .metrics(TypeFidelityView.total_order_value)
        .dimensions(TypeFidelityView.region)
    )
    return engine.execute(query)


class TestIntoDecimalRoundTrip:
    """DTO-01: a live decimal metric reaches a Decimal-annotated field as a Decimal."""

    def test_into_returns_model_instances(self, probe_engine: Engine) -> None:
        """.into() returns instances of the requested model, one per result row."""

        class SalesDTO(pydantic.BaseModel):
            region: str
            total_order_value: decimal.Decimal

        with _decimal_cursor(probe_engine) as cursor:
            rows = cursor.into(SalesDTO)

        assert rows, "The probe fixture seeds three regions; the result was empty"
        assert all(isinstance(row, SalesDTO) for row in rows)
        assert {row.region for row in rows} == {"US", "MX", "CA"}

    def test_decimal_metric_arrives_as_a_real_decimal(self, probe_engine: Engine) -> None:
        """
        The headline claim, asserted by isinstance on a value from the real driver path.

        ``total_order_value`` is ``SUM(o.order_total)`` over a ``DECIMAL(10, 2)`` column, which
        the warehouse widens to ``decimal128(38, 2)``. 47-DECISIONS.md Decision 1 exists so
        that column reaches the user as a :class:`decimal.Decimal` and not a float; this is
        that claim measured, end to end, through ``.into()``.
        """
        with _decimal_cursor(probe_engine) as cursor:
            arrow_type = str(dict((d[0], d[1]) for d in cursor.description or [])[DECIMAL_FIELD])
            rows = cursor.into(SalesDecimalDTO)

        assert arrow_type == "decimal128(38, 2)", (
            f"The fixture no longer produces the decimal shape under test: {arrow_type}"
        )

        by_region = {row.region: row.total_order_value for row in rows}
        assert isinstance(by_region["US"], decimal.Decimal)
        assert by_region["US"] == decimal.Decimal("43.25")

    def test_validate_true_also_returns_decimals(self, probe_engine: Engine) -> None:
        """The validated path preserves the Decimal when the annotation is right."""

        class NullableSalesDTO(pydantic.BaseModel):
            region: str
            total_order_value: decimal.Decimal | None

        with _decimal_cursor(probe_engine) as cursor:
            rows = cursor.into(NullableSalesDTO, validate=True)

        by_region = {row.region: row.total_order_value for row in rows}
        assert isinstance(by_region["US"], decimal.Decimal)
        assert by_region["US"] == decimal.Decimal("43.25")

    def test_validate_true_rejects_a_null_the_pre_check_allows(self, probe_engine: Engine) -> None:
        """
        ``validate=True`` refuses a NULL in a non-optional field; the pre-check does not.

        Measured, and recorded because it is the one thing the validated path catches that the
        structural pre-check deliberately does not. D-09 declines to check nullability at all:
        Phase 47 measured the Arrow ``nullable`` flag as True for every DuckDB field including
        ``COUNT``, so treating "result nullable, field not ``| None``" as a mismatch would flag
        essentially every field of every query. The flag carries no information.

        The accepted consequence is exactly this asymmetry. The probe's ``CA`` group
        aggregates nothing, so ``total_order_value`` is NULL there; the fast path puts ``None``
        into a ``decimal.Decimal`` field and says nothing, while the validated path raises
        pydantic's own ``ValidationError``. Neither behaviour is a bug, and this test pins both
        so a future change to either has to be deliberate.
        """
        with _decimal_cursor(probe_engine) as cursor:
            fast_rows = cursor.into(SalesDecimalDTO)

        assert {row.region: row.total_order_value for row in fast_rows}["CA"] is None

        with (
            _decimal_cursor(probe_engine) as cursor,
            pytest.raises(pydantic.ValidationError, match="total_order_value"),
        ):
            cursor.into(SalesDecimalDTO, validate=True)


class SalesDecimalDTO(pydantic.BaseModel):
    """The correct DTO for the probe's decimal metric."""

    region: str
    total_order_value: decimal.Decimal


class SalesFloatDTO(pydantic.BaseModel):
    """
    The DTO-03 headline case: a money column declared ``float``.

    Refused on the fast path (nothing would convert it) and coerced under ``validate=True``
    (Pydantic converts, accepting the precision loss the author asked for).
    """

    region: str
    total_order_value: float


class SalesIntDTO(pydantic.BaseModel):
    """A money column declared ``int`` — a narrowing Pydantic refuses on either path."""

    region: str
    total_order_value: int


class SalesOptionalFloatDTO(pydantic.BaseModel):
    """
    ``float | None`` — the coercion case with nullability taken out of the question.

    The probe view's ``CA`` region has a NULL metric, and ``validate=True`` enforces
    nullability where the structural check deliberately does not (D-09). Declaring the field
    optional isolates the type narrowing under test from that separate concern.
    """

    region: str
    total_order_value: float | None


class TestIntoSchemaMismatch:
    """DTO-03: the fast path requires exact types; the validated path coerces instead."""

    def test_decimal_into_float_raises(self, probe_engine: Engine) -> None:
        """
        A decimal128 column declared ``float`` raises on the fast path, naming both types.

        arrowmodel does not catch this: ``model_construct`` converts nothing, so the field
        would simply hold a ``Decimal`` in violation of its own annotation — and the same
        model then yields a ``Decimal`` from ``model_dump()`` and a lossy float from
        ``model_dump_json()``. The pre-check is the only guard on this path.
        """
        with (
            _decimal_cursor(probe_engine) as cursor,
            pytest.raises(SemolinaSchemaMismatchError) as excinfo,
        ):
            cursor.into(SalesFloatDTO)

        message = str(excinfo.value)
        assert DECIMAL_FIELD in message
        assert "decimal128" in message
        assert "decimal.Decimal" in message
        assert "float" in message

    def test_decimal_into_float_coerces_with_validate_true(self, probe_engine: Engine) -> None:
        """
        ``validate=True`` performs the narrowing instead of refusing it.

        This is the deliberate-coercion path: the author asked for a ``float`` and Pydantic
        converts each value, accepting the precision loss that implies. The structural type
        comparison is skipped precisely so it cannot veto a conversion that works. The
        counterpart — a narrowing Pydantic *cannot* perform — is
        ``test_decimal_into_int_still_raises_with_validate_true`` below.
        """
        with _decimal_cursor(probe_engine) as cursor:
            rows = cursor.into(SalesOptionalFloatDTO, validate=True)

        values = [getattr(row, DECIMAL_FIELD) for row in rows]
        coerced = [value for value in values if value is not None]
        assert coerced, "expected at least one non-null metric from the probe view"
        assert all(isinstance(value, float) for value in coerced), (
            f"expected coerced floats, got {[type(v).__name__ for v in coerced]}"
        )
        # The fast path would have left decimal.Decimal here — that is the whole difference.
        assert not any(isinstance(value, decimal.Decimal) for value in coerced)

    def test_decimal_into_int_still_raises_with_validate_true(self, probe_engine: Engine) -> None:
        """
        A narrowing Pydantic cannot perform still fails, as a ``ValidationError``.

        ``validate=True`` is "coerce where legal", not "accept anything": Pydantic refuses to
        drop the fractional part of a decimal silently. Pinned so that skipping the structural
        check is never mistaken for removing type enforcement from the validated path.
        """
        with _decimal_cursor(probe_engine) as cursor, pytest.raises(ValidationError):
            cursor.into(SalesIntDTO, validate=True)

    def test_no_row_value_reaches_the_message(self, probe_engine: Engine) -> None:
        """
        The error names types and columns, never data.

        The pre-check reads ``description`` and fetches nothing, so no value is even in scope.
        Asserted rather than assumed, because an error message is exactly the place a value
        leaks into a log.
        """
        with (
            _decimal_cursor(probe_engine) as cursor,
            pytest.raises(SemolinaSchemaMismatchError) as excinfo,
        ):
            cursor.into(SalesFloatDTO)

        message = str(excinfo.value)
        for seeded_value in ("43.25", "100.00", "30.75", "12.50"):
            assert seeded_value not in message, (
                f"A row value {seeded_value!r} reached the error message: {message}"
            )

    def test_every_mismatch_is_reported_at_once(self, probe_engine: Engine) -> None:
        """
        Two wrong fields produce ONE error naming both (D-11).

        The whole schema is in hand up front, so reporting one field at a time would only cost
        the user a fix-and-rerun cycle per field.
        """

        class DoublyWrongDTO(pydantic.BaseModel):
            region: int
            total_order_value: float

        with (
            _decimal_cursor(probe_engine) as cursor,
            pytest.raises(SemolinaSchemaMismatchError) as excinfo,
        ):
            cursor.into(DoublyWrongDTO)

        message = str(excinfo.value)
        assert "region" in message
        assert DECIMAL_FIELD in message
        assert "2 mismatched fields" in message

    def test_int_column_into_float_field_is_a_mismatch(self, probe_engine: Engine) -> None:
        """
        An int64 metric declared ``float`` is refused too (PD-02): there is no numeric tower.

        ``issubclass(int, float)`` is False in Python, and the fast path really does leave an
        ``int`` in the field — the same class of silent wrong-typing as Decimal into float.
        """

        class CountDTO(pydantic.BaseModel):
            n_order_totals: float

        query = TypeFidelityView.query().metrics(TypeFidelityView.n_order_totals)
        with (
            probe_engine.execute(query) as cursor,
            pytest.raises(SemolinaSchemaMismatchError) as excinfo,
        ):
            cursor.into(CountDTO)

        assert "n_order_totals" in str(excinfo.value)

    def test_unmapped_arrow_type_passes_without_a_verdict(self, probe_engine: Engine) -> None:
        """
        A ``list<string>`` column reaches a ``list[str]`` field without the pre-check objecting.

        ``arrow_type_to_runtime_type`` answers None for a list, which the pre-check reads as
        "no opinion". Failing here would break a conversion arrowmodel performs correctly.
        """

        class RegionsDTO(pydantic.BaseModel):
            region_list: list[str]

        query = TypeFidelityView.query().metrics(TypeFidelityView.region_list)
        with probe_engine.execute(query) as cursor:
            rows = cursor.into(RegionsDTO)

        assert rows
        assert all(isinstance(value, str) for value in rows[0].region_list)


class TestIntoFieldPresence:
    """D-07 and D-08: unclaimed columns are ignored, defaults make a field optional."""

    def test_undeclared_result_columns_are_ignored(self, probe_engine: Engine) -> None:
        """A DTO declaring only one of two result columns converts fine (D-07)."""

        class RegionOnlyDTO(pydantic.BaseModel):
            region: str

        with _decimal_cursor(probe_engine) as cursor:
            rows = cursor.into(RegionOnlyDTO)

        assert {row.region for row in rows} == {"US", "MX", "CA"}

    def test_required_field_with_no_column_raises(self, probe_engine: Engine) -> None:
        """A required field the result has no column for is an error naming it (D-08)."""

        class ExtraFieldDTO(pydantic.BaseModel):
            region: str
            nonexistent_column: str

        with (
            _decimal_cursor(probe_engine) as cursor,
            pytest.raises(SemolinaSchemaMismatchError) as excinfo,
        ):
            cursor.into(ExtraFieldDTO)

        message = str(excinfo.value)
        assert "nonexistent_column" in message
        assert "region" in message, "The message should list the columns the result does have"

    def test_field_with_a_default_is_optional_in_the_result(self, probe_engine: Engine) -> None:
        """A missing column with a default converts, and the default is filled (D-08)."""

        class DefaultedDTO(pydantic.BaseModel):
            region: str
            nonexistent_column: str = "fallback"

        with _decimal_cursor(probe_engine) as cursor:
            rows = cursor.into(DefaultedDTO)

        assert rows
        assert all(row.nonexistent_column == "fallback" for row in rows)

    def test_none_default_is_also_a_default(self, probe_engine: Engine) -> None:
        """``= None`` counts as a default, so the field is optional in the result."""

        class NullableDTO(pydantic.BaseModel):
            region: str
            nonexistent_column: str | None = None

        with _decimal_cursor(probe_engine) as cursor:
            rows = cursor.into(NullableDTO)

        assert rows
        assert all(row.nonexistent_column is None for row in rows)

    def test_optional_without_a_default_is_still_required(self, probe_engine: Engine) -> None:
        """
        ``str | None`` with no default is required, and its absence is an error.

        The test is ``FieldInfo.is_required()``, not "the annotation admits None" — pydantic
        treats an un-defaulted optional as required, and so does arrowmodel.
        """

        class UndefaultedOptionalDTO(pydantic.BaseModel):
            region: str
            nonexistent_column: str | None

        with _decimal_cursor(probe_engine) as cursor, pytest.raises(SemolinaSchemaMismatchError):
            cursor.into(UndefaultedOptionalDTO)


class TestIntoEdgeShapes:
    """Zero rows, Any-annotated fields, and a NULL in a nullable column."""

    def test_zero_row_result_returns_an_empty_list(self, probe_engine: Engine) -> None:
        """.into() on a query matching nothing returns [] and raises nothing."""
        query = (
            TypeFidelityView.query()
            .metrics(TypeFidelityView.total_order_value)
            .dimensions(TypeFidelityView.region)
            .where(TypeFidelityView.region == UNMATCHED_REGION)
        )

        with probe_engine.execute(query) as cursor:
            rows = cursor.into(SalesDecimalDTO)

        assert rows == []

    def test_any_annotated_field_passes_the_pre_check(self, probe_engine: Engine) -> None:
        """
        DTO-04: an ``Any`` field accepts any Arrow type.

        ``Any`` is the only shape needing an explicit special case — it is not a class on
        3.11 (where ``issubclass`` raises) and is one on 3.14 (where ``issubclass`` quietly
        answers False), so falling through would turn a deliberate opt-out into a crash or a
        false mismatch depending on the interpreter.
        """

        class UntypedDTO(pydantic.BaseModel):
            region: Any
            total_order_value: Any

        with _decimal_cursor(probe_engine) as cursor:
            rows = cursor.into(UntypedDTO)

        by_region = {row.region: row.total_order_value for row in rows}
        assert isinstance(by_region["US"], decimal.Decimal)

    def test_object_annotated_field_passes_without_a_special_case(
        self, probe_engine: Engine
    ) -> None:
        """``object`` is a real class and everything subclasses it, so it opts out for free."""

        class ObjectDTO(pydantic.BaseModel):
            total_order_value: object

        with _decimal_cursor(probe_engine) as cursor:
            rows = cursor.into(ObjectDTO)

        assert rows

    def test_null_in_a_nullable_column_arrives_as_none(self, probe_engine: Engine) -> None:
        """
        The ``CA`` group aggregates nothing, so its decimal metric arrives as None.

        Nullability is not checked at all (D-09): the Arrow nullable flag reads True for every
        DuckDB field including COUNT, so it carries no signal. What matters is that the value
        path passes the NULL through as ``None`` rather than substituting a zero.
        """

        class NullableMetricDTO(pydantic.BaseModel):
            region: str
            total_order_value: decimal.Decimal | None

        with _decimal_cursor(probe_engine) as cursor:
            rows = cursor.into(NullableMetricDTO)

        by_region = {row.region: row.total_order_value for row in rows}
        assert by_region["CA"] is None
        assert isinstance(by_region["US"], decimal.Decimal)

    def test_alias_resolves_the_column_key(self, probe_engine: Engine) -> None:
        """
        A field renamed through ``validation_alias`` matches on the alias, not the field name.

        This is the shape every Snowflake result needs, where the column is expression text
        like ``AGG("REVENUE")`` rather than a Python identifier. Proven here on DuckDB because
        the mechanism is arrowmodel's, not the warehouse's — and the pre-check has to resolve
        on the same key or it would reject a DTO arrowmodel converts fine.
        """

        class AliasedDTO(pydantic.BaseModel):
            revenue: decimal.Decimal = pydantic.Field(validation_alias=DECIMAL_FIELD)

        with _decimal_cursor(probe_engine) as cursor:
            rows = cursor.into(AliasedDTO)

        assert rows
        assert all(isinstance(row.revenue, decimal.Decimal) for row in rows if row.revenue)

    def test_view_name_is_the_probe_fixture(self) -> None:
        """Guard: these tests describe ``type_fidelity_view`` and nothing else."""
        assert TypeFidelityView._view_name == PROBE_VIEW_NAME


class TestRequire:
    """RESULT-02: the optional-dependency guard's two branches and its message."""

    def test_raises_when_the_package_is_absent(self) -> None:
        """_require() raises SemolinaMissingDependencyError naming the installable extra."""
        from semolina.exceptions import _require

        with (
            patch("importlib.util.find_spec", return_value=None),
            pytest.raises(SemolinaMissingDependencyError) as excinfo,
        ):
            _require("nosuchpkg", "polars")

        message = str(excinfo.value)
        assert "nosuchpkg" in message
        assert "pip install semolina[polars]" in message

    def test_returns_none_when_the_package_is_present(self) -> None:
        """_require() is a no-op for an installed package."""
        from semolina.exceptions import _require

        with patch("importlib.util.find_spec", return_value=object()):
            assert _require("sys", "polars") is None

    def test_reaches_a_real_installed_package_unpatched(self) -> None:
        """Unpatched, the guard agrees with reality: ``sys`` is importable."""
        from semolina.exceptions import _require

        assert _require("sys", "polars") is None
