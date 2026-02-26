---
created: 2026-02-18T15:42:10.866Z
title: FastAPI integration enhancements
area: api
files:
  - src/cubano/results.py
  - src/cubano/registry.py
---

## Problem

Cubano works in FastAPI today but has rough edges:

1. **`Result` / `Row` aren't JSON-serializable** — FastAPI's `jsonable_encoder` doesn't know how to handle them, so users must manually convert to dicts or lists before returning from route handlers.
2. **Engine lifecycle** — no idiomatic FastAPI lifespan hook for `cubano.register()` / `cubano.unregister()`. Users wire this up manually in `@app.on_event("startup")` or the newer `@asynccontextmanager` lifespan pattern.
3. **Dependency injection** — no `Depends()`-compatible engine provider. Getting the right engine per-request (e.g. per-tenant multi-engine setups) requires custom boilerplate.
4. **No Pydantic schema for `Result`** — can't declare `response_model=CubanoResult` in a route; no OpenAPI schema generated for query outputs.

## Solution

TBD — explore what minimal surface area makes Cubano feel native in FastAPI:
- `Result.__iter__` / `Row.__iter__` already exist — does `jsonable_encoder` pick these up? Test first before building anything.
- A `cubano.fastapi` optional module (or `cubano[fastapi]` extra) with: lifespan helper, `Depends(get_engine)` factory, and a `JSONResponse` subclass that handles `Result` serialization.
- Pydantic v2 `model_validator` / custom type approach for `Row` → auto-generated response schema.
- Arrow response via `StreamingResponse` with `media_type="application/vnd.apache.arrow.stream"` for large result sets (ties into the Arrow DataFrame todo).
