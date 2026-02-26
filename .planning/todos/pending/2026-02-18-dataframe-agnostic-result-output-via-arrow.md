---
created: 2026-02-18T15:27:12.996Z
title: DataFrame-agnostic result output via Arrow
area: api
files:
  - src/cubano/results.py
---

## Problem

Cubano `Result` currently returns `Row` objects (attribute + dict-style access). Users who want to do further analysis with Pandas, Polars, or DuckDB must manually convert. Adding `.to_pandas()` and `.to_polars()` would create hard optional dependencies and an ever-growing list of `.to_X()` methods for each library.

The open question: is Apache Arrow the right interchange? Arrow tables can be zero-copy converted to Pandas (`pa.Table.to_pandas()`), Polars (`pl.from_arrow()`), DuckDB (`duckdb.from_arrow()`), and more — making it a natural "return one thing, convert to anything" solution. But it adds `pyarrow` as a dependency (even optional), and it might be overkill when users just want `.to_pandas()`.

## Solution

TBD — needs design exploration. Options:
1. **Return `pyarrow.Table`** via `.to_arrow()` — single optional dep, users call `.to_pandas()` / `pl.from_arrow()` themselves. Clean, but adds pyarrow.
2. **Narwhals** — thin compatibility layer over Pandas/Polars/etc. with a unified API. Zero-copy where possible. Keeps Cubano dep-light.
3. **`__dataframe__` protocol** (PEP 679 / dataframe interchange protocol) — return a custom object implementing the protocol; Pandas/Polars can consume it directly. Most dep-free but least mature.
4. **Just `.to_pandas()` and `.to_polars()`** as optional-extra methods — pragmatic, discoverable, no new abstraction needed.

Arrow as the canonical output makes most sense if backends (Snowflake, Databricks) can return Arrow natively (both have Arrow-native drivers), avoiding double-conversion through Python Row objects entirely.
