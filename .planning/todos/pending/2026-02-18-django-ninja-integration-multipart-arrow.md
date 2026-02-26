---
created: 2026-02-18T15:25:00.081Z
title: django-ninja integration with multipart/mixed JSON + Arrow response
area: api
files: []
---

## Problem

Cubano `Result` objects currently return Python `Row` lists — fine for in-process use but inefficient when serving query results over an HTTP API. Large result sets serialized as JSON are slow and wasteful; DataFrame conversions happen client-side with no schema information.

Apache Arrow IPC format is the ideal wire format for tabular data: columnar, zero-copy on the client, directly consumable by Pandas/Polars/DuckDB. A `multipart/mixed` response (part 1: JSON metadata with schema/query info, part 2: Arrow IPC binary) gives API consumers both human-readable context and a high-performance data payload in a single round-trip.

django-ninja (FastAPI-style async REST for Django) is a natural fit for hosting this — it handles OpenAPI schema generation, async views, and custom response types cleanly.

## Solution

TBD — likely a separate package or optional extra. Key design questions:
- Custom django-ninja response renderer that serializes `Result` → Arrow IPC via `pyarrow`
- `multipart/mixed` content type with boundary: part 1 = `application/json` (field names, types, row count, query metadata), part 2 = `application/vnd.apache.arrow.stream` (IPC stream)
- Client-side: single `requests` or `httpx` call, parse multipart, load Arrow buffer with `pyarrow.ipc.open_stream()`
- Schema inference: map Cubano field types (Metric/Dimension/Fact) to Arrow schema types
- Could integrate with `django-cubano` for settings-based engine config + ninja router registration
