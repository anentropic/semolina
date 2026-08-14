"""
Fake-driven tests for ``iter_into``: what raises at the call, and what streams lazily.

The warehouse-backed half of this phase lives in ``tests/unit/test_dto_duckdb.py``, which
proves that a real ``DECIMAL(38, 2)`` reaches a ``decimal.Decimal`` field through a real ADBC
driver. This module is its complement and deliberately uses no warehouse at all: every case
here is about *timing* or about *which schemas the pre-check will and will not object to*, and
neither is observable through a query. A fake reader can be asked how many batches it has
handed out; DuckDB cannot. A hand-built ``description`` can pair an Arrow ``struct`` with a
``str``-annotated field in one line; producing that from SQL would take a fixture.

Covers DTO-02 (streaming one instance at a time), DTO-03 (mismatches raise) on the streaming
path, and decision D-05 (the raise lands at the call). The pre-check's full rule set lands in
the same module in the next task.

Test classes:

- ``TestIterIntoFailFast`` — D-05: the raise lands on the call expression, not on ``next()``.
- ``TestIterIntoLaziness`` — DTO-02: one consumed instance costs exactly one batch.
- ``TestIterIntoDelivery`` — instances not lists, empty streams, holes, drained readers.
- ``TestIterIntoValidate`` — the flag reaches the converter's constructor.
"""

from __future__ import annotations

import importlib.util
import types
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pyarrow
import pydantic
import pytest

from semolina.cursor import SemolinaCursor
from semolina.exceptions import SemolinaMissingDependencyError, SemolinaSchemaMismatchError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

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
