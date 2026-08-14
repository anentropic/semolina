---
created: 2026-08-14T00:00:00.000Z
title: "polars 2.0 changes what fetch_polars() returns — the [polars] extra is deliberately uncapped"
area: api
files:
  - pyproject.toml
  - src/semolina/cursor.py
  - src/semolina/acursor.py
  - docs/src/how-to/arrow-output.rst
---

## Problem

`semolina[polars]` is declared as `polars>=1.0.0` with **no upper cap**, so it will one day
resolve polars 2.x — and `fetch_polars()` returns a different type there.

ADBC implements `fetch_polars()` as `polars.from_arrow(self.fetch_arrow())`, handing polars the
raw Arrow PyCapsule stream rather than a `pyarrow.Table`. polars already warns about that call
shape. Measured on adbc-driver-manager 1.12.0 + polars 1.43.2, emitted from
`adbc_driver_manager/dbapi.py:1543` during a `fetch_polars()` call:

```
FutureWarning: from_arrow(<ArrowStreamExportable>) will return a Series instead of a DataFrame
in 2.0. To avoid this warning, pass the ArrowStreamExportable to either `pl.DataFrame` or
`pl.Series` instead based on your desired output type.
```

So under polars 2.0, `cursor.fetch_polars()` returns a **`polars.Series`**, not a
`polars.DataFrame` — a silent return-type change in a passthrough Semolina does not own.

Note the project venv's adbc-driver-manager was 1.10.0 at the time of writing and does **not**
emit the warning; 1.12.0 does. So the absence of the warning locally is a driver-version
artefact, not evidence the problem is gone.

## Why it is uncapped anyway (Phase 49, PD-03)

A cap was considered and deliberately rejected. `[polars]` is a **published extra**, which is an
install contract (Phase 49 D-12, rated *costly*): a `polars>=1.0.0,<2.0` pin would hold every
Semolina user back from a polars major release on the strength of a break nobody has hit yet,
and lifting a cap later is its own release. A support burden shipped pre-emptively is still a
support burden.

The decision is therefore: no cap, and this todo instead of one.

## What to do when polars 2.0 ships

1. Re-run `cursor.fetch_polars()` against polars 2.x and confirm the return type actually did
   become a `Series` — the FutureWarning states an intent, not a shipped fact.
2. Check whether adbc-driver-manager fixed it upstream first. The clean fix belongs there
   (`pl.DataFrame(self.fetch_arrow())` instead of `pl.from_arrow(...)`), not in Semolina. If a
   fixed adbc-driver-manager exists, the answer is a floor bump on that package, not a cap on
   polars.
3. Only if upstream does not fix it: decide between capping `[polars]`, or normalising in
   Semolina's own `fetch_polars()` wrapper — and note that normalising means Semolina starts
   owning a return type it currently only passes through.
4. Whatever is decided, `docs/src/how-to/arrow-output.rst` and both cursors' `fetch_polars()`
   docstrings state a `polars.DataFrame` return and would need updating.

## Why it matters

`fetch_polars()` is one of RESULT-01's four passthrough methods and its return type is part of
Semolina's published surface even though the conversion is ADBC's. A user pinning
`semolina[polars]` and letting polars float would get a `Series` where their code expects a
`DataFrame`, with nothing in Semolina's changelog to explain it. This todo is what makes that
break a known one rather than a surprise.
