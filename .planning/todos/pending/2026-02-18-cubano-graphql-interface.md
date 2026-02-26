---
created: 2026-02-18T15:23:19.220Z
title: cubano-graphql interface
area: api
files: []
---

## Problem

Cubano's query API is Python-only. Teams building APIs or dashboards that need to expose semantic view data to frontends or external consumers must write their own bridge layer between Cubano and their API surface.

A GraphQL interface would let Cubano models auto-generate a typed GraphQL schema — fields become query arguments, metrics/dimensions become selectable fields — making it trivial to expose semantic layer data over a standard API protocol without hand-writing resolvers.

## Solution

TBD — likely a separate package (`cubano-graphql`), probably built on Strawberry or Ariadne. Key design questions:
- Auto-generate GraphQL types from Cubano model classes (Metric → Float field, Dimension → String/filter arg)
- Map GraphQL query arguments to `.where()` filters and `.metrics()` / `.dimensions()` selections
- Handle engine selection (per-request context vs. global default)
- Could integrate with `django-cubano` for a full Django + GraphQL + Cubano stack
