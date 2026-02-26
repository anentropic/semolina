# Phase 13: Documentation Accuracy & Phase Verification (GAP CLOSURE) - Research

**Researched:** 2026-02-22
**Domain:** Documentation accuracy corrections, phase verification, credential pattern alignment
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Verification approach
- Verify Phase 11 by doing **both**: inspect CI config/workflow files AND run doctest commands locally
- Both signals are required — config existence alone is not sufficient; tests must pass
- If doctests fail during verification: **block** — fix the failures before writing VERIFICATION.md
- Scope of verification: DOCS-10 (CI enforcement) AND confirm doctest content exists in the source modules being tested

#### VERIFICATION.md format
- **Standard level of detail**: each Phase 11 success criterion gets its own section with what was checked and the result; include short command outputs or relevant file excerpts as evidence
- Verdict structure and retrospective-noting: Claude's discretion — follow existing VERIFICATION.md format in the project if one exists, otherwise use a clear VERIFIED / NOT VERIFIED header with date

#### Fix scope
- Fix the 3 listed items (filtering.md, warehouse-testing.md, conftest.py) **plus** do a light review of all v0.2 user-facing docs in the `docs/` directory
- If the review finds additional inaccuracies: **fix them in this phase** (don't log for later)
- Review scope: all v0.2 user-facing docs in `docs/` — not just the files being directly edited
- After fixing `conftest.py`: run jaffle-shop tests to confirm no breakage

### Claude's Discretion
- Whether to add a retrospective note to Phase 11 VERIFICATION.md (e.g., "verified in Phase 13 gap closure")
- Exact VERIFICATION.md verdict format — match existing project conventions
- How to handle partial doctest failures during verification (fix vs note)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DOCS-10 | Examples in docstrings validated with doctest (fail on broken examples) | Phase 11 CI changes confirmed: two-step pytest in ci.yml, both steps verified to exist. VERIFICATION.md creation will formally close this. |
| DOCS-04 | Query language guide: Q-objects and AND/OR composition | filtering.md lookup table uses `__gte`/`__lte`; `fields.py` Field operators produce `__ge`/`__le`. Exact lines to fix identified. |
| TEST-VCR/DOCS-09 | Snapshot record/replay warehouse tests; GitHub Pages auto-deploy | warehouse-testing.md has 5 categories of inaccuracies (file paths, constant name, conftest location, snapshot dir, Databricks env var). All verified against actual files. |
| INT-01 | User can run pytest suite against real Snowflake jaffle-shop data | Covered by INT-06 fix below — correct credential loading enables real warehouse test execution. |
| INT-06 | Warehouse credentials loaded from environment (not hardcoded) | cubano-jaffle-shop conftest.py uses `os.environ` directly. `SnowflakeCredentials.load()` API fully characterized — supports CUBANO_ENV_FILE priority chain. |
</phase_requirements>

---

## Summary

Phase 13 is a targeted gap-closure phase with four discrete deliverables, all of which are surgical corrections to existing files. No new features, no new infrastructure, no dependency installs. The research confirms every specific change required and provides the exact current state of each file to fix.

**Plan 13-01** creates a missing VERIFICATION.md for Phase 11. Phase 11's CI changes are fully confirmed: `ci.yml` has two separate pytest steps (`uv run pytest tests/ -n auto -v --snapshot-warn-unused` and `uv run pytest src/ --doctest-modules -v`). The VERIFICATION.md must follow the same frontmatter + observable-truth-table format used by Phases 10.1 and 12. Verification requires running both commands locally to confirm they pass.

**Plans 13-02 through 13-04** are documentation accuracy fixes. All inaccuracies were precisely enumerated in the v0.2 milestone audit and confirmed by direct file inspection. The filtering.md fix is 2 cells in a Markdown table. The warehouse-testing.md fix is 5 categories of stale references. The conftest.py fix is a pattern substitution in the `snowflake_connection` fixture from raw `os.environ` to `SnowflakeCredentials.load()`.

**Primary recommendation:** Execute each plan as a standalone atomic change. All four plans are independent — no ordering constraints between plans 13-02, 13-03, 13-04. Plan 13-01 (VERIFICATION.md creation) should follow the same evidence-gathering pattern used in Phase 12 VERIFICATION.md: run commands, capture output, document in a truth table.

---

## Standard Stack

This phase uses no new libraries. It operates entirely within the existing project stack.

### Existing Tools In Use

| Tool | Purpose | Where |
|------|---------|--------|
| pytest | Run doctests locally during verification (`pytest src/ --doctest-modules -v`) | CI + local |
| `SnowflakeCredentials.load()` | Credential loading with CUBANO_ENV_FILE priority chain | `src/cubano/testing/credentials.py` |
| `CredentialError` | Exception class for failed credential loading | `src/cubano/testing/credentials.py` |
| ruff | Lint/format check after any Python file changes | `pyproject.toml` |
| basedpyright | Typecheck after any Python file changes | `pyproject.toml` |

**Installation:** No new packages required.

---

## Architecture Patterns

### VERIFICATION.md Format (Established Convention)

All existing VERIFICATION.md files follow this structure. Phase 11 VERIFICATION.md must match.

```
---
phase: 11-ci-example-updates
verified: <ISO date>
status: VERIFIED | gaps_found | human_needed
score: N/M must-haves verified
re_verification: true (this is a re-verification)
---

# Phase 11: CI & Example Updates - Verification Report

**Phase Goal:** <from CONTEXT.md>
**Verified:** <date>
**Status:** VERIFIED
**Re-verification:** Yes — verified in Phase 13 gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | ... | VERIFIED | <short command output or file excerpt> |
...

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| DOCS-10 | 11-01-PLAN.md | Doctest validation in CI | SATISFIED | ... |
```

**Existing VERIFICATION.md files to reference:** `.planning/phases/12-warehouse-testing-syrupy/12-VERIFICATION.md` (most recent, best template).

### SnowflakeCredentials.load() Pattern (for jaffle-shop conftest fix)

The correct replacement for the raw `os.environ` fixture:

```python
# BEFORE (Plan 13-04 target — raw os.environ access)
@pytest.fixture
def snowflake_connection() -> None:
    import os
    from cubano.engines.snowflake import SnowflakeEngine

    account = os.environ.get("SNOWFLAKE_ACCOUNT")
    if not account:
        pytest.skip("SNOWFLAKE_* credentials not set")

    engine = SnowflakeEngine(
        account=account,
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        role=os.environ.get("SNOWFLAKE_ROLE"),
    )
    cubano.register("default", engine)
    yield
    cubano.unregister("default")


# AFTER (uses SnowflakeCredentials.load() with proper fallback chain)
@pytest.fixture
def snowflake_connection() -> None:
    from cubano.engines.snowflake import SnowflakeEngine
    from cubano.testing.credentials import CredentialError, SnowflakeCredentials

    try:
        creds = SnowflakeCredentials.load()
    except CredentialError as e:
        pytest.skip(f"Snowflake credentials not available: {e}")

    engine = SnowflakeEngine(
        account=creds.account,
        user=creds.user,
        password=creds.password.get_secret_value(),
        warehouse=creds.warehouse,
        database=creds.database,
        role=creds.role,
    )
    cubano.register("default", engine)
    yield
    cubano.unregister("default")
```

**Key difference:** `SnowflakeCredentials.load()` respects the `CUBANO_ENV_FILE > env_file param > .env` priority chain. Raw `os.environ` bypasses `.env` fallback and `.cubano.toml` config file fallback entirely.

**Important:** `password` is a `SecretStr` — must call `.get_secret_value()` when passing to `SnowflakeEngine`. The existing `tests/integration/conftest.py:snowflake_engine` fixture (lines 264-279) is the canonical reference for this pattern.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Credential loading fallback chain | Custom `os.environ` with manual checks | `SnowflakeCredentials.load()` | Already handles CUBANO_ENV_FILE > .env > .cubano.toml chain; raises `CredentialError` for clean skip |
| VERIFICATION.md format | Custom format | Match Phase 12 VERIFICATION.md structure | Consistency enables audit tooling; Phase 12 is the most recent and best template |

---

## Common Pitfalls

### Pitfall 1: SecretStr.get_secret_value() Required
**What goes wrong:** `SnowflakeCredentials.load().password` is a `pydantic.SecretStr`, not a plain `str`. Passing it directly to `SnowflakeEngine(password=...)` will fail at runtime or typecheck.
**Why it happens:** pydantic-settings uses `SecretStr` to prevent accidental logging of credentials.
**How to avoid:** Always call `.get_secret_value()`: `creds.password.get_secret_value()`
**Warning signs:** basedpyright will flag the type mismatch if `SnowflakeEngine.__init__` expects `str`.

### Pitfall 2: warehouse-testing.md Has More Than 2 Inaccuracies
**What goes wrong:** The audit found 5 categories of inaccuracies (not just the "7 references" — these 7 are spread across 5 distinct types of errors). A fix that only corrects the most obvious ones (file path, constant name) will leave the Databricks env var name and snapshot directory path wrong.
**Why it happens:** The doc was written before the directory restructuring from `tests/` flat layout to `tests/integration/` subfolder.
**How to avoid:** Fix all 5 categories (detailed in Code Examples section below).
**Warning signs:** After editing, grep for `SNAPSHOT_TEST_DATA`, `test_snapshot_queries`, `tests/__snapshots__`, `DATABRICKS_HOST`, `tests/conftest.py` — all should return 0 matches in the updated file.

### Pitfall 3: Phase 11 Doctest Count Discrepancy
**What goes wrong:** Phase 10 verification (original) recorded "16 doctests" but Phase 11 SUMMARY reports "20 passed + 6 skipped = 26 items". The correct current count is 26 items (20 passing + 6 skipped), not 16.
**Why it happens:** More doctests were added in Phase 10.1 (API refactor added docstring examples to new methods). The Phase 10 verification ran before Phase 10.1 was complete.
**How to avoid:** Run `uv run pytest src/ --doctest-modules -v` locally and report the actual count in the VERIFICATION.md.
**Warning signs:** If local run shows a count different from either 16 or 26, report the actual count; do not hardcode either estimate.

### Pitfall 4: filtering.md — Only `__gte`/`__lte` Need Changing
**What goes wrong:** Fixing `__gte` → `__ge` and `__lte` → `__le` in the table but also mistakenly changing `__gt` and `__lt` (which are already correct).
**Why it happens:** All four look similar. The operators `__gt` and `__lt` are correct in both the docs table AND `fields.py`. Only the "or equal" variants are wrong.
**How to avoid:** Verify against `fields.py` Field operator output: `__ge` (>=), `__le` (<=), `__gt` (>), `__lt` (<) — these are the four implemented operators. The table currently has `__gt` (correct), `__gte` (wrong), `__lt` (correct), `__lte` (wrong).

### Pitfall 5: Scope Creep on Light Doc Review
**What goes wrong:** "Light review of all v0.2 user-facing docs" becomes a major rewrite that delays phase completion.
**Why it happens:** Finding minor phrasing issues triggers editing beyond what's needed.
**How to avoid:** The review scope is accuracy only — wrong facts, wrong file paths, wrong command syntax. Style improvements go in Phase 14 (documentation overhaul). If a found issue is a "nice to improve" rather than "factually wrong", skip it.

---

## Code Examples

### Plan 13-01: Phase 11 Observable Truths to Verify

The VERIFICATION.md must verify these truths (based on Phase 11 CONTEXT.md and SUMMARY.md):

| Truth | Verification Command | Expected |
|-------|---------------------|---------|
| CI has two separate pytest steps | `grep -n "pytest" .github/workflows/ci.yml` | Shows "Run unit tests" and "Run doctests" steps |
| Unit test step: `pytest tests/ -n auto -v --snapshot-warn-unused` | Read ci.yml | Exact command present |
| Doctest step: `pytest src/ --doctest-modules -v` | Read ci.yml | Exact command present |
| Unit tests pass locally | `uv run pytest tests/ -n auto -v` | Exit 0, ~433+ passed |
| Doctests pass locally | `uv run pytest src/ --doctest-modules -v` | Exit 0, 20+ passed, 6 skipped |
| No merged `pytest tests/ src/` form | `grep "pytest tests/ src/" .github/workflows/ci.yml` | 0 results |

**Current ci.yml truth** (verified by direct read): Lines 109-113:
```yaml
- name: Run unit tests
  run: uv run pytest tests/ -n auto -v --snapshot-warn-unused

- name: Run doctests
  run: uv run pytest src/ --doctest-modules -v
```
This exactly satisfies the DOCS-10 requirement. The VERIFICATION.md can be written with HIGH confidence.

### Plan 13-02: filtering.md Lookup Table Fix

Current table (lines 39-49 of `docs/src/guides/filtering.md`):

```markdown
| `__gt` | Greater than | `Q(revenue__gt=1000)` |
| `__gte` | Greater than or equal | `Q(revenue__gte=500)` |   ← WRONG: should be __ge
| `__lt` | Less than | `Q(revenue__lt=100)` |
| `__lte` | Less than or equal | `Q(revenue__lte=999)` |    ← WRONG: should be __le
```

Source of truth (`src/cubano/fields.py`):
- `Field.__ge__` → `Q(**{f"{self.name}__ge": value})` (line 290)
- `Field.__le__` → `Q(**{f"{self.name}__le": value})` (line 250)

After fix:
```markdown
| `__gt` | Greater than | `Q(revenue__gt=1000)` |
| `__ge` | Greater than or equal | `Q(revenue__ge=500)` |
| `__lt` | Less than | `Q(revenue__lt=100)` |
| `__le` | Less than or equal | `Q(revenue__le=999)` |
```

Note: The examples using `revenue__gte` and `revenue__lte` in the right column also need updating to `revenue__ge` and `revenue__le`.

Also check: The "Multiple `.where()` calls" code example at line 136 uses `Q(revenue__gte=min_revenue)` — this should be fixed to `Q(revenue__ge=min_revenue)` if present.

### Plan 13-03: warehouse-testing.md Specific Corrections

**Audit-confirmed inaccuracies (from v0.2-MILESTONE-AUDIT.md cross-referenced with actual files):**

| Location in doc | Wrong | Correct | How to verify |
|----------------|-------|---------|--------------|
| Line 17: fixture location | `tests/conftest.py` | `tests/integration/conftest.py` | `ls tests/integration/conftest.py` |
| Line 43, 82, 175: test file | `tests/test_snapshot_queries.py` | `tests/integration/test_queries.py` | `ls tests/integration/test_queries.py` |
| Line 54-57, 153, 169, 215, 217: constant | `SNAPSHOT_TEST_DATA` | `TEST_DATA` | `grep "TEST_DATA" tests/integration/conftest.py` |
| Line 92, 100, 183, 225: snapshot dir | `tests/__snapshots__/` | `tests/integration/__snapshots__/` | `ls tests/integration/__snapshots__/` |
| Line 137, 285: Databricks env var | `DATABRICKS_HOST` | `DATABRICKS_SERVER_HOSTNAME` | `grep server_hostname src/cubano/testing/credentials.py` |

**Recording command** (lines 82, 175) also references wrong file path and needs updating:
```bash
# Wrong:
pytest --snapshot-update tests/test_snapshot_queries.py
# Correct:
uv run pytest tests/integration/test_queries.py --snapshot-update
```

**Step 2 instructions** reference `tests/conftest.py` → must become `tests/integration/conftest.py`.

**git diff step** (lines 92, 183) references `tests/__snapshots__/` → must become `tests/integration/__snapshots__/`.

### Plan 13-04: jaffle-shop conftest.py Pattern

**Current state** (`cubano-jaffle-shop/tests/conftest.py`, lines 82-108):

```python
@pytest.fixture
def snowflake_connection() -> None:
    import os
    from cubano.engines.snowflake import SnowflakeEngine

    account = os.environ.get("SNOWFLAKE_ACCOUNT")
    if not account:
        pytest.skip("SNOWFLAKE_* credentials not set")

    engine = SnowflakeEngine(
        account=account,
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        role=os.environ.get("SNOWFLAKE_ROLE"),
    )
    cubano.register("default", engine)
    yield
    cubano.unregister("default")
```

**Target state:**
```python
@pytest.fixture
def snowflake_connection() -> None:
    from cubano.engines.snowflake import SnowflakeEngine
    from cubano.testing.credentials import CredentialError, SnowflakeCredentials

    try:
        creds = SnowflakeCredentials.load()
    except CredentialError as e:
        pytest.skip(f"Snowflake credentials not available: {e}")

    engine = SnowflakeEngine(
        account=creds.account,
        user=creds.user,
        password=creds.password.get_secret_value(),
        warehouse=creds.warehouse,
        database=creds.database,
        role=creds.role,
    )
    cubano.register("default", engine)
    yield
    cubano.unregister("default")
```

**After fix:** Run `uv run pytest cubano-jaffle-shop/tests/ -m mock -v` to confirm all mock tests still pass. The `snowflake_connection` fixture is only used by warehouse-marked tests, so mock tests should not be affected.

---

## State of the Art

| Old/Wrong | Correct | Phase Introduced | Impact |
|-----------|---------|-----------------|--------|
| `__gte`/`__lte` in filtering.md | `__ge`/`__le` | Phase 10.1-02 (Field operators added) | Users writing Q lookups from docs get different behavior than operator overloads |
| `tests/test_snapshot_queries.py` | `tests/integration/test_queries.py` | Restructured during Phase 12 | Developer cannot find file; guide completely non-functional for new contributors |
| `SNAPSHOT_TEST_DATA` | `TEST_DATA` | Renamed during Phase 12 | Devs looking for the constant in the conftest find nothing |
| `tests/conftest.py` (snapshot fixtures) | `tests/integration/conftest.py` | Restructured during Phase 12 | Wrong conftest location throughout guide |
| `tests/__snapshots__/` | `tests/integration/__snapshots__/` | Restructured during Phase 12 | Wrong path for `git diff` review step |
| `DATABRICKS_HOST` | `DATABRICKS_SERVER_HOSTNAME` | Databricks SDK convention | Snowflake uses HOST but Databricks SDK uses SERVER_HOSTNAME |
| `os.environ["SNOWFLAKE_*"]` in jaffle-shop conftest | `SnowflakeCredentials.load()` | Pattern established in Phase 8 | Bypasses CUBANO_ENV_FILE chain, .env files, and .cubano.toml config |
| Phase 11 missing VERIFICATION.md | VERIFICATION.md exists | Process gap from Phase 11 execution | Audit blocker; DOCS-10 remains "partial" without it |

---

## Open Questions

1. **filtering.md: `revenue__gte` usage in prose/examples beyond the table**
   - What we know: The table has `__gte`/`__lte` in rows 2 and 4. The "Multiple `.where()` calls" section at the end of filtering.md also uses `Q(revenue__gte=min_revenue)`.
   - What's unclear: May be additional occurrences in other docs files that the audit didn't flag.
   - Recommendation: During plan 13-02 execution, `grep -r "__gte\|__lte" docs/` to find all occurrences and fix all in one pass.

2. **Light doc review scope — what to look for**
   - What we know: The audit explicitly called out filtering.md and warehouse-testing.md. Other docs were not audited in the same depth.
   - What's unclear: Whether other guides have similar staleness from Phase 10.1 refactor.
   - Recommendation: For the light review (part of plan 13-02 per CONTEXT.md fix scope), check: (a) any reference to old `Query()` API vs `Model.query()`, (b) any reference to `.filter()` vs `.where()`, (c) any references to deprecated imports. The quick-4 task already updated docs for the API refactor, so this is likely clean.

3. **Whether doctests currently pass locally**
   - What we know: Phase 11 SUMMARY reports 20 passed, 6 skipped. Phase 10 verification reported 16.
   - What's unclear: Whether any doctest was broken by Phase 12 or quick tasks since Phase 11.
   - Recommendation: Run `uv run pytest src/ --doctest-modules -v` as the first action in plan 13-01. If any doctests fail, fix them before writing VERIFICATION.md (locked decision: block if failures).

---

## File Map (Complete Reference)

All files relevant to this phase:

| Plan | File | Action |
|------|------|--------|
| 13-01 | `.planning/phases/11-ci-example-updates/11-VERIFICATION.md` | CREATE |
| 13-01 | `.github/workflows/ci.yml` | READ (verify, do not modify) |
| 13-01 | `src/cubano/` | RUN doctests (do not modify) |
| 13-02 | `docs/src/guides/filtering.md` | EDIT (2 table rows + any prose occurrences) |
| 13-03 | `docs/src/guides/warehouse-testing.md` | EDIT (5 categories of inaccuracies, ~15 lines) |
| 13-04 | `cubano-jaffle-shop/tests/conftest.py` | EDIT (snowflake_connection fixture only) |

**Light review files** (per CONTEXT.md fix scope):
- `docs/src/guides/first-query.md`
- `docs/src/guides/models.md`
- `docs/src/guides/queries.md`
- `docs/src/guides/ordering.md`
- `docs/src/guides/installation.md`
- `docs/src/guides/backends/snowflake.md`
- `docs/src/guides/backends/databricks.md`
- `docs/src/guides/backends/overview.md`
- `docs/src/guides/codegen.md`
- `docs/src/index.md`
- `docs/src/changelog.md`

---

## Sources

### Primary (HIGH confidence)

- Direct file reads — `docs/src/guides/filtering.md` (full content, inaccuracies confirmed)
- Direct file reads — `docs/src/guides/warehouse-testing.md` (full content, all 5 inaccuracy categories confirmed)
- Direct file reads — `src/cubano/fields.py` (Field.__ge__ and Field.__le__ operator implementations)
- Direct file reads — `cubano-jaffle-shop/tests/conftest.py` (current `snowflake_connection` fixture)
- Direct file reads — `src/cubano/testing/credentials.py` (SnowflakeCredentials.load() full implementation)
- Direct file reads — `.github/workflows/ci.yml` (Phase 11 CI changes confirmed: two pytest steps present)
- Direct file reads — `.planning/phases/11-ci-example-updates/11-01-SUMMARY.md` (Phase 11 truth confirmed)
- Direct file reads — `.planning/phases/12-warehouse-testing-syrupy/12-VERIFICATION.md` (VERIFICATION.md format template)
- Direct file reads — `.planning/v0.2-MILESTONE-AUDIT.md` (authoritative gap enumeration)
- Direct file reads — `tests/integration/conftest.py` (canonical SnowflakeCredentials.load() pattern for fixtures)
- Direct file reads — `tests/integration/test_queries.py` (actual test file replacing `tests/test_snapshot_queries.py`)

### Secondary (MEDIUM confidence)

None required — all findings verified from source files directly.

---

## Metadata

**Confidence breakdown:**
- Plan 13-01 (VERIFICATION.md): HIGH — ci.yml content directly read, Phase 11 SUMMARY documents exact changes; only uncertainty is current doctest count (must run locally)
- Plan 13-02 (filtering.md): HIGH — exact wrong values and correct values verified from `fields.py` source
- Plan 13-03 (warehouse-testing.md): HIGH — all 5 inaccuracy categories verified by reading both the doc and the actual files they reference
- Plan 13-04 (conftest.py): HIGH — current fixture code directly read, target pattern directly read from `tests/integration/conftest.py`

**Research date:** 2026-02-22
**Valid until:** Stable — all findings are based on current file state; valid until any of the referenced files change
