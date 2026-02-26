---
created: 2026-02-20T00:22:53.126Z
title: DB migrations system
area: api
files: []
---

## Problem

Cubano defines SemanticView models but has no mechanism for managing schema migrations as models evolve. When a field is added, renamed, or its type changes, there's no tooling to generate or apply SQL migrations — this is entirely left to the user. As the library grows toward production use, this becomes a meaningful gap.

Open question: is there an ORM-agnostic migrations library we can build on, or should we design something purpose-built for analytic/warehouse schemas?

## Solution

Research ORM-agnostic migration frameworks (e.g. Alembic without SQLAlchemy ORM, Flyway-style plain SQL, yoyo-migrations, migra for Postgres schema diffing). Evaluate fit for data warehouse backends (Snowflake, Databricks) where DDL semantics differ from OLTP. Design a cubano-native migration CLI command or plugin that can diff SemanticView definitions against live schemas and emit migration SQL.
