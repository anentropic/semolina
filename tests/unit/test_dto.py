"""
Fake-driven tests for ``iter_into`` and for the structural pre-check's full rule set.

The warehouse-backed half of this phase lives in ``tests/unit/test_dto_duckdb.py``, which
proves that a real ``DECIMAL(38, 2)`` reaches a ``decimal.Decimal`` field through a real ADBC
driver. This module is its complement and deliberately uses no warehouse at all: every case
here is about *timing* or about *which schemas the pre-check will and will not object to*, and
neither is observable through a query. A fake reader can be asked how many batches it has
handed out; DuckDB cannot. A hand-built ``description`` can pair an Arrow ``struct`` with a
``str``-annotated field in one line; producing that from SQL would take a fixture.

Covers DTO-02 (streaming one instance at a time), DTO-03 (mismatches raise) on the streaming
path, DTO-04 (``Any``-annotated and partially-typed models), and decisions D-05 (raise at the
call), D-07 (extra columns ignored), D-08 (required means ``is_required()``), D-09 (nullability
not consulted), D-10 (subtype-tolerant comparison), D-11 (every mismatch in one error) and
PD-02 (``int`` into ``float`` is a mismatch).

Test classes:

- ``TestIterIntoFailFast`` — D-05: the raise lands on the call expression, not on ``next()``.
- ``TestIterIntoLaziness`` — DTO-02: one consumed instance costs exactly one batch.
- ``TestIterIntoDelivery`` — instances not lists, empty streams, holes, drained readers.
- ``TestIterIntoValidate`` — the flag reaches the converter's constructor.
- ``TestPresenceAndDefaults`` — D-08, including ``str | None`` with no default.
- ``TestExtraColumns`` — D-07.
- ``TestTypeComparison`` — D-10 and PD-02, on both sides of each rule.
- ``TestUnionAndAny`` — both union spellings, ``Any``, ``object``.
- ``TestQuietCases`` — the confidence boundary: what the pre-check refuses to have an opinion on.
- ``TestUnsupportedAliasConstructs`` — ALIAS-03: what arrowmodel refuses, refused here first.
- ``TestAliasGenerator`` — ALIAS-03's model-level construct, which no field-level rule can see.
- ``TestJsonValueSpellings`` — why the docs must say ``pydantic.JsonValue``.
- ``TestAliasResolution`` — the Snowflake ``AGG("REVENUE")`` trap.
- ``TestPopulateByName`` — ALIAS-02: the field name is a second key, not a replaced one.
- ``TestReportShape`` — D-11.
- ``TestUntypedModels`` — DTO-04, and why "untyped" has to mean ``Any``-annotated.
"""

from __future__ import annotations

import datetime  # noqa: TC003
import decimal
import importlib
import importlib.util
import types
from typing import TYPE_CHECKING, Any, Union
from unittest.mock import patch

import pyarrow
import pydantic
import pytest

from semolina.cursor import SemolinaCursor
from semolina.dto import check_result_schema
from semolina.exceptions import SemolinaMissingDependencyError, SemolinaSchemaMismatchError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

pytest.importorskip("arrowmodel")

pytestmark = pytest.mark.unit


SALES_SCHEMA = pyarrow.schema(
    [
        pyarrow.field("region", pyarrow.string()),
        pyarrow.field("revenue", pyarrow.int64()),
    ]
)
"""The two-column schema the streaming tests read, kept trivial on purpose."""


def describe(schema: pyarrow.Schema) -> list[tuple[Any, ...]]:
    """
    Build a DBAPI ``description`` from an Arrow schema.

    ADBC fills the second element of each 7-tuple with a real ``pyarrow.DataType``, which is
    the only element the pre-check reads. The remaining five are ``None``, as ADBC leaves them.

    Args:
        schema: The Arrow schema to describe.

    Returns:
        One 7-tuple per field, in schema order.
    """
    return [(field.name, field.type, None, None, None, None, None) for field in schema]


def columns(*pairs: tuple[str, pyarrow.DataType]) -> list[tuple[Any, ...]]:
    """
    Build a ``description`` straight from ``(name, arrow_type)`` pairs.

    The pre-check tests use this rather than :func:`describe` so each case is one line and
    reads as the schema it is testing.

    Args:
        pairs: ``(column_name, arrow_type)`` in result order.

    Returns:
        One 7-tuple per pair.
    """
    return [(name, dtype, None, None, None, None, None) for name, dtype in pairs]


def batch(rows: list[dict[str, Any]], schema: pyarrow.Schema = SALES_SCHEMA) -> pyarrow.RecordBatch:
    """
    Build a ``RecordBatch`` from row dicts.

    Args:
        rows: The rows, possibly empty — an empty list produces a legitimate zero-row batch,
            which is one of the shapes ``iter_into`` must skip rather than stop on.
        schema: The Arrow schema. Defaults to :data:`SALES_SCHEMA`.

    Returns:
        A ``pyarrow.RecordBatch``.
    """
    return pyarrow.RecordBatch.from_pylist(rows, schema=schema)


class CountingReader:
    """
    Duck-typed fake of ``pyarrow.RecordBatchReader`` that counts what it hands out.

    Duck-typed rather than subclassed because pyarrow forbids subclassing
    ``RecordBatchReader``, and counted rather than merely sequenced because "streams without
    materializing the whole table" is a claim about *how many batches were pulled*. Asserting
    on the number of results returned would pass just as well against an implementation that
    read everything up front.
    """

    def __init__(
        self,
        batches: Iterable[pyarrow.RecordBatch],
        drain_error: BaseException | None = None,
    ) -> None:
        """
        Initialize with the batches to serve and how to behave once they run out.

        Args:
            batches: The batches to hand out, in order.
            drain_error: Raised instead of ``StopIteration`` once the batches are exhausted.
                ADBC drivers surface a drained reader as ``OSError`` rather than
                ``StopIteration``, and ``iter_into`` must normalize both to termination.
        """
        self._batches = list(batches)
        self._position = 0
        self.batches_read = 0
        self._drain_error = drain_error

    def read_next_batch(self) -> pyarrow.RecordBatch:
        """
        Return the next batch, incrementing the pull counter.

        Returns:
            The next ``pyarrow.RecordBatch``.

        Raises:
            StopIteration: When exhausted and no ``drain_error`` was configured.
            BaseException: The configured ``drain_error``, when exhausted and one was given.
        """
        if self._position >= len(self._batches):
            if self._drain_error is not None:
                raise self._drain_error
            raise StopIteration
        result = self._batches[self._position]
        self._position += 1
        self.batches_read += 1
        return result


class FakeCursor:
    """
    Minimal duck-typed fake of an ADBC cursor, counting reader creations.

    ``fetch_record_batch_calls`` is what makes the fail-fast test non-vacuous: "raised before
    any batch moved" is weaker than "raised before a reader even existed", and only the second
    distinguishes an eager pre-check from a lazy one that happens to fail on the first pull.
    """

    def __init__(
        self,
        description: list[tuple[Any, ...]] | None,
        reader: CountingReader | None = None,
        fetch_error: BaseException | None = None,
    ) -> None:
        """
        Initialize with a description and an optional reader.

        Args:
            description: The DBAPI description the pre-check reads.
            reader: The reader ``fetch_record_batch()`` hands back. ``None`` for tests that
                must never reach it.
            fetch_error: Raised by ``fetch_record_batch()`` instead of returning a reader.
                Some ADBC drivers report an already-drained result when the reader is
                *created* rather than on the first pull, and that is not a shape
                :class:`CountingReader` can express: it never gets constructed.
        """
        self.description = description
        self.reader = reader
        self.fetch_error = fetch_error
        self.fetch_record_batch_calls = 0
        self.closed = False

    def fetch_record_batch(self) -> CountingReader:
        """
        Return the configured reader, counting the call.

        Returns:
            The ``CountingReader`` this fake was built with.

        Raises:
            BaseException: The configured ``fetch_error``, when the test supplied one.
            AssertionError: If the test configured no reader — reaching here means the code
                under test created a stream it was supposed to refuse.
        """
        self.fetch_record_batch_calls += 1
        if self.fetch_error is not None:
            raise self.fetch_error
        if self.reader is None:
            raise AssertionError("fetch_record_batch() reached on a cursor that has no reader")
        return self.reader

    def close(self) -> None:
        """Mark the fake closed, so ``SemolinaCursor.close()`` has something to call."""
        self.closed = True


def make_cursor(
    description: list[tuple[Any, ...]] | None,
    reader: CountingReader | None = None,
    fetch_error: BaseException | None = None,
) -> tuple[SemolinaCursor, FakeCursor]:
    """
    Wrap a :class:`FakeCursor` in a real :class:`~semolina.cursor.SemolinaCursor`.

    The wrapper is real rather than mocked because the behaviour under test is the wrapper's.
    The connection is a stub carrying only ``close()``, which is all ``__del__`` needs to stay
    quiet when a test drops the cursor without closing it.

    Args:
        description: The DBAPI description the pre-check will read.
        reader: The reader to serve, or ``None`` for tests that must not reach one.
        fetch_error: Raised from ``fetch_record_batch()`` instead of serving a reader.

    Returns:
        The ``SemolinaCursor`` and the ``FakeCursor`` underneath it, so a test can assert on
        the fake's counters.
    """
    inner = FakeCursor(description, reader, fetch_error)
    conn = types.SimpleNamespace(close=lambda: None)
    return SemolinaCursor(cursor=inner, conn=conn, pool=None), inner


def find_spec_without(missing: str) -> Callable[..., Any]:
    """
    Build a ``find_spec`` replacement that reports exactly one package absent.

    A blanket ``return_value=None`` would make the *pyarrow* guard fire first, so a test
    written that way would assert the wrong error's message and still pass.

    Args:
        missing: The importable name to report as absent.

    Returns:
        A drop-in for ``importlib.util.find_spec`` that defers to the real one for every other
        name.
    """
    real = importlib.util.find_spec

    def fake(name: str, package: str | None = None) -> Any:
        if name == missing:
            return None
        return real(name, package)

    return fake


class SalesDTO(pydantic.BaseModel):
    """A DTO that matches :data:`SALES_SCHEMA` exactly."""

    region: str
    revenue: int


class MistypedSalesDTO(pydantic.BaseModel):
    """A DTO declaring the ``int64`` revenue column as ``str`` — a confident mismatch."""

    region: str
    revenue: str


# -- DTO-02 / D-05: iter_into --------------------------------------------------------------


class TestIterIntoFailFast:
    """D-05: the error lands on the call expression, before any stream exists."""

    def test_iter_into_with_a_mismatched_dto_raises_at_call(self) -> None:
        """
        A bad DTO raises inside ``iter_into(...)`` itself — no ``next()``, no ``list()``.

        Written with no iteration of any kind on purpose. A version that wrapped
        ``list(cursor.iter_into(...))`` in ``pytest.raises`` would pass identically against a
        bare generator function, which is exactly the implementation D-05 forbids.
        """
        cursor, inner = make_cursor(describe(SALES_SCHEMA), reader=None)

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            cursor.iter_into(MistypedSalesDTO)

        assert inner.fetch_record_batch_calls == 0
        message = str(excinfo.value)
        assert "revenue" in message
        assert "int64" in message

    def test_iter_into_is_not_a_generator_function(self) -> None:
        """
        ``iter_into`` returns an iterator it did not itself yield from.

        The structural counterpart to the test above: a generator function's return value is
        a generator *object*, and the method's own frame never runs. Asserting the returned
        object is not the method's own generator pins the shape rather than the symptom.
        """
        import inspect

        assert not inspect.isgeneratorfunction(SemolinaCursor.iter_into)
        assert inspect.isgeneratorfunction(SemolinaCursor._iter_into_impl)  # noqa: SLF001

    def test_iter_into_without_arrowmodel_raises_at_call(self) -> None:
        """A missing arrowmodel is reported at the call, naming the extra that fixes it."""
        cursor, inner = make_cursor(describe(SALES_SCHEMA), reader=None)

        with (
            patch("importlib.util.find_spec", side_effect=find_spec_without("arrowmodel")),
            pytest.raises(SemolinaMissingDependencyError) as excinfo,
        ):
            cursor.iter_into(SalesDTO)

        assert inner.fetch_record_batch_calls == 0
        assert "pip install semolina[arrowmodel]" in str(excinfo.value)

    def test_iter_into_without_pyarrow_raises_before_reading_description(self) -> None:
        """
        The pyarrow guard fires first, so ``description`` is never touched without it.

        Reading ``description`` on an ADBC cursor with no pyarrow raises ADBC's own
        ``ProgrammingError`` from a ``_NoOpBackend``, which names neither Semolina nor the
        extra to install.
        """
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader=None)

        with (
            patch("importlib.util.find_spec", side_effect=find_spec_without("pyarrow")),
            pytest.raises(SemolinaMissingDependencyError) as excinfo,
        ):
            cursor.iter_into(SalesDTO)

        assert "pip install semolina[pyarrow]" in str(excinfo.value)


class TestIterIntoLaziness:
    """DTO-02: streaming, measured on a counter rather than inferred from a result length."""

    def test_iter_into_lazy_first_item_pulls_exactly_one_batch(self) -> None:
        """Taking one instance from a two-batch reader pulls one batch, not two."""
        reader = CountingReader(
            [
                batch([{"region": "US", "revenue": 1}, {"region": "CA", "revenue": 2}]),
                batch([{"region": "MX", "revenue": 3}, {"region": "DE", "revenue": 4}]),
            ]
        )
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        stream = cursor.iter_into(SalesDTO)
        assert reader.batches_read == 0

        first = next(iter(stream))

        assert isinstance(first, SalesDTO)
        assert reader.batches_read == 1

    def test_iter_into_lazy_reader_is_untouched_until_the_first_next(self) -> None:
        """Holding the iterator without consuming it pulls nothing and creates no reader."""
        reader = CountingReader([batch([{"region": "US", "revenue": 1}])])
        cursor, inner = make_cursor(describe(SALES_SCHEMA), reader)

        _stream = cursor.iter_into(SalesDTO)

        assert inner.fetch_record_batch_calls == 0
        assert reader.batches_read == 0


class TestIterIntoDelivery:
    """What comes out, and what the odd stream shapes do."""

    def test_iter_into_yields_model_instances_not_lists(self) -> None:
        """Each item is a single DTO, so ``for dto in ...`` needs no unpacking (D-03)."""
        reader = CountingReader(
            [batch([{"region": "US", "revenue": 1}, {"region": "CA", "revenue": 2}])]
        )
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        items = list(cursor.iter_into(SalesDTO))

        assert [type(item) for item in items] == [SalesDTO, SalesDTO]
        assert [item.region for item in items] == ["US", "CA"]

    def test_iter_into_skips_a_zero_row_batch_mid_stream(self) -> None:
        """A hole in the stream is skipped, not treated as its end (mirrors ``__next__``)."""
        reader = CountingReader(
            [
                batch([{"region": "US", "revenue": 1}, {"region": "CA", "revenue": 2}]),
                batch([]),
                batch([{"region": "MX", "revenue": 3}, {"region": "DE", "revenue": 4}]),
            ]
        )
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        items = list(cursor.iter_into(SalesDTO))

        assert len(items) == 4
        assert [item.region for item in items] == ["US", "CA", "MX", "DE"]

    def test_iter_into_over_an_empty_reader_yields_nothing(self) -> None:
        """A result with no batches at all yields nothing and raises nothing."""
        reader = CountingReader([])
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        assert list(cursor.iter_into(SalesDTO)) == []

    def test_iter_into_treats_a_drained_reader_oserror_as_termination(self) -> None:
        """An ``OSError`` from a drained reader ends iteration rather than propagating."""
        reader = CountingReader(
            [batch([{"region": "US", "revenue": 1}])],
            drain_error=OSError("reader is drained"),
        )
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        items = list(cursor.iter_into(SalesDTO))

        assert len(items) == 1

    def test_iter_into_normalises_a_drained_reader_creation_error(self) -> None:
        """
        A driver reporting the drain when the reader is *created* also stops cleanly.

        ``__next__`` catches ``(StopIteration, OSError)`` in exactly this position, and
        ``AsyncSemolinaCursor._aiter_into_impl`` wraps its own reader creation for exactly this
        reason, so the sync streaming path was the one place that let the raw ``OSError``
        through. DuckDB does not raise here — it returns an empty stream — which is why the
        gap survived a green suite, and why the fake has to supply the shape.

        The contract this defends is the one ``howto-streaming`` states for every consumer of
        the shared stream: iterating after something else drained it yields zero rows, not an
        error.
        """
        cursor, _inner = make_cursor(
            describe(SALES_SCHEMA),
            reader=None,
            fetch_error=OSError("Attempting to execute an unsuccessful or closed query result"),
        )

        assert list(cursor.iter_into(SalesDTO)) == []


class TestIterIntoValidate:
    """The ``validate`` flag reaches the converter's *constructor*, where it lives."""

    def test_iter_into_with_validate_true_rejects_a_null_in_a_required_field(self) -> None:
        """
        ``validate=True`` catches the one thing the pre-check deliberately does not.

        Nullability is not checked structurally (D-09): the Arrow ``nullable`` flag reads True
        for every DuckDB field including ``COUNT``, so it carries no information. A NULL in a
        non-optional field is therefore the case that distinguishes the two settings, and it
        is what proves the flag was passed rather than dropped.
        """
        reader = CountingReader([batch([{"region": "US", "revenue": None}])])
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        with pytest.raises(pydantic.ValidationError):
            list(cursor.iter_into(SalesDTO, validate=True))

    def test_iter_into_with_validate_false_leaves_the_null_in_place(self) -> None:
        """The fast path performs no per-value validation, which is the contrast that matters."""
        reader = CountingReader([batch([{"region": "US", "revenue": None}])])
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        items = list(cursor.iter_into(SalesDTO))

        assert len(items) == 1
        assert items[0].revenue is None


# -- DTO-03 / D-07…D-11: the pre-check's rule set -------------------------------------------


class TestPresenceAndDefaults:
    """D-08: "required" is ``FieldInfo.is_required()``, not "has no ``= None``"."""

    def test_a_required_field_with_no_column_errors(self) -> None:
        """A declared field the result has no column for is an error when required."""

        class M(pydantic.BaseModel):
            region: str
            missing: str

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(columns(("region", pyarrow.string())), M)

        assert "missing" in str(excinfo.value)

    def test_a_missing_field_with_a_default_is_accepted(self) -> None:
        """``= "dflt"`` makes the field optional in the result, as arrowmodel also does."""

        class M(pydantic.BaseModel):
            region: str
            missing: str = "dflt"

        assert check_result_schema(columns(("region", pyarrow.string())), M) is None

    def test_a_missing_optional_field_with_a_none_default_is_accepted(self) -> None:
        """``str | None = None`` is not required, so its absence is fine."""

        class M(pydantic.BaseModel):
            region: str
            missing: str | None = None

        assert check_result_schema(columns(("region", pyarrow.string())), M) is None

    def test_an_optional_annotation_with_no_default_is_still_required(self) -> None:
        """
        ``str | None`` **without** a default is still required, and still errors.

        The trap D-08 exists to avoid: reading ``| None`` as "optional" would accept a DTO
        that arrowmodel then rejects with its own ``ValueError`` several frames later.
        """

        class M(pydantic.BaseModel):
            region: str
            missing: str | None

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(columns(("region", pyarrow.string())), M)

        assert "missing" in str(excinfo.value)


class TestExtraColumns:
    """D-07: the result may offer more than the DTO asks for."""

    def test_a_column_no_field_declares_is_ignored(self) -> None:
        """One DTO serves several queries; a query may gain a column without breaking it."""

        class M(pydantic.BaseModel):
            region: str

        description = columns(
            ("region", pyarrow.string()),
            ("revenue", pyarrow.int64()),
            ("order_count", pyarrow.int64()),
        )

        assert check_result_schema(description, M) is None

    def test_a_dto_with_no_fields_at_all_accepts_any_result(self) -> None:
        """The degenerate end of the same rule: declaring nothing objects to nothing."""

        class M(pydantic.BaseModel):
            pass

        assert check_result_schema(columns(("region", pyarrow.string())), M) is None


class TestTypeComparison:
    """D-10 and PD-02: subtype-tolerant ``issubclass``, with no numeric tower."""

    def test_decimal_column_into_a_decimal_field_passes(self) -> None:
        """The headline positive: a warehouse decimal annotated as ``decimal.Decimal``."""

        class M(pydantic.BaseModel):
            revenue: decimal.Decimal

        assert check_result_schema(columns(("revenue", pyarrow.decimal128(38, 2))), M) is None

    def test_decimal_into_float_raises(self) -> None:
        """
        The case Phase 47's whole Decimal policy exists to protect, on the fast path.

        ``model_construct`` converts nothing, so without this check the field would hold a
        ``Decimal`` in violation of its own ``float`` annotation — and the same instance then
        serializes as a ``Decimal`` through ``model_dump()`` and as a lossy float through
        ``model_dump_json()``. The check is the only guard on this path.
        """

        class M(pydantic.BaseModel):
            revenue: float

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(columns(("revenue", pyarrow.decimal128(38, 2))), M)

        message = str(excinfo.value)
        assert "revenue" in message
        assert "decimal128(38, 2)" in message
        assert "float" in message

    def test_type_check_is_skipped_when_types_are_not_checked(self) -> None:
        """
        ``check_types=False`` drops the type comparison — the validated path's contract.

        Under ``validate=True`` Pydantic converts per value and raises where it cannot, so
        running this comparison first would refuse narrowings that demonstrably work.
        """

        class M(pydantic.BaseModel):
            revenue: float

        assert (
            check_result_schema(
                columns(("revenue", pyarrow.decimal128(38, 2))), M, check_types=False
            )
            is None
        )

    def test_missing_column_still_raises_when_types_are_not_checked(self) -> None:
        """
        ``check_types=False`` drops only the type half. Presence is checked either way.

        A required field with no matching column is not a coercion decision — no conversion
        invents a column — so opting out of type comparison must not opt out of this. Semolina
        also names the field, the column key and what the result carried, where arrowmodel's
        own ``ValueError`` names only the column.
        """

        class M(pydantic.BaseModel):
            revenue: float
            currency: str

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(
                columns(("revenue", pyarrow.decimal128(38, 2))), M, check_types=False
            )

        message = str(excinfo.value)
        assert "currency" in message
        assert "no such column" in message
        # The type half stayed silent: only the missing column is reported.
        assert "decimal128" not in message

    def test_decimal_into_float_raises_only_on_the_fast_path(self) -> None:
        """
        Through ``iter_into``: refused with ``validate=False``, permitted with ``validate=True``.

        Driven through the cursor rather than the pre-check directly, because the claim is
        about the public surface and ``validate=`` is a parameter of that surface only. The
        validated call is asserted to *not* raise; whether Pydantic then coerces the value is
        pinned against a live driver in ``test_dto_duckdb.py``.
        """

        class M(pydantic.BaseModel):
            revenue: float

        schema = pyarrow.schema([pyarrow.field("revenue", pyarrow.decimal128(38, 2))])

        reader = CountingReader([batch([{"revenue": decimal.Decimal("43.25")}], schema)])
        cursor, inner = make_cursor(describe(schema), reader)
        with pytest.raises(SemolinaSchemaMismatchError):
            cursor.iter_into(M, validate=False)
        assert inner.fetch_record_batch_calls == 0

        reader = CountingReader([batch([{"revenue": decimal.Decimal("43.25")}], schema)])
        cursor, inner = make_cursor(describe(schema), reader)
        cursor.iter_into(M, validate=True)  # must not raise
        # Still lazy: returning the iterator pulls no batch on either setting.
        assert inner.fetch_record_batch_calls == 0

    def test_int_column_into_a_float_field_raises(self) -> None:
        """
        PD-02, recorded as a decision rather than discovered as a surprise.

        ``issubclass(int, float)`` is False — Python has no nominal numeric tower — and the
        fast path really does leave an ``int`` in a field declared ``float``, which is the
        same class of silent wrong-typing as the Decimal case. Strict here, and documented.
        """

        class M(pydantic.BaseModel):
            revenue: float

        with pytest.raises(SemolinaSchemaMismatchError):
            check_result_schema(columns(("revenue", pyarrow.int64())), M)

    def test_int_column_into_an_int_field_passes(self) -> None:
        """The other side of PD-02."""

        class M(pydantic.BaseModel):
            revenue: int

        assert check_result_schema(columns(("revenue", pyarrow.int64())), M) is None

    def test_bool_column_into_an_int_field_passes(self) -> None:
        """``issubclass(bool, int)`` is True, and subtype tolerance is intended."""

        class M(pydantic.BaseModel):
            flag: int

        assert check_result_schema(columns(("flag", pyarrow.bool_())), M) is None

    def test_timestamp_column_into_a_date_field_passes(self) -> None:
        """``datetime`` is a subclass of ``date``, so widening in that direction is fine."""

        class M(pydantic.BaseModel):
            occurred: datetime.date

        assert check_result_schema(columns(("occurred", pyarrow.timestamp("us"))), M) is None

    def test_date_column_into_a_datetime_field_raises(self) -> None:
        """The reverse direction is not a subtype, and is refused."""

        class M(pydantic.BaseModel):
            occurred: datetime.datetime

        with pytest.raises(SemolinaSchemaMismatchError):
            check_result_schema(columns(("occurred", pyarrow.date32())), M)

    def test_string_column_into_an_int_field_raises(self) -> None:
        """The plainest mismatch there is, kept as the control case."""

        class M(pydantic.BaseModel):
            region: int

        with pytest.raises(SemolinaSchemaMismatchError):
            check_result_schema(columns(("region", pyarrow.string())), M)


class TestUnionAndAny:
    """Both union spellings unwrap, and the two opt-outs both pass."""

    def test_both_union_spellings_unwrap_to_the_same_verdict(self) -> None:
        """
        Both spellings of an optional annotation reach the same verdict.

        On Python 3.11 these are genuinely different objects: ``get_origin(int | None)`` is
        ``types.UnionType`` while ``get_origin(Union[int, None])`` is ``typing.Union``, which
        is why the pre-check tests for both origins rather than one. On 3.14 PEP 604's
        unification has collapsed them — ``typing.Union`` *is* ``types.UnionType`` there,
        measured — so this test is a tautology on the newer interpreter and load-bearing on
        the older one. Both are in the CI matrix, so it stays.

        Spelled ``Union[int, None]`` rather than ``Optional[int]``, which is the same object
        (``==`` holds and both give the same ``get_origin``). The ``Optional`` spelling needs
        a ``noqa`` whose rule code differs between the ruff pinned in
        ``.pre-commit-config.yaml`` (UP007) and the newer ruff in the venv (UP045), so
        whichever one the ``noqa`` does not name rewrites it to ``int | None`` and quietly
        turns this class into a duplicate of its sibling. Measured, twice.
        """

        class Pep604(pydantic.BaseModel):
            revenue: int | None

        class Typing(pydantic.BaseModel):
            revenue: Union[int, None]  # noqa: UP007

        description = columns(("revenue", pyarrow.int64()))

        assert check_result_schema(description, Pep604) is None
        assert check_result_schema(description, Typing) is None

    def test_a_union_where_no_arm_accepts_still_raises(self) -> None:
        """Dropping ``NoneType`` must not turn a union into an unconditional pass."""

        class M(pydantic.BaseModel):
            revenue: Union[str, bytes]  # noqa: UP007 — exercises the typing.Union origin

        with pytest.raises(SemolinaSchemaMismatchError):
            check_result_schema(columns(("revenue", pyarrow.int64())), M)

    def test_an_any_annotated_field_passes_against_anything(self) -> None:
        """``typing.Any`` is the deliberate opt-out, and needs its own branch to stay one."""

        class M(pydantic.BaseModel):
            revenue: Any

        assert check_result_schema(columns(("revenue", pyarrow.decimal128(38, 2))), M) is None

    def test_an_object_annotated_field_passes_against_anything(self) -> None:
        """``object`` is a real class, so the same opt-out falls out of ``issubclass``."""

        class M(pydantic.BaseModel):
            revenue: object

        assert check_result_schema(columns(("revenue", pyarrow.decimal128(38, 2))), M) is None


class TestQuietCases:
    """
    The confidence boundary, pinned on both sides.

    A verdict is worth having only where it is right. Every false positive here is a call
    site that worked yesterday and raises today, so the pre-check reports a mismatch only
    when both sides reduce to a class, and says nothing otherwise.
    """

    def test_a_struct_column_produces_no_verdict(self) -> None:
        """
        An Arrow struct against a ``str`` field is *not* reported, deliberately.

        ``arrow_type_to_python`` maps no struct, and arrowmodel converts a struct into a
        nested ``BaseModel`` correctly. Objecting here would break conversions that work, and
        arrowmodel's own message for the genuinely wrong case is already actionable.
        """

        class M(pydantic.BaseModel):
            payload: str

        description = columns(("payload", pyarrow.struct([("a", pyarrow.int64())])))

        assert check_result_schema(description, M) is None

    def test_a_list_column_produces_no_verdict(self) -> None:
        """Same rule, same reason: ``list[str]`` from an Arrow list converts fine."""

        class M(pydantic.BaseModel):
            tags: list[str]

        assert check_result_schema(columns(("tags", pyarrow.list_(pyarrow.string()))), M) is None

    def test_an_unmapped_arrow_type_produces_no_verdict(self) -> None:
        """An interval maps to no Python class, so no opinion is available to give."""

        class M(pydantic.BaseModel):
            span: str

        description = columns(("span", pyarrow.month_day_nano_interval()))

        assert check_result_schema(description, M) is None

    def test_a_description_entry_without_an_arrow_type_produces_no_verdict(self) -> None:
        """
        A non-ADBC cursor puts a DBAPI type code in ``d[1]``; a verdict read off one is invented.

        The column still counts as *present*, though — folding the two together would report
        every field of such a result as missing, turning "no opinion" into a wall of false
        positives.
        """

        class M(pydantic.BaseModel):
            revenue: decimal.Decimal

        description: list[tuple[Any, ...]] = [("revenue", 1042, None, None, None, None, None)]

        assert check_result_schema(description, M) is None

    def test_a_none_description_produces_no_verdict(self) -> None:
        """A cursor that has not executed has nothing to disagree with."""

        class M(pydantic.BaseModel):
            revenue: decimal.Decimal

        assert check_result_schema(None, M) is None


class TestUnsupportedAliasConstructs:
    """
    ALIAS-03: the alias forms arrowmodel refuses outright, which the pre-check must refuse too.

    An earlier rule skipped an ``AliasChoices`` / ``AliasPath`` field with no verdict, on the
    rationale that "a verdict about a column the converter may never look at is worse than no
    verdict". That rationale is factually wrong. arrowmodel does not look at a different
    column: ``_build_field_map`` raises ``NotImplementedError`` for either construct before any
    column is consulted, and it does so inside ``ArrowModelConverter.__init__`` — which
    ``iter_into`` reaches from *inside* the generator body. Skipping therefore did not produce
    "no verdict"; it produced D-05's raise landing several frames away, as a bare third-party
    error naming neither Semolina nor a fix.
    """

    AMBIGUOUS_ALIASES: list[pydantic.AliasChoices | pydantic.AliasPath] = [
        pydantic.AliasChoices("revenue", "REVENUE"),
        pydantic.AliasPath("revenue", 0),
    ]
    """Both constructs arrowmodel names in its ALIAS-03 ``NotImplementedError``."""

    @staticmethod
    def model_with(
        validation_alias: pydantic.AliasChoices | pydantic.AliasPath,
    ) -> type[pydantic.BaseModel]:
        """
        Build a one-field DTO carrying the given ``validation_alias``.

        Args:
            validation_alias: The alias construct to attach to ``revenue``.

        Returns:
            The model class.
        """

        class M(pydantic.BaseModel):
            revenue: float = pydantic.Field(validation_alias=validation_alias)

        return M

    @pytest.mark.parametrize("alias", AMBIGUOUS_ALIASES, ids=["choices", "path"])
    def test_the_pre_check_refuses_the_model(
        self, alias: pydantic.AliasChoices | pydantic.AliasPath
    ) -> None:
        """The construct is named in the message, along with the remedy that works."""
        model = TestUnsupportedAliasConstructs.model_with(alias)

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(columns(("revenue", pyarrow.decimal128(38, 2))), model)

        message = str(excinfo.value)
        assert type(alias).__name__ in message
        assert "revenue" in message
        assert "plain string alias" in message

    @pytest.mark.parametrize("alias", AMBIGUOUS_ALIASES, ids=["choices", "path"])
    def test_the_refusal_survives_check_types_false(
        self, alias: pydantic.AliasChoices | pydantic.AliasPath
    ) -> None:
        """
        ``validate=True`` does not make the construct supported — the converter still refuses.

        This half must not be gated on ``check_types``, unlike the type comparison: Pydantic
        owning per-value conversion changes nothing about a field map arrowmodel will not
        build.
        """
        model = TestUnsupportedAliasConstructs.model_with(alias)

        with pytest.raises(SemolinaSchemaMismatchError):
            check_result_schema(
                columns(("revenue", pyarrow.decimal128(38, 2))),
                model,
                check_types=False,
            )

    def test_iter_into_raises_at_the_call_and_never_builds_a_converter(self) -> None:
        """
        D-05 for the alias case: the raise lands on ``iter_into(...)``, not on ``next()``.

        The reader assertion is what makes this non-vacuous. arrowmodel's own
        ``NotImplementedError`` comes from the converter's constructor, which
        ``_iter_into_impl`` runs in the generator body — so a version that merely "raises
        eventually" would pass a test written with ``list(...)`` inside ``pytest.raises``.
        """
        model = TestUnsupportedAliasConstructs.model_with(
            pydantic.AliasChoices("revenue", "REVENUE")
        )
        cursor, inner = make_cursor(columns(("revenue", pyarrow.int64())), reader=None)

        with pytest.raises(SemolinaSchemaMismatchError):
            cursor.iter_into(model)

        assert inner.fetch_record_batch_calls == 0

    @pytest.mark.parametrize("alias", AMBIGUOUS_ALIASES, ids=["choices", "path"])
    def test_the_refusal_does_not_need_a_description(
        self, alias: pydantic.AliasChoices | pydantic.AliasPath
    ) -> None:
        """
        A ``None`` description is not a reason to let the construct through.

        The model-level ``alias_generator`` rule is checked before ``description`` is read,
        but this per-field one sat inside the loop a ``None`` description returns before
        reaching — so the two halves of ALIAS-03 disagreed about a case they are written as
        one rule. There is no schema here to be uncertain about: arrowmodel refuses to build
        a field map for this model against *any* result, including none.
        """
        model = TestUnsupportedAliasConstructs.model_with(alias)

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(None, model)

        assert type(alias).__name__ in str(excinfo.value)

    def test_iter_into_over_a_none_description_still_raises_at_the_call(self) -> None:
        """
        The user-visible consequence: otherwise ``NotImplementedError`` lands on ``next()``.

        Measured before the fix, through this same cursor: ``iter_into`` returned an iterator
        and the first ``next()`` raised ``NotImplementedError: Field 'revenue' uses
        AliasChoices as validation_alias, which is not supported`` — a bare third-party error
        several frames from the call, naming neither Semolina nor a remedy. That is exactly
        the D-05 failure this rule exists to close, surviving in the one corner it did not
        reach.
        """
        model = TestUnsupportedAliasConstructs.model_with(
            pydantic.AliasChoices("revenue", "REVENUE")
        )
        reader = CountingReader([batch([{"region": "US", "revenue": 1}])])
        cursor, inner = make_cursor(None, reader)

        with pytest.raises(SemolinaSchemaMismatchError):
            cursor.iter_into(model)

        assert inner.fetch_record_batch_calls == 0

    def test_a_clean_model_still_passes_a_none_description_quietly(self) -> None:
        """
        The control: hoisting the alias scan must not turn ``None`` into a verdict of its own.

        ``TestQuietCases`` owns this claim for the general case; it is repeated here because
        the hoist is what could break it, and a rule that refused every model on an
        unexecuted cursor would pass every other test in this class.
        """
        assert check_result_schema(None, SalesDTO) is None

    def test_arrowmodel_really_does_refuse_the_same_models(self) -> None:
        """
        The behaviour being mirrored, asserted against arrowmodel rather than described.

        Without this, the pre-check's refusal is a claim about a third party that nothing in
        the suite would notice going stale — and "we refuse what they refuse" is the entire
        justification for refusing at all.
        """
        from arrowmodel import ArrowModelConverter

        for alias in TestUnsupportedAliasConstructs.AMBIGUOUS_ALIASES:
            model = TestUnsupportedAliasConstructs.model_with(alias)
            with pytest.raises(NotImplementedError) as excinfo:
                ArrowModelConverter(model)
            assert type(alias).__name__ in str(excinfo.value)


class TestAliasGenerator:
    """
    ALIAS-03's third construct, and the only one that reaches the pre-check disguised.

    Pydantic materializes a generated alias onto each ``FieldInfo``, so nothing about the
    fields looks unusual: they carry plain string aliases, and the pre-check happily resolves
    them. The model is nonetheless unconvertible — arrowmodel reads ``alias_generator`` off
    ``model_config`` and refuses before it looks at a single field.

    That disguise is what makes the case worth its own class. Without a model-level check the
    two reachable outcomes are both wrong: a "no such column" report blaming the generated
    spelling and never mentioning the generator (when the result spells columns as the field
    names), or — once ``populate_by_name`` makes the field name acceptable too — the pre-check
    passing the model straight to arrowmodel to fail.
    """

    @staticmethod
    def generated_model(
        generator: Callable[[str], str] | pydantic.AliasGenerator = str.upper,
        *,
        populate_by_name: bool = False,
    ) -> type[pydantic.BaseModel]:
        """
        Build a one-field DTO whose aliases come from a generator.

        Args:
            generator: The ``alias_generator`` to set. Both the bare-callable and the
                ``AliasGenerator`` object spelling are legal pydantic, and arrowmodel refuses
                either.
            populate_by_name: Whether to also accept the field name as a column key, which is
                what turns the refusal into the case a field-level rule would wave through.

        Returns:
            The model class.
        """

        class G(pydantic.BaseModel):
            model_config = pydantic.ConfigDict(
                alias_generator=generator,
                populate_by_name=populate_by_name,
            )
            revenue: int

        return G

    def test_the_generated_alias_really_is_materialized_onto_the_field(self) -> None:
        """
        The premise, asserted rather than assumed: this is why a field-level rule cannot see it.

        If pydantic ever stopped materializing the alias, the model-level check would be
        redundant rather than load-bearing, and this test is what would say so.
        """
        model = TestAliasGenerator.generated_model()

        assert model.model_fields["revenue"].alias == "REVENUE"

    def test_the_pre_check_names_the_generator_and_the_remedy(self) -> None:
        """A message blaming a column spelling would send the reader after the wrong thing."""
        model = TestAliasGenerator.generated_model()

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(columns(("revenue", pyarrow.int64())), model)

        message = str(excinfo.value)
        assert "alias_generator" in message
        assert "per-field" in message
        assert "no such column" not in message

    def test_it_is_refused_even_when_every_field_would_otherwise_resolve(self) -> None:
        """
        The case ALIAS-02 support would otherwise turn into a *pass*, which is worse.

        With ``populate_by_name`` set, ``resolve_column_keys`` accepts the field name, so the
        result below satisfies every field and the structural check has nothing to say. Only
        the model-level rule stops this reaching arrowmodel's own ``NotImplementedError``.
        """
        model = TestAliasGenerator.generated_model(populate_by_name=True)

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(columns(("revenue", pyarrow.int64())), model)

        assert "alias_generator" in str(excinfo.value)

    def test_the_refusal_survives_check_types_false(self) -> None:
        """``validate=True`` does not teach the converter a construct it does not implement."""
        model = TestAliasGenerator.generated_model()

        with pytest.raises(SemolinaSchemaMismatchError):
            check_result_schema(columns(("REVENUE", pyarrow.int64())), model, check_types=False)

    def test_iter_into_raises_at_the_call_and_never_builds_a_converter(self) -> None:
        """D-05: on the call expression, before a reader exists."""
        model = TestAliasGenerator.generated_model(populate_by_name=True)
        cursor, inner = make_cursor(columns(("revenue", pyarrow.int64())), reader=None)

        with pytest.raises(SemolinaSchemaMismatchError):
            cursor.iter_into(model)

        assert inner.fetch_record_batch_calls == 0

    def test_arrowmodel_really_does_refuse_both_generator_spellings(self) -> None:
        """
        The anchor. Both the bare-callable and the ``AliasGenerator`` object form are refused.

        Measured against arrowmodel 1.0.0: ``NotImplementedError: AliasGenerator on G is not
        supported. Use explicit per-field aliases instead.`` — raised for either spelling,
        because arrowmodel tests the config key rather than its value's type.
        """
        from arrowmodel import ArrowModelConverter

        generators: list[Callable[[str], str] | pydantic.AliasGenerator] = [
            str.upper,
            pydantic.AliasGenerator(validation_alias=str.upper),
        ]
        for generator in generators:
            model = TestAliasGenerator.generated_model(generator)
            with pytest.raises(NotImplementedError) as excinfo:
                ArrowModelConverter(model)
            assert "AliasGenerator" in str(excinfo.value)


class TestJsonValueSpellings:
    """Why the DTO docs must say ``pydantic.JsonValue`` and never ``semolina.JsonValue``."""

    def test_pydantic_jsonvalue_produces_no_verdict(self) -> None:
        """
        ``pydantic.JsonValue`` is a ``TypeAliasType``: legal, opaque, and left alone.

        ``get_origin()`` is ``None`` and ``get_args()`` is ``()``, so a naive union walk sees
        an object it cannot reduce — which is precisely when the pre-check stays quiet.
        """

        class M(pydantic.BaseModel):
            payload: pydantic.JsonValue

        assert check_result_schema(columns(("payload", pyarrow.string())), M) is None

    def test_semolina_jsonvalue_cannot_be_a_dto_annotation_at_all(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        ``semolina.JsonValue`` recurses pydantic to death at *class creation*.

        It is a self-referential **string** alias, which pydantic re-expands at every nesting
        level instead of turning into a definition-ref. It stays correct for generated
        ``SemanticView`` models, which are read as text and never imported by pydantic — but a
        DTO annotated with it never comes into existence. Recorded here so the docs claim is
        backed by the suite rather than by a paragraph.

        The DTO is written to a real module and imported, rather than declared inside this
        function, because the failure needs the annotation to actually resolve: pydantic looks
        a ``ForwardRef`` up in ``sys.modules[cls.__module__]``, so a class defined in a local
        scope leaves the model deferred and unbuilt and raises nothing at all. Measured both
        ways — the function-local spelling passes this test for the wrong reason. The module
        cannot live on disk under ``tests/`` either: pytest runs with ``--doctest-modules``
        over ``testpaths``, which would import it at collection time and take the whole suite
        down with it.
        """
        probe = tmp_path / "semolina_jsonvalue_dto_probe.py"
        probe.write_text(
            "import pydantic\n"
            "\n"
            "from semolina import JsonValue\n"
            "\n"
            "\n"
            "class VariantDTO(pydantic.BaseModel):\n"
            "    payload: JsonValue\n",
            encoding="utf-8",
        )
        monkeypatch.syspath_prepend(str(tmp_path))

        with pytest.raises(RecursionError):
            importlib.import_module("semolina_jsonvalue_dto_probe")


class TestAliasResolution:
    """Pitfall 2: a Snowflake result column is not a Python identifier."""

    SNOWFLAKE_COLUMN = 'AGG("REVENUE")'
    """The canonical Snowflake result-column spelling, read from a committed cassette."""

    def test_a_validation_alias_resolves_the_snowflake_column(self) -> None:
        """``Field(validation_alias='AGG("REVENUE")')`` is what makes a DTO portable."""

        class M(pydantic.BaseModel):
            revenue: decimal.Decimal = pydantic.Field(
                validation_alias=TestAliasResolution.SNOWFLAKE_COLUMN
            )

        description = columns((TestAliasResolution.SNOWFLAKE_COLUMN, pyarrow.decimal128(38, 0)))

        assert check_result_schema(description, M) is None

    def test_a_plain_alias_resolves_the_snowflake_column_too(self) -> None:
        """``alias=`` is arrowmodel's second choice, so the pre-check honours it second too."""

        class M(pydantic.BaseModel):
            revenue: decimal.Decimal = pydantic.Field(alias=TestAliasResolution.SNOWFLAKE_COLUMN)

        description = columns((TestAliasResolution.SNOWFLAKE_COLUMN, pyarrow.decimal128(38, 0)))

        assert check_result_schema(description, M) is None

    def test_without_an_alias_the_field_is_missing_and_the_message_lists_the_columns(
        self,
    ) -> None:
        """
        A bare ``revenue`` field cannot see ``AGG("REVENUE")``, and the message says so.

        Naming the available columns is what turns this from a puzzle into a copy-paste fix,
        because the answer the user needs is the exact spelling to put in the alias.
        """

        class M(pydantic.BaseModel):
            revenue: decimal.Decimal

        description = columns((TestAliasResolution.SNOWFLAKE_COLUMN, pyarrow.decimal128(38, 0)))

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(description, M)

        message = str(excinfo.value)
        assert "revenue" in message
        assert TestAliasResolution.SNOWFLAKE_COLUMN in message
        assert "validation_alias" in message

    def test_a_mistyped_aliased_field_is_reported_under_its_column_key(self) -> None:
        """The report names both the field and the column, which differ whenever an alias does."""

        class M(pydantic.BaseModel):
            revenue: float = pydantic.Field(validation_alias=TestAliasResolution.SNOWFLAKE_COLUMN)

        description = columns((TestAliasResolution.SNOWFLAKE_COLUMN, pyarrow.decimal128(38, 0)))

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(description, M)

        message = str(excinfo.value)
        assert "revenue" in message
        assert TestAliasResolution.SNOWFLAKE_COLUMN in message


class TestPopulateByName:
    """
    ALIAS-02: ``populate_by_name`` makes the field name a *second* acceptable column key.

    arrowmodel's ``_build_field_map`` appends every field name to its lookup map when either
    ``populate_by_name`` or ``validate_by_name`` is set, so an aliased field is satisfied by a
    column spelled either way. A pre-check that resolved one key and stopped refused DTOs the
    converter handles correctly — the exact failure the pre-check exists to prevent, and one
    with no user-side workaround short of deleting the alias.
    """

    @staticmethod
    def aliased_model(config: pydantic.ConfigDict) -> type[pydantic.BaseModel]:
        """
        Build a one-field DTO whose ``revenue`` field carries ``alias='REVENUE'``.

        Args:
            config: The ``model_config`` to attach — ``populate_by_name`` or
                ``validate_by_name`` for the accepting cases, empty for the refusing one.

        Returns:
            The model class.
        """

        class M(pydantic.BaseModel):
            model_config = config
            revenue: int = pydantic.Field(alias="REVENUE")

        return M

    ACCEPTING_CONFIGS = [
        pydantic.ConfigDict(populate_by_name=True),
        pydantic.ConfigDict(validate_by_name=True),
    ]
    """Both config spellings arrowmodel reads for ALIAS-02, checked one at a time."""

    @pytest.mark.parametrize("config", ACCEPTING_CONFIGS, ids=["populate", "validate"])
    def test_a_column_spelled_as_the_field_name_is_accepted(
        self, config: pydantic.ConfigDict
    ) -> None:
        """Both spellings of the config flag admit the field name, as arrowmodel does."""
        model = TestPopulateByName.aliased_model(config)

        assert check_result_schema(columns(("revenue", pyarrow.int64())), model) is None

    def test_the_alias_is_still_accepted(self) -> None:
        """Adding a key must not remove one: the alias remains the first choice."""
        model = TestPopulateByName.aliased_model(pydantic.ConfigDict(populate_by_name=True))

        assert check_result_schema(columns(("REVENUE", pyarrow.int64())), model) is None

    def test_the_alias_wins_the_type_check_when_both_spellings_are_present(self) -> None:
        """
        With both columns in the result, the verdict must read the one arrowmodel will read.

        arrowmodel resolves in field-map insertion order, and the ALIAS-02 field names are
        appended *after* every alias — so the alias column wins. Measured: a result carrying
        ``REVENUE=9`` and ``revenue=1`` converts to ``revenue=9``. A pre-check that typed the
        field against the wrong column would object to a conversion that works.
        """
        model = TestPopulateByName.aliased_model(pydantic.ConfigDict(populate_by_name=True))
        description = columns(
            ("REVENUE", pyarrow.int64()),
            ("revenue", pyarrow.string()),
        )

        assert check_result_schema(description, model) is None

    def test_without_the_flag_the_field_name_is_not_accepted(self) -> None:
        """
        The new key is conditional, not unconditional — arrowmodel raises here too.

        Measured against arrowmodel 1.0.0: ``ValueError: Arrow schema is missing required
        columns: ['REVENUE']``. The pre-check must keep saying so, in its own better words.
        """
        model = TestPopulateByName.aliased_model(pydantic.ConfigDict())

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(columns(("revenue", pyarrow.int64())), model)

        assert "REVENUE" in str(excinfo.value)

    def test_iter_into_converts_a_populate_by_name_dto_end_to_end(self) -> None:
        """
        The pre-check and the converter agree, driven through a real ``iter_into``.

        The assertion that matters is that this does not raise: before the fix the pre-check
        refused at the ``iter_into(...)`` call, while arrowmodel — reached here for real —
        builds the instances without complaint.
        """
        model = TestPopulateByName.aliased_model(pydantic.ConfigDict(populate_by_name=True))
        schema = pyarrow.schema([pyarrow.field("revenue", pyarrow.int64())])
        reader = CountingReader([batch([{"revenue": 1}, {"revenue": 2}], schema=schema)])
        cursor, _ = make_cursor(describe(schema), reader)

        instances = list(cursor.iter_into(model))

        assert [instance.model_dump()["revenue"] for instance in instances] == [1, 2]


class TestDuplicateResultColumns:
    """
    A result column name that occurs twice is, to the converter, a name that occurs zero times.

    arrowmodel resolves each lookup name with ``pyarrow.Schema.get_field_index``, which returns
    ``-1`` for an ambiguous name exactly as it does for an absent one, and then reports the
    field as a missing required column. Measured against arrowmodel 1.0.0 and pyarrow: a
    two-column ``['x', 'x']`` schema against ``class M: x: int`` raises ``ValueError: Arrow
    schema is missing required columns: ['x']. Available columns: ['x', 'x']`` — under
    ``validate=True`` as well, and even when both ``x`` columns carry the same Arrow type.

    So the pre-check must not treat a duplicated name as *present*. Doing so cost three
    separate wrong answers, all of them reachable from one badly aliased query:

    * ``typed_columns`` kept the last entry per name, so the type half was decided against a
      column arrowmodel would never have read.
    * A DTO the converter refuses was passed through, putting the refusal back inside the
      generator body for ``iter_into`` — the D-05 timing failure the alias findings fixed.
    * That refusal, when it arrived, was ``ValueError`` naming ``['x']`` as missing while
      listing ``['x', 'x']`` as available.

    Treating the name as unresolvable instead makes all four of the converter's behaviours
    fall out for free: fall-through to the next lookup key, a defaulted field left at its
    default, an untouched verdict for fields that do not name the duplicate, and a refusal at
    the call for a required one.
    """

    @staticmethod
    def duplicated() -> list[tuple[Any, ...]]:
        """
        Build a description carrying ``x`` twice at different types, plus a clean ``y``.

        Returns:
            The three-entry description. ``y`` is there so the "only the field that names
            the duplicate is affected" claim has something to be true of.
        """
        return columns(
            ("x", pyarrow.int64()),
            ("x", pyarrow.string()),
            ("y", pyarrow.string()),
        )

    def test_arrowmodel_really_does_refuse_a_duplicated_column(self) -> None:
        """
        The behaviour being mirrored, asserted against arrowmodel rather than described.

        Checked at both settings of ``validate``, because that is what decides whether the
        pre-check's half may be gated on ``check_types``.
        """
        from arrowmodel import model_convert

        schema = pyarrow.schema(
            [
                pyarrow.field("x", pyarrow.int64()),
                pyarrow.field("x", pyarrow.string()),
            ]
        )
        table = pyarrow.Table.from_arrays(
            [pyarrow.array([1], pyarrow.int64()), pyarrow.array(["a"], pyarrow.string())],
            schema=schema,
        )

        class M(pydantic.BaseModel):
            x: int

        for validate in (False, True):
            with pytest.raises(ValueError, match="missing required columns"):
                model_convert(M, table, validate=validate)

    def test_a_duplicated_column_does_not_satisfy_a_required_field(self) -> None:
        """The field is refused, at the pre-check, rather than passed to a converter that will."""

        class M(pydantic.BaseModel):
            x: int

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(TestDuplicateResultColumns.duplicated(), M)

        assert "x" in str(excinfo.value)

    def test_the_message_says_the_name_is_duplicated_rather_than_absent(self) -> None:
        """
        "No such column" would be a lie about a result the reader can see contains it twice.

        This is the message arrowmodel's own ``ValueError`` gets wrong, and the reason for
        reporting the case here at all rather than letting that error through: the remedy is
        to alias one of the two columns in the query, which neither "missing" nor "no such
        column" points at.
        """

        class M(pydantic.BaseModel):
            x: int

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(TestDuplicateResultColumns.duplicated(), M)

        message = str(excinfo.value)
        assert "2 columns" in message
        assert "no such column" not in message
        assert "['x', 'x', 'y']" in message

    def test_the_type_half_is_not_decided_against_the_last_duplicate(self) -> None:
        """
        The old failure in its own right: ``x: int`` was reported as disagreeing with ``string``.

        ``typed_columns[name] = dtype`` kept whichever entry came last, so the verdict was
        read off a column arrowmodel would never reach. The declared type here is right for
        the *first* ``x`` and wrong for the second, so a report naming ``string`` is proof the
        wrong column was consulted.
        """

        class M(pydantic.BaseModel):
            x: int

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(TestDuplicateResultColumns.duplicated(), M)

        assert "string" not in str(excinfo.value)

    def test_the_refusal_survives_check_types_false(self) -> None:
        """
        ``validate=True`` does not make a duplicated name resolvable — arrowmodel still refuses.

        Ungated for the same reason the unsupported alias constructs are: Pydantic owning
        per-value conversion changes nothing about a column lookup that cannot be performed.
        """

        class M(pydantic.BaseModel):
            x: int

        with pytest.raises(SemolinaSchemaMismatchError):
            check_result_schema(TestDuplicateResultColumns.duplicated(), M, check_types=False)

    def test_a_field_naming_only_a_clean_column_is_unaffected(self) -> None:
        """
        The duplicate poisons its own name, not the result. Measured: arrowmodel converts this.

        Refusing the whole result would be the easy over-reaction, and it would break a DTO
        that never asks for the ambiguous column.
        """

        class M(pydantic.BaseModel):
            y: str

        assert check_result_schema(TestDuplicateResultColumns.duplicated(), M) is None

    def test_an_optional_field_whose_column_is_duplicated_is_left_at_its_default(self) -> None:
        """
        Mirrors the converter: measured, arrowmodel returns ``Opt(x=0)`` rather than raising.

        The pre-check already treats "absent" as fine for a defaulted field, and a duplicated
        name is absent as far as the lookup is concerned, so the two must agree here too.
        """

        class M(pydantic.BaseModel):
            x: int = 0

        assert check_result_schema(TestDuplicateResultColumns.duplicated(), M) is None

    def test_resolution_falls_through_to_the_next_acceptable_key(self) -> None:
        """
        A duplicated *alias* is skipped for the field name, exactly as arrowmodel skips it.

        Measured: with ``REVENUE`` twice and ``revenue`` once, arrowmodel returns
        ``M(revenue=7)`` — the value from the clean ``revenue`` column. A pre-check that
        stopped at the first key present would refuse a conversion that works, and one that
        typed the field against a ``REVENUE`` column would object to the wrong type.
        """

        class M(pydantic.BaseModel):
            model_config = pydantic.ConfigDict(populate_by_name=True)
            revenue: int = pydantic.Field(alias="REVENUE")

        description = columns(
            ("REVENUE", pyarrow.int64()),
            ("REVENUE", pyarrow.string()),
            ("revenue", pyarrow.int64()),
        )

        assert check_result_schema(description, M) is None

    def test_iter_into_raises_at_the_call_and_never_builds_a_reader(self) -> None:
        """
        D-05 for the duplicate case: arrowmodel's own refusal comes from inside the generator.

        Measured: the ``ValueError`` is raised when the converter first sees a batch, not in
        ``ArrowModelConverter.__init__`` — so it lands even later than the alias errors did,
        on the first ``next()``. The reader assertion is what makes this test non-vacuous.
        """

        class M(pydantic.BaseModel):
            x: int

        cursor, inner = make_cursor(TestDuplicateResultColumns.duplicated(), reader=None)

        with pytest.raises(SemolinaSchemaMismatchError):
            cursor.iter_into(M)

        assert inner.fetch_record_batch_calls == 0


class TestReportShape:
    """D-11: the whole schema is in hand, so listing every mismatch costs nothing."""

    def test_reports_every_mismatched_field_in_one_error(self) -> None:
        """
        Two bad fields produce one error naming both, not the first only.

        Reporting one at a time would cost a fix-and-rerun cycle per field, and every one of
        those cycles is a full query against a warehouse.
        """

        class M(pydantic.BaseModel):
            region: int
            revenue: float

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(describe(SALES_SCHEMA), M)

        message = str(excinfo.value)
        assert "region" in message
        assert "revenue" in message
        assert "2 mismatched fields" in message

    def test_reports_every_kind_of_mismatch_together(self) -> None:
        """A missing field and a mistyped field arrive in the same error, not in sequence."""

        class M(pydantic.BaseModel):
            revenue: float
            absent: str

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(columns(("revenue", pyarrow.int64())), M)

        message = str(excinfo.value)
        assert "revenue" in message
        assert "absent" in message
        assert "2 mismatched fields" in message

    def test_a_single_mismatch_reads_in_the_singular(self) -> None:
        """One field is a "field", not "1 mismatched fields"."""

        class M(pydantic.BaseModel):
            revenue: float

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(columns(("revenue", pyarrow.int64())), M)

        assert "1 mismatched field" in str(excinfo.value)

    def test_the_message_names_the_model(self) -> None:
        """The DTO's own name anchors the error when several are in play."""

        class WrongSalesDTO(pydantic.BaseModel):
            revenue: float

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(columns(("revenue", pyarrow.int64())), WrongSalesDTO)

        assert "WrongSalesDTO" in str(excinfo.value)

    def test_a_missing_column_reads_as_a_sentence(self) -> None:
        """
        The missing-column line denies the column instead of asserting it exists.

        One report template served all three reasons, so the missing case was interpolated
        into "but the column is {got}" and came out asserting the existence of a column in
        the act of denying it. The wording is the whole value of this half: the reader is
        being told which spelling to write, and a sentence they have to re-read first is a
        worse instruction than one they do not.
        """

        class M(pydantic.BaseModel):
            currency: str

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(columns(("revenue", pyarrow.int64())), M)

        message = str(excinfo.value)
        assert "but the result has no such column" in message
        assert "the column is no such column" not in message
        # The columns the result *did* carry still have to survive the rewording: they are
        # the answer the reader came for.
        assert "'revenue'" in message

    def test_the_type_line_still_says_what_the_column_is(self) -> None:
        """
        Rewording the missing case must not reword the type case, which was already right.

        The type line genuinely is talking about a column that exists, so "the column is
        int64" is the correct sentence there and the two must not converge.
        """

        class M(pydantic.BaseModel):
            revenue: float

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(columns(("revenue", pyarrow.int64())), M)

        assert "but the column is int64" in str(excinfo.value)


class TestUntypedModels:
    """DTO-04, and why "untyped model" has to mean ``Any``-annotated."""

    def test_an_all_any_untyped_model_converts_against_any_schema(self) -> None:
        """The `Any`-everywhere DTO is the escape hatch DTO-04 asks for."""

        class Untyped(pydantic.BaseModel):
            region: Any
            revenue: Any

        assert check_result_schema(describe(SALES_SCHEMA), Untyped) is None

    def test_a_partially_typed_model_is_checked_only_where_it_is_annotated(self) -> None:
        """Half-typed DTOs are useful, so the check has to tolerate them."""

        class HalfTyped(pydantic.BaseModel):
            region: str
            revenue: Any

        assert check_result_schema(describe(SALES_SCHEMA), HalfTyped) is None

    def test_a_partially_typed_model_still_raises_on_the_field_it_does_annotate(self) -> None:
        """Tolerating ``Any`` is not tolerating everything — the other half still counts."""

        class HalfTyped(pydantic.BaseModel):
            region: Any
            revenue: float

        with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
            check_result_schema(describe(SALES_SCHEMA), HalfTyped)

        assert "1 mismatched field" in str(excinfo.value)

    def test_a_genuinely_untyped_attribute_is_rejected_by_pydantic_itself(self) -> None:
        """
        A non-annotated attribute is not a model field — pydantic refuses the class.

        This is what makes DTO-04's "untyped model" mean ``Any``-annotated rather than
        un-annotated: the un-annotated variety cannot be built, so the pre-check has no edge
        to handle on that axis and the assumption is recorded here instead of in a paragraph.
        """

        def declare_it() -> type[pydantic.BaseModel]:
            """
            Declare the illegal model, and return it so the name is genuinely used.

            The class never comes into existence — the ``return`` is unreachable — but writing
            it keeps a strict type checker from reading the class as dead code, which a bare
            ``class`` statement inside a ``pytest.raises`` block otherwise is.
            """

            class UnannotatedDTO(pydantic.BaseModel):
                x = 1  # noqa: RUF012

            return UnannotatedDTO

        with pytest.raises(pydantic.errors.PydanticUserError):
            declare_it()

    def test_an_all_any_model_streams_through_iter_into(self) -> None:
        """DTO-04 on the streaming path, not only through the pre-check in isolation."""

        class Untyped(pydantic.BaseModel):
            region: Any
            revenue: Any

        reader = CountingReader([batch([{"region": "US", "revenue": 1}])])
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        items = list(cursor.iter_into(Untyped))

        assert len(items) == 1
        assert items[0].region == "US"
