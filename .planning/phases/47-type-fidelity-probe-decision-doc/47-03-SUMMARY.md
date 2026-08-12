---
phase: 47-type-fidelity-probe-decision-doc
plan: 03
subsystem: testing
tags: [snowflake, databricks, adbc, cassette-replay, pyarrow, decimal, execute-schema, type-fidelity]

# Dependency graph
requires:
  - phase: 47-type-fidelity-probe-decision-doc
    plan: 01
    provides: "tests/type_fidelity_probe.py — probe_schema(), FidelityRow, classify_verdict(), render_artifact(), BACKEND_ORDER, the just recipe and the drift/disjointness guards"
  - phase: 47-type-fidelity-probe-decision-doc
    plan: 02
    provides: "The seven DuckDB rows, ProbeEvidence, render_disagreements / render_downstream_decimal, and the line-bounded comparison-table parser the guards use"
provides:
  - "All three backends in one comparison table: 7 duckdb + 2 snowflake + 2 databricks rows, per-cell provenance"
  - "A `## Driver capability` table answering adbc_execute_schema per driver from driver source, sharing no column with the comparison table"
  - "A `## Evidence limitations` section naming six gaps this phase cannot close, each with what would close it"
  - "tests/integration/test_type_fidelity.py — five tests: two replay probes plus the reviewer's raw-Arrow bypass check, promoted from a manual procedure"
  - "Two copied cassettes serving probe_schema() offline for Snowflake and Databricks"
  - "collect_snowflake_rows / collect_databricks_rows / render_capability_table / render_evidence_limitations"
affects: [47-04, 48-type-map, 49-into-dto, 50-codegen-dtos]

actuals:
  tokens: 14200
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Two-table separation by construction: a capability table and a result-type table that share no column header, so no cell can carry both kinds of claim"
    - "Artifact numbers sourced from the reviewer's own bypass path (pyarrow.ipc.open_file over the committed cassette), with a test asserting the replay cursor agrees field for field"
    - "Named cassettes (positional @pytest.mark.adbc_cassette('<path>')) let several tests replay one committed recording instead of demanding a copy per node id"

key-files:
  created:
    - tests/integration/test_type_fidelity.py
    - tests/integration/cassettes/integration/test_type_fidelity/test_snowflake_probe/adbc_driver_snowflake.dbapi/000_params.json
    - tests/integration/cassettes/integration/test_type_fidelity/test_snowflake_probe/adbc_driver_snowflake.dbapi/000_query.sql
    - tests/integration/cassettes/integration/test_type_fidelity/test_snowflake_probe/adbc_driver_snowflake.dbapi/000_result.arrow
    - tests/integration/cassettes/integration/test_type_fidelity/test_databricks_probe/adbc_driver_manager.dbapi/databricks/000_params.json
    - tests/integration/cassettes/integration/test_type_fidelity/test_databricks_probe/adbc_driver_manager.dbapi/databricks/000_query.sql
    - tests/integration/cassettes/integration/test_type_fidelity/test_databricks_probe/adbc_driver_manager.dbapi/databricks/000_result.arrow
  modified:
    - tests/type_fidelity_probe.py
    - tests/unit/test_type_fidelity_table.py
    - .planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md
    - .planning/phases/47-type-fidelity-probe-decision-doc/47-VALIDATION.md
    - .planning/WINDOWS.md

key-decisions:
  - "A capability claim and a result-type claim live in two tables sharing no column header; the capability column is named `Capability provenance` rather than `Provenance` so the disjointness is literal, not approximate"
  - "The artifact's Snowflake and Databricks numbers are read with pyarrow.ipc.open_file straight off the committed cassettes, never through the replay cursor; two tests assert the replay cursor returns the same schema"
  - "Snowflake metadata cells are derived and labelled `derived-from-code` (RESEARCH.md option b); the hand-fed mock in tests/unit/test_snowflake_engine.py is named in the artifact as deliberately unused"
  - "The DuckDB capability row is a live measurement, not a quote: ProbeEvidence gained probe_route so the one cell labelled `live` was actually observed this run"
  - "The two later replay tests use positional named cassettes rather than a third and fourth copy of the same recording"

patterns-established:
  - "Grep-target integrity in generated prose: textwrap breaking `derived-from-code` at its hyphen corrupts a provenance label a reviewer greps for, so wrapping disables hyphen and long-word breaking"
  - "A guard that matches a heading must match it as a whole line — the artifact now cites its own section names in prose, and a substring match opens the section at the citation"

requirements-completed: []  # TYPE-01 is now measured on all three backends, but the executor was instructed not to set requirement status; see "Requirement status" below.

coverage:
  - id: D16
    description: "probe_schema() serves Snowflake and Databricks offline from copied cassettes, asserting exact recorded Arrow types and the probe route"
    requirement: TYPE-01
    verification:
      - kind: integration
        ref: "tests/integration/test_type_fidelity.py#test_snowflake_probe"
        status: pass
      - kind: integration
        ref: "tests/integration/test_type_fidelity.py#test_databricks_probe"
        status: pass
    human_judgment: false
  - id: D17
    description: "The replay cursor and a raw pyarrow.ipc.open_file read of the same recording return the same schema field for field, so the artifact's numbers are checkable without a warehouse"
    requirement: TYPE-01
    verification:
      - kind: integration
        ref: "tests/integration/test_type_fidelity.py#test_snowflake_replay_schema_matches_raw_arrow_file"
        status: pass
      - kind: integration
        ref: "tests/integration/test_type_fidelity.py#test_databricks_replay_schema_matches_raw_arrow_file"
        status: pass
    human_judgment: false
  - id: D18
    description: "Snowflake's decimal128(38, 0) metric arrives as decimal.Decimal, measured off the cassette file with no engine fixture and no replay marker"
    requirement: TYPE-01
    verification:
      - kind: integration
        ref: "tests/integration/test_type_fidelity.py#test_recorded_snowflake_values_are_decimal"
        status: pass
    human_judgment: false
  - id: D19
    description: "The comparison table carries 11 rows across all three backends in fixed backend order, and the drift guard still reproduces the committed bytes"
    requirement: TYPE-01
    verification:
      - kind: integration
        ref: "just type-fidelity && uv run python tests/type_fidelity_probe.py --check"
        status: pass
      - kind: unit
        ref: "tests/unit/test_type_fidelity_table.py#test_committed_table_is_not_stale"
        status: pass
    human_judgment: false
  - id: D20
    description: "The per-driver adbc_execute_schema answer is stated from driver source at pinned versions, in a table that shares no column with the result-type table"
    requirement: TYPE-02
    verification: []
    human_judgment: true
    rationale: "Structural and citational, so no test settles it. A reviewer confirms three things: the `Capability provenance` column reads `driver-source` for Snowflake and Databricks and `live` only for DuckDB; the capability headers and ARTIFACT_HEADERS share no string; and the Databricks row reads `no` even though `test_databricks_probe` returns a schema through replay. Broken window 4 records that no automated guard enforces the second."
  - id: D21
    description: "Every gap this phase cannot close is named in writing rather than left as a silent absence"
    requirement: TYPE-02
    verification: []
    human_judgment: true
    rationale: "`## Evidence limitations` carries six entries: the missing Snowflake introspection cassette, Snowflake widening undemonstrable at NUMBER(38,0), the absent Databricks decimal column, the unrun Databricks zero-row fallback, Snowflake's undocumented AVG return type, and the Snowflake bind-parameter refusal as a Phase 48 --check constraint. A reviewer reads them and confirms each names what is missing, why, and what would close it."

duration: 12min
completed: 2026-08-12
status: complete
---

# Phase 47 Plan 03: Snowflake, Databricks, and the Two Claims Summary

**All three backends now sit in one comparison table, and the question "does this driver implement `adbc_execute_schema`" sits in a different table with no column in common — because a replayed probe answers the second question convincingly and the first one not at all.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 3
- **Files modified:** 12 (7 created, 5 modified)

## The four new rows

| Backend | Field | Role | Warehouse type | Metadata provenance | Mapped annotation | Result Arrow type | Result provenance | Python value type | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| snowflake | AGG("REVENUE") | metric | {"type": "FIXED", "scale": 0} | derived-from-code | int | decimal128(38, 0) | cassette-file | decimal.Decimal | mismatch |
| snowflake | COUNTRY | dimension | {"type": "TEXT"} | derived-from-code | str | string | cassette-file | str | match |
| databricks | country | dimension | string | cassette-file | str | string | cassette-file | str | match |
| databricks | measure(revenue) | metric | bigint | cassette-file | int | int64 | cassette-file | int | match |

The Snowflake metric row is the phase's headline restated with real recorded evidence: codegen would emit `Metric[int]` for a field whose values arrive as `decimal.Decimal`. It is a `mismatch` on the same two-valued vocabulary plans 47-01 and 47-02 used; `mapping-gap` was not reintroduced.

## The separation, and why it is two tables rather than two columns

`## Driver capability` carries three rows and six columns, none of which appear in `## Field type comparison`:

| Driver | Version checked | implemented | Fallback needed | Capability provenance |
|---|---|---|---|---|
| snowflake | `adbc-driver-snowflake` 1.10.0 (Foundry tag `go/v1.10.0`) | yes | only for parameterised queries | driver-source |
| databricks | Foundry `go/v0.1.3` | no | yes, the zero-row fallback is the only path | driver-source |
| duckdb | duckdb v1.5.5 | yes | no | live |

The Databricks row reads **no** while `test_databricks_probe` returns a schema through replay. That contradiction is the whole point: pytest-adbc-replay serves `adbc_execute_schema` by reading the recorded result table, so it succeeds whatever the driver does. The artifact says this in its own text under the capability table, and `test_databricks_probe`'s docstring says it at the point where a reader might mistake a green test for a capability claim.

The column was named `Capability provenance`, not `Provenance`, so "the two tables share no column" is checkable by string comparison rather than by interpretation.

## The DuckDB capability cell is measured, not quoted

Two of the three capability rows are citations of driver source at pinned versions — that is the only source that can answer them. The third is labelled `live`, and a cell labelled `live` in an evidence artifact has to have been observed. `ProbeEvidence` gained `probe_route`, so the DuckDB row's `yes` and its version string are both read off this run rather than typed in. Had DuckDB refused, the cell would read `no` with a `zero-row` route and nobody would have had to edit prose.

## Divergence from the plan's prediction, recorded rather than reconciled

The plan's `must_haves` specify "a Databricks row for `MEASURE("revenue")`". The recorded result column is **`measure(revenue)`** — lower-cased and unquoted, the name Databricks returned, not the `MEASURE("revenue")` that Semolina sent. The measurement was taken as found:

- `test_databricks_probe` asserts `{"measure(revenue)": "int64", "country": "string"}` and its docstring states the spelling difference explicitly.
- `DATABRICKS_FIELD_SOURCES` maps the result name `measure(revenue)` to the introspection column `revenue`, because the two halves of the comparison genuinely do not share a spelling on this backend.

No query, assertion, or expectation was adjusted to make `MEASURE("revenue")` come true. This is the one place in this plan where a predicted value and a measured value disagreed.

## Everything else matched RESEARCH.md

`decimal128(38, 0)`, `string`, `int64`, `decimal.Decimal`, `bigint` from the introspection payload, and the recorded `[]` params all came back as predicted on the first run. The three mechanics RESEARCH.md warned about (node-id-derived paths, `[]` versus `None` params, sqlglot-normalised SQL) all behaved exactly as described — the SQL built through `engine.dialect.create_builder()` hit both copied cassettes on the first attempt.

## Task Commits

1. **Task 1: Copy the two cassettes and probe them through replay** — `067ddeb` (feat)
2. **Task 2: Check the replayed schema against a raw Arrow read of the same cassette** — `f2cec74` (test)
3. **Task 3: Emit the Snowflake and Databricks rows, the driver-capability table, and the evidence limitations** — `163e71f` (feat)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The two new replay tests derived their own cassette paths**

- **Found during:** Task 2, first run
- **Issue:** pytest-adbc-replay derives a cassette directory from the node id, which is exactly the key link the plan states. It cuts both ways: `test_snowflake_replay_schema_matches_raw_arrow_file` derived `cassettes/integration/test_type_fidelity/test_snowflake_replay_schema_matches_raw_arrow_file/...`, which does not exist, and the run died with `CassetteMissError: Cassette directory does not exist`. Read as the plan instructs, that message is a *path* problem, not a key problem. The obvious response — copy the same recording into two more directories — would put four byte-identical copies of one recording in git for a plan whose prohibitions are about not multiplying recordings.
- **Fix:** Used the positional marker form, `@pytest.mark.adbc_cassette("integration/test_type_fidelity/test_snowflake_probe")`. The plugin resolves a named cassette as `cassette_dir / name / driver_module` and still appends the dialect differentiator, so both new tests replay the already-committed directories. This is the in-repo precedent from `tests/integration/test_async_queries.py`, where one cassette serves both loop backends for the same reason.
- **Files modified:** `tests/integration/test_type_fidelity.py`
- **Verification:** 5 passed; `git status --porcelain` on the source recordings is empty; no cassette was copied beyond Task 1's two.
- **Committed in:** `f2cec74`

**2. [Rule 3 - Blocking] `_parse_comparison_table` opened the section at a citation, not the heading**

- **Found during:** Task 3, after generating the artifact
- **Issue:** The guard did `markdown.split("## Field type comparison", 1)[1]`, a substring match. The new capability section says in prose that "`## Field type comparison` holds only the second" — a sentence the plan's `must_haves` require. The split therefore landed on that citation, the loop then hit the real heading line (which starts with `## `) and stopped immediately, leaving zero pipe lines and an `IndexError` in two of the four guards.
- **Fix:** Match the heading as a whole line, scanning `splitlines()` for `line.strip() == TABLE_HEADING`, with an assertion if no such line exists. The alternative — deleting the cross-reference — would have removed a required claim to keep a guard convenient.
- **Files modified:** `tests/unit/test_type_fidelity_table.py` (outside this plan's `files_modified`, same shape as plan 47-02's deviation 1)
- **Verification:** `uv run pytest tests/unit/test_type_fidelity_table.py -q` — 4 passed, as the acceptance criterion requires. Non-vacuity checked by parsing the committed artifact directly: the guard sees the 10 real headers and exactly 11 data rows in backend order, so it is reading the intended table rather than passing on an empty one.
- **Committed in:** `163e71f`

**3. [Rule 1 - Bug] `textwrap` corrupted `derived-from-code` inside an inline code span**

- **Found during:** Task 3, reading the generated evidence-limitations section
- **Issue:** `_paragraph` wrapped at width 92 with `textwrap`'s defaults, which break on hyphens. The rendered output contained `` `derived- `` at the end of one line and `` from-code` `` at the start of the next, so the code span rendered as `derived- from-code`. That label is the artifact's own circularity marker and the thing RESEARCH.md's reviewer procedure greps the provenance column for. A wrapper silently mangling it is a bug, not a formatting preference. `re-record` broke the same way.
- **Fix:** `break_long_words=False, break_on_hyphens=False`, with the reason in the docstring so nobody restores the default. Note the knock-on: all prose in the artifact re-wrapped, so the whole document was regenerated and re-committed.
- **Files modified:** `tests/type_fidelity_probe.py`
- **Verification:** `grep 'derived-$'` over the artifact returns nothing; `uv run python tests/type_fidelity_probe.py --check` exits 0.
- **Committed in:** `163e71f`

**4. [Rule 2 - Missing critical] `render_capability_table` takes measured evidence**

- **Found during:** Task 3
- **Issue:** The plan specifies `render_capability_table()` with no arguments and a DuckDB row whose provenance cell reads `live`. A no-argument renderer can only *assert* that DuckDB implements `ExecuteSchema` and can only quote a version string. `live` means measured in this process; a hand-typed `live` cell is precisely the class of unverified claim this phase exists to delete.
- **Fix:** Added `probe_route` to `ProbeEvidence` and gave the renderer the signature `render_capability_table(evidence)`. The DuckDB row's implemented/fallback cells are derived from the observed route and its version cell from `measure_versions`.
- **Files modified:** `tests/type_fidelity_probe.py`
- **Verification:** The artifact reads `duckdb v1.5.5 | yes | probed in this process and answered by the execute-schema route`; regenerating reproduces it byte for byte.
- **Committed in:** `163e71f`

**5. [Rule 3 - Blocking] `render_artifact` gained `leading_sections`**

- **Found during:** Task 3
- **Issue:** The required section order puts `## Driver capability` between the provenance legend and the comparison table, but `render_artifact(rows, sections)` could only append after the table. Making the capability table a trailing section would have inverted the plan's ordering; making it a required parameter would have broken `render_artifact(collect_duckdb_rows())` in `test_regeneration_is_deterministic`.
- **Fix:** A third parameter, `leading_sections: Sequence[str] = ()`, inserted after the legend. Both existing call shapes still work.
- **Files modified:** `tests/type_fidelity_probe.py`
- **Verification:** `uv run pytest tests/unit/test_type_fidelity_table.py -q` — 4 passed.
- **Committed in:** `163e71f`

**6. [Rule 2 - Missing critical] The capability provenance column was renamed to make disjointness literal**

- **Found during:** Task 3
- **Issue:** The plan names the capability column "provenance". The comparison table already has `Metadata provenance` and `Result provenance`. Three columns all called provenance, two of them carrying result-type claims and one a capability claim, is one careless edit away from the merged cell the whole plan exists to prevent.
- **Fix:** `Capability provenance`. The header tuples are now disjoint as strings, so "the two tables share no column" is checkable rather than argued.
- **Files modified:** `tests/type_fidelity_probe.py`
- **Verification:** `CAPABILITY_HEADERS` and `ARTIFACT_HEADERS` share no member; the acceptance criterion's provenance cells still read `driver-source`, `driver-source`, `live` exactly.
- **Committed in:** `163e71f`

### Carried forward, honoured not re-litigated

- Verdict vocabulary stays two-valued. Both new `derived-from-code` Snowflake rows score on the same rule; `mapping-gap` was not reintroduced.
- `render_disagreements` stays DuckDB-shaped, as plan 47-02 flagged. It was not extended and not duplicated per backend: the four named disagreements are DuckDB measurements, and the Snowflake and Databricks facts that would belong in such a section are gaps, so they went to `## Evidence limitations` where a gap can be stated as a gap.
- `## Downstream Decimal behaviour` was left backend-independent and undisturbed.
- No package installed. `git diff --exit-code pyproject.toml uv.lock` is clean.
- No cassette re-recorded. `git status --porcelain` on `tests/integration/cassettes/integration/test_queries/` is empty.

---

**Total deviations:** 6 auto-fixed (3 blocking, 3 missing-critical). No architectural decisions; no user input required.
**Impact on plan:** No scope creep. Deviations 4 and 6 have the same shape as plan 47-02's: the plan's own `must_haves` demanded a claim the plan's stated signature or naming could not support honestly, so the measurement or the distinction was strengthened rather than the claim asserted.

## Issues Encountered

**The RED sweep for Task 2.** All three bypass tests were written with their raw read pointed at the wrong cassette and run as a batch before any correction. The two schema-equality failures name the differing field names, which is what the acceptance criterion asks for. Verbatim:

```
>       assert _field_types(_probe(snowflake_engine)) == _recorded_field_types(DATABRICKS_CASSETTE)
E       assert {'AGG("REVENU...RY': 'string'} == {'measure(rev...ry': 'string'}
E
E         Left contains 2 more items:
E         {'AGG("REVENUE")': 'decimal128(38, 0)', 'COUNTRY': 'string'}
E         Right contains 2 more items:
E         {'country': 'string', 'measure(revenue)': 'int64'}
```

and its mirror image:

```
>       assert _field_types(_probe(databricks_engine)) == _recorded_field_types(SNOWFLAKE_CASSETTE)
E       assert {'measure(rev...ry': 'string'} == {'AGG("REVENU...RY': 'string'}
E
E         Left contains 2 more items:
E         {'country': 'string', 'measure(revenue)': 'int64'}
E         Right contains 2 more items:
E         {'AGG("REVENUE")': 'decimal128(38, 0)', 'COUNTRY': 'string'}
```

The third failed at the lookup rather than the assertion, which is itself the finding that the two backends do not share a field spelling:

```
>       values = [row['AGG("REVENUE")'] for row in rows]
E       KeyError: 'AGG("REVENUE")'
```

In every case the correction moved the *raw read* onto the matching recording. No expectation was loosened and no recorded value was reinterpreted.

**The credential check found nothing, as expected.** `grep -rilE 'password|token|account|\.snowflakecomputing\.com|\.databricks\.com'` over the copied tree returns no matches, and both `000_params.json` files read exactly `[]`. `adbc_scrub_keys` had already scrubbed the sources, and copying cannot reintroduce a key that was never recorded — but the check is cheap and this was a fresh commit of credential-adjacent files.

**Threat T-47-06 held without effort.** `collect_snowflake_rows` and `collect_databricks_rows` call `to_pylist()` on real recordings, and `_databricks_introspection_columns` parses a payload that contains an owner email, a catalog name, and a schema name. None of it can reach the artifact: `FidelityRow` has no value-bearing field, and only `type.name` and `is_measure` are read out of the introspection payload.

## The zero-row fallback still has not fired

Broken window 2 tracks that `probe_schema`'s fallback branch has never run against a driver that genuinely refuses `ExecuteSchema`. **It did not fire in this plan either.** Both replay probes report `route == "execute-schema"`, because pytest-adbc-replay answers `adbc_execute_schema` from the recorded table for both backends. The Snowflake bind-parameter refusal was not exercised: the recorded query this plan replays is the *unfiltered* `test_metric_with_dimension` shape with `[]` params, so no bound parameter ever reached the driver.

The window stays **open**, and it is not implied closed anywhere. What this plan did instead was write the constraint down where Phase 48 will read it: `## Evidence limitations` quotes the recorded `WHERE "COUNTRY" = ?` query verbatim from `test_filtered_by_dimension_snowflake_engine_`'s cassette and states that a `--check` over a filtered canonical query hits the refusal.

## Requirement status

`.planning/REQUIREMENTS.md` was **not** touched, on explicit instruction from the orchestrator ("Requirement status is NOT yours to set. Leave `.planning/REQUIREMENTS.md` alone — TYPE-01 and TYPE-02 are marked by the phase-completion step"). This contradicts plan 47-02's note to the next plan ("Mark `TYPE-01` complete"), so the conflict is recorded here rather than resolved unilaterally.

For whoever does mark it: TYPE-01 reads "an empirical comparison, per backend, ... over existing Snowflake cassettes and jaffle-shop DuckDB". All three backends are now measured and committed, so the substance of TYPE-01 is met. TYPE-02 is not — the decision doc is plan 47-04's deliverable.

## Known Stubs

None. Every function added is exercised by a test or by artifact generation, and no placeholder text was written.

## Broken window recorded

`.planning/WINDOWS.md` entry **4** (`deviation`, phase 47, open): **the two tables' column disjointness has no automated guard.** It is enforced by the naming choice in deviation 6 and by review. The disjointness is the mechanism behind threat T-47-08 — it is what stops a cell carrying both a capability claim and a result-type claim — but this plan's acceptance criteria pin `tests/unit/test_type_fidelity_table.py` at 4 tests, so no fifth guard was added. Renaming `Capability provenance` back to `Provenance` would merge the vocabularies silently. Closing it costs one test asserting `CAPABILITY_HEADERS` and `ARTIFACT_HEADERS` are disjoint.

Windows 2 and 3 were left open and untouched, as instructed.

## User Setup Required

None. No credential, service, or package was needed; everything replayed from committed cassettes or ran against in-memory DuckDB.

## Verification

- `uv run pytest tests/integration/test_type_fidelity.py -q` — **5 passed**, offline, no credentials.
- `just test` — **1073 passed, 16 skipped** (main suite), **16 passed, 15 skipped** (jaffle-shop). Green end to end.
- `prek run --all-files` — clean. No `# type: ignore` and no `# pyright: ignore` added.
- `just type-fidelity && uv run python tests/type_fidelity_probe.py --check` — exits 0; `git diff` on the artifact is empty.
- `uv run pytest tests/unit/test_type_fidelity_table.py -q` — 4 passed.
- `diff -r` between each copied cassette tree and its source — no differences.
- `grep -rilE 'password|token|account|\.snowflakecomputing\.com|\.databricks\.com'` over the copied tree — no matches.
- `git status --porcelain tests/integration/cassettes/integration/test_queries/` — empty.
- `git diff --exit-code pyproject.toml uv.lock` — clean.
- Artifact structure: `## Driver capability` has 3 data rows; `## Field type comparison` has 11 (7 duckdb, 2 snowflake, 2 databricks, in that order); `grep -c StatusNotImplemented` returns 2, one of them the Databricks capability row.

## Self-Check: PASSED

All seven created files exist on disk; all five modified files exist; all three task commits (`067ddeb`, `f2cec74`, `163e71f`) resolve in `git log`. The artifact carries a `## Driver capability` heading with 3 data rows whose provenance cells read `driver-source`, `driver-source`, `live`; a `## Evidence limitations` heading with 6 subsections; `decimal128(38, 0)` in a Snowflake result cell with `decimal.Decimal` beside it; and `bigint` in the Databricks metadata cell with provenance `cassette-file`.

---
*Phase: 47-type-fidelity-probe-decision-doc*
*Completed: 2026-08-12*
