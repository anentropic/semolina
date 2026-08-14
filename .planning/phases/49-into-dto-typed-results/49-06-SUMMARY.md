---
phase: 49-into-dto-typed-results
plan: 06
subsystem: api
tags: [async, anyio, trio, arrowmodel, pydantic, streaming, dto, pandas, polars, pyarrow]

requires:
  - phase: 49-into-dto-typed-results
    plan: 01
    provides: "check_result_schema, _require, both error classes, and the extras the guards name"
  - phase: 49-into-dto-typed-results
    plan: 02
    provides: "The sync iter_into / _iter_into_impl shape this plan mirrors, the confirmed `iter_into` name, and the non-vacuity-by-execution pattern"
  - phase: 49-into-dto-typed-results
    plan: 03
    provides: "The measured polars Decimal row carried verbatim into the async fetch_polars docstring"
  - phase: 49-into-dto-typed-results
    plan: 05
    provides: "The per-method guard sets, read out of ADBC's own source, transferred here unchanged"
  - phase: 46-async-cursor-streaming
    provides: "The reader-ownership delegate, the synchronous `description` property, the plain `__aiter__` precedent, and the aclose ordering these methods must not contradict"
provides:
  - "AsyncSemolinaCursor.into(model, *, validate=False) -> list[_M] — async def, pre-check before the first await"
  - "AsyncSemolinaCursor.iter_into(model, *, validate=False) -> AsyncIterator[_M] — a PLAIN method, provably neither a coroutine function nor an async generator function"
  - "AsyncSemolinaCursor._aiter_into_impl — the async generator that owns all the laziness and takes its reader through the cursor's own delegate"
  - "AsyncSemolinaCursor.fetch_df() / fetch_polars() — one-line poolhouse delegates with guards"
  - "pyarrow guards on the async fetch_arrow_table and fetch_record_batch"
  - "tests/unit/test_dto_async.py — 20 tests × 2 loop backends, satisfying the AST matrix contract"
  - "tests/unit/test_async_cursor.py — async probe engine, live dataframe returns, and the four-way guard parametrisation"
affects: [49-07-docs, 50-codegen-dtos]

actuals:
  tokens: 15964
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Eager check, lazy production, async edition: a plain `def` that runs the guards and the pre-check and returns the async generator a separate private async generator function produces"
    - "A drive loop copied from `__anext__` must convert its `raise` into `return` — PEP 525 turns a StopAsyncIteration escaping an async generator body into a RuntimeError, exactly as PEP 479 does for the sync case"
    - "Abandoned async generators in tests are closed explicitly through `contextlib.aclosing`, so no test depends on a backend's asyncgen finalisation hooks"

key-files:
  created:
    - tests/unit/test_dto_async.py
    - .planning/phases/49-into-dto-typed-results/49-06-SUMMARY.md
  modified:
    - src/semolina/acursor.py
    - tests/unit/test_async_cursor.py

key-decisions:
  - "The async `iter_into` is a plain method returning an async iterator, confirmed mechanically by `inspect.iscoroutinefunction` and `inspect.isasyncgenfunction` both reading False, and by an AST walk finding no Await/Yield in its body"
  - "`into` stays `async def` — it awaits `fetch_arrow_table`, which is what every other fetch on this class does; D-05 constrains `iter_into` only, and the SUMMARY records the weaker timing claim `into`'s test makes as a result"
  - "The four async guard sets are Plan 05's unchanged: poolhouse offloads ADBC's own implementations rather than reimplementing them, so the imports happen in the same order on the same code"
  - "Guards run BEFORE the await, because poolhouse explicitly declines to pre-check pandas/polars and lets the driver's native ModuleNotFoundError cross the thread boundary unchanged"
  - "The plan's literal `-k missing_dependency` selector matches nothing (pytest -k is case-sensitive and Plan 05 named the class TestMissingDependencyGuards); `-k MissingDependency` is the selector that does what the criterion intended, and it selects both cursors' cases"

patterns-established:
  - "An async fail-fast test contains no `await` and no `async for` in the assertion block at all, and additionally asserts `cursor._reader is None` — anything weaker passes against both of the shapes D-05 forbids"

requirements-completed: [DTO-01, DTO-02, RESULT-01, RESULT-02]

coverage:
  - id: A1
    description: "`cursor.iter_into(BadDTO)` raises SemolinaSchemaMismatchError on the call expression with no await, no async for, and no reader created — under both loop backends"
    requirement: DTO-02
    verification:
      - kind: unit
        ref: "tests/unit/test_dto_async.py#TestAsyncIterIntoFailFast::test_iter_into_with_a_mismatched_dto_raises_at_call (asyncio + trio)"
        status: pass
      - kind: unit
        ref: "tests/unit/test_dto_async.py#TestAsyncIterIntoFailFast::test_iter_into_is_neither_a_coroutine_nor_an_async_generator_function"
        status: pass
      - kind: other
        ref: "non-vacuity proof by deliberate breakage — observed output recorded below"
        status: pass
    human_judgment: false
  - id: A2
    description: "Consuming one DTO from an `async for` pulls exactly one batch, measured on a counting fake reader"
    requirement: DTO-02
    verification:
      - kind: unit
        ref: "tests/unit/test_dto_async.py#TestAsyncIterIntoLaziness (2 tests × 2 backends)"
        status: pass
    human_judgment: false
  - id: A3
    description: "Zero-row batches are skipped, an empty reader yields nothing, and a drained reader's OSError terminates iteration at both the creation and the pull site"
    requirement: DTO-02
    verification:
      - kind: unit
        ref: "tests/unit/test_dto_async.py#TestAsyncIterIntoDelivery (6 tests × 2 backends)"
        status: pass
    human_judgment: false
  - id: A4
    description: "`await cursor.into(DTO)` returns Pydantic instances matched by column name, and a mismatched DTO raises the same error before the result is materialised"
    requirement: DTO-01
    verification:
      - kind: unit
        ref: "tests/unit/test_dto_async.py#TestAsyncInto (4 tests × 2 backends)"
        status: pass
    human_judgment: false
  - id: A5
    description: "`await cursor.fetch_df()` returns a pandas.DataFrame and `await cursor.fetch_polars()` a polars.DataFrame from a live async DuckDB semantic-view result, asserted by isinstance against the real classes"
    requirement: RESULT-01
    verification:
      - kind: unit
        ref: "tests/unit/test_async_cursor.py#TestAsyncFetchDf::test_returns_a_pandas_dataframe"
        status: pass
      - kind: unit
        ref: "tests/unit/test_async_cursor.py#TestAsyncFetchPolars::test_returns_a_polars_dataframe"
        status: pass
    human_judgment: false
  - id: A6
    description: "Each of the four async Arrow/dataframe methods raises SemolinaMissingDependencyError naming its own package and its own literal install command; fetch_polars does not require pyarrow"
    requirement: RESULT-02
    verification:
      - kind: unit
        ref: "tests/unit/test_async_cursor.py#TestAsyncMissingDependencyGuards::test_each_method_names_its_own_extra (4 params × 2 backends)"
        status: pass
      - kind: unit
        ref: "tests/unit/test_async_cursor.py#TestAsyncMissingDependencyGuards::test_fetch_polars_does_not_require_pyarrow"
        status: pass
      - kind: unit
        ref: "tests/unit/test_async_cursor.py#TestAsyncMissingDependencyGuards::test_fetch_df_reports_pyarrow_before_pandas"
        status: pass
    human_judgment: false
  - id: A7
    description: "tests/unit/test_dto_async.py is actually collected and run under BOTH asyncio and Trio, not merely marked"
    verification:
      - kind: unit
        ref: "`-k trio` selects 20 of 40; `-k asyncio` selects the other 20; test ids carry [asyncio]/[trio] — output below"
        status: pass
      - kind: unit
        ref: "tests/unit/test_asyncio_trio_matrix.py — 3 passed, module in scope"
        status: pass
    human_judgment: false
  - id: A8
    description: "No test leaks an unclosed async cursor — the leak this cursor has no __del__ rescue for"
    requirement: DTO-02
    verification:
      - kind: unit
        ref: "`uv run pytest tests/unit/test_dto_async.py -W error::ResourceWarning` — 40 passed"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-08-14
status: complete
---

# Phase 49 Plan 06: The Async Twins Summary

**`into`, `iter_into`, `fetch_df` and `fetch_polars` now exist on `AsyncSemolinaCursor` with
the same guards and the same pre-check as their synchronous siblings — and `iter_into` is
provably a plain method rather than a coroutine, proven by making it `async def` on purpose and
watching six tests go red across both loop backends.**

## Performance

- **Duration:** ~12 min (08:12 → 08:24 UTC), plus this artifact
- **Tasks:** 3, all `type="auto"`, no checkpoints
- **Files modified:** 3 (1 created, 2 modified) — 1,335 inserted, 1 deleted
- **Tests added:** 56 (root suite 1424 → 1480): 40 in the new async module, 16 in
  `test_async_cursor.py`

## Task Commits

1. **Task 1: async `into` and `iter_into` — the check happens before the first await** — `809f845` (feat)
2. **Task 2: async `fetch_df` / `fetch_polars`, and the four async guards** — `5a9eac7` (feat)
3. **Task 3: the two-backend async test module, built to the AST matrix contract** — `17ab24b` (test)

## The non-vacuity proof, as observed

This is the artifact the plan asked for by name, and on the async cursor it matters more than
it did on the sync one. The forbidden implementation here is not exotic — `async def
iter_into(...)` is what you write if you reach the schema through `await
self.fetch_record_batch()` instead of through `description`, which is the obvious way to do it.

`iter_into`'s `def` was temporarily changed to `async def`, nothing else, and the fail-fast
selection re-run. **Six tests went red** — three cases × two backends:

```
=================================== FAILURES ===================================
    async def test_iter_into_without_arrowmodel_raises_at_call(self) -> None:
        """A missing arrowmodel is reported at the call, naming the extra that fixes it."""
        cursor, inner = make_cursor(describe(SALES_SCHEMA), reader=None)

        async with cursor:
            with (
                patch("importlib.util.find_spec", side_effect=find_spec_without("arrowmodel")),
>               pytest.raises(SemolinaMissingDependencyError) as excinfo,
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            ):
E           Failed: DID NOT RAISE SemolinaMissingDependencyError

tests/unit/test_dto_async.py:413: Failed
=============================== warnings summary ===============================
tests/unit/test_dto_async.py::TestAsyncIterIntoFailFast::test_iter_into_with_a_mismatched_dto_raises_at_call[asyncio]
tests/unit/test_dto_async.py::TestAsyncIterIntoFailFast::test_iter_into_with_a_mismatched_dto_raises_at_call[trio]
  /Users/paul/…/tests/unit/test_dto_async.py:384: RuntimeWarning: coroutine
  'AsyncSemolinaCursor.iter_into' was never awaited
    cursor.iter_into(MistypedSalesDTO)
=========================== short test summary info ============================
FAILED …::test_iter_into_with_a_mismatched_dto_raises_at_call[asyncio]
FAILED …::test_iter_into_with_a_mismatched_dto_raises_at_call[trio]
FAILED …::test_iter_into_is_neither_a_coroutine_nor_an_async_generator_function[asyncio]
FAILED …::test_iter_into_is_neither_a_coroutine_nor_an_async_generator_function[trio]
FAILED …::test_iter_into_without_arrowmodel_raises_at_call[asyncio]
FAILED …::test_iter_into_without_arrowmodel_raises_at_call[trio]
================= 6 failed, 34 deselected, 4 warnings in 0.11s =================
```

Two things in that output are worth reading rather than skimming.

**The failure mode is silence, not a wrong error.** `DID NOT RAISE` — the broken `iter_into`
returned a perfectly ordinary coroutine object and the mismatched DTO produced nothing at all.
A user would see the call that named the wrong type succeed, and the traceback would arrive
from whatever `async for` eventually consumed it.

**`RuntimeWarning: coroutine 'iter_into' was never awaited` is the user-facing symptom** the
plain-method shape avoids. Under the broken version, `async for dto in cursor.iter_into(DTO)`
would fail with `TypeError: 'async for' requires an object with __aiter__ method, got
coroutine` — a call-convention break, not a subtle one, which is precisely why the shape is
recorded as costly to reverse.

The break was reverted from a byte-for-byte copy taken before the edit. `git diff --stat`
against the Task 1 commit was **empty**, and all 40 tests pass again.

## The new module really does run under both backends

"The tests passed" would not have said this, so here is the measurement. The module defines
20 tests; the suite collects and runs **40**:

```
$ uv run pytest tests/unit/test_dto_async.py -q
40 passed in 0.08s

$ uv run pytest tests/unit/test_dto_async.py -k trio -q
20 passed, 20 deselected in 0.04s

$ uv run pytest tests/unit/test_dto_async.py -k asyncio -q
20 passed, 20 deselected in 0.04s
```

and the ids carry the backend, which is what proves the parametrisation reached the tests
rather than merely the fixture:

```
tests/unit/test_dto_async.py::TestAsyncIterIntoFailFast::test_iter_into_with_a_mismatched_dto_raises_at_call[asyncio] PASSED
tests/unit/test_dto_async.py::TestAsyncIterIntoFailFast::test_iter_into_with_a_mismatched_dto_raises_at_call[trio] PASSED
tests/unit/test_dto_async.py::TestAsyncIterIntoLaziness::test_iter_into_lazy_first_item_pulls_exactly_one_batch[asyncio] PASSED
tests/unit/test_dto_async.py::TestAsyncIterIntoLaziness::test_iter_into_lazy_first_item_pulls_exactly_one_batch[trio] PASSED
```

`tests/unit/test_asyncio_trio_matrix.py` is green (3 passed), so the new module satisfies the
AST contract rather than escaping it: the walk selects any module containing an `async def
test_*`, and every test in this module is one. **Every test is `async def` deliberately**,
including the two that assert on `inspect` and never await — a synchronous test would not
request `anyio_backend` and would therefore be collected once, quietly halving the matrix for
that case.

The header was copied from `test_async_cursor.py:27-46` rather than reconstructed, so all
three load-bearing details survive: `pytestmark = pytest.mark.anyio` as a top-level assignment
naming the `anyio` *attribute*, `@pytest.fixture(params=["asyncio", "trio"])` with the
decorator **called** and the backend names as **literal strings** inside the keyword.

## Guard sets for the four async methods, with the line that justifies each

Plan 05's sets transfer **unchanged**, and the reason they transfer is worth stating precisely
rather than assumed by symmetry: adbc-poolhouse does not reimplement any of these. Each async
method offloads the *same* `adbc_driver_manager` function onto a worker thread, so the same
imports happen in the same order on the same code.

| Async method | Guards, in order | Source line that decides it |
|---|---|---|
| `fetch_arrow_table` | pyarrow | ADBC `dbapi.py:1424` `self.reader.read_all` → `reader` property → `_requires_pyarrow()` at `:1359` |
| `fetch_record_batch` | pyarrow | ADBC `dbapi.py:1293` calls `_requires_pyarrow()` directly |
| `fetch_df` | pyarrow, **then** pandas | ADBC `dbapi.py:1428` `self.reader.read_pandas` reaches `:1359` before pandas is imported |
| `fetch_polars` | polars **only** | ADBC `dbapi.py:1430-1441` `polars.from_arrow(self.fetch_arrow())` over the raw PyCapsule stream — no reader is built, `_requires_pyarrow()` is never reached |

The poolhouse side, read this session to confirm it changes nothing (`_async/_cursor.py:384-489`):

```python
    async def fetch_df(self) -> pandas.DataFrame:
        ...
        return cast(
            "pandas.DataFrame",
            await cancellable_offload(
                self._adbc_cancel,
                self._cursor.fetch_df,
                limiter=self._limiter,
                on_abort=self._owner.invalidate,
            ),
        )
```

**And one thing poolhouse says out loud that makes the guard placement non-optional**, quoted
from that method's own docstring:

> `pandas` is not a poolhouse dependency --- you install it yourself. poolhouse never imports
> it: the driver imports `pandas` inside the worker, so a missing install surfaces the native
> `ModuleNotFoundError` unchanged, with no pre-check and no wrapping.

So the guard must run on Semolina's side of the offload, *before* the `await`. Without it the
user's `ModuleNotFoundError` is raised on a worker thread, several frames deep in someone
else's module, naming neither Semolina nor the extra. All four guards are the first statement
in their method for that reason.

## Where poolhouse's async implementation disagreed with ADBC's sync one

**Nowhere.** The plan asked for this to be checked rather than assumed, and the answer is that
the async path is a pure offload of the sync path: `fetch_df` and `fetch_polars` both hand
`self._cursor.fetch_df` / `.fetch_polars` — the ADBC callables themselves — to
`cancellable_offload`. There is no second implementation to disagree.

Two consequences carried into the docstrings rather than left implicit:

- **The `fetch_polars` first-consuming-call rule holds identically on the async cursor.** Its
  mechanism is `fetch_arrow()` *taking* the stream handle and leaving `None`, which is a
  property of the driver, not of threading. The async docstring states it in the same words.
- **The Decimal paragraph is carried across verbatim** from the sync `fetch_polars` docstring,
  including the conditional `decimal256` clause, so a reader comparing the two cursors is not
  left wondering whether the difference in wording means a difference in behaviour. Same for
  `fetch_df`'s `object`-dtype sentence.

## What `into`'s timing claim is, and is not

Recorded because the plan's `must_haves` are careful about it and a later reader might not be.

`iter_into` raises on the **call expression**: no `await`, no `async for`, no reader. That is
D-05 and it is tested with an assertion block containing neither keyword.

`into` is `async def` — it awaits `fetch_arrow_table`, exactly as every other fetch on this
class does — so its check runs before the first await *inside the body*, not before the
caller's `await`. The claim its test makes is therefore deliberately weaker and deliberately
stated: the mismatch raises **before any data moves**, asserted on
`inner.fetch_arrow_table_calls == 0`. D-05 constrains `iter_into` only, and pretending
otherwise would have meant a second shape nobody asked for.

## PEP 525: why the drive loop is not a copy of `__anext__`

`AsyncSemolinaCursor.__anext__` handles a drained reader with `raise` /
`raise StopAsyncIteration from exc`. `_aiter_into_impl` is an async generator, and PEP 525
turns a `StopAsyncIteration` escaping an async generator body into a `RuntimeError` — the
async analogue of the PEP 479 trap Plan 02 hit on the sync side. Both drain paths `return`
instead. Covered by `test_iter_into_over_an_empty_reader_yields_nothing` and
`test_iter_into_treats_a_drained_reader_oserror_as_termination`, and by the creation-time
variant `test_iter_into_normalises_a_drained_reader_creation_error`.

## T-49-03 (pool exhaustion): what actually mitigates it

The threat register rates this high on the async cursor specifically because a leak here is
permanent — there is no `__del__` rescue. Three things were done, and only the first two are
code:

1. **The inner generator takes its reader through `self.fetch_record_batch()`**, the cursor's
   own delegate, so the cursor records it and `aclose()` closes it first. Pinned by
   `test_iter_into_takes_its_reader_through_the_cursors_own_delegate`, which asserts
   `cursor._reader is reader` and `fetch_record_batch_calls == 1`, and by
   `test_aclose_after_a_partial_stream_closes_the_reader_first`, which asserts the close log
   reads `["reader", "cursor", "conn"]` after abandoning the stream half-way.
2. **The docstrings say the async cursor has no `__del__` rescue** and that `async with` is
   the whole mitigation, rather than repeating the sync cursor's gentler wording.
3. **The whole module runs under `-W error::ResourceWarning`** (40 passed), so a test that
   leaks a cursor fails rather than warning into a summary nobody reads.

## Deviations from Plan

### 1. `-k missing_dependency` selects nothing — the working selector is `-k MissingDependency`

Not an auto-fix under Rules 1-3; a defect in a plan acceptance criterion, recorded rather than
worked around. Measured:

```
$ uv run pytest tests/unit/test_cursor.py -k missing_dependency -q --collect-only
collected 48 items / 48 deselected / 0 selected
```

pytest's `-k` is case-sensitive, and Plan 05 named its class `TestMissingDependencyGuards`
with tests `test_each_method_names_its_own_extra` and friends — no item name contains the
lowercase string. The criterion also asked for names kept parallel with Plan 05 "so one `-k`
selects both cursors' cases", and those two requirements cannot both be met literally.

**Parallel naming won**, because it is the one the intent depends on. The async class is
`TestAsyncMissingDependencyGuards` with the same three test names, and the selector that does
what the criterion meant is:

```
$ uv run pytest tests/unit/test_async_cursor.py tests/unit/test_cursor.py -k MissingDependency -q
18 passed, 103 deselected
```

18 = 6 sync items + 12 async (6 × two backends): four parametrised cases, the guard-order case
and the negative case, on each cursor.

### 2. `prek run --all-files` does not check untracked files

Not a code change — a process finding that nearly shipped a lint error. `prek run --all-files`
was run and reported all hooks green while `tests/unit/test_dto_async.py` was still untracked,
so the file was not examined at all. The first `git commit` then failed on `E501` (a 105-char
`def` line) from the same hook set. Worth knowing for any future plan that creates a new file:
`git add` first, then run the hooks, or the green is about the other files.

No source behaviour changed as a deviation, and no Rule 4 situation arose.

## Prohibitions: held

- **The row value path is untouched.** `__anext__`'s `batch.to_pylist()` feeding `Row(...)` is
  byte-unchanged, and no `float()` / `int()` / `Decimal()` conversion was added anywhere. The
  new methods hand conversion to arrowmodel, ADBC, pandas or polars and express no opinion
  about a value. Enforced by execution, not inspection: `tests/unit/test_scope_fence.py`
  reports **2 passed, neither skipped**.
- **No warehouse row value reaches an exception message, a log line, or this artifact.** The
  pre-check reads `description` only and has no values in hand by construction; the guards
  raise before any fetch. Every assertion in the new tests is on a type, a column name, a field
  name, an install string, or a region *dimension* label (`US` / `MX` / `CA`) seeded by the
  probe fixture — never on a metric value.
- **No `asyncio` or `anyio` import entered `src/semolina/`** (ruff TID251 would have failed the
  build; `prek` is green).
- **No `# type: ignore`, no `noqa`, and no pyproject exemption** was added. The two places where
  a union or a protocol fought the checker were resolved with `typing.cast` in source and one
  documented `cast` in the tests.
- **No module-scope optional import** added to `src/semolina/`: `pandas`, `polars`, `pyarrow`
  and `pydantic` entered `acursor.py` under `TYPE_CHECKING` only, so Plan 04's
  `test_packaging_no_module_scope_optional_imports` AST scan stays green.

## Verification Results

| Gate | Result |
|---|---|
| `uv run pytest tests/unit/test_dto_async.py tests/unit/test_async_cursor.py tests/unit/test_asyncio_trio_matrix.py -x -q` | **116 passed** |
| `uv run pytest tests/unit/test_dto_async.py -q` | **40 passed** (20 tests × 2 backends) |
| `uv run pytest tests/unit/test_dto_async.py -k trio -q` / `-k asyncio -q` | 20 passed + 20 deselected, each way |
| `uv run pytest tests/unit/test_dto_async.py -W error::ResourceWarning -x -q` | **40 passed** |
| non-vacuity: fail-fast selection against an `async def iter_into` | **6 failed** (output above), reverted, diff empty |
| `uv run pytest … -k raises_at_call` (both DTO modules) | 6 passed |
| `uv run pytest … -k lazy` (both DTO modules) | 6 passed |
| `uv run pytest … -k MissingDependency` (both cursor modules) | 18 passed |
| `uv run pytest tests/unit/test_scope_fence.py -q` | 2 passed, **neither skipped** |
| `uv run pytest -q` (root) | **1480 passed**, 16 skipped, 2 xfailed |
| `just test` (jaffle-shop half) | 16 passed, 15 skipped |
| `prek run --all-files` | all hooks passed, incl. basedpyright strict |
| `inspect` gate on `iter_into` / `_aiter_into_impl` / `into` | `OK` |
| AST gate: no `Await`/`Yield`/`YieldFrom` in `iter_into` | `AST OK` |

The three warnings in the root run are the polars `FutureWarning` from
`adbc_driver_manager/dbapi.py:1436` — one from the sync `fetch_polars` test and two from the
new async one (once per backend). Plan 05 measured it on this exact stack; it is ADBC's to fix,
no suppression was added, and it is not a failure.

## Known Stubs

None. All four async methods are fully implemented and exercised, and `iter_into`'s shape is
pinned by three independent checks (two `inspect` assertions, one AST walk, one behavioural
test) rather than by convention.

## Requirement Status

`DTO-01`, `DTO-02`, `RESULT-01` and `RESULT-02` are complete across **both** cursors as of this
plan. Plan 05 ticked `RESULT-01`/`RESULT-02` for the sync half and said re-ticking here would
be harmless; this is that re-tick, and it is the one that makes them true of the whole surface.

## Next Phase Readiness

Ready. Four things Plan 07's docs should take from here rather than re-derive:

- **`async for dto in cursor.iter_into(DTO)` needs no `await` on the call**, and that is worth
  one sentence in the docs because it looks like a typo to anyone used to `await`-everything
  async APIs. `await cursor.into(DTO)` *does* take one.
- **Do not write that the async reader's `.schema` is free.** It is (a plain `@property`,
  measured at two microseconds), but that is a property of adbc-poolhouse 1.6.2 rather than of
  Semolina, and nothing in Semolina depends on it — the pre-check reads `description`. This
  plan's `<flagged_assumptions>` asked for exactly this restraint.
- **The async examples must use `async with`.** Not style: the async cursor cannot rescue a
  forgotten close, so an example that omits it documents a permanent pool leak.
- **`fetch_polars()` must be the first consuming call**, on both cursors, for the same
  driver-level reason. An example that shows `fetch_polars()` after `into()` on one cursor is
  showing a `ProgrammingError`.

## Self-Check: PASSED

- `src/semolina/acursor.py` — exists; `AsyncSemolinaCursor.into`, `.iter_into`,
  `._aiter_into_impl`, `.fetch_df` and `.fetch_polars` all resolve by import (`inspect` gate
  ran on all five).
- `tests/unit/test_dto_async.py` — exists, 40 tests collected.
- `tests/unit/test_async_cursor.py` — exists, 73 tests collected (57 before).
- `.planning/phases/49-into-dto-typed-results/49-06-SUMMARY.md` — this file.
- All three claimed commits resolve in `git log`: `809f845`, `5a9eac7`, `17ab24b`.
- Working tree clean before this SUMMARY was written.

---
*Phase: 49-into-dto-typed-results*
*Completed: 2026-08-14*
