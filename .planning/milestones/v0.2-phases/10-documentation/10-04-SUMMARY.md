---
phase: 10-documentation
plan: "04"
subsystem: ci-docs
tags: [github-actions, mkdocs, docs-deployment, doctest, ci]
dependency_graph:
  requires: ["10-01", "10-02", "10-03"]
  provides: ["DOCS-08", "DOCS-09"]
  affects: [".github/workflows/docs.yml", ".github/workflows/ci.yml", "pyproject.toml"]
tech_stack:
  added: ["actions/upload-pages-artifact@v3", "actions/deploy-pages@v4"]
  patterns: ["two-job build+deploy", "doctest-modules CI discovery"]
key_files:
  created:
    - .github/workflows/docs.yml
  modified:
    - .github/workflows/ci.yml
    - pyproject.toml
decisions:
  - "Two-job pattern (build artifact then deploy) avoids need for `contents: write` permission — only `pages: write` and `id-token: write` required"
  - "Keep `-m 'mock or warehouse'` marker filter unchanged — doctest items have no marker so they run unconditionally alongside filtered tests"
  - "Use `uv sync --group docs` (not --dev) in docs build job — keeps build lean by excluding dev tooling"
  - "Added Documentation URL to pyproject.toml [project.urls] matching mkdocs.yml site_url for PyPI discoverability"
metrics:
  duration: "2 min"
  completed: "2026-02-17"
  tasks: 2
  files: 3
requirements-completed: [DOCS-08, DOCS-09]
---

# Phase 10 Plan 04: GitHub Actions Docs Build & Deploy Workflow Summary

GitHub Actions docs workflow using two-job build+deploy pattern with actions/deploy-pages and doctest discovery added to CI test step.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create .github/workflows/docs.yml | c447dff | .github/workflows/docs.yml |
| 2 | Update ci.yml + pyproject.toml | 6436bee | .github/workflows/ci.yml, pyproject.toml |

## What Was Built

### Task 1: docs.yml Workflow

Created `.github/workflows/docs.yml` with a two-job build-then-deploy pattern:

- **Build job:** checks out repo, installs docs dependencies via `uv sync --locked --group docs`, runs `mkdocs build --strict` (warnings are errors), uploads `site/` as a Pages artifact via `actions/upload-pages-artifact@v3`
- **Deploy job:** depends on `build`, uses `actions/deploy-pages@v4` to publish the artifact to GitHub Pages
- **Triggers:** push to `main` branch and `workflow_dispatch` for manual runs
- **Permissions:** `pages: write` + `id-token: write` only — no `contents: write` needed with this pattern
- **Concurrency:** `cancel-in-progress: true` prevents simultaneous deployments on rapid pushes
- **Secrets:** `DOCSEARCH_APP_ID` and `DOCSEARCH_API_KEY` injected into build step for Algolia search (graceful degradation if unset)
- **Setup note:** GitHub Pages source must be set to "GitHub Actions" in repo Settings > Pages (one-time manual step)

### Task 2: CI doctest discovery + Documentation URL

Updated `.github/workflows/ci.yml` test step:
- Renamed step from "Run pytest (Cubano)" to "Run pytest (Cubano + doctests)"
- Added `src/` to pytest command: `uv run pytest tests/ src/ -m "mock or warehouse" -n auto -v`
- Doctest items collected via `--doctest-modules` (already in `pyproject.toml addopts`) have no markers, so they run unconditionally alongside marker-filtered tests

Added `[project.urls]` table to `pyproject.toml`:
- Homepage, Documentation, Repository, Issues, Changelog URLs
- Documentation URL matches `mkdocs.yml` `site_url`: `https://anentropic.github.io/cubano/`
- PyPI uses this to surface the docs link on the package page

## Decisions Made

1. **Two-job pattern over `mkdocs gh-deploy`:** `actions/deploy-pages` is the GitHub-recommended modern approach — avoids `contents: write` permission, supports OIDC-based deployment, provides deployment URL output.

2. **Marker filter unchanged (`mock or warehouse`):** Doctest items collected from `src/` via `--doctest-modules` have no pytest markers. Marker filtering only excludes items with explicitly excluded markers — items with NO marker run unconditionally. So adding `src/` with the existing marker filter correctly runs doctests in every CI run.

3. **`uv sync --group docs` in build job:** Keeps the docs CI job lean by not installing dev tooling (basedpyright, ruff, pytest, etc.) that is only needed in the test/lint/typecheck jobs.

4. **`fetch-depth: 0` in checkout:** Required if `mkdocs-git-revision-date-localized` plugin is used; harmless otherwise.

## Deviations from Plan

None — plan executed exactly as written.

## Requirements Satisfied

- **DOCS-08:** GitHub Actions `docs.yml` workflow triggers on push to main and deploys to GitHub Pages via `actions/deploy-pages`
- **DOCS-09:** Deploy job uses `actions/deploy-pages` (not `mkdocs gh-deploy`) with least-privilege permissions

## Self-Check: PASSED

Files verified:
- FOUND: .github/workflows/docs.yml
- FOUND: .github/workflows/ci.yml (updated)
- FOUND: pyproject.toml (updated with [project.urls])

Commits verified:
- FOUND: c447dff (feat(10-04): add GitHub Actions docs build and deploy workflow)
- FOUND: 6436bee (feat(10-04): add src/ doctest discovery to CI and Documentation URL to pyproject)
