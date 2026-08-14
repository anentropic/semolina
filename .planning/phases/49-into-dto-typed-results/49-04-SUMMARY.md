---
phase: 49-into-dto-typed-results
plan: "04"
subsystem: packaging
tags: [packaging, extras, ci, arrowmodel, polars, pandas, pyarrow, lazy-import, DTO-05]
status: complete

requires:
  - "49-01: the four extras in pyproject.toml, the regenerated uv.lock, and both new errors exported from the package root"
provides:
  - "A clean-venv CI proof that a default install carries none of arrowmodel, polars, pandas or pyarrow (DTO-05)"
  - "A clean-venv CI proof that semolina[arrowmodel] installs arrowmodel"
  - "Unit assertions on the four extras' exact pins, [all] reachability, and the [duckdb] self-reference"
  - "A module-scope import scan over src/semolina that catches a hoisted optional import"
affects:
  - "Any future edit that loosens a pin, drops an extra from [all], or hoists an optional import to module scope"

tech-stack:
  added: []
  patterns:
    - "Declaration half + lazy-import half, copied from tests/unit/test_async_packaging.py"
    - "One CI step per claim, each a single `python -c` with an inline assert and a trailing print('OK')"
    - "AST scan of module-level imports as a substitute for a sys.modules check that a transitive dependency has made vacuous"

key-files:
  created:
    - tests/unit/test_dto_packaging.py
  modified:
    - tests/unit/test_public_surface.py
    - .github/workflows/ci.yml

decisions:
  - "Assert absence for all four optional packages in CI, not just arrowmodel and polars — a real base venv was measured and returned False for every one of them"
  - "Replace the sys.modules coverage lost to adbc-driver-manager's opportunistic imports with a source-level module-scope import scan, rather than dropping it"
  - "Keep timeout-minutes: 5 — the job is observed at 13s, so the third venv is nowhere near the ceiling"

metrics:
  duration: ~25m
  completed: 2026-08-14

actuals:
  tokens: 3950
  tasks: 2
  commits: 2
---

# Phase 49 Plan 04: Packaging Contract for the DTO Surface Summary

DTO-05 is now proven where it can be proven — the extras contract in the unit suite, and what a
default install actually contains in a clean-venv CI job that was measured before it was written.

## What Shipped

**`tests/unit/test_dto_packaging.py` (new, 9 tests).** The declaration half asserts each of the
four extras equals its committed pin exactly (`pyarrow>=17.0.0`, `pandas>=2.0.0`,
`polars>=1.0.0`, `arrowmodel>=1.0.0`), that `[all]` reaches all four, and that `[duckdb]`
carries `semolina[pyarrow]` and no pyarrow pin of its own. Equality rather than containment, so
a silently loosened floor fails here. The lazy-import half runs a child interpreter and asserts
`arrowmodel` stays out of its `sys.modules`.

**`tests/unit/test_public_surface.py` (+4 tests).** `SemolinaMissingDependencyError` and
`SemolinaSchemaMismatchError` each get the import-path and `__all__`-membership pair that
`JsonValue` already had.

**`.github/workflows/ci.yml` `packaging-smoke` (extended).** Four base-install absence steps and
one new clean-venv `.[arrowmodel]` install with a positive assertion. The `[duckdb]` install,
the import smoke test, the base-install step and the ASYNC-04 anyio assertion are byte-identical
to before.

## The Measurements

Two different venvs give two different answers, and the difference is the whole reason this plan
splits its evidence between a test and a CI job.

**Clean base venv (`uv pip install .`, no extras) — `find_spec` presence:**

```python
{'arrowmodel': False, 'polars': False, 'pandas': False, 'pyarrow': False}
```

All four absent. So all four got an absence assertion in `packaging-smoke`, and none was
assumed. `import semolina` was also confirmed to succeed in that venv, which matters: it is what
makes the `_require(...)` guards reachable rather than pre-empted by an ImportError at package
import.

**Dev venv (`--extra all`) — `sys.modules` after `import semolina` in a child interpreter:**

| package | in `sys.modules` | pulled by |
|---------|------------------|-----------|
| arrowmodel | no | — |
| pyarrow | yes | `adbc_driver_manager/dbapi.py:53`, unconditional module-scope import |
| pandas | yes | `pyarrow.dataset` (imported at `dbapi.py:54`) |
| polars | yes | `adbc_driver_manager/_dbapi_backend.py:188`, in a `try`/`except ImportError` |

The full chain is `semolina.config` -> `adbc_poolhouse` ->
`adbc_poolhouse._adapters._databricks_python` -> `adbc_driver_manager.dbapi`. adbc-driver-manager
declares none of the three as a dependency; it imports them opportunistically when present. That
is why the base venv is clean and the dev venv is not, and it is exactly why a `find_spec`
monkeypatch cannot stand in for a real install.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — wrong premise] The lazy-import test covers `arrowmodel` only, not `arrowmodel` and `polars`**

- **Found during:** Task 1, before writing a line.
- **Issue:** The plan parametrised the child-interpreter check over `arrowmodel` and `polars`,
  excluding `pandas` and `pyarrow` as already-present. The executor prompt gave a third list
  (`arrowmodel`, `pandas`, `polars`). Measurement agrees with neither: `polars` and `pandas` are
  both in `sys.modules` after `import semolina`, alongside `pyarrow`. Wave 1 had found the
  pyarrow case and inferred the others were safe; they are not.
- **Fix:** Parametrised over `arrowmodel` alone, with the parametrisation kept (adding a module
  later is one line) and its docstring naming the measured chain for each exclusion.
- **Files modified:** `tests/unit/test_dto_packaging.py`
- **Commit:** 8cd1064

**2. [Rule 2 — missing critical coverage] Added a module-scope import scan to replace what the exclusion cost**

- **Found during:** Task 1, as a consequence of deviation 1.
- **Issue:** Dropping three packages from the `sys.modules` check leaves a real hole. A
  hoisted `import polars` at the top of `cursor.py` would be completely invisible to a
  `sys.modules` assertion, because adbc-driver-manager has already put polars there. The
  lazy-import discipline would then be unguarded for three of the four packages it governs.
- **Fix:** `test_packaging_no_module_scope_optional_imports` parses every module under
  `src/semolina` and collects imports that execute at module scope, following module-level
  `try`/`except` blocks and skipping `if TYPE_CHECKING:` blocks (which is the escape hatch
  `cursor.py` uses to annotate a `pyarrow.Table` return type without importing pyarrow).
  `codegen/arrow_map.py` is allowlisted — pyarrow is not optional to a module that maps Arrow
  types to annotations — and the allowlist entry is paired with
  `test_packaging_importing_semolina_leaves_codegen_unimported`, so the exemption stays safe only
  while the package root does not reach it. The scanner was checked against a synthetic module to
  confirm it is not vacuous: it caught the `try`-block and plain module-scope imports and
  correctly ignored the `TYPE_CHECKING` and function-local ones.
- **Files modified:** `tests/unit/test_dto_packaging.py`
- **Commit:** 8cd1064

**3. [Rule 2 — measurement supersedes plan text] Four absence steps in CI, not two**

- **Found during:** Task 2.
- **Issue:** The plan's `<behavior>` named arrowmodel and polars; its `<action>` said to write
  assertions only for packages measured `False`, and predicted pandas and pyarrow "may or may
  not" be present depending on what `adbc-poolhouse`, `typer`, `rich` and `jinja2` drag in.
- **Fix:** All four measured `False`, so all four got a step. Each was reproduced locally against
  the venv it targets and printed `OK` before being written into the workflow. The pyarrow step
  carries a comment explaining why it is a CI claim and not a test claim, since the two venvs
  disagree about pyarrow and a future reader will otherwise assume one of them is wrong.
- **Files modified:** `.github/workflows/ci.yml`
- **Commit:** c3645f1

## Verification

- `uv run pytest tests/unit/test_dto_packaging.py tests/unit/test_public_surface.py tests/unit/test_asyncio_trio_matrix.py -x -q` — 20 passed. The new module does not fall into the asyncio/trio matrix's scope; it defines no `async def test_*`, and selection there is by content rather than by glob.
- `just test` — 1415 passed, 16 skipped, 2 xfailed (root), 16 passed, 15 skipped (jaffle-shop). Baseline was 1402; the 13 added are 9 in `test_dto_packaging.py` and 4 in `test_public_surface.py`.
- `prek run --all-files` — all hooks pass, including the YAML checks over the workflow.
- Both plan `<verify>` commands pass. PyYAML was available in the dev venv, so the step-name check ran as written rather than falling back to `grep -F`; the three pre-existing step names are present.
- Every new CI step was executed locally against its target venv and printed `OK`. The `.[arrowmodel]` venv build is a separate step from its assertion, matching the existing `[duckdb]` shape.

The `packaging-smoke` job is observed at 13 seconds with two venvs (run 31231284657, 2026-08-08).
The third venv installs one small wheel set, so `timeout-minutes: 5` was left alone — a
measurement, not a guess. Confirming the job green on the pushed branch remains a phase-level
verification item; nothing here has been through GitHub Actions yet.

## Open Gap, Surfaced Not Closed

`pip install semolina[arrowmodel]` is proven to install arrowmodel. It is **not** proven
sufficient to run `.into()`, because `.into()` also needs pyarrow and no single extra composes
the two. This plan asserts nothing about that, deliberately: the plan flagged it, and the fix if
a reviewer decides it matters is a `pyproject.toml` change — making `[arrowmodel]` reference
`semolina[pyarrow]`, exactly as `[duckdb]` now does — not another test.

## Notes for Later Plans

- The new absence steps make the base install's contents a hard contract. Any future dependency
  that pulls pandas, polars or pyarrow into the base tree turns `packaging-smoke` red. That is
  the intended alarm, not a flake: it means a `_require` guard has gone unreachable and a docs
  claim about extras has quietly become false.
- `test_packaging_no_module_scope_optional_imports` is where a lazy-import regression will
  surface first, ahead of any runtime symptom. If Plan 05 or 06 needs a new module-scope import
  of an optional package, the allowlist is one line — but it needs the companion "not reached by
  the package root" assertion beside it, or the exemption is unguarded.

## Self-Check: PASSED

- `tests/unit/test_dto_packaging.py` — FOUND
- `tests/unit/test_public_surface.py` — FOUND
- `.github/workflows/ci.yml` — FOUND
- commit `8cd1064` — FOUND
- commit `c3645f1` — FOUND
