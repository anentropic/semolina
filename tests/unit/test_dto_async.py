"""
Fake-driven tests for the async cursor's ``into`` and ``iter_into``, under both loop backends.

The async complement of ``tests/unit/test_dto.py``, and it uses no warehouse for the same
reason that module does not: every claim here is about *timing* — when the schema check runs,
how many batches a single consumed instance costs — and neither is observable through a query.
A fake reader can be asked how many batches it has handed out; DuckDB cannot.

What this module adds over its synchronous twin is the thing that makes D-05 load-bearing
rather than stylistic. On the sync cursor, writing ``iter_into`` as a generator function is
merely wrong. On the async cursor it is also *tempting*, because the obvious way to reach a
schema is ``await self.fetch_record_batch()`` — and the moment ``iter_into`` needs an await it
becomes a coroutine and the check can no longer land on the call. ``cursor.description`` is the
way out, and :class:`TestAsyncIterIntoFailFast` is what stops that from silently regressing.

Every test here runs twice, once under asyncio and once under Trio, via the module-local
parametrized ``anyio_backend`` fixture. Three details of the header are load-bearing and are
checked by an AST walk in ``tests/unit/test_asyncio_trio_matrix.py``, so a tidier rewrite fails
a test that names a different module: ``pytestmark`` must be a top-level assignment whose value
mentions the ``anyio`` attribute, ``@pytest.fixture`` must be *called*, and the backend names
must be string literals inside the ``params=`` keyword rather than a module constant.

Test classes:

- ``TestAsyncIterIntoFailFast`` — D-05: the raise lands on the call expression, with no
  ``await``, no ``async for``, and no reader.
- ``TestAsyncIterIntoLaziness`` — DTO-02: one consumed instance costs exactly one batch pull.
- ``TestAsyncIterIntoDelivery`` — instances not lists, empty streams, holes, drained readers,
  and the reader-ownership rule ``aclose()`` depends on.
- ``TestAsyncIterIntoValidate`` — the flag reaches the converter's constructor.
- ``TestAsyncInto`` — DTO-01 on the async side: the same pre-check and the same error.
- ``TestAsyncIterIntoClose`` — teardown after a partially consumed stream.
"""
# Test-only: these tests inspect cursor state such as `_reader` to prove the reader the
# cursor hands out is the one it recorded. Scope-disable the private-access rule
# (intentionally not a `# type: ignore`).
# pyright: reportPrivateUsage=false

from __future__ import annotations

import contextlib
import importlib.util
import inspect
import warnings
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import patch

import pyarrow
import pydantic
import pytest

from semolina.acursor import AsyncSemolinaCursor
from semolina.exceptions import SemolinaMissingDependencyError, SemolinaSchemaMismatchError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Iterable

pytest.importorskip("arrowmodel")

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio", "trio"])
def anyio_backend(request: pytest.FixtureRequest) -> str:
    """Run every test in this module under both asyncio and Trio."""
    backend: str = request.param
    return backend


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


class CountingAsyncReader:
    """
    Duck-typed fake of adbc-poolhouse's async record batch reader, counting what it hands out.

    Duck-typed rather than subclassed because poolhouse's async reader is not a public
    importable name, and counted rather than merely sequenced because "streams without
    materialising the whole result" is a claim about *how many batches were pulled*. Asserting
    on the number of instances returned would pass just as well against an implementation that
    drained the reader up front.
    """

    def __init__(
        self,
        batches: Iterable[pyarrow.RecordBatch],
        drain_error: BaseException | None = None,
        log: list[str] | None = None,
    ) -> None:
        """
        Initialise with the batches to serve, how to behave once they run out, and a close log.

        Args:
            batches: The batches to hand out, in order.
            drain_error: Raised instead of ``StopAsyncIteration`` once the batches are
                exhausted. A stream drained by something else surfaces as ``OSError`` across
                poolhouse's thread boundary, and ``iter_into`` must normalise both to
                termination.
            log: Shared list appended to on close, so a test can assert the reader closed
                before the cursor and the connection.
        """
        self._batches = list(batches)
        self._position = 0
        self.batches_read = 0
        self.closed = False
        self._drain_error = drain_error
        self._log = log

    def __aiter__(self) -> CountingAsyncReader:
        """Return self so the reader is its own async iterator."""
        return self

    async def __anext__(self) -> pyarrow.RecordBatch:
        """
        Return the next batch, incrementing the pull counter.

        Returns:
            The next ``pyarrow.RecordBatch``.

        Raises:
            StopAsyncIteration: When exhausted and no ``drain_error`` was configured.
            BaseException: The configured ``drain_error``, when exhausted and one was given.
        """
        if self._position >= len(self._batches):
            if self._drain_error is not None:
                raise self._drain_error
            raise StopAsyncIteration
        result = self._batches[self._position]
        self._position += 1
        self.batches_read += 1
        return result

    async def close(self) -> None:
        """Mark the reader closed and record the close order."""
        self.closed = True
        if self._log is not None:
            self._log.append("reader")


class FakeAsyncCursor:
    """
    Minimal duck-typed fake of adbc-poolhouse's ``AsyncCursor``, counting stream creations.

    ``fetch_record_batch_calls`` is what makes the fail-fast tests non-vacuous: "raised before
    any batch moved" is weaker than "raised before a reader even existed", and only the second
    distinguishes an eager pre-check from a lazy one that happens to fail on the first pull.
    """

    def __init__(
        self,
        description: list[tuple[Any, ...]] | None,
        reader: CountingAsyncReader | None = None,
        table: pyarrow.Table | None = None,
        fetch_error: BaseException | None = None,
        log: list[str] | None = None,
    ) -> None:
        """
        Initialise with a description, an optional reader and table, an error, and a close log.

        Args:
            description: The DBAPI description the pre-check reads.
            reader: The reader ``fetch_record_batch()`` hands back. ``None`` for tests that
                must never reach it.
            table: The table ``fetch_arrow_table()`` hands back. ``None`` for tests that must
                never reach it.
            fetch_error: Raised by ``fetch_record_batch()`` instead of returning, standing in
                for a driver that reports an already-drained result at reader-creation time.
            log: Shared list appended to on close.
        """
        self.description = description
        self.reader = reader
        self.table = table
        self.fetch_record_batch_calls = 0
        self.fetch_arrow_table_calls = 0
        self.closed = False
        self._fetch_error = fetch_error
        self._log = log

    async def fetch_record_batch(self) -> CountingAsyncReader:
        """
        Return the configured reader, counting the call.

        Returns:
            The ``CountingAsyncReader`` this fake was built with.

        Raises:
            BaseException: The configured ``fetch_error``, when one was given.
            AssertionError: If the test configured no reader — reaching here means the code
                under test created a stream it was supposed to refuse.
        """
        self.fetch_record_batch_calls += 1
        if self._fetch_error is not None:
            raise self._fetch_error
        if self.reader is None:
            raise AssertionError("fetch_record_batch() reached on a cursor that has no reader")
        return self.reader

    async def fetch_arrow_table(self) -> pyarrow.Table:
        """
        Return the configured table, counting the call.

        Returns:
            The ``pyarrow.Table`` this fake was built with.

        Raises:
            AssertionError: If the test configured no table — reaching here means the code
                under test materialised a result it was supposed to refuse.
        """
        self.fetch_arrow_table_calls += 1
        if self.table is None:
            raise AssertionError("fetch_arrow_table() reached on a cursor that has no table")
        return self.table

    async def close(self) -> None:
        """Mark the fake closed and record the close order."""
        self.closed = True
        if self._log is not None:
            self._log.append("cursor")


class FakeAsyncConn:
    """Minimal duck-typed fake of adbc-poolhouse's ``AsyncConnection``."""

    def __init__(self, log: list[str] | None = None) -> None:
        """Initialise with a shared close log."""
        self.closed = False
        self._log = log

    async def close(self) -> None:
        """Mark the connection closed and record the close order."""
        self.closed = True
        if self._log is not None:
            self._log.append("conn")


def make_cursor(
    description: list[tuple[Any, ...]] | None,
    reader: CountingAsyncReader | None = None,
    table: pyarrow.Table | None = None,
    fetch_error: BaseException | None = None,
    log: list[str] | None = None,
) -> tuple[AsyncSemolinaCursor, FakeAsyncCursor]:
    """
    Wrap a :class:`FakeAsyncCursor` in a real :class:`~semolina.acursor.AsyncSemolinaCursor`.

    The wrapper is real rather than mocked because the behaviour under test is the wrapper's.
    Both fakes expose ``close()`` as a coroutine, so ``aclose()`` runs clean and the async
    cursor's ``__del__`` — which can only warn, never rescue — stays quiet.

    Args:
        description: The DBAPI description the pre-check will read.
        reader: The reader to serve, or ``None`` for tests that must not reach one.
        table: The table to serve, or ``None`` for tests that must not reach one.
        fetch_error: Raised by ``fetch_record_batch()`` instead of returning.
        log: Shared close-order log.

    Returns:
        The ``AsyncSemolinaCursor`` and the ``FakeAsyncCursor`` underneath it, so a test can
        assert on the fake's counters.
    """
    inner = FakeAsyncCursor(description, reader, table, fetch_error, log)
    conn = FakeAsyncConn(log)
    return AsyncSemolinaCursor(cursor=inner, conn=conn, pool=None), inner


def find_spec_without(missing: str) -> Callable[..., Any]:
    """
    Build a ``find_spec`` replacement that reports exactly one package absent.

    A blanket ``return_value=None`` would make the *pyarrow* guard fire first, so a test
    written that way would assert the wrong error's message and still pass. Restated from
    ``tests/unit/test_dto.py`` rather than imported, following this suite's convention that
    test modules stay self-contained.

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


def stream_of(
    cursor: AsyncSemolinaCursor, model: type[pydantic.BaseModel]
) -> AsyncGenerator[Any, None]:
    """
    Call ``iter_into`` and type the result as the async generator it really is.

    ``iter_into`` is annotated ``-> AsyncIterator`` because that is the contract callers
    program against, and an ``AsyncIterator`` declares no ``aclose()``. The tests that abandon
    a stream part-way need one, so that they close it explicitly rather than leaving a
    suspended generator for the garbage collector — which under Trio is a warning and under
    any backend is a distraction from what the test is measuring.

    Args:
        cursor: The cursor to stream from.
        model: The DTO to build.

    Returns:
        The same object ``iter_into`` returned, typed as an ``AsyncGenerator``.
    """
    return cast("AsyncGenerator[Any, None]", cursor.iter_into(model))


class SalesDTO(pydantic.BaseModel):
    """A DTO that matches :data:`SALES_SCHEMA` exactly."""

    region: str
    revenue: int


class MistypedSalesDTO(pydantic.BaseModel):
    """A DTO declaring the ``int64`` revenue column as ``str`` — a confident mismatch."""

    region: str
    revenue: str


# -- D-05: the check lands on the call, not on the first await or the first `async for` -----


class TestAsyncIterIntoFailFast:
    """D-05 on the async cursor, where it is structural rather than stylistic."""

    async def test_iter_into_with_a_mismatched_dto_raises_at_call(self) -> None:
        """
        A bad DTO raises inside ``iter_into(...)`` itself — no ``await``, no ``async for``.

        Written with no awaiting and no iteration of any kind on purpose. A version spelled
        ``[dto async for dto in cursor.iter_into(...)]`` inside ``pytest.raises`` would pass
        identically against an ``async def`` or against an async generator function, which are
        exactly the two implementations D-05 forbids. ``cursor._reader is None`` afterwards is
        the second half of the claim: not merely that nothing was converted, but that no
        stream was ever opened.
        """
        cursor, inner = make_cursor(describe(SALES_SCHEMA), reader=None)

        async with cursor:
            with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
                cursor.iter_into(MistypedSalesDTO)

            assert cursor._reader is None
            assert inner.fetch_record_batch_calls == 0
            message = str(excinfo.value)
            assert "revenue" in message
            assert "int64" in message

    async def test_iter_into_is_neither_a_coroutine_nor_an_async_generator_function(self) -> None:
        """
        The structural counterpart: ``iter_into`` is a plain method, and only the impl is lazy.

        Both halves matter. An ``async def`` would defer the body to the caller's first
        ``await``; an ``async def`` containing ``yield`` would defer it to the first
        ``async for``. Either would make the test above pass for the wrong reason, if that
        test were written with iteration in it.
        """
        assert not inspect.iscoroutinefunction(AsyncSemolinaCursor.iter_into)
        assert not inspect.isasyncgenfunction(AsyncSemolinaCursor.iter_into)
        assert inspect.isasyncgenfunction(AsyncSemolinaCursor._aiter_into_impl)
        assert inspect.iscoroutinefunction(AsyncSemolinaCursor.into)

    async def test_iter_into_without_arrowmodel_raises_at_call(self) -> None:
        """A missing arrowmodel is reported at the call, naming the extra that fixes it."""
        cursor, inner = make_cursor(describe(SALES_SCHEMA), reader=None)

        async with cursor:
            with (
                patch("importlib.util.find_spec", side_effect=find_spec_without("arrowmodel")),
                pytest.raises(SemolinaMissingDependencyError) as excinfo,
            ):
                cursor.iter_into(SalesDTO)

            assert inner.fetch_record_batch_calls == 0
            assert "pip install semolina[arrowmodel]" in str(excinfo.value)

    async def test_iter_into_without_pyarrow_raises_before_reading_description(self) -> None:
        """
        The pyarrow guard fires first, so ``description`` is never touched without it.

        Reading ``description`` on an ADBC cursor with no pyarrow raises ADBC's own
        ``ProgrammingError`` from a ``_NoOpBackend``, which names neither Semolina nor the
        extra to install.
        """
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader=None)

        async with cursor:
            with (
                patch("importlib.util.find_spec", side_effect=find_spec_without("pyarrow")),
                pytest.raises(SemolinaMissingDependencyError) as excinfo,
            ):
                cursor.iter_into(SalesDTO)

            assert "pip install semolina[pyarrow]" in str(excinfo.value)


class TestAsyncIterIntoLaziness:
    """DTO-02: streaming, measured on a counter rather than inferred from a result length."""

    async def test_iter_into_lazy_first_item_pulls_exactly_one_batch(self) -> None:
        """
        Taking one instance from a two-batch reader pulls one batch, not two.

        The discriminator against materialising the whole result behind a streaming interface:
        a version that drained the reader up front would show ``batches_read == 2`` here.
        """
        reader = CountingAsyncReader(
            [
                batch([{"region": "US", "revenue": 1}, {"region": "CA", "revenue": 2}]),
                batch([{"region": "MX", "revenue": 3}, {"region": "DE", "revenue": 4}]),
            ]
        )
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        async with cursor:
            stream = stream_of(cursor, SalesDTO)
            assert reader.batches_read == 0

            async with contextlib.aclosing(stream):
                first = None
                async for dto in stream:
                    first = dto
                    break

            assert isinstance(first, SalesDTO)
            assert reader.batches_read == 1

    async def test_iter_into_lazy_reader_is_untouched_until_the_first_anext(self) -> None:
        """Holding the iterator without consuming it pulls nothing and creates no reader."""
        reader = CountingAsyncReader([batch([{"region": "US", "revenue": 1}])])
        cursor, inner = make_cursor(describe(SALES_SCHEMA), reader)

        async with cursor:
            stream = stream_of(cursor, SalesDTO)

            assert inner.fetch_record_batch_calls == 0
            assert reader.batches_read == 0
            assert cursor._reader is None

            await stream.aclose()


class TestAsyncIterIntoDelivery:
    """What comes out, what the odd stream shapes do, and who owns the reader."""

    async def test_iter_into_yields_model_instances_not_lists(self) -> None:
        """Each item is a single DTO, so ``async for dto in ...`` needs no unpacking (D-03)."""
        reader = CountingAsyncReader(
            [batch([{"region": "US", "revenue": 1}, {"region": "CA", "revenue": 2}])]
        )
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        async with cursor:
            items = [dto async for dto in cursor.iter_into(SalesDTO)]

        assert [type(item) for item in items] == [SalesDTO, SalesDTO]
        assert [item.region for item in items] == ["US", "CA"]

    async def test_iter_into_skips_a_zero_row_batch_mid_stream(self) -> None:
        """A hole in the stream is skipped, not treated as its end (mirrors ``__anext__``)."""
        reader = CountingAsyncReader(
            [
                batch([{"region": "US", "revenue": 1}, {"region": "CA", "revenue": 2}]),
                batch([]),
                batch([{"region": "MX", "revenue": 3}, {"region": "DE", "revenue": 4}]),
            ]
        )
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        async with cursor:
            items = [dto async for dto in cursor.iter_into(SalesDTO)]

        assert len(items) == 4
        assert [item.region for item in items] == ["US", "CA", "MX", "DE"]

    async def test_iter_into_over_an_empty_reader_yields_nothing(self) -> None:
        """
        A result with no batches at all yields nothing and raises nothing.

        Also the PEP 525 case: a ``StopAsyncIteration`` allowed to escape an async generator
        body becomes a ``RuntimeError``, so the drive loop cannot copy ``__anext__``'s bare
        ``raise`` and this test is what says so.
        """
        reader = CountingAsyncReader([])
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        async with cursor:
            assert [dto async for dto in cursor.iter_into(SalesDTO)] == []

    async def test_iter_into_treats_a_drained_reader_oserror_as_termination(self) -> None:
        """An ``OSError`` from a drained reader ends iteration rather than propagating."""
        reader = CountingAsyncReader(
            [batch([{"region": "US", "revenue": 1}])],
            drain_error=OSError("reader is drained"),
        )
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        async with cursor:
            items = [dto async for dto in cursor.iter_into(SalesDTO)]

        assert len(items) == 1

    async def test_iter_into_normalises_a_drained_reader_creation_error(self) -> None:
        """
        A driver reporting the drain when the reader is created also stops cleanly.

        The async parity case for ``__anext__``'s own creation-time guard: some ADBC drivers
        report an already-consumed result at reader creation rather than on the first pull.
        """
        cursor, _inner = make_cursor(
            describe(SALES_SCHEMA),
            reader=None,
            fetch_error=OSError("Attempting to execute an unsuccessful or closed query result"),
        )

        async with cursor:
            assert [dto async for dto in cursor.iter_into(SalesDTO)] == []

    async def test_iter_into_takes_its_reader_through_the_cursors_own_delegate(self) -> None:
        """
        The stream's reader is the one the cursor recorded, which is what makes teardown work.

        A reader obtained behind the cursor's back would leak its pool slot in silence: it
        locks the connection for its whole lifetime, ``aclose()`` would not know to close it
        first, and the resulting ``ConnectionBusyError`` from the cursor and connection closes
        are both suppressed.
        """
        reader = CountingAsyncReader([batch([{"region": "US", "revenue": 1}])])
        cursor, inner = make_cursor(describe(SALES_SCHEMA), reader)

        async with cursor:
            items = [dto async for dto in cursor.iter_into(SalesDTO)]

            assert len(items) == 1
            assert cursor._reader is reader
            assert inner.fetch_record_batch_calls == 1

        assert reader.closed is True


class TestAsyncIterIntoValidate:
    """The ``validate`` flag reaches the converter's *constructor*, where it lives."""

    async def test_iter_into_with_validate_true_rejects_a_null_in_a_required_field(self) -> None:
        """
        ``validate=True`` catches the one thing the pre-check deliberately does not.

        Nullability is not checked structurally (D-09), so a NULL in a non-optional field is
        the case that distinguishes the two settings — and therefore the case that proves the
        flag was passed to the converter rather than dropped.
        """
        reader = CountingAsyncReader([batch([{"region": "US", "revenue": None}])])
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        async with cursor:
            with pytest.raises(pydantic.ValidationError):
                _items = [dto async for dto in cursor.iter_into(SalesDTO, validate=True)]

    async def test_validate_true_skips_the_type_check_on_the_async_cursor_too(self) -> None:
        """
        The ``check_types=not validate`` wiring reaches the async twin, not just the sync one.

        ``int64`` into a ``float``-annotated field is refused on the fast path (PD-02: Python
        has no nominal numeric tower and ``model_construct`` really would leave an ``int``
        there) and coerced under ``validate=True``, where Pydantic converts it to ``42.0``.
        Asserted through the async surface because a threading mistake would be invisible from
        the sync tests.
        """

        class RevenueFloatDTO(pydantic.BaseModel):
            region: str
            revenue: float

        reader = CountingAsyncReader([batch([{"region": "US", "revenue": 42}])])
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)
        async with cursor:
            with pytest.raises(SemolinaSchemaMismatchError):
                cursor.iter_into(RevenueFloatDTO, validate=False)

        reader = CountingAsyncReader([batch([{"region": "US", "revenue": 42}])])
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)
        async with cursor:
            items = [dto async for dto in cursor.iter_into(RevenueFloatDTO, validate=True)]

        assert [item.revenue for item in items] == [42.0]
        assert all(isinstance(item.revenue, float) for item in items)

    async def test_into_with_validate_true_skips_the_type_check(self) -> None:
        """The eager async twin threads ``validate`` into the check the same way."""

        class RevenueFloatDTO(pydantic.BaseModel):
            region: str
            revenue: float

        reader = CountingAsyncReader([batch([{"region": "US", "revenue": 42}])])
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)
        async with cursor:
            with pytest.raises(SemolinaSchemaMismatchError):
                await cursor.into(RevenueFloatDTO, validate=False)

    async def test_iter_into_with_validate_false_leaves_the_null_in_place(self) -> None:
        """The fast path performs no per-value validation, which is the contrast that matters."""
        reader = CountingAsyncReader([batch([{"region": "US", "revenue": None}])])
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        async with cursor:
            items = [dto async for dto in cursor.iter_into(SalesDTO)]

        assert len(items) == 1
        assert items[0].revenue is None


# -- DTO-01: `await cursor.into(DTO)` -------------------------------------------------------


class TestAsyncInto:
    """DTO-01 on the async cursor: same matching, same pre-check, same error."""

    async def test_into_returns_model_instances(self) -> None:
        """``await cursor.into(DTO)`` builds one instance per row, matched by column name."""
        table = pyarrow.Table.from_batches(
            [batch([{"region": "US", "revenue": 1}, {"region": "CA", "revenue": 2}])],
            schema=SALES_SCHEMA,
        )
        cursor, inner = make_cursor(describe(SALES_SCHEMA), table=table)

        async with cursor:
            items = await cursor.into(SalesDTO)

        assert [type(item) for item in items] == [SalesDTO, SalesDTO]
        assert [item.region for item in items] == ["US", "CA"]
        assert inner.fetch_arrow_table_calls == 1

    async def test_into_over_a_zero_row_result_returns_an_empty_list(self) -> None:
        """A result with no rows converts to an empty list rather than raising."""
        table = pyarrow.Table.from_batches([batch([])], schema=SALES_SCHEMA)
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), table=table)

        async with cursor:
            assert await cursor.into(SalesDTO) == []

    async def test_into_with_a_mismatched_dto_raises_before_the_result_is_materialised(
        self,
    ) -> None:
        """
        A bad DTO raises the same error as the sync twin, and fetches nothing to do it.

        ``into`` is legitimately a coroutine — it awaits ``fetch_arrow_table`` — so the timing
        claim here is weaker than ``iter_into``'s by design: the check runs before the first
        await inside the body, not before the caller's await. What it must still be is *before
        any data moves*, which the untouched ``fetch_arrow_table_calls`` counter says.
        """
        cursor, inner = make_cursor(describe(SALES_SCHEMA), table=None)

        async with cursor:
            with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
                await cursor.into(MistypedSalesDTO)

            assert inner.fetch_arrow_table_calls == 0
            assert "revenue" in str(excinfo.value)

    async def test_into_without_arrowmodel_names_the_extra(self) -> None:
        """A missing arrowmodel is reported with the install command, before any fetch."""
        cursor, inner = make_cursor(describe(SALES_SCHEMA), table=None)

        async with cursor:
            with (
                patch("importlib.util.find_spec", side_effect=find_spec_without("arrowmodel")),
                pytest.raises(SemolinaMissingDependencyError) as excinfo,
            ):
                await cursor.into(SalesDTO)

            assert inner.fetch_arrow_table_calls == 0
            assert "pip install semolina[arrowmodel]" in str(excinfo.value)


class TestAsyncIterIntoClose:
    """Teardown after a partially consumed stream — the leak the async cursor cannot rescue."""

    async def test_aclose_after_a_partial_stream_closes_the_reader_first(self) -> None:
        """
        Abandoning the stream half-way still closes reader, then cursor, then connection.

        The order is not cosmetic: a live reader locks its pooled connection, and closing the
        cursor or the connection first raises ``ConnectionBusyError`` inside teardown, where
        it is suppressed — so the slot would never come back.
        """
        log: list[str] = []
        reader = CountingAsyncReader(
            [
                batch([{"region": "US", "revenue": 1}, {"region": "CA", "revenue": 2}]),
                batch([{"region": "MX", "revenue": 3}]),
            ],
            log=log,
        )
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader, log=log)

        stream = stream_of(cursor, SalesDTO)
        async with contextlib.aclosing(stream):
            async for _dto in stream:
                break

        await cursor.aclose()

        assert log == ["reader", "cursor", "conn"]
        assert reader.closed is True

    async def test_a_partially_consumed_stream_emits_no_resource_warning(self) -> None:
        """
        A cursor closed through ``async with`` after a partial stream warns about nothing.

        The async cursor has no ``__del__`` rescue — it can only warn — so a ``ResourceWarning``
        here would mean a pooled connection that never comes back.
        """
        reader = CountingAsyncReader(
            [batch([{"region": "US", "revenue": 1}, {"region": "CA", "revenue": 2}])]
        )
        cursor, _inner = make_cursor(describe(SALES_SCHEMA), reader)

        with warnings.catch_warnings():
            warnings.simplefilter("error", ResourceWarning)
            async with cursor:
                stream = stream_of(cursor, SalesDTO)
                async with contextlib.aclosing(stream):
                    async for _dto in stream:
                        break
