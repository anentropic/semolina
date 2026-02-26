---
created: 2026-02-18T15:43:03.757Z
title: MCP tools and agent skills interface
area: api
files:
  - src/cubano/models.py
  - src/cubano/registry.py
---

## Problem

LLM agents need structured, discoverable interfaces to query data. Cubano's typed models and registry are a natural fit — the model class already encodes the schema (field names, types, docstrings) that an LLM needs to construct valid queries. But there's no way for an agent to discover available models, enumerate their fields, or execute queries without writing Python.

Two concrete surfaces:
1. **MCP server** — expose registered Cubano models as MCP tools so Claude, Cursor, or any MCP-compatible agent can query semantic views directly from a chat or coding session.
2. **LangChain / LlamaIndex tools** — wrap `Model.query().execute()` as a structured tool with auto-generated input schema derived from the model's fields, so agents can call it with natural language → structured query translation.

## Solution

TBD — the model introspection API (`.metrics()`, `.dimensions()`) from Phase 10.1 makes schema generation straightforward. Key design questions:
- **MCP server:** `cubano-mcp` package with a `FastMCP` server that auto-registers one tool per Cubano model. Tool input schema = field names + types; tool output = JSON-serialized Result rows. Engine config via env vars or MCP server args.
- **Agent tools:** A `cubano.tools` module (or separate `cubano-langchain` package) providing `CubanoQueryTool(model=Sales, engine="default")` that generates a Pydantic input schema from the model's fields and executes the query.
- Both surfaces benefit from the bidirectional codegen todo (agents could also generate models from warehouse introspection).
