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
- ``TestJsonValueSpellings`` — why the docs must say ``pydantic.JsonValue``.
- ``TestAliasResolution`` — the Snowflake ``AGG("REVENUE")`` trap.
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
    materialising the whole table" is a claim about *how many batches were pulled*. Asserting
    on the number of results returned would pass just as well against an implementation that
    read everything up front.
    """

    def __init__(
        self,
        batches: Iterable[pyarrow.RecordBatch],
        drain_error: BaseException | None = None,
    ) -> None:
        """
        Initialise with the batches to serve and how to behave once they run out.

        Args:
            batches: The batches to hand out, in order.
            drain_error: Raised instead of ``StopIteration`` once the batches are exhausted.
                ADBC drivers surface a drained reader as ``OSError`` rather than
                ``StopIteration``, and ``iter_into`` must normalise both to termination.
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
    ) -> None:
        """
        Initialise with a description and an optional reader.

        Args:
            description: The DBAPI description the pre-check reads.
            reader: The reader ``fetch_record_batch()`` hands back. ``None`` for tests that
                must never reach it.
        """
        self.description = description
        self.reader = reader
        self.fetch_record_batch_calls = 0
        self.closed = False

    def fetch_record_batch(self) -> CountingReader:
        """
        Return the configured reader, counting the call.

        Returns:
            The ``CountingReader`` this fake was built with.

        Raises:
            AssertionError: If the test configured no reader — reaching here means the code
                under test created a stream it was supposed to refuse.
        """
        self.fetch_record_batch_calls += 1
        if self.reader is None:
            raise AssertionError("fetch_record_batch() reached on a cursor that has no reader")
        return self.reader

    def close(self) -> None:
        """Mark the fake closed, so ``SemolinaCursor.close()`` has something to call."""
        self.closed = True


def make_cursor(
    description: list[tuple[Any, ...]] | None,
    reader: CountingReader | None = None,
) -> tuple[SemolinaCursor, FakeCursor]:
    """
    Wrap a :class:`FakeCursor` in a real :class:`~semolina.cursor.SemolinaCursor`.

    The wrapper is real rather than mocked because the behaviour under test is the wrapper's.
    The connection is a stub carrying only ``close()``, which is all ``__del__`` needs to stay
    quiet when a test drops the cursor without closing it.

    Args:
        description: The DBAPI description the pre-check will read.
        reader: The reader to serve, or ``None`` for tests that must not reach one.

    Returns:
        The ``SemolinaCursor`` and the ``FakeCursor`` underneath it, so a test can assert on
        the fake's counters.
    """
    inner = FakeCursor(description, reader)
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
        serialises as a ``Decimal`` through ``model_dump()`` and as a lossy float through
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

    def test_an_ambiguous_validation_alias_is_skipped(self) -> None:
        """
        ``AliasChoices`` names several candidate keys, and guessing one invents a verdict.

        The field is skipped entirely rather than resolved to its own name, because a verdict
        about a column the converter may never look at is worse than no verdict.
        """

        class M(pydantic.BaseModel):
            revenue: float = pydantic.Field(
                validation_alias=pydantic.AliasChoices("revenue", "REVENUE")
            )

        assert check_result_schema(columns(("revenue", pyarrow.decimal128(38, 2))), M) is None


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
