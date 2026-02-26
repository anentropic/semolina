---
created: 2026-02-23T15:21:41.996Z
title: Async query interface for FastAPI and async frameworks
area: api
files:
  - src/cubano/query.py
  - src/cubano/engines/snowflake.py
  - src/cubano/engines/databricks.py
  - src/cubano/registry.py
---

## Problem

Cubano's `.execute()` is synchronous — it blocks the event loop when called from an async FastAPI route handler. This forces users to either wrap calls in `run_in_executor()` or accept blocking their async application. The entire engine interface (connect, execute cursor, fetch results) is synchronous.

This is likely a prerequisite for the FastAPI integration todo — without async execute, Cubano can't be a first-class citizen in async web frameworks (FastAPI, Starlette, Litestar, Django async views).

Related todos:
- FastAPI integration enhancements (serialization, lifecycle, DI)
- Lazy/streaming Result (cursor-based iteration — async iteration via `__aiter__` would compound with this)

## Solution

TBD — options to explore:

- `await Sales.query().metrics(Sales.revenue).async_execute()` or `aexecute()`
- Async engine protocol (`AsyncEngine` base class with `async def execute()`)
- Whether Snowflake/Databricks connectors support async natively (snowflake-connector-python has no async; databricks-sql-connector is sync too) — may need `anyio.to_thread.run_sync()` wrapper
- Whether to use anyio (framework-agnostic) vs asyncio directly
- Interaction with lazy Result: `async for row in result` via `__aiter__`
