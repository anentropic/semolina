# Phase 12: warehouse-testing-syrupy - Research

**Researched:** 2026-02-17
**Domain:** pytest snapshot testing for warehouse query replay
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- Record automatically on first local run (snapshot file doesn't exist)
- Snapshots capture query results only (no execution metadata like timing or row counts)
- Automatically scrub credentials from snapshots before storage to prevent accidental secret leaks
- Use syrupy's standard directory structure: `__snapshots__/test_module.ambr` (human-readable YAML format)
- Tests include `snapshot` fixture parameter in signature: `def test_query(snapshot):`
- Use syrupy's built-in behavior directly: developers run `pytest --snapshot-update` to record, `pytest` defaults to replay
- No warehouse test markers needed (all tests in this phase use snapshots)
- Fail fast with clear message when snapshot file is missing or stale (guides developer to `pytest --snapshot-update`)
- Demonstrate both Snowflake and Databricks backend compatibility (primary focus: SQL compatibility, no errors, expected semantics)
- Include query patterns with model relationships and metric aggregations (beyond simple SELECTs)
- Happy path only (error cases tested separately)
- Use synthetic test dataset for sample tests (isolated, simplified)
- Commit snapshot files to git (version control all recorded results)
- Developers run `pytest --snapshot-update` locally to create initial snapshots before committing
- Use standard git diff for snapshot changes in PRs (no custom diff tooling)
- Developer guide covers both workflow (how to add tests) and snapshot management (re-recording strategy, auditing changes, deprecation approach)

### Claude's Discretion

- Specific test patterns within the Snowflake/Databricks coverage scope
- Snapshot comparison logic and exact matching strategy
- Performance optimization of snapshot storage/comparison

### Deferred Ideas (OUT OF SCOPE)

- Custom snapshot diff tooling (e.g., "X rows changed, Y values differ" summaries)
- Performance regression testing via snapshot metadata (execution time tracking)
- Snapshot versioning/expiry policies
</user_constraints>

---

## Summary

Syrupy 5.1.0 is the correct choice for this phase. It is a zero-dependency pytest plugin that integrates directly with the existing `pytest>=8` infrastructure already in Cubano's dev dependencies. The library's `snapshot` fixture fits the locked API design exactly: `def test_query(snapshot): assert result == snapshot`. Missing snapshots fail immediately with "snapshot missing" error, guiding developers to run `pytest --snapshot-update`. Snapshots are stored in `__snapshots__/test_module.ambr` files using a human-readable Amber format (not YAML proper, but Python-repr-based with structure similar to YAML).

The core implementation challenge is credential scrubbing. Syrupy has no built-in secret detection; the approach is to use a custom `conftest.py` snapshot fixture override that wraps results through a scrubber before assertion, or use syrupy's `exclude` / `path_value` matcher to redact known credential-bearing fields. For warehouse query results (which return data rows, not connection metadata), credential leakage is low-risk by design: query results don't contain connection strings or tokens. The scrubbing requirement is primarily defensive — ensure synthetic test data doesn't happen to match credential patterns.

The key architectural decision is where snapshot tests live. Given the zero-runtime-dependencies constraint and the synthetic dataset requirement, snapshot tests should be a new test module in `tests/` (the main cubano package test suite), not in `cubano-jaffle-shop`. This keeps them tightly coupled to the core query infrastructure.

**Primary recommendation:** Add `syrupy>=5.1.0` to `[dependency-groups].dev`, create `tests/test_snapshot_queries.py` with a synthetic SemanticView model and snapshot fixture override in `tests/conftest.py`, and structure CI to run snapshot tests as part of the regular `pytest tests/` command (snapshots already committed, no credentials needed).

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| syrupy | >=5.1.0 | Snapshot assertion fixture for pytest | Industry standard, zero deps, native pytest integration, MIT license |

### Supporting (already present)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8.0.0 | Test framework (already in dev deps) | Required by syrupy 5.x |
| pydantic-settings | >=2.7.0 | Credential loading (already in dev deps) | Needed for warehouse fixtures |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| syrupy | pytest-snapshot | pytest-snapshot is simpler but less featured; no exclude/matcher API for credential scrubbing |
| syrupy | snapshottest | Unmaintained, older API style (`snapshot.assert_match(x)` vs `assert x == snapshot`) |
| syrupy | VCR.py | VCR intercepts HTTP transport; not applicable to warehouse connectors using native binary protocols |
| syrupy | Betamax | Same constraint as VCR — HTTP only, not applicable |
| syrupy Amber format | JSONSnapshotExtension | JSON is diff-friendly for large datasets, but Amber is default and handles all Python types natively |

**Installation:**
```bash
uv add --group dev syrupy
```

This adds to `[dependency-groups].dev` in `pyproject.toml`.

---

## Architecture Patterns

### Recommended Project Structure

```
tests/
├── conftest.py                    # Add snapshot fixture override here
├── test_snapshot_queries.py       # New: snapshot-based query tests
└── __snapshots__/
    └── test_snapshot_queries.ambr # Auto-generated, committed to git
```

The `__snapshots__` directory is created automatically by syrupy on first `pytest --snapshot-update` run.

### Pattern 1: Basic Snapshot Assertion

**What:** The snapshot fixture compares query results against stored `.ambr` file. On first run (missing snapshot), the test fails with "snapshot missing" — developer runs `pytest --snapshot-update` to create it.

**When to use:** Any deterministic query result that should not change.

```python
# Source: https://github.com/syrupy-project/syrupy (README)
def test_query_returns_expected_results(snapshot):
    result = SyntheticModel.query().metrics(SyntheticModel.revenue).execute()
    # Converts to list[dict] for stable serialization
    assert [dict(row) for row in result] == snapshot
```

### Pattern 2: Snapshot Fixture Override in conftest.py

**What:** Override the default `snapshot` fixture in `tests/conftest.py` to apply credential scrubbing globally for all snapshot tests.

**When to use:** When you need to apply consistent transforms (scrubbing) across all snapshot assertions.

```python
# Source: https://github.com/syrupy-project/syrupy/blob/main/tests/examples/test_custom_snapshot_directory.py
import pytest
from syrupy.extensions.amber import AmberSnapshotExtension

@pytest.fixture
def snapshot(snapshot):
    """Override snapshot fixture to apply credential scrubbing."""
    return snapshot.with_defaults(
        matcher=path_value(
            mapping={
                ".*password.*": r".*",
                ".*token.*": r".*",
                ".*secret.*": r".*",
            },
            replacer=lambda data, match: "[REDACTED]",
            types=(str,),
            regex=True,
        )
    )
```

**Important note:** For warehouse query results (rows of business data), credential fields will not appear in result data. The matcher pattern above is a defensive belt-and-suspenders approach.

### Pattern 3: Convert Result to Stable Serializable Form

**What:** Cubano `Result` objects contain `Row` objects with a custom `__repr__` (`Row(revenue=1000, country='US')`). Syrupy will use `__repr__` for serialization by default. Converting to `list[dict]` produces more readable, diff-friendly snapshots.

**When to use:** Always — prefer explicit `[dict(row) for row in result]` over raw `Result` object.

```python
def test_metric_aggregation(snapshot):
    result = SyntheticModel.query().metrics(SyntheticModel.revenue).execute()
    rows = [dict(row.items()) for row in result]  # stable dict form
    assert rows == snapshot
```

The `.ambr` output for a list of dicts looks like:
```
# serializer version: 1
# name: test_metric_aggregation
list([
  dict({
    'revenue': 1000,
    'country': 'US',
  }),
  dict({
    'revenue': 2000,
    'country': 'CA',
  }),
])
# ---
```

### Pattern 4: Excluding Non-Deterministic Fields

**What:** Use syrupy's `exclude` parameter with `props()` to omit fields that are timing-dependent or contain run-specific IDs.

**When to use:** If query results include timestamps, auto-incrementing IDs, or execution metadata (Phase context says to capture results only — no metadata — so this should not be needed for well-designed test queries).

```python
from syrupy.filters import props

def test_query_results(snapshot):
    rows = [dict(row.items()) for row in result]
    assert rows == snapshot(exclude=props("created_at", "updated_at"))
```

### Pattern 5: Credential Scrubbing via path_value

**What:** Replace any value matching a sensitive-looking pattern before snapshot storage.

**When to use:** When query results might inadvertently contain credential-like strings (e.g., a "token" dimension field in a test model).

```python
from syrupy.matchers import path_value

def test_query(snapshot):
    rows = [dict(row.items()) for row in result]
    assert rows == snapshot(
        matcher=path_value(
            mapping={"api_key": r".+"},
            replacer=lambda data, match: "[REDACTED]",
            types=(str,),
        )
    )
```

### Anti-Patterns to Avoid

- **Snapshotting raw `Result` objects:** Syrupy uses `__repr__` which produces `Row(field=value)` format. The snapshot becomes brittle to `__repr__` changes. Always convert to `list[dict]`.
- **Snapshotting with non-deterministic ordering:** Warehouse queries without `ORDER BY` may return rows in any order. Always use `.order_by()` in snapshot test queries or sort the result list before asserting.
- **Including row counts or execution time in snapshots:** Violates the locked decision to capture query results only. Keep snapshot assertions to data values.
- **Placing snapshot tests in the `cubano-jaffle-shop` workspace:** That workspace uses live jaffle-shop data which may change. Snapshot tests require a synthetic, isolated dataset.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Snapshot file format | Custom `.yaml` or `.json` serializer | syrupy Amber format | Handles all Python types, edge cases, None, Decimal, datetime |
| Missing snapshot detection | Custom file-existence check | syrupy's built-in | syrupy fails test with clear message automatically |
| Snapshot update workflow | Custom `--record` flag | `pytest --snapshot-update` | Standard flag, documented, expected by developers |
| Credential detection | Custom regex scanner | syrupy `path_value` matcher | Composable, path-aware, configurable |
| Snapshot comparison | Custom diff algorithm | syrupy's built-in diff | Already handles nested dicts, lists, type formatting |

**Key insight:** Syrupy handles all of the snapshot lifecycle. The implementation is primarily: (1) add dependency, (2) write tests using the fixture, (3) handle Result→dict conversion, (4) set up conftest override for scrubbing.

---

## Common Pitfalls

### Pitfall 1: Row Order Non-Determinism

**What goes wrong:** Test passes locally (warehouse happens to return rows in one order) but fails on re-record because warehouse returns a different order.

**Why it happens:** Warehouse query engines do not guarantee row order without `ORDER BY`. The `__snapshots__/test_module.ambr` stores rows in the order captured at record time.

**How to avoid:** Every snapshot test query MUST include `.order_by()` on a stable, unique field. For synthetic test data, design the test data to have a clear natural ordering.

**Warning signs:** Snapshot tests that pass sometimes and fail other times (flaky). Snapshot diffs showing only row reordering.

### Pitfall 2: Decimal/Float Precision Drift

**What goes wrong:** Numeric results from warehouse (e.g., `Decimal("45.50")`) serialize differently across Python versions or warehouse configurations (e.g., `45.5` vs `45.50`).

**Why it happens:** Amber format uses Python `repr()` for serialization. `Decimal("45.50")` and `Decimal("45.5")` have different reprs.

**How to avoid:** Use synthetic test data with clean integer or simple decimal values. Avoid floating-point fields in snapshot tests where possible. For Snowflake, ensure test view returns typed data consistently.

**Warning signs:** Snapshot failures showing trivial numeric differences like `45.5` vs `45.50`.

### Pitfall 3: Missing Snapshot Confusion in CI

**What goes wrong:** Developer adds a new snapshot test but forgets to run `pytest --snapshot-update` locally before committing. CI fails with "snapshot missing" error.

**Why it happens:** Syrupy fails immediately when snapshot file does not exist — this is by design (soundness guarantee). CI cannot run `--snapshot-update` (no warehouse credentials).

**How to avoid:** Developer workflow documentation must prominently state: always run `pytest --snapshot-update` locally before committing new snapshot tests. The CI error message "snapshot missing" provides the `--snapshot-update` hint.

**Warning signs:** CI failures with "AssertionError: snapshot missing" on a branch with new test files.

### Pitfall 4: Stale Snapshots After Query Refactor

**What goes wrong:** After a query API change or SQL generation change, existing snapshots no longer match. All snapshot tests fail simultaneously.

**Why it happens:** Snapshots capture exact query results. If the underlying SQL changes (even semantically equivalent changes), results may differ (column order, formatting, precision).

**How to avoid:** Treat a wave of snapshot failures as a signal to re-record. Run `pytest --snapshot-update` after any intentional SQL generation change, review the git diff to verify changes are expected, then commit.

**Warning signs:** Multiple snapshot test failures after a non-data-changing refactor.

### Pitfall 5: Row Object __repr__ in Snapshots

**What goes wrong:** Asserting `result == snapshot` directly (without converting to `list[dict]`) stores `Row(revenue=1000)` repr in the snapshot. Any change to `Row.__repr__` format invalidates all snapshots.

**Why it happens:** Syrupy uses `__repr__` for custom objects. Cubano's `Row` has a custom repr.

**How to avoid:** Always assert `[dict(row.items()) for row in result] == snapshot`. This decouples snapshot stability from `Row.__repr__` implementation.

**Warning signs:** Massive snapshot failures after any internal `Row` or `Result` refactor.

---

## Code Examples

Verified patterns from official sources and project codebase analysis:

### Adding syrupy to dev dependencies

```toml
# pyproject.toml — add to [dependency-groups].dev
[dependency-groups]
dev = [
    # ... existing ...
    "syrupy>=5.1.0",
]
```

### Synthetic SemanticView for snapshot tests

```python
# tests/test_snapshot_queries.py
from cubano import Dimension, Metric, SemanticView

class SnapshotSales(SemanticView, view="snapshot_sales_view"):
    """Isolated synthetic view for snapshot tests."""
    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()
```

### conftest.py snapshot fixture override

```python
# tests/conftest.py — add to existing conftest.py
import pytest
from syrupy.matchers import path_value, compose_matchers

@pytest.fixture
def snapshot(snapshot):
    """
    Override snapshot fixture with credential scrubbing.

    Redacts any string values at paths containing 'password', 'token',
    'secret', or 'key' — defensive scrubbing for warehouse query results.
    """
    return snapshot.with_defaults(
        matcher=compose_matchers(
            path_value(
                mapping={".*password.*": r".+"},
                replacer=lambda data, match: "[REDACTED]",
                types=(str,),
                regex=True,
            ),
            path_value(
                mapping={".*token.*": r".+"},
                replacer=lambda data, match: "[REDACTED]",
                types=(str,),
                regex=True,
            ),
        )
    )
```

**Note:** path_value with `regex=True` is verified in syrupy 5.x docs. The `mapping` key is the path regex, not the value regex. This approach scrubs values at sensitive-named paths.

**Alternative simpler scrubber** (if path_value regex proves complex):

```python
@pytest.fixture
def snapshot(snapshot):
    """Snapshot fixture — warehouse results contain no credentials by design."""
    return snapshot  # No-op: query result rows don't contain connection metadata
```

For this phase, since synthetic test data is controlled and results are business data rows (not connection metadata), the scrubbing may be a no-op in practice.

### Basic snapshot test

```python
def test_snowflake_metric_query(snapshot, snowflake_engine):
    """Snapshot: single metric query on Snowflake."""
    result = SnapshotSales.query().metrics(SnapshotSales.revenue).order_by(SnapshotSales.revenue).execute()
    rows = [dict(row.items()) for row in result]
    assert rows == snapshot
```

### Snapshot test with multi-metric aggregation

```python
def test_snowflake_metric_with_dimension(snapshot, snowflake_engine):
    """Snapshot: metric grouped by dimension."""
    result = (
        SnapshotSales.query()
        .metrics(SnapshotSales.revenue, SnapshotSales.cost)
        .dimensions(SnapshotSales.country)
        .order_by(SnapshotSales.country)
        .execute()
    )
    rows = [dict(row.items()) for row in result]
    assert rows == snapshot
```

### Engine fixture for snapshot tests

```python
# tests/conftest.py or tests/test_snapshot_queries.py
import pytest
import cubano
from cubano.engines.snowflake import SnowflakeEngine
from cubano.testing.credentials import CredentialError, SnowflakeCredentials

@pytest.fixture(scope="session")
def snowflake_snapshot_engine(snowflake_credentials):
    """
    Register SnowflakeEngine for snapshot tests.

    Uses existing snowflake_credentials fixture (session-scoped).
    If credentials unavailable, snapshot replay still works (no engine needed).
    """
    engine = SnowflakeEngine(
        account=snowflake_credentials.account,
        user=snowflake_credentials.user,
        password=snowflake_credentials.password.get_secret_value(),
        warehouse=snowflake_credentials.warehouse,
        database=snowflake_credentials.database,
    )
    cubano.register("snapshot", engine)
    yield engine
    cubano.unregister("snapshot")
```

**Key insight:** When running in CI without credentials, the `snowflake_credentials` fixture skips tests via `pytest.skip()`. But syrupy snapshot replay doesn't need warehouse credentials — it reads from `.ambr` files. This means snapshot replay tests need a different mechanism: they should not use `snowflake_credentials` at all when replaying.

This is the core architectural question: how do snapshot tests run in CI without needing the fixture that skips when credentials are absent?

**Resolution:** Snapshot tests in replay mode need to use a `MockEngine` loaded with the snapshot data, NOT the live SnowflakeEngine. However, the locked decision says to use syrupy's built-in behavior with `--snapshot-update` for recording. The actual query is executed against the warehouse only during recording; in CI, the test asserts `[dict(row.items()) for row in result] == snapshot` — but `result` still needs to come from somewhere.

**Correct interpretation:** In CI, snapshot tests that require warehouse credentials will be skipped (same as today's `@pytest.mark.warehouse` tests). The CI benefit is that the snapshots can be compared in unit test mode using a MockEngine loaded with the same synthetic data. OR: snapshot tests always run against the warehouse (skipped in CI if no creds) but the `.ambr` files serve as documentation of expected results.

**Clarification needed:** The requirement says "enable real warehouse testing in CI without cost." The mechanism is: snapshot tests run against real warehouse ONCE (locally, on `--snapshot-update`), snapshots are committed. In CI, these same tests would need to run without the warehouse. This requires either:

1. The snapshot tests use `MockEngine` in CI (loaded with same synthetic data), OR
2. The snapshot tests are warehouse-only and CI just verifies the `.ambr` files exist (no re-execution in CI)

Given the context that Phase 8 established `@pytest.mark.warehouse` for tests requiring live connections, the Phase 12 pattern is likely option (2) enhanced: snapshot tests are marked as unit tests in CI because they assert against committed `.ambr` files without a warehouse connection — but that requires the query to still execute somehow.

**Most likely correct model:** The snapshot tests run ONLY with `--snapshot-update` (against real warehouse) to create/update `.ambr` files. In CI, snapshot files are present and the test asserts that the current snapshot result matches stored snapshot. This requires the CI to also execute the query — unless we use a MockEngine approach.

This is the critical design gap to resolve during planning. Research supports both patterns are feasible.

---

## Fixture Implementation Pattern

### Syrupy's AssertionSnapshot Interface

From official docs and deepwiki (HIGH confidence):

```python
# The snapshot fixture type is SnapshotAssertion
# Key methods (all return modified SnapshotAssertion for chaining):
snapshot(
    extension_class=...,   # override serializer
    matcher=...,           # transform values before comparison
    exclude=...,           # filter out fields
    include=...,           # keep only specific fields
    name=...,              # custom snapshot name (default: test function name)
)
snapshot.with_defaults(...)   # apply defaults that persist across assertions
snapshot.use_extension(...)   # switch extension class
```

### Missing Snapshot Behavior

- **Error:** "AssertionError: snapshot missing" (verified via syrupy GitHub issues and docs)
- **Next step hint:** The output tells developers to run `pytest --snapshot-update`
- **Behavior:** Test FAILS, not skips. This is a conscious design choice by syrupy to enforce soundness.

### Recording Mode Lifecycle

```
# Developer workflow:
pytest --snapshot-update              # Creates/updates __snapshots__/*.ambr
git add tests/__snapshots__/         # Commit snapshot files
git commit -m "feat: add snapshot tests"

# CI workflow:
pytest tests/                         # Reads from committed .ambr files, asserts match
# If snapshots not committed → "snapshot missing" → CI fails → developer fix needed
```

### Stale Snapshot Detection

Syrupy detects stale snapshots (stored snapshots with no matching test) and:
- Warns with `--snapshot-warn-unused`
- Fails with default behavior

Use `--snapshot-warn-unused` in CI to prevent stale snapshot buildup becoming an error.

---

## Sample Test Patterns for Phase Scope

### Snowflake-Specific Patterns

Snowflake uses `AGG()` syntax for metrics. The generated SQL for a snapshot test looks like:
```sql
SELECT AGG("revenue"), "country" FROM "snapshot_sales_view" GROUP BY "country" ORDER BY "country"
```

Tests to cover:
1. Single metric (basic AGG validation)
2. Multiple metrics (multi-AGG)
3. Metric + dimension grouping (GROUP BY)
4. Dimension-only (no AGG, just SELECT)
5. Filtered metric (WHERE clause)
6. Ordered result (ORDER BY for deterministic snapshot)

### Databricks-Specific Patterns

Databricks uses `MEASURE()` syntax. The generated SQL:
```sql
SELECT MEASURE(`revenue`), `country` FROM `snapshot_sales_view` GROUP BY `country` ORDER BY `country`
```

Tests cover same patterns but validate `MEASURE()` generates correct results.

**Compatibility focus:** The primary goal is not to compare Snowflake vs Databricks results to each other, but to verify each backend executes correctly and returns semantically expected results. The snapshot for Snowflake and Databricks tests can differ (different aggregation semantics) — what matters is each is stable and correct.

### Model Relationship Patterns

Cubano does not yet support JOINs (each query targets one SemanticView). "Model relationships" in this phase context means: queries that involve multiple metrics and dimensions from the same model (complex multi-field queries), not cross-model queries.

Example: Query that groups `revenue` and `cost` by `country` and `region` simultaneously.

### Edge Cases Benefiting from Snapshot Comparison

1. **NULL handling:** Synthetic data includes a NULL dimension value; snapshot verifies NULL appears as `None` in results consistently
2. **Decimal precision:** Synthetic data with `Decimal("100.00")` verifies precision is stable in results
3. **Empty string dimensions:** Verifies empty strings serialize consistently
4. **Boolean dimensions:** Verifies `True`/`False` serialize consistently
5. **Integer vs Decimal distinction:** Some warehouses return integers as floats

---

## Integration with Existing Test Infrastructure

### Layering on Phase 8 Fixtures

Phase 8 established:
- `snowflake_credentials` (session-scoped, skips if missing)
- `databricks_credentials` (session-scoped, skips if missing)
- `snowflake_connection` (session-scoped, creates test schema)
- `databricks_connection` (session-scoped, creates test schema)
- `test_schema_name` (worker-specific isolation)

Phase 12 snapshot tests need:
- A lightweight engine fixture that registers SnowflakeEngine/DatabricksEngine without schema creation (snapshot tests use their own synthetic view)
- OR: reuse existing Phase 8 `snowflake_connection` and create the synthetic view within that schema

**Recommended:** Create a new `snowflake_snapshot_engine` fixture that uses `snowflake_credentials` but skips schema creation (snapshot tests query a pre-existing view, not a created-at-test-time schema).

### CI Configuration for Snapshot Tests

Current CI structure (from `ci.yml`):
```yaml
- name: Run unit tests
  run: uv run pytest tests/ -n auto -v
- name: Run doctests
  run: uv run pytest src/ --doctest-modules -v
```

Snapshot tests in `tests/test_snapshot_queries.py` will run automatically as part of `pytest tests/`. In CI without warehouse credentials:

- Tests using `snowflake_credentials` fixture will be skipped (existing behavior from Phase 8)
- The snapshot `.ambr` files are committed, so no "snapshot missing" errors
- `pytest --snapshot-warn-unused` is recommended in CI to catch stale snapshots without failing

**CI command update needed:**
```yaml
- name: Run unit tests
  run: uv run pytest tests/ -n auto -v --snapshot-warn-unused
```

### Developer Workflow

```bash
# Step 1: Record snapshots (first time, or after warehouse changes)
# Requires warehouse credentials in environment
uv run pytest tests/test_snapshot_queries.py --snapshot-update

# Step 2: Verify snapshots look correct
git diff tests/__snapshots__/

# Step 3: Commit snapshots
git add tests/__snapshots__/
git commit -m "feat(12): add warehouse query snapshots"

# Step 4: Ongoing CI replay (no credentials needed if using MockEngine in replay)
uv run pytest tests/test_snapshot_queries.py
```

---

## Implementation Risks & Mitigations

### Risk 1: Snapshot Drift

**Description:** Over time, as warehouse schema, data, or SQL generation evolves, snapshots become out of date.

**Detection:** `pytest --snapshot-update` in a PR shows unexpected diff; or test failures in CI.

**Re-recording cadence:** Re-record when:
- SQL generation changes (any engine or dialect change)
- Synthetic test data changes
- Warehouse behavior changes (e.g., Snowflake AGG semantics update)

**Mitigation:** Document in developer guide that snapshot diffs in PRs are a required review artifact. Any snapshot change must be intentional and reviewed.

**Audit approach:** `git diff HEAD~1 tests/__snapshots__/` in PR review. syrupy's Amber format is designed to be readable in diffs.

**Deprecation approach:** When removing a test, run `pytest --snapshot-update` to let syrupy delete the orphaned snapshot. Or manually delete the relevant `# name: ...` block from `.ambr` file.

### Risk 2: Secrets in Results

**Description:** Warehouse query results accidentally contain credential-like strings.

**Likelihood:** LOW. Query results are business data rows. Connection parameters, tokens, and passwords are not returned as query result columns.

**Mitigation:**
1. Synthetic test data is controlled — no credential-like values in test data
2. Defensive `path_value` matcher in `conftest.py` scrubs any field named `password`, `token`, `secret`, `key`
3. Pre-commit hook or CI check to scan `.ambr` files for common credential patterns (optional, LOW priority)

**Scrubbing strategy:** Implement at conftest.py level so scrubbing applies to all snapshot assertions transparently. Developers writing new tests don't need to think about it.

### Risk 3: Large Snapshots

**Description:** Queries returning many rows produce large `.ambr` files, causing slow diffs and git bloat.

**Likelihood:** MEDIUM. Without `LIMIT`, warehouse queries can return thousands of rows.

**Mitigation:**
1. All snapshot test queries MUST include `.limit(N)` with a small N (recommend N ≤ 20 for snapshots)
2. Design synthetic test data to have exactly the rows needed (not hundreds)
3. Keep synthetic dataset to ≤ 10 rows per view

**Performance of comparison:** syrupy loads the entire `.ambr` file for comparison. Files under 1MB are fast. With ≤ 20 rows × ≤ 10 fields = trivial.

### Risk 4: Replay Without Warehouse (The CI Gap)

**Description:** The fundamental tension: snapshot tests need to produce a `result` object to assert against the snapshot, but in CI there's no warehouse.

**Resolution options:**

**Option A: MockEngine with Synthetic Data (Recommended)**
- Snapshot tests have two modes: record (against real warehouse) and replay (against MockEngine)
- The MockEngine is loaded with the same synthetic data that was in the warehouse when snapshots were recorded
- Assertions `assert [dict(row.items()) for row in result] == snapshot` compare MockEngine results to stored snapshots
- CI always uses MockEngine; warehouse connection only used with `--snapshot-update`
- This is the cleanest pattern for zero-cost CI

**Option B: Warehouse-Only Snapshot Tests (Simpler but No CI Benefit)**
- Snapshot tests always require warehouse, skipped in CI
- `.ambr` files serve as documentation only
- CI benefit: none (same as existing warehouse tests)
- Does not satisfy "enable real warehouse testing in CI without cost"

**Option A is the correct interpretation of the requirement.** The synthetic dataset in MockEngine is the "recorded" warehouse state. The snapshot captures what the warehouse returned for that data. CI verifies the query logic (SQL generation + result mapping) produces the same output against MockEngine.

**Implementation:**
```python
@pytest.fixture
def snapshot_engine(request):
    """MockEngine for snapshot replay; SnowflakeEngine when --snapshot-update."""
    if request.config.getoption("--snapshot-update", default=False):
        # Use real warehouse for recording
        creds = SnowflakeCredentials.load()
        engine = SnowflakeEngine(...)
    else:
        # Use MockEngine for replay
        engine = MockEngine()
        engine.load("snapshot_sales_view", SNAPSHOT_TEST_DATA)
    cubano.register("default", engine)
    yield engine
    cubano.unregister("default")
```

**Critical issue with Option A:** The MockEngine result may differ from warehouse result (MockEngine may not implement exact same aggregation semantics). The snapshot must be recorded against the warehouse but replayed against the MockEngine with the same raw data. If MockEngine and warehouse agree on the result, the snapshot is valid for both. If they differ, the snapshot strategy needs reconsideration.

**Recommendation:** Record against warehouse, verify MockEngine produces same result with same data, only then commit snapshot. This validates SQL compatibility and result mapping simultaneously.

---

## Open Questions

1. **CI Replay Mechanism**
   - What we know: Tests need `result` to compare against snapshot
   - What's unclear: Whether the decision is Option A (MockEngine replay) or Option B (warehouse-only, skipped in CI)
   - Recommendation: Confirm with user which interpretation of "enable warehouse testing in CI without cost" is intended. Option A requires MockEngine to produce identical results to warehouse for the snapshot to be meaningful.

2. **Synthetic View Creation**
   - What we know: Tests need a view named `snapshot_sales_view` (or similar) to exist on Snowflake/Databricks
   - What's unclear: Does Phase 12 create the view programmatically (DDL in fixture), or does it rely on an existing view?
   - Recommendation: Create view in fixture setup using the existing Phase 8 `snowflake_connection` + `test_schema_name` pattern. The fixture creates the view, loads synthetic data via INSERT, tests run, fixture drops the view.

3. **Multi-Backend Snapshot Files**
   - What we know: Snowflake and Databricks may return slightly different result types (e.g., Decimal vs float precision)
   - What's unclear: Should there be separate snapshot files per backend or a single shared snapshot?
   - Recommendation: Single snapshot per test, but tests are parameterized by backend. Separate test functions for Snowflake vs Databricks allow separate `.ambr` entries.

---

## Sources

### Primary (HIGH confidence)

- `https://syrupy-project.github.io/syrupy/` — Official docs: fixture API, --snapshot-update, file format
- `https://github.com/syrupy-project/syrupy` (README.md) — Matchers API, path_type, path_value, props, paths
- `https://pypi.org/project/syrupy/` — Version 5.1.0 (released 2026-01-25), Python >=3.10, pytest >=8
- `https://github.com/syrupy-project/syrupy/blob/main/CHANGELOG.md` — 5.0 breaking changes: Python 3.10 min, DataSerializer→AmberDataSerializer rename, MIT license
- `https://github.com/syrupy-project/syrupy/blob/main/tests/examples/test_custom_snapshot_directory.py` — Pattern for custom extension override in conftest.py
- `https://deepwiki.com/syrupy-project/syrupy/2-user-guide` — AssertionSnapshot interface, use_extension/with_defaults, error messages
- `/Users/paul/Documents/Dev/Personal/cubano/tests/conftest.py` — Existing Phase 8 fixtures (snowflake_credentials, databricks_credentials, snowflake_connection, databricks_connection)
- `/Users/paul/Documents/Dev/Personal/cubano/pyproject.toml` — Current dev deps, pytest config, markers
- `/Users/paul/Documents/Dev/Personal/cubano/.github/workflows/ci.yml` — Current CI structure

### Secondary (MEDIUM confidence)

- `https://til.simonwillison.net/pytest/syrupy` — Practical usage patterns, `.ambr` format examples
- `https://github.com/syrupy-project/syrupy/issues/843` — Confirms missing snapshots cause test failure (not skip)

### Tertiary (LOW confidence)

- WebSearch results on credential scrubbing patterns — general practice, not syrupy-specific

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — syrupy 5.1.0 verified on PyPI, API verified in official docs
- Architecture: HIGH for syrupy patterns; MEDIUM for CI replay mechanism (open question on Option A vs B)
- Pitfalls: HIGH for row ordering and repr issues (verified from docs and existing codebase analysis); MEDIUM for Decimal precision (inferred from Python behavior)
- Open questions: CI replay mechanism and synthetic view creation approach need planning decisions

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (syrupy 5.x is stable; unlikely to change in 30 days)
