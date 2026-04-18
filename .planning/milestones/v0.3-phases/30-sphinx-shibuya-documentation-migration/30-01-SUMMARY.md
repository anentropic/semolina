---
phase: 30-sphinx-shibuya-documentation-migration
plan: 01
subsystem: documentation
tags: [sphinx, shibuya, docs-tooling, migration]
dependency_graph:
  requires: []
  provides: [sphinx-scaffold, conf-py, toctree-structure]
  affects: [docs-build, pyproject-toml]
tech_stack:
  added: [sphinx, shibuya, sphinx-autoapi, sphinx-design, sphinx-copybutton]
  removed: [mkdocs, mkdocs-material, mkdocstrings, mkdocs-gen-files, mkdocs-literate-nav, mkdocs-section-index]
  patterns: [sphinx-autoapi-for-api-reference, napoleon-google-docstrings, shibuya-violet-accent]
key_files:
  created:
    - docs/src/conf.py
    - docs/src/index.rst
    - docs/src/tutorials/index.rst
    - docs/src/how-to/index.rst
    - docs/src/explanation/index.rst
  modified:
    - pyproject.toml
    - uv.lock
  deleted:
    - mkdocs.yml
    - docs/scripts/gen_ref_pages.py
    - docs/src/index.md
    - docs/src/tutorials/index.md
    - docs/src/how-to/index.md
    - docs/src/explanation/index.md
    - docs/src/reference/ (entire directory)
decisions:
  - "conf.py placed in docs/src/ to preserve existing source directory structure"
  - "autoapi_root set to 'reference' so sphinx-autoapi auto-adds its toctree entry without manual index"
  - "reference/ directory not listed in index.rst toctree since autoapi adds it automatically"
metrics:
  duration: 3min
  completed: "2026-04-09T12:17:26Z"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 7
---

# Phase 30 Plan 01: Sphinx Scaffold & Dependency Swap Summary

Replaced the MkDocs Material documentation stack with Sphinx + shibuya theme, creating the build foundation for the full content migration in Plans 02-03.

## One-liner

Sphinx scaffold with shibuya theme, autoapi, napoleon, and 4 toctree index.rst files replacing MkDocs Material stack.

## What Changed

### Task 1: Update pyproject.toml docs group and create conf.py (60c1ec5)

Replaced 6 MkDocs packages in pyproject.toml with 5 Sphinx packages: sphinx, shibuya, sphinx-autoapi, sphinx-design, sphinx-copybutton. Created `docs/src/conf.py` with shibuya theme (violet accent), sphinx-autoapi pointed at `../../src/semolina`, napoleon for Google-style docstrings, intersphinx for Python stdlib links, viewcode for source links, and nav_links matching the existing site navigation structure.

### Task 2: Create toctree index.rst files and delete MkDocs artifacts (9aad12c)

Created 4 RST index files with toctree directives:
- `docs/src/index.rst` -- root with tutorials, how-to, explanation sections (reference excluded since autoapi handles it)
- `docs/src/tutorials/index.rst` -- installation, first-query
- `docs/src/how-to/index.rst` -- all 9 how-to entries (backends/overview, backends/snowflake, backends/databricks, models, queries, filtering, ordering, codegen, warehouse-testing)
- `docs/src/explanation/index.rst` -- semantic-views

Deleted all MkDocs artifacts: mkdocs.yml, docs/scripts/gen_ref_pages.py, docs/scripts/ directory, docs/src/reference/ directory (all auto-generated reference .md files), and the 4 old .md index files replaced by .rst equivalents.

## Decisions Made

1. **conf.py in docs/src/**: Keeps the source directory flat and matches the existing project structure.
2. **autoapi_root = "reference"**: sphinx-autoapi automatically adds a toctree entry for the reference section, so no manual reference/index.rst is needed in the root toctree.
3. **No -W flag at this stage**: The build runs without -W since content pages (tutorials, how-tos, explanation) are still .md files not yet converted to .rst. Plans 02 and 03 will handle conversion, after which -W will pass.

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

- `sphinx-build docs/src docs/_build` exits 0 and produces HTML output in `docs/_build/`
- sphinx-autoapi discovers all semolina modules (26 source files processed)
- shibuya theme renders with violet accent color
- No MkDocs artifacts remain (mkdocs.yml, docs/scripts/, docs/src/reference/)
- pyproject.toml docs group contains all 5 Sphinx packages, no MkDocs packages

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 60c1ec5 | Replace MkDocs deps with Sphinx stack and create conf.py |
| 2 | 9aad12c | Create toctree index.rst files and delete MkDocs artifacts |

## Self-Check: PASSED

All created files verified present. All deleted files verified absent. Both commit hashes verified in git log.
