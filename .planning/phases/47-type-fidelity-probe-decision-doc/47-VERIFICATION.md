---
phase: 47-type-fidelity-probe-decision-doc
verified: 2026-08-12T00:00:00Z
status: passed
score: 9/9 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 47: Type Fidelity Probe & Decision Doc Verification Report

**Phase Goal:** Settle, on evidence, how warehouse types map to Python — so every later typing
decision in this milestone rests on a measured answer rather than an assumption.
**Verified:** 2026-08-12
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A maintainer can read a committed, per-backend comparison of introspection-time field types against query-time `adbc_execute_schema` result types (ROADMAP SC1 / TYPE-01) | ✓ VERIFIED | `47-TYPE-FIDELITY.md` § "Field type comparison" carries 11 rows across duckdb (7), snowflake (2), databricks (2). `uv run python tests/type_fidelity_probe.py --check` exits 0 — committed artifact is byte-identical to a fresh regeneration, run independently by this verifier. |
| 2 | The comparison names each concrete disagreement rather than a pass/fail summary — decimal widening under SUM, `AVG(int)`→double, COUNT→int64, metric nullability on empty groups (ROADMAP SC2 / TYPE-01) | ✓ VERIFIED | `47-TYPE-FIDELITY.md` § "Named disagreements" has four numbered subsections, each with a minimal SQL query, measured Arrow type, Python value type, and a contrast case. Backed by `tests/unit/test_type_fidelity_duckdb.py::test_sum_decimal_widens_to_38`, `test_max_decimal_does_not_widen`, `test_avg_int_is_double`, `test_count_is_int64_and_never_null`, `test_min_int_is_int32`, `test_empty_group_nullability_is_not_uniform` — all 6 run independently by this verifier and pass. |
| 3 | A committed decision doc states the Decimal policy, the metric-nullability stance, and which source of truth codegen uses, each backed by cited evidence (ROADMAP SC3 / TYPE-02) | ✓ VERIFIED | `47-DECISIONS.md` Decisions 1–3, each citing a named `47-TYPE-FIDELITY.md` section or a source file/line (e.g. `src/semolina/cursor.py:281`, verified to be the literal `to_pylist()` call site; `type_map.py` lines 90-92, verified to be the literal `int`/`float` FIXED-scale split). |
| 4 | The decision doc records, per driver, whether `adbc_execute_schema` is implemented or needs the zero-row fallback (ROADMAP SC4 / TYPE-02) | ✓ VERIFIED | `47-DECISIONS.md` Decision 4 and `47-TYPE-FIDELITY.md` § "Driver capability" — Snowflake yes (refuses on bound params), Databricks no (zero-row only), DuckDB yes, each with pinned driver version and provenance. |
| 5 | Circular-evidence guard holds: the known-mismatch canary is real and still mismatching; provenance is data, not prose; the raw-Arrow bypass test genuinely reads the committed `.arrow` file; no cell compares Semolina's type map against itself | ✓ VERIFIED | `test_decimal_metric_disagrees_by_value` (run independently, passes) asserts `TODO: DECIMAL(38,2)` / `decimal128(38, 2)` / `decimal.Decimal` by literal. `probe_schema`/`probe_value_types` (the result half) never import `semolina.codegen.type_map` — confirmed by reading `tests/type_fidelity_probe.py`; only `collect_snowflake_rows`/`collect_databricks_rows` import it, and only to populate the `Mapped annotation` column, which the artifact's own header states "is the type map and is the thing under measurement." `test_recorded_snowflake_values_are_decimal` and `_recorded_table`/`_read_cassette_table` call `pyarrow.ipc.open_file` directly on `000_result.arrow` with no engine, no Semolina cursor, no replay plugin in the call path — confirmed by code read. `FidelityRow` has `metadata_provenance` and `result_provenance` as first-class dataclass fields rendered as table columns, not prose. |
| 6 | Capability claims and result-type claims are never conflated: the two tables share no column, and no replayed result is presented as capability evidence | ✓ VERIFIED | `CAPABILITY_HEADERS` = (Driver, Version checked, `adbc_execute_schema` implemented, Caveat, Fallback needed, Capability provenance) and `ARTIFACT_HEADERS` = (Backend, Field, Role, Warehouse type, Metadata provenance, Mapped annotation, Result Arrow type, Result provenance, Python value type, Verdict) — checked by inspection, zero token overlap. `tests/integration/test_type_fidelity.py` docstrings on `test_databricks_probe` explicitly state a pass there is "zero evidence about whether either driver implements `ExecuteSchema`." No automated test enforces this disjointness (WINDOWS.md #4, disclosed below) — it currently rests on naming discipline and review, and the artifact/doc say so rather than implying a guard exists. |
| 7 | Honesty about gaps: WINDOWS.md items 2 (unrun zero-row fallback against a genuinely-refusing driver), 3 (environment-dependent pandas row), 4 (no automated column-disjointness guard) are stated as limits, not implied as covered | ✓ VERIFIED | `47-TYPE-FIDELITY.md` § "Evidence limitations" states all three explicitly, each with "what would close it." `47-DECISIONS.md` § "Evidence limitations carried forward" mirrors them. `WINDOWS.md` carries them as `open` (not `waived`, not falsely `fixed`) — cross-checked against the artifact text, which matches word for word in substance. |
| 8 | Decision-doc citation discipline: every policy statement cites a named artifact section or source file; Decision 1's generalisation from one measured scale-0 column to the whole Snowflake `FIXED` family is honestly labelled driver-source rather than measured | ✓ VERIFIED | Read `47-DECISIONS.md` end to end — every decision's claims trace to `47-TYPE-FIDELITY.md` sections or source lines. The FIXED-family generalisation text reads verbatim: "the generalisation to the whole `FIXED` family rests on the driver docstring above rather than on a measured row per type. That generalisation is driver-source evidence, not measurement, and Phase 48 should treat it as such." No unlabeled leap found. |
| 9 | The Databricks zero-row-fallback carve-out (no workspace available) and the human checkpoint approval are recorded accurately rather than glossed | ✓ VERIFIED | `47-04-SUMMARY.md` states the gate was `checkpoint:human-verify gate="blocking", approved 2026-08-12` and that the Databricks fallback "was not run: no workspace was available... stated in four places — Decision 3, the artifact's evidence limitations, broken window 2, and a follow-up todo." All four locations checked and consistent. Follow-up todo `.planning/todos/pending/2026-08-12-verify-databricks-zero-row-fallback.md` exists. |

**Score:** 9/9 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/type_fidelity_probe.py` | Probe driver, fixture DDL, row model, renderer, `--write`/`--check` entry point | ✓ VERIFIED | 1892 lines; `main()` implements both modes; `--check` run independently, exits 0. |
| `tests/unit/test_type_fidelity_duckdb.py` | Live DuckDB canary + per-disagreement tests | ✓ VERIFIED | 13 tests total; 6 spot-checked here individually and pass; no `adbc_cassette` marker present (grep confirmed). |
| `tests/unit/test_type_fidelity_table.py` | Drift guard + vocabulary-disjointness guard | ✓ VERIFIED | 4 tests exactly, matching plan 47-03's pinned count: staleness, determinism, vocabulary-disjointness, no-value-column. |
| `tests/integration/test_type_fidelity.py` | Replay probes + raw-Arrow bypass check | ✓ VERIFIED | 274 lines, 6 tests: 2 replay probes, 2 replay-vs-raw-file equality checks, 1 raw-file-only value-type check, plus module docstring stating the capability/result-type distinction. |
| `.planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md` | Generated, committed comparison artifact | ✓ VERIFIED | Committed, regenerated bytes match (`--check` exit 0). |
| `.planning/phases/47-type-fidelity-probe-decision-doc/47-DECISIONS.md` | Normative decision doc | ✓ VERIFIED | 5 decisions, all cited; "What Phase 48 must change" table names exact `type_map.py` locations, verified accurate against current source. |
| `tests/integration/cassettes/.../test_type_fidelity/...` | Copied Snowflake and Databricks cassettes | ✓ VERIFIED | 6 files present (params/query/result × 2 backends); grepped for credentials/account identifiers/hosts — clean. |
| `docs/src/explanation/type-fidelity.rst` | User-facing Diataxis Explanation page | ✓ VERIFIED | Reachable from `docs/src/explanation/index.rst` toctree; `just docs-build` passed under `-W` (per pre-established check). Correctly separates "current runtime behaviour" from "annotations codegen doesn't yet emit" per its own closing note. |
| `.planning/todos/pending/2026-08-12-record-snowflake-introspection-cassette.md` | Follow-up todo | ✓ VERIFIED | Present. |
| `.planning/todos/pending/2026-08-12-verify-databricks-zero-row-fallback.md` | Follow-up todo | ✓ VERIFIED | Present. |
| `justfile` — `type-fidelity` recipe | Regeneration entry point | ✓ VERIFIED | `just type-fidelity` → `uv run python tests/type_fidelity_probe.py --write`, confirmed present at lines 22-24. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `DuckDBEngine.introspect()` (metadata half) | `probe_schema()` (result half) | Kept in separate columns with separate provenance in `FidelityRow` | ✓ WIRED | Confirmed no shared code path; result half never imports `type_map`. |
| `just type-fidelity` | `tests/type_fidelity_probe.py --write` → committed artifact → `test_type_fidelity_table.py` → `just test` | Regeneration + drift-guard chain | ✓ WIRED | Verified end to end: recipe exists, `--check` passes, tests are collected and pass in the full suite (pre-established) and re-confirmed for the DuckDB canary subset here. |
| `probe_schema()` (replay cursor) | raw `pyarrow.ipc.open_file` read of `000_result.arrow` | Independent-read equality tests | ✓ WIRED | `test_snowflake_replay_schema_matches_raw_arrow_file`, `test_databricks_replay_schema_matches_raw_arrow_file` exist and assert equality; part of the pre-established green full-suite run. |
| `47-DECISIONS.md` | `47-TYPE-FIDELITY.md` / source files | Citation on every policy claim | ✓ WIRED | Spot-checked multiple citations (cursor.py:281, type_map.py:90-92, driver source quotes) against actual files — all accurate. |
| `docs/src/explanation/index.rst` toctree | `docs/src/explanation/type-fidelity.rst` | toctree entry | ✓ WIRED | `type-fidelity` entry present at line 12 of index.rst. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Artifact regeneration is idempotent / not stale | `uv run python tests/type_fidelity_probe.py --check` | exit 0 | ✓ PASS |
| Decimal-mismatch canary holds by exact literal | `pytest -k test_decimal_metric_disagrees_by_value tests/unit/test_type_fidelity_duckdb.py` | 1 passed | ✓ PASS |
| Four named disagreements + contrast cases hold | `pytest -k "test_sum_decimal_widens_to_38 or test_avg_int_is_double or test_count_is_int64_and_never_null or test_empty_group_nullability_is_not_uniform" tests/unit/test_type_fidelity_duckdb.py` | 4 selected of the batch, all passed (ran as part of a 6-test batch, 6 passed) | ✓ PASS |
| Zero-row fallback agrees with `adbc_execute_schema` on DuckDB | `pytest -k test_zero_row_fallback_matches_execute_schema tests/unit/test_type_fidelity_duckdb.py` | 1 passed (in the same 6-test batch) | ✓ PASS |
| No secrets in committed cassettes | `grep -riE "account|password|token|snowflakecomputing|databricks.com|https://"` over the two copied cassette dirs | no matches | ✓ PASS |

(Full-suite pass — 1073 passed / 16 skipped, jaffle-shop 16 passed / 15 skipped, `prek run --all-files` all green, `just docs-build` green under `-W` — established by the orchestrator prior to this verification; not re-run here per the single-full-run constraint.)

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| TYPE-01 | 47-01, 47-02, 47-03 | Empirical per-backend comparison of introspection-time vs. query-time result types, run over existing Snowflake cassettes and jaffle-shop DuckDB | ✓ SATISFIED | `47-TYPE-FIDELITY.md`, 11-row comparison table, all 3 backends, generated from real DuckDB probing and real committed cassettes. |
| TYPE-02 | 47-04 | Committed type-mapping decision doc — Decimal policy, metric-nullability stance, source-of-truth choice | ✓ SATISFIED | `47-DECISIONS.md`, all three decisions stated with citations, plus Decision 4 (per-driver capability) and Decision 5 (non-gating filter typing). |

No orphaned requirements: `.planning/REQUIREMENTS.md` maps only TYPE-01 and TYPE-02 to Phase 47, and both are accounted for above. Both rows currently read `Pending` in `REQUIREMENTS.md` — per the phase's `<what_actually_matters_here>` instruction this is a deliberate suppression (per-plan marking withheld so the phase-completion step owns the update) and is **not** treated as a gap here; the substance of both requirements is met.

### Anti-Patterns Found

None found in the phase's modified files (`tests/type_fidelity_probe.py`, `tests/unit/test_type_fidelity_duckdb.py`, `tests/unit/test_type_fidelity_table.py`, `tests/integration/test_type_fidelity.py`, `47-DECISIONS.md`, `docs/src/explanation/type-fidelity.rst`). Grepped for `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`/"not yet implemented"/"coming soon" — the only hits are the deliberate `TODO_PREFIX` constant/behavior (a documented, tested renderer convention for unmapped types, not a debt marker) and quoted driver error-message text (`"executing schema with bound params not yet implemented"`, quoting `adbc-driver-snowflake`'s own error string as cited evidence, not an unfinished-work marker). No debt markers requiring `#issue`/`DEF-*` references were found.

### Human Verification Required

None outstanding. The one item that structurally required human judgment — plan 47-04's `checkpoint:human-verify` over the three policy calls in `47-DECISIONS.md` — was already run and approved during execution (`47-04-SUMMARY.md`: "approved 2026-08-12, not auto-approved"). The Databricks zero-row-fallback live check could not be run (no workspace) and is recorded as an open broken window (#2) plus a follow-up todo rather than silently skipped — this is a documented, accepted evidence gap for a later phase to close, not a pending verification item for this one.

### Gaps Summary

No gaps found. All four ROADMAP success criteria for Phase 47 are met with codebase evidence, not SUMMARY.md assertion: the comparison artifact is real, regenerable, and idempotent; each of the four named disagreements is backed by an individually-asserted, independently-run test; the decision doc's three (plus two non-gating) decisions are each traceable to a cited measurement or a labelled driver-source claim; and the per-driver capability table is complete. The circular-evidence risk this phase exists to guard against was audited directly against the source — the result-type code path never imports Semolina's own type map, the raw-Arrow bypass test genuinely reads committed bytes off disk with no Semolina code in the call path, and the capability/result-type claim tables share no column. Three broken windows (WINDOWS.md #2, #3, #4) remain deliberately open and are honestly disclosed in both the artifact and the decision doc rather than implied as closed — this matches the phase's own stated intent and is not treated as a blocking gap.

---

_Verified: 2026-08-12_
_Verifier: Claude (gsd-verifier)_
