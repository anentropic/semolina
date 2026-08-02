# Phase 46 — Deferred Items

Out-of-scope discoveries logged during execution. Not fixed in the plan that found them.

| Found in | Item | Why deferred |
|----------|------|--------------|
| 46-04 Task 2 | `_sales_query()` is now defined identically in three test modules (`test_async_engine.py`, `test_async_cursor.py`, `test_async_query.py`). 46-02-SUMMARY's handoff asked for promotion to `tests/conftest.py` on the third copy. | Promotion means converting a module-local helper into a fixture and threading it through ~16 call sites in two already-green modules, none of which 46-04 declares in `files_modified`. Pure churn against passing tests, with no behaviour change. A later plan in this phase that already touches those modules should absorb it. |

## From 46-06 (documentation)

- `docs/src/how-to/warehouse-testing.rst:36,83` still calls `close_pool(engine._pool)`.
  46-06 switched `connection-pools.rst` to `engine.dispose()` (the sanctioned teardown
  path since v0.6), leaving that page inconsistent. Not in 46-06's `files_modified`; the
  example is dated rather than wrong.
- Async cancellation / timeout / client-disconnect docs are deliberately unwritten,
  pending adbc-poolhouse 1.6.2 (open PR anentropic/adbc-poolhouse#43). The four sections a
  follow-up should add are listed in `46-06-SUMMARY.md` under "Deliberately omitted".
