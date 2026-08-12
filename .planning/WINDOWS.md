---
schema_version: 1
open_count: 8
waived_count: 0
fixed_count: 1
total_count: 9
last_updated: 2026-08-12T15:40:00.000Z
---

# Broken Windows Ledger

> Cross-phase defect register. `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 46 | deviation | docs/src/how-to/web-api.rst |  | Async cancellation/timeout/client-disconnect sections of docs/src/how-to/web-api.rst are still unwritten. Both blockers are now gone and only the writing remains. Blocker 1 (adbc-poolhouse cancelled-query deadlock) was fixed in 1.6.2 and the floor moved to it. Blocker 2 (semantic_view() ran its inner query on a new ClientContext, so it never read the interrupt flag adbc_cancel had set) was fixed in duckdb-semantic-views 0.12.0, published to the community CDN for DuckDB core 1.5.5 on 2026-08-11; the pin moved 1.5.3 -> 1.5.5 in the same change. Verified on one machine across both builds, interrupting at a tenth of the baseline: 0.10.3 returned at 3.22s of a 3.97s baseline (ran to completion), 0.12.0 returns at 0.55s of 3.21s. ASYNC-06's elapsed-time claim is now asserted on Semolina's own generated SQL in TestCancellationThroughAexecute, closing the verification gap; it is non-vacuous, since the old build fails the same assertion at 0.81 of baseline where the new one passes at 0.17. What is left is authoring the four sections with no caveat. | fixed |  | 2026-08-02T11:23:22.862Z | 2026-08-11T22:37:52.730Z |
| 2 | 47 | unrun-verify | tests/type_fidelity_probe.py |  | probe_schema's zero-row fallback branch has never fired against a driver that actually refuses ExecuteSchema — RESEARCH.md assumption A5 (Databricks metric-view planner accepting a WHERE 1=0 wrapper) remains unrun Re-confirmed 2026-08-12 by 48-04 against driver source rather than assumption: the Foundry Databricks ADBC driver still defines no ExecuteSchema at go/v0.1.2 (sha 0d25c45d44d8ecd09b40cba836ab734e7468f5bb), and go/statement.go is byte-identical at go/v0.1.3, so the newer tag would not change the answer; go/pkg/driver.go:1581-1605 fails the adbc.StatementExecuteSchema type assertion and returns ADBC_STATUS_NOT_IMPLEMENTED. The zero-row wrapper is therefore Databricks' only route to a result schema, and it remains unexercised against a refusing driver. Do not repeat this re-read; what is missing is a live workspace. | open |  | 2026-08-12T00:02:53.283Z |  |
| 3 | 47 | deviation | .planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md |  | The artifact's Downstream Decimal pandas row is environment-dependent: pandas is not a declared dependency and arrives only via databricks-sql-connector[pyarrow] under the 'all' extra. CI syncs --dev --extra all so the row measures there, but regenerating after a plain 'uv sync --dev' flips it to 'not measured' and turns test_committed_table_is_not_stale red for an environment reason rather than genuine drift. Documented in the section text; not fixed. The user-facing half of this is now documented rather than only recorded: 48-06 wrote the TIMESTAMP_NS environment dependence (a pandas.Timestamp when pandas is importable; microsecond truncation and a ValueError on sub-microsecond input when it is not) into docs/src/explanation/type-fidelity.rst per D-04. The artifact's regeneration hazard is unfixed. Correction to the command named above: regenerate under 'uv sync --all-groups --extra all', not 'uv sync --dev --extra all', which prunes the docs dependency group and breaks just docs-build (48-01). | open |  | 2026-08-12T00:20:32.562Z |  |
| 4 | 47 | deviation | .planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md |  | The '## Driver capability' and '## Field type comparison' tables are kept column-disjoint by naming convention and review only — there is no automated guard. The disjointness is the mechanism that stops a cell carrying both a capability claim and a result-type claim (threat T-47-08), but plan 47-03's acceptance criteria pinned tests/unit/test_type_fidelity_table.py at 4 tests, so no guard was added. A future editor renaming 'Capability provenance' to 'Provenance' would merge the vocabularies silently. Closing it costs one test asserting the two header tuples are disjoint. | open |  | 2026-08-12T00:39:54.404Z |  |
| 5 | 48 | unrun-verify | src/semolina/engines/sql.py |  | DBX-04 date/timestamp/Decimal literal forms are unverified against a live Databricks workspace; they rest on the cited literal grammars plus an offline inlining test | open |  | 2026-08-12T14:10:59.402Z |  |
| 6 | 48 | deviation | src/semolina/codegen/type_map.py |  | D-06: _DUCKDB_TYPE_MAP["INTERVAL"] = "datetime.timedelta" is known wrong and deliberately left unfixed. Measured 2026-08-12 through adbc_driver_duckdb.dbapi on duckdb 1.5.5 / pyarrow 24.0.0: a DuckDB INTERVAL column arrives over Arrow as month_day_nano_interval and to_pylist() yields a pyarrow.MonthDayNano, not a datetime.timedelta. No stdlib type describes MonthDayNano (a timedelta cannot carry a month component, whose length is not fixed), so choosing a replacement annotation is a design question Phase 48 specification does not cover. Phase 48 recorded it rather than widening scope; the mapping and its test are pinned so a future fix is a deliberate change rather than drift. What would close it: a decision on how Semolina represents a month-day-nano interval in an annotation. | open |  | 2026-08-12T14:19:52.769Z |  |
| 7 | 48 | unrun-verify | src/semolina/codegen/type_map.py |  | TYPE-05 is evidence-limited on its Databricks-interval half: a Databricks interval column stays unmapped and still emits a TODO. Phase 48 briefly annotated the day-time family datetime.timedelta on the strength of the documented type-object grammar ({"name": "interval", "start_unit": ..., "end_unit": ...}, docs.databricks.com sql-ref-syntax-aux-describe-table) and reverted it: no fixture, cassette, or recording anywhere in this repo contains a Databricks interval column, so what such a value actually arrives as over the Foundry ADBC driver is unmeasured. Every other annotation in the type map names a measured value, and shipping one unmeasured guess beside them would have made the contract weaker than it reads. The year-month family is unmappable in principle (a month has no fixed length). What would close it: one recording session against a live Databricks workspace with an INTERVAL DAY TO SECOND column on the metric view, then map it to whatever isinstance says. Tracked as .planning/todos/pending/2026-08-12-record-databricks-interval-column.md | open |  | 2026-08-12T14:29:54.748Z |  |
| 8 | 48 | unrun-verify | src/semolina/codegen/type_map.py |  | The VARIANT -> JsonValue annotation (TYPE-06) is the one row of the Phase 48 contract that tests/unit/test_annotation_contract.py cannot measure: no fixture, cassette, or recording in this repo contains a Snowflake VARIANT or Databricks variant column, so nobody has seen what such a value arrives as. It was NOT reverted, unlike the Databricks interval guess, because the claim is of a different strength: JsonValue is a union over the whole JSON value domain (str, int, float, bool, None, list, dict), so it holds whether a VARIANT arrives as raw JSON text or as a parsed structure. It is only wrong if the value is something outside that domain entirely, such as a pyarrow extension scalar or a driver-specific wrapper object. What would close it: a VARIANT column on the Snowflake recording fixture or a variant column on the Databricks one, then adding the field to the cassette-backed half of test_annotation_contract.py, where isinstance settles it. Same recording session as the Databricks interval and decimal gaps. | open |  | 2026-08-12T14:35:21.294Z |  |
| 9 | 48 | unrun-verify | src/semolina/cli/codegen.py |  | semolina codegen --check has only ever been run end-to-end against DuckDB. The Snowflake half of D-09's acceptance was narrowed to the comparison core (check_view over the committed test_snowflake_probe recording read with pyarrow.ipc.open_file) because this repo has NO Snowflake introspection cassette — tests/type_fidelity_probe.py states it verbatim — so engine.introspect() cannot be replayed and a full CLI --check on Snowflake is not runnable here. Databricks is unrun for the separate reason in entry 2 (no ExecuteSchema, zero-row wrapper never exercised against a live metric view). What would close it: a Snowflake introspection recording (SHOW COLUMNS IN VIEW for the recorded sales_view) added in the same session as the interval/VARIANT/decimal gaps, then a replayed CLI --check test alongside the live-DuckDB ones in tests/unit/codegen/test_cli.py. | open |  | 2026-08-12T15:20:16.846Z |  |

````json
[
  {
    "id": 1,
    "kind": "deviation",
    "phase": "46",
    "file": "docs/src/how-to/web-api.rst",
    "line": null,
    "description": "Async cancellation/timeout/client-disconnect sections of docs/src/how-to/web-api.rst are still unwritten. Both blockers are now gone and only the writing remains. Blocker 1 (adbc-poolhouse cancelled-query deadlock) was fixed in 1.6.2 and the floor moved to it. Blocker 2 (semantic_view() ran its inner query on a new ClientContext, so it never read the interrupt flag adbc_cancel had set) was fixed in duckdb-semantic-views 0.12.0, published to the community CDN for DuckDB core 1.5.5 on 2026-08-11; the pin moved 1.5.3 -> 1.5.5 in the same change. Verified on one machine across both builds, interrupting at a tenth of the baseline: 0.10.3 returned at 3.22s of a 3.97s baseline (ran to completion), 0.12.0 returns at 0.55s of 3.21s. ASYNC-06's elapsed-time claim is now asserted on Semolina's own generated SQL in TestCancellationThroughAexecute, closing the verification gap; it is non-vacuous, since the old build fails the same assertion at 0.81 of baseline where the new one passes at 0.17. What is left is authoring the four sections with no caveat.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-02T11:23:22.862Z",
    "resolved_at": "2026-08-11T22:37:52.730Z"
  },
  {
    "id": 2,
    "kind": "unrun-verify",
    "phase": "47",
    "file": "tests/type_fidelity_probe.py",
    "line": null,
    "description": "probe_schema's zero-row fallback branch has never fired against a driver that actually refuses ExecuteSchema \u2014 RESEARCH.md assumption A5 (Databricks metric-view planner accepting a WHERE 1=0 wrapper) remains unrun Re-confirmed 2026-08-12 by 48-04 against driver source rather than assumption: the Foundry Databricks ADBC driver still defines no ExecuteSchema at go/v0.1.2 (sha 0d25c45d44d8ecd09b40cba836ab734e7468f5bb), and go/statement.go is byte-identical at go/v0.1.3, so the newer tag would not change the answer; go/pkg/driver.go:1581-1605 fails the adbc.StatementExecuteSchema type assertion and returns ADBC_STATUS_NOT_IMPLEMENTED. The zero-row wrapper is therefore Databricks' only route to a result schema, and it remains unexercised against a refusing driver. Do not repeat this re-read; what is missing is a live workspace.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-12T00:02:53.283Z",
    "resolved_at": null
  },
  {
    "id": 3,
    "kind": "deviation",
    "phase": "47",
    "file": ".planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md",
    "line": null,
    "description": "The artifact's Downstream Decimal pandas row is environment-dependent: pandas is not a declared dependency and arrives only via databricks-sql-connector[pyarrow] under the 'all' extra. CI syncs --dev --extra all so the row measures there, but regenerating after a plain 'uv sync --dev' flips it to 'not measured' and turns test_committed_table_is_not_stale red for an environment reason rather than genuine drift. Documented in the section text; not fixed. The user-facing half of this is now documented rather than only recorded: 48-06 wrote the TIMESTAMP_NS environment dependence (a pandas.Timestamp when pandas is importable; microsecond truncation and a ValueError on sub-microsecond input when it is not) into docs/src/explanation/type-fidelity.rst per D-04. The artifact's regeneration hazard is unfixed. Correction to the command named above: regenerate under 'uv sync --all-groups --extra all', not 'uv sync --dev --extra all', which prunes the docs dependency group and breaks just docs-build (48-01).",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-12T00:20:32.562Z",
    "resolved_at": null
  },
  {
    "id": 4,
    "kind": "deviation",
    "phase": "47",
    "file": ".planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md",
    "line": null,
    "description": "The '## Driver capability' and '## Field type comparison' tables are kept column-disjoint by naming convention and review only \u2014 there is no automated guard. The disjointness is the mechanism that stops a cell carrying both a capability claim and a result-type claim (threat T-47-08), but plan 47-03's acceptance criteria pinned tests/unit/test_type_fidelity_table.py at 4 tests, so no guard was added. A future editor renaming 'Capability provenance' to 'Provenance' would merge the vocabularies silently. Closing it costs one test asserting the two header tuples are disjoint.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-12T00:39:54.404Z",
    "resolved_at": null
  },
  {
    "id": 5,
    "kind": "unrun-verify",
    "phase": "48",
    "file": "src/semolina/engines/sql.py",
    "line": null,
    "description": "DBX-04 date/timestamp/Decimal literal forms are unverified against a live Databricks workspace; they rest on the cited literal grammars plus an offline inlining test",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-12T14:10:59.402Z",
    "resolved_at": null
  },
  {
    "id": 6,
    "kind": "deviation",
    "phase": "48",
    "file": "src/semolina/codegen/type_map.py",
    "line": null,
    "description": "D-06: _DUCKDB_TYPE_MAP[\"INTERVAL\"] = \"datetime.timedelta\" is known wrong and deliberately left unfixed. Measured 2026-08-12 through adbc_driver_duckdb.dbapi on duckdb 1.5.5 / pyarrow 24.0.0: a DuckDB INTERVAL column arrives over Arrow as month_day_nano_interval and to_pylist() yields a pyarrow.MonthDayNano, not a datetime.timedelta. No stdlib type describes MonthDayNano (a timedelta cannot carry a month component, whose length is not fixed), so choosing a replacement annotation is a design question Phase 48 specification does not cover. Phase 48 recorded it rather than widening scope; the mapping and its test are pinned so a future fix is a deliberate change rather than drift. What would close it: a decision on how Semolina represents a month-day-nano interval in an annotation.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-12T14:19:52.769Z",
    "resolved_at": null
  },
  {
    "id": 7,
    "kind": "unrun-verify",
    "phase": "48",
    "file": "src/semolina/codegen/type_map.py",
    "line": null,
    "description": "TYPE-05 is evidence-limited on its Databricks-interval half: a Databricks interval column stays unmapped and still emits a TODO. Phase 48 briefly annotated the day-time family datetime.timedelta on the strength of the documented type-object grammar ({\"name\": \"interval\", \"start_unit\": ..., \"end_unit\": ...}, docs.databricks.com sql-ref-syntax-aux-describe-table) and reverted it: no fixture, cassette, or recording anywhere in this repo contains a Databricks interval column, so what such a value actually arrives as over the Foundry ADBC driver is unmeasured. Every other annotation in the type map names a measured value, and shipping one unmeasured guess beside them would have made the contract weaker than it reads. The year-month family is unmappable in principle (a month has no fixed length). What would close it: one recording session against a live Databricks workspace with an INTERVAL DAY TO SECOND column on the metric view, then map it to whatever isinstance says. Tracked as .planning/todos/pending/2026-08-12-record-databricks-interval-column.md",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-12T14:29:54.748Z",
    "resolved_at": null
  },
  {
    "id": 8,
    "kind": "unrun-verify",
    "phase": "48",
    "file": "src/semolina/codegen/type_map.py",
    "line": null,
    "description": "The VARIANT -> JsonValue annotation (TYPE-06) is the one row of the Phase 48 contract that tests/unit/test_annotation_contract.py cannot measure: no fixture, cassette, or recording in this repo contains a Snowflake VARIANT or Databricks variant column, so nobody has seen what such a value arrives as. It was NOT reverted, unlike the Databricks interval guess, because the claim is of a different strength: JsonValue is a union over the whole JSON value domain (str, int, float, bool, None, list, dict), so it holds whether a VARIANT arrives as raw JSON text or as a parsed structure. It is only wrong if the value is something outside that domain entirely, such as a pyarrow extension scalar or a driver-specific wrapper object. What would close it: a VARIANT column on the Snowflake recording fixture or a variant column on the Databricks one, then adding the field to the cassette-backed half of test_annotation_contract.py, where isinstance settles it. Same recording session as the Databricks interval and decimal gaps.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-12T14:35:21.294Z",
    "resolved_at": null
  },
  {
    "id": 9,
    "kind": "unrun-verify",
    "phase": "48",
    "file": "src/semolina/cli/codegen.py",
    "line": null,
    "description": "semolina codegen --check has only ever been run end-to-end against DuckDB. The Snowflake half of D-09's acceptance was narrowed to the comparison core (check_view over the committed test_snowflake_probe recording read with pyarrow.ipc.open_file) because this repo has NO Snowflake introspection cassette \u2014 tests/type_fidelity_probe.py states it verbatim \u2014 so engine.introspect() cannot be replayed and a full CLI --check on Snowflake is not runnable here. Databricks is unrun for the separate reason in entry 2 (no ExecuteSchema, zero-row wrapper never exercised against a live metric view). What would close it: a Snowflake introspection recording (SHOW COLUMNS IN VIEW for the recorded sales_view) added in the same session as the interval/VARIANT/decimal gaps, then a replayed CLI --check test alongside the live-DuckDB ones in tests/unit/codegen/test_cli.py.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-12T15:20:16.846Z",
    "resolved_at": null
  }
]
````
