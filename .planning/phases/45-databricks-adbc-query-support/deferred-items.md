# Phase 45 — Deferred Items

Out-of-scope discoveries found during plan execution. NOT fixed here (scope boundary:
only auto-fix issues directly caused by the current task's changes).

## From 45-01 (literal-inlining)

1. **7 Databricks integration tests fail — cassettes not recorded (DBX-03)**
   - `tests/integration/test_queries.py::*[databricks_engine]` raise
     `CassetteMissError: Cassette directory does not exist — record first.`
   - Expected: the 7 `*_databricks_engine_` cassettes do not exist yet. RESEARCH +
     PATTERNS explicitly defer recording to a separate `autonomous: false` task
     (needs live Databricks creds + warm SQL Warehouse + Foundry ADBC driver).
   - Not a regression from 45-01. The recorded `000_query.sql` for the WHERE test
     will now show the inline-literal form (`` `country` = 'US' ``) + `000_params.json == []`.

2. **jaffle-shop suite: `ModuleNotFoundError: No module named 'semolina.testing.credentials'`**
   - `semolina-jaffle-shop/tests/conftest.py:275` imports
     `from semolina.testing.credentials import CredentialError, SnowflakeCredentials`.
   - That module does not exist under `src/semolina/testing/` (only `__init__.py`).
   - 28 collection-time ERRORS in the jaffle suite — a stale conftest import, unrelated
     to SQL dialect work. Pre-existing; introduced by an earlier refactor that moved/removed
     the credentials helper. Out of scope for 45-01.
