---
phase: 09-codegen-cli
plan: "01"
subsystem: cli
tags: [typer, rich, jinja2, cli, codegen, strum]

# Dependency graph
requires:
  - phase: 07-packaging
    provides: pyproject.toml structure and project metadata (__version__)
provides:
  - cubano CLI entrypoint (cubano command)
  - codegen subcommand shell (cubano codegen <input> --backend <backend>)
  - Backend enum (snowflake/databricks)
  - resolve_input_paths() path resolution utility
  - generate_sql_for_files() stub for wave 2 implementation
affects:
  - 09-02-PLAN (model discovery uses codegen package structure)
  - 09-03-PLAN (SQL generation fills generate_sql_for_files stub)
  - 09-04-PLAN (CLI tests exercise all options from this plan)

# Tech tracking
tech-stack:
  added: [typer>=0.12.0, rich>=13.0.0, jinja2>=3.1.0]
  patterns:
    - Typer app.command() registration pattern for subcommands (avoids nested Typer nesting issue)
    - StrEnum for CLI enum values (Python 3.11+, UP042 compliant)
    - Separate Rich Console instances for stdout (SQL) and stderr (diagnostics)
    - TYPE_CHECKING guards for type-only imports (TC003/TC002 compliance)
    - Lazy local imports inside command functions for fast CLI startup

key-files:
  created:
    - src/cubano/cli/__init__.py
    - src/cubano/cli/codegen.py
    - src/cubano/cli/utils.py
    - src/cubano/__main__.py
    - src/cubano/codegen/__init__.py
    - src/cubano/codegen/generator.py
  modified:
    - pyproject.toml
    - src/cubano/__init__.py
    - uv.lock

key-decisions:
  - "Register codegen as app.command('codegen') directly rather than add_typer() to avoid double-nesting (cubano codegen <input> not cubano codegen codegen <input>)"
  - "Use StrEnum instead of str+Enum for Backend — Python 3.11+ native, satisfies UP042"
  - "Place Path import in TYPE_CHECKING guard for codegen/generator.py stubs; use noqa: TC003 in codegen.py where Typer needs runtime Path for option type"

patterns-established:
  - "CLI option: use Annotated[Type, typer.Option(...)] pattern for all CLI params"
  - "Separate stdout/stderr consoles: _stdout for SQL output, _stderr for diagnostics"
  - "Lazy imports inside command body for fast CLI startup time"

requirements-completed: [CODEGEN-01]

# Metrics
duration: 10min
completed: 2026-02-17
---

# Phase 9 Plan 01: Codegen CLI Foundation Summary

**Typer CLI shell for `cubano codegen` with Backend enum, path resolution, Rich console routing, and generate_sql_for_files() stub — full argument validation and help text working**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-17T10:12:47Z
- **Completed:** 2026-02-17T10:22:47Z
- **Tasks:** 8
- **Files modified:** 9 (6 created, 3 modified)

## Accomplishments

- `cubano codegen <input> --backend snowflake` parses and validates all arguments correctly
- Backend enum (snowflake/databricks) enforced at CLI boundary with clear error messages
- Path resolution handles files, directories, and glob patterns with proper error reporting
- `cubano --help`, `cubano codegen --help`, and `cubano --version` all work correctly
- `generate_sql_for_files()` stub in place with correct type signatures for wave 2 implementation
- All quality gates pass: basedpyright, ruff check, ruff format, pytest (254 tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Typer, Rich, and Jinja2 as runtime dependencies** - `289ab33` (chore)
2. **Tasks 2-7: CLI package, codegen command, utils, __main__, codegen stubs, __version__** - `fdbd510` (feat)

## Files Created/Modified

- `pyproject.toml` - Added typer/rich/jinja2 deps, [project.scripts] cubano entry point
- `uv.lock` - Updated lockfile with new deps
- `src/cubano/__init__.py` - Added `__version__ = "0.1.0"` and added to `__all__`
- `src/cubano/__main__.py` - Entry point for `python -m cubano`
- `src/cubano/cli/__init__.py` - Typer app with version callback, codegen command registered
- `src/cubano/cli/codegen.py` - Backend StrEnum, all five CLI options, file routing logic
- `src/cubano/cli/utils.py` - resolve_input_paths() and make_stderr_console() helpers
- `src/cubano/codegen/__init__.py` - Codegen package stub
- `src/cubano/codegen/generator.py` - generate_sql_for_files() stub with correct type signatures

## Decisions Made

- **Direct command registration vs add_typer():** Used `app.command("codegen")(codegen)` instead of `app.add_typer(codegen_app, name="codegen")` to avoid nested command path `cubano codegen codegen <input>`. Direct registration gives the desired `cubano codegen <input>` UX.
- **StrEnum for Backend:** Python 3.11+ native `StrEnum` satisfies ruff UP042 lint rule and avoids the `(str, Enum)` multi-inheritance pattern.
- **noqa: TC003 on Path import in codegen.py:** Typer needs `Path` at runtime for option type introspection, so moving it to TYPE_CHECKING would break the CLI. Used inline suppression to satisfy the requirement.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Typer nested command nesting (cubano codegen codegen)**
- **Found during:** Task 8 (quality gates / verification)
- **Issue:** Plan used `add_typer(codegen_app, name="codegen")` + `@codegen_app.command()` with function named `codegen`, creating double-nested path `cubano codegen codegen <input>` instead of `cubano codegen <input>`
- **Fix:** Switched from sub-Typer approach to `app.command("codegen")(codegen)` direct registration. Removed `codegen_app = typer.Typer(...)` sub-app wrapper.
- **Files modified:** `src/cubano/cli/__init__.py`, `src/cubano/cli/codegen.py`
- **Verification:** All 6 verification criteria pass (`cubano codegen --help` shows correct options, error cases return expected exit codes)
- **Committed in:** `fdbd510` (feat commit)

**2. [Rule 1 - Bug] Fixed ruff lint errors in generated code**
- **Found during:** Task 8 (quality gates — pre-commit hook)
- **Issue:** D200 (multi-line docstring fits on one line), UP042 (use StrEnum), B904 (raise from err)
- **Fix:** Converted module docstring to one-liner, changed `class Backend(str, Enum)` to `class Backend(StrEnum)`, added `from e` to exception re-raise
- **Files modified:** `src/cubano/cli/codegen.py`
- **Verification:** `ruff check` passes
- **Committed in:** `fdbd510` (feat commit)

---

**Total deviations:** 2 auto-fixed (2x Rule 1 bugs)
**Impact on plan:** Both fixes required for correct CLI UX and lint compliance. No scope creep.

## Issues Encountered

- Pre-commit hook `uv-lock` updated lockfile on first commit attempt — resolved by staging `uv.lock` alongside `pyproject.toml`
- Pre-existing `test_databricks_engine.py` and `test_snowflake_engine.py` failures (optional deps not installed) are unrelated to this plan's changes; 254 other tests pass cleanly

## User Setup Required

None - no external service configuration required. CLI is available immediately after `uv sync`.

## Next Phase Readiness

- CLI shell complete and working; `generate_sql_for_files()` stub ready for 09-03 to implement
- `cubano codegen` command correctly routes files, directories, and glob patterns to the generator
- All five CLI options (`--backend`, `--output`, `--verbose`, `--no-comments`, INPUT) validated and working
- 09-02 can proceed independently (model discovery introspection)

## Self-Check: PASSED

All created files exist and all commits verified:
- FOUND: src/cubano/cli/__init__.py
- FOUND: src/cubano/cli/codegen.py
- FOUND: src/cubano/cli/utils.py
- FOUND: src/cubano/__main__.py
- FOUND: src/cubano/codegen/__init__.py
- FOUND: src/cubano/codegen/generator.py
- FOUND: commit 289ab33 (chore: deps)
- FOUND: commit fdbd510 (feat: CLI files)

---
*Phase: 09-codegen-cli*
*Completed: 2026-02-17*
