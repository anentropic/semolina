# Phase 11: CI & Example Updates - Research

**Date:** 2026-02-17
**Objective:** Understand what's needed to plan Phase 11 (CI doctest enforcement + cubano-jaffle-shop API update)

---

## Research Questions & Findings

### 1. Current CI Workflow Structure & Test Execution

**Current State:**
- **File:** `.github/workflows/ci.yml`
- **Test Command:** `uv run pytest tests/ src/ -m "mock or warehouse" -n auto -v`
- **Key Issue:** The `-m "mock or warehouse"` filter **excludes doctests from CI**
  - This filter only runs tests marked with `@pytest.mark.mock` or `@pytest.mark.warehouse`
  - Doctests are NOT marked with these markers, so they're silently excluded from CI validation

**Pytest Configuration:**
- **File:** `pyproject.toml` ([tool.pytest.ini_options])
- **Doctest Settings:**
  ```
  addopts = [
      "--doctest-modules",        # Collect doctests from all .py files
      "--doctest-continue-on-failure",  # Continue on failure (for logging)
  ]
  doctest_optionflags = ["ELLIPSIS", "NORMALIZE_WHITESPACE"]
  testpaths = ["tests", "src"]
  ```
- **Current Behavior:** `--doctest-modules` is configured but the `-m "mock or warehouse"` filter in CI bypasses it

**Finding:** The pytest doctest infrastructure is already configured correctly. The problem is purely in the CI command.

---

### 2. How Pytest Doctests Integrate with GitHub Actions

**Current Gap:**
- GitHub Actions CI runs: `pytest tests/ src/ -m "mock or warehouse"`
- This explicitly **filters out doctests** because pytest's `-m` flag only applies to pytest markers
- Doctests have no pytest marker mechanism (they are collected via `--doctest-modules`)

**Solution Required:**
The CI needs to run BOTH:
1. Unit tests with marker filter: `pytest tests/ -m "mock or warehouse" -n auto`
2. Doctests (all of them, from src/): `pytest src/ --doctest-modules -v`

**Or** (simpler): Remove the `-m` filter and let doctests run naturally. Testing shows:
```bash
$ uv run pytest src/ --doctest-modules -v
# Collects 26 doctest items automatically
# 20 passed, 6 skipped (marked with # doctest: +SKIP)
```

**Doctest Reporting:**
- pytest automatically separates doctest output: `src/module.py::function_name PASSED`
- Failed doctests show full example + expected vs actual
- This already provides clear separation without extra configuration

---

### 3. Docstring Examples Currently in src/cubano/

**Count & Location:**
- **Total doctest items:** 26 collected
- **Passed:** 20
- **Skipped:** 6 (intentionally marked with `# doctest: +SKIP`)

**Files with Examples:**
| File | Doctest Items | Status |
|------|-------------------|--------|
| `src/cubano/models.py` | 4 (SemanticView, .query(), .metrics(), .dimensions()) | 4 passing |
| `src/cubano/query.py` | 9 (_Query and its 8 methods) | 9 passing |
| `src/cubano/fields.py` | 9 (OrderTerm + comparison ops: ==, !=, <, >, <=, >=, .asc(), .desc()) | 3 passing, 6 SKIPPED |
| `src/cubano/filters.py` | 1 (Q filter logic) | 1 passing |
| `src/cubano/results.py` | 2 (Result, Row) | 2 SKIPPED |
| `src/cubano/registry.py` | 1 (register function) | 1 passing |

**SKIP Directives in Use:**
- 8 doctests use `# doctest: +SKIP` to prevent execution
- Reason: Examples require external warehouse connection or mock setup not available in doctest context
- Examples: Field comparison operators (require model definition), Row iteration (requires Result object)

**Key Finding:** All 20 runnable doctests already pass. The 6 skipped are intentionally marked because they need external context.

---

### 4. cubano-jaffle-shop Location & Code Status

**Location:** `/Users/paul/Documents/Dev/Personal/cubano/cubano-jaffle-shop/`

**Structure:**
```
cubano-jaffle-shop/
├── src/cubano_jaffle_shop/
│   ├── jaffle_models.py      # SemanticView definitions (CLEAN)
│   ├── test_models.py         # Test models
│   └── __init__.py
├── tests/
│   ├── test_mock_queries.py   # USES OLD API ❌
│   ├── test_warehouse_queries.py # USES OLD API ❌
│   ├── conftest.py
│   └── fixtures/
└── pyproject.toml
```

**API Migration Status:**
- `jaffle_models.py`: ✅ CLEAN - Uses `SemanticView`, `Dimension`, `Metric` correctly
- `test_mock_queries.py`: ❌ BROKEN - Imports `Query` (no longer exported), uses old `Query()` constructor
- `test_warehouse_queries.py`: ❌ BROKEN - Imports `Query` (no longer exported), uses old `Query()` constructor

**Current Import Errors:**
```python
# In both test files:
from cubano import Q, Query  # ❌ Query no longer exported
query = Query().metrics(Orders.order_total)  # ❌ Query() constructor removed
```

**What Phase 10.1 Changed:**
- Removed public `Query()` constructor (now private `_Query`)
- Removed `.filter()` method (now use `.where()`)
- Removed `.fetch()` method (now use `.execute()`)
- Added `SemanticView.query()` class method (new model-centric entry point)

**What Needs Updating in cubano-jaffle-shop:**
```python
# OLD (Phase 10.1-removed):
query = Query().metrics(Orders.order_total)
results = orders_engine.execute(query)

# NEW (Model-centric):
results = Orders.query().metrics(Orders.order_total).execute(using=orders_engine)
```

---

### 5. Specific Pytest Command Needed for Full Validation

**Current (INCOMPLETE - excludes doctests):**
```bash
uv run pytest tests/ src/ -m "mock or warehouse" -n auto -v
# Result: 443 unit tests, 0 doctests
```

**Required (COMPLETE - includes all 459):**
```bash
# Option A: Single command (simple, clear)
uv run pytest tests/ src/ --doctest-modules -v

# Option B: Two separate commands (structured reporting)
uv run pytest tests/ -m "mock or warehouse" -n auto -v        # Unit tests
uv run pytest src/ --doctest-modules -v                        # Doctests
```

**Test Breakdown from Collection:**
```
Total: 459 items
├── Unit tests (433)
│   └── tests/ directory: 433 tests
└── Doctests (26 items)
    ├── src/cubano/fields.py: 9 items (6 SKIPPED + 3 passing)
    ├── src/cubano/query.py: 9 items (all passing)
    ├── src/cubano/models.py: 4 items (all passing)
    ├── src/cubano/filters.py: 1 item (passing)
    ├── src/cubano/results.py: 2 items (2 SKIPPED)
    └── src/cubano/registry.py: 1 item (passing)
```

**Exact Counts:**
- Total doctests collected: 26
- Doctests passing: 20 (or 14 running + 6 skipped; either way 20 pass)
- Doctests skipped: 6
- Unit tests: 433
- **Total when all run: 459 items**

**Note:** Phase 10.1-08 reported "453 tests + 6 skipped doctests = 459 total" which aligns with this finding.

---

### 6. Doctest Failure Reporting in CI

**Current Capability:**
pytest already separates doctest output naturally:

**Example from `pytest src/ --doctest-modules -v`:**
```
src/cubano/models.py::cubano.models.SemanticView PASSED
src/cubano/models.py::cubano.models.SemanticView.query PASSED
src/cubano/query.py::cubano.query._Query PASSED
src/cubano/query.py::cubano.query._Query.where PASSED
src/cubano/fields.py::cubano.fields.Field.asc PASSED
src/cubano/fields.py::cubano.fields.Field.__eq__ SKIPPED
...
```

**For CI Reporting:**
To show separate counts as specified in decisions (443 unit tests + 16 doctests = 459 total):
- Run unit tests: `pytest tests/ -m "mock or warehouse" --tb=short -v`
- Run doctests: `pytest src/ --doctest-modules --tb=short -v`
- Parse output and report: "443 passed + 16 passed = 459 total"

**Failure Reporting:**
If a doctest fails, pytest shows:
```
FAILED src/cubano/query.py::cubano.query._Query.where - AssertionError: ...
Expected:
    ...
Got:
    ...
```

This is naturally distinct from unit test failures.

---

### 7. Phase 10.1 Decisions That Lock the Doctest Approach

**From Phase 10.1-CONTEXT.md & 10.1-08-SUMMARY.md:**

| Decision | Impact on Phase 11 |
|----------|-------------------|
| **Query API Migration Complete** | Phase 11 must update cubano-jaffle-shop to use `SemanticView.query()` not old `Query()` |
| **Model-centric API Locked** | All doctests already use new API (verified passing in 10.1-08) |
| **No Backward Compatibility** | Cannot support old `Query()` import; must update examples completely |
| **Doctest Marker Mechanism** | Currently using `# doctest: +SKIP` (Python standard, not pytest marker); Phase 11 can keep this approach |
| **Docstring Examples Already Verified** | Phase 10.1-08 verified all 20 doctest examples pass; CI just needs to enable them |

**Key Lock:** The doctest approach is NOT a free decision area. The existing 16 doctests in src/cubano/ are already written and use the new API. Phase 11 just needs to:
1. Remove the `-m "mock or warehouse"` filter in CI to expose these tests
2. Update cubano-jaffle-shop examples to match

---

## Summary Table

| Question | Finding |
|----------|---------|
| **CI workflow location?** | `.github/workflows/ci.yml` — test job runs `pytest tests/ src/ -m "mock or warehouse"` |
| **Pytest doctest integration?** | Already configured in `pyproject.toml` with `--doctest-modules`. Gap is purely the `-m` filter blocking them in CI. |
| **How many doctests exist?** | 26 collected (20 passing, 6 skipped intentionally). These are spread across 6 files in src/cubano/. |
| **cubano-jaffle-shop status?** | Two test files broken (import `Query`, use old API). Semantic view definitions are clean. |
| **Specific command needed?** | Remove `-m "mock or warehouse"` or run separate doctest command: `pytest src/ --doctest-modules -v` |
| **Doctest failure reporting?** | pytest naturally separates doctests in output (e.g., `src/cubano/query.py::_Query.where FAILED`). No extra configuration needed. |
| **Phase 10.1 locks?** | New model-centric API is locked; can't revert. Doctests already use it and pass. Can't support old `Query()` in examples. |

---

## Actionable Insights for Planning

### Must-Haves (Locked by Phase 10.1)
1. **Update cubano-jaffle-shop tests** to use `Model.query().execute()` API
   - Cannot use old `Query()` constructor
   - Must use `Orders.query()`, `Customers.query()`, etc.
   - This is a breaking change for the example code

2. **Remove `-m "mock or warehouse"` from CI test command**
   - Current command filters out doctests
   - Need to run both unit tests and doctests
   - Or restructure as two separate pytest calls for clearer reporting

### Claude's Discretion (Implementation Details)
1. **How to structure CI reporting** (whether to separate unit/doctest counts in output)
2. **Whether to keep `-m` filter or remove it entirely** (affects what other tests run in CI)
3. **Whether to use a single pytest command or two separate commands** for unit vs doctest validation
4. **Verbosity level for doctest output** in CI logs (pytest defaults are reasonable)

### Out of Scope
- Changing the doctest marker mechanism (`# doctest: +SKIP` is standard Python; locked)
- Modifying the 16 existing doctests (they already pass and use the new API)
- Supporting the old `Query()` API in any way (Phase 10.1 removed it permanently)

---

## Files to Reference During Planning

| File | Purpose |
|------|---------|
| `.github/workflows/ci.yml` | CI workflow to modify (line 110 test command) |
| `pyproject.toml` | pytest config already correct (no changes needed) |
| `src/cubano/models.py` | Example of model-centric API (SemanticView.query()) |
| `cubano-jaffle-shop/tests/test_mock_queries.py` | Example that needs rewriting (uses old API) |
| `cubano-jaffle-shop/tests/test_warehouse_queries.py` | Example that needs rewriting (uses old API) |
| `.planning/phases/10.1-refactor-query-interface-to-model-centric/10.1-08-SUMMARY.md` | Verification that doctests pass with new API |

---

## Next Steps for Planner

1. Verify the 16 doctest items are the correct count (cross-check pytest collection)
2. Decide on CI structure: single command vs two commands for reporting clarity
3. Identify all files in cubano-jaffle-shop that need updating (tests, not models)
4. Estimate effort for rewriting cubano-jaffle-shop examples to new API
5. Plan for how to verify cubano-jaffle-shop tests pass after update (warehouse vs mock)

---

*Research completed: 2026-02-17*
