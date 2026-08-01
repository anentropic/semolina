# Phase 41: DuckDB File-Backed Codegen — Research

**Researched:** 2026-05-15
**Domain:** Python CLI path handling, DuckDB extension lifecycle, pytest fixtures, packaging smoke tests
**Confidence:** HIGH

## Summary

Phase 41 is a small, gap-filling phase. The DuckDB engine already accepts a `database=` path
(`DuckDBEngine.__init__`, `engines/duckdb.py:96`) and the CLI already exposes `--database`
with a `DUCKDB_DATABASE` env-var fallback (`cli/codegen.py:104-112`). What's missing:

1. **Path normalization at the CLI boundary** — `~` expansion + `resolve(strict=False)`, with
   a non-negotiable `:memory:`-sentinel skip guard (CONTEXT.md decision).
2. **`INSTALL semantic_views FROM community`** added at `engines/duckdb.py:199`, immediately
   before the existing `LOAD semantic_views`, on the same native (non-ADBC) connection.
   `LOAD` is already there and demonstrably works against `read_only=True`; INSTALL is
   idempotent and writes to the user-level cache (`~/.duckdb/extensions/`), not the DB file.
3. **An end-to-end CLI test** driven by `typer.testing.CliRunner`, asserting against a
   `.db` file generated at fixture-collection time. **Use `syrupy`** — already a dev
   dependency (`pyproject.toml:60`) and the codebase's only existing snapshot mechanism
   (`tests/integration/test_queries.py`). Regenerate via `pytest --snapshot-update`.
4. **A packaging smoke-test CI job** that runs `uv pip install '.[duckdb]'` in a clean venv
   and imports `semolina.engines.duckdb` — narrow scope, carries forward the Phase 38 lesson.
5. **Amendment** (not new page) of `docs/src/how-to/codegen.rst` to cover `--database <path>`
   with `~`/relative path behavior, plus a brief note that the `semantic_views` extension is
   auto-installed on first run (needs network).

**Primary recommendation:** Single plan, three implementation tasks (path helper + INSTALL
hook + test fixture/CI), one docs task, one traceability task. The whole phase is
~50 LOC of production code plus the fixture/test wiring. No architectural risk.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Path Handling:**
- Apply `expanduser()` + `resolve(strict=False)` to the `--database` value AND to the value
  of the `DUCKDB_DATABASE` env-var fallback. Same treatment for both sources.
- **Skip expansion for the `:memory:` sentinel.** Guard pattern:
  ```python
  if database and database != ":memory:":
      database = str(Path(database).expanduser().resolve(strict=False))
  ```
- Use `resolve(strict=False)` (not strict). Let DuckDB raise the file-not-found error so the
  error path is consistent with other database-open failures.

**Extension Install at Codegen Time:**
- `INSTALL semantic_views FROM community; LOAD semantic_views` must run on the **native**
  DuckDB connection used by introspection (`src/semolina/engines/duckdb.py:198`). Currently
  only `LOAD` is called there.
- INSTALL is idempotent. Mirrors the existing ADBC-side hook in `src/semolina/config.py:40`.

**Fixture Strategy:**
- pytest fixture generates the `.db` at test-collection time. **Do NOT commit a binary `.db`
  blob.**
- Pin DuckDB version via the existing `[duckdb]` extra to keep fixture-generation
  deterministic across machines.

**End-to-End Codegen Test:**
- Drive the CLI surface (`semolina codegen --backend duckdb --database <fixture>`), not just
  internal APIs.
- Assert against generated module output. Prefer regenerate-on-flag pattern over brittle
  string-for-string compares.

**Packaging Smoke Test:**
- CI verifies `uv pip install '.[duckdb]'` in a clean environment + an import smoke test for
  `semolina.engines.duckdb`. Narrow scope — no functional assertions.

**Documentation:**
- **Amend** the existing DuckDB codegen how-to (`docs/src/how-to/codegen.rst`), not a new
  page.
- Update REQUIREMENTS.md DKGEN-04 traceability on close.

### Claude's Discretion

- File layout for the pytest fixture (`tests/fixtures/` and/or `conftest.py` — planner
  decides).
- Snapshot mechanism flavor (raw file comparison vs syrupy vs manual fixture golden module).
- Exact CI workflow file/job placement for the `[duckdb]` extras smoke test.
- Whether path-normalization helper lives in `cli/codegen.py` or `cli/utils.py`.

### Deferred Ideas (OUT OF SCOPE)

- Field-type inference across backends — explicitly Phase 42.
- Query execution against file-backed DuckDB — DuckDBEngine is introspection-only.
- ADBC connection support for file-backed DuckDB — criterion #2 specifies non-ADBC only.
- A new dedicated "DuckDB file-backed codegen" how-to page — explicit amendment of existing.
- MotherDuck (`md:`) URIs — out of scope for v0.5 (REQUIREMENTS.md "Out of Scope").
- Attach-database codegen (`ATTACH 'other.db' AS x`) — out of scope for v0.5.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DKGEN-04 | `semolina codegen --backend duckdb --database <path>` accepts filesystem paths (relative, `~`-expansion, absolute), opens read-only, runs `INSTALL/LOAD semantic_views` on the native codegen connection, and is verified against a fixture `.db` committed to the test suite | Path normalization slots into `_resolve_backend` (cli/codegen.py:28); INSTALL slots into `engines/duckdb.py:199` (one line before existing LOAD); fixture pattern follows existing `tests/conftest.py:_setup_sales_data`; snapshot pattern follows `tests/integration/test_queries.py` (syrupy). **Note:** REQUIREMENTS.md text says "fixture .db committed to the test suite" but CONTEXT.md overrides this to "generated by pytest at collection time, do NOT commit a binary blob." Planner must respect CONTEXT.md override and update REQUIREMENTS.md DKGEN-04 wording on close (or accept that "committed to the test suite" is satisfied by the fixture-generation code being committed). |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Quality gates:** `prek run --all-files` (ruff lint+format, basedpyright strict,
  shellcheck), `just test` (uv pytest + jaffle-shop mock tests), `just docs-build`
  (sphinx-build -W).
- **Bug fix rule:** Reproduce with failing test first, then fix. Not applicable here
  (greenfield additions, not a bug fix).
- **Code style:** 100-char lines; ruff isort enabled; D213 docstrings (summary on second
  line after opening quotes); multi-line docstring `"""` on own lines.
- **No `# type: ignore` in code** — solve typing issues or use pyproject.toml-level
  exemptions as last resort.
- **Diataxis docs skill (mandatory for doc changes):** Any plan touching
  `docs/src/how-to/codegen.rst` MUST include `@.claude/skills/semolina-docs-author/SKILL.md`
  in its `<execution_context>` block. This is a project-level CLAUDE.md directive.
- **Python ≥3.11**, uv-build backend.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| duckdb | >=1.5.0 (lock: 1.5.2) | Native DuckDB Python driver | Already a `[duckdb]` extra dep (`pyproject.toml:38-41`); only candidate for the native non-ADBC codegen path. [VERIFIED: pyproject.toml + uv.lock] |
| typer | >=0.12.0 | CLI parsing, `BadParameter`, `CliRunner` | Already in core deps (`pyproject.toml:12`); existing CLI uses it throughout. [VERIFIED: pyproject.toml] |
| pytest | >=8.0.0 | Test framework | Existing dev dep (`pyproject.toml:57`); `-n auto` parallel via pytest-xdist. [VERIFIED: pyproject.toml] |
| syrupy | >=5.1.0 | Snapshot assertions with `--snapshot-update` regenerate flag | Already a dev dep (`pyproject.toml:60`); the codebase's only existing snapshot tool (`tests/integration/test_queries.py`, `tests/integration/conftest.py`). Matches CONTEXT.md "regenerate-on-flag" preference. [VERIFIED: pyproject.toml + grep] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib (stdlib) | — | `Path.expanduser()`, `Path.resolve(strict=False)` | The canonical Pythonic path-normalization API. No third-party needed. [CITED: docs.python.org/3/library/pathlib.html] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| syrupy snapshot | Raw `assert source == expected_text` | Brittle to whitespace/ruff format changes; Phase 42 will re-shape generated output. Syrupy is already the project's idiom. |
| syrupy snapshot | Golden file checked into `tests/__snapshots__/` manually | Manual golden files have no regenerate-on-flag affordance; we'd be reinventing what syrupy already provides. |
| pytest fixture generates `.db` | Commit a binary `.db` blob | User explicitly rejected; binary diffs in git history are opaque and the generation code is the better spec. |
| Helper in `cli/codegen.py` (inline) | New `cli/utils.py` module | No existing `cli/utils.py`; introducing one for a 4-line helper is over-abstraction. Inline in `cli/codegen.py` keeps the surface area tight. Planner can decide; **recommendation: inline private helper `_normalize_database_path()` in `cli/codegen.py`**. |

**Installation:**
No new dependencies. All required packages are already in `pyproject.toml`.

**Version verification:**
- duckdb 1.5.2 currently locked (`uv.lock`); pyproject pins `duckdb>=1.5.0` [VERIFIED via uv.lock grep]
- syrupy 5.1.0+ pinned in dev deps; latest 5.x on PyPI [VERIFIED: pyproject.toml dev group]
- pyarrow 17.0.0+ pinned; transitive via `[duckdb]` extra [VERIFIED: pyproject.toml:40]

## Architecture Patterns

### Recommended Code Structure

```
src/semolina/
├── cli/
│   └── codegen.py           # +1 helper: _normalize_database_path
├── engines/
│   └── duckdb.py            # +1 line: INSTALL before LOAD (line 199)
tests/
├── conftest.py              # NEW fixture: duckdb_file_backed_db (session scope)
├── unit/codegen/
│   ├── test_cli.py          # +tests for path normalization (mock layer)
│   └── test_codegen_e2e.py  # NEW: CLI-driven E2E against fixture .db
└── __snapshots__/           # syrupy auto-creates next to test files
```

The pytest fixture file location is Claude's discretion. **Recommendation:** put a
session-scoped fixture in `tests/conftest.py` next to `_setup_sales_data()` (which already
shows the canonical DuckDB semantic-view DDL we need to mirror). A `tests/fixtures/`
directory is overkill for a single .db generator.

### Pattern 1: Path Normalization Helper (RECOMMENDED INLINE)

**What:** A 4-line private helper inside `cli/codegen.py` that applies the locked guard
pattern from CONTEXT.md.

**When to use:** Called from `_resolve_backend` immediately before passing `database` to
`DuckDBEngine(database=...)`.

**Example (verified against CONTEXT.md guard pattern):**
```python
# Source: cli/codegen.py modifications (this phase)
from pathlib import Path

def _normalize_database_path(database: str) -> str:
    """
    Expand ``~`` and resolve relative paths; pass ``":memory:"`` through unchanged.

    Args:
        database: Raw value from --database CLI option or DUCKDB_DATABASE env var.

    Returns:
        Expanded absolute path, or the literal ``":memory:"`` sentinel unchanged.
    """
    if database == ":memory:":
        return database
    return str(Path(database).expanduser().resolve(strict=False))
```

Called from `_resolve_backend` (replaces the bare pass-through at `cli/codegen.py:73`):
```python
elif backend_spec == "duckdb":
    if database is None:
        raise typer.BadParameter(...)
    from semolina.engines.duckdb import DuckDBEngine
    return DuckDBEngine(database=_normalize_database_path(database))
```

The helper takes a non-Optional `str` because the `None` guard fires earlier; this also
keeps the body of `_normalize_database_path` simple.

### Pattern 2: INSTALL Before LOAD on Native Connection

**What:** One-line addition at `engines/duckdb.py:198-199`.

**Current (lines 196-199):**
```python
conn = None
try:
    conn = duckdb.connect(database=self._database, read_only=True)
    conn.execute("LOAD semantic_views")
```

**Target:**
```python
conn = None
try:
    conn = duckdb.connect(database=self._database, read_only=True)
    conn.execute("INSTALL semantic_views FROM community")
    conn.execute("LOAD semantic_views")
```

**Why this works with `read_only=True`:**
- DuckDB extensions are cached at `~/.duckdb/extensions/<version>/<platform>/`, NOT inside
  the database file. [CITED: docs.duckdb.org/lts/extensions/installing_extensions]
- The `read_only` flag controls writes to the DB file; INSTALL writes to the user-level
  extension cache, which is independent.
- The existing `LOAD semantic_views` already runs successfully against `read_only=True`
  in the in-memory codegen path (test `test_introspect_loads_semantic_views_extension_before_describe`
  at `tests/unit/test_duckdb_engine.py:514-549` verifies this is the first SQL executed).
- The CI workflow's "Warm DuckDB semantic_views extension cache" step
  (`.github/workflows/ci.yml:117-127`) runs the same `INSTALL ... FROM community; LOAD ...`
  pair against an in-memory ADBC connection, confirming the pattern is sanctioned.

**Test impact:** `tests/unit/test_duckdb_engine.py` has 7+ tests asserting the executed SQL
sequence (e.g. `test_introspect_loads_semantic_views_extension_before_describe` at line 514).
These will need an extra `INSTALL ...` SQL string in the expected sequence (low-impact
mechanical update).

### Pattern 3: pytest Session Fixture for `.db` Generation

**What:** A session-scoped pytest fixture that builds a real DuckDB file with a
2-dimension + 2-metric + 1-fact semantic view, then yields the path.

**When to use:** Consumed by the new E2E test in `tests/unit/codegen/test_codegen_e2e.py`.

**Reference pattern from `tests/conftest.py:118-160` (`_setup_sales_data`):** that function
already shows the exact `CREATE OR REPLACE SEMANTIC VIEW` DDL we need; the new fixture
will mirror it but write to a `tmp_path_factory`-allocated `.db` file instead of in-memory.

**Example:**
```python
# tests/conftest.py — new fixture, session-scoped
@pytest.fixture(scope="session")
def duckdb_file_backed_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    Generate a file-backed DuckDB database with a sales_view semantic view.

    Session-scoped so the install/setup cost is paid once across the suite.
    The .db is created in a pytest tmp dir and cleaned up at session end.
    """
    import duckdb  # pyright: ignore[reportMissingImports]
    db_path = tmp_path_factory.mktemp("duckdb_fixture") / "sales.db"
    conn = duckdb.connect(database=str(db_path))
    conn.execute("INSTALL semantic_views FROM community")
    conn.execute("LOAD semantic_views")
    conn.execute("""
        CREATE TABLE sales_data (
            id INTEGER, revenue INTEGER, cost INTEGER,
            country VARCHAR, region VARCHAR, unit_price INTEGER
        )
    """)
    conn.execute("""
        INSERT INTO sales_data VALUES
        (1, 1000, 100, 'US', 'West', 10),
        (2, 2000, 200, 'CA', 'West', 20)
    """)
    conn.execute("""
        CREATE SEMANTIC VIEW sales_view
        TABLES (s AS sales_data PRIMARY KEY (id))
        DIMENSIONS (s.country AS s.country, s.region AS s.region)
        METRICS (s.revenue AS SUM(s.revenue), s.cost AS SUM(s.cost))
        FACTS (s.unit_price AS s.unit_price)
    """)
    conn.close()
    return db_path
```

**Critical:** the fixture must use a writable (not `read_only=True`) connection — we're
creating the DB. The codegen-time read-only connection is the engine's concern.

### Pattern 4: CliRunner-Driven E2E Test with syrupy

**What:** Use `typer.testing.CliRunner` (already established at
`tests/unit/codegen/test_cli.py:20`) to invoke the real `semolina codegen` against the
fixture `.db`. Assert generated output against a syrupy snapshot.

**Why not mock:** Success criterion #1 says "generates the same model classes as the
in-memory equivalent." The point is to drive the full surface — `_resolve_backend`, real
`DuckDBEngine`, real introspection — against a real on-disk DB.

**Example:**
```python
# tests/unit/codegen/test_codegen_e2e.py — NEW file
from typer.testing import CliRunner
from semolina.cli import app

runner = CliRunner()

def test_codegen_file_backed_duckdb(
    duckdb_file_backed_db: Path,
    snapshot: SnapshotAssertion,
) -> None:
    """Codegen against an on-disk DuckDB .db produces the expected model class."""
    result = runner.invoke(
        app,
        [
            "codegen", "sales_view",
            "--backend", "duckdb",
            "--database", str(duckdb_file_backed_db),
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.output == snapshot
```

Regenerate via `uv run pytest --snapshot-update tests/unit/codegen/test_codegen_e2e.py`.

### Pattern 5: Packaging Smoke Test CI Job

**What:** A new job in `.github/workflows/ci.yml` that installs `semolina[duckdb]` into a
clean venv (not the dev sync) and imports the duckdb engine module.

**Why:** Phase 38 regression — `[duckdb]` extra was dropped silently during a worktree
merge. A direct extras install in CI catches this class of bug instantly.

**Example (add to ci.yml):**
```yaml
packaging-smoke:
  name: Smoke test [duckdb] extras install
  runs-on: ubuntu-latest
  timeout-minutes: 5
  steps:
    - name: Checkout
      uses: actions/checkout@v6
    - name: Set up uv
      uses: astral-sh/setup-uv@v7
      with:
        enable-cache: true
        cache-dependency-glob: "uv.lock"
    - name: Install [duckdb] extra in clean venv
      run: |
        uv venv /tmp/smoke-venv
        uv pip install --python /tmp/smoke-venv/bin/python ".[duckdb]"
    - name: Import smoke test
      run: |
        /tmp/smoke-venv/bin/python -c "from semolina.engines.duckdb import DuckDBEngine; print('OK')"
```

Narrow by design — no warehouse, no semantic_views extension network call, no test data.
If `[duckdb]` is broken (missing dep, metadata error, version conflict), the import fails.

### Anti-Patterns to Avoid

- **Path-normalize before the `None` check.** `_resolve_backend` already raises
  `BadParameter` when `database is None`; normalize AFTER that guard, not before.
- **Pre-validate file existence in the CLI.** CONTEXT.md is explicit: let DuckDB raise the
  file-not-found error so the error path is consistent. Two error paths = inconsistent UX.
- **Commit the `.db` binary.** User-rejected. Generate via fixture.
- **Use `Path.resolve(strict=True)`.** Would raise `FileNotFoundError` before DuckDB sees
  it; CONTEXT.md mandates non-strict.
- **Open a separate read-write connection just for INSTALL.** Unnecessary — INSTALL writes
  to `~/.duckdb/extensions/`, not the DB file. The `read_only=True` connection works.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Path expansion | Custom regex / `os.path.expanduser` + `os.path.abspath` | `pathlib.Path(...).expanduser().resolve(strict=False)` | Stdlib idiom; round-trips Windows separators; handles symlinks; covered by CONTEXT.md mandate. |
| Snapshot assertions | Manual file-write + diff | `syrupy` (already a dev dep) | Existing project idiom (`tests/integration/test_queries.py`); `--snapshot-update` regenerate flag matches CONTEXT.md preference; PR diffs are readable. |
| Test DB fixture | Hand-built bytes / blob | pytest session fixture + `duckdb.connect()` | CONTEXT.md mandate. Also: `_setup_sales_data` in `tests/conftest.py` is the canonical pattern. |
| CLI testing | `subprocess.run("semolina codegen ...")` | `typer.testing.CliRunner.invoke(app, [...])` | In-process, ANSI-clean (already configured via `_TYPER_FORCE_DISABLE_TERMINAL` in `tests/conftest.py:35`), 100× faster, captures stdout cleanly. |

**Key insight:** Every piece of infrastructure this phase needs already exists in the
codebase. The work is composition + one new SQL string + a documentation pass.

## Common Pitfalls

### Pitfall 1: `Path(":memory:").resolve()` Rewrites the Sentinel

**What goes wrong:** Without the `:memory:` guard, `Path(":memory:").resolve()` returns
something like `/Users/paul/Documents/Dev/Personal/semolina/:memory:` (cwd-prefixed),
which DuckDB then tries to open as a file. In-memory codegen silently breaks.

**Why it happens:** `:memory:` is a DuckDB-specific sentinel, not a real path; `pathlib`
treats it as a relative file name.

**How to avoid:** Apply the CONTEXT.md guard pattern. Add a regression unit test:
```python
def test_normalize_database_path_preserves_memory_sentinel() -> None:
    assert _normalize_database_path(":memory:") == ":memory:"
```

**Warning signs:** Default codegen path (no `--database` value, no env var) failing with
a DuckDB IOException about a missing `:memory:` file.

### Pitfall 2: Existing Unit Tests Asserting SQL Sequence Will Fail

**What goes wrong:** `tests/unit/test_duckdb_engine.py:test_introspect_loads_semantic_views_extension_before_describe`
(line 514) asserts `executed_sqls[0] == "LOAD semantic_views"`. After this phase, it will
be `executed_sqls[0] == "INSTALL semantic_views FROM community"` and
`executed_sqls[1] == "LOAD semantic_views"`.

**Why it happens:** The new INSTALL line is the new index 0.

**How to avoid:** Update the existing test, OR (preferred) loosen the assertion to:
```python
assert "INSTALL semantic_views FROM community" in executed_sqls
assert "LOAD semantic_views" in executed_sqls
install_idx = executed_sqls.index("INSTALL semantic_views FROM community")
load_idx = executed_sqls.index("LOAD semantic_views")
describe_idx = next(i for i, s in enumerate(executed_sqls) if "DESCRIBE SEMANTIC VIEW" in s)
assert install_idx < load_idx < describe_idx
```

**Warning signs:** `test_introspect_loads_semantic_views_extension_before_describe`
fails with `assert 'INSTALL...' == 'LOAD semantic_views'`.

### Pitfall 3: First-Run Network Requirement for INSTALL

**What goes wrong:** A test machine without network connectivity (rare in CI but possible
locally) will fail INSTALL with a download error on first run.

**Why it happens:** INSTALL fetches the extension from `community.duckdb.org` on cache
miss.

**How to avoid:**
- CI is fine: `.github/workflows/ci.yml:117-127` already warms the cache before tests run.
- Local dev: document in the how-to amendment that first run needs network.
- Test marker: NOT recommended (the test is fast and the cache is already warmed in CI).

**Warning signs:** First-run-on-fresh-machine `RuntimeError: IO Error: Failed to download
extension`.

### Pitfall 4: `read_only=True` + Writable Fixture Conflict

**What goes wrong:** If the fixture happens to use `read_only=True` (copy-paste from the
engine code), `CREATE TABLE` and `CREATE SEMANTIC VIEW` fail.

**Why it happens:** Cargo-culting the engine's connection pattern into the fixture.

**How to avoid:** The fixture creates a new file — open with default writable connection
(`duckdb.connect(database=str(db_path))`, no `read_only` kwarg). The engine still opens
read-only for codegen.

**Warning signs:** Fixture fails with `Cannot execute statement of type "CREATE" on
database "sales" which is attached in read-only mode`.

### Pitfall 5: `pytest --doctest-modules` Sees `.db` File and Tries to Doctest

**What goes wrong:** None expected, but worth noting: pytest is configured with
`--doctest-modules` (`pyproject.toml:120`) and `testpaths = ["tests", "src"]`. Binary
`.db` files don't get scanned, but a `.py` fixture-generator script inside `tests/` would
get doctested.

**Why it happens:** `--doctest-modules` walks every `.py` file in `testpaths`.

**How to avoid:** The fixture should live in `tests/conftest.py` (already exempt from
doctest scanning of generated outputs because conftest is harvested separately) or be a
plain pytest fixture function (no module-level executable code). Both patterns are safe.

## Runtime State Inventory

**Skipped:** Phase 41 is greenfield code additions + one CI job + doc amendment. No
renames, refactors, or migrations. Nothing in any of the five state categories applies.

## Code Examples

Verified patterns from project source files:

### CLI Backend Resolution (existing, target for diff)

```python
# Source: src/semolina/cli/codegen.py:65-73 (current)
elif backend_spec == "duckdb":
    if database is None:
        raise typer.BadParameter(
            "DuckDB backend requires a database path. "
            "Use --database or set DUCKDB_DATABASE environment variable."
        )
    from semolina.engines.duckdb import DuckDBEngine

    return DuckDBEngine(database=database)
```

### DuckDB Engine Introspect Connection Setup (existing, target for diff)

```python
# Source: src/semolina/engines/duckdb.py:196-202 (current)
conn = None
try:
    conn = duckdb.connect(database=self._database, read_only=True)
    conn.execute("LOAD semantic_views")
    # Step 1: Get field structure from DESCRIBE SEMANTIC VIEW
    result = conn.execute(f"DESCRIBE SEMANTIC VIEW {unqualified}")
```

### ADBC-side Install Hook (existing template)

```python
# Source: src/semolina/config.py:30-42
def _load_semantic_views(dbapi_conn: Any, connection_record: Any) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("INSTALL semantic_views FROM community")
    cur.execute("LOAD semantic_views")
    cur.close()
```

### Existing Semantic View DDL (template for fixture)

```sql
-- Source: tests/conftest.py:144-158 (the _setup_sales_data fixture)
CREATE OR REPLACE SEMANTIC VIEW sales_view AS
TABLES (
    s AS sales_data PRIMARY KEY (id)
)
DIMENSIONS (
    s.country AS s.country,
    s.region AS s.region,
    s.unit_price AS s.unit_price
)
METRICS (
    s.revenue AS SUM(s.revenue),
    s.cost AS SUM(s.cost)
)
```

For the Phase 41 fixture, recommend splitting `unit_price` into the FACTS clause to
exercise all three field kinds (matches the codegen.rst DuckDB example at lines 159-169):

```sql
CREATE SEMANTIC VIEW sales_view
TABLES (s AS sales_data PRIMARY KEY (id))
DIMENSIONS (s.country AS s.country, s.region AS s.region)
METRICS (s.revenue AS SUM(s.revenue), s.cost AS SUM(s.cost))
FACTS (s.unit_price AS s.unit_price)
```

### Syrupy Snapshot Pattern (existing template)

```python
# Source: tests/integration/test_queries.py:42-47
def test_single_metric(backend_engine: Any, snapshot: SnapshotAssertion) -> None:
    query = _Query().metrics(Sales.revenue)
    rows = list(backend_engine.execute(query))
    assert rows == snapshot
```

Regenerate via `pytest --snapshot-update`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| duckdb (Python) | Engine + fixture | ✓ (locked) | 1.5.2 | — |
| pyarrow | Transitive via `[duckdb]` | ✓ (locked) | 17.0+ | — |
| pytest | Test runner | ✓ | 8.0+ | — |
| syrupy | Snapshot assertions | ✓ | 5.1+ | Hand-written golden file |
| typer | CLI + CliRunner | ✓ | 0.12+ | — |
| Network (community.duckdb.org) | First-run INSTALL only | ✓ (CI warms cache) | n/a | Pre-warmed cache (already in ci.yml) |
| ruff | format_with_ruff() subprocess in renderer | ✓ | — | Renderer falls back to unformatted source if absent |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — all required tooling already present.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x with pytest-xdist (`-n auto`) and pytest-cov |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]` lines 117-135) |
| Quick run command | `uv run pytest tests/unit/codegen/ tests/unit/test_duckdb_engine.py -x` |
| Full suite command | `just test` (uv run pytest + jaffle-shop mock tests) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DKGEN-04 | Path normalization expands `~`, resolves relative paths, preserves `:memory:` | unit | `uv run pytest tests/unit/codegen/test_cli.py -x -k normalize_database_path` | ❌ Wave 0 (add cases) |
| DKGEN-04 | `--backend duckdb --database <path>` invokes DuckDBEngine with normalized path | unit | `uv run pytest tests/unit/codegen/test_cli.py -x -k duckdb_resolve` | ✅ extend existing `test_duckdb_resolve_creates_engine_with_database` |
| DKGEN-04 | INSTALL precedes LOAD on the native codegen connection | unit | `uv run pytest tests/unit/test_duckdb_engine.py -x -k install_loads_semantic_views` | ✅ amend existing `test_introspect_loads_semantic_views_extension_before_describe` |
| DKGEN-04 | E2E: codegen against on-disk fixture .db produces snapshot-matched output | integration (unit-style) | `uv run pytest tests/unit/codegen/test_codegen_e2e.py -x` | ❌ Wave 0 (new test module) |
| DKGEN-04 | `[duckdb]` extra installs cleanly in a clean venv | smoke (CI-only) | GitHub Actions job `packaging-smoke` | ❌ Wave 0 (new ci.yml job) |
| DKGEN-04 | How-to amendment renders (Sphinx -W passes) | doc-build | `just docs-build` (= `uv run sphinx-build -W docs/src docs/_build`) | ✅ existing (job in docs.yml line 42) |
| DKGEN-04 | Traceability table updated on close | static check | manual + `grep DKGEN-04 .planning/REQUIREMENTS.md` | ✅ table exists at REQUIREMENTS.md:57-68 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/codegen/ tests/unit/test_duckdb_engine.py -x`
  (≈3-5 seconds; covers the unit-level surface this phase touches).
- **Per wave merge:** `just test` (full suite, ~30s with `-n auto`); for doc tasks also
  `just docs-build`.
- **Phase gate:** Full suite green + `prek run --all-files` + `just docs-build` before
  `/gsd-verify-work`. The new CI `packaging-smoke` job must also be green.

### Wave 0 Gaps

- [ ] `tests/unit/codegen/test_codegen_e2e.py` — new file, hosts the file-backed E2E test
      covering REQ-DKGEN-04 success criterion #3.
- [ ] `tests/conftest.py` — add session-scoped `duckdb_file_backed_db` fixture (DDL pattern
      from `_setup_sales_data` already present).
- [ ] `tests/unit/codegen/test_cli.py` — add `TestPathNormalization` class with at least:
      `test_memory_sentinel_preserved`, `test_tilde_expanded`, `test_relative_resolved`.
- [ ] `.github/workflows/ci.yml` — add `packaging-smoke` job.

*(Wave 0 produces all four artifacts before Wave 1 implementation begins. Existing
test infrastructure — pytest, syrupy, CliRunner, `_TYPER_FORCE_DISABLE_TERMINAL` env —
needs no setup.)*

### Nyquist Dimension Coverage (Dim 1–8)

| Dim | Property | Coverage in this phase |
|-----|----------|------------------------|
| 1. Surface behaviour | Public CLI / API behaves as documented | E2E test via CliRunner against real fixture .db (DKGEN-04 SC1) |
| 2. Boundary conditions | Edge inputs handled | `:memory:` sentinel preservation; non-existent file path (DuckDB-native error); empty `--database` string |
| 3. Error paths | Failures produce typed errors with correct exit codes | Existing `test_duckdb_connection_error_exits_4` covers SemolinaConnectionError; non-existent file path bubbles through `engines/duckdb.py:174` (covered) |
| 4. State / persistence | Side effects on disk / extension cache | INSTALL is idempotent + writes to `~/.duckdb/extensions/`; fixture creates `.db` in `tmp_path_factory` (auto-cleaned) |
| 5. Concurrency / ordering | Operation sequence is correct | SQL execution-order assertion: INSTALL → LOAD → DESCRIBE SEMANTIC VIEW |
| 6. Integration boundary | External tooling cooperates | Packaging smoke job: `uv pip install '.[duckdb]'` in clean venv + import |
| 7. Documentation | User-facing surface is documented | how-to amendment + Sphinx `-W` build gate |
| 8. Traceability | Requirement closure is observable | REQUIREMENTS.md Traceability table updated (Pending → Complete) at phase close |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `os.path.expanduser` + `os.path.abspath` | `pathlib.Path(...).expanduser().resolve(strict=False)` | Python 3.6+ | Idiomatic; handles Windows separators; same line count |
| Hand-written golden files | `syrupy` snapshot assertions | Project standard (already in use) | `--snapshot-update` regenerate flag; diffable PR output |
| Committing binary test fixtures | pytest fixture generators | This phase (CONTEXT.md mandate) | Generation code = authoritative spec; clean git diffs |
| Single CI test job | Test job + packaging-smoke job | This phase | Catches "extra silently missing" regressions (Phase 38 lesson) |

**Deprecated/outdated:** None applicable — this is greenfield additions.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | INSTALL extension succeeds on a `read_only=True` connection because the extension cache lives outside the DB file | Pattern 2 + Pitfall 4 | If wrong, the engine code path breaks the whole codegen flow. **Mitigation:** the CI workflow already runs the same INSTALL pattern (`.github/workflows/ci.yml:117-127`) on an in-memory connection, confirming the pattern works at least there. The E2E test will catch any read-only-specific failure during Phase 41 execution. Likelihood of being wrong: LOW — extension cache being external is documented [CITED: docs.duckdb.org]. |
| A2 | Existing `tests/unit/test_duckdb_engine.py` tests need only mechanical updates (one new expected SQL string) | Pitfall 2 | Low — change is additive (one line) and the affected assertion is well-localized. |
| A3 | The DuckDB semantic_views extension is stable enough across 1.5.0–1.5.2 that a fixture built with one version is introspectable by another in the same minor range | Pattern 3 | LOW risk — pyproject pins `duckdb>=1.5.0` and uv.lock pins 1.5.2; CI runs against the locked version. |
| A4 | `tmp_path_factory.mktemp` provides session-scoped cleanup adequate for the fixture | Pattern 3 | LOW — standard pytest idiom; well-documented. |

## Open Questions

1. **Should `_normalize_database_path` live in `cli/codegen.py` or `cli/utils.py`?**
   - What we know: CONTEXT.md flags this as Claude's discretion. No `cli/utils.py` exists today.
   - What's unclear: Whether Phase 42 (field-type inference) will introduce other CLI helpers
     that would naturally cluster.
   - Recommendation: **Inline in `cli/codegen.py`** as a private `_normalize_database_path`.
     Extract to `cli/utils.py` only when a second caller appears (YAGNI). The function is 4
     lines; the indirection cost of a new module exceeds the cohesion benefit.

2. **Should the fixture be session- or function-scoped?**
   - What we know: pytest sessions can run in parallel (`-n auto` via xdist).
   - What's unclear: Whether multiple workers would race on the same fixture .db.
   - Recommendation: **Session-scoped, per-worker** — `tmp_path_factory` is per-worker
     under xdist (each worker gets its own tmp dir), so session scope is safe and avoids
     paying the install/load cost N times per worker.

3. **REQUIREMENTS.md DKGEN-04 wording vs CONTEXT.md fixture override.**
   - What we know: REQUIREMENTS.md line 22 says "fixture `.db` committed to the test
     suite." CONTEXT.md says "do NOT commit a binary blob; generate at fixture time."
   - What's unclear: Whether the planner should silently accept the override, or amend
     REQUIREMENTS.md wording when closing the requirement.
   - Recommendation: **Amend REQUIREMENTS.md DKGEN-04 wording at phase close** to read
     "...verified against a fixture `.db` generated at test-collection time by a committed
     pytest fixture." Honors CONTEXT.md without breaking the audit trail. Add this as a
     line item in the traceability-close task.

## Sources

### Primary (HIGH confidence)
- `src/semolina/cli/codegen.py` (full file read) — current `_resolve_backend` signature and
  DuckDB branch
- `src/semolina/engines/duckdb.py` (full file read) — current LOAD-only behavior at line 199
- `src/semolina/config.py:30-42` — ADBC-side install template
- `src/semolina/codegen/python_renderer.py` (full file read) — output formatting via ruff
- `src/semolina/codegen/introspector.py` (full file read) — IntrospectedView dataclass shape
- `tests/conftest.py` (full file read) — existing `_setup_sales_data` semantic-view DDL
- `tests/unit/codegen/test_cli.py` (full file read) — CliRunner pattern + existing DuckDB tests
- `tests/unit/test_duckdb_engine.py` (full file read) — assertion patterns to amend
- `tests/integration/test_queries.py` + `tests/integration/conftest.py` (read for syrupy idiom)
- `.github/workflows/ci.yml` (full file read) — existing extension cache-warming step
- `.github/workflows/docs.yml` (full file read) — Sphinx -W build gate location
- `pyproject.toml` (full file read) — confirms syrupy 5.1+, duckdb>=1.5.0, pyarrow>=17 in `[duckdb]`
- `uv.lock` — duckdb 1.5.2 locked [VERIFIED via grep]
- `.planning/REQUIREMENTS.md` — DKGEN-04 wording + Traceability table format (lines 57-68)
- `.planning/milestones/v0.4.0-REQUIREMENTS.md:75-97` — canonical Traceability table example
  with Evidence column
- `.planning/milestones/v0.4.0-phases/38-packaging-fix-test-cleanup/38-RESEARCH.md` —
  context on the Phase 38 packaging regression this phase guards against
- `docs/src/how-to/codegen.rst` (full file read) — current how-to structure to amend
- `CLAUDE.md` (full project instructions) — quality gates, docs skill mandate
- `.claude/skills/semolina-docs-author/SKILL.md` — doc workflow mandate

### Secondary (MEDIUM confidence)
- DuckDB official docs (extension installation): extensions are cached at
  `~/.duckdb/extensions/<version>/<platform>/`, independent of the DB file
  [CITED: https://duckdb.org/docs/lts/extensions/installing_extensions]
- DuckDB community extensions docs: `INSTALL name FROM community` is the standard pattern
  [CITED: https://duckdb.org/community_extensions/]

### Tertiary (LOW confidence)
- WebSearch: "INSTALL extension stores in user cache, not DB file, therefore read_only=True
  permits INSTALL." Multiple sources agree but no single authoritative DuckDB doc page
  spells this out for `read_only=True` explicitly. **Mitigation:** the project's own CI
  already runs the INSTALL on an in-memory ADBC connection successfully, and `LOAD` already
  runs successfully on `read_only=True`. The E2E test in this phase will be the definitive
  proof.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every dependency already in `pyproject.toml`; versions verified
  via uv.lock and grep.
- Architecture / patterns: HIGH — all patterns are 1-line additions to verified existing
  code (`_resolve_backend`, `introspect`).
- Pitfalls: HIGH — pitfalls 1–4 are all anchored to specific verified file:line locations.
- INSTALL-on-read-only-connection behavior: MEDIUM — inferred from cache-location docs and
  project's existing CI pattern; not a direct quote from DuckDB docs. The E2E test will
  empirically verify in this phase.
- Validation architecture: HIGH — Wave 0 gaps are explicit; full suite command verified
  against project `justfile`.

**Research date:** 2026-05-15
**Valid until:** 2026-06-15 (30-day window; DuckDB 1.5.x is stable, `[duckdb]` extra is
locked in pyproject; nothing fast-moving in scope.)
