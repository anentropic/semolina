# Phase 46 — Deferred Items

Out-of-scope discoveries logged during execution. Not fixed in the plan that found them.

| Found in | Item | Why deferred |
|----------|------|--------------|
| 46-04 Task 2 | `_sales_query()` is now defined identically in three test modules (`test_async_engine.py`, `test_async_cursor.py`, `test_async_query.py`). 46-02-SUMMARY's handoff asked for promotion to `tests/conftest.py` on the third copy. | Promotion means converting a module-local helper into a fixture and threading it through ~16 call sites in two already-green modules, none of which 46-04 declares in `files_modified`. Pure churn against passing tests, with no behaviour change. A later plan in this phase that already touches those modules should absorb it. |
