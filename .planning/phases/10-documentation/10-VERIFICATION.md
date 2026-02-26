---
phase: 10-documentation
verified: 2026-02-17T14:00:00Z
status: gaps_found
score: 13/14 must-haves verified
re_verification: false
gaps:
  - truth: "CI test job runs doctests from `src/` in addition to `tests/` — broken docstring examples fail CI"
    status: failed
    reason: "ci.yml test step runs `pytest tests/ src/ -m 'mock or warehouse'` but 0 of 377 collected tests have `mock` or `warehouse` markers, so the command runs 0 tests including 0 doctests. Docstring example breakage is NOT enforced in CI."
    artifacts:
      - path: ".github/workflows/ci.yml"
        issue: "Line 110: `uv run pytest tests/ src/ -m \"mock or warehouse\" -n auto -v` deselects all 377 tests because none are marked `mock` or `warehouse`. The 16 doctests from src/ also have no markers and are therefore excluded."
    missing:
      - "Remove or replace the `-m 'mock or warehouse'` marker filter in the CI test step. Options: (1) drop the marker filter entirely — run all tests including doctests; (2) change to `-m 'not warehouse'` to skip real warehouse tests while running everything else; (3) add a separate `pytest src/ --doctest-modules` step without marker filtering. The simplest fix is to remove `-m \"mock or warehouse\"` from the pytest command, or change it to `-m \"not warehouse\"` so that all non-warehouse tests (including doctests) run unconditionally."
human_verification:
  - test: "Browse the docs site locally"
    expected: "Run `uv run --group docs mkdocs serve` and open http://localhost:8000. Verify: Material theme loads with dark/light mode toggle; card grid on landing page; sidebar has Home, Getting Started, Guides, API Reference sections; API reference pages rendered for cubano.query, cubano.fields, etc."
    why_human: "Site visual appearance and interactive theme behavior cannot be verified programmatically"
  - test: "Verify DocSearch Algolia integration (optional)"
    expected: "If DOCSEARCH_APP_ID and DOCSEARCH_API_KEY secrets are configured in GitHub, the docs.yml workflow should use Algolia search. If not set, mkdocs.yml gracefully falls back to standard search."
    why_human: "External service integration depends on secret configuration that cannot be verified locally"
  - test: "Verify GitHub Pages deployment (requires push to main)"
    expected: "After a push to main, GitHub Actions should run the docs.yml workflow, build docs, and deploy to https://anentropic.github.io/cubano/"
    why_human: "Requires actual GitHub Actions run and GitHub Pages setup (Settings > Pages > Source = GitHub Actions)"
---

# Phase 10: Documentation Verification Report

**Phase Goal:** Users can learn Cubano concepts and reference the API with executable, tested examples
**Verified:** 2026-02-17
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Getting started guide walks through install, model definition, and first query with working example | VERIFIED | `docs/guides/installation.md` (87 lines), `docs/guides/first-query.md` (136 lines) — full content, cross-linked, working code examples |
| 2 | API reference is auto-generated from docstrings via mkdocstrings and browsable locally | VERIFIED | `scripts/gen_ref_pages.py` generates reference pages via gen-files plugin; `mkdocs build --strict` exits 0; `site/reference/cubano/` contains 10 module groups |
| 3 | Code examples in docstrings are validated with doctest; docs build fails if examples break | PARTIAL | 16 doctests all pass locally (`uv run pytest src/ --doctest-modules`). However the CI command (`pytest tests/ src/ -m "mock or warehouse"`) deselects all 377 tests including doctests — so CI does NOT enforce doctest correctness |
| 4 | Docs build automatically on push to main and deploy to GitHub Pages | VERIFIED | `.github/workflows/docs.yml` triggers on push to main with two-job build+deploy; uses `actions/deploy-pages@v4`; `mkdocs build --strict` is the build command |

**Score:** 3/4 success criteria verified (truth 3 partially fails due to CI gap)

### Required Artifacts

#### Plan 10-01 (DOCS-02, DOCS-06, DOCS-07)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `mkdocs.yml` | MkDocs config with Material theme, plugins, nav | VERIFIED | Full config: Material theme dark/light, 5 plugins (search, gen-files, literate-nav, section-index, mkdocstrings), complete nav structure |
| `docs/index.md` | Landing page with card grid | VERIFIED | 59 lines, grid cards linking to Getting Started, Models, Queries, API Reference; working code example |
| `scripts/gen_ref_pages.py` | Auto-generates API reference from src/ | VERIFIED | Uses mkdocs_gen_files; generates reference SUMMARY.md; skips private/conftest modules |
| `pyproject.toml` | docs dependency group with mkdocs stack | VERIFIED | `[dependency-groups] docs` with mkdocs>=1.6.0, mkdocs-material>=9.7.0, mkdocstrings, gen-files, literate-nav, section-index |

#### Plan 10-02 (DOCS-10)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/cubano/conftest.py` | autouse doctest_namespace fixture with MockEngine | VERIFIED | 84 lines; `doctest_setup` fixture with autouse=True; injects Sales, Query, Q, mock_engine, cubano, SemanticView, Metric, Dimension, Fact, NullsOrdering; yield-based cleanup unregisters engine |
| `pyproject.toml` | --doctest-modules in addopts, src in testpaths | VERIFIED | `addopts = ["--doctest-modules", "--doctest-continue-on-failure"]`; `testpaths = ["tests", "src"]`; `doctest_optionflags = ["ELLIPSIS", "NORMALIZE_WHITESPACE"]` |

#### Plan 10-03 (DOCS-01, DOCS-03, DOCS-04, DOCS-05)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docs/guides/installation.md` | Install with extras | VERIFIED | 87 lines; pip/uv tabs, snowflake/databricks extras, verify command, CLI note |
| `docs/guides/first-query.md` | 5-minute walkthrough | VERIFIED | 136 lines; 5-step walkthrough (model → engine → query → fetch → Row access), full code example with MockEngine |
| `docs/guides/models.md` | SemanticView, Metric, Dimension, Fact | VERIFIED | 127 lines; all three field types with comparison table, descriptor protocol, immutability |
| `docs/guides/queries.md` | All 8 Query methods | VERIFIED | 191 lines; all 8 methods (metrics, dimensions, filter, order_by, limit, using, fetch, to_sql), immutable chaining pattern |
| `docs/guides/filtering.md` | Q-objects with AND/OR/NOT and precedence warning | VERIFIED | 157 lines; 9 lookup operators in table, OR/AND/NOT composition, `!!! warning` on operator precedence |
| `docs/guides/ordering.md` | order_by, asc, desc, NullsOrdering, limit | VERIFIED | 137 lines; asc()/desc(), NullsOrdering table, multi-field ordering, limit() combination |
| `docs/guides/backends/overview.md` | Snowflake vs Databricks comparison table | VERIFIED | 108 lines; 6-column comparison table, unified API demo, tabbed SQL showing AGG() vs MEASURE() |
| `docs/guides/backends/snowflake.md` | SnowflakeEngine, credentials, AGG() syntax | VERIFIED | 155 lines; connection params table, SnowflakeCredentials.load() pattern, env vars, codegen output |
| `docs/guides/backends/databricks.md` | DatabricksEngine, Unity Catalog, MEASURE() | VERIFIED | 164 lines; connection params, DatabricksCredentials, Unity Catalog three-part names, codegen output |
| `docs/guides/codegen.md` | cubano codegen CLI usage with examples | VERIFIED | 175 lines; all CLI options table, tabbed Snowflake/Databricks output, TODO placeholder explanations |

#### Plan 10-04 (DOCS-08, DOCS-09)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.github/workflows/docs.yml` | Docs build+deploy on push to main | VERIFIED | 65 lines; two-job pattern (build → deploy); triggers on push to main + workflow_dispatch; `mkdocs build --strict`; `actions/upload-pages-artifact@v3`; `actions/deploy-pages@v4`; least-privilege permissions (pages: write, id-token: write) |
| `.github/workflows/ci.yml` | CI test step includes src/ doctest discovery | PARTIAL | Step renamed to "Run pytest (Cubano + doctests)" and `src/` added. HOWEVER: `-m "mock or warehouse"` deselects ALL 377 collected tests (including doctests) because none have these markers. Net result: 0 tests run, breaking the purpose of the change. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `scripts/gen_ref_pages.py` | `docs/reference/` (virtual) | `mkdocs-gen-files plugin` | VERIFIED | `mkdocs_gen_files.open` call present; gen-files plugin lists script in mkdocs.yml |
| `mkdocs.yml plugins.gen-files` | `scripts/gen_ref_pages.py` | scripts list in gen-files config | VERIFIED | `scripts: - scripts/gen_ref_pages.py` in mkdocs.yml |
| `mkdocs.yml plugins.literate-nav` | `docs/reference/SUMMARY.md` | nav_file: SUMMARY.md | VERIFIED | `nav_file: SUMMARY.md` in mkdocs.yml literate-nav config; gen_ref_pages.py writes `reference/SUMMARY.md` |
| `src/cubano/conftest.py` | pytest doctest discovery | conftest.py in src/cubano/ tree | VERIFIED | Confirmed by `uv run pytest src/ --doctest-modules --collect-only` showing 16 DoctestItems |
| `doctest_setup fixture` | `cubano.registry` | register() at start, unregister() after yield | VERIFIED | `register("default", engine)` then `yield` then `unregister("default")` — cleanup pattern correct |
| `.github/workflows/docs.yml build job` | `actions/upload-pages-artifact` | site/ directory from mkdocs build | VERIFIED | `uses: actions/upload-pages-artifact@v3` with `path: site/` |
| `.github/workflows/docs.yml deploy job` | `actions/deploy-pages` | needs: build, github-pages environment | VERIFIED | `needs: build`; `environment: name: github-pages`; `uses: actions/deploy-pages@v4` |
| `.github/workflows/ci.yml test job` | src/ doctest discovery | pytest with src/ in command | FAILED | `src/` IS in the command BUT `-m "mock or warehouse"` filter deselects ALL 377 tests (confirmed: 377 collected / 377 deselected / 0 selected) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DOCS-01 | 10-03 | Getting started guide with install, model definition, first query | SATISFIED | `docs/guides/installation.md` + `docs/guides/first-query.md` — complete 5-step walkthrough |
| DOCS-02 | 10-01 | API reference auto-generated from docstrings | SATISFIED | `scripts/gen_ref_pages.py` + mkdocstrings; `site/reference/cubano/` has 10 module groups |
| DOCS-03 | 10-03 | Query language guide: all Query methods | SATISFIED | `docs/guides/queries.md` — 8 methods documented with examples |
| DOCS-04 | 10-03 | Q-objects and AND/OR/NOT composition | SATISFIED | `docs/guides/filtering.md` — 9 lookup operators, composition patterns, precedence warning |
| DOCS-05 | 10-03 | Backend comparison: Snowflake vs Databricks | SATISFIED | `docs/guides/backends/overview.md` + snowflake.md + databricks.md — comparison table, per-backend guides |
| DOCS-06 | 10-01 | MkDocs + Material theme configured locally | SATISFIED | mkdocs.yml with Material theme, dark/light mode, copy-to-clipboard; `mkdocs build --strict` exits 0 |
| DOCS-07 | 10-01 | Explore and integrate useful mkdocs plugins | SATISFIED | 5 plugins active: search, gen-files, literate-nav, section-index, mkdocstrings |
| DOCS-08 | 10-04 | GitHub Actions workflow builds docs on push to main | SATISFIED | `docs.yml` triggers on push to main; build job runs `mkdocs build --strict` |
| DOCS-09 | 10-04 | Built docs auto-deploy to GitHub Pages | SATISFIED | deploy job uses `actions/deploy-pages@v4`; two-job pattern with pages: write permission |
| DOCS-10 | 10-02 | Examples in docstrings validated with doctest | PARTIALLY SATISFIED | 16 doctests pass locally. CI enforcement broken: marker filter excludes all tests from running in CI. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `.github/workflows/ci.yml` | 110 | `-m "mock or warehouse"` marker filter deselects all collected tests (377/377 deselected) | Blocker | CI test job runs 0 tests; doctest breakage not detected in CI; any regression in existing tests also goes undetected |

**Note:** The "TODO" occurrences in `docs/guides/codegen.md` and backend guides are intentional documentation of actual placeholder text in generated SQL output — they are not stub content.

### Human Verification Required

#### 1. Local docs site browsing

**Test:** Run `uv run --group docs mkdocs serve` and open http://localhost:8000
**Expected:** Material theme loads with dark/light mode toggle; card grid on landing page; left sidebar shows Home, Getting Started, Guides (with all subsections), API Reference; API reference pages show rendered docstrings for cubano.query, cubano.fields, etc.; copy-to-clipboard button on code blocks
**Why human:** Visual appearance and interactive theme behavior (dark mode toggle, copy button, search highlight) cannot be verified programmatically

#### 2. GitHub Pages deployment (after push to main)

**Test:** After a push to main, check GitHub Actions tab for the "Docs" workflow
**Expected:** Build job completes (mkdocs build --strict exits 0), Deploy job deploys to https://anentropic.github.io/cubano/
**Prerequisites:** GitHub Pages source must be set to "GitHub Actions" in Settings > Pages
**Why human:** Requires actual GitHub Actions run and repo configuration

### Gaps Summary

**One gap blocks the CI enforcement of doctest correctness (DOCS-10 partial):**

The `ci.yml` test step was updated to include `src/` for doctest discovery, but the `-m "mock or warehouse"` marker filter was retained. None of the 377 tests in the project have `mock` or `warehouse` markers — the majority of test functions use no marker at all. As a result, the CI command runs 0 tests per run. This means:

1. Broken docstring examples would NOT be caught in CI
2. ALL existing unit tests (test_query.py, test_engines.py, test_fields.py, etc.) also do not run in CI

The SUMMARY claimed "Doctest items collected from src/ via --doctest-modules have no markers, so they run unconditionally alongside marker-filtered tests" but this is incorrect — marker filtering in pytest excludes items with NO marker when a marker filter is specified. Items must explicitly match the filter expression to be selected.

**Fix:** Change the CI pytest command from:
```
uv run pytest tests/ src/ -m "mock or warehouse" -n auto -v
```
to one of:
- `uv run pytest tests/ src/ -n auto -v` (run all tests, no filter)
- `uv run pytest tests/ src/ -m "not warehouse" -n auto -v` (skip real warehouse tests)
- Keep the command AND add a separate step: `uv run pytest src/ --doctest-modules -v`

---

_Verified: 2026-02-17_
_Verifier: Claude (gsd-verifier)_
