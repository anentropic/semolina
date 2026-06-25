---
quick_id: 260623-t6a
status: complete
date: 2026-06-23
---

# Quick Task 260623-t6a — Summary

**Task:** Remove legacy dead code uncovered during the pytest-adbc-replay migration —
(1) the unused `semolina.testing.credentials` module, and (2) the legacy native
`Engine.execute()` query path.

## Outcome: split

### Part 1 — `semolina.testing.credentials` removed ✅ (committed `9da2f4e`)
Deleted the module (`SnowflakeCredentials`/`DatabricksCredentials`), its
`semolina.testing` re-export, and `tests/unit/test_credentials.py`. Unused by `src/`
since credentials now come from `[connections.*]` in `.semolina.toml`. Stands on its
own.

### Part 2 — `Engine.execute()` removal → REVERTED, escalated to Phase 44
Mid-execution the user reconsidered: rather than *remove* `Engine.execute()`, it
should **route via the ADBC pool like everything else**. The in-progress removal was
reverted (working tree restored; nothing committed). Discussion then established that
the SQLAlchemy "Engine owns the pool + dialect" model is the right target, that
introspection works over ADBC (validated by live spike — `SHOW COLUMNS IN VIEW` is
byte-identical over ADBC vs native), and that this is a core-API redesign, not a
cleanup.

This became **Phase 44: Engine Owns the Pool** — design locked in
`.planning/phases/44-engine-owns-the-pool/44-CONTEXT.md`; ready for
`/gsd-plan-phase 44`.

## Note
Routed in via `/gsd-progress --do` → `/gsd-quick` on the
`gsd/pytest-adbc-replay-migration` branch (no quick-task branch). Ran on the main
tree (not a worktree) to reuse the configured `.venv` for the cassette-replay
verification.
