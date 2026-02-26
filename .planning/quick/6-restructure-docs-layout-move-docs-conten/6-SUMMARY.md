---
phase: quick-6
plan: 1
subsystem: docs
tags: [mkdocs, docs-layout, restructure]

# Dependency graph
requires: []
provides:
  - docs markdown content at docs/src/ (was docs/)
  - gen-files script at docs/scripts/gen_ref_pages.py (was scripts/)
  - mkdocs.yml with docs_dir, updated script path, and updated edit_uri
affects: [docs, ci]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created:
    - docs/src/ (directory containing all markdown files)
    - docs/scripts/gen_ref_pages.py (moved from scripts/)
  modified:
    - mkdocs.yml

key-decisions:
  - "docs/src/ is now the canonical MkDocs docs_dir (overrides default docs/)"
  - "docs/scripts/ holds build scripts; scripts/ retains only warehouse connections files"
  - "edit_uri updated to edit/main/docs/src/ so GitHub edit links point to correct path"

patterns-established:
  - "Docs content under docs/src/, build scripts under docs/scripts/, warehouse scripts under scripts/"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-02-19
---

# Quick Task 6: Restructure Docs Layout Summary

**Moved 13 markdown files from docs/ to docs/src/ and gen_ref_pages.py from scripts/ to docs/scripts/, with mkdocs.yml updated to match; mkdocs build --strict passes.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-02-19T00:00:00Z
- **Completed:** 2026-02-19T00:05:00Z
- **Tasks:** 2
- **Files modified:** 15 (14 moved, 1 edited)

## Accomplishments
- All 13 markdown docs files moved to docs/src/ via git mv (history preserved)
- gen_ref_pages.py moved from scripts/ to docs/scripts/ via git mv
- mkdocs.yml updated with docs_dir, new script path, and corrected edit_uri
- mkdocs build --strict exits 0 with no errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Move files with git mv** - `d9235cc` (chore)
2. **Task 2: Update mkdocs.yml** - `94e33d6` (chore)

## Files Created/Modified
- `docs/src/index.md` - Homepage content (moved from docs/index.md)
- `docs/src/changelog.md` - Changelog content (moved from docs/changelog.md)
- `docs/src/guides/` - All 11 guide markdown files (moved from docs/guides/)
- `docs/scripts/gen_ref_pages.py` - Gen-files script (moved from scripts/)
- `mkdocs.yml` - Added docs_dir: docs/src, updated script path, updated edit_uri

## Decisions Made
- `docs_dir: docs/src` placed immediately after `edit_uri` line in mkdocs.yml (before `theme:` block)
- gen-files script path: `scripts/gen_ref_pages.py` -> `docs/scripts/gen_ref_pages.py`
- edit_uri: `edit/main/docs/` -> `edit/main/docs/src/`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Docs layout is clean: docs/src/ for content, docs/scripts/ for build scripts, scripts/ for warehouse connections
- mkdocs build --strict confirmed working
- Edit links on published pages will now point to the correct GitHub path (docs/src/)

---
*Phase: quick-6*
*Completed: 2026-02-19*
