---
created: 2026-08-12T00:00:00.000Z
title: "Record a Databricks interval column so its annotation can be measured"
area: testing
files:
  - src/semolina/codegen/type_map.py
  - tests/unit/test_annotation_contract.py
  - tests/integration/conftest.py
  - .planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md
---

## Problem

A Databricks `interval` column stays unmapped. `databricks_type_to_python` returns `None` for
every interval shape, so codegen emits `Dimension[Any]()` with a `TODO: interval` comment and
the user picks a type by hand.

Phase 48 briefly mapped the day-time family to `datetime.timedelta`. Databricks documents the
type-object grammar (`{"name": "interval", "start_unit": "<start_unit>", "end_unit":
"<end_unit>"}`, `docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-describe-table`),
Databricks has two interval families, and a day-to-second interval is a fixed duration that
`datetime.timedelta` plausibly describes. It was reverted, because plausible is not measured:
no fixture, cassette, or recording anywhere in this repo contains a Databricks interval column,
so nobody has seen what one arrives as over the Foundry ADBC driver. Every other annotation in
the type map names a value someone measured, and one guess sitting among them would have made
the whole contract read stronger than it is.

The year-month family is a separate matter and does not need a recording: a month has no fixed
length, so no stdlib duration type describes it even in principle. It stays a `TODO:`
regardless of what this todo finds.

## What to do

Add an `INTERVAL DAY TO SECOND` column to the Databricks recording fixture's `sales_view`,
re-record `tests/integration/test_type_fidelity.py::test_databricks_probe` and the introspection
cassette, then read what the value actually is:

```python
with pyarrow.ipc.open_file(cassette_dir / "000_result.arrow") as reader:
    value = reader.read_all().to_pylist()[0]["the_interval_column"]
print(type(value))
```

Then map `interval` to whatever `isinstance` says — the same standard the rest of the contract
is held to. Candidates worth expecting: `datetime.timedelta`, or a `pyarrow.MonthDayNano` as
DuckDB produces (in which case the Databricks row joins DuckDB's `INTERVAL` as an unmappable
type rather than becoming a `timedelta`).

Then:

- add the column to `tests/unit/test_annotation_contract.py`'s Databricks parametrization, so
  the new annotation is measured rather than asserted;
- close the `unrun-verify` entry for it in `.planning/WINDOWS.md`;
- regenerate `47-TYPE-FIDELITY.md` and drop the interval line from its evidence limitations.

## What it needs

**A live Databricks workspace** with a SQL warehouse and permission to alter the `sales_view`
metric view the existing recordings under `tests/integration/cassettes/` use, plus the Foundry
ADBC Databricks shared library on the machine doing the recording. Worth doing in the same
session as
`.planning/todos/pending/2026-08-12-verify-databricks-zero-row-fallback.md`, which needs the
same workspace, and as the Databricks decimal column noted in `47-TYPE-FIDELITY.md`'s evidence
limitations — three gaps, one recording session.

## Why it matters

TYPE-05 asked that no category-1 type still emit a `TODO:` placeholder. Every DuckDB type in
that set now resolves; the Databricks interval is the one row that does not, and it is
outstanding for want of evidence rather than for want of code. The fix is a recording, and then
roughly one line of `_DATABRICKS_TYPE_MAP`.
