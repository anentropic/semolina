# Phase 49: `.into(DTO)` Typed Results - Pattern Map

**Mapped:** 2026-08-14
**Files analyzed:** 12 (3 new source, 4 modified source, 4 new tests, 1 CI workflow)
**Analogs found:** 12 / 12 (11 exact/role-match, 1 partial)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/semolina/exceptions.py` (new) | error module + `_require` guard | n/a (control) | `src/semolina/engines/base.py:22-27` (classes) + `src/semolina/codegen/python_renderer.py:429-440` (`ruff_available`) | exact (split across two) |
| `src/semolina/dto.py` (new) | service (structural pre-check) | transform (schema→verdicts) | `src/semolina/codegen/annotation_check.py:96-130` — **report shape only**, see warning | partial |
| `src/semolina/codegen/arrow_map.py` (modified: `arrow_type_to_runtime_type`) | utility | transform | `arrow_map.py:26-114` `arrow_type_to_python` itself | exact |
| `src/semolina/cursor.py` (modified) | cursor / result surface | request-response + streaming | `cursor.py:139-197` (`fetch_arrow_table` / `fetch_record_batch`), `cursor.py:238-285` (`__next__` batch loop) | exact |
| `src/semolina/acursor.py` (modified) | async cursor | streaming | `acursor.py:181-251` (async passthroughs), `acursor.py:255-266` (sync `description`) | exact |
| `src/semolina/__init__.py` (modified) | package export | n/a | `__init__.py:14, 48-49` (existing error exports) | exact |
| `pyproject.toml` (modified) | config | n/a | `pyproject.toml:38-68` (`duckdb`, `async`, `all` extras) | exact |
| `tests/type_fidelity_probe.py::_measure_polars` (modified) | probe measurement | transform | `tests/type_fidelity_probe.py:1499-1532` `_measure_pandas` | exact |
| `tests/unit/test_dto.py` (new) | unit test | request-response | `tests/unit/test_cursor.py` + `tests/unit/codegen/test_python_renderer.py:1065-1093` (find_spec patch) | exact |
| `tests/unit/test_dto_async.py` (new) | async unit test | streaming | `tests/unit/test_async_cursor.py:1-55` — **must satisfy the AST matrix, see below** | exact |
| `tests/unit/test_dto_duckdb.py` (new) | live-DuckDB unit test | request-response | `tests/unit/test_type_fidelity_duckdb.py:1-140` | exact |
| `tests/unit/test_dto_packaging.py` (new) | packaging contract test | file-I/O (reads pyproject) + subprocess | `tests/unit/test_async_packaging.py` (whole file) | exact |
| `.github/workflows/ci.yml` `packaging-smoke` (modified) | CI job | n/a | `ci.yml:149-180` (extend, do not replace) | exact |

---

## Pattern Assignments

### `src/semolina/exceptions.py` (new — errors + `_require`)

**Analog A — class shape:** `src/semolina/engines/base.py:22-27`

```python
class SemolinaViewNotFoundError(RuntimeError):
    """Raised when the requested semantic view does not exist in the warehouse."""


class SemolinaConnectionError(RuntimeError):
    """Raised when the engine cannot connect to or authenticate with the warehouse."""
```

Flat `RuntimeError` subclass, one-line docstring beginning "Raised when …", no body, no
common base. Copy exactly for `SemolinaMissingDependencyError` and
`SemolinaSchemaMismatchError`. Note the analogs are defined **above** the class that raises
them, at module top after imports. D-14 leaves `engines/base.py` untouched.

**Analog B — the `find_spec` guard helper:** `src/semolina/codegen/python_renderer.py:429-440`

```python
def ruff_available() -> bool:
    """
    Report whether ruff can be invoked in the current environment.

    ruff ships as the optional ``codegen-lint`` extra. When it is installed,
    :func:`format_with_ruff` produces formatted, import-sorted output; otherwise
    the generated source is returned unchanged.

    Returns:
        True if the ``ruff`` package is importable, False otherwise.
    """
    return importlib.util.find_spec("ruff") is not None
```

Two load-bearing details for RESULT-02: the module imports `importlib` (not
`from importlib.util import find_spec`), and the call is spelled `importlib.util.find_spec(...)`
**inside** the function body — that is exactly what makes `patch("importlib.util.find_spec", ...)`
reach it. `_require(package, extra)` must keep both properties or its tests silently stop
patching anything.

---

### `src/semolina/dto.py` (new — the structural pre-check)

**Analog:** `src/semolina/codegen/annotation_check.py` — **report shape only.**

Copyable (`annotation_check.py:96-130`):

```python
@dataclass(frozen=True)
class FieldCheckRow:
    """
    One field's verdict.

    Attributes:
        name: The field name, as the warehouse (or the committed model) spells it.
        committed: The annotation the committed model declares, or :data:`ABSENT`.
        probed: The annotation the result schema implies, or :data:`ABSENT`.
        route: What produced ``probed`` ...
        status: :data:`STATUS_MATCH` or :data:`STATUS_DRIFT`.
        detail: Why the row drifted for a reason the two annotation columns cannot show ...
    """

    name: str
    committed: str
    probed: str
    route: str
    status: str
    detail: str = ""
```

Take from this: a frozen dataclass per field with a `name` / expected / got / `status`
quartet, module-level string constants for statuses with docstring-per-constant
(`STATUS_MATCH`, `STATUS_DRIFT`, `ABSENT` at :74-88), and the stated rule "No row value ever
reaches a report" (:22-25).

**DO NOT copy or import** (all probe-coupled, absent at `.into()` time):

| Element | Location | Why it cannot be reused |
|---|---|---|
| `probe_schema` import | `annotation_check.py:39` | requires a live probe query |
| `IntrospectedField` / `IntrospectedView` | `:45` (TYPE_CHECKING) | codegen introspection models |
| `CommittedField` / `CommittedModel` | `:46` | textually parsed committed source |
| `ROUTE_*` constants, `route` field | `:47-71` | describe which probe route resolved the value |
| `metric_annotation` import | `:41` | renderer, produces annotation **strings** |

The comparator is **string-vs-string** over renderer output. The pre-check holds real runtime
objects from `DTO.model_fields[name].annotation`. Build a fresh comparator in `dto.py`; import
nothing from `codegen/`.

**Placement rationale to preserve:** `dto.py` sits at `src/semolina/` top level, beside
`cursor.py`/`results.py` (the result half), not under `codegen/` (the probe/render half).

---

### `src/semolina/codegen/arrow_map.py` (modified — `arrow_type_to_runtime_type`)

**Analog:** the function it sits beside, `arrow_map.py:26-114`.

Signature and dispatch shape to mirror:

```python
def arrow_type_to_python(dtype: pyarrow.DataType) -> str | None:
```

Predicate cascade, in this exact order (order is load-bearing and commented as such at :62-65):
`is_boolean` → `is_decimal` → `is_integer` → `is_floating` → `is_dictionary`/`is_run_end_encoded`
(recursive on `dtype.value_type`) → `is_string`/`is_large_string`/`is_string_view` →
the four binary predicates → `is_date` → `is_timestamp` → `is_time` → `return None`.

Exhaustive return set (every literal the cascade can produce): `"bool"`, `"decimal.Decimal"`,
`"int"`, `"float"`, `"str"`, `"bytes"`, `"datetime.date"`, `"datetime.datetime"`,
`"datetime.time"`, plus a recursive call and `None`.

The new sibling must be a **thin adapter over the same cascade** (`arrow_type_to_python` then a
name→type dict), never a second cascade — the module docstring's whole thesis (:4-8) is that
two mappings must not drift. Note this module imports `pyarrow` at module scope (`:22-23`),
which is fine because `codegen/` is not on the base-import path; `dto.py`/`cursor.py` must NOT
follow that and must keep pyarrow under `TYPE_CHECKING`.

---

### `src/semolina/cursor.py` (modified — `into`, `iter_into`, `fetch_df`, `fetch_polars`, guards)

**Analog 1 — the optional-import header** (`cursor.py:1-18`):

```python
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from .results import Row

if TYPE_CHECKING:
    import pyarrow
```

`from __future__ import annotations` is what lets `-> pyarrow.Table` resolve with no runtime
import. `pandas`, `polars`, `arrowmodel` and `pydantic` (for `type[BaseModel]`) go in the same
`TYPE_CHECKING` block; the runtime import is function-local, after the `_require` guard.

**Analog 2 — the two-line ADBC delegate with a long lifetime docstring**
(`cursor.py:139-163`, the shorter of the pair):

```python
    def fetch_arrow_table(self) -> pyarrow.Table:
        """
        Fetch all remaining rows as a PyArrow Table (ADBC passthrough).

        Delegates to the underlying ADBC cursor's ``fetch_arrow_table()``
        method for zero-copy Arrow data transfer.

        Requires an ADBC-capable cursor (Snowflake, Databricks, or DuckDB
        pool connections). Not supported by non-ADBC cursors.

        Returns:
            ``pyarrow.Table`` with the query results.

        Raises:
            AttributeError: If the underlying cursor does not support
                ``fetch_arrow_table()`` (e.g. a non-ADBC cursor).

        Example:
            .. code-block:: python

                cursor = Sales.query().metrics(Sales.revenue).execute()
                table = cursor.fetch_arrow_table()
                df = table.to_pandas()
        """
        return self._cursor.fetch_arrow_table()
```

`fetch_df` / `fetch_polars` copy this exactly — one delegating line, plus (new) a `_require(...)`
line above it, plus a `Raises: SemolinaMissingDependencyError` entry. Note `Example:` uses
`.. code-block:: python`, **never** `>>>`: root pytest runs `--doctest-modules` over
`testpaths = ["tests", "src"]`, so a doctest importing arrowmodel would fail on a base install.

**Analog 3 — the streaming-lifetime docstring paragraph** (`cursor.py:174-181`), the sentences
`iter_into` and `fetch_polars` must restate:

```
        The returned reader shares state with this cursor's other fetch
        methods — consume the reader before calling ``fetchone()``,
        ``fetch_arrow_table()``, or iterating the cursor.

        The cursor must outlive the reader: consume the reader inside the
        context manager (or before ``.close()``). See arrow-adbc issue #1893.
```

**Analog 4 — the per-batch drive loop** (`cursor.py:266-282`), the shape `_iter_into_impl`
replaces `to_pylist()` in:

```python
        reader = self._reader
        assert reader is not None  # narrowing for the type checker
        while self._batch_pos >= len(self._batch_rows):
            try:
                batch = reader.read_next_batch()
            except StopIteration:
                self._stream_exhausted = True
                raise
            except OSError as exc:
                # ADBC drivers may surface drained-reader access as OSError
                # rather than StopIteration; normalise to iteration termination.
                self._stream_exhausted = True
                raise StopIteration from exc
            if batch.num_rows == 0:
                continue
            self._batch_rows = batch.to_pylist()
```

Two behaviours to carry into `iter_into`: zero-row batches are skipped, and a drained reader
may surface as `OSError` rather than `StopIteration`. **Do not touch `cursor.py:281-283`** —
`batch.to_pylist()` feeding `Row(...)` is the value path 47-DECISIONS.md Decision 1 prohibits
changing.

**Analog 5 — `description` as the pre-check source** (`cursor.py:201-209`), sync on both
cursors, and the extractor idiom at `cursor.py:55-65`:

```python
    def _column_names(self) -> list[str]:
        desc = self._cursor.description
        if desc is None:
            return []
        return [d[0] for d in desc]
```

The pre-check needs `d[0]` (name) and `d[1]` (a `pyarrow.DataType`) from the same 7-tuples.
Handle `description is None` the same defensive way.

---

### `src/semolina/acursor.py` (modified — the async twins)

**Analog 1 — async delegate** (`acursor.py:181-204`): identical to the sync analog but
`async def` + `return await self._cursor.fetch_arrow_table()`. `fetch_df` / `fetch_polars`
follow this.

**Analog 2 — the reader-ownership delegate** (`acursor.py:249-251`), which `iter_into`'s inner
async generator must go through rather than calling the raw cursor:

```python
        if self._reader is None:
            self._reader = await self._cursor.fetch_record_batch()
        return self._reader
```

Its docstring (`:206-248`) carries the rules the new methods must not contradict: one reader per
cursor; a repeat call returns the reader already in flight; close the reader before the cursor;
`Any` return type because poolhouse's reader class is not a public importable name.

**Analog 3 — sync-property justification** (`acursor.py:255-266`), the precedent that lets
`iter_into` stay a plain `def` on the async cursor:

```python
    @property
    def description(self) -> list[tuple[Any, ...]] | None:
        """
        Cursor description passthrough.

        Synchronous, with no await, because adbc-poolhouse keeps it a plain
        property read: there is no I/O to offload.
        ...
        """
        return self._cursor.description
```

**Analog 4 — plain `__aiter__` beside `async def` fetchers** (`acursor.py:282-293`): Phase 46's
precedent for D-05's "plain method returning an async iterator".

---

### `src/semolina/__init__.py` (modified — export two errors)

**Analog:** `__init__.py:14` and `:48-49`.

```python
from .engines.base import SemolinaConnectionError, SemolinaViewNotFoundError
```

```python
__all__ = [
    "__version__",
    "AsyncSemolinaCursor",
    ...
    "SemolinaCursor",
    "SemolinaConnectionError",
    "SemolinaViewNotFoundError",
    ...
]
```

Add `from .exceptions import SemolinaMissingDependencyError, SemolinaSchemaMismatchError`
(alphabetical among the relative imports, after `.engines.base`) and both names to `__all__`.
`__all__` is dunder-first then roughly alphabetical with classes before functions — match the
surrounding ordering, and let ruff isort settle the import block.

**Guard test analog:** `tests/unit/test_public_surface.py:17-25`

```python
    def test_is_exported_in_all(self) -> None:
        """``JsonValue`` is in ``semolina.__all__``, so it is a supported public name."""
        assert "JsonValue" in semolina.__all__
```

---

### `pyproject.toml` (modified — four extras, `[all]`, lock)

**Analog:** `pyproject.toml:38-68`.

```toml
duckdb = [
    # Pinned: the version-locked `semantic_views` community extension only has
    # published binaries for specific DuckDB core versions. Bumped automatically
    # by .github/workflows/duckdb-extension-check.yml when a newer build ships.
    "duckdb==1.5.5",
    "pyarrow>=17.0.0",
]
codegen-lint = [
    # Optional: lets `semolina codegen` emit ruff-formatted, import-sorted source.
    "ruff>=0.15.1",
]
async = [
    # Optional: pulls in adbc-poolhouse's async stack ... Two separate reasons set this floor.
    # Not 1.5.0: ...
    # Not 1.6.1: ...
    "adbc-poolhouse[async]>=1.6.2",
]
all = [
    "semolina[snowflake,databricks,duckdb,async]",
]
```

Two conventions this file enforces: **every extra carries a comment justifying its floor** (the
`async` block is the maximal form — a paragraph per rejected version), and `all` is a single
self-referencing `semolina[...]` requirement, not a repeated list. The `duckdb` extra's
`"pyarrow>=17.0.0"` becomes `"semolina[pyarrow]"` per D-15, following how `snowflake` already
references `adbc-poolhouse[snowflake]`.

`--locked` CI (`ci.yml:34, 55, 76, 107`) means `uv.lock` is regenerated and committed in the
same commit.

---

### `tests/type_fidelity_probe.py::_measure_polars` (modified)

**Analog:** `_measure_pandas` at `tests/type_fidelity_probe.py:1499-1532`.

```python
def _measure_pandas(table: Any) -> DownstreamObservation:
    """
    Measure what ``pyarrow.Table.to_pandas()`` does with the decimal column.

    Closes RESEARCH.md assumption A2 ... Imported inside the function so an absent
    pandas produces an honest artifact row instead of an import error.

    Args:
        table: The probe result table.

    Returns:
        The observation for the ``pandas`` row.
    """
    try:
        import pandas
    except ImportError:
        return DownstreamObservation(
            consumer="pandas",
            observed="not measured — pandas not installed",
            status=STATUS_NOT_MEASURED,
            assumption="A2",
        )

    column = table.to_pandas()[DECIMAL_PROBE_FIELD]
    element_type = python_value_type_name(column.iloc[0])
    return DownstreamObservation(
        consumer="pandas",
        observed=(
            f"pandas {pandas.__version__}: dtype `{column.dtype}`, elements `{element_type}`"
        ),
        status=STATUS_MEASURED,
        assumption="A2",
    )
```

Copy verbatim, substituting: `table` parameter added to the current no-arg
`_measure_polars()` (:1575, called at :1634 — update the call site to `_measure_polars(table)`),
`polars.from_arrow(table)[DECIMAL_PROBE_FIELD]`, `column[0]` instead of `column.iloc[0]`,
`assumption="A3"`, and the existing `importlib.util.find_spec("polars")` absent-branch kept
(returning `STATUS_NOT_MEASURED`) rather than the analog's `try/import`. Keep
`python_value_type_name(...)` and the `f"polars {polars.__version__}: dtype ..."` sentence shape
so the artifact's cells stay parallel.

---

### `tests/unit/test_dto.py` (new)

**Analog A — the find_spec monkeypatch:** `tests/unit/codegen/test_python_renderer.py:1078-1093`

```python
class TestRuffAvailable:
    """Tests for ruff_available() helper."""

    def test_true_when_installed(self) -> None:
        """ruff_available() is True when importlib finds the ruff package."""
        from semolina.codegen.python_renderer import ruff_available

        with patch("importlib.util.find_spec", return_value=object()):
            assert ruff_available() is True

    def test_false_when_not_installed(self) -> None:
        """ruff_available() is False when the ruff package cannot be found."""
        from semolina.codegen.python_renderer import ruff_available

        with patch("importlib.util.find_spec", return_value=None):
            assert ruff_available() is False
```

**Analog B — patch the helper, not `find_spec`,** for tests that only need the *failure branch*
without disturbing unrelated `find_spec` calls (`test_python_renderer.py:1064-1076`):

```python
    def test_short_circuits_when_ruff_unavailable(self) -> None:
        """format_with_ruff() returns source and spawns no subprocess when ruff is absent."""
        from semolina.codegen import python_renderer

        source = "x=1\n"
        with (
            patch.object(python_renderer, "ruff_available", return_value=False),
            patch("subprocess.run") as mock_run,
        ):
            result = python_renderer.format_with_ruff(source)
        assert result == source
        mock_run.assert_not_called()
```

Use B for the RESULT-02 message tests on `fetch_df`/`fetch_polars`/`fetch_arrow_table`; use A
for the `_require` helper's own two-branch unit test.

Module conventions from the same tree: `from __future__ import annotations`, `pytestmark =
pytest.mark.unit`, one class per behaviour group with a one-line class docstring, one-line test
docstrings in the indicative mood.

---

### `tests/unit/test_dto_async.py` (new) — CRITICAL: the AST matrix contract

`tests/unit/test_asyncio_trio_matrix.py` walks `tests/**/test_*.py` with `ast.parse`. A module
is **in scope** if `any(isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("test_")
for node in ast.walk(tree))` (`:54-70`) — i.e. any `async def test_*` anywhere, including inside
a class. An in-scope module fails the build unless **both** of the following hold:

**1. A module-level `pytestmark` assignment whose expression contains the attribute `anyio`**
(`_has_anyio_pytestmark`, `:129-154`). The check is `ANYIO_MARKER in _attribute_names(value)`,
where `_attribute_names` walks the value for any `ast.Attribute`. So `pytest.mark.anyio` and
`[pytest.mark.anyio, pytest.mark.unit]` both pass; a bare string `"anyio"` does not. It must be
a top-level `Assign`/`AnnAssign` targeting the name `pytestmark` — inside a class or an `if`
block it is invisible.

**2. A module-level `def anyio_backend` decorated with a *called* decorator whose dotted name
ends in `fixture`, carrying a `params=` keyword whose literal string constants are a superset of
`{"asyncio", "trio"}`** (`_has_both_backends_fixture`, `:157-186`). `@pytest.fixture` without
parentheses fails (`isinstance(decorator, ast.Call)` is False). `params=BACKENDS` where
`BACKENDS` is a module constant fails (the check reads string constants out of the keyword
expression itself). The function must be at `tree.body` level, not nested.

**Exact copyable header — `tests/unit/test_async_cursor.py:27-46`:**

```python
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

import pytest

from semolina.acursor import AsyncSemolinaCursor
from semolina.results import Row

if TYPE_CHECKING:
    from semolina.query import _Query

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio", "trio"])
def anyio_backend(request: pytest.FixtureRequest) -> str:
    """Run every test in this module under both asyncio and Trio."""
    backend: str = request.param
    return backend
```

Note `pytestmark = pytest.mark.anyio` here replaces rather than includes `pytest.mark.unit`.
Also copy the module-scope pragma comment when reaching into cursor privates
(`test_async_cursor.py:21-25`):

```python
# Test-only: the async tests reach the owned async pool's inner sync pool via
# engine._pool._pool to assert checkin, and inspect cursor state such as
# _closed / _reader. Scope-disable the private-access rule (intentionally not a
# `# type: ignore`).
# pyright: reportPrivateUsage=false
```

**Fake async reader analog:** `_CountingAsyncReader` at `test_async_cursor.py:57+` — a duck-typed
stand-in for poolhouse's reader, driven from `FIXTURE_DATA: list[dict[str, Any]]` (`:49-54`).
Reuse its shape for the `iter_into` streaming tests (it also lets the "reader not drained after
N yields" laziness assertion be made by counting).

---

### `tests/unit/test_dto_duckdb.py` (new)

**Analog:** `tests/unit/test_type_fidelity_duckdb.py`.

Header contract to restate in the new module's docstring (`:1-18`): this module runs **live,
in-process**, records and replays nothing, and must never carry `pytest.mark.adbc_cassette` —
`adbc_auto_patch` lists `adbc_driver_manager.dbapi`, which DuckDB routes through, so a marked
DuckDB test is diverted into cassette replay and has its SQL normalised as Databricks.

Import + skip idiom (`:22-51`):

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from type_fidelity_probe import (
    DUCKDB_PROBE_FIELDS,
    PROBE_VIEW_NAME,
    make_probe_engine,
    ...
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from semolina.engines.base import Engine

pytest.importorskip("adbc_driver_duckdb")
```

Fixture pair to copy verbatim (`:115-137`):

```python
@pytest.fixture
def probe_engine() -> Generator[Engine, None, None]:
    """
    Yield the probe's own in-memory DuckDB engine, closing its pool on teardown.

    Mirrors the register/unregister/close symmetry of ``tests/conftest.py``'s
    ``duckdb_pool``, minus the registry step: the probe never resolves an engine by name.
    """
    from adbc_poolhouse import close_pool

    engine = make_probe_engine()
    yield engine
    close_pool(engine._pool)


@pytest.fixture
def probe_cursor(probe_engine: Engine) -> Generator[Any, None, None]:
    """Yield a live ADBC cursor on the probe engine's pool."""
    with probe_engine.connect() as conn:
        cursor = conn.cursor()
        yield cursor
        cursor.close()
```

`make_probe_engine()` (`type_fidelity_probe.py:179-199`) builds an in-memory DuckDB carrying
`type_fidelity_view` with a `DECIMAL(10,2)` column whose `SUM` metric arrives as
`decimal128(38, 2)` — exactly the DTO-03 Decimal→float headline case. It uses `pool_size=1`
and a SQLAlchemy `event.listen(engine._pool, "connect", setup_probe_view)`; the caller owns the
engine and must dispose it (hence the fixture above). Add `pytest.importorskip("arrowmodel")`
alongside the duckdb skip.

Also copy the module's "assert by value, not by 'the two differ'" discipline (`:14-18`) —
`isinstance(rows[0].total_order_value, decimal.Decimal)` against a value from the real driver
path, not a table lookup.

---

### `tests/unit/test_dto_packaging.py` (new)

**Analog:** `tests/unit/test_async_packaging.py` — copy the whole file's structure.

Module scaffolding (`:29-51`):

```python
from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

ASYNC_PIN = "adbc-poolhouse[async]>=1.6.2"


def _pyproject() -> dict[str, Any]:
    """Parse the project's own pyproject.toml."""
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)
```

Declaration-half tests (`:59-74`) — one per extra, plus the `all` reachability test:

```python
def test_packaging_declares_async_extra() -> None:
    """The [async] extra exists and pins adbc-poolhouse[async]>=1.6.2 exactly."""
    extras = _pyproject()["project"]["optional-dependencies"]
    assert "async" in extras, sorted(extras)
    assert extras["async"] == [ASYNC_PIN], extras["async"]


def test_packaging_all_extra_includes_async() -> None:
    """
    The ``all`` extra reaches ``async``.

    CI's four test jobs sync with ``--extra all``; leaving async out would mean
    the async tests never run there while passing locally.
    """
    extras = _pyproject()["project"]["optional-dependencies"]
    assert any("async" in requirement for requirement in extras["all"]), extras["all"]
```

Child-interpreter import check (`:88-106`) — the DTO-05 workhorse:

```python
def test_packaging_importing_semolina_does_not_import_anyio() -> None:
    """
    ``import semolina`` leaves anyio unimported, so a base install stays clean.

    adbc-poolhouse resolves its async entry points lazily (PEP 562) precisely to
    keep the sync path anyio-free ... anyio is installed in this
    venv, so the observation has to happen in a child interpreter.
    """
    result = subprocess.run(
        [sys.executable, "-c", "import semolina, sys; print('anyio' in sys.modules)"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False", (
        f"importing semolina pulled anyio into sys.modules: {result.stdout!r}"
    )
```

Parametrise the module name over `arrowmodel` / `pandas` / `polars` (pyarrow cannot be asserted
absent — `semolina.results`/codegen may pull it; check before asserting). Note this module is
deliberately **out of scope** for the asyncio/trio matrix and is named as such at
`test_asyncio_trio_matrix.py:264` — a new packaging module defines no `async def test_*`, so it
stays out too.

Also copy the file docstring's two-halves framing (`:1-13`): "the declaration half reads
pyproject.toml …; the lazy-import half checks that `import semolina` does not drag X in", and
the convention that every version floor gets a prose justification in the docstring.

---

### `.github/workflows/ci.yml` `packaging-smoke` (modified — extend)

**Analog:** `ci.yml:164-180` (the job's existing steps).

```yaml
      - name: Install [duckdb] extra in clean venv
        run: |
          uv venv /tmp/smoke-venv
          uv pip install --python /tmp/smoke-venv/bin/python ".[duckdb]"

      - name: Import smoke test
        run: |
          /tmp/smoke-venv/bin/python -c "from semolina.engines.duckdb import DuckDBEngine; print('OK')"

      - name: Install base (no extras) in clean venv
        run: |
          uv venv /tmp/base-venv
          uv pip install --python /tmp/base-venv/bin/python "."

      - name: Base install pulls no anyio (ASYNC-04)
        run: |
          /tmp/base-venv/bin/python -c "import semolina, importlib.util; assert importlib.util.find_spec('anyio') is None, 'anyio present in a base install'; print('OK')"
```

Add sibling steps in the same shape: one `- name: Base install pulls no arrowmodel (DTO-05)`
step per package, each a single `python -c` with an inline `assert` carrying its own message and
a trailing `print('OK')`. The job name at `:150` (`Smoke test [duckdb] extras install`) and the
`timeout-minutes: 5` may need updating as steps grow. Do not replace the two existing steps.

---

## Shared Patterns

### Optional-dependency guarding
**Source:** `src/semolina/codegen/python_renderer.py:429-440` (`importlib.util.find_spec`, called
by name inside the function body)
**Apply to:** `exceptions.py::_require`, and every one of the six new/guarded cursor methods on
both cursors.

### Lazy-import discipline
**Source:** `src/semolina/cursor.py:9-17` — `from __future__ import annotations` plus a
`if TYPE_CHECKING:` import block; runtime imports are function-local.
**Apply to:** `cursor.py`, `acursor.py`, `dto.py`. Never module-scope `import pyarrow` outside
`codegen/`. The guard is `tests/unit/test_dto_packaging.py`'s child-interpreter check plus
CI `packaging-smoke`.

### Error class shape
**Source:** `src/semolina/engines/base.py:22-27`
**Apply to:** both new exceptions. Flat `RuntimeError` subclass, one-line "Raised when …"
docstring, no body, exported from the package root and listed in `__all__`.

### Docstring shape
**Source:** `src/semolina/cursor.py:139-162`
**Apply to:** every new public method. Summary on the line after `"""` (D213), blank line,
prose paragraphs, then `Args:` / `Returns:` / `Raises:` / `Example:` with
`.. code-block:: python` — never `>>>` (root pytest runs `--doctest-modules` over `src`).

### Test module conventions
**Source:** `tests/unit/test_async_packaging.py:29-39`, `tests/unit/test_async_cursor.py:1-46`
**Apply to:** all four new test modules. `from __future__ import annotations`; a module docstring
naming the requirement IDs covered and listing the test classes; `pytestmark = pytest.mark.unit`
(or `pytest.mark.anyio` for async modules); one-line docstrings on every test; a
`# pyright: reportPrivateUsage=false` scope pragma instead of `# type: ignore` when touching
privates.

### Never touch the value path
**Source:** `src/semolina/cursor.py:281-283` (`batch.to_pylist()` → `Row(...)`)
**Apply to:** every plan in the phase. 47-DECISIONS.md Decision 1 names a change here as
inverting the decision. The pre-check is schema-only and fetches no rows; error messages carry
no row values (`annotation_check.py:22-25`).

---

## No Analog Found

None. Every file in scope has at least a role-match analog. The weakest is `src/semolina/dto.py`,
whose only analog (`codegen/annotation_check.py`) supplies the *report shape* but none of the
comparison machinery — the planner should treat the comparator itself as new code written against
RESEARCH.md §Q7's measured `issubclass` / annotation-shape tables, not as a port.

---

## Metadata

**Analog search scope:** `src/semolina/`, `src/semolina/codegen/`, `src/semolina/engines/`,
`tests/unit/`, `tests/`, `.github/workflows/`, `pyproject.toml`
**Files scanned:** 15 read, 5 grepped
**Pattern extraction date:** 2026-08-14
