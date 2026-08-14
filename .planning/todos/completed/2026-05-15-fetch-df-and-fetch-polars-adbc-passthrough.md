---
created: 2026-05-15T00:00:00.000Z
updated: 2026-08-14T00:00:00.000Z
title: fetch_df() and fetch_polars() ADBC passthrough methods on SemolinaCursor
area: api
resolves_phase: 49
files:
  - src/semolina/cursor.py
  - docs/src/how-to/arrow-output.rst
---

## Status

**Retired by Phase 49 (`.into(DTO)` Typed Results), 2026-08-14.** RESULT-01 and RESULT-02
both shipped. Against the acceptance list:

- `SemolinaCursor.fetch_df()` and `fetch_polars()` exist, plus the `AsyncSemolinaCursor`
  twins, which the list did not ask for because async did not exist when it was written.
- The guard was the genuinely open part, and it is where the work went. Both layers
  deliberately refuse to pre-check: adbc-poolhouse never imports pandas, and ADBC does a
  bare `import polars` inside the fetch. Semolina now raises
  `SemolinaMissingDependencyError` naming the extra that fixes it, via a `find_spec`
  guard that imports nothing. The guard sets were read from the installed ADBC source
  rather than assumed — `fetch_df` needs pyarrow *and* pandas (it is
  `self.reader.read_pandas()`, and the `reader` property calls `_requires_pyarrow()`
  first), while `fetch_polars` needs polars only, because ADBC hands polars the raw Arrow
  PyCapsule stream and never builds a reader.
- Extras: `[pandas]`, `[polars]` and `[pyarrow]` are declared, and `[all]` covers them.
- "Update `docs/src/how-to/arrow-output.rst` to prefer these where applicable" — done.
  The page now leads with both methods and keeps `table.to_pandas()` documented, demoted,
  for a reader who already holds a table.
- "Tests across all three backends" is the one line only partly met. Both methods are
  covered by unit tests on both cursors, and `fetch_polars()`'s behaviour on a decimal
  column was measured live against DuckDB in `tests/type_fidelity_probe.py`. No
  per-backend integration test calls either method, so Snowflake and Databricks are
  covered by the delegation being a two-line passthrough rather than by a cassette. Both
  methods are pure ADBC passthroughs with no Semolina-side branch by backend, which is
  why that was accepted rather than closed.

## Problem

Users who want results as Pandas or Polars DataFrames currently have to call `fetch_arrow_table()` and convert manually (`.to_pandas()`, `pl.from_arrow(...)`), or stream batches and convert each one. The underlying ADBC cursor exposes `fetch_df()` and `fetch_polars()` directly, but Semolina doesn't surface them.

Surfaced during Phase 40 (Streaming How-To Guide) — the alternative was documenting batched conversion workarounds in the how-to, which is worse for users than just adding the methods.

## Solution

Add `fetch_df()` and `fetch_polars()` passthrough methods on `SemolinaCursor`, mirroring the `fetch_arrow_table()` / `fetch_record_batch()` pattern. Both delegate to the underlying ADBC cursor.

Acceptance:
- `SemolinaCursor.fetch_df()` returns `pandas.DataFrame`
- `SemolinaCursor.fetch_polars()` returns `polars.DataFrame`
- Pandas/Polars are optional deps — guard imports, raise actionable error if missing
- Update `docs/src/how-to/arrow-output.rst` to prefer these where applicable
- Tests across all three backends (Snowflake, Databricks, DuckDB)

## Notes

Previously tracked as backlog Phase 999.1 in ROADMAP.md. Moved to todo on 2026-05-15 — the backlog parking lot was the wrong home for an idea this concrete; it belongs in todos until promoted to an active phase.
