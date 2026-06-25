# Phase 38: Packaging Fix + Test Cleanup - Research

**Researched:** 2026-05-01
**Domain:** Python packaging (pyproject.toml), pytest xfail markers, dependency management
**Confidence:** HIGH

## Summary

Phase 38 is a gap-closure phase that restores packaging changes lost during Phase 36's worktree merge, fixes a misplaced development dependency, and removes pytest `xfail` markers that are no longer needed because the upstream `duckdb-semantic-views` extension v0.7.1 fixes the catalog resolution bug.

The work is straightforward: (1) re-add the `duckdb` extra to `[project.optional-dependencies]`, (2) update `[all]` to include it, (3) move `sphinx-autobuild` from `[project.dependencies]` to `[dependency-groups] docs`, and (4) remove all `@pytest.mark.xfail` and `@_xfail_adbc` markers from test files, then verify tests pass.

**Primary recommendation:** This is a single-plan phase with three independent mechanical edits (pyproject.toml packaging, pyproject.toml deps, test file xfail removal) that should be done atomically and verified with `uv lock --check`, `just test`, and `just docs-build`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DUCK-01 | User can install DuckDB support via `semolina[duckdb]` extra (`duckdb>=1.5.0`, `pyarrow>=17.0.0` explicit) | Packaging fix restores the extra that was lost during Phase 36 worktree merge. Verified: duckdb 1.5.2 and pyarrow 24.0.0 are current on PyPI. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Quality gates:** `prek run --all-files`, `just test`, `just docs-build` must pass before commit
- **Bug fix rule:** Reproduce with failing test first (not applicable here -- these are packaging/config fixes)
- **Code style:** 100 char lines, ruff formatting
- **Build system:** uv + pyproject.toml, uv-build backend

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| duckdb | >=1.5.0 (latest: 1.5.2) | DuckDB Python package (includes ADBC driver) | Required for semantic_views extension v0.7.x compatibility [VERIFIED: PyPI registry] |
| pyarrow | >=17.0.0 (latest: 24.0.0) | Arrow columnar data format | Required for fetch_arrow_table() ADBC passthrough [VERIFIED: PyPI registry] |
| sphinx-autobuild | 2025.8.25 (latest) | Live-reload docs server | Dev tool, belongs in docs dependency group [VERIFIED: PyPI registry] |
| uv | build system | Package manager and lockfile | Project standard [VERIFIED: pyproject.toml] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| adbc-poolhouse | >=1.2.0 | Connection pooling with DuckDBConfig | Already a core dependency; has its own `[duckdb]` extra (installs duckdb>=0.9.1) but semolina pins >=1.5.0 [VERIFIED: PyPI registry] |

## Architecture Patterns

### Pattern 1: pyproject.toml Optional Dependencies

**What:** Pip extras declared in `[project.optional-dependencies]` allow users to install backend-specific packages.
**When to use:** When the package supports multiple backends with different driver requirements.
**Current state (broken):**
```toml
# MISSING: duckdb extra was removed by Phase 36 worktree merge
[project.optional-dependencies]
databricks = ["databricks-sql-connector[pyarrow]>=4.2.5"]
snowflake = ["adbc-poolhouse[snowflake]", "snowflake-connector-python>=4.3.0"]
all = ["semolina[snowflake,databricks]"]  # missing duckdb
```

**Target state (restored from commit a96e156):**
```toml
[project.optional-dependencies]
databricks = ["databricks-sql-connector[pyarrow]>=4.2.5"]
snowflake = ["adbc-poolhouse[snowflake]", "snowflake-connector-python>=4.3.0"]
duckdb = [
    "duckdb>=1.5.0",
    "pyarrow>=17.0.0",
]
all = ["semolina[snowflake,databricks,duckdb]"]
```
[VERIFIED: git show a96e156 -- pyproject.toml]

### Pattern 2: Dependency Group vs Project Dependencies

**What:** Development-only tools (docs builders, linters, test runners) belong in `[dependency-groups]`, not `[project.dependencies]`.
**Why it matters:** `sphinx-autobuild[dev]>=2025.8.25` in `[project.dependencies]` means it gets installed for ALL users of semolina, even in production. This is a dev-only live-reload server.
**Current state (broken):**
```toml
[project]
dependencies = [
    "adbc-poolhouse>=1.2.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
    "jinja2>=3.1.0",
    "sphinx-autobuild[dev]>=2025.8.25",  # WRONG: dev tool in runtime deps
]
```

**Target state:**
```toml
[project]
dependencies = [
    "adbc-poolhouse>=1.2.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
    "jinja2>=3.1.0",
]

[dependency-groups]
docs = [
    "sphinx>=8.0",
    "shibuya>=2025.1.1",
    "sphinx-autoapi>=3.6.0",
    "sphinx-design>=0.6.0",
    "sphinx-copybutton>=0.5.2",
    "sphinx-autobuild>=2025.8.25",  # MOVED here
]
```
[VERIFIED: current pyproject.toml has sphinx-autobuild in project.dependencies]

### Pattern 3: Removing xfail Markers

**What:** `pytest.mark.xfail` marks tests as expected failures. Once the underlying bug is fixed, markers should be removed so tests actually assert correctness.
**Scope:** 20 total xfail markers across 2 files:
- `tests/unit/test_query.py`: 16 markers (via shared `_xfail_adbc` variable + direct usage)
- `tests/unit/test_pool.py`: 4 markers (direct `@pytest.mark.xfail(...)`)

**Cleanup steps:**
1. Remove the `_xfail_adbc` variable definition from `test_query.py` (lines 115-118)
2. Remove all `@_xfail_adbc` decorator usages (16 occurrences)
3. Remove all `@pytest.mark.xfail(reason="DuckDB semantic_view()...", strict=False)` decorators from `test_pool.py` (4 occurrences)
4. Update module docstrings that reference the xfail/catalog bug
5. Run tests to verify they now pass

[VERIFIED: grep of tests/ directory]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Lockfile regeneration | Manual edits to uv.lock | `uv lock` | Lockfile is auto-generated from pyproject.toml |
| Extra validation | pip install --dry-run | `uv pip install -e ".[duckdb]" --dry-run` | uv resolves from local pyproject.toml |

## Common Pitfalls

### Pitfall 1: Forgetting to update `[all]` extra

**What goes wrong:** Adding the `duckdb` extra but forgetting to include it in `all = ["semolina[snowflake,databricks,duckdb]"]`.
**Why it happens:** The `all` meta-extra must explicitly list every backend extra.
**How to avoid:** Update both in the same edit.
**Warning signs:** `pip install semolina[all]` doesn't install duckdb.

### Pitfall 2: Lockfile drift after pyproject.toml edit

**What goes wrong:** Editing pyproject.toml without running `uv lock` leaves the lockfile inconsistent.
**Why it happens:** uv requires explicit lock regeneration.
**How to avoid:** Run `uv lock` immediately after editing pyproject.toml. Verify with `uv lock --check`.
**Warning signs:** `uv sync` fails or installs wrong versions.

### Pitfall 3: xfail(strict=False) tests silently passing

**What goes wrong:** With `strict=False`, if a test starts passing, pytest reports it as XPASS but does NOT fail the suite. This means the fix may have landed weeks ago without notice.
**Why it happens:** `strict=False` was used because the bug fix was anticipated but not yet confirmed.
**How to avoid:** Remove xfail markers and run the full suite. If any test still fails, the bug isn't fully fixed and the test needs investigation (not re-marking).
**Warning signs:** XPASS in test output.

### Pitfall 4: sphinx-autobuild removal breaking docs-serve

**What goes wrong:** Moving sphinx-autobuild to `[dependency-groups] docs` means it's only available when the docs group is installed.
**Why it happens:** `just docs-serve` uses sphinx-autobuild.
**How to avoid:** The justfile already uses `uv run` which should resolve from dependency groups. Verify `just docs-serve` still works after the move.
**Warning signs:** `sphinx-autobuild: command not found` when running docs server.

### Pitfall 5: Description string regression

**What goes wrong:** Phase 33 also updated the project description to include "DuckDB" but that change was also lost.
**Why it happens:** Same pyproject.toml revert from Phase 36 worktree.
**How to avoid:** Restore the description: `"A Pythonic ORM for querying data warehouse semantic views (Snowflake, Databricks, DuckDB)"`
**Warning signs:** grep for "DuckDB" in project description.

## Code Examples

### pyproject.toml final state (relevant sections)

```toml
# Source: git show a96e156 (Phase 33 original) + current state
[project]
name = "semolina"
version = "0.3.0"
description = "A Pythonic ORM for querying data warehouse semantic views (Snowflake, Databricks, DuckDB)"
dependencies = [
    "adbc-poolhouse>=1.2.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
    "jinja2>=3.1.0",
    # NOTE: sphinx-autobuild REMOVED from here
]

[project.optional-dependencies]
databricks = [
    "databricks-sql-connector[pyarrow]>=4.2.5",
]
snowflake = [
    "adbc-poolhouse[snowflake]",
    "snowflake-connector-python>=4.3.0",
]
duckdb = [
    "duckdb>=1.5.0",
    "pyarrow>=17.0.0",
]
all = [
    "semolina[snowflake,databricks,duckdb]",
]

[dependency-groups]
docs = [
    "sphinx>=8.0",
    "shibuya>=2025.1.1",
    "sphinx-autoapi>=3.6.0",
    "sphinx-design>=0.6.0",
    "sphinx-copybutton>=0.5.2",
    "sphinx-autobuild>=2025.8.25",
]
```

### test_query.py xfail removal (before/after)

```python
# BEFORE (lines 115-118):
_xfail_adbc = pytest.mark.xfail(
    reason="DuckDB semantic_view() has catalog resolution issue through ADBC driver",
    strict=False,
)

# AFTER: Delete these lines entirely, plus all @_xfail_adbc usages
```

### test_pool.py xfail removal (before/after)

```python
# BEFORE:
@pytest.mark.xfail(
    reason="DuckDB semantic_view() has catalog resolution issue through ADBC driver",
    strict=False,
)
def test_execute_with_duckdb_pool_returns_cursor(self, duckdb_pool: Any):

# AFTER:
def test_execute_with_duckdb_pool_returns_cursor(self, duckdb_pool: Any):
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| xfail markers for catalog bug | Tests pass directly (duckdb-semantic-views 0.7.1) | 2026-04-26 | Remove 20 xfail markers |
| sphinx-autobuild in runtime deps | sphinx-autobuild in docs group | This phase | Slimmer install for end users |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | duckdb-semantic-views 0.7.1 fixes the ADBC catalog resolution bug | Pattern 3, Success Criterion 4 | Tests will still fail; xfail markers would need to stay. Mitigation: run tests before committing |
| A2 | `sphinx-autobuild[dev]` extra tag not needed (plain `sphinx-autobuild>=2025.8.25` is sufficient) | Pattern 2 | The `[dev]` extra may provide something needed. Mitigation: check sphinx-autobuild docs |

**Note on A1:** The ROADMAP (authored by the project owner) explicitly states "remove xfail markers now that duckdb-semantic-views 0.7.1 fixes the catalog resolution bug". The extension is the project owner's own project (github.com/anentropic/duckdb-semantic-views). The extension v0.7.1 was released 2026-04-26 and is cached locally at `~/.duckdb/extensions/v1.5.2/osx_arm64/semantic_views.duckdb_extension`. However, the changelog for v0.7.1 mentions "DDL-time type inference" not "catalog resolution fix" explicitly. The fix may have been a side-effect of v0.7.0 or v0.7.1 changes. Risk is LOW since the project owner asserts this in the ROADMAP.

**Note on A2:** The `[dev]` extra for sphinx-autobuild installs optional dependencies for development. Looking at the current pyproject.toml it uses `sphinx-autobuild[dev]>=2025.8.25`. Since it's moving to a `docs` dependency group (already a dev context), the `[dev]` extra should be preserved: `sphinx-autobuild[dev]>=2025.8.25`.

## Open Questions (RESOLVED)

1. **Should `sphinx-autobuild[dev]` keep its `[dev]` extra in the docs group?**
   - What we know: Currently specified as `sphinx-autobuild[dev]>=2025.8.25` in project.dependencies
   - What's unclear: Whether the `[dev]` extra provides meaningful functionality for the docs-serve workflow
   - Recommendation: Keep `[dev]` extra to preserve current behavior: `"sphinx-autobuild[dev]>=2025.8.25"` in docs group

2. **Should the project description be updated to include DuckDB?**
   - What we know: Phase 33 changed it to include "DuckDB" but Phase 36 reverted it
   - What's unclear: Nothing -- it should be restored
   - Recommendation: Restore `"A Pythonic ORM for querying data warehouse semantic views (Snowflake, Databricks, DuckDB)"`

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| DuckDB extension (semantic_views) | xfail removal tests | Yes | v0.7.2 (cached at v1.5.2) | None -- tests require it |
| uv | Lock regeneration | Yes | (project build tool) | None |
| pytest | Test verification | Yes | via dev deps | None |

**Missing dependencies with no fallback:** None -- all required tools are available locally.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0.0 |
| Config file | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/unit/test_pool.py tests/unit/test_query.py -x` |
| Full suite command | `just test` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DUCK-01 | `pip install semolina[duckdb]` resolves duckdb>=1.5.0 + pyarrow>=17.0.0 | smoke | `uv pip install -e ".[duckdb]" --dry-run` | N/A (CLI validation) |
| SC-1 | `pip install semolina[duckdb]` installs correct packages | smoke | `uv pip install -e ".[duckdb]" --dry-run` | N/A |
| SC-2 | `pip install semolina[all]` includes duckdb | smoke | `uv pip install -e ".[all]" --dry-run` | N/A |
| SC-3 | sphinx-autobuild not in project.dependencies | lint | `grep -v sphinx-autobuild pyproject.toml (in deps section)` | N/A |
| SC-4 | All xfail tests pass without markers | unit | `uv run pytest tests/unit/test_pool.py tests/unit/test_query.py -x` | Yes |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_pool.py tests/unit/test_query.py -x`
- **Per wave merge:** `just test`
- **Phase gate:** Full suite green (`just test` + `prek run --all-files`)

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. The xfail-marked tests already exist and just need their markers removed.

## Sources

### Primary (HIGH confidence)
- [PyPI: duckdb 1.5.2] - `curl https://pypi.org/pypi/duckdb/json` verified latest version
- [PyPI: pyarrow 24.0.0] - `curl https://pypi.org/pypi/pyarrow/json` verified latest version
- [PyPI: sphinx-autobuild 2025.8.25] - `curl https://pypi.org/pypi/sphinx-autobuild/json` verified latest version
- [PyPI: adbc-poolhouse 1.2.0] - `curl https://pypi.org/pypi/adbc-poolhouse/json` verified extras include `duckdb`
- [git show a96e156] - Phase 33 commit showing original duckdb extra addition
- [git show 2933df2] - Phase 36 commit that reverted pyproject.toml changes
- [Current pyproject.toml] - Verified sphinx-autobuild in project.dependencies and missing duckdb extra
- [tests/unit/test_query.py, test_pool.py] - Verified 20 total xfail markers

### Secondary (MEDIUM confidence)
- [github.com/anentropic/duckdb-semantic-views/tags] - v0.7.1 released 2026-04-26, v0.7.2 released 2026-05-01
- [~/.duckdb/extensions/v1.5.2/] - semantic_views extension cached locally

### Tertiary (LOW confidence)
- [ROADMAP.md claim] - "duckdb-semantic-views 0.7.1 fixes the catalog resolution bug" -- project owner assertion, changelog does not explicitly mention this fix

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - versions verified on PyPI, changes are mechanical restoration
- Architecture: HIGH - exact target state known from git history (commit a96e156)
- Pitfalls: HIGH - well-understood packaging mechanics

**Research date:** 2026-05-01
**Valid until:** 2026-06-01 (stable -- packaging changes are mechanical)
