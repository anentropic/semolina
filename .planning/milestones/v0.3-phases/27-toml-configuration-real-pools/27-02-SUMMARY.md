---
phase: 27-toml-configuration-real-pools
plan: 02
subsystem: api
tags: [toml, config, pool, adbc-poolhouse, registry]

# Dependency graph
requires:
  - phase: 27-toml-configuration-real-pools (plan 01)
    provides: pool_from_config function in config.py
provides:
  - pool_from_config in semolina public API (__init__.py + __all__)
  - .semolina.toml.example with new [connections.name] format
  - Proper ADBC pool cleanup in registry.reset() via close_pool()
affects: [28-arrow-cursor-integration, 29-docs-migration-guide]

# Tech tracking
tech-stack:
  added: []
  patterns: [lazy import in function body for testing-only code paths]

key-files:
  created: []
  modified:
    - src/semolina/__init__.py
    - src/semolina/registry.py
    - .semolina.toml.example
    - tests/unit/test_registry.py

key-decisions:
  - "Lazy import of close_pool inside reset() to avoid adding adbc_poolhouse as module-level import to registry.py"
  - "hasattr(_adbc_source) check distinguishes real ADBC pools from MockPool for backward-compatible reset()"

patterns-established:
  - "Lazy imports in function body for testing-only code paths that depend on optional packages"

requirements-completed: [CONF-03]

# Metrics
duration: 2min
completed: 2026-03-17
---

# Phase 27 Plan 02: Public API Export & Registry Close Pool Summary

**pool_from_config exported in semolina public API, TOML example updated to [connections.name] format, registry.reset() uses close_pool for ADBC pools**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-17T09:16:54Z
- **Completed:** 2026-03-17T09:19:12Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- pool_from_config importable via `from semolina import pool_from_config` (added to __init__.py and __all__)
- .semolina.toml.example replaced with new [connections.name] format using correct adbc-poolhouse field names
- registry.reset() uses close_pool() for proper ADBC resource cleanup, falls back to pool.close() for MockPool

## Task Commits

Each task was committed atomically:

1. **Task 1: Export pool_from_config and update TOML example** - `55e4ad5` (feat)
2. **Task 2: Improve registry.reset() to use close_pool for adbc-poolhouse pools** - `2a34c80` (feat)

## Files Created/Modified
- `src/semolina/__init__.py` - Added pool_from_config import and __all__ entry
- `.semolina.toml.example` - Replaced old format with new [connections.name] TOML structure
- `src/semolina/registry.py` - Updated reset() to use close_pool() for ADBC pools with hasattr fallback
- `tests/unit/test_registry.py` - Added test_reset_uses_close_pool_for_adbc_pools test

## Decisions Made
- Used lazy import of `close_pool` inside `reset()` function body rather than module-level import, since registry.py does not otherwise import adbc_poolhouse and reset() is testing-only
- Used `hasattr(pool, "_adbc_source")` to distinguish ADBC pools from MockPool, maintaining backward compatibility

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 27 (TOML Configuration & Real Pools) is fully complete
- pool_from_config is part of the public API and discoverable
- Registry properly cleans up both ADBC and mock pools
- Ready for Phase 28 (Arrow Cursor Integration)

## Self-Check: PASSED

All files verified present, all commit hashes found in git log.

---
*Phase: 27-toml-configuration-real-pools*
*Completed: 2026-03-17*
