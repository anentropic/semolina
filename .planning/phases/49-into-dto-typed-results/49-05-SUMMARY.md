---
phase: 49-into-dto-typed-results
plan: 05
subsystem: api
tags: [adbc, passthrough, pandas, polars, pyarrow, optional-dependencies, error-messages, decimal]

requires:
  - phase: 49-into-dto-typed-results
    plan: 01
    provides: "_require(package, extra), SemolinaMissingDependencyError, and the [pyarrow]/[pandas]/[polars] extras these guards name in their messages"
  - phase: 49-into-dto-typed-results
    plan: 03
    provides: "The measured polars Decimal row in 47-TYPE-FIDELITY.md, which is the only permitted source for fetch_polars()'s Decimal sentence"
  - phase: 39-adbc-passthrough
    provides: "fetch_arrow_table / fetch_record_batch — the two-line ADBC delegate shape and the lifetime-docstring register both new methods copy"
provides:
  - "SemolinaCursor.fetch_df() -> pandas.DataFrame — guarded pyarrow then pandas"
  - "SemolinaCursor.fetch_polars() -> polars.DataFrame — guarded on polars ONLY"
  - "pyarrow guards on fetch_arrow_table and fetch_record_batch, closing the pre-phase hole where pyarrow was declared only inside [duckdb]"
  - "The per-method guard set, derived by reading ADBC's own implementation and pinned by tests"
  - "tests/unit/test_cursor.py: probe_engine / _probe_cursor / _find_spec_without and 9 tests across three classes"
affects: [49-06-async-twins, 49-07-docs]

actuals:
  tokens: 4437
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Guard a delegate for what the delegate's own implementation imports, read from its source — not for what its siblings import"
    - "A per-method dependency test patches find_spec to report exactly ONE package absent, so it asserts the message the method actually owns rather than whichever guard happens to fire first"

key-files:
  created:
    - .planning/phases/49-into-dto-typed-results/49-05-SUMMARY.md
  modified:
    - src/semolina/cursor.py
    - tests/unit/test_cursor.py

key-decisions:
  - "fetch_df is guarded on pyarrow AND pandas, pyarrow first — confirmed by reading ADBC, not assumed: `fetch_df` is `self.reader.read_pandas()` and the `reader` property calls `_requires_pyarrow()` before pandas is imported"
  - "fetch_polars is guarded on polars ONLY, correcting D-15's list — ADBC hands polars the raw PyCapsule stream via `polars.from_arrow(self.fetch_arrow())`, builds no reader, and never reaches pyarrow"
  - "The consumed-result error from a second consumer is left unwrapped: ADBC's own message already says the result set was closed or consumed, and wrapping it would hide which library owns the rule"
  - "fetch_polars() carries NO precision caveat, because Plan 03 measured polars preserving decimal128 as a native Decimal dtype. The only caveat written is the conditional decimal256 one, phrased as unreachable on all three supported backends"
  - "The probe_engine fixture and the find_spec_without helper are restated in test_cursor.py rather than imported across test modules — no cross-test-module import precedent exists in this repo, and both are under ten lines"

patterns-established:
  - "Every RESULT-02 test asserts the literal `pip install semolina[<extra>]` string for its own extra, so a copy-paste error that gives every method the same extra fails rather than shipping"

requirements-completed: [RESULT-01, RESULT-02]

coverage:
  - id: R1
    description: "fetch_df() returns a pandas.DataFrame and fetch_polars() a polars.DataFrame from a live in-memory DuckDB semantic-view result, asserted by isinstance against the real classes"
    requirement: RESULT-01
    verification:
      - kind: unit
        ref: "tests/unit/test_cursor.py#TestFetchDf::test_returns_a_pandas_dataframe"
        status: pass
      - kind: unit
        ref: "tests/unit/test_cursor.py#TestFetchPolars::test_returns_a_polars_dataframe"
        status: pass
    human_judgment: false
  - id: R2
    description: "fetch_polars() must be the first consuming call: after fetch_record_batch() it raises the driver's own ProgrammingError, unwrapped by Semolina"
    requirement: RESULT-01
    verification:
      - kind: unit
        ref: "tests/unit/test_cursor.py#TestFetchPolars::test_after_fetch_record_batch_raises_the_drivers_own_error"
        status: pass
    human_judgment: false
  - id: R3
    description: "Each of the four Arrow/dataframe methods raises SemolinaMissingDependencyError naming its own package and its own literal install command"
    requirement: RESULT-02
    verification:
      - kind: unit
        ref: "tests/unit/test_cursor.py#TestMissingDependencyGuards::test_each_method_names_its_own_extra (4 params)"
        status: pass
      - kind: unit
        ref: "tests/unit/test_cursor.py#TestMissingDependencyGuards::test_fetch_df_reports_pyarrow_before_pandas"
        status: pass
    human_judgment: false
  - id: R4
    description: "fetch_polars() does not raise when pyarrow is absent and polars is present — it delegates and returns"
    requirement: RESULT-02
    verification:
      - kind: unit
        ref: "tests/unit/test_cursor.py#TestMissingDependencyGuards::test_fetch_polars_does_not_require_pyarrow"
        status: pass
    human_judgment: false
  - id: R5
    description: "fetch_polars()'s Decimal sentence is sourced from the committed 47-TYPE-FIDELITY.md polars row, not from an expectation"
    verification:
      - kind: other
        ref: "docstring vs `grep '^| polars |' 47-TYPE-FIDELITY.md` — both quoted side by side below"
        status: pass
    human_judgment: true
    rationale: "That the docstring paraphrases the measured row faithfully, and that the decimal256 clause is worded as unreachable rather than as a hazard, is a judgment about prose. The two texts are quoted below so a reader can check the paraphrase themselves."

duration: 18min
completed: 2026-08-14
status: complete
---

# Phase 49 Plan 05: `fetch_df` / `fetch_polars` and the Guard Sets Summary

**Both dataframe entry points ship as one-line ADBC delegates, and each of the four Arrow/dataframe methods is now guarded for exactly what its own ADBC implementation imports — `fetch_polars` on polars alone, which is the correction D-15 needed and which a test now pins so a later consistency tidy-up cannot break a working call.**

## Performance

- **Duration:** ~18 min
- **Tasks:** 2, both `type="auto"`, no checkpoints
- **Files modified:** 2 (330 inserted, 1 deleted)
- **Tests added:** 9 (root suite 1415 → 1424)

## Task Commits

1. **Task 1: `fetch_df` and `fetch_polars`, and a guard on each method for what it actually imports** — `5f1737c` (feat)
2. **Task 2: Prove the returns live, and prove every guard message names the install** — `931bb7d` (test)

## The ADBC source line that decided `fetch_df`'s guard set

The plan required this to be confirmed by reading, not assumed. It is confirmed, and the answer
is **pyarrow AND pandas**. From `.venv/lib/python3.14/site-packages/adbc_driver_manager/dbapi.py`,
quoted verbatim:

```python
1427    def fetch_df(self) -> "pandas.DataFrame":
1428        return _blocking_call(self.reader.read_pandas, (), {}, self._stmt.cancel)
```

`self.reader` is the property immediately above it, and line **1359** is the one that settles it:

```python
1356    @property
1357    def reader(self) -> "_reader.AdbcRecordBatchReader":
1358        if self._reader is None:
1359            _requires_pyarrow()
```

So `fetch_df` reaches `_requires_pyarrow()` **before** anything imports pandas — `read_pandas`
is a pyarrow reader method. Guard order therefore matters and is not cosmetic: pyarrow first,
then pandas. Guarding pandas first would let ADBC's own
`ProgrammingError("This API requires PyArrow to be installed")` (`:1479-1484`) win on a
pyarrow-less install, naming neither Semolina nor the extra.

The planner's reading was right, and the flagged assumption on RESULT-02 is now closed by
measurement rather than by symmetry.

## The line that keeps `fetch_polars` off the pyarrow guard

Same file, and the reason D-15's list of four pyarrow-guarded methods over-guards one of them:

```python
1430    def fetch_polars(self) -> "polars.DataFrame":
1431        import polars
1432
1433        return _blocking_call(
1434            lambda: typing.cast(
1435                polars.DataFrame,
1436                polars.from_arrow(self.fetch_arrow()),
1437            ),
```

`self.fetch_arrow()` at `:1443-1450` returns the raw `ArrowArrayStreamHandle`. No reader is
built, so the `reader` property is never entered and `_requires_pyarrow()` is never called.
`fetch_polars()` is guarded on **polars only**. A pyarrow guard here would refuse a call that
works, which is a worse failure than the one RESULT-02 exists to fix.

The same three lines are the mechanism behind the first-consuming-call rule:

```python
1443    def fetch_arrow(self) -> _lib.ArrowArrayStreamHandle:
1444        if self._handle is None:
1445            raise ProgrammingError(
1446                "Result set has been closed or consumed",
...
1449        handle, self._handle = self._handle, None
1450        return handle
```

It *takes* the handle and leaves `None`. Anything that already created a reader — iteration,
`fetch_record_batch()`, `fetch_arrow_table()`, `into()`, `iter_into()` — leaves it nothing.

## Final guard sets

| Method | Guards, in order | Why |
|---|---|---|
| `fetch_arrow_table` | pyarrow | `self.reader.read_all` → `reader` property → `_requires_pyarrow()` (`:1424`, `:1359`) |
| `fetch_record_batch` | pyarrow | `_requires_pyarrow()` called directly in the method (`:1293`) |
| `fetch_df` | pyarrow, then pandas | `self.reader.read_pandas` → both (`:1428`, `:1359`) |
| `fetch_polars` | polars | raw PyCapsule stream, no reader (`:1430-1441`) |

The pyarrow guards on `fetch_arrow_table` / `fetch_record_batch` close a hole that predates
this phase: `pyarrow` was declared only inside the `[duckdb]` extra, so a base install plus
`[snowflake]` could reach `fetch_arrow_table()` and fail with ADBC's message.

## The Decimal sentence, and the row it came from

The committed artifact row, byte-for-byte from `47-TYPE-FIDELITY.md:200`:

```
| polars | polars 1.43.2: dtype `Decimal(precision=38, scale=2)`, elements `decimal.Decimal` | measured | A3 |
```

The paragraph written into `fetch_polars`'s docstring, byte-for-byte from `cursor.py`:

> A ``DECIMAL`` metric keeps its precision and its type: polars 1.43.2 gives a warehouse
> ``decimal128(38, 2)`` column a native ``Decimal(precision=38, scale=2)`` dtype holding
> ``decimal.Decimal`` values, measured on this project's own type-fidelity probe. That is
> better than ``fetch_df()``, where the same column falls back to an untyped ``object``
> dtype. One condition, recorded because it is reachable in principle and not in practice:
> polars was measured raising a Rust ``PanicException`` on a ``decimal256`` column, and no
> backend Semolina supports has been observed producing one — a Snowflake ``NUMBER`` stops at
> precision 38, and Databricks and DuckDB decimals stop there too.

**No precision caveat was written, because the measurement does not support one.** Plan 03's
"Next Phase Readiness" said exactly this, and the artifact agrees: the Decimal survives with
its scale. The only caveat available is the conditional `decimal256` one, and it is phrased as
unreachable rather than as a hazard — one clause inside a paragraph, matching how Plan 03
handled the same fact in the generated artifact.

`fetch_df`'s docstring carries the contrasting sentence sourced from the pandas row on the same
table (`object` dtype holding `decimal.Decimal`), so a reader choosing between the two methods
sees the tradeoff at the point of choice.

## Deviations from Plan

**None.** Both tasks executed as written. The one thing the plan told me to confirm rather than
assume — `fetch_df`'s pyarrow dependency — confirmed the planner's reading, so no correction
was needed there either.

## Findings recorded rather than fixed

**1. The polars `FutureWarning` DOES fire on adbc-driver-manager 1.10.0.** `49-RESEARCH.md`
§ Pitfall 7 says "the project venv's adbc-driver-manager is 1.10.0 and does not emit the
warning; 1.12.0 does". Measured this session on 1.10.0 + polars 1.43.2, it does:

```
.venv/…/adbc_driver_manager/dbapi.py:1436: FutureWarning: from_arrow(<ArrowStreamExportable>)
will return a Series instead of a DataFrame in 2.0.
```

It surfaces once in the root suite, from `test_returns_a_polars_dataframe`. Nothing was done
about it, deliberately: the project's `filterwarnings` does not promote warnings to errors, the
warning is ADBC's to fix, and Plan 01 already recorded the polars-2.0 break as a known future
change in `pyproject.toml`'s `[polars]` extra comment rather than capping the floor. Recorded
here only because the research note is now wrong about which version emits it, and Plan 06 will
hit the same warning through the async twin.

**2. `fetch_df()` was measured NOT to consume the stream in a way that breaks `description`,**
consistent with RESEARCH.md § Pitfall 5. That observation is deliberately **not** documented as
a contract in the docstring — the flagged assumption says it is an observation about
adbc-driver-manager 1.10.0/1.12.0, not a rule. `fetch_df`'s docstring says only "pick one
consumption pattern per cursor", which is true of every consuming method here.

## Prohibitions: held

- **The row value path is untouched.** No `float()` / `int()` / `Decimal()` conversion was added
  anywhere; `batch.to_pylist()` feeding `Row(...)` is byte-unchanged. Both new methods are
  literally `_require(...)` lines plus `return self._cursor.fetch_*()`. Enforced by execution:
  `tests/unit/test_scope_fence.py` reports **2 passed, neither skipped**.
- **No warehouse row value reaches an exception message, a log line or this artifact.** The
  guards raise before any fetch and have no values in hand; the assertions in this plan's tests
  are on `isinstance`, on column names, and on region *dimension* labels (`US` / `MX` / `CA`)
  seeded by the probe fixture — never on a metric value.
- **Neither conversion is reimplemented.** Both delegate to ADBC, which is already
  cancellation-aware through `_blocking_call(..., self._stmt.cancel)`.
- **No module-scope optional import added**, so Plan 04's
  `test_packaging_no_module_scope_optional_imports` AST scan stays green — `pandas` and `polars`
  entered `cursor.py` only under `TYPE_CHECKING`.

## Verification Results

| Gate | Result |
|---|---|
| `uv run pytest tests/unit/test_cursor.py -x -q` | **48 passed** (39 before) |
| `uv run pytest tests/unit/test_cursor.py -k "FetchDf or FetchPolars or MissingDependency" -v` | **9 passed** — 4 parametrised + guard-order + negative + 3 live |
| `uv run pytest tests/unit/test_scope_fence.py -x -q` | 2 passed, **neither skipped** |
| `uv run pytest -q` (root) | **1424 passed**, 16 skipped, 2 xfailed |
| `just test` (jaffle-shop half) | 16 passed, 15 skipped |
| `prek run --all-files` | all hooks passed, incl. basedpyright strict — **no `# type: ignore`, no `noqa`, no pyproject exemption added** |
| `uv run python -c "…inspect.getsource…"` | `fetch_df 42`, `fetch_polars 51` — both resolve |

The `polars.from_arrow` typing friction Plan 03 warned about did **not** recur here, and the
reason is worth recording: Semolina never calls `from_arrow` itself. It delegates to ADBC's
`fetch_polars`, which does its own `typing.cast` internally, so the `DataFrame | Series` union
never reaches Semolina's code. The return annotation is a plain `polars.DataFrame` under
`TYPE_CHECKING` and basedpyright strict accepts it unassisted.

## Known Stubs

None. Both methods are fully implemented; there is nothing left to wire. The async twins
(`AsyncSemolinaCursor.fetch_df` / `fetch_polars`) do not exist yet and are Plan 06's — not
stubbed, simply not in this plan, which is why `RESULT-01` and `RESULT-02` are recorded as the
**sync half** below.

## Requirement Status

`RESULT-01` and `RESULT-02` are ticked. Both are satisfied on the synchronous cursor, which is
this plan's stated scope (`success_criteria`: "the async twins are Plan 06"). Plan 06 will
mirror the same four guard sets onto `AsyncSemolinaCursor`; if the phase's convention is to
leave a requirement pending until both cursors ship, Plan 06 re-ticking them is harmless.

## Next Phase Readiness

Ready. Three things Plan 06 should carry over rather than re-derive:

- **The guard sets transfer unchanged.** poolhouse's `AsyncCursor.fetch_df` / `fetch_polars`
  offload the same ADBC calls into a worker thread, so the same imports happen in the same
  order — and poolhouse explicitly declines to pre-check them, which is why the guard must live
  on Semolina's side of the offload. Guard **before** the `await`, not inside it.
- **The first-consuming-call rule applies identically to the async cursor**, because the
  mechanism is `fetch_arrow()` taking the handle, not anything about threading. Phase 46 already
  documents one-reader-per-cursor there; `fetch_polars` is a stricter case of it.
- **`fetch_polars` on polars only.** The same test — pyarrow absent, polars present, call
  succeeds — is the one to write for the async twin, for the same reason: it stops a later
  tidy-up from "making the guards consistent" and silently breaking a working call.

## Self-Check: PASSED

- `src/semolina/cursor.py` — exists; `SemolinaCursor.fetch_df` and `SemolinaCursor.fetch_polars`
  both resolve by import (`inspect.getsource` ran on both).
- `tests/unit/test_cursor.py` — exists, 48 tests collected.
- `.planning/phases/49-into-dto-typed-results/49-05-SUMMARY.md` — this file.
- Both claimed commits resolve in `git log`: `5f1737c`, `931bb7d`.
- Working tree clean before this SUMMARY was written.

---
*Phase: 49-into-dto-typed-results*
*Completed: 2026-08-14*
</content>
</invoke>
