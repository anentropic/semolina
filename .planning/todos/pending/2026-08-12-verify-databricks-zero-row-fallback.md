---
created: 2026-08-12T00:00:00.000Z
title: "Verify the Databricks zero-row schema fallback against a real metric view"
area: testing
files:
  - tests/type_fidelity_probe.py
  - tests/integration/conftest.py
  - .planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md
---

## Problem

The Databricks ADBC driver implements no `ExecuteSchema`. Its `go/statement.go` embeds
`driverbase.StatementImplBase` and defines no `ExecuteSchema`, so the inherited `driverbase-go`
default returns `StatusNotImplemented` (checked at Foundry `go/v0.1.3`). That leaves the zero-row
wrapper as the only route to a Databricks result schema without fetching rows.

Nobody has run it. `probe_schema`'s fallback branch has fired only on DuckDB, where the primary
route works as well, so it has never executed against a driver that genuinely refuses. Whether
the Databricks metric-view planner accepts a `WHERE 1=0` wrapper around a
`MEASURE(...) ... GROUP BY ALL` query is unanswered — `47-RESEARCH.md` carries it as assumption
A5, and it is broken window 2 in `.planning/WINDOWS.md`.

Note that replay does not answer this. `pytest-adbc-replay` serves `adbc_execute_schema` from the
recorded result table, so a replayed Databricks probe returns a schema regardless of what the
real driver does. Only a live run settles it.

## What to do

Run the wrapped query against a real Databricks metric view:

```sql
SELECT * FROM (SELECT MEASURE(m) FROM v GROUP BY ALL) WHERE 1=0
```

Then confirm the planner accepts it and that the returned schema matches the schema of the
unwrapped query executed for real. Record the result either way:

- **Accepted** — record a cassette for the fallback path, close broken window 2, and update
  `47-TYPE-FIDELITY.md`'s evidence-limitations entry.
- **Rejected** — Databricks has neither `ExecuteSchema` nor a working fallback. That is a Phase 48
  blocker, not a footnote: `--check` and DTO codegen would both need a different route on that
  backend (a real `LIMIT 0` execution, or metadata-only annotation with the source labelled).

Worth checking at the same time whether the driver has gained `ExecuteSchema` since `go/v0.1.3`.
It is still 0.1.x and moving, and a `yes` there makes the fallback question moot for Databricks.

## What it needs

**A live Databricks workspace** with a SQL warehouse and the `sales_view` metric view used by the
existing recordings under `tests/integration/cassettes/integration/test_queries/`, plus the
Foundry ADBC Databricks shared library on the machine running it. Phase 47 had neither credential
nor workspace in session, so it recorded the gap rather than asserting the answer.

If the warehouse is serverless, expect a wake-up cost — the wrapper genuinely compiles and runs.

## Why it matters

Phase 47's Decision 3 makes the query-time result schema the primary source of truth for a
field's type, with warehouse metadata as a labelled fallback. On Databricks the zero-row wrapper
is the only way to reach that primary source. Phase 48's `--check` (TYPE-07) and Phase 50's DTO
codegen (DTO-09, which promises a working fallback rather than a hard failure) both depend on
this answer.
