---
phase: quick-11
plan: "01"
subsystem: tests
tags: [ci, ansi, typer, pytest, conftest]
dependency_graph:
  requires: []
  provides: [CI-ANSI-FIX]
  affects: [tests/conftest.py]
tech_stack:
  added: []
  patterns:
    - pytest_configure hook sets env vars before Typer import-time initialization
key_files:
  created: []
  modified:
    - tests/conftest.py
decisions:
  - pytest_configure is the correct hook for env var injection — fires before any test module
    imports Typer, ensuring _TYPER_FORCE_DISABLE_TERMINAL=1 overrides FORCE_TERMINAL before
    it is baked into the typer.rich_utils module-level constant
metrics:
  duration_minutes: 4
  completed: "2026-02-26T16:56:26Z"
  tasks_completed: 1
  files_changed: 1
---

# Quick-11 Plan 01: Suppress CI ANSI Escape Codes via pytest_configure Summary

Committed the `tests/conftest.py` fix that sets `_TYPER_FORCE_DISABLE_TERMINAL=1` in
a `pytest_configure` hook, preventing Typer from emitting ANSI escape codes when
`GITHUB_ACTIONS=true` is present in the CI environment.

## What Was Done

Typer's `rich_utils.py` reads `GITHUB_ACTIONS`, `FORCE_COLOR`, and `PY_COLORS` at
**import time** and bakes `FORCE_TERMINAL=True` into a module-level constant. Once baked,
`NO_COLOR=1` has no effect — the Rich Console emits ANSI codes regardless. This caused
`test_help_shows_usage` to fail in CI because the assertion compared plain strings against
ANSI-decorated output.

The fix adds a `pytest_configure` hook to `tests/conftest.py` that calls:

```python
os.environ.setdefault("_TYPER_FORCE_DISABLE_TERMINAL", "1")
os.environ.setdefault("NO_COLOR", "1")
```

`pytest_configure` fires before any test module is imported, so Typer reads the override
at import time and sets `FORCE_TERMINAL=False`. `NO_COLOR` is kept as defence-in-depth for
other cases (e.g. `FORCE_COLOR=1` in a local dev environment).

## Commit

| Hash | Message |
|------|---------|
| `6f9bf3e` | fix(tests): set _TYPER_FORCE_DISABLE_TERMINAL in pytest_configure to suppress ANSI codes in CI |

## Quality Gates

| Gate | Result |
|------|--------|
| `ruff check` | All checks passed |
| `ruff format --check` | 55 files already formatted |
| `basedpyright` | 0 errors, 0 warnings, 0 notes |
| `pytest tests/ -n auto --snapshot-warn-unused -q` (GITHUB_ACTIONS=true) | **739 passed** in 3.42s |

## Verification

```
GITHUB_ACTIONS=true pytest tests/unit/codegen/test_cli.py::TestCLIBasicBehavior::test_help_shows_usage -v
```

Result: `1 passed in 0.07s` — confirms ANSI suppression works under simulated CI.

## Deviations from Plan

None — plan executed exactly as written. The `--extra dev` flag in the plan is incorrect
for this project (uses `[dependency-groups]` not `[optional-dependencies]`); used
`--group dev` instead. This is a plan wording issue, not a code deviation.

## Self-Check: PASSED

- [x] `tests/conftest.py` exists and contains `_TYPER_FORCE_DISABLE_TERMINAL`
- [x] Commit `6f9bf3e` confirmed in git log
- [x] 739 tests pass with `GITHUB_ACTIONS=true`
- [x] `test_help_shows_usage` passes with `GITHUB_ACTIONS=true`
