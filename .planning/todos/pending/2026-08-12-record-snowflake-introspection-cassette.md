---
created: 2026-08-12T00:00:00.000Z
title: "Record a Snowflake introspection cassette and add a NUMBER(10,2) fixture column"
area: testing
files:
  - tests/integration/test_introspect.py
  - tests/integration/conftest.py
  - .planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md
  - tests/type_fidelity_probe.py
---

## Problem

Two of Phase 47's six evidence limitations share one fix, and it is a single recording session.

**Snowflake introspection has no cassette.** `tests/integration/test_introspect.py` is
Databricks-only, and Snowflake introspection is covered nowhere else by a recording. Its only
other coverage is a hand-fed mock in `tests/unit/test_snowflake_engine.py`, which feeds
`{"type": "FIXED", "scale": 0}` in and asserts `int` comes out — it asserts the answer the type
map already produces, so quoting it as evidence would be circular. Phase 47 deliberately shipped
the derivation path instead: the Snowflake metadata cells in `47-TYPE-FIDELITY.md` are produced
by running the recording fixture's declared types through `snowflake_json_type_to_python` and are
labelled `derived-from-code` so a reviewer sees the derivation rather than inferring a
measurement. That labelling is honest, but the cells are still not measured.

**Snowflake decimal widening is not demonstrable.** The Snowflake recording fixture in
`tests/integration/conftest.py` declares `revenue NUMBER`, which is `NUMBER(38,0)` — already at
maximum precision. A `SUM` over it cannot widen, so the measured `decimal128(38, 0)` is
consistent with widening while demonstrating none of it. The DuckDB rows are the only place in
the artifact where widening is shown end to end.

## What to do

1. Add a `NUMBER(10,2)` column to the Snowflake recording fixture in
   `tests/integration/conftest.py` (alongside the existing `revenue NUMBER, cost NUMBER`), and
   add a metric over it to the semantic view so a `SUM` result type becomes observable.
2. Re-record with `pytest --adbc-record=new_episodes` against a live Snowflake account, including
   a `SHOW COLUMNS IN VIEW` cassette so Snowflake introspection stops being derived.
3. Point `tests/type_fidelity_probe.py`'s Snowflake metadata half at the new recording, so the
   provenance cell flips from `derived-from-code` to `cassette-file`.
4. Regenerate with `just type-fidelity` and update `47-TYPE-FIDELITY.md`'s evidence-limitations
   entries for the two gaps this closes.

While there, a Snowflake `COUNT` metric on the fixture would settle one more open case: Phase 47's
Decimal policy annotates the whole Snowflake `FIXED` family as `decimal.Decimal`, which covers
`COUNT` (reported as `NUMBER(38,0)`), and no recording in this repo measures it.

## Added by Phase 48 — two more gaps the same session closes

Phase 48 opened two broken windows whose only closer is this recording, so they are listed here
rather than as separate todos. One session, four gaps.

5. **Add a `VARIANT` column to the fixture and a field over it** (broken window 8). TYPE-06 maps
   `VARIANT` to `semolina.JsonValue`, and it is the one row of the Phase 48 annotation contract
   that `tests/unit/test_annotation_contract.py` cannot measure: nothing in this repo has a
   VARIANT or `variant` column, so nobody has seen what such a value arrives as. Once recorded,
   add the field to the cassette-backed half of `test_annotation_contract.py`, where `isinstance`
   settles it. `JsonValue` holds whether the value is raw JSON text or a parsed structure, so the
   likely outcome is confirmation rather than a map change — but it is unmeasured either way.
6. **Add a replayed CLI `--check` test** (broken window 9). `semolina codegen --check` has only
   ever run end to end against DuckDB. `check_view` calls `engine.introspect()` first, so without
   a Snowflake introspection recording there is nothing to replay and only the comparison core is
   covered (`tests/unit/codegen/test_annotation_check.py::TestSnowflakeFromTheCommittedRecording`,
   which reads the result schema with `pyarrow.ipc.open_file`). Step 2 above produces exactly the
   missing recording; with it, a replayed `--check` test belongs beside the live-DuckDB ones in
   `tests/unit/codegen/test_cli.py`.

## What it needs

**Live Snowflake credentials** for the account holding the recording fixture — the same ones used
for the existing query cassettes under
`tests/integration/cassettes/integration/test_queries/`. Nothing else. Phase 47 could not run
this because no Snowflake credential was available in its session, so the derivation path was
shipped on purpose rather than as a shortcut.

Before committing the new recordings, check `000_params.json` for anything the scrubber missed.

## Why it matters

`.planning/phases/47-type-fidelity-probe-decision-doc/47-DECISIONS.md` Decision 1 rests on the
Snowflake driver's `use_high_precision` default, which is driver-source evidence, plus one
measured scale-0 column. A real introspection cassette and a `NUMBER(10,2)` column turn both the
metadata side and the widening claim into measurements.
