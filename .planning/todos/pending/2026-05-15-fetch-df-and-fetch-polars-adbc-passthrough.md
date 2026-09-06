---
created: 2026-05-15T00:00:00.000Z
title: fetch_df() and fetch_polars() ADBC passthrough methods on SemolinaCursor
area: api
resolves_phase: 49
files:
  - src/semolina/cursor.py
  - docs/src/how-to/arrow-output.rst
---

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
