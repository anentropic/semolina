---
created: 2026-02-18T15:18:32.430Z
title: Add a query interface to the CLI
area: api
files: []
---

## Problem

The cubano CLI currently supports only the `codegen` command (generating CREATE SEMANTIC VIEW SQL from models). There's no way to execute queries from the command line — users must write Python code to use the query API.

A CLI query interface would allow ad-hoc querying of semantic views without writing Python, useful for exploration, debugging, and scripting.

## Solution

TBD — likely a new `cubano query` command that accepts a model path and optional field/filter arguments, connects to a registered engine, and outputs results. Could support `--output json|table|csv` formats. Requires design work on how models and engines are specified at the CLI level (config file? env vars?).
