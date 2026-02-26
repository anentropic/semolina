# Phase 24 Deferred Items

## Pre-existing issues discovered during 24-04 execution

### docs/src/reference/cubano/codegen/models.md references deleted module

**Discovered during:** Task 2 verification (mkdocs build --strict)
**Status:** Pre-existing, not caused by 24-04 changes
**Evidence:** Docs build fails both before and after 24-04 task 1 commit

`docs/src/reference/cubano/codegen/models.md` was left behind when `src/cubano/codegen/models.py`
was deleted in Phase 24-02. The file references `cubano.codegen.models` which no longer exists.

**Fix:** Delete `docs/src/reference/cubano/codegen/models.md`

This was not fixed in 24-04 because it predates the plan's changes (scope boundary rule).
Should be addressed in a follow-up quick task.
