---
phase: 39
plan: 02
type: execute
wave: 2
depends_on:
  - 39-01
files_modified:
  - tests/integration/test_queries.py
  - .planning/REQUIREMENTS.md
autonomous: true
requirements:
  - STREAM-01
  - STREAM-02
requirements_addressed:
  - STREAM-01
  - STREAM-02
user_setup: []

must_haves:
  truths:
    - "A cross-backend integration test exercises `for row in cursor:` end-to-end through a registered pool (the SC-3 success criterion is observably proven against real ADBC backends when run in record mode)."
    - "The integration test skips cleanly in replay mode (CI default) because MockEngine's MockCursor does not expose `fetch_record_batch`; behaviour matches the locked decision D-07 and the user-locked parity rule D-06."
    - "REQUIREMENTS.md Traceability table marks STREAM-01 and STREAM-02 as `Complete` (not `Pending`), satisfying success criterion SC-5."
    - "Requirement text for STREAM-01 and STREAM-02 in REQUIREMENTS.md still names the shipped method surface (`fetch_record_batch`, `for row in cursor:`) — verified at phase close per SC-4."
  artifacts:
    - path: "tests/integration/test_queries.py"
      provides: "test_streaming_iteration — cross-backend smoke covering Snowflake and Databricks via the backend_engine fixture"
      contains: "def test_streaming_iteration"
    - path: ".planning/REQUIREMENTS.md"
      provides: "Updated Traceability rows for STREAM-01 and STREAM-02 with Status=Complete"
      contains: "STREAM-01 | Phase 39 | Complete"
  key_links:
    - from: "tests/integration/test_queries.py::test_streaming_iteration"
      to: "SemolinaCursor.__iter__ / fetch_record_batch"
      via: "Sales.query().using('test').execute() → for row in cursor"
      pattern: "for row in cursor"
    - from: ".planning/REQUIREMENTS.md Traceability table"
      to: "Shipped method surface in src/semolina/cursor.py"
      via: "Status column updated to Complete"
      pattern: "STREAM-0[12].*Complete"
---

<objective>
Close out Phase 39 with cross-backend coverage and traceability:

1. Add a single `test_streaming_iteration` test in `tests/integration/test_queries.py` that exercises `for row in cursor:` through a registered pool, parametrized via the existing `backend_engine` fixture so it runs against Snowflake AND Databricks under `--snapshot-update`. In replay mode (CI default, MockEngine), the test skips because MockCursor has no `fetch_record_batch` — matching D-06 parity and D-07 gating.

2. Update `.planning/REQUIREMENTS.md` Traceability table to mark `STREAM-01` and `STREAM-02` as `Complete`, and verify the requirement text still matches the shipped method names (per success criterion SC-4 — the v0.4.0 `to_arrow()` → `fetch_arrow_table()` lesson).

Purpose: Satisfies success criteria SC-3 (cross-backend correctness via ADBC passthrough) and SC-5 (traceability updated at phase close, not deferred to milestone archive).

Output:
- One new test function in `tests/integration/test_queries.py`.
- Two rows updated in `.planning/REQUIREMENTS.md`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/39-streaming-arrow-output/39-RESEARCH.md
@.planning/phases/39-streaming-arrow-output/39-VALIDATION.md
@.planning/phases/39-streaming-arrow-output/39-01-SUMMARY.md
@CLAUDE.md
@tests/integration/test_queries.py
@tests/integration/conftest.py

<interfaces>
From tests/integration/test_queries.py (existing test shape to mirror):
```python
def test_single_metric(backend_engine: Any, snapshot: SnapshotAssertion) -> None:  # noqa: ARG001
    """Validate single metric query returns expected aggregated revenue."""
    cursor = Sales.query().using("test").metrics(Sales.revenue).order_by(Sales.revenue).execute()
    rows = [dict(row.items()) for row in cursor.fetchall_rows()]
    cursor.close()
    assert rows == snapshot
```

- `backend_engine` is parametrized via pytest indirection — produces `[snowflake_engine]` and `[databricks_engine]` variants automatically.
- In replay mode: `backend_engine` is `MockEngine` (no ADBC, no `fetch_record_batch`).
- In record mode (`--snapshot-update`): `backend_engine` is the real `SnowflakeEngine` / `DatabricksEngine` and ADBC streaming works.
- Both engines register a pool under the name `"test"` (see `semolina.register("test", engine)` in conftest at line 207).
- The `Sales` model at the top of `test_queries.py` defines `revenue`, `cost`, `country`, `region` columns.
- `cursor.execute()` returns a `SemolinaCursor`; the new `__iter__` from Plan 01 yields `Row` objects.

Locked gating decision (D-07):
- DuckDB ADBC integration is already covered by the unit tests in Plan 01 (`_make_adbc_cursor` + `TestStreamingIteration`).
- Snowflake/Databricks integration must NOT require credentials in CI. The natural gate: in replay mode, MockCursor lacks `fetch_record_batch` → test skips. This is option (a) from RESEARCH.md §Wave 0 Gaps, which is the default per D-07.

Output naming (per D-08):
- The test function MUST be named `test_streaming_iteration` to match the row already present in 39-VALIDATION.md per-task verification map (line 55).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add test_streaming_iteration to integration test suite</name>
  <files>tests/integration/test_queries.py</files>
  <read_first>
    - tests/integration/test_queries.py (entire file — `Sales` model definition at top, existing test patterns)
    - tests/integration/conftest.py lines 110-230 (snowflake_engine and databricks_engine fixtures, `is_recording` gating pattern, `backend_engine` parametrized fixture at line 338)
    - src/semolina/cursor.py (the just-shipped `__iter__`/`__next__` and `fetch_record_batch` from Plan 01)
    - .planning/phases/39-streaming-arrow-output/39-RESEARCH.md §Wave 0 Gaps (option (a) gating) and §Validation Architecture
    - .planning/phases/39-streaming-arrow-output/39-01-SUMMARY.md (confirms Plan 01 shipped the methods)
  </read_first>
  <action>
    Append a new test to `tests/integration/test_queries.py`:

    ```python
    def test_streaming_iteration(backend_engine: Any, snapshot: SnapshotAssertion) -> None:  # noqa: ARG001
        """Validate `for row in cursor:` streams Row objects across backends."""
        # MockEngine (replay mode) does not expose fetch_record_batch — streaming is
        # an ADBC-only surface. Skip in replay; record mode runs against real warehouses.
        if not hasattr(backend_engine, "_connection_params"):
            pytest.skip("Streaming iteration requires a real ADBC engine (run with --snapshot-update)")

        cursor = (
            Sales.query()
            .using("test")
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .order_by(Sales.country)
            .execute()
        )
        try:
            rows = [dict(row.items()) for row in cursor]
        finally:
            cursor.close()
        assert rows == snapshot
    ```

    Add `import pytest` at the top of the file if not already imported (check line 16-20 area). Note: existing tests use `backend_engine: Any` with `# noqa: ARG001` because the fixture's side effect (registering the pool) is what matters — mirror that convention exactly.

    Skip-mechanism reasoning (recorded for the executor):
    - In replay mode, `backend_engine` is `MockEngine` (conftest.py:204). `MockEngine` has no `_connection_params` attribute — only the real `SnowflakeEngine` / `DatabricksEngine` do (used in conftest teardown at line 217, 326). Using `hasattr(backend_engine, "_connection_params")` is a stable, dependency-free way to detect "is this a real ADBC engine?".
    - Alternative considered: `request.config.getoption("--snapshot-update")` would also work but requires injecting the `request` fixture. The hasattr check is local to the test and doesn't add a new fixture dependency.
    - In record mode, the cursor returned by `.execute()` wraps a real ADBC cursor, `for row in cursor:` exercises the full pool → connection → SemolinaCursor → `__iter__` → ADBC RecordBatchReader chain end-to-end. The snapshot fixture file is created on first `--snapshot-update` run and re-used in subsequent runs IF anyone re-runs the streaming test in record mode (which is the only mode it runs in).

    Snapshot file behaviour:
    - In replay mode this test is SKIPPED, so no snapshot mismatch occurs in CI.
    - When a maintainer runs `pytest --snapshot-update tests/integration/test_queries.py::test_streaming_iteration` with warehouse credentials available, syrupy writes the ambient snapshot the first time and asserts against it on subsequent record-mode runs.
  </action>
  <verify>
    <automated>uv run pytest tests/integration/test_queries.py::test_streaming_iteration -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "def test_streaming_iteration" tests/integration/test_queries.py` returns 1
    - `grep -E "for row in cursor" tests/integration/test_queries.py` matches at least once
    - `grep -E 'hasattr\(backend_engine, "_connection_params"\)' tests/integration/test_queries.py` matches (skip gate present)
    - `grep -E "pytest\.skip" tests/integration/test_queries.py` matches
    - Test collects without error: `uv run pytest tests/integration/test_queries.py::test_streaming_iteration --collect-only -q` exits 0
    - Test runs without error in CI/replay mode (must skip cleanly — exit code 0, "skipped" in output): `uv run pytest tests/integration/test_queries.py::test_streaming_iteration -v` exits 0 and stdout matches `SKIPPED` for both `[snowflake_engine]` and `[databricks_engine]` variants
    - `uv run prek run --all-files` exits 0 (no lint/type regressions)
    - Full unit + jaffle-shop suite still green: `just test` exits 0
  </acceptance_criteria>
  <done>
    `test_streaming_iteration` exists in `tests/integration/test_queries.py`, parametrized over `backend_engine`, skips cleanly in replay mode, and is ready to capture a real cross-backend snapshot under `--snapshot-update`. `prek` and `just test` are green.
  </done>
</task>

<task type="auto">
  <name>Task 2: Mark STREAM-01 and STREAM-02 Complete in REQUIREMENTS.md and verify text parity</name>
  <files>.planning/REQUIREMENTS.md</files>
  <read_first>
    - .planning/REQUIREMENTS.md (entire file — Traceability table at line 61, requirement text for STREAM-01 at line 14, STREAM-02 at line 15)
    - src/semolina/cursor.py (verify the shipped method names: `fetch_record_batch` and `__iter__/__next__`)
    - .planning/phases/39-streaming-arrow-output/39-01-SUMMARY.md (Plan 01 outcome)
    - .planning/ROADMAP.md (Phase 39 Success Criteria 4 and 5 — text-parity audit + close-time traceability)
  </read_first>
  <action>
    1. **Parity audit (manual cross-check, no edits required if both pass).** Confirm:
       - REQUIREMENTS.md line 14 names `cursor.fetch_record_batch()` → shipped method is `SemolinaCursor.fetch_record_batch()`. Match.
       - REQUIREMENTS.md line 15 names `for row in cursor:` → shipped method is `SemolinaCursor.__iter__`/`__next__` which makes that syntax work. Match.
       - If either does NOT match the shipped surface, the requirement text in REQUIREMENTS.md must be amended FIRST (per SC-4 — text and shipped names must reconcile). Then proceed to step 2. In this phase, both already match — verify and move on.

    2. **Update the Traceability table** (REQUIREMENTS.md lines 61-68). Change:
       ```
       | STREAM-01   | Phase 39 | Pending  |
       | STREAM-02   | Phase 39 | Pending  |
       ```
       to:
       ```
       | STREAM-01   | Phase 39 | Complete |
       | STREAM-02   | Phase 39 | Complete |
       ```
       Preserve exact column alignment of the existing table (other rows stay `Pending`).

    3. **Update the footer timestamp** (REQUIREMENTS.md last line):
       Replace `*Last updated: 2026-05-14 — Traceability populated by roadmapper (Phases 39–43)*`
       with `*Last updated: 2026-05-14 — STREAM-01 and STREAM-02 marked Complete at Phase 39 close*`.

    4. **Update the Coverage block** (lines 70-73) ONLY if the math changes. v0.5 still has 6 requirements; mapped/unmapped counts unchanged. Leave as-is.
  </action>
  <verify>
    <automated>grep -cE 'STREAM-0[12]\s*\|\s*Phase 39\s*\|\s*Complete' .planning/REQUIREMENTS.md</automated>
  </verify>
  <acceptance_criteria>
    - `grep -cE 'STREAM-0[12]\s*\|\s*Phase 39\s*\|\s*Complete' .planning/REQUIREMENTS.md` returns 2
    - `! grep -E 'STREAM-0[12]\s*\|\s*Phase 39\s*\|\s*Pending' .planning/REQUIREMENTS.md` (no Pending rows for STREAM-01/02 remain)
    - Other phase rows in Traceability still Pending: `grep -cE 'STREAM-03\|DKGEN-0[45]\|AUDIT-01.*\|\s*Pending' .planning/REQUIREMENTS.md` returns 4 (or `grep -c 'Pending' .planning/REQUIREMENTS.md` returns 4 — STREAM-03, DKGEN-04, DKGEN-05, AUDIT-01)
    - Footer timestamp updated: `grep -E 'STREAM-01 and STREAM-02 marked Complete' .planning/REQUIREMENTS.md` matches
    - Shipped-method-name parity: `grep "fetch_record_batch" src/semolina/cursor.py` matches AND `grep "fetch_record_batch" .planning/REQUIREMENTS.md` matches (both reference the same name — SC-4 satisfied)
  </acceptance_criteria>
  <done>
    REQUIREMENTS.md Traceability shows STREAM-01 and STREAM-02 as `Complete`. The shipped method names match the requirement text (parity verified per SC-4). Phase 39's documentation surface is closed.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Integration test → real warehouse | Only crossed in `--snapshot-update` record mode; in CI/replay the test skips. Credentials are loaded by existing conftest fixtures, no new credential paths added. |
| REQUIREMENTS.md → source of truth for shipped API | Documentation-only change; no executable code crosses this boundary. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-39-07 | Tampering | Documentation drift between REQUIREMENTS.md and shipped method names (the v0.4.0 `to_arrow()` → `fetch_arrow_table()` regression class) | mitigate | Task 2 step 1 is an explicit parity audit before marking Complete. Acceptance criterion greps for `fetch_record_batch` in both `src/semolina/cursor.py` and `.planning/REQUIREMENTS.md` — they must both reference the same name. |
| T-39-08 | Denial of Service | Integration test accidentally runs in CI without credentials → blocks merges | mitigate | `hasattr(backend_engine, "_connection_params")` skip gate. CI replay-mode runs skip cleanly with exit 0. Verified by acceptance criterion in Task 1 (test must show `SKIPPED` in replay-mode output). |
| T-39-09 | Information Disclosure | Snapshot file commits warehouse-specific data (table names, row counts) | accept | The Sales fixture data is synthetic (defined in conftest TEST_DATA at line 76) — no real customer data ever touches the snapshot. Matches the pattern of all 6 existing tests in `test_queries.py`. |
</threat_model>

<verification>
After both tasks complete:

1. `uv run pytest tests/integration/test_queries.py::test_streaming_iteration -v` — both backend variants SKIP cleanly in CI/replay mode (exit code 0).
2. `just test` — full unit + jaffle-shop suite green; integration tests still pass.
3. `uv run prek run --all-files` — clean (no lint/type regressions from the test addition or markdown edits).
4. `grep -cE 'STREAM-0[12]\s*\|\s*Phase 39\s*\|\s*Complete' .planning/REQUIREMENTS.md` returns 2.
5. `grep "fetch_record_batch" src/semolina/cursor.py` AND `grep "fetch_record_batch" .planning/REQUIREMENTS.md` both match — SC-4 parity confirmed.
</verification>

<success_criteria>
- Cross-backend integration test `test_streaming_iteration` exists, skips in replay mode, and is ready to run against real Snowflake/Databricks under `--snapshot-update`.
- REQUIREMENTS.md Traceability marks STREAM-01 and STREAM-02 as `Complete`.
- Requirement text in REQUIREMENTS.md still names the shipped method surface (`fetch_record_batch`, `for row in cursor:`) — parity audit (SC-4) passed.
- `prek run --all-files` clean; `just test` green.
- Phase 39 success criteria 3 (cross-backend), 4 (text parity), and 5 (traceability updated at close) are observably satisfied.
</success_criteria>

<output>
After completion, create `.planning/phases/39-streaming-arrow-output/39-02-SUMMARY.md` recording: the integration test gating strategy (hasattr probe on `_connection_params`), the parity audit outcome, the updated traceability rows, and any deferred items (none expected).
</output>
